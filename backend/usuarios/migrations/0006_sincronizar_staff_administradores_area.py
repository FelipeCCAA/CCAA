from django.db import migrations


def sincronizar_staff(apps, schema_editor):
    User = apps.get_model("auth", "User")
    PerfilUsuario = apps.get_model("usuarios", "PerfilUsuario")
    ids_administradores = PerfilUsuario.objects.filter(nivel="admin").values_list(
        "usuario_id", flat=True
    )
    User.objects.filter(pk__in=ids_administradores).update(is_staff=True)


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0005_empresa_perfilusuario_empresa_sucursal_and_more"),
    ]

    operations = [migrations.RunPython(sincronizar_staff, migrations.RunPython.noop)]
