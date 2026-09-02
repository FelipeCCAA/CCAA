from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maestros", "0031_sembrar_siglas")]

    operations = [
        migrations.AddField(
            model_name="especificacion",
            name="tipo_analisis",
            field=models.CharField(
                choices=[
                    ("lote", "Producto / lote"),
                    ("silo", "Intermedio en silo"),
                ],
                default="lote",
                help_text=(
                    "Separa los rangos del producto terminado de los controles "
                    "fisicoquímicos aplicables a una salida intermedia en silo."
                ),
                max_length=10,
                verbose_name="Tipo de análisis",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="especificacion",
            name="especificacion_version_unica_por_producto",
        ),
        migrations.AddConstraint(
            model_name="especificacion",
            constraint=models.UniqueConstraint(
                fields=("producto", "tipo_analisis", "version"),
                name="especificacion_version_unica_por_producto_y_tipo",
            ),
        ),
    ]
