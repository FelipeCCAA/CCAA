from django.db import migrations
from django.db.models import F


def limpiar_autofirmas(apps, schema_editor):
    AnalisisSilo = apps.get_model("recepcion", "AnalisisSilo")
    AnalisisSilo.objects.filter(
        analista_id=F("visualizado_por_id")
    ).update(visualizado_por=None, visualizado_en=None)


class Migration(migrations.Migration):
    dependencies = [
        ("recepcion", "0023_analisissilo_alcohol_75_conforme_and_more"),
    ]

    operations = [
        migrations.RunPython(limpiar_autofirmas, migrations.RunPython.noop),
    ]
