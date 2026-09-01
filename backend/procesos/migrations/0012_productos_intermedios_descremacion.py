import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0031_sembrar_siglas"),
        ("procesos", "0011_rutas_productivas_especificas"),
    ]

    operations = [
        migrations.AddField(
            model_name="corridadescremacion",
            name="producto_crema",
            field=models.ForeignKey(
                blank=True,
                help_text="Identidad del intermedio que queda en el TK de crema.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corridas_como_crema",
                to="maestros.producto",
            ),
        ),
        migrations.AddField(
            model_name="corridadescremacion",
            name="producto_descremada",
            field=models.ForeignKey(
                blank=True,
                help_text="Identidad del intermedio que queda en el TK de descremada.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corridas_como_descremada",
                to="maestros.producto",
            ),
        ),
        migrations.AddField(
            model_name="corridamantequilla",
            name="operacion_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
