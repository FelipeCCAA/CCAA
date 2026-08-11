"""
Pruebas del MRP encolado.

El cálculo salió de la petición HTTP: ocupaba un worker de Gunicorn de
principio a fin y con workers `sync` tres cálculos dejaban al resto de la
planta esperando.

Lo que se fija aquí es que **el contrato sea uno solo**. Con broker o sin él, la
API devuelve la ejecución y la pantalla consulta su estado; si hubiera dos
formas de responder habría dos caminos que mantener y solo uno se probaría.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from planificacion.models import SemanaPlan

from .models import EjecucionMRP
from .tareas import calcular_mrp_semana


class BaseMRP(TestCase):

    def setUp(self):
        cache.clear()

        usuario = User.objects.create_superuser(username="admin-mrp", password="x")

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        self.usuario = usuario

        self.semana = SemanaPlan.objects.create(
            codigo="W-MRP", anio=2026, fecha_inicio=date(2026, 8, 3),
            estado=SemanaPlan.Estado.PUBLICADA,
        )

    def tearDown(self):
        cache.clear()

    def _ejecutar(self, semana=None):
        return self.cliente.post(
            "/api/inventario/ejecuciones-mrp/ejecutar/",
            {"semana": (semana or self.semana).pk},
            format="json",
        )


class ContratoTests(BaseMRP):

    def test_responde_202_con_la_ejecucion(self):
        """
        202 y no 201: lo que vuelve es la ejecución, no el resultado. La
        pantalla consulta su estado.
        """
        respuesta = self._ejecutar()

        self.assertEqual(respuesta.status_code, 202)
        self.assertIn("estado", respuesta.data)
        self.assertIn("terminada", respuesta.data)

    def test_la_respuesta_sale_antes_de_que_el_calculo_termine(self):
        """
        Es el punto de todo esto: la petición **no espera** al cálculo. Devuelve
        la ejecución en cola y se va.
        """
        respuesta = self._ejecutar()

        self.assertEqual(respuesta.data["estado"], EjecucionMRP.Estado.PENDIENTE)
        self.assertFalse(respuesta.data["terminada"])

    def test_sin_broker_la_tarea_corre_al_confirmar_la_transaccion(self):
        """
        Es lo que permite desplegar esto sin tener todavía Redis ni un worker.

        La tarea se despacha con `transaction.on_commit` y no con `delay()` a
        secas: con un worker real, la tarea puede empezar antes de que se
        confirme la transacción de esta petición y no encontrar la ejecución
        que acaba de crearse. Es una carrera que solo aparece bajo carga.

        `captureOnCommitCallbacks` es lo que dispara esos avisos aquí: en una
        `TestCase` todo vive dentro de una transacción que nunca se confirma,
        así que sin esto la tarea no correría **nunca** y la prueba mediría el
        vacío.
        """
        with self.captureOnCommitCallbacks(execute=True):
            respuesta = self._ejecutar()

        ejecucion = EjecucionMRP.objects.get(pk=respuesta.data["id"])

        self.assertEqual(ejecucion.estado, EjecucionMRP.Estado.TERMINADA)
        self.assertIsNotNone(ejecucion.terminada_en)

    def test_el_estado_no_se_puede_escribir_desde_la_api(self):
        """
        Lo escribe la tarea. Escribible desde fuera, cualquiera podría marcar
        como terminada una ejecución a medias — y nadie vuelve a mirar algo que
        figura hecho.
        """
        ejecucion = EjecucionMRP.objects.create(
            fecha_corte=date(2026, 8, 3), horizonte_hasta=date(2026, 8, 9),
            ejecutada_por=self.usuario, estado=EjecucionMRP.Estado.PENDIENTE,
        )

        respuesta = self.cliente.get(
            f"/api/inventario/ejecuciones-mrp/{ejecucion.pk}/"
        )

        self.assertEqual(respuesta.data["estado"], EjecucionMRP.Estado.PENDIENTE)
        self.assertFalse(respuesta.data["terminada"])


class RechazoTempranoTests(BaseMRP):

    def test_una_semana_no_publicada_se_rechaza_en_el_acto(self):
        """
        Lo que puede fallar rápido falla antes de encolar: quien pulsa el botón
        se entera al momento, en vez de tener que consultar el estado para
        descubrir un rechazo que no dependía del cálculo.
        """
        borrador = SemanaPlan.objects.create(
            codigo="W-BORRADOR", anio=2026, fecha_inicio=date(2026, 8, 10),
        )

        respuesta = self._ejecutar(borrador)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(EjecucionMRP.objects.count(), 0)

    def test_no_se_apilan_dos_calculos_de_la_misma_semana(self):
        """
        El candado sigue vigente aunque el cálculo se encole: con worker, dos
        peticiones seguidas meterían dos tareas idénticas en la cola.
        """
        from .bloqueo import solo_uno

        with solo_uno(f"mrp:semana:{self.semana.pk}"):
            respuesta = self._ejecutar()

        self.assertEqual(respuesta.status_code, 409)


class FalloDeLaTareaTests(BaseMRP):

    def test_un_fallo_deja_el_motivo_escrito(self):
        """
        Una ejecución fallida sin decir por qué obliga a repetirla para
        averiguarlo, y repetirla es justo lo caro.
        """
        ejecucion = EjecucionMRP.objects.create(
            fecha_corte=date(2026, 8, 3), horizonte_hasta=date(2026, 8, 9),
            ejecutada_por=self.usuario, estado=EjecucionMRP.Estado.PENDIENTE,
            # Una semana que no existe: la tarea falla al buscarla.
            parametros={"semana": 999999},
        )

        calcular_mrp_semana(ejecucion.pk)

        ejecucion.refresh_from_db()
        self.assertEqual(ejecucion.estado, EjecucionMRP.Estado.FALLIDA)
        self.assertTrue(ejecucion.error)
        self.assertIsNotNone(ejecucion.terminada_en)

    def test_una_ejecucion_que_ya_no_existe_no_revienta(self):
        """
        Puede desaparecer entre encolar y correr. No es un error del cálculo y
        reintentar no la va a resucitar.
        """
        calcular_mrp_semana(999999)
