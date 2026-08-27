"""Completa el mínimo maestro para recorrer el flujo en una instalación nueva."""

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from maestros.models import DocumentoLiberacion, Especificacion, Producto


RANGOS_POR_FAMILIA = {
    Producto.Familia.POLVO: {"humedad": {"min": 2.5, "max": 5.0, "obligatorio": True}},
    Producto.Familia.CREMA: {
        "mg": {"min": 35.0, "max": 50.0, "obligatorio": True},
        "temperatura": {"min": 2.0, "max": 8.0, "obligatorio": True},
    },
    Producto.Familia.LIQUIDO: {
        "mg": {"min": 3.0, "max": 6.0, "obligatorio": True},
        "temperatura": {"min": 2.0, "max": 8.0, "obligatorio": True},
    },
    Producto.Familia.OTRO: {"temperatura": {"min": 2.0, "max": 25.0, "obligatorio": True}},
}


class Command(BaseCommand):
    help = "Crea especificaciones y checklist iniciales marcados como provisorios."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Escribe los datos.")

    def handle(self, *args, **options):
        creadas_especificaciones = 0
        creados_documentos = 0
        with transaction.atomic():
            for producto in Producto.objects.filter(activo=True):
                if not producto.especificaciones.exists():
                    Especificacion.objects.create(
                        producto=producto,
                        version=1,
                        vigente_desde=date.today(),
                        rangos=RANGOS_POR_FAMILIA[producto.familia],
                        fuente="Configuración inicial provisoria: validar con Calidad antes de operación comercial.",
                    )
                    creadas_especificaciones += 1

            for familia, etiqueta in Producto.Familia.choices:
                if DocumentoLiberacion.objects.filter(aplica_a__contains=[familia]).exists():
                    continue
                empresa = Producto.objects.filter(familia=familia).values_list(
                    "mandante__empresa", flat=True
                ).first()
                if empresa is None:
                    continue
                DocumentoLiberacion.objects.create(
                    empresa_id=empresa,
                    codigo=f"CCAA.CALIDAD.INICIAL.{familia.upper()}",
                    nombre=f"Verificación inicial de liberación · {etiqueta}",
                    area=DocumentoLiberacion.Area.CALIDAD,
                    aplica_a=[familia],
                    instruccion="Confirmar la revisión del lote y reemplazar este documento provisorio por el formato oficial de Calidad.",
                    plantilla=[
                        {"clave": "lote", "etiqueta": "Lote", "tipo": "texto", "req": True, "origen": "lote.codigo_lote"},
                        {"clave": "verificado", "etiqueta": "Verificado por Calidad", "tipo": "booleano", "req": True},
                    ],
                    fuente="Configuración inicial provisoria: validar con Calidad.",
                )
                creados_documentos += 1

            if not options["aplicar"]:
                transaction.set_rollback(True)

        accion = "Creadas" if options["aplicar"] else "Se crearían"
        self.stdout.write(f"{accion}: {creadas_especificaciones} especificaciones y {creados_documentos} documentos.")
