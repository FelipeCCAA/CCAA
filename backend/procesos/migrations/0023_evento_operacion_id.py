from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("procesos", "0022_balance_mantequilla_reproceso")]

    operations = [
        migrations.AddField(
            model_name="eventoproceso",
            name="operacion_id",
            field=models.UUIDField(
                blank=True,
                editable=False,
                help_text="Clave idempotente de la accion que origino el evento.",
                null=True,
                unique=True,
            ),
        ),
    ]
