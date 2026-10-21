from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0031_op01_autorizacion_evidencia"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimientoinventario",
            name="operacion_id",
            field=models.UUIDField(
                blank=True,
                editable=False,
                help_text="Clave idempotente para operaciones manuales de inventario.",
                null=True,
                unique=True,
            ),
        ),
    ]
