"""
Los criterios de evidencia pasan a nombrar equipos por su código del maestro.

Estaban escritos contra la lista fija de `produccion` —«VEB», «SCH2», «E1»—
que ya no existe. El maestro usa otro alfabeto («veb», «scheffers2», «e1»), y
mientras hubo dos, un criterio no podía compararse contra el registro sin
traducir en el medio.

Y con el equipo hecho referencia se pueden atar dos documentos más, que es lo
que este cambio perseguía:

- `Sec.FORM.022` · PPRO 3 · Monitoreo de PPRO E1-E2
- `Sec.FORM.005` · PPRO 4 · Monitoreo PPRO Rovemas 3 y 4

Los dos exigen además el **tipo** de monitoreo, no solo la máquina. Sin eso,
un checklist de cuerpos extraños hecho en la Rovema 3 —que es otro documento,
`Sec.FORM.007`— daría por cumplido el PPRO 4, y el PPRO 4 vigila presión de
aire y roce de válvulas: cosas que nadie habría mirado. Un documento cumplido
de más deja salir producto.

El detector de metales (`ENV.FORM.001`) no lleva equipo a propósito: es un
PCC del envasado que no cuelga de una máquina del maestro.
"""

from django.db import migrations


#: Los tres tipos que un «Monitoreo PPRO» de máquina cubre. Los otros dos que
#: existen —cuerpos extraños y detector de metales— tienen documento propio.
TIPOS_PPRO_DE_MAQUINA = ["aire_transporte", "aire_secundario", "roce_valvulas"]

#: codigo → criterio nuevo.
CRITERIOS = {
    "CCAA.Cond.FORM.010": {
        "fuente": "control_proceso",
        "equipo_en": ["veb", "scheffers2", "scheffers3"],
    },
    "CCAA.Sec.FORM.025": {
        "fuente": "control_proceso",
        "equipo_en": ["e1", "e2"],
    },
    "CCAA.Sec.FORM.022": {
        "fuente": "monitoreo_ppro",
        "equipo_en": ["e1", "e2"],
        "tipo_en": TIPOS_PPRO_DE_MAQUINA,
    },
    "CCAA.Sec.FORM.005": {
        "fuente": "monitoreo_ppro",
        "equipo_en": ["rovema3", "rovema4"],
        "tipo_en": TIPOS_PPRO_DE_MAQUINA,
    },
}

#: Cómo estaban antes, para poder revertir sin inventar.
ANTERIORES = {
    "CCAA.Cond.FORM.010": {
        "fuente": "control_proceso",
        "equipo_en": ["VEB", "SCH2", "SCH3"],
    },
    "CCAA.Sec.FORM.025": {
        "fuente": "control_proceso",
        "equipo_en": ["E1", "E2"],
    },
    "CCAA.Sec.FORM.022": {},
    "CCAA.Sec.FORM.005": {},
}


def aplicar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for codigo, criterio in CRITERIOS.items():
        Documento.objects.filter(codigo=codigo).update(evidencia=criterio)


def revertir(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for codigo, criterio in ANTERIORES.items():
        Documento.objects.filter(codigo=codigo).update(evidencia=criterio)


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0018_alter_equipo_tipo"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
