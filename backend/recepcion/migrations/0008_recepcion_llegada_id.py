import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("recepcion", "0007_alter_movimientosilo_origen_tipo")]

    operations = [
        migrations.AddField(
            model_name="recepcion",
            name="llegada_id",
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Agrupa todos los modulos que llegaron en el mismo camion.",
                verbose_name="Identificador de llegada",
            ),
        ),
    ]
