"""
Pruebas del desbloqueo del login.

El límite existía sin forma de levantarlo: la única salida era abrir una shell
de Django dentro del contenedor y borrar una clave de caché a mano. Eso no se
le puede pedir al turno de noche cuando el jefe de planta no puede entrar.

Lo que se fija aquí es que el desbloqueo **sirva de verdad**: que después de
usarlo se pueda entrar, no solo que el comando diga que sí.
"""

from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase

from .models import IntentoAcceso
from .throttling import (
    LoginIPThrottle,
    LoginUsuarioThrottle,
    clave_de_ip,
    clave_de_usuario,
    estado_del_limite,
)


class BaseDesbloqueo(TestCase):

    def setUp(self):
        cache.clear()

        for clase, tasa in ((LoginIPThrottle, "5/hour"), (LoginUsuarioThrottle, "3/hour")):
            parche = patch.object(clase, "rate", tasa, create=True)
            parche.start()
            self.addCleanup(parche.stop)

        User.objects.create_user(username="operario", password="clave-correcta-123")

    def tearDown(self):
        cache.clear()

    def _login(self, username="operario", password="mala", **extra):
        return self.client.post(
            "/api/usuarios/login/",
            {"username": username, "password": password},
            content_type="application/json",
            **extra,
        )

    def _bloquear(self, username="operario"):
        """Agota el límite de esa cuenta y comprueba que quedó bloqueada."""
        for _ in range(3):
            self._login(username=username)

        self.assertEqual(self._login(username=username).status_code, 429)


class ComandoTests(BaseDesbloqueo):

    def test_desbloquear_una_cuenta_permite_volver_a_entrar(self):
        """
        Lo que importa no es que el comando conteste: es que después se pueda
        entrar. Comprobarlo mirando solo la caché dejaría pasar un desbloqueo
        que borra la clave equivocada.
        """
        self._bloquear()

        call_command("desbloquear_login", usuario="operario", stdout=StringIO())

        respuesta = self._login(password="clave-correcta-123")
        self.assertEqual(respuesta.status_code, 200)

    def test_el_nombre_se_normaliza_igual_que_el_limite(self):
        """
        El límite indexa en minúsculas. Si el desbloqueo no normalizara,
        `--usuario Operario` borraría una clave que no existe y diría que todo
        salió bien mientras la persona sigue sin poder entrar.
        """
        self._bloquear()

        call_command("desbloquear_login", usuario="  OPERARIO ", stdout=StringIO())

        self.assertEqual(self._login(password="clave-correcta-123").status_code, 200)

    def test_desbloquear_una_direccion(self):
        for n in range(5):
            self._login(username=f"nadie{n}", REMOTE_ADDR="10.1.1.1")

        self.assertEqual(self._login(REMOTE_ADDR="10.1.1.1").status_code, 429)

        call_command("desbloquear_login", ip="10.1.1.1", stdout=StringIO())

        self.assertEqual(
            self._login(password="clave-correcta-123", REMOTE_ADDR="10.1.1.1").status_code,
            200,
        )

    def test_avisa_cuando_no_habia_bloqueo(self):
        """
        No es un error —puede haber caducado solo—, pero decirlo evita que
        alguien siga buscando un bloqueo que ya no existe.
        """
        salida = StringIO()

        call_command("desbloquear_login", usuario="nadie", stdout=salida)

        self.assertIn("no estaba bloqueada", salida.getvalue())

    def test_sin_argumentos_explica_como_se_usa(self):
        with self.assertRaises(CommandError) as fallo:
            call_command("desbloquear_login")

        self.assertIn("--usuario", str(fallo.exception))

    def test_listar_muestra_a_quien_esta_bloqueado(self):
        self._bloquear()

        salida = StringIO()
        call_command("desbloquear_login", listar=True, stdout=salida)
        texto = salida.getvalue()

        self.assertIn("BLOQUEADO", texto)
        self.assertIn("operario", texto)

    def test_listar_no_cambia_nada(self):
        """Es un diagnóstico. Que desbloqueara al mirar sería una sorpresa."""
        self._bloquear()

        call_command("desbloquear_login", listar=True, stdout=StringIO())

        self.assertEqual(self._login().status_code, 429)

    def test_listar_sin_intentos_recientes_lo_dice(self):
        salida = StringIO()

        call_command("desbloquear_login", listar=True, stdout=salida)

        self.assertIn("Sin intentos", salida.getvalue())


class EstadoDelLimiteTests(BaseDesbloqueo):

    def test_los_intentos_caducados_no_cuentan(self):
        """
        La ventana es deslizante: DRF va soltando las marcas más viejas que la
        duración. Contarlas todas diría que alguien sigue bloqueado cuando ya
        no lo está, y mandaría a desbloquear lo que no toca.
        """
        import time

        clave = clave_de_usuario("operario")
        throttle = LoginUsuarioThrottle()

        # Tres intentos, todos anteriores a la ventana.
        viejo = time.time() - throttle.duration - 10
        cache.set(clave, [viejo, viejo, viejo], 3600)

        estado = estado_del_limite(clave, throttle)

        self.assertEqual(estado["usados"], 0)
        self.assertFalse(estado["bloqueado"])

    def test_dice_cuando_se_libera_el_siguiente_hueco(self):
        self._bloquear()

        estado = estado_del_limite(clave_de_usuario("operario"), LoginUsuarioThrottle())

        self.assertTrue(estado["bloqueado"])
        self.assertGreater(estado["libre_en"], 0)
        self.assertLessEqual(estado["libre_en"], 3600)


class AccionDelAdminTests(BaseDesbloqueo):
    """
    La acción del admin es donde esto se va a usar de verdad: quien resuelve un
    «no puedo entrar» a las tres de la mañana no abre una consola.
    """

    def _admin(self):
        from django.contrib.admin.sites import site

        from .admin import IntentoAccesoAdmin

        return IntentoAccesoAdmin(IntentoAcceso, site)

    def _peticion(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        peticion = RequestFactory().post("/admin/")
        peticion.session = {}
        peticion._messages = FallbackStorage(peticion)

        return peticion

    def test_la_accion_desbloquea_la_cuenta(self):
        self._bloquear()

        self._admin().desbloquear_usuario(
            self._peticion(), IntentoAcceso.objects.filter(usuario="operario")
        )

        self.assertEqual(self._login(password="clave-correcta-123").status_code, 200)

    def test_la_accion_desbloquea_la_direccion(self):
        for n in range(5):
            self._login(username=f"nadie{n}", REMOTE_ADDR="10.2.2.2")

        self.assertEqual(self._login(REMOTE_ADDR="10.2.2.2").status_code, 429)

        self._admin().desbloquear_direccion(
            self._peticion(), IntentoAcceso.objects.filter(ip="10.2.2.2")
        )

        self.assertEqual(
            self._login(password="clave-correcta-123", REMOTE_ADDR="10.2.2.2").status_code,
            200,
        )

    def test_la_columna_muestra_el_estado_del_limite(self):
        self._bloquear()

        intento = IntentoAcceso.objects.filter(usuario="operario").first()

        self.assertIn("BLOQUEADO", self._admin().limite(intento))

    def test_el_registro_sigue_siendo_de_solo_lectura(self):
        """
        Desbloquear borra un contador de la caché, no toca el registro: es un
        registro de hechos y poder editarlo lo invalidaría como evidencia.
        """
        admin = self._admin()
        peticion = self._peticion()

        self.assertFalse(admin.has_add_permission(peticion))
        self.assertFalse(admin.has_change_permission(peticion))
        self.assertFalse(admin.has_delete_permission(peticion))

    def test_desbloquear_no_borra_los_intentos(self):
        self._bloquear()
        antes = IntentoAcceso.objects.count()

        self._admin().desbloquear_usuario(
            self._peticion(), IntentoAcceso.objects.filter(usuario="operario")
        )

        self.assertEqual(IntentoAcceso.objects.count(), antes)


class AlcanceTests(BaseDesbloqueo):

    def test_desbloquear_una_cuenta_no_toca_a_las_demas(self):
        """
        Un desbloqueo demasiado ancho sería peor que ninguno: levantaría el
        freno a un ataque en curso contra otra cuenta sin que nadie lo pida.
        """
        self._bloquear(username="victima")
        self._bloquear(username="operario")

        call_command("desbloquear_login", usuario="operario", stdout=StringIO())

        self.assertEqual(self._login(username="victima").status_code, 429)

    def test_desbloquear_una_cuenta_no_libera_su_direccion(self):
        """
        Son dos límites distintos y protegen de cosas distintas. Que uno
        levantara el otro dejaría sin efecto el que frena la fuerza bruta desde
        una sola máquina.
        """
        for n in range(5):
            self._login(username=f"nadie{n}", REMOTE_ADDR="10.3.3.3")

        call_command("desbloquear_login", usuario="nadie0", stdout=StringIO())

        estado = estado_del_limite(clave_de_ip("10.3.3.3"), LoginIPThrottle())
        self.assertTrue(estado["bloqueado"])
