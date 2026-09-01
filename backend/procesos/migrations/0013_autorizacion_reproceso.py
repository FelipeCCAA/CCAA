import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("procesos", "0012_productos_intermedios_descremacion"),
        ("produccion", "0014_pallet_kg_maximo_500"),
    ]

    operations = [
        migrations.CreateModel(
            name="AutorizacionReproceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origen", models.CharField(choices=[("rechazo", "Producto rechazado"), ("saco_danado", "Saco dañado"), ("excedente", "Excedente de proceso"), ("recuperable", "Material recuperable")], max_length=20)),
                ("estado", models.CharField(choices=[("pendiente", "Pendiente de Calidad"), ("aprobado", "Rework aprobado"), ("bloqueado", "Rework bloqueado"), ("destruido", "Material destruido")], db_index=True, default="pendiente", max_length=20)),
                ("cantidad_kg", models.DecimalField(decimal_places=3, max_digits=14)),
                ("motivo", models.TextField()),
                ("observacion_calidad", models.TextField(blank=True)),
                ("solicitado_en", models.DateTimeField(auto_now_add=True)),
                ("decidido_en", models.DateTimeField(blank=True, null=True)),
                ("decidido_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reprocesos_decididos", to=settings.AUTH_USER_MODEL)),
                ("lote", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="autorizacion_reproceso", to="produccion.lote")),
                ("solicitado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reprocesos_solicitados", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-solicitado_en", "-id"]},
        ),
    ]
