import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("procesos", "0008_corridadescremacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="entradaproceso",
            name="salida_origen",
            field=models.ForeignKey(
                blank=True,
                help_text="Resultado intermedio liberado que aporta esta entrada.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="usos_como_origen",
                to="procesos.salidaproceso",
            ),
        ),
    ]
