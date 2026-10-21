from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("procesos", "0023_evento_operacion_id")]

    operations = [
        migrations.AddField(
            model_name="corridamantequilla",
            name="salida_crema",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="corridas_mantequilla", to="procesos.salidaproceso",
                help_text="Salida de crema elegida expresamente; las corridas históricas quedan sin atribución.",
            ),
        ),
    ]
