"""
Pasa de los roles ADMIN/TRABAJADOR a los cinco del proceso.

La conversión de los datos va incluida: cambiar solo las opciones dejaría los
perfiles existentes con un valor que ya no es válido, y el fallo aparecería
mucho después, al editar un perfil cualquiera.
"""

from django.db import migrations, models


# TRABAJADOR no tiene equivalente directo: agrupaba a Recepción, Producción y
# Calidad, que ahora son roles distintos. Se convierte al de menor privilegio
# y se reasigna a mano desde el admin, porque adivinar aquí quién es de
# Calidad daría permiso de liberar producto a quien no le corresponde.
CONVERSION = {
    "ADMIN": "admin",
    "TRABAJADOR": "lectura",
}


def a_roles_del_proceso(apps, schema_editor):
    PerfilUsuario = apps.get_model("usuarios", "PerfilUsuario")

    for antiguo, nuevo in CONVERSION.items():
        PerfilUsuario.objects.filter(rol=antiguo).update(rol=nuevo)


def a_roles_antiguos(apps, schema_editor):
    PerfilUsuario = apps.get_model("usuarios", "PerfilUsuario")

    # La vuelta atrás no puede recuperar la distinción que no existía: todo
    # lo que no sea administrador vuelve a ser trabajador.
    PerfilUsuario.objects.filter(rol="admin").update(rol="ADMIN")
    PerfilUsuario.objects.exclude(rol="ADMIN").update(rol="TRABAJADOR")


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(a_roles_del_proceso, a_roles_antiguos),
        migrations.AlterModelOptions(
            name='perfilusuario',
            options={'verbose_name': 'Perfil de usuario', 'verbose_name_plural': 'Perfiles de usuario'},
        ),
        migrations.AlterField(
            model_name='perfilusuario',
            name='rol',
            field=models.CharField(choices=[('recepcion', 'Recepción'), ('produccion', 'Producción'), ('calidad', 'Calidad'), ('admin', 'Administrador'), ('lectura', 'Solo lectura')], default='lectura', max_length=20),
        ),
    ]
