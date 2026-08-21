"""
Traslada el módulo y la crioscopía de cada recepción a su hijo.

NO colapsa filas hermanas. Sumar los litros de dos recepciones del mismo
camión exigiría decidir qué silo, qué estado y qué veredicto quedan, y
produciría un registro que nadie hizo. Las filas viejas quedan como están; la
forma nueva —un camión, un registro— rige desde la captura siguiente.

A una recepción sin módulo ni crioscopía se le crea igual un módulo vacío:
que la relación sea siempre no vacía evita que cada consumidor tenga que
distinguir el caso.
"""

from django.db import migrations


def _numero_de_modulo(texto):
    """`Módulo 2`, `M2`, `2` → 2. Cualquier otra cosa → 1."""
    digitos = "".join(caracter for caracter in (texto or "") if caracter.isdigit())

    if not digitos:
        return 1

    numero = int(digitos)

    return numero if 1 <= numero <= 4 else 1


def poblar(apps, schema_editor):
    Recepcion = apps.get_model("recepcion", "Recepcion")
    ModuloRecepcion = apps.get_model("recepcion", "ModuloRecepcion")

    for recepcion in Recepcion.objects.all().iterator():
        controles = recepcion.controles or {}
        crioscopia = controles.pop("crioscopia", None)

        ModuloRecepcion.objects.create(
            recepcion=recepcion,
            numero=_numero_de_modulo(recepcion.modulo),
            crioscopia=crioscopia if crioscopia not in (None, "") else None,
            carga_recoleccion_id=recepcion.carga_recoleccion_id,
        )

        # La clave sale de `controles` porque deja de estar declarada: dejarla
        # haría fallar el `clean()` de la fila la próxima vez que se guarde.
        recepcion.controles = controles
        recepcion.save(update_fields=["controles"])


def revertir(apps, schema_editor):
    ModuloRecepcion = apps.get_model("recepcion", "ModuloRecepcion")
    ModuloRecepcion.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [("recepcion", "0011_modulorecepcion")]

    operations = [migrations.RunPython(poblar, revertir)]
