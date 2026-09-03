"""Prepara solo los maestros sin pantalla requeridos por el E2E de granel."""

from datetime import date

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max

from inventario.models import ClienteDespacho
from maestros.models import Especificacion, Producto
from procesos.models import RutaProducto
from produccion.models import OrdenProduccion
from usuarios.models import Sucursal


PRODUCTO = "Precondensado Entero NE Granel"


class Command(BaseCommand):
    help = "Prepara OP, especificacion provisoria y cliente para el E2E de precondensado."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opciones):
        planta = Sucursal.objects.filter(activa=True).select_related("empresa").order_by("id").first()
        usuario = User.objects.filter(is_superuser=True).order_by("id").first()
        producto = Producto.objects.filter(nombre=PRODUCTO).first()
        if not planta or not usuario or not producto:
            raise CommandError("Falta planta activa, superusuario o producto de precondensado.")
        if not RutaProducto.objects.filter(
            producto=producto, sucursal=planta, activa=True,
            destino_final=RutaProducto.DestinoFinal.DESPACHO_DIRECTO,
        ).exists():
            raise CommandError("El producto no tiene una ruta activa hacia despacho directo.")

        especificacion = producto.especificaciones.filter(
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
        ).order_by("-version").first()
        if especificacion is None:
            version = (producto.especificaciones.aggregate(maxima=Max("version"))["maxima"] or 0) + 1
            especificacion = Especificacion.objects.create(
                producto=producto,
                tipo_analisis=Especificacion.TipoAnalisis.SILO,
                version=version,
                vigente_desde=date.today(),
                rangos={
                    "mg": {"min": 3.0, "max": 6.0, "obligatorio": True},
                    "st": {"min": 40.0, "max": 55.0, "obligatorio": True},
                    "ph": {"min": 6.2, "max": 6.9, "obligatorio": True},
                },
                fuente=(
                    "E2E provisorio: Calidad debe reemplazar estos rangos por "
                    "la especificacion aprobada de planta."
                ),
            )

        orden = OrdenProduccion.objects.filter(
            sucursal=planta,
            producto=producto,
            estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
        ).first()
        if orden is None:
            base = f"OP-E2E-PRE-{date.today():%Y%m%d}"
            correlativo = OrdenProduccion.objects.filter(codigo__startswith=base).count() + 1
            orden = OrdenProduccion.objects.create(
                sucursal=planta,
                codigo=f"{base}-{correlativo}",
                producto=producto,
                cantidad_planificada=20000,
                unidad="l",
                estado=OrdenProduccion.Estado.PROGRAMADA,
                creada_por=usuario,
            )

        cliente, _ = ClienteDespacho.objects.get_or_create(
            empresa=planta.empresa,
            codigo="CLI-E2E",
            defaults={"nombre": "Cliente E2E despacho granel", "direccion": "Destino de prueba"},
        )
        if not cliente.activo:
            cliente.activo = True
            cliente.save(update_fields=["activo"])

        self.stdout.write(
            f"Producto={producto.nombre}; OP={orden.codigo}; "
            f"especificacion={especificacion.version}; cliente={cliente.codigo}"
        )
        if not opciones["aplicar"]:
            transaction.set_rollback(True)
            self.stdout.write(self.style.WARNING("Simulacion: usa --aplicar para guardar."))
        else:
            self.stdout.write(self.style.SUCCESS("Circuito de precondensado preparado."))
