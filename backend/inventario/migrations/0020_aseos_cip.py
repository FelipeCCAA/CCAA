import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


AREAS = [
    ("aseo", "Aseo y saneamiento"),
    ("recepcion", "Recepción"),
    ("condensacion", "Condensación"),
    ("secado", "Secado"),
    ("envase", "Envase"),
    ("calidad", "Calidad"),
    ("bodega", "Bodega"),
    ("compras", "Compras"),
    ("despacho", "Despacho"),
    ("mantenimiento", "Mantenimiento"),
    ("administracion", "Administración general"),
]


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0019_ejecucionmrp_error_ejecucionmrp_estado_and_more"),
        ("maestros", "0027_tenant_maestros"),
        ("usuarios", "0013_area_aseo"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="ciclocip", name="documento_codigo",
            field=models.CharField(blank=True, help_text="Código del formulario o procedimiento de Calidad aplicable.", max_length=60),
        ),
        migrations.AddField(
            model_name="ciclocip", name="ejecutado_por",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="aseos_ejecutados", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="ciclocip", name="inicio_real",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ciclocip", name="ph_final",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True),
        ),
        migrations.AddField(
            model_name="ciclocip", name="seccion",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name="ciclocip", name="silo",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ciclos_cip", to="maestros.silo"),
        ),
        migrations.AddField(
            model_name="ciclocip", name="tipo_aseo",
            field=models.CharField(choices=[("cip", "CIP"), ("cop", "COP"), ("general", "Aseo general")], default="cip", max_length=20),
        ),
        migrations.AddField(
            model_name="ciclocip", name="tipo_objetivo",
            field=models.CharField(choices=[("equipo", "Máquina / equipo"), ("silo", "Silo / tanque"), ("seccion", "Área / sección")], default="equipo", max_length=20),
        ),
        migrations.AddField(
            model_name="ciclocip", name="verificacion",
            field=models.CharField(choices=[("pendiente", "Pendiente"), ("conforme", "Conforme"), ("observado", "Observado")], default="pendiente", max_length=20),
        ),
        migrations.AddField(
            model_name="ciclocip", name="verificado_por",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="aseos_verificados", to=settings.AUTH_USER_MODEL),
        ),
        migrations.CreateModel(
            name="EtapaCIP",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveSmallIntegerField(default=1)),
                ("tipo", models.CharField(choices=[("pre_enjuague", "Pre-enjuague"), ("soda", "Soda cáustica"), ("enjuague", "Enjuague"), ("acido", "Ácido nítrico"), ("sanitizacion", "Sanitización"), ("otro", "Otra etapa")], max_length=20)),
                ("duracion_min", models.PositiveIntegerField(blank=True, null=True)),
                ("temperatura_c", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("caudal", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("conductividad", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("concentracion_pct", models.DecimalField(blank=True, decimal_places=3, max_digits=6, null=True)),
                ("cumple", models.BooleanField(blank=True, null=True)),
                ("observaciones", models.CharField(blank=True, max_length=250)),
                ("ciclo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="etapas", to="inventario.ciclocip")),
            ],
            options={
                "ordering": ["orden", "id"],
                "constraints": [models.UniqueConstraint(fields=("ciclo", "orden"), name="cip_etapa_orden_unico")],
            },
        ),
        migrations.AlterField(model_name="insumo", name="area", field=models.CharField(choices=AREAS, max_length=30)),
        migrations.AlterField(model_name="ciclocip", name="area", field=models.CharField(choices=AREAS, max_length=30)),
        migrations.AlterField(model_name="bodega", name="area", field=models.CharField(choices=AREAS, default="bodega", max_length=30)),
        migrations.AlterField(model_name="solicitudcompra", name="area", field=models.CharField(choices=AREAS, max_length=30)),
        migrations.AlterField(model_name="solicitudmaterial", name="area", field=models.CharField(choices=AREAS, max_length=30)),
    ]
