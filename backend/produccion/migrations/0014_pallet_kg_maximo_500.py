from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("produccion", "0013_correccionlote")]

    operations = [
        migrations.AddConstraint(
            model_name="palletproducto",
            constraint=models.CheckConstraint(
                condition=models.Q(("kg_neto__lte", 500)),
                name="pallet_kg_maximo_500",
            ),
        ),
    ]
