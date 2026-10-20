from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("calidad", "0006_analisis_lote_liberacion_proceso")]

    # Solo estructura aditiva. No se asigna una firma a expedientes históricos
    # ni se escribe su estado: deberán revisarse por los canales de Calidad.
    operations = [
        migrations.AddField(model_name=nombre, name=campo, field=tipo)
        for nombre in ("liberacion", "liberacionproceso")
        for campo, tipo in (
            ("firma_id", models.UUIDField(blank=True, editable=False, null=True)),
            ("version_evidencia", models.PositiveIntegerField(default=0, editable=False)),
            ("version_firmada", models.PositiveIntegerField(blank=True, editable=False, null=True)),
            ("evidencia_firmada", models.JSONField(blank=True, default=dict, editable=False)),
        )
    ]
