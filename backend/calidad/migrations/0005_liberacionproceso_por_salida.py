import django.db.models.deletion
from django.db import migrations, models


def asociar_salida(apps, schema_editor):
    LiberacionProceso = apps.get_model("calidad", "LiberacionProceso")
    SalidaProceso = apps.get_model("procesos", "SalidaProceso")
    for decision in LiberacionProceso.objects.all().iterator():
        salida = SalidaProceso.objects.filter(
            ejecucion_id=decision.ejecucion_id,
            naturaleza="principal",
        ).order_by("id").first()
        if salida is None:
            salida = SalidaProceso.objects.filter(
                ejecucion_id=decision.ejecucion_id
            ).order_by("id").first()
        if salida is None:
            raise RuntimeError(
                f"La decisión de proceso {decision.pk} no tiene una salida trazable."
            )
        decision.salida_id = salida.pk
        decision.save(update_fields=["salida"])


class Migration(migrations.Migration):
    dependencies = [
        ("calidad", "0004_liberacionproceso"),
        ("procesos", "0008_corridadescremacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="liberacionproceso",
            name="salida",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="liberacion_calidad",
                to="procesos.salidaproceso",
            ),
        ),
        migrations.RunPython(asociar_salida, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="liberacionproceso",
            name="ejecucion",
        ),
        migrations.AlterField(
            model_name="liberacionproceso",
            name="salida",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="liberacion_calidad",
                to="procesos.salidaproceso",
            ),
        ),
    ]
