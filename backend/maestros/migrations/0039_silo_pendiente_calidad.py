from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("maestros", "0038_formatoenvasado_tipo_unidad_logistica_and_more")]

    operations = [migrations.AlterField(
        model_name="silo", name="estado",
        field=models.CharField(
            choices=[("disponible", "Disponible"), ("recibiendo", "Recibiendo"),
                     ("en_uso", "En uso"), ("reservado", "Reservado"),
                     ("bloqueado_calidad", "Bloqueado por Calidad"),
                     ("pendiente_calidad", "Pendiente de Calidad"),
                     ("pendiente_cip", "Pendiente de CIP"), ("en_cip", "En CIP"),
                     ("fuera_servicio", "Fuera de servicio")],
            db_index=True, default="disponible", max_length=30, verbose_name="Estado operacional",
        ),
    )]
