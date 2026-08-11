"""
Crea la tabla que respalda la caché.

Va como migración y no como un `manage.py createcachetable` a mano porque de
esta tabla depende que los límites de peticiones funcionen: si falta, el
throttle de login y el de recuperación de contraseña fallan al escribir y la
protección desaparece. Un paso manual que hay que recordar en cada despliegue
es un paso que algún día no se da.

También la crea en la base de pruebas, que es lo que permite comprobar los
límites de verdad en vez de con un doble.
"""

from django.core.management import call_command
from django.db import migrations


def crear(apps, schema_editor):
    # `createcachetable` genera el DDL correcto para el motor que haya y es
    # idempotente: si la tabla ya existe, no hace nada.
    call_command(
        "createcachetable",
        "cache_ccaa",
        database=schema_editor.connection.alias,
        verbosity=0,
    )


def borrar(apps, schema_editor):
    schema_editor.execute("DROP TABLE IF EXISTS cache_ccaa")


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]

    operations = [
        migrations.RunPython(crear, borrar),
    ]
