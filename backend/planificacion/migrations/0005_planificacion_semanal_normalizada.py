import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


TIPOS = [
    ("produccion", "Producción", "#2563EB", True, True, True),
    ("aseo", "Aseo", "#64748B", False, False, False),
    ("pnp", "PNP", "#DC2626", False, False, False),
    ("mantenimiento", "Mantenimiento", "#475569", False, False, False),
    ("preparacion", "Preparación", "#94A3B8", False, False, False),
    ("atraso_partida", "Atraso de partida", "#F59E0B", False, False, False),
    ("recepcion", "Recepción", "#0D9488", False, True, False),
    ("despacho", "Despacho", "#7C3AED", False, True, False),
    ("trasvasije", "Trasvasije", "#0891B2", False, True, False),
    ("ensayo", "Ensayo", "#DB2777", False, False, False),
    ("capacitacion", "Capacitación", "#16A34A", False, False, False),
]


def sembrar_y_normalizar(apps, schema_editor):
    Tipo = apps.get_model("planificacion", "TipoActividadPlan")
    Capacidad = apps.get_model("planificacion", "CapacidadProceso")
    Bloque = apps.get_model("planificacion", "BloquePlan")
    Equipo = apps.get_model("maestros", "Equipo")

    por_codigo = {}
    for codigo, nombre, color, producto, origen, capacidad in TIPOS:
        tipo, _ = Tipo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "color": color,
                "requiere_producto": producto,
                "requiere_origen": origen,
                "requiere_capacidad": capacidad,
                "activo": True,
            },
        )
        por_codigo[codigo] = tipo

    capacidades = {"scheffers2": Decimal("15900"), "scheffers3": Decimal("11000"), "veb": Decimal("12400")}
    for equipo in Equipo.objects.filter(codigo__in=capacidades):
        Capacidad.objects.get_or_create(
            equipo=equipo,
            vigente_desde=datetime.date(2000, 1, 1),
            defaults={"capacidad_hora": capacidades[equipo.codigo], "unidad": "L/h", "observacion": "Capacidad inicial del programa histórico"},
        )

    estados = {"A": "aseo", "P": "pnp", "M": "mantenimiento", "X": "preparacion", "AP": "atraso_partida"}
    zona = ZoneInfo("America/Santiago")
    for bloque in Bloque.objects.select_related("semana", "codigo"):
        clave = "produccion" if bloque.tipo == "produccion" else estados.get(bloque.estado_equipo, "preparacion")
        inicio_h = float(bloque.hora_inicio)
        fin_h = float(bloque.hora_fin)
        fecha = bloque.semana.fecha_inicio + datetime.timedelta(days=bloque.dia)

        def momento(hora):
            if hora == 24:
                return datetime.datetime.combine(fecha + datetime.timedelta(days=1), datetime.time.min, tzinfo=zona)
            horas = int(hora)
            minutos = round((hora - horas) * 60)
            return datetime.datetime.combine(fecha, datetime.time(horas, minutos), tzinfo=zona)

        bloque.tipo_actividad = por_codigo[clave]
        bloque.fecha_hora_inicio = momento(inicio_h)
        bloque.fecha_hora_fin = momento(fin_h)
        bloque.producto_id = bloque.codigo.producto_id if bloque.codigo_id else None
        bloque.origen_leche_id = bloque.codigo.mandante_id if bloque.codigo_id else None
        bloque.capacidad_hora = bloque.codigo.rendimiento_lh if bloque.codigo_id else None
        bloque.color = por_codigo[clave].color
        bloque.save(update_fields=["tipo_actividad", "fecha_hora_inicio", "fecha_hora_fin", "producto", "origen_leche", "capacidad_hora", "color"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0023_alter_ajusteinventario_options_and_more"),
        ("maestros", "0031_sembrar_siglas"),
        ("planificacion", "0004_semanaplan_cancelada_en_semanaplan_cancelada_por_and_more"),
        ("produccion", "0014_pallet_kg_maximo_500"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TipoActividadPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.SlugField(max_length=30, unique=True)),
                ("nombre", models.CharField(max_length=80)),
                ("color", models.CharField(max_length=7)),
                ("requiere_producto", models.BooleanField(default=False)),
                ("requiere_origen", models.BooleanField(default=False)),
                ("requiere_capacidad", models.BooleanField(default=False)),
                ("activo", models.BooleanField(default=True)),
            ],
            options={"ordering": ["nombre"]},
        ),
        migrations.AddField(model_name="bloqueplan", name="actualizado_en", field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name="bloqueplan", name="capacidad_hora", field=models.DecimalField(blank=True, decimal_places=2, help_text="Capacidad vigente copiada al programar; conserva el cálculo histórico.", max_digits=14, null=True)),
        migrations.AddField(model_name="bloqueplan", name="cliente", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades_planificadas", to="inventario.clientedespacho")),
        migrations.AddField(model_name="bloqueplan", name="color", field=models.CharField(blank=True, max_length=7)),
        migrations.AddField(model_name="bloqueplan", name="creado_por", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades_planificadas_creadas", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="bloqueplan", name="fecha_hora_fin", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="bloqueplan", name="fecha_hora_inicio", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="bloqueplan", name="orden_produccion", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades_planificadas", to="produccion.ordenproduccion")),
        migrations.AddField(model_name="bloqueplan", name="origen_leche", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades_origen", to="maestros.mandante")),
        migrations.AddField(model_name="bloqueplan", name="producto", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades_planificadas", to="maestros.producto")),
        migrations.CreateModel(
            name="MovimientoPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_hora", models.DateTimeField(db_index=True)),
                ("tipo", models.CharField(choices=[("stock_inicial", "Stock inicial"), ("recepcion", "Recepción"), ("despacho", "Despacho"), ("trasvasije_salida", "Trasvasije salida"), ("trasvasije_entrada", "Trasvasije entrada"), ("ajuste", "Ajuste identificado")], max_length=25)),
                ("cantidad", models.DecimalField(decimal_places=2, help_text="Positiva para entradas; un ajuste puede ser positivo o negativo.", max_digits=14)),
                ("documento", models.CharField(blank=True, max_length=80)),
                ("observacion", models.TextField(blank=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actividad", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="movimientos", to="planificacion.bloqueplan")),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_plan_creados", to=settings.AUTH_USER_MODEL)),
                ("propietario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="movimientos_plan", to="maestros.mandante")),
                ("semana", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movimientos_plan", to="planificacion.semanaplan")),
            ],
            options={"ordering": ["fecha_hora", "id"]},
        ),
        migrations.AddField(model_name="bloqueplan", name="tipo_actividad", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="actividades", to="planificacion.tipoactividadplan")),
        migrations.CreateModel(
            name="CapacidadProceso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vigente_desde", models.DateField(db_index=True)),
                ("capacidad_hora", models.DecimalField(decimal_places=2, max_digits=14)),
                ("unidad", models.CharField(default="L/h", max_length=20)),
                ("observacion", models.CharField(blank=True, max_length=250)),
                ("equipo", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="capacidades_planificacion", to="maestros.equipo")),
            ],
            options={"ordering": ["equipo", "-vigente_desde"], "constraints": [models.UniqueConstraint(fields=("equipo", "vigente_desde"), name="capacidad_equipo_vigencia_unica"), models.CheckConstraint(condition=models.Q(("capacidad_hora__gt", 0)), name="capacidad_proceso_positiva")]},
        ),
        migrations.CreateModel(
            name="StockSeguridadPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vigente_desde", models.DateField(db_index=True)),
                ("cantidad", models.DecimalField(decimal_places=2, max_digits=14)),
                ("propietario", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="stocks_seguridad_plan", to="maestros.mandante")),
            ],
            options={"ordering": ["propietario", "-vigente_desde"], "constraints": [models.UniqueConstraint(fields=("propietario", "vigente_desde"), name="stock_seguridad_vigencia_unica"), models.CheckConstraint(condition=models.Q(("cantidad__gte", 0)), name="stock_seguridad_no_negativo")]},
        ),
        migrations.CreateModel(
            name="VersionSemanaPlan",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.PositiveIntegerField()),
                ("instantanea", models.JSONField()),
                ("publicada_en", models.DateTimeField(auto_now_add=True)),
                ("publicada_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versiones_plan_publicadas", to=settings.AUTH_USER_MODEL)),
                ("semana", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="versiones", to="planificacion.semanaplan")),
            ],
            options={"ordering": ["semana", "-numero"], "constraints": [models.UniqueConstraint(fields=("semana", "numero"), name="version_semana_numero_unico")]},
        ),
        migrations.RunPython(sembrar_y_normalizar, migrations.RunPython.noop),
    ]
