import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("procesos", "0021_remove_entradaproceso_entrada_de_un_lote_o_de_un_silo_and_more"),
        ("produccion", "0016_remove_palletproducto_pallet_kg_maximo_500_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="corridamantequilla",
            name="kg_reproceso",
            field=models.DecimalField(decimal_places=3, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="corridamantequilla",
            name="lote_reproceso",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corridas_como_reproceso_mantequilla",
                to="produccion.lote",
            ),
        ),
        migrations.AddField(
            model_name="corridamantequilla",
            name="motivo_reproceso",
            field=models.CharField(blank=True, max_length=250),
        ),
        migrations.AddConstraint(
            model_name="corridamantequilla",
            constraint=models.CheckConstraint(
                condition=models.Q(("kg_mantequilla__isnull", True), ("kg_mantequilla__gt", 0), _connector="OR"),
                name="mantequilla_salida_positiva",
            ),
        ),
        migrations.AddConstraint(
            model_name="corridamantequilla",
            constraint=models.CheckConstraint(
                condition=models.Q(("kg_reproceso__gte", 0)),
                name="mantequilla_reproceso_no_negativo",
            ),
        ),
    ]
