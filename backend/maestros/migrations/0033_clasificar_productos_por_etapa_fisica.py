from django.db import migrations
from django.db.models import Q


def clasificar_productos(apps, schema_editor):
    Producto = apps.get_model("maestros", "Producto")

    Producto.objects.filter(
        Q(categoria__in=["precondensado", "crema", "leche_fresca_est"])
        | Q(tipo="descremada", unidad_base="L")
        | Q(
            categoria__in=["leche_polvo", "mantequilla"],
            formato="granel",
        )
    ).update(naturaleza="intermedio")

    Producto.objects.filter(
        Q(categoria="leche_polvo", formato="saco_25kg")
        | Q(categoria="mantequilla", formato="caja_20kg")
    ).update(naturaleza="terminado")


class Migration(migrations.Migration):
    dependencies = [("maestros", "0032_especificacion_tipo_analisis")]

    operations = [
        migrations.RunPython(clasificar_productos, migrations.RunPython.noop),
    ]
