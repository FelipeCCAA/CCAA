from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from inventario.models import Bodega, Insumo, LoteInventario, Ubicacion
from inventario.servicios import registrar_entrada
from maestros.models import (
    Equipo, Especificacion, Mandante, Producto, Receta, RecetaComponente,
)
from procesos.models import RutaProducto
from procesos.servicios import sueros_libres
from produccion.models import Lote, OrdenProduccion
from usuarios.tenancy import unica_sucursal_activa


FUENTE_CODEX = (
    "Referencia provisional: Codex CXS 279-1971, mantequilla: minimo 80% "
    "grasa lactea y maximo 16% agua. Validar especificacion CCAA."
)
FUENTE_ENVASE = (
    "Configuración operacional provisional CCAA: caja de mantequilla de 20 kg, "
    "25 cajas por pallet de 500 kg. Validar materiales y proveedores homologados."
)
MATERIALES_ENVASE = (
    ("EMB-CAJA-MANT-20", "Caja corrugada para mantequilla 20 kg", False, False, Decimal("25"), Decimal("250")),
    ("EMB-LINER-MANT-20", "Liner grado alimentario para mantequilla 20 kg", True, True, Decimal("25"), Decimal("250")),
    ("EMB-ETQ-MANT-20", "Etiqueta trazable mantequilla 20 kg", False, False, Decimal("25"), Decimal("250")),
    ("EMB-PALLET", "Pallet madera industrial", False, False, Decimal("1"), Decimal("10")),
    ("EMB-FILM", "Film stretch para pallet", False, False, Decimal("1"), Decimal("10")),
)
CODIGO_ENVASADORA = "envasadora_mantequilla"


class Command(BaseCommand):
    help = "Prepara OP, especificacion y lote de mazada para probar Mantequilla."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opciones):
        # Clave histórica de persistencia; no es selector ni dimensión funcional.
        planta = unica_sucursal_activa(None)
        if planta is None:
            raise CommandError("Falta la configuración técnica histórica requerida.")
        usuario = User.objects.filter(is_superuser=True).order_by("id").first()
        if usuario is None:
            raise CommandError("Falta un administrador local para auditar la preparacion.")

        producto = Producto.objects.filter(
            categoria=Producto.Categoria.MANTEQUILLA,
            formato=Producto.Formato.CAJA_20KG,
            activo=True,
        ).order_by("nombre").first()
        if producto is None:
            raise CommandError("Falta un producto activo de mantequilla en caja de 20 kg.")
        if not RutaProducto.objects.filter(
            producto=producto, proceso__codigo="ruta-mantequilla",
            activa=True,
        ).exists():
            raise CommandError("La mantequilla no tiene una ruta activa de Mantequilla a Envasado.")
        mantequera = Equipo.objects.filter(
            activo=True, tipo=Equipo.Tipo.MANTEQUERA,
        ).order_by("codigo").first()
        if mantequera is None:
            raise CommandError(
                "Falta una mantequera activa: créala en Maestros › Máquinas con tipo «Mantequera»."
            )

        if not opciones["aplicar"]:
            self.stdout.write(self.style.WARNING(
                f"Vista previa: {producto.nombre}, OP 40 kg, {mantequera.nombre}, "
                "envasadora de mantequilla autorizada en sus formatos, especificacion "
                "Codex provisional y lote trazable de mazada."
            ))
            transaction.set_rollback(True)
            return

        especificaciones = list(producto.especificaciones.filter(
            tipo_analisis=Especificacion.TipoAnalisis.LOTE,
        ))
        especificacion = next(
            (
                item for item in especificaciones
                if {"mg", "humedad"} <= set(item.rangos)
                or item.fuente == FUENTE_CODEX
            ),
            None,
        )
        if especificacion is None:
            version = (producto.especificaciones.aggregate(
                maxima=Max("version")
            )["maxima"] or 0) + 1
            especificacion = Especificacion.objects.create(
                producto=producto,
                tipo_analisis=Especificacion.TipoAnalisis.LOTE,
                version=version,
                vigente_desde=date.today(),
                rangos={
                    "mg": {"min": 80.0, "max": 100.0, "obligatorio": True},
                    "humedad": {"min": 0.0, "max": 16.0, "obligatorio": True},
                    "sng": {"min": 0.0, "max": 2.0, "obligatorio": True},
                },
                fuente=FUENTE_CODEX,
            )
        elif (
            especificacion.fuente == FUENTE_CODEX
            and (
                especificacion.vigente_desde < date.today()
                or "grasa" in especificacion.rangos
            )
        ):
            especificacion.vigente_desde = date.today()
            if "grasa" in especificacion.rangos:
                especificacion.rangos["mg"] = especificacion.rangos.pop("grasa")
            especificacion.save(update_fields=["vigente_desde", "rangos"])

        receta_envase = None
        materiales = 0
        productos_mantequilla = Producto.objects.filter(
            categoria=Producto.Categoria.MANTEQUILLA,
            formato=Producto.Formato.CAJA_20KG,
            activo=True,
        )
        for producto_mantequilla in productos_mantequilla:
            receta_configurada, materiales = self._preparar_materiales_envase(
                planta=planta, producto=producto_mantequilla, usuario=usuario,
            )
            if producto_mantequilla.pk == producto.pk:
                receta_envase = receta_configurada
        envasadora, sin_formato = self._autorizar_envasadora(
            planta=planta, productos=productos_mantequilla,
        )
        for nombre in sin_formato:
            self.stdout.write(self.style.WARNING(
                f"{nombre} no tiene un formato de envasado activo: créalo en Maestros "
                "› Formatos de envasado y vuelve a correr el comando."
            ))

        orden = OrdenProduccion.objects.filter(
            producto=producto,
            estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
        ).first()
        if orden is None:
            base = f"OP-E2E-MANT-{date.today():%Y%m%d}"
            correlativo = OrdenProduccion.objects.filter(codigo__startswith=base).count() + 1
            orden = OrdenProduccion.objects.create(
                sucursal=planta,
                codigo=f"{base}-{correlativo}",
                producto=producto,
                cantidad_planificada=40,
                unidad="kg",
                equipo=mantequera,
                linea=mantequera.nombre,
                estado=OrdenProduccion.Estado.PROGRAMADA,
                creada_por=usuario,
                observacion="Orden local de validacion; no representa una orden comercial.",
            )

        mandante = Mandante.objects.filter(
            empresa=planta.empresa,
            codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
        ).first()
        if mandante is None:
            raise CommandError("Falta el mandante propio CCAA.")
        mazada, _ = Producto.objects.get_or_create(
            mandante=mandante,
            nombre="Mazada de mantequilla intermedia CCAA",
            defaults={
                "naturaleza_comercial": Producto.NaturalezaComercial.PRODUCTO_PROPIO,
                "categoria": Producto.Categoria.SUERO,
                "tipo": Producto.TipoProducto.SIN_ESPECIFICAR,
                "formato": Producto.Formato.GRANEL,
                "mercado": Producto.Mercado.LOCAL,
                "familia": Producto.Familia.LIQUIDO,
                "naturaleza": Producto.Naturaleza.INTERMEDIO,
                "unidad_base": Producto.Unidad.KG,
            },
        )
        lote_suero = sueros_libres(Lote.objects.filter(producto=mazada)).order_by("pk").first()
        if lote_suero is None:
            base = f"MAZ-E2E-{date.today():%Y%m%d}"
            correlativo = Lote.objects.filter(codigo_lote__startswith=base).count() + 1
            lote_suero = Lote.objects.create(
                sucursal=planta,
                codigo_lote=f"{base}-{correlativo}",
                codigo_lote_propuesto=f"{base}-{correlativo}",
                producto=mazada,
                fecha=date.today(),
                estado=Lote.Estado.BORRADOR,
                observacion="Lote de coproducto preparado para una corrida E2E de mantequilla.",
            )

        self.stdout.write(self.style.SUCCESS(
            f"Mantequilla preparada: OP={orden.codigo}; producto={producto.nombre}; "
            f"especificacion=v{especificacion.version}; mazada={lote_suero.codigo_lote}; "
            f"envasadora={envasadora.nombre}; "
            f"receta_envase=v{receta_envase.version}; materiales={materiales}."
        ))

    def _autorizar_envasadora(self, *, planta, productos):
        """
        La mantequilla se envasa en una envasadora, no en la mantequera: el
        envasado acepta solo envasadora o línea (`FormatoEnvasado`,
        `Envase.clean()`) y `maestros.0040` sacó la mantequera de los
        formatos. Se asegura una y se autoriza en los formatos activos de cada
        mantequilla. Un producto sin formato se avisa, no se inventa: el
        formato es configuración de planta.

        Sin `consume_materiales`: la mantequera ya lo tiene, y marcar las dos
        haría que el MRP pidiera los envases dos veces.
        """
        envasadora, _ = Equipo.objects.get_or_create(
            sucursal=planta, codigo=CODIGO_ENVASADORA,
            defaults={"nombre": "Envasadora de mantequilla", "tipo": Equipo.Tipo.ENVASADORA},
        )
        if envasadora.tipo != Equipo.Tipo.ENVASADORA or not envasadora.activo:
            raise CommandError(
                f"{CODIGO_ENVASADORA} existe pero no es una envasadora activa: "
                "corrígelo en Maestros › Máquinas."
            )
        sin_formato = []
        for producto in productos:
            formatos = list(producto.formatos_envasado.filter(activo=True))
            if not formatos:
                sin_formato.append(producto.nombre)
            for formato in formatos:
                formato.equipos.add(envasadora)
        return envasadora, sin_formato

    def _preparar_materiales_envase(self, *, planta, producto, usuario):
        """Configura una BOM explícita; el stock entra mediante movimientos."""
        bodega, _ = Bodega.objects.get_or_create(
            sucursal=planta, codigo="BEM",
            defaults={"nombre": "Bodega de embalaje", "area": "bodega"},
        )
        disponible, _ = Ubicacion.objects.get_or_create(
            bodega=bodega, codigo="EMB-DISP",
            defaults={
                "tipo": Ubicacion.Tipo.DISPONIBLE,
                "descripcion": "Material liberado para producción",
            },
        )
        insumos = {}
        for codigo, nombre, requiere_calidad, certificado, _cantidad, stock in MATERIALES_ENVASE:
            insumo, _ = Insumo.objects.get_or_create(
                empresa=planta.empresa, codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "descripcion": "Material de referencia; validar ficha técnica y proveedor homologado.",
                    "categoria": Insumo.Categoria.EMPAQUE,
                    "area": "envase",
                    "unidad": Insumo.Unidad.UN,
                    "requiere_lote": True,
                    "requiere_calidad": requiere_calidad,
                    "requiere_certificado": certificado,
                    "stock_minimo": 50 if _cantidad == 25 else 5,
                    "stock_seguridad": 50 if _cantidad == 25 else 5,
                },
            )
            insumos[codigo] = insumo
            if not LoteInventario.objects.filter(
                sucursal=planta, insumo=insumo, codigo=f"E2E-MANT-{codigo}",
            ).exists():
                lote_material = LoteInventario.objects.create(
                    sucursal=planta, insumo=insumo, codigo=f"E2E-MANT-{codigo}",
                    estado_calidad=(
                        LoteInventario.EstadoCalidad.APROBADO
                        if requiere_calidad
                        else LoteInventario.EstadoCalidad.NO_REQUIERE
                    ),
                )
                registrar_entrada(
                    lote=lote_material, ubicacion=disponible, cantidad=stock,
                    usuario=usuario,
                    documento_tipo="produccion.PreparacionCircuitoMantequilla",
                    documento_id=insumo.pk,
                )

        receta = producto.recetas.filter(
            componentes__fase=RecetaComponente.Fase.ENVASADO,
        ).order_by("-vigente_desde", "-version").first()
        if receta is None:
            anterior = producto.recetas.order_by("-vigente_desde", "-version").first()
            base = anterior.cantidad_base if anterior else Decimal("500")
            receta = Receta.objects.create(
                producto=producto,
                version=(producto.recetas.aggregate(maxima=Max("version"))["maxima"] or 0) + 1,
                cantidad_base=base,
                vigente_desde=date.today(),
                fuente=FUENTE_ENVASE,
            )
            if anterior:
                for componente in anterior.componentes.all():
                    RecetaComponente.objects.create(
                        receta=receta,
                        producto=componente.producto,
                        insumo=componente.insumo,
                        cantidad=componente.cantidad,
                        unidad=componente.unidad,
                        merma=componente.merma,
                        fase=componente.fase,
                    )
            escala = base / Decimal("500")
            for codigo, _nombre, _calidad, _certificado, cantidad, _stock in MATERIALES_ENVASE:
                RecetaComponente.objects.create(
                    receta=receta, insumo=insumos[codigo],
                    cantidad=cantidad * escala, unidad="un",
                    fase=RecetaComponente.Fase.ENVASADO,
                )
        return receta, len(insumos)
