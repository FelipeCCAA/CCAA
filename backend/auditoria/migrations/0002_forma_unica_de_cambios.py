"""
Unifica la forma de `cambios` en los registros de alta.

Las altas se guardaban como `{campo: valor}` y las modificaciones como
`{campo: [antes, despues]}`. Dos formas en el mismo campo obligan a cada
consumidor a distinguirlas, y el que no lo haga revienta — la pantalla de
auditoría lo hizo, intentando desestructurar un número como par.
"""

from django.db import migrations


def unificar(apps, schema_editor):
    Registro = apps.get_model("auditoria", "RegistroAuditoria")

    for registro in Registro.objects.filter(accion="creacion").iterator():
        cambios = registro.cambios or {}

        # Ya convertido: no volver a envolver.
        if all(isinstance(v, list) and len(v) == 2 for v in cambios.values()):
            continue

        registro.cambios = {
            campo: [None, valor] for campo, valor in cambios.items() if campo != "id"
        }
        registro.save(update_fields=["cambios"])


def revertir(apps, schema_editor):
    """Vuelve a la forma plana, por si hay que retroceder la migración."""
    Registro = apps.get_model("auditoria", "RegistroAuditoria")

    for registro in Registro.objects.filter(accion="creacion").iterator():
        cambios = registro.cambios or {}

        if not all(isinstance(v, list) and len(v) == 2 for v in cambios.values()):
            continue

        registro.cambios = {campo: par[1] for campo, par in cambios.items()}
        registro.save(update_fields=["cambios"])


class Migration(migrations.Migration):

    dependencies = [("auditoria", "0001_initial")]

    operations = [migrations.RunPython(unificar, revertir)]
