import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0027_tenant_maestros"),
        ("procesos", "0004_ejecucionproceso_vale_entradaproceso_silo_and_more"),
        ("produccion", "0006_lote_vale"),
    ]

    operations = [
        migrations.AddField(
            model_name="lote",
            name="equipo",
            field=models.ForeignKey(
                blank=True,
                help_text="Equipo en el que se ejecuta esta corrida de producción.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lotes_produccion",
                to="maestros.equipo",
                verbose_name="Máquina / equipo",
            ),
        ),
        migrations.AddField(
            model_name="lote",
            name="ejecucion",
            field=models.OneToOneField(
                blank=True,
                help_text="Identidad única de la corrida dentro de la cadena industrial.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lote_produccion",
                to="procesos.ejecucionproceso",
                verbose_name="Ejecución del proceso",
            ),
        ),
    ]
