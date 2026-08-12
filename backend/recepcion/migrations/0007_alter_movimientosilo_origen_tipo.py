from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("recepcion", "0006_tenant_recepcion")]

    operations = [
        migrations.AlterField(
            model_name="movimientosilo",
            name="origen_tipo",
            field=models.CharField(
                blank=True,
                choices=[
                    ("recepcion", "Recepción"),
                    ("estandarizacion", "Estandarización"),
                    ("lote", "Consumo de lote"),
                    ("ajuste", "Ajuste manual"),
                ],
                max_length=20,
                verbose_name="Origen",
            ),
        ),
    ]
