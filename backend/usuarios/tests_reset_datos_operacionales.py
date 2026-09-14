from io import StringIO

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase

from inventario.models import Notificacion

from .management.commands.reset_datos_operacionales import validar_destino


class SeguridadResetOperacionalTests(TestCase):
    # PostgreSQL permite revertir TRUNCATE: el envoltorio transaccional de
    # TestCase restaura tanto datos sembrados como secuencias al terminar.

    def test_aborta_si_el_destino_parece_productivo(self):
        with self.assertRaisesMessage(CommandError, "parece productiva"):
            validar_destino({
                "entorno": "qa",
                "motor": "django.db.backends.postgresql",
                "host": "postgres-production.internal",
                "puerto": "5432",
                "base": "ccaa",
            })

    def test_exige_confirmacion_exacta_antes_de_borrar(self):
        usuario = User.objects.create_user("conservar")
        Notificacion.objects.bulk_create([Notificacion(
            destinatario=usuario,
            tipo="prueba",
            titulo="Se debe borrar",
            mensaje="Dato operacional",
        )])

        with self.assertRaisesMessage(CommandError, "--confirmar-base"):
            call_command(
                "reset_datos_operacionales",
                aplicar=True,
                confirmar_base="base-equivocada",
                stdout=StringIO(),
            )

        self.assertTrue(Notificacion.objects.exists())

    def test_borra_operacion_y_conserva_usuarios_y_maestros(self):
        from maestros.models import Equipo, Producto

        usuario = User.objects.create_user("usuario-maestro")
        productos_antes = Producto.objects.count()
        equipos_antes = Equipo.objects.count()
        Notificacion.objects.bulk_create([Notificacion(
            destinatario=usuario,
            tipo="prueba",
            titulo="Se debe borrar",
            mensaje="Dato operacional",
        )])
        connection.check_constraints()

        from django.conf import settings

        nombre_base = str(settings.DATABASES["default"]["NAME"])
        call_command(
            "reset_datos_operacionales",
            aplicar=True,
            confirmar_base=nombre_base,
            stdout=StringIO(),
        )

        self.assertFalse(Notificacion.objects.exists())
        self.assertTrue(User.objects.filter(pk=usuario.pk).exists())
        self.assertEqual(Producto.objects.count(), productos_antes)
        self.assertEqual(Equipo.objects.count(), equipos_antes)
