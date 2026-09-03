from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("maestros", "0034_normalizar_codigos_silos_recepcion_confirmados"),
        ("procesos", "0018_rutas_crema_despacho_directo"),
    ]

    operations = [
        migrations.AddField(
            model_name="corridadescremacion",
            name="fuente_plan",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="corridadescremacion",
            name="litros_crema_plan",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="corridadescremacion",
            name="litros_descremada_plan",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="corridadescremacion",
            name="plan_confirmado_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="corridadescremacion",
            name="plan_confirmado_por",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="planes_descremacion_confirmados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name="corridadescremacion",
            constraint=models.CheckConstraint(
                condition=models.Q(litros_descremada_plan__isnull=True)
                | models.Q(litros_descremada_plan__gt=0),
                name="descremacion_plan_descremada_positivo",
            ),
        ),
        migrations.AddConstraint(
            model_name="corridadescremacion",
            constraint=models.CheckConstraint(
                condition=models.Q(litros_crema_plan__isnull=True)
                | models.Q(litros_crema_plan__gt=0),
                name="descremacion_plan_crema_positivo",
            ),
        ),
        migrations.CreateModel(
            name="ReservaSiloProceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tipo", models.CharField(choices=[("origen", "Material de origen"), ("destino", "Capacidad de destino")], max_length=10)),
                ("estado", models.CharField(choices=[("activa", "Activa"), ("consumida", "Consumida"), ("liberada", "Liberada")], db_index=True, default="activa", max_length=12)),
                ("cantidad_planificada", models.DecimalField(decimal_places=2, max_digits=14)),
                ("cantidad_real", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("cerrada_en", models.DateTimeField(blank=True, null=True)),
                ("ejecucion", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservas_silo", to="procesos.ejecucionproceso")),
                ("producto", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reservas_silo", to="maestros.producto")),
                ("silo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reservas_proceso", to="maestros.silo")),
            ],
            options={"ordering": ["ejecucion_id", "silo_id", "tipo"]},
        ),
        migrations.AddConstraint(
            model_name="reservasiloproceso",
            constraint=models.CheckConstraint(
                condition=models.Q(cantidad_planificada__gt=0),
                name="reserva_silo_cantidad_positiva",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservasiloproceso",
            constraint=models.UniqueConstraint(
                fields=("ejecucion", "silo", "tipo"),
                name="reserva_silo_unica_por_ejecucion",
            ),
        ),
        migrations.AddConstraint(
            model_name="reservasiloproceso",
            constraint=models.UniqueConstraint(
                condition=models.Q(estado="activa", tipo="destino"),
                fields=("silo",),
                name="reserva_destino_activa_unica_por_silo",
            ),
        ),
    ]
