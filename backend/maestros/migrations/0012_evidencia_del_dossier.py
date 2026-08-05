"""
Marca qué documentos del Dossier los cumple el propio dato del sistema.

Once de los diecinueve registros son datos que la aplicación ya captura, pero
**solo cinco se pueden atar sin ambigüedad**. Los otros seis dependen del
equipo donde se registró, y ahí el dato todavía no distingue: un monitoreo de
cuerpos extraños daría por cumplidos los tres checklists —evaporadores, E1-E2
y Rovema— cuando solo se hizo uno. Un documento cumplido de más deja salir
producto, así que se quedan manuales hasta que el equipo esté normalizado.

Qué falta para habilitar los seis restantes: que `MonitoreoPPRO.equipo` deje
de ser texto libre y referencie el maestro de equipos —el mismo cambio que se
hizo con `BloquePlan`—. El maestro además no tiene todavía las Rovemas ni las
torres E1/E2 como registros.
"""

from django.db import migrations


# codigo -> criterio. Solo los inequívocos.
EVIDENCIA = {
    # La trazabilidad de la leche es la asignación de silos del lote: qué
    # estanques la aportaron y cuánto de cada uno.
    "CCAA.REC.FORM.005": {"fuente": "asignacion_leche"},
    # El PCC 1 se corre en cualquiera de los tres evaporadores.
    "CCAA.Cond.FORM.010": {
        "fuente": "control_proceso",
        "equipo_en": ["VEB", "SCH2", "SCH3"],
    },
    # La hoja de pulverización es el control de proceso de las torres.
    "CCAA.Sec.FORM.025": {"fuente": "control_proceso", "equipo_en": ["E1", "E2"]},
    # El fisicoquímico es el análisis del lote. Es el único documento que
    # apunta a esa fuente, así que no hay con qué confundirlo.
    "CCAA.Sec.FORM.001": {"fuente": "analisis"},
    # El detector de metales es un tipo propio de monitoreo: inequívoco.
    "CCAA.ENV.FORM.001": {
        "fuente": "monitoreo_ppro",
        "tipo": "detector_metales",
    },
}


def marcar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for codigo, criterio in EVIDENCIA.items():
        Documento.objects.filter(codigo=codigo).update(evidencia=criterio)


def desmarcar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")
    Documento.objects.filter(codigo__in=EVIDENCIA).update(evidencia={})


class Migration(migrations.Migration):

    dependencies = [("maestros", "0011_documentoliberacion_evidencia")]

    operations = [migrations.RunPython(marcar, desmarcar)]
