"""
Marca qué equipos consumen materiales del MRP.

Repara una regresión de la migración `0017`. El MRP semanal elegía sus bloques
con `equipo.tipo == "linea"`, escrito cuando las líneas 1 y 2 eran de ese tipo.
Al reconocerlas como las torres Egron y cambiarles el tipo a `torre`, sus
bloques dejaron de contar: el MRP siguió corriendo y devolviendo resultados,
solo que sin los materiales de secado. Una orden de compra corta no se ve
distinta de una completa.

La regla pasa al maestro, como `consume_leche`, para que no vuelva a depender
de una cadena de texto en el código.

Quiénes la llevan: el equipo del **final** de la cadena. La torre envasa el
polvo y la línea de mantequilla su producto; el evaporador que las alimenta no
—marcarlo pediría los sacos dos veces, que es el mismo error que
`consume_leche` evita por el otro extremo—.
"""

from django.db import migrations


#: Los que envasan. Las Rovemas no entran: no se programan en la carta Gantt,
#: así que no hay bloque suyo que contar, y marcarlas no cambiaría nada hoy
#: pero duplicaría el consumo el día que se programen.
CONSUMEN_MATERIALES = ["e1", "e2", "linea_mantequilla"]


def aplicar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")

    Equipo.objects.filter(codigo__in=CONSUMEN_MATERIALES).update(
        consume_materiales=True
    )


def revertir(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")

    Equipo.objects.update(consume_materiales=False)


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0024_equipo_consume_materiales"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
