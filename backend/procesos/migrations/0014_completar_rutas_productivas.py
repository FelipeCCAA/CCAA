from django.db import migrations


CLASIFICACION_RUTAS = {
    "precondensado": "ruta-precondensado",
    "mantequilla": "ruta-mantequilla",
    "leche_polvo": "ruta-polvo",
    "lp_instantanea": "ruta-polvo",
    "lp_con_lecitina": "ruta-polvo",
}


def completar_rutas(apps, schema_editor):
    Proceso = apps.get_model("procesos", "Proceso")
    Ruta = apps.get_model("procesos", "RutaProducto")
    Producto = apps.get_model("maestros", "Producto")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    procesos = {
        proceso.codigo: proceso
        for proceso in Proceso.objects.filter(
            codigo__in=set(CLASIFICACION_RUTAS.values()), activo=True
        )
    }
    destinos = {
        "ruta-polvo": "Inventario después de envasado y liberación",
        "ruta-mantequilla": "Inventario después de envasado y liberación",
        "ruta-precondensado": "Despacho directo después de liberación",
    }

    esperados = []
    productos = Producto.objects.filter(activo=True).select_related("mandante")
    for producto in productos.iterator():
        codigo_ruta = CLASIFICACION_RUTAS.get(producto.categoria)
        if codigo_ruta is None and producto.familia == "polvo":
            codigo_ruta = "ruta-polvo"
        proceso = procesos.get(codigo_ruta)
        if proceso is None:
            continue
        plantas = Sucursal.objects.filter(
            empresa_id=producto.mandante.empresa_id, activa=True
        )
        for planta in plantas.iterator():
            Ruta.objects.update_or_create(
                sucursal=planta,
                producto=producto,
                proceso=proceso,
                defaults={
                    "prioridad": 1,
                    "destino": destinos[codigo_ruta],
                    "observaciones": (
                        "Ruta productiva completada antes de exigir "
                        "trazabilidad obligatoria."
                    ),
                    "activa": True,
                },
            )
            esperados.append((producto.pk, planta.pk))

    cobertura_completa = all(
        Ruta.objects.filter(
            producto_id=producto_id,
            sucursal_id=sucursal_id,
            activa=True,
            proceso__activo=True,
        ).exists()
        for producto_id, sucursal_id in esperados
    )
    if esperados and cobertura_completa:
        Proceso.objects.filter(codigo="flujo-lacteo").update(activo=False)


class Migration(migrations.Migration):
    dependencies = [
        ("procesos", "0013_autorizacion_reproceso"),
    ]

    operations = [
        migrations.RunPython(completar_rutas, migrations.RunPython.noop),
    ]
