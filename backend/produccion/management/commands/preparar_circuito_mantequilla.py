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
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Sucursal


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


class Command(BaseCommand):
    help = "Prepara OP, especificacion y lote de mazada para probar Mantequilla."

    def add_arguments(self, parser):
        parser.add_argument("--sucursal", type=int)
        parser.add_argument("--aplicar", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opciones):
        plantas = Sucursal.objects.filter(activa=True).select_related("empresa")
        if opciones["sucursal"]:
            plantas = plantas.filter(pk=opciones["sucursal"])
        if plantas.count() != 1:
            raise CommandError("Indica --sucursal cuando no exista una unica planta activa.")
        planta = plantas.get()
        usuario = User.objects.filter(is_superuser=True).order_by("id").first()
        if usuario is None:
            raise CommandError("Falta un administrador local para auditar la preparacion.")

        producto = Producto.objects.filter(
            mandante__empresa=planta.empresa,
            categoria=Producto.Categoria.MANTEQUILLA,
            formato=Producto.Formato.CAJA_20KG,
            activo=True,
        ).order_by("nombre").first()
        if producto is None:
            raise CommandError("Falta un producto activo de mantequilla en caja de 20 kg.")
        if not RutaProducto.objects.filter(
            sucursal=planta, producto=producto, proceso__codigo="ruta-mantequilla",
            activa=True,
        ).exists():
            raise CommandError("La mantequilla no tiene una ruta activa de Mantequilla a Envasado.")
        linea = Equipo.objects.filter(
            sucursal=planta, activo=True, tipo=Equipo.Tipo.LINEA,
            nombre__icontains="mantequilla",
        ).first()
        if linea is None:
            raise CommandError("Falta la linea activa de mantequilla.")

        if not opciones["aplicar"]:
            self.stdout.write(self.style.WARNING(
                f"Vista previa: {producto.nombre}, OP 40 kg, {linea.nombre}, "
                "especificacion Codex provisional y lote trazable de mazada."
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
            mandante__empresa=planta.empresa,
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

        orden = OrdenProduccion.objects.filter(
            sucursal=planta, producto=producto,
            estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
        ).first()
        if orden is None:
            base = f"OP-E2E-MANT-{date.today():%Y%m%d}"
            correlativo = OrdenProduccion.objects.filter(
                sucursal=planta, codigo__startswith=base,
            ).count() + 1
            orden = OrdenProduccion.objects.create(
                sucursal=planta,
                codigo=f"{base}-{correlativo}",
                producto=producto,
                cantidad_planificada=40,
                unidad="kg",
                equipo=linea,
                linea=linea.nombre,
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
        lote_suero = Lote.objects.filter(
            sucursal=planta, producto=mazada,
            estado__in=[Lote.Estado.BORRADOR, Lote.Estado.EN_PROCESO],
            kg_producidos__isnull=True,
            corridas_como_suero_mantequilla__isnull=True,
        ).first()
        if lote_suero is None:
            base = f"MAZ-E2E-{date.today():%Y%m%d}"
            correlativo = Lote.objects.filter(
                sucursal=planta, codigo_lote__startswith=base,
            ).count() + 1
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
            f"receta_envase=v{receta_envase.version}; materiales={materiales}."
        ))

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
