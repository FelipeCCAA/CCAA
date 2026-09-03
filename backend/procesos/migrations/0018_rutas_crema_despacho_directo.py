from django.db import migrations


def crear_rutas_crema_despacho(apps, schema_editor):
    Proceso = apps.get_model("procesos", "Proceso")
    Etapa = apps.get_model("procesos", "EtapaProceso")
    Ruta = apps.get_model("procesos", "RutaProducto")
    Producto = apps.get_model("maestros", "Producto")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    proceso, _ = Proceso.objects.get_or_create(
        codigo="ruta-crema-despacho",
        version=1,
        defaults={
            "nombre": "Crema a despacho directo",
            "descripcion": "Rama comercial de crema obtenida en descremacion.",
        },
    )
    Etapa.objects.get_or_create(
        proceso=proceso,
        codigo="descremacion-crema",
        defaults={
            "nombre": "Descremacion",
            "tipo": "descremacion",
            "orden": 1,
            "requiere_calidad": True,
        },
    )
    for producto in Producto.objects.filter(
        activo=True,
        categoria="crema",
        formato="granel",
    ).select_related("mandante"):
        for sucursal in Sucursal.objects.filter(
            empresa_id=producto.mandante.empresa_id
        ):
            Ruta.objects.update_or_create(
                sucursal_id=sucursal.pk,
                producto_id=producto.pk,
                proceso=proceso,
                defaults={
                    "prioridad": 1,
                    "destino": "Despacho directo despues de liberacion",
                    "destino_final": "despacho_directo",
                    "activa": True,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0034_normalizar_codigos_silos_recepcion_confirmados"),
        ("procesos", "0017_corridadescremacion_destino_crema_and_more"),
    ]

    operations = [
        migrations.RunPython(crear_rutas_crema_despacho, migrations.RunPython.noop),
    ]
