from django.db import migrations


RUTAS = {
    "ruta-polvo": (
        "Leche en polvo",
        "Inventario después de envasado y liberación",
        [
            (1, "estandarizacion", "Estandarización", "estandarizacion", True),
            (2, "evaporacion", "Evaporación", "evaporacion", True),
            (3, "secado", "Secado", "secado", True),
            (4, "envasado", "Envasado", "envasado", True),
        ],
    ),
    "ruta-mantequilla": (
        "Mantequilla",
        "Inventario después de envasado y liberación",
        [
            (1, "mantequilla", "Elaboración de mantequilla", "mantequilla", True),
            (2, "envasado", "Envasado en cajas", "envasado", True),
        ],
    ),
    "ruta-precondensado": (
        "Precondensado",
        "Despacho directo después de liberación",
        [
            (1, "estandarizacion", "Estandarización", "estandarizacion", True),
            (2, "evaporacion", "Evaporación y precondensado", "evaporacion", True),
        ],
    ),
}


def sembrar_rutas(apps, schema_editor):
    Proceso = apps.get_model("procesos", "Proceso")
    Etapa = apps.get_model("procesos", "EtapaProceso")
    Ruta = apps.get_model("procesos", "RutaProducto")
    Producto = apps.get_model("maestros", "Producto")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    procesos = {}
    for codigo, (nombre, destino, etapas) in RUTAS.items():
        proceso, _ = Proceso.objects.update_or_create(
            codigo=codigo,
            version=1,
            defaults={
                "nombre": nombre,
                "descripcion": f"Ruta operacional específica. Destino: {destino}.",
                "activo": True,
            },
        )
        procesos[codigo] = (proceso, destino)
        for orden, codigo_etapa, nombre_etapa, tipo, calidad in etapas:
            Etapa.objects.update_or_create(
                proceso=proceso,
                codigo=codigo_etapa,
                defaults={
                    "nombre": nombre_etapa,
                    "tipo": tipo,
                    "orden": orden,
                    "requiere_calidad": calidad,
                    "requiere_inocuidad": tipo in {"evaporacion", "secado", "envasado"},
                    "activa": True,
                },
            )

    categorias_polvo = {"leche_polvo", "lp_instantanea", "lp_con_lecitina"}
    for producto in Producto.objects.select_related("mandante").all().iterator():
        if producto.categoria == "precondensado":
            clave = "ruta-precondensado"
        elif producto.categoria == "mantequilla":
            clave = "ruta-mantequilla"
        elif producto.familia == "polvo" or producto.categoria in categorias_polvo:
            clave = "ruta-polvo"
        else:
            continue
        proceso, destino = procesos[clave]
        plantas = Sucursal.objects.filter(empresa_id=producto.mandante.empresa_id)
        for planta in plantas.iterator():
            Ruta.objects.update_or_create(
                sucursal=planta,
                producto=producto,
                proceso=proceso,
                defaults={
                    "prioridad": 1,
                    "destino": destino,
                    "observaciones": "Ruta específica sembrada sin alterar el producto histórico.",
                    "activa": True,
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("procesos", "0010_entradaproceso_motivo_salidaproceso_clasificacion_and_more"),
    ]

    operations = [
        migrations.RunPython(sembrar_rutas, migrations.RunPython.noop),
    ]
