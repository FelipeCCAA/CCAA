from django.db import migrations


ETAPAS = [
    (1, "recepcion", "Recepción y almacenamiento", "recepcion", True, True),
    (2, "estandarizacion", "Estandarización", "estandarizacion", True, False),
    (3, "descremacion", "Descremación y separación", "descremacion", True, False),
    (4, "evaporacion", "Evaporación", "evaporacion", False, True),
    (5, "condensacion", "Condensación y precondensado", "condensacion", True, True),
    (6, "secado", "Secado", "secado", True, True),
    (7, "envasado", "Envasado", "envasado", True, True),
]


def sembrar(apps, schema_editor):
    Proceso = apps.get_model("procesos", "Proceso")
    Etapa = apps.get_model("procesos", "EtapaProceso")
    proceso, _ = Proceso.objects.update_or_create(
        codigo="flujo-lacteo",
        version=1,
        defaults={
            "nombre": "Transformación industrial de leche",
            "descripcion": "Ruta configurable desde recepción hasta producto envasado.",
            "activo": True,
        },
    )
    for orden, codigo, nombre, tipo, calidad, inocuidad in ETAPAS:
        Etapa.objects.update_or_create(
            proceso=proceso,
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "tipo": tipo,
                "orden": orden,
                "requiere_calidad": calidad,
                "requiere_inocuidad": inocuidad,
                "activa": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("procesos", "0001_initial")]
    operations = [migrations.RunPython(sembrar, migrations.RunPython.noop)]
