"""
Deja la planta en condiciones de correr el circuito completo de leche en polvo.

Qué prepara y por qué cada cosa
-------------------------------
El circuito —recepción, silo, vale, lote, pallet— se puede recorrer entero por
pantalla, pero hay tres cosas que **no** se crean desde ninguna pantalla y sin
las cuales el recorrido se detiene a mitad:

1. **El área de cada perfil.** El desplegable «Responsable de la prueba» del
   muestreo se llena con los usuarios del área Recepción. Con la base como
   viene —ningún perfil tiene área— la lista sale vacía, el botón de confirmar
   queda deshabilitado y el circuito no pasa del primer paso. Es el hueco 4 de
   `docs/FLUJO_DEL_SISTEMA.md`: no falla, no hace nada.

2. **La receta del producto.** Declarar el lote producido descuenta su material
   de bodega. Sin receta el descuento queda pendiente y visible, que es el
   comportamiento correcto —no bloquea la producción del día—, pero entonces el
   circuito no prueba el descuento, que es justo lo que se quiere ver.

3. **Material con existencia en una ubicación disponible.** `consumir_receta_
   produccion` descuenta por FEFO y **solo** mira existencias en ubicaciones de
   tipo `disponible`. Material en cuarentena no lo ve, así que sembrar el
   catálogo sin sembrar existencia deja el mismo error de stock insuficiente
   que no sembrar nada.

Lo que este comando NO hace
---------------------------
No crea recepciones, vales ni lotes. Eso es el circuito, y el circuito lo
recorre la prueba de `frontend/e2e/circuito-polvo.spec.ts` por pantalla, que es
la única forma de comprobar que un operador puede hacerlo. Un sembrado que
además fabricara el lote probaría que el ORM funciona, no que la planta se
puede operar.

Es idempotente: repetirlo no duplica nada. Sin `--aplicar` simula recorriendo
el mismo camino y revirtiendo, no calculando aparte lo que pasaría.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventario.models import Bodega, Insumo, LoteInventario, Ubicacion
from inventario.servicios import registrar_entrada
from maestros.models import Especificacion, Producto, Receta, RecetaComponente
from produccion.models import OrdenProduccion
from usuarios.areas import usuarios_del_area
from usuarios.models import PerfilUsuario, Rol, Sucursal


#: El producto del circuito. Se elige por tener especificación vigente: sin
#: ella el análisis del lote no se puede contrastar contra nada y el expediente
#: diría «sin especificación» justo en el paso que se quiere ver funcionar.
PRODUCTO = "Leche entera en polvo"

#: Un pallet lleno. La receta se declara sobre esta base para que las
#: cantidades se lean directamente: 500 kg son 20 sacos de 25 y una base.
KG_POR_PALLET = Decimal("500")

#: Material del formato 25 kg, con la cantidad que lleva un pallet completo.
#: Los códigos son los que siembra `configurar_inventario_inicial`; este
#: comando no inventa un catálogo paralelo.
COMPONENTES = (
    ("EMB-BOL-25", Decimal("20"), "un"),
    ("EMB-ETQ-25", Decimal("20"), "un"),
    ("EMB-PALLET", Decimal("1"), "un"),
    ("EMB-FILM", Decimal("1"), "un"),
)

#: Existencia inicial, holgada a propósito: el circuito se corre muchas veces
#: mientras se depura, y quedarse sin sacos a la tercera vuelta parece un
#: defecto del circuito cuando es del sembrado.
EXISTENCIA = {
    "EMB-BOL-25": Decimal("600"),
    "EMB-ETQ-25": Decimal("600"),
    "EMB-PALLET": Decimal("30"),
    "EMB-FILM": Decimal("30"),
}

#: Las familias cuyo lote se abre sobre un evaporador. Sale de
#: `rutaPorFamilia` en `FormularioLote.tsx`, que es quien decide qué máquinas
#: ofrece: polvo → evaporador; líquido → evaporador o carga.
FAMILIAS_QUE_EVAPORAN = ("polvo", "liquido")

#: Área que le corresponde a cada rol. La clave está en que **alguien** quede
#: en Recepción: es la única área que una pantalla consulta para llenar un
#: desplegable, y sin ella el muestreo no se puede confirmar.
AREA_POR_ROL = {
    Rol.RECEPCION: PerfilUsuario.Area.RECEPCION,
    Rol.PRODUCCION: PerfilUsuario.Area.SECADO,
    Rol.CALIDAD: PerfilUsuario.Area.CALIDAD,
    Rol.ADMIN: PerfilUsuario.Area.ADMINISTRACION,
}


class Command(BaseCommand):
    help = "Prepara áreas, receta y existencia para correr el circuito de leche en polvo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Escribe de verdad. Sin esto simula y revierte.",
        )

    def handle(self, *args, **opciones):
        with transaction.atomic():
            lineas = self._preparar()

            if not opciones["aplicar"]:
                transaction.set_rollback(True)

        for linea in lineas:
            self.stdout.write(linea)

        self.stdout.write(
            self.style.SUCCESS("\nCircuito preparado.")
            if opciones["aplicar"]
            else self.style.WARNING("\nSimulación: nada se escribió. Usa --aplicar.")
        )

    def _preparar(self):
        sucursal = Sucursal.objects.filter(activa=True).order_by("id").first()
        if sucursal is None:
            raise CommandError("No hay una sucursal activa.")

        usuario = User.objects.filter(is_superuser=True).order_by("id").first()
        if usuario is None:
            raise CommandError("No hay un superusuario que firme los movimientos.")

        return [
            *self._areas(),
            *self._orden(sucursal, usuario),
            *self._especificacion_intermedia(),
            *self._receta(sucursal),
            *self._existencia(sucursal, usuario),
        ]

    # -- 0. Orden de producción ---------------------------------------------

    def _orden(self, sucursal, usuario):
        """
        Programa una OP para el producto que **tiene leche esperando**.

        Desde que abrir un lote exige orden de producción, sin ella el
        desplegable «Orden de producción» sale vacío y el formulario no se
        puede enviar. **Ninguna pantalla crea órdenes**: el viewset existe
        (`/api/produccion/ordenes/`) pero el frontend no lo usa, así que hoy
        salen del admin o de Planificación. Por eso es un prerrequisito y no
        un paso del circuito.

        No se programa a ciegas para un producto fijo. El formulario filtra las
        órdenes **por el producto del vale**, así que una OP del producto que
        toca pero sin vale liberado deja a Producción igual de bloqueada que no
        tener ninguna: hay orden y hay leche, pero de productos distintos. Se
        mira qué vales tienen saldo y se programa para uno de ellos, que es lo
        que hace un planificador.

        Se reutiliza la que ya sirva en vez de crear una por corrida: una OP
        admite varios lotes, y acumular órdenes de un solo lote llenaría la
        planificación de ruido.
        """
        from estandarizacion.models import ValeEstandarizacion
        from produccion.servicios import litros_ya_tomados

        programadas = OrdenProduccion.objects.filter(
            estado__in=[
                OrdenProduccion.Estado.PROGRAMADA,
                OrdenProduccion.Estado.EN_PROCESO,
            ],
        )

        # Solo familias que van a un evaporador. El formulario de lote mapea
        # familia → tipo de máquina, y para «crema» ofrece líneas y envasadoras:
        # una OP de crema deja el desplegable de órdenes lleno y el de máquinas
        # sin ningún evaporador, que es el mismo bloqueo movido de sitio.
        con_saldo = [
            vale
            for vale in ValeEstandarizacion.objects.filter(
                estado=ValeEstandarizacion.Estado.LIBERADO,
                producto__familia__in=FAMILIAS_QUE_EVAPORAN,
            ).select_related("producto")
            if vale.volumen - litros_ya_tomados(vale) > 0
        ]

        servida = programadas.filter(
            producto_id__in=[vale.producto_id for vale in con_saldo]
        ).first()

        if servida is not None:
            return [
                f"Orden: {servida.codigo} ya cubre «{servida.producto.nombre}», "
                "que tiene vale con saldo. No se toca."
            ]

        # Sin vales con saldo se programa igual, para el producto del circuito:
        # la orden es configuración y puede esperar a que llegue la leche.
        objetivo = next(
            (vale.producto for vale in con_saldo),
            Producto.objects.filter(nombre=PRODUCTO).first(),
        )
        if objetivo is None:
            raise CommandError(
                f"No hay vales con saldo ni existe el producto «{PRODUCTO}»."
            )

        hoy = date.today()
        base_codigo = f"OP-CIRCUITO-{hoy:%Y%m%d}-{objetivo.pk}"
        codigo = base_codigo
        correlativo = 2
        while OrdenProduccion.objects.filter(sucursal=sucursal, codigo=codigo).exists():
            codigo = f"{base_codigo}-{correlativo}"
            correlativo += 1
        orden = OrdenProduccion.objects.create(
            sucursal=sucursal,
            codigo=codigo,
            producto=objetivo,
            cantidad_planificada=Decimal("20000"),
            unidad="l",
            estado=OrdenProduccion.Estado.PROGRAMADA,
            creada_por=usuario,
        )
        return [
            f"Orden: {orden.codigo} programada para {objetivo.nombre}."
        ]

    # -- 1. Áreas -----------------------------------------------------------

    def _areas(self):
        """
        Le pone área a los perfiles que no la tienen, deducida de su rol.

        No toca los que ya la tienen cargada: un área puesta a mano es una
        decisión de quien administra usuarios, y sobrescribirla desde un
        comando de sembrado la borraría sin dejar rastro de por qué.
        """
        lineas = ["Áreas de perfil:"]
        pendientes = PerfilUsuario.objects.filter(area="").select_related("usuario")

        if not pendientes.exists():
            lineas.append("  todos los perfiles ya tienen área.")

        for perfil in pendientes:
            area = AREA_POR_ROL.get(perfil.rol)
            if area is None:
                lineas.append(
                    f"  {perfil.usuario.username}: rol «{perfil.rol}» sin área "
                    "equivalente; se deja como está."
                )
                continue
            perfil.area = area
            perfil.save(update_fields=["area"])
            lineas.append(f"  {perfil.usuario.username} → {perfil.get_area_display()}")

        # El aviso vale la pena aunque el sembrado haya ido bien: si nadie
        # quedó en Recepción, el muestreo sigue bloqueado y el circuito falla
        # tres pantallas más adelante, donde la causa ya no se ve.
        #
        # Se pregunta con `usuarios_del_area`, la misma función que llena el
        # desplegable. Una consulta propia aquí podría decir que sí mientras la
        # pantalla sigue vacía —le pasó a este código: `PerfilUsuario` no tiene
        # campo `activo`, lo tiene `User`—.
        if not usuarios_del_area(PerfilUsuario.Area.RECEPCION).exists():
            lineas.append(
                "  AVISO: ningún perfil activo quedó en Recepción. El muestreo "
                "no se podrá confirmar."
            )

        return lineas

    def _especificacion_intermedia(self):
        """Prepara únicamente el control líquido requerido por el circuito E2E."""
        producto = Producto.objects.filter(nombre=PRODUCTO).first()
        if producto is None:
            raise CommandError(f"No existe el producto «{PRODUCTO}».")
        existente = producto.especificaciones.filter(
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
        ).order_by("-version").first()
        if existente:
            return [
                f"Especificación intermedia: {producto.nombre} v{existente.version} ya existe."
            ]
        especificacion = Especificacion.objects.create(
            producto=producto,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1,
            vigente_desde=date.today(),
            rangos={
                "mg": {"min": 5.0, "max": 9.0, "obligatorio": True},
                "st": {"min": 40.0, "max": 55.0, "obligatorio": True},
                "ph": {"min": 6.2, "max": 6.9, "obligatorio": True},
            },
            fuente=(
                "Circuito E2E de precondensado: rangos provisorios; "
                "Calidad debe reemplazarlos antes de operación comercial."
            ),
        )
        return [
            f"Especificación intermedia: {producto.nombre} v{especificacion.version} creada."
        ]

    # -- 2. Receta ----------------------------------------------------------

    def _receta(self, sucursal):
        producto = Producto.objects.filter(nombre=PRODUCTO).first()
        if producto is None:
            raise CommandError(
                f"No existe el producto «{PRODUCTO}». Cárgalo en Maestros antes."
            )

        faltan = [
            codigo
            for codigo, _, _ in COMPONENTES
            if not Insumo.objects.filter(
                empresa=sucursal.empresa, codigo=codigo
            ).exists()
        ]
        if faltan:
            raise CommandError(
                "Falta el catálogo de embalaje: "
                + ", ".join(faltan)
                + ". Córrelo antes con «configurar_inventario_inicial "
                f"--empresa {sucursal.empresa_id} --aplicar»."
            )

        vigente = producto.recetas.order_by("-version").first()
        if vigente is not None:
            return [
                f"Receta: {producto.nombre} ya tiene la versión {vigente.version} "
                f"({vigente.componentes.count()} componentes). No se toca."
            ]

        receta = Receta.objects.create(
            producto=producto,
            version=1,
            cantidad_base=KG_POR_PALLET,
            vigente_desde=date(2026, 1, 1),
            fuente="Circuito de prueba: un pallet de 20 sacos de 25 kg.",
        )
        for codigo, cantidad, unidad in COMPONENTES:
            RecetaComponente.objects.create(
                receta=receta,
                insumo=Insumo.objects.get(empresa=sucursal.empresa, codigo=codigo),
                cantidad=cantidad,
                unidad=unidad,
            )

        return [
            f"Receta: {producto.nombre} v1 por {KG_POR_PALLET} kg — "
            + ", ".join(f"{c} ×{q:g}" for c, q, _ in COMPONENTES)
        ]

    # -- 3. Existencia ------------------------------------------------------

    def _existencia(self, sucursal, usuario):
        """
        Deja material contado en una ubicación **disponible**.

        El tipo de la ubicación no es un detalle de clasificación: el descuento
        por FEFO filtra por él, así que material en cuarentena no existe para
        la receta aunque esté en la bodega.
        """
        bodega = Bodega.objects.filter(sucursal=sucursal, codigo="BEM").first()
        if bodega is None:
            raise CommandError(
                "No existe la bodega de embalaje BEM. Córrelo antes con "
                f"«configurar_inventario_inicial --empresa {sucursal.empresa_id} --aplicar»."
            )

        ubicacion = Ubicacion.objects.filter(
            bodega=bodega, tipo=Ubicacion.Tipo.DISPONIBLE
        ).order_by("id").first()
        if ubicacion is None:
            raise CommandError(
                f"La bodega {bodega.codigo} no tiene ninguna ubicación disponible; "
                "el descuento por FEFO no vería el material."
            )

        lineas = [f"Existencia en {bodega.codigo}/{ubicacion.codigo}:"]

        for codigo, cantidad in EXISTENCIA.items():
            insumo = Insumo.objects.get(empresa=sucursal.empresa, codigo=codigo)
            codigo_lote = f"CIRCUITO-{codigo}"

            if LoteInventario.objects.filter(
                sucursal=sucursal, insumo=insumo, codigo=codigo_lote
            ).exists():
                lineas.append(f"  {codigo}: el lote {codigo_lote} ya existe.")
                continue

            lote = LoteInventario.objects.create(
                sucursal=sucursal,
                insumo=insumo,
                codigo=codigo_lote,
                # Un material que exige decisión de Calidad entra aprobado
                # porque este sembrado representa material ya inspeccionado;
                # dejarlo en cuarentena probaría el bloqueo, no el circuito.
                estado_calidad=(
                    LoteInventario.EstadoCalidad.APROBADO
                    if insumo.requiere_calidad
                    else LoteInventario.EstadoCalidad.NO_REQUIERE
                ),
            )
            registrar_entrada(
                lote=lote,
                ubicacion=ubicacion,
                cantidad=cantidad,
                usuario=usuario,
                documento_tipo="produccion.PrepararCircuito",
                documento_id=insumo.pk,
            )
            lineas.append(f"  {codigo}: {cantidad:g} {insumo.unidad}")

        return lineas
