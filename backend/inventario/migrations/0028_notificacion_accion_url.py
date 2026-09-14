from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0027_unidadrework_movimientorework_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificacion",
            name="accion_url",
            field=models.CharField(blank=True, max_length=240),
        ),
    ]
