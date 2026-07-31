"""
Siembra los equipos que hasta ahora eran una lista fija en el código.

`consume_leche` reproduce exactamente la tupla `EVAPORADORES` que gobernaba
el balance: Scheffers 2, Scheffers 3 y VEB. Cambiarlo aquí cambia cuánta
leche resta el plan, así que se siembra igual a lo que había y se deja al
administrador la decisión de tocarlo.
"""

from django.db import migrations


# (codigo, nombre, tipo, consume_leche) en el orden en que se leen en el Excel.
EQUIPOS = [
    ("carga_precondensado", "Carga de precondensado", "carga", False),
    ("scheffers2", "Evaporador Scheffers 2", "evaporador", True),
    ("scheffers3", "Evaporador Scheffers 3", "evaporador", True),
    ("veb", "Evaporador VEB", "evaporador", True),
    ("linea1", "Línea 1", "linea", False),
    ("linea2", "Línea 2", "linea", False),
    ("linea_mantequilla", "Línea de mantequilla", "linea", False),
]


def sembrar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")

    for orden, (codigo, nombre, tipo, consume) in enumerate(EQUIPOS):
        Equipo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "tipo": tipo,
                "consume_leche": consume,
                "orden": orden,
                "activo": True,
            },
        )


def borrar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(codigo__in=[e[0] for e in EQUIPOS]).delete()


class Migration(migrations.Migration):

    dependencies = [("maestros", "0009_equipo")]

    operations = [migrations.RunPython(sembrar, borrar)]
