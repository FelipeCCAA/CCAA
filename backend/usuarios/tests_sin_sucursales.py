"""
Pruebas de que la partición histórica no forma parte del modelo funcional.

La aplicación trabaja por empresa. Los registros internos que aún conservan
las tablas se resuelven en el servidor y nunca se seleccionan desde la API.
"""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from maestros.models import Mandante

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

    def test_con_dos_se_usa_la_configuracion_canonica(self):
        elegida = sucursal_para_escritura(
            self._usuario(PerfilUsuario.Alcance.EMPRESA), {}
        )

        self.assertEqual(elegida, self.planta)

    def test_una_seleccion_del_cliente_se_ignora(self):
        administrador = self._usuario(PerfilUsuario.Alcance.EMPRESA)

        elegida = sucursal_para_escritura(
            administrador, {"sucursal": self.segunda}
        )

        self.assertEqual(elegida, self.planta)

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

    def test_una_seleccion_ajena_del_cliente_se_ignora(self):
        otra = Empresa.objects.create(rut="77.333.333-3", nombre="Tercera")
        ajena = Sucursal.objects.create(empresa=otra, codigo="X", nombre="Ajena")

        elegida = sucursal_para_escritura(
            self._usuario(PerfilUsuario.Alcance.EMPRESA), {"sucursal": ajena}
        )
        self.assertEqual(elegida, self.planta)


class AltaDePersonalTests(BaseSinSucursales):
    """
    El formulario de personal no pide empresa, sucursal ni alcance: la pantalla
    no tiene esos campos. Sin deducirlos, el alta fallaba con «Debes indicar
    una sucursal» sobre algo que el operador no ve.
    """

    URL = "/api/usuarios/trabajadores/"

    def _crear(self, actor, **datos):
        self.client.force_authenticate(actor)

        return self.client.post(
            self.URL,
            {
                "username": datos.pop("username"),
                "password": "una-clave-larga-y-rara-42",
                **datos,
            },
            format="json",
        )

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.administrador = self._usuario(PerfilUsuario.Alcance.EMPRESA)

    def test_administracion_nace_con_alcance_de_empresa(self):
        """
        Lo que pidió Administración: es quien responde por toda la empresa, y
        atarla a una planta le negaría lo que su propio nivel dice que abarca.
        """
        respuesta = self._crear(
            self.administrador,
            username="nueva.jefa",
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        perfil = PerfilUsuario.objects.get(usuario__username="nueva.jefa")
        self.assertEqual(perfil.alcance, PerfilUsuario.Alcance.EMPRESA)
        self.assertIsNone(perfil.sucursal_id)
        self.assertEqual(perfil.empresa_id, self.empresa.pk)

    def test_el_resto_nace_con_alcance_de_empresa(self):
        respuesta = self._crear(
            self.administrador,
            username="operario",
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        perfil = PerfilUsuario.objects.get(usuario__username="operario")
        self.assertEqual(perfil.alcance, PerfilUsuario.Alcance.EMPRESA)
        self.assertIsNone(perfil.sucursal_id)

    def test_un_segundo_registro_interno_no_cambia_el_alta(self):
        Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA2", nombre="Segunda"
        )

        respuesta = self._crear(
            self.administrador,
            username="operario2",
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        perfil = PerfilUsuario.objects.get(usuario__username="operario2")
        self.assertEqual(perfil.alcance, PerfilUsuario.Alcance.EMPRESA)
        self.assertIsNone(perfil.sucursal_id)

    def test_con_dos_plantas_administracion_sigue_sin_elegir(self):
        """Su alcance no es una planta: la segunda no le añade ambigüedad."""
        Sucursal.objects.create(
            empresa=self.empresa, codigo="PLANTA3", nombre="Tercera"
        )

        respuesta = self._crear(
            self.administrador,
            username="otra.jefa",
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)


# Sin esto la prueba no comprueba nada: bajo `test` el `default` del campo
# entrega siempre el tenant sembrado, así que `empresa` nunca llega vacía y la
# resolución automática no se ejercita jamás. El defecto solo existe donde el
# default no inventa nada, que es donde corre la aplicación.
@override_settings(DJANGO_ENV="development")
class UnaSolaEmpresaTests(TestCase):
    """
    El otro lado de la planta única: el **superusuario** no está acotado a
    ninguna empresa, así que es el único a quien se le podía pedir que la
    eligiera. Ninguna pantalla la muestra —CCAA es una empresa— y el alta de
    mandantes moría con «Un superusuario debe indicar la empresa» sobre un
    desplegable que no existe.
    """

    URL = "/api/maestros/mandantes/"

    def setUp(self):
        Empresa.objects.update(activa=False)
        self.empresa = Empresa.objects.create(
            rut="76.555.555-5", nombre="Campos Australes"
        )
        self.jefe = User.objects.create_superuser(username="raiz", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.jefe)

    def _crear(self, nombre, codigo="nestle"):
        return self.client.post(
            self.URL,
            {"nombre": nombre, "codigo_cliente": codigo, "activo": True},
            format="json",
        )

    def test_el_superusuario_no_tiene_que_indicarla(self):
        respuesta = self._crear("Nestlé")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(
            Mandante.objects.get(nombre="Nestlé").empresa_id, self.empresa.pk
        )

    def test_con_dos_empresas_activas_hay_que_indicarla(self):
        """
        Elegir por él sería registrar el mandante en la empresa equivocada —y
        sus productos heredarían ese error en el SKU.
        """
        Empresa.objects.create(rut="77.666.666-6", nombre="Otra")

        respuesta = self._crear("Colun", "colun")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("empresa", respuesta.data)
        self.assertFalse(Mandante.objects.filter(nombre="Colun").exists())

    def test_una_empresa_inactiva_no_cuenta(self):
        self.empresa.activa = False
        self.empresa.save(update_fields=["activa"])

        self.assertEqual(self._crear("Soprole", "soprole").status_code, 400)


class DefaultDeTenantTests(TestCase):
    """
    **Sin `override_settings` a propósito.** Esta corre en el entorno de
    pruebas, que es el único donde el `default` de tenant entrega un valor.

    DRF copia ese mismo callable al campo del serializer, así que lo que
    devuelve acaba en `validated_data`. Devolviendo `pk` en vez del objeto,
    guardar reventaba con «Cannot assign "1": debe ser una instancia de
    Empresa» — un 500, no un error de validación, y solo en pruebas y CI, que
    es donde nadie lo estaba mirando.
    """

    def test_el_default_llega_al_serializer_como_objeto(self):
        jefe = User.objects.create_superuser(username="raiz2", password="x")
        cliente = APIClient()
        cliente.force_authenticate(jefe)

        respuesta = cliente.post(
            "/api/maestros/mandantes/",
            {"nombre": "Nestlé", "codigo_cliente": "nestle", "activo": True},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertIsNotNone(Mandante.objects.get(nombre="Nestlé").empresa_id)


class CodigoDeClienteOcupadoTests(TestCase):
    """
    «Un código de cliente, un mandante» lo garantiza una restricción de base de
    datos — y una restricción avisa con un `IntegrityError`, o sea un **500 y un
    "no se pudo guardar"** en pantalla, sobre una regla que tiene explicación
    corta y salida clara.
    """

    def setUp(self):
        self.jefe = User.objects.create_superuser(username="raiz3", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.jefe)
        self.primero = self._crear("Nestlé", "nestle")

    def _crear(self, nombre, codigo):
        return self.client.post(
            "/api/maestros/mandantes/",
            {"nombre": nombre, "codigo_cliente": codigo, "activo": True},
            format="json",
        )

    def test_repetir_el_codigo_se_explica_en_vez_de_reventar(self):
        self.assertEqual(self.primero.status_code, 201, self.primero.data)

        respuesta = self._crear("Nestle S.A.", "nestle")

        self.assertEqual(respuesta.status_code, 400, respuesta.status_code)
        # El mensaje nombra al que ya lo tiene: sin eso hay que ir a buscarlo.
        self.assertIn("Nestlé", str(respuesta.data["codigo_cliente"]))

    def test_sin_codigo_se_pueden_repetir(self):
        """Uno sin código es uno que todavía no genera SKU, y puede haber varios."""
        self.assertEqual(self._crear("Cliente nuevo", "").status_code, 201)
        self.assertEqual(self._crear("Otro sin código", "").status_code, 201)


@override_settings(DJANGO_ENV="development")
class RegistrarRecepcionTests(TestCase):
    """
    El ingreso del camión, que es donde se vio el fallo.

    `RecepcionViewSet.perform_create` resolvía el tenant por su cuenta —una de
    tres copias a mano de la misma regla— y solo contemplaba el perfil de
    planta: al superusuario le exigía una sucursal que la pantalla no muestra.
    Ahora pasa por `sucursal_para_escritura`, igual que el resto.

    Con `DJANGO_ENV=development` a propósito: bajo `test` el `default` del campo
    entrega la sucursal sembrada, `validated_data` nunca viene sin ella y el
    defecto no se reproduce — la prueba pasaría con el código roto.
    """

    def setUp(self):
        from maestros.models import Silo, Vehiculo

        Sucursal.objects.update(activa=False)
        self.empresa = Empresa.objects.create(rut="76.777.777-7", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="P", nombre="Planta"
        )
        self.silo = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 1", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.camion = Vehiculo.objects.create(
            sucursal=self.planta, placa="BZFF-89", transportista="Transp. Sur"
        )

        self.client = APIClient()
        self.client.force_authenticate(
            User.objects.create_superuser(username="raiz4", password="x")
        )

    def _registrar(self):
        return self.client.post(
            "/api/recepcion/recepciones/",
            {
                "fecha": "2026-08-12",
                "tipo_leche": "Entera",
                "litros": "50000.00",
                "vehiculo": self.camion.id,
                "procedencia": "Nestlé",
                "modulo": "M4",
            },
            format="json",
        )

    def test_el_superusuario_no_tiene_que_indicar_la_planta(self):
        respuesta = self._registrar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.json()["estado"], "registrada")

    def test_un_segundo_registro_interno_no_se_pide(self):
        Sucursal.objects.create(empresa=self.empresa, codigo="P2", nombre="Segunda")

        respuesta = self._registrar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)


@override_settings(DJANGO_ENV="development")
class RegistrarLlegadaTests(TestCase):
    """
    `registrar-llegada/` es una acción a medida, no un `perform_create`, y nació
    con la misma copia a mano del tenant que se retiró de las cuatro escrituras:
    al superusuario le exigía una planta que el formulario no envía.
    """

    def setUp(self):
        from maestros.models import Vehiculo

        Sucursal.objects.update(activa=False)
        self.empresa = Empresa.objects.create(rut="76.444.444-4", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="U", nombre="Planta"
        )
        self.camion = Vehiculo.objects.create(
            sucursal=self.planta, placa="XXYY-11", transportista="Transp."
        )
        self.client = APIClient()
        self.client.force_authenticate(
            User.objects.create_superuser(username="raiz5", password="x")
        )

    def _registrar(self, **extra):
        return self.client.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-08-12",
                "guia": "G-9",
                "vehiculo": self.camion.id,
                "tipo_leche": "Entera",
                "modulos": [
                    {"modulo": "M1", "litros": "20000.00"},
                    {"modulo": "M2", "litros": "20000.00"},
                ],
                **extra,
            },
            format="json",
        )

    def test_el_superusuario_no_tiene_que_indicar_la_planta(self):
        respuesta = self._registrar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        creadas = respuesta.json()
        self.assertEqual(len(creadas), 2)
        self.assertEqual(creadas[0]["llegada_id"], creadas[1]["llegada_id"])

    def test_un_segundo_registro_interno_no_se_pide(self):
        Sucursal.objects.create(empresa=self.empresa, codigo="U2", nombre="Segunda")

        respuesta = self._registrar()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_una_seleccion_inexistente_del_cliente_se_ignora(self):
        respuesta = self._registrar(sucursal=999999)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
