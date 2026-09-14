import uuid

from django.db import migrations, models
import django.db.models.deletion


def preparar_datos_historicos(apps, schema_editor):
    EjecucionMRP = apps.get_model("inventario", "EjecucionMRP")
    ResultadoMRP = apps.get_model("inventario", "ResultadoMRP")
    SolicitudCompra = apps.get_model("inventario", "SolicitudCompra")
    SemanaPlan = apps.get_model("planificacion", "SemanaPlan")

    semanas_validas = set(SemanaPlan.objects.values_list("pk", flat=True))
    for ejecucion in EjecucionMRP.objects.all().iterator():
        ejecucion.operacion_id = uuid.uuid4()
        semana_id = (ejecucion.parametros or {}).get("semana")
        try:
            semana_id = int(semana_id)
        except (TypeError, ValueError):
            semana_id = None
        if semana_id in semanas_validas:
            ejecucion.semana_id = semana_id
        ejecucion.save(update_fields=["operacion_id", "semana"])

        solicitud = SolicitudCompra.objects.filter(
            numero=f"SC-MRP-{ejecucion.pk}", ejecucion_mrp__isnull=True
        ).order_by("pk").first()
        if solicitud:
            solicitud.ejecucion_mrp_id = ejecucion.pk
            solicitud.save(update_fields=["ejecucion_mrp"])

    vistos = set()
    duplicados = []
    for resultado in ResultadoMRP.objects.order_by("pk").iterator():
        clave = (resultado.ejecucion_id, resultado.insumo_id)
        if clave in vistos:
            duplicados.append(resultado.pk)
        else:
            vistos.add(clave)
    if duplicados:
        ResultadoMRP.objects.filter(pk__in=duplicados).delete()

    activos = {}
    for ejecucion in EjecucionMRP.objects.filter(
        semana__isnull=False, estado__in=["pendiente", "en_curso"]
    ).order_by("-creada_en", "-pk"):
        if ejecucion.semana_id in activos:
            ejecucion.estado = "fallida"
            ejecucion.error = "Cerrada al migrar: existia otra ejecucion activa para la semana."
            ejecucion.save(update_fields=["estado", "error"])
        else:
            activos[ejecucion.semana_id] = ejecucion.pk


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0028_notificacion_accion_url"),
        ("planificacion", "0005_planificacion_semanal_normalizada"),
    ]

    operations = [
        migrations.AddField(
            model_name="ejecucionmrp",
            name="semana",
            field=models.ForeignKey(
                blank=True,
                help_text="Relacion operacional directa; null solo para ejecuciones historicas.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ejecuciones_mrp",
                to="planificacion.semanaplan",
            ),
        ),
        migrations.AddField(
            model_name="ejecucionmrp",
            name="operacion_id",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="solicitudcompra",
            name="ejecucion_mrp",
            field=models.OneToOneField(
                blank=True,
                help_text="Ejecucion que origino la solicitud; garantiza conversion idempotente.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="solicitud_compra",
                to="inventario.ejecucionmrp",
            ),
        ),
        migrations.RunPython(preparar_datos_historicos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ejecucionmrp",
            name="operacion_id",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddConstraint(
            model_name="ejecucionmrp",
            constraint=models.UniqueConstraint(
                condition=models.Q(estado__in=["pendiente", "en_curso"]),
                fields=("semana",),
                name="mrp_una_ejecucion_activa_por_semana",
            ),
        ),
        migrations.AddConstraint(
            model_name="resultadomrp",
            constraint=models.UniqueConstraint(
                fields=("ejecucion", "insumo"),
                name="resultado_mrp_unico_por_ejecucion_insumo",
            ),
        ),
    ]
