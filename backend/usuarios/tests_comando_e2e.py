"""
Pruebas del comando que crea la cuenta de la auditoría de accesibilidad.

Lo que se cubre aquí no es el comando entero: es la **guarda de entorno**. El
comando crea una cuenta de administración con una contraseña escrita en el
repositorio, así que lo único que no puede fallar nunca es la comprobación que
impide correrlo en staging o producción.

Esa guarda no se puede probar a mano de forma fiable: en un staging real mal
configurado, el endurecimiento de `config.settings` revienta antes y da la
impresión de que la guarda actuó cuando en realidad nunca llegó a evaluarse.
Aquí se fuerza el entorno con la configuración ya cargada, que es el único modo
de comprobar que quien bloquea es el comando.
"""

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from usuarios.models import Empresa, PerfilUsuario, Rol, rol_de

USUARIO = "e2e_auditoria"


class GuardaDeEntorno(TestCase):
    """En un entorno endurecido el comando no crea nada."""

    def test_produccion_lo_bloquea(self):
        with override_settings(DJANGO_ENV="production"):
            with self.assertRaises(CommandError):
                call_command("crear_usuario_e2e")

        self.assertFalse(User.objects.filter(username=USUARIO).exists())

    def test_staging_lo_bloquea(self):
        with override_settings(DJANGO_ENV="staging"):
            with self.assertRaises(CommandError):
                call_command("crear_usuario_e2e")

        self.assertFalse(User.objects.filter(username=USUARIO).exists())


class CuentaCreada(TestCase):
    """La cuenta sale con el perfil que la auditoría necesita."""

    def setUp(self):
        """
        Se reutiliza la empresa que siembra `usuarios.0008`, no se crea otra.

        Crear una segunda dejaría dos empresas activas, y entonces el comando
        haría lo correcto —negarse a elegir por su cuenta— y la prueba fallaría
        por el montaje, no por el comportamiento que quiere comprobar.
        """
        self.empresa = Empresa.objects.filter(activa=True).first()

        if self.empresa is None:
            self.empresa = Empresa.objects.create(
                rut="76.000.000-0", nombre="Campos Australes (pruebas)"
            )

        Empresa.objects.exclude(pk=self.empresa.pk).update(activa=False)

    def test_crea_un_administrador_de_alcance_empresa(self):
        call_command("crear_usuario_e2e", verbosity=0)

        usuario = User.objects.get(username=USUARIO)
        perfil = usuario.perfil

        self.assertEqual(perfil.area, PerfilUsuario.Area.ADMINISTRACION)
        self.assertEqual(perfil.nivel, PerfilUsuario.Nivel.ADMIN)
        self.assertEqual(perfil.alcance, PerfilUsuario.Alcance.EMPRESA)

        # Alcance empresa y sucursal son excluyentes (CHECK del modelo). Si esto
        # se rompiera, el perfil dejaría de guardarse y la auditoría no entraría.
        self.assertIsNone(perfil.sucursal)

    def test_el_rol_efectivo_es_admin(self):
        """
        Es lo que `auth.setup.ts` exige antes de auditar.

        Sin rol admin, `/administracion` redirige al panel y esa pantalla se
        auditaría sin que nadie note que se midió otra cosa.
        """
        call_command("crear_usuario_e2e", verbosity=0)

        self.assertEqual(rol_de(User.objects.get(username=USUARIO)), Rol.ADMIN)

    def test_no_es_superusuario(self):
        """
        Un superusuario tendría alcance global (`scope_de`) y vería datos que
        ningún administrador real ve: la auditoría mediría pantallas que en
        planta nadie tiene delante.
        """
        self.assertFalse(User.objects.filter(username=USUARIO, is_superuser=True).exists())

        call_command("crear_usuario_e2e", verbosity=0)

        self.assertFalse(User.objects.get(username=USUARIO).is_superuser)

    def test_repetirlo_repone_la_contrasena_sin_duplicar(self):
        """
        Idempotente a propósito: el caso real es una cuenta que quedó de antes
        con otra contraseña, y el comando tiene que dejarla utilizable.
        """
        call_command("crear_usuario_e2e", clave="primera", verbosity=0)
        call_command("crear_usuario_e2e", clave="segunda", verbosity=0)

        self.assertEqual(User.objects.filter(username=USUARIO).count(), 1)
        self.assertTrue(User.objects.get(username=USUARIO).check_password("segunda"))


class SinEmpresa(TestCase):
    """Sin empresa activa el comando se niega, en vez de dejar un perfil inválido."""

    def test_avisa_en_vez_de_crear_un_perfil_a_medias(self):
        Empresa.objects.update(activa=False)

        with self.assertRaises(CommandError):
            call_command("crear_usuario_e2e", verbosity=0)

        self.assertFalse(User.objects.filter(username=USUARIO).exists())
