from django.db import migrations


def reparar_lotes_suero(apps, schema_editor):
    Corrida = apps.get_model("procesos", "CorridaMantequilla")
    Lote = apps.get_model("produccion", "Lote")
    for corrida in Corrida.objects.filter(
        lote_suero_id__isnull=False,
        kg_suero__gt=0,
    ).iterator():
        Lote.objects.filter(pk=corrida.lote_suero_id).update(
            kg_producidos=corrida.kg_suero,
            estado="producido",
        )


class Migration(migrations.Migration):
    dependencies = [
        ("procesos", "0019_reservas_silo_y_plan_descremacion"),
        ("produccion", "0014_pallet_kg_maximo_500"),
    ]

    operations = [
        migrations.RunPython(reparar_lotes_suero, migrations.RunPython.noop),
    ]
