"""
Pruebas del acceso: límites de intentos y registro.

El login no tenía ninguna protección: se podían probar miles de contraseñas
por minuto sin freno, sin bloqueo y sin dejar rastro. Lo que se fija aquí son
las tres decisiones que lo arreglan.

**Las pruebas limpian la caché en `setUp`**: `SimpleRateThrottle` cuenta ahí, y
sin limpiarla el contador de una prueba se filtra a la siguiente y el orden de
ejecución cambia el resultado.
"""

from unittest.mock import patch

from django.conf import settings as ajustes
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings

from .models import IntentoAcceso
from .throttling import LoginIPThrottle, LoginUsuarioThrottle


class BaseLogin(TestCase):
    """
    Los límites reales (60/h y 15/h) son los de planta y no se pueden agotar en
    una prueba sin hacerla lenta y frágil. Se bajan aquí a propósito: lo que se
    comprueba es **que el mecanismo muerde**, no el número, que es
    configurable por entorno.

    Se bajan parcheando `rate` en las clases y **no** con
    `override_settings(REST_FRAMEWORK=...)`: DRF copia
    `DEFAULT_THROTTLE_RATES` a un atributo de clase de `SimpleRateThrottle` al
    importarse, así que recargar la configuración no lo alcanza. Comprobado —
    con `override_settings` la tasa del ajuste cambia y la de la instancia no,
    y las pruebas pasaban en verde sin ejercer nada.

    La caché se limpia en `setUp` y `tearDown`: el contador vive ahí, y sin
    limpiarla el de una prueba se filtra a la siguiente y el orden de ejecución
    cambia el resultado.
    """

    def setUp(self):
        cache.clear()

        # `create=True` porque `SimpleRateThrottle` no declara `rate` como
        # atributo de clase: lo asigna en `__init__` solo si no lo encuentra,
        # que es justo el hueco por el que se cuela este ajuste.
        for clase, tasa in ((LoginIPThrottle, "5/hour"), (LoginUsuarioThrottle, "3/hour")):
            parche = patch.object(clase, "rate", tasa, create=True)
            parche.start()
            self.addCleanup(parche.stop)

        self.usuario = User.objects.create_user(
            username="operario", password="clave-correcta-123"
        )

    def tearDown(self):
        cache.clear()

    def _login(self, username="operario", password="mala", **extra):
        return self.client.post(
            "/api/usuarios/login/",
            {"username": username, "password": password},
            content_type="application/json",
            **extra,
        )


class LimiteDeIntentosTests(BaseLogin):

    def test_la_fuerza_bruta_contra_una_cuenta_se_corta(self):
        """
        Es el agujero que motivó todo esto: sin límite se podían probar miles
        de contraseñas por minuto contra la misma cuenta.
        """
        for _ in range(3):
            self.assertEqual(self._login().status_code, 401)

        self.assertEqual(self._login().status_code, 429)

    def test_el_limite_por_cuenta_sobrevive_al_cambio_de_direccion(self):
        """
        Un atacante con una botnet rota direcciones. Si el único límite fuera
        por IP, no lo tocaría; por eso el estricto es el de cuenta.
        """
        for n in range(3):
            self._login(REMOTE_ADDR=f"10.0.0.{n}")

        respuesta = self._login(REMOTE_ADDR="10.0.0.200")

        self.assertEqual(respuesta.status_code, 429)

    def test_agotar_una_cuenta_no_deja_fuera_a_las_demas(self):
        """
        La planta sale por una sola dirección: si bloquear una cuenta cerrara
        la puerta a las otras, un atacante dejaría al turno entero sin entrar
        con solo insistir contra un nombre. Eso es una denegación de servicio
        servida en bandeja.
        """
        for _ in range(3):
            self._login(username="victima")

        self.assertEqual(self._login(username="victima").status_code, 429)
        self.assertEqual(self._login(username="operario").status_code, 401)

    def test_el_nombre_se_normaliza(self):
        """
        `Operario`, `operario ` y `OPERARIO` son tres formas de atacar la
        misma cuenta. Sin normalizar, cada una tendría su propia cuota.
        """
        for nombre in ("operario", "Operario", "OPERARIO "):
            self._login(username=nombre)

        self.assertEqual(self._login(username="  operario").status_code, 429)

    def test_un_login_correcto_tambien_cuenta(self):
        """
        El contador no se reinicia al acertar: si lo hiciera, bastaría
        intercalar una credencial válida propia para renovar la cuota y seguir
        probando contra otra cuenta desde la misma dirección.
        """
        # Cinco nombres distintos: agotan el límite por dirección (5/hora) sin
        # tocar el de cuenta, que es de tres.
        for n in range(5):
            self._login(username=f"nadie{n}")

        respuesta = self._login(username="operario", password="clave-correcta-123")

        self.assertEqual(respuesta.status_code, 429)


@override_settings(
    PROXIES_DE_CONFIANZA=1,
    # **Hay que anular las dos.** `PROXIES_DE_CONFIANZA` la lee el registro de
    # intentos; DRF lee `NUM_PROXIES` del diccionario `REST_FRAMEWORK`, que se
    # arma al importar la configuración. Con solo la primera, el throttle sigue
    # con 0 —o sea con `REMOTE_ADDR`, que en las pruebas es siempre
    # `127.0.0.1`— y todo cae en el mismo cubo: la prueba pasa sin ejercer
    # nada. Ocurrió, y por eso está escrito.
    REST_FRAMEWORK={**ajustes.REST_FRAMEWORK, "NUM_PROXIES": 1},
)
class DetrasDeUnProxyTests(BaseLogin):
    """
    El caso del despliegue real: Nginx o Vercel delante.

    Sin declarar cuántos proxies hay, DRF usa la cabecera `X-Forwarded-For`
    **entera** como identidad. Quien ataca manda una distinta en cada petición,
    el proxy le añade la suya al final, la cadena resultante cambia siempre y
    cada intento estrena cubo: el límite por IP quedaba de adorno.
    """

    def test_no_se_esquiva_el_limite_falsificando_la_cabecera(self):
        """
        Cinco intentos con cinco cabeceras inventadas, todos desde el mismo
        proxy. El sexto tiene que cortarse: la identidad la pone el proxy, no
        quien llama.
        """
        for n in range(5):
            self._login(
                username=f"nadie{n}",
                HTTP_X_FORWARDED_FOR=f"9.9.9.{n}, 203.0.113.7",
            )

        respuesta = self._login(
            username="otro", HTTP_X_FORWARDED_FOR="9.9.9.99, 203.0.113.7"
        )

        self.assertEqual(respuesta.status_code, 429)

    def test_dos_clientes_distintos_no_comparten_cubo(self):
        """
        La otra mitad: el límite tiene que distinguir de verdad. Si tomara
        siempre la del proxy, la planta entera compartiría cuota y bastaría un
        atacante para dejar a todos fuera.
        """
        for n in range(5):
            self._login(username=f"nadie{n}", HTTP_X_FORWARDED_FOR="203.0.113.7")

        respuesta = self._login(
            username="operario", HTTP_X_FORWARDED_FOR="198.51.100.4"
        )

        self.assertEqual(respuesta.status_code, 401)


class RegistroDeIntentosTests(BaseLogin):

    def test_un_intento_fallido_queda_registrado(self):
        """
        Antes no quedaba rastro: un ataque era indistinguible de un turno
        normal, y después de un incidente no había forma de responder «desde
        dónde y contra qué cuenta».
        """
        self._login()

        intento = IntentoAcceso.objects.get()
        self.assertEqual(intento.usuario, "operario")
        self.assertFalse(intento.exito)
        self.assertEqual(intento.motivo, "credenciales")

    def test_un_intento_correcto_tambien(self):
        self._login(password="clave-correcta-123")

        self.assertTrue(IntentoAcceso.objects.get().exito)

    def test_se_registra_una_cuenta_que_no_existe(self):
        """
        La mitad de los intentos de un ataque van contra cuentas inventadas, y
        son los que más dicen. Con una clave foránea al usuario se perderían.
        """
        self._login(username="administrador")

        self.assertEqual(IntentoAcceso.objects.get().usuario, "administrador")

    def test_nunca_se_guarda_la_contrasena(self):
        """
        Ni la de un intento fallido: quien teclea su contraseña en el campo del
        usuario la dejaría escrita en claro en la base.
        """
        self._login(username="operario", password="secreto-que-no-debe-quedar")

        campos = " ".join(
            str(valor) for valor in IntentoAcceso.objects.values().first().values()
        )

        self.assertNotIn("secreto-que-no-debe-quedar", campos)

    @override_settings(PROXIES_DE_CONFIANZA=1)
    def test_detras_de_un_proxy_toma_la_que_puso_el_proxy(self):
        """
        Cada proxy añade **al final** la dirección que él mismo vio. Con un
        proxy de confianza delante, la última es la única que el cliente no
        pudo escribir.
        """
        self._login(HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7")

        self.assertEqual(IntentoAcceso.objects.get().ip, "203.0.113.7")

    @override_settings(PROXIES_DE_CONFIANZA=1)
    def test_no_se_cree_lo_que_el_cliente_escribe_delante(self):
        """
        La primera entrada la pone quien llama. Tomarla —que es lo que hacía
        antes— dejaba falsificar la dirección del registro con una cabecera.
        """
        self._login(HTTP_X_FORWARDED_FOR="8.8.8.8, 203.0.113.7")

        self.assertNotEqual(IntentoAcceso.objects.get().ip, "8.8.8.8")

    @override_settings(PROXIES_DE_CONFIANZA=0)
    def test_sin_proxy_declarado_la_cabecera_se_ignora(self):
        """
        Fallo seguro: sin proxy delante, `X-Forwarded-For` no la manda nadie de
        confianza y creerla sería regalar la identidad a quien llama.
        """
        self._login(HTTP_X_FORWARDED_FOR="8.8.8.8", REMOTE_ADDR="127.0.0.1")

        self.assertEqual(IntentoAcceso.objects.get().ip, "127.0.0.1")

    def test_el_registro_no_puede_tumbar_el_login(self):
        """
        Una auditoría que impide entrar es peor que no tenerla.
        """


        from django.db import DatabaseError

        with patch.object(
            IntentoAcceso.objects, "create", side_effect=DatabaseError("caída")
        ):
            respuesta = self._login(password="clave-correcta-123")

        self.assertEqual(respuesta.status_code, 200)


class SinEnumeracionTests(BaseLogin):

    def test_el_mensaje_no_distingue_una_cuenta_inexistente(self):
        """
        Distinguirlos convertiría el login en un comprobador de nombres de
        usuario: se sabría qué cuentas existen antes de atacarlas.
        """
        existente = self._login(username="operario")
        inventada = self._login(username="no-existe-esta-cuenta")

        self.assertEqual(existente.status_code, inventada.status_code)
        self.assertEqual(existente.json()["error"], inventada.json()["error"])
