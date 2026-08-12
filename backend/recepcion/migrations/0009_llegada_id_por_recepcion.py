"""
Reparte los `llegada_id` del histórico, que la 0008 dejó todos iguales.

`AddField` con `default=uuid.uuid4` **evalúa el default una sola vez** y escribe
ese mismo valor en todas las filas existentes. Comprobado sobre una copia de la
base de desarrollo: las seis recepciones que había —cuatro guías distintas,
cuatro fechas distintas— quedaron con el mismo UUID.

Importa porque `llegada_id` es ahora lo que agrupa los módulos de un camión para
compartir los controles de calidad: con todo el histórico en una sola llegada,
decidir la calidad de cualquiera de ellas propagaría sus resultados al resto.

Se agrupa por lo que identificaba una carga **antes** de que existiera el campo
—sucursal, fecha, camión y guía—, que es la misma regla que usaba la vista hasta
ahora. Las que no traen ni camión ni guía no tienen carga a la que pertenecer y
se quedan **cada una sola**: es la respuesta segura, porque juntarlas mezclaría
controles entre camiones distintos, y separarlas de más solo obliga a teclear.

No tiene vuelta atrás porque no hay nada que devolver: el estado anterior era un
único valor repetido, y reponerlo sería reintroducir el defecto.
"""

import uuid

from django.db import migrations


def repartir(apps, schema_editor):
    Recepcion = apps.get_model("recepcion", "Recepcion")

    cargas = {}

    for recepcion in Recepcion.objects.all().order_by("pk"):
        identificado = recepcion.vehiculo_id is not None or bool(recepcion.guia)

        clave = (
            (
                recepcion.sucursal_id,
                recepcion.fecha,
                recepcion.vehiculo_id,
                recepcion.guia,
            )
            if identificado
            else ("sola", recepcion.pk)
        )

        if clave not in cargas:
            cargas[clave] = uuid.uuid4()

        Recepcion.objects.filter(pk=recepcion.pk).update(llegada_id=cargas[clave])


class Migration(migrations.Migration):

    dependencies = [("recepcion", "0008_recepcion_llegada_id")]

    operations = [
        migrations.RunPython(repartir, migrations.RunPython.noop),
    ]
