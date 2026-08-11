import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


def completar_sucursal(apps, schema_editor):
    Ejecucion = apps.get_model("procesos", "EjecucionProceso")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    for ejecucion in Ejecucion.objects.filter(sucursal__isnull=True).select_related("equipo"):
        if ejecucion.equipo_id and ejecucion.equipo.sucursal_id:
            sucursal_id = ejecucion.equipo.sucursal_id
        else:
            candidatas = list(Sucursal.objects.values_list("pk", flat=True))
            if len(candidatas) != 1:
                raise RuntimeError(
                    f"No se puede inferir una única sucursal para la ejecución {ejecucion.pk}."
                )
            sucursal_id = candidatas[0]
        ejecucion.sucursal_id = sucursal_id
        ejecucion.save(update_fields=["sucursal"])


class Migration(migrations.Migration):
    dependencies = [
        ("procesos", "0002_sembrar_flujo_lacteo"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]
    operations = [
        migrations.RunPython(completar_sucursal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="ejecucionproceso", name="sucursal",
                    field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ejecuciones_proceso", to="usuarios.sucursal"),
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="ejecucionproceso", name="sucursal",
                    field=models.ForeignKey(default=usuarios.tenancy.sucursal_predeterminada_pruebas, on_delete=django.db.models.deletion.PROTECT, related_name="ejecuciones_proceso", to="usuarios.sucursal"),
                )
            ],
        ),
    ]
