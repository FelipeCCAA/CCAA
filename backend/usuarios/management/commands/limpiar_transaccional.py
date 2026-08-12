"""
Borra los movimientos de planta y deja los maestros en pie.

El sistema está en desarrollo y lo que hay son datos de prueba acumulados a
mano. Lo que se borra es **lo que se produce operando**: recepciones, vales,
lotes, análisis, liberaciones, planes. Lo que se conserva es **lo que cuesta
volver a cargar**: los 27 productos, los mandantes, los silos, los equipos, los
vehículos, el catálogo de documentos, las especificaciones, las personas.

Sin `--aplicar` solo cuenta lo que borraría. Es la misma forma que
`cargar_productos`: una orden destructiva que se ejecuta a ciegas es una que
tarde o temprano se ejecuta sobre lo que no era.

La auditoría se borra también **a propósito**: es el registro de los cambios que
estamos borrando, y dejarla convertiría el expediente en una lista de
referencias a filas que ya no existen.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction


# En orden de borrado: primero lo que apunta, después lo apuntado. Con `PROTECT`
# en medio, el orden no es cosmético.
MODELOS = [
    ("calidad", "Liberacion"),
    ("calidad", "RegistroCalidad"),
    ("calidad", "RegistroEquipo"),
    ("inocuidad", "PproLectura"),
    ("inocuidad", "MonitoreoPPRO"),
    ("produccion", "Analisis"),
    ("produccion", "ControlProcesoLectura"),
    ("produccion", "ControlProceso"),
    ("procesos", "SalidaProceso"),
    ("procesos", "EntradaProceso"),
    ("procesos", "EventoProceso"),
    ("procesos", "EjecucionProceso"),
    ("estandarizacion", "ValeEstandarizacion"),
    ("recepcion", "MovimientoSilo"),
    ("recepcion", "Recepcion"),
    ("recoleccion", "CargaModulo"),
    ("recoleccion", "Recoleccion"),
    ("recoleccion", "ParadaRuta"),
    ("recoleccion", "RutaRecoleccion"),
    ("produccion", "Lote"),
    ("planificacion", "BloquePlan"),
    ("planificacion", "BalanceDia"),
    ("planificacion", "SemanaPlan"),
    ("inventario", "Notificacion"),
    ("inventario", "EjecucionMRP"),
    ("auditoria", "RegistroAuditoria"),
]


class Command(BaseCommand):
    help = "Borra los movimientos de planta y conserva los maestros."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Borra de verdad. Sin esto solo cuenta.",
        )

    def handle(self, *args, **opciones):
        aplicar = opciones["aplicar"]
        total = 0

        with transaction.atomic():
            for app, nombre in MODELOS:
                try:
                    modelo = apps.get_model(app, nombre)
                except LookupError:
                    self.stdout.write(f"  (no existe {app}.{nombre}, se omite)")
                    continue

                cuantos = modelo.objects.count()

                if not cuantos:
                    continue

                total += cuantos
                self.stdout.write(f"  {app}.{nombre:<26}{cuantos}")

                if aplicar:
                    modelo.objects.all().delete()

            if not aplicar:
                # Se revierte igual, pero se recorre el mismo camino: contar por
                # otro lado daría un número que no es el que se va a borrar.
                transaction.set_rollback(True)

        verbo = "Borrados" if aplicar else "Se borrarían"
        self.stdout.write(self.style.SUCCESS(f"{verbo} {total} registros."))

        if not aplicar:
            self.stdout.write("Nada se escribió. Repite con --aplicar.")
