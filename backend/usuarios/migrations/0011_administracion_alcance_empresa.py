"""
Administración general pasa a alcance de empresa.

`0008` asignó **todos** los perfiles existentes a la sucursal inicial, porque
era lo único que podía hacer sin inventar criterios. El resultado es que
Administración quedó atada a una planta: veía y escribía como un operario de
esa planta, no como quien responde por la empresa.

Solo se mueven los perfiles que el propio modelo admite en ese alcance
—`area = administracion` **y** `nivel = admin`—, que es la misma condición que
`PerfilUsuario.clean()` exige. Mover a otro sería ampliarle el acceso a alguien
que nadie decidió ampliar.

Los dos campos se escriben en un solo `UPDATE`: la restricción
`perfil_scope_coherente` exige que el alcance de empresa no lleve sucursal, y en
dos pasos la fila intermedia la violaría.

La vuelta atrás los devuelve a la sucursal de su empresa **solo si hay una
sola**. Con varias no hay forma de saber cuál era la suya —el dato se perdió al
subir de alcance— y se prefiere fallar a repartirlos por sorteo.
"""

from django.db import migrations


def subir_administracion(apps, schema_editor):
    PerfilUsuario = apps.get_model("usuarios", "PerfilUsuario")

    PerfilUsuario.objects.filter(
        area="administracion", nivel="admin", alcance="sucursal"
    ).update(alcance="empresa", sucursal=None)


def bajar_administracion(apps, schema_editor):
    PerfilUsuario = apps.get_model("usuarios", "PerfilUsuario")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    for perfil in PerfilUsuario.objects.filter(alcance="empresa"):
        candidatas = list(
            Sucursal.objects.filter(
                empresa_id=perfil.empresa_id, activa=True
            ).order_by("pk")[:2]
        )

        if len(candidatas) != 1:
            raise RuntimeError(
                f"El perfil {perfil.pk} no se puede devolver a "
                "una sucursal: su empresa no tiene exactamente una activa, y "
                "cuál era la suya no se guardó en ninguna parte."
            )

        perfil.alcance = "sucursal"
        perfil.sucursal = candidatas[0]
        perfil.save(update_fields=["alcance", "sucursal"])


class Migration(migrations.Migration):

    dependencies = [("usuarios", "0010_intentoacceso")]

    operations = [
        migrations.RunPython(subir_administracion, bajar_administracion),
    ]
