from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("produccion", "0016_remove_palletproducto_pallet_kg_maximo_500_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="registroenvase",
            name="solicitud_firma",
            field=models.CharField(
                max_length=64, null=True, blank=True, editable=False,
                help_text="SHA-256 del pedido original; nulo para registros anteriores a OP-08.",
            ),
        ),
    ]
