"""Completa y verifica el estado maestro reproducible para QA."""

from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from auditoria.models import RegistroAuditoria
from inventario.models import Bodega, Insumo, Ubicacion
from maestros.models import Equipo, Especificacion, Producto, Silo
from procesos.models import EtapaProceso, Proceso, RutaProducto
from usuarios.models import PerfilUsuario

from .reset_datos_operacionales import (
    datos_conexion,
    modelos_operacionales,
    validar_destino,
)


class Command(BaseCommand):
    help = "Prepara maestros y cuentas QA sin crear datos operacionales."

    def handle(self, *args, **options):
        info = datos_conexion()
        self.stdout.write(
            f"QA: entorno={info['entorno']} host={info['host']} base={info['base']}"
        )
        validar_destino(info)

        existentes = sum(modelo.objects.count() for modelo in modelos_operacionales())
        if existentes:
            raise CommandError(
                f"El estado QA no está limpio: quedan {existentes} registros operacionales. "
                "Ejecuta primero reset_datos_operacionales."
            )

        salida = StringIO()
        call_command("configurar_maestro_inicial", aplicar=True, stdout=salida)
        call_command("configurar_inventario_inicial", aplicar=True, stdout=salida)
        call_command("crear_usuarios_flujo_e2e", stdout=salida)

        # Configurar un maestro puede producir auditoría por señal. Es un rastro
        # del propio sembrado, no una operación de planta, y el estado inicial
        # exige comenzar también ese libro en cero.
        RegistroAuditoria.objects.all().delete()
        operacionales_despues = sum(
            modelo.objects.count() for modelo in modelos_operacionales()
        )
        if operacionales_despues:
            raise CommandError(
                "El sembrado QA creó datos operacionales; se aborta su validación."
            )

        conteos = {
            "perfiles": PerfilUsuario.objects.count(),
            "productos": Producto.objects.count(),
            "rutas": RutaProducto.objects.count(),
            "procesos": Proceso.objects.count(),
            "etapas": EtapaProceso.objects.count(),
            "equipos": Equipo.objects.count(),
            "silos": Silo.objects.count(),
            "especificaciones": Especificacion.objects.count(),
            "insumos": Insumo.objects.count(),
            "bodegas": Bodega.objects.count(),
            "ubicaciones": Ubicacion.objects.count(),
        }
        vacios = [nombre for nombre, cantidad in conteos.items() if cantidad == 0]
        if vacios:
            raise CommandError(
                "Estado QA incompleto; faltan maestros: " + ", ".join(vacios)
            )

        for nombre, cantidad in conteos.items():
            self.stdout.write(f"  {nombre:<20}{cantidad:>5}")
        self.stdout.write("  datos_operacionales      0")
        self.stdout.write(self.style.SUCCESS("ESTADO QA INICIAL PREPARADO"))
