from django.db import migrations


CODIGOS_RECEPCION = {
    "Silo": "Silo 1",
    "silo 2": "Silo 2",
    "Silo  3": "Silo 3",
    "Silo 4": "Silo 4",
    "Silo 5": "Silo 5",
    "Silo  6": "Silo 6",
    "Silo 7": "Silo 7",
    "Silo 8": "Silo 8",
}


def normalizar_sin_duplicar(apps, schema_editor):
    Silo = apps.get_model("maestros", "Silo")
    for anterior, nuevo in CODIGOS_RECEPCION.items():
        for silo in Silo.objects.filter(tipo="silo", codigo=anterior).iterator():
            colision = Silo.objects.filter(
                sucursal_id=silo.sucursal_id,
                codigo=nuevo,
            ).exclude(pk=silo.pk).exists()
            if not colision and silo.codigo != nuevo:
                Silo.objects.filter(pk=silo.pk).update(codigo=nuevo)


class Migration(migrations.Migration):
    dependencies = [("maestros", "0033_clasificar_productos_por_etapa_fisica")]

    operations = [
        migrations.RunPython(normalizar_sin_duplicar, migrations.RunPython.noop),
    ]
