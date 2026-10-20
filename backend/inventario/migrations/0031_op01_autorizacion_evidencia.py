from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventario", "0030_despacho_cancelacion")]

    operations = [
        migrations.AddField(
            model_name="despacho",
            name="autorizacion_evidencia",
            field=models.JSONField(blank=True, default=dict, editable=False),
        ),
    ]
