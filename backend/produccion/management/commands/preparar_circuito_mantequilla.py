from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from maestros.models import Equipo, Especificacion, Mandante, Producto
from procesos.models import RutaProducto
from produccion.models import Lote, OrdenProduccion
from usuarios.models import Sucursal


FUENTE_CODEX = (
    "Referencia provisional: Codex CXS 279-1971, mantequilla: minimo 80% "
    "grasa lactea y maximo 16% agua. Validar especificacion CCAA."
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
            f"especificacion=v{especificacion.version}; mazada={lote_suero.codigo_lote}."
        ))
