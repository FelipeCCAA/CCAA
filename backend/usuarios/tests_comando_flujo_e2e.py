from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal


class CuentasFlujoE2E(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(
            rut="99.999.999-9", nombre="Compatibilidad histórica E2E"
        )
        Sucursal.objects.create(
            empresa=empresa, codigo="E2E", nombre="Planta E2E", activa=True
        )

    def test_crea_dos_personas_distintas_autorizadas_por_calidad(self):
        call_command("crear_usuarios_flujo_e2e", verbosity=0)

        analista = User.objects.get(username="e2e_calidad")
        firmante = User.objects.get(username="e2e_calidad_firma")

        self.assertNotEqual(analista.pk, firmante.pk)
        for usuario in (analista, firmante):
            self.assertEqual(usuario.perfil.rol, Rol.CALIDAD)
            self.assertEqual(usuario.perfil.area, PerfilUsuario.Area.CALIDAD)
            self.assertFalse(usuario.is_superuser)

    @override_settings(DJANGO_ENV="production")
    def test_no_crea_cuentas_en_un_entorno_endurecido(self):
        with self.assertRaises(CommandError):
            call_command("crear_usuarios_flujo_e2e", verbosity=0)

        self.assertFalse(User.objects.filter(username__startswith="e2e_").exists())
