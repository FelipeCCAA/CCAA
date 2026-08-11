import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


def completar_sucursal(apps, schema_editor):
    Semana = apps.get_model("planificacion", "SemanaPlan")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    Bloque = apps.get_model("planificacion", "BloquePlan")
    for semana in Semana.objects.filter(sucursal__isnull=True):
        candidatas = set(
            Bloque.objects.filter(semana_id=semana.pk)
            .exclude(equipo__sucursal_id=None)
            .values_list("equipo__sucursal_id", flat=True)
        )
        if not candidatas:
            candidatas = set(Sucursal.objects.values_list("pk", flat=True))
        if len(candidatas) != 1:
            raise RuntimeError(f"No se puede inferir una única sucursal para la semana {semana.pk}.")
        semana.sucursal_id = next(iter(candidatas))
        semana.save(update_fields=["sucursal"])


class Migration(migrations.Migration):
    dependencies = [
        ("planificacion", "0002_bloqueplan_equipo_fk"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]
    operations = [
        migrations.AddField(
            model_name="semanaplan", name="sucursal",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="semanas_planificacion", to="usuarios.sucursal"),
        ),
        migrations.RunPython(completar_sucursal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(model_name="semanaplan", name="sucursal", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="semanas_planificacion", to="usuarios.sucursal")),
            ],
            state_operations=[
                migrations.AlterField(model_name="semanaplan", name="sucursal", field=models.ForeignKey(default=usuarios.tenancy.sucursal_predeterminada_pruebas, on_delete=django.db.models.deletion.PROTECT, related_name="semanas_planificacion", to="usuarios.sucursal")),
            ],
        ),
        migrations.RemoveConstraint(model_name="semanaplan", name="semana_plan_unica_por_anio"),
        migrations.AddConstraint(
            model_name="semanaplan",
            constraint=models.UniqueConstraint(fields=("sucursal", "codigo", "anio"), name="semana_plan_unica_por_anio"),
        ),
    ]
