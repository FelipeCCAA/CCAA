"""
Pruebas de que la planta única no se nota.

La organización de CCAA no tiene sucursales: hay una sola planta. El modelo
conserva la dimensión —quitarla costaría migrar quince modelos con datos
encima, y volvería a costar lo mismo el día que haya una segunda— pero nadie
debería tener que verla.

Lo que se fija aquí son las dos mitades de esa promesa:

1. Con **una** planta, ningún perfil necesita indicarla.
2. Con **dos**, el sistema deja de adivinar y la pide.

La segunda importa tanto como la primera: resolver lo que solo tiene una
respuesta es servicial; elegir entre dos es escribir en la planta equivocada
sin que nadie lo pida.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .models import Empresa, PerfilUsuario, Sucursal
from .tenancy import sucursal_para_escritura


class BaseSinSucursales(TestCase):

    def setUp(self):
        # Las migraciones siembran el tenant de pruebas, así que la base de
        # test arranca con una sucursal que no es de este escenario. Se
        # desactiva en vez de borrarse: otras filas sembradas la referencian
        # con `PROTECT`, y para la resolución automática lo que cuenta es que
        # esté activa.
        Sucursal.objects.update(activa=False)

        self.empresa = Empresa.objects.create(
            rut="76.111.111-1", nombre="Campos Australes"
        )
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA", nombre="Planta"
        )

    def _usuario(self, alcance, *, sucursal=None, superusuario=False):
        crear = User.objects.create_superuser if superusuario else User.objects.create_user
        usuario = crear(username=f"u-{alcance}-{superusuario}", password="x")

        if not superusuario:
            PerfilUsuario.objects.create(
                usuario=usuario,
                area=PerfilUsuario.Area.ADMINISTRACION,
                # El alcance de empresa esta reservado a Administracion
                # general: es quien responde por toda la empresa.
                nivel=PerfilUsuario.Nivel.ADMIN,
                empresa=self.empresa,
                sucursal=sucursal,
                alcance=alcance,
            )

        return usuario


class UnaSolaPlantaTests(BaseSinSucursales):

    def test_administracion_no_tiene_que_indicarla(self):
        """
        Es el caso que motivó el cambio. Un perfil de alcance empresa recibía
        «Debes indicar una sucursal permitida» sobre un concepto que en esta
        organización no existe, y no podía crear nada.
        """
        administrador = self._usuario(PerfilUsuario.Alcance.EMPRESA)

        self.assertEqual(sucursal_para_escritura(administrador, {}), self.planta)

    def test_un_perfil_de_planta_tampoco(self):
        """Ya funcionaba: se toma la suya, sin mirar cuántas hay."""
        operario = self._usuario(
            PerfilUsuario.Alcance.SUCURSAL, sucursal=self.planta
        )

        self.assertEqual(sucursal_para_escritura(operario, {}), self.planta)

    def test_el_superusuario_tampoco(self):
        self.assertEqual(
            sucursal_para_escritura(self._usuario("", superusuario=True), {}),
            self.planta,
        )

    def test_una_planta_inactiva_no_cuenta(self):
        """
        Desactivarla es sacarla de circulación. Si la resolución la eligiera,
        se registraría producción contra una planta que ya no opera.
        """
        self.planta.activa = False
        self.planta.save(update_fields=["activa"])

        with self.assertRaises(ValidationError):
            sucursal_para_escritura(self._usuario(PerfilUsuario.Alcance.EMPRESA), {})


class DosPlantasTests(BaseSinSucursales):
    """
    El día que haya una segunda, la ambigüedad vuelve y hay que decidir. Es la
    diferencia entre resolver lo que solo tiene una respuesta y adivinar entre
    dos.
    """

    def setUp(self):
        super().setUp()
        self.segunda = Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA2", nombre="Segunda planta"
        )

    def test_con_dos_hay_que_indicarla(self):
        with self.assertRaises(ValidationError) as fallo:
            sucursal_para_escritura(self._usuario(PerfilUsuario.Alcance.EMPRESA), {})

        self.assertIn("más de una planta", str(fallo.exception))

    def test_indicada_explicitamente_se_acepta(self):
        administrador = self._usuario(PerfilUsuario.Alcance.EMPRESA)

        elegida = sucursal_para_escritura(
            administrador, {"sucursal": self.segunda}
        )

        self.assertEqual(elegida, self.segunda)

    def test_el_perfil_de_planta_sigue_sin_elegir(self):
        """Su alcance ya la fija: no hay ambigüedad que resolver."""
        operario = self._usuario(
            PerfilUsuario.Alcance.SUCURSAL, sucursal=self.planta
        )

        self.assertEqual(sucursal_para_escritura(operario, {}), self.planta)


class AislamientoEntreEmpresasTests(BaseSinSucursales):

    def test_no_se_resuelve_con_la_planta_de_otra_empresa(self):
        """
        La resolución automática mira **solo** las de su empresa. Si mirara
        todas, un administrador de una empresa sin plantas terminaría
        escribiendo en la de otra — que es exactamente lo que el aislamiento
        existe para impedir.
        """
        otra = Empresa.objects.create(rut="77.222.222-2", nombre="Otra")
        usuario = User.objects.create_user(username="ajeno", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
            empresa=otra,
            # Explícito: el campo tiene por omisión el tenant de pruebas, así
            # que omitirlo no da `None` sino la sucursal sembrada — y el
            # alcance de empresa exige que no lleve ninguna.
            sucursal=None,
            alcance=PerfilUsuario.Alcance.EMPRESA,
        )

        with self.assertRaises(ValidationError):
            sucursal_para_escritura(usuario, {})

    def test_no_se_acepta_la_planta_de_otra_empresa_aunque_se_indique(self):
        from rest_framework.exceptions import PermissionDenied

        otra = Empresa.objects.create(rut="77.333.333-3", nombre="Tercera")
        ajena = Sucursal.objects.create(empresa=otra, codigo="X", nombre="Ajena")

        with self.assertRaises(PermissionDenied):
            sucursal_para_escritura(
                self._usuario(PerfilUsuario.Alcance.EMPRESA), {"sucursal": ajena}
            )
