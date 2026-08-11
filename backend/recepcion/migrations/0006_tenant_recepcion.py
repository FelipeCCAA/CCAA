import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


def completar_sucursal(apps, schema_editor):
    Recepcion = apps.get_model("recepcion", "Recepcion")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    for recepcion in Recepcion.objects.filter(sucursal__isnull=True).select_related("vehiculo", "silo"):
        candidatas = {
            valor for valor in (
                getattr(recepcion.vehiculo, "sucursal_id", None),
                getattr(recepcion.silo, "sucursal_id", None),
            ) if valor
        }
        if not candidatas:
            candidatas = set(Sucursal.objects.values_list("pk", flat=True))
        if len(candidatas) != 1:
            raise RuntimeError(f"No se puede inferir una única sucursal para la recepción {recepcion.pk}.")
        recepcion.sucursal_id = next(iter(candidatas))
        recepcion.save(update_fields=["sucursal"])


class Migration(migrations.Migration):
    dependencies = [
        ("recepcion", "0005_recepcion_carga_recoleccion"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]
    operations = [
        migrations.AddField(model_name="recepcion", name="sucursal", field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="recepciones_leche", to="usuarios.sucursal")),
        migrations.RunPython(completar_sucursal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.AlterField(model_name="recepcion", name="sucursal", field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recepciones_leche", to="usuarios.sucursal"))],
            state_operations=[migrations.AlterField(model_name="recepcion", name="sucursal", field=models.ForeignKey(default=usuarios.tenancy.sucursal_predeterminada_pruebas, on_delete=django.db.models.deletion.PROTECT, related_name="recepciones_leche", to="usuarios.sucursal"))],
        ),
    ]
