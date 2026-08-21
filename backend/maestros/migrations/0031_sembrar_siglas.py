"""
Siglas de los equipos que encabezan una corrida.

Se siembran porque los equipos también se siembran por migración: dejar la
sigla vacía haría que ningún lote pudiera proponer su código recién
instalado. Las que no encabezan corrida quedan en blanco a propósito.
"""

from django.db import migrations


SIGLAS = {
    "e1": "E1",
    "e2": "E2",
    "veb": "VB",
    "scheffers2": "S2",
    "scheffers3": "S3",
    "rovema3": "R3",
    "rovema4": "R4",
    "linea_mantequilla": "LM",
}


def sembrar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    for codigo, sigla in SIGLAS.items():
        Equipo.objects.filter(codigo=codigo).update(sigla=sigla)


def revertir(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(codigo__in=SIGLAS).update(sigla="")


class Migration(migrations.Migration):

    dependencies = [("maestros", "0030_equipo_sigla")]

    operations = [migrations.RunPython(sembrar, revertir)]
