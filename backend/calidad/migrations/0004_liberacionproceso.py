import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("calidad", "0003_tenant_registro_equipo"),
        ("procesos", "0008_corridadescremacion"),
        ("recepcion", "0027_despacholeche_anulado_en_despacholeche_anulado_por_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="LiberacionProceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente"), ("liberado", "Liberado"), ("rechazado", "Rechazado")], db_index=True, default="pendiente", max_length=20)),
                ("decidida_en", models.DateTimeField(blank=True, null=True)),
                ("observacion", models.TextField(blank=True)),
                ("analisis_silo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="liberaciones_proceso", to="recepcion.analisissilo")),
                ("decidida_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="liberaciones_proceso", to=settings.AUTH_USER_MODEL)),
                ("ejecucion", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="liberacion_calidad", to="procesos.ejecucionproceso")),
            ],
            options={
                "verbose_name": "Liberación de resultado de proceso",
                "verbose_name_plural": "Liberaciones de resultados de proceso",
                "ordering": ["-decidida_en", "-id"],
            },
        ),
    ]
