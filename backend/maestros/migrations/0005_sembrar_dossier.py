"""
Siembra los 19 registros del Dossier de Liberación.

Origen: CCAA.Calidad.FORM.023, levantado en `docs/levantamiento-2026-07/`. Es
el checklist real de la planta, en su orden de flujo: Recepción →
Condensación → Secado → Envase.

Va como migración y no como fixture porque es **configuración del sistema**,
no datos de ejemplo: sin estos documentos el módulo de Liberación no tiene
checklist que exigir, y cualquier instalación nueva los necesita desde el
primer arranque.

Todos entran como atestación —`plantilla` vacía— a propósito. La plantilla de
cada formulario se define después, uno a uno, contra su formato real; ponerlos
ahora inventados sería peor que dejarlos vacíos, porque un formulario que pide
campos equivocados se completa igual y da el documento por cumplido.

Pendiente de confirmar con Calidad (MODELO_DATOS.md §8.3): todos se siembran
con `aplica_a = ["polvo"]`, que es la línea que el Dossier cubre. Qué
documentos exigen además crema o mantequilla es una pregunta abierta, y
responderla es editar el catálogo, no volver a migrar.
"""

from django.db import migrations


# (orden, área, nombre, código). El orden es el del Dossier.
DOSSIER = [
    (1, "recepcion", "Trazabilidad de Leche fresca", "CCAA.REC.FORM.005"),
    (2, "condensacion", "PCC 1 - Formulario de Control de Proceso", "CCAA.Cond.FORM.010"),
    (3, "condensacion", "Checklist de Cuerpos Extraños Evaporadores", "CCAA.Cond.FORM.005"),
    (4, "condensacion", "Disco de Uperización", ""),
    (5, "secado", "Hoja de Pulverización E1-E2", "CCAA.Sec.FORM.025"),
    (6, "secado", "Inspección Pre-operativa E1-E2", "CCAA.Sec.FORM.003"),
    (7, "secado", "Conexión a Tierra E1-E2", "CCAA.Sec.FORM.016"),
    (8, "secado", "Formulario de Análisis Fisicoquímico E1-E2", "CCAA.Sec.FORM.001"),
    (9, "secado", "Formulario de Filtros de Limpieza de producto", "CCAA.Sec.FORM.020"),
    (10, "secado", "Dosificación de Lecitina en Leche en Polvo", "CCAA.Sec.FORM.021"),
    (11, "secado", "Checklist de Cuerpos Extraños E1-E2", "CCAA.Sec.FORM.012"),
    (12, "secado", "PPRO 3 - Monitoreo de PPRO E1-E2", "CCAA.Sec.FORM.022"),
    (13, "envase", "PPRO 4 - Monitoreo PPRO Rovemas 3 y 4", "CCAA.Sec.FORM.005"),
    (14, "envase", "Checklist de Cuerpos Extraños Rovema 3 y 4", "CCAA.Sec.FORM.007"),
    (15, "envase", "Inspección en Operación Rovema 3-4", "CCAA.Sec.FORM.024"),
    (16, "envase", "Seguimiento FEFO", "CCAA.Sec.FORM.023"),
    (17, "envase", "PPRO 5 - Monitoreo PPRO Detector de Metales", "CCAA.ENV.FORM.001"),
    (18, "envase", "Control de Consumo de Materiales", "CCAA.Sec.FORM.011"),
    (19, "envase", "Control de Hermeticidad y Peso Neto", "CCAA.ENV.FORM.004"),
]

FUENTE = "Dossier CCAA.Calidad.FORM.023 (levantamiento 2026-07)"

# El disco de uperización es un registro físico sin código de formato. Se
# identifica por nombre, que es lo único que tiene.
SIN_CODIGO = "Disco de Uperización"


def sembrar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for orden, area, nombre, codigo in DOSSIER:
        valores = {
            "nombre": nombre,
            "area": area,
            "orden": orden,
            # Pendiente de confirmar con Calidad si alguno aplica a crema.
            "aplica_a": ["polvo"],
            "plantilla": [],
            "fuente": FUENTE,
            "activo": True,
        }

        # `update_or_create` por código la hace idempotente: volver a correrla
        # actualiza en vez de duplicar. El único sin código se busca por
        # nombre, porque la unicidad de `codigo` no alcanza a los vacíos.
        if codigo:
            Documento.objects.update_or_create(codigo=codigo, defaults=valores)
        else:
            Documento.objects.update_or_create(
                codigo="", nombre=nombre, defaults=valores
            )


def borrar(apps, schema_editor):
    """
    Deshacer borra solo lo que esta migración sembró.

    Se filtra además por `fuente`: si alguien edita uno de estos documentos y
    lo marca como propio, revertir no debería llevárselo por delante.
    """
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    codigos = [codigo for _, _, _, codigo in DOSSIER if codigo]

    Documento.objects.filter(codigo__in=codigos, fuente=FUENTE).delete()
    Documento.objects.filter(codigo="", nombre=SIN_CODIGO, fuente=FUENTE).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0004_documentoliberacion_area"),
    ]

    operations = [
        migrations.RunPython(sembrar, borrar),
    ]
