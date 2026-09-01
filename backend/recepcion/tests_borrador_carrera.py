"""
Que confirmar un borrador no se pueda deshacer por un autoguardado en vuelo.

El defecto que esto fija
------------------------
Los formularios con borrador —recepción, análisis de silo, vale y lote—
autoguardan con dos segundos de retardo. Al pulsar «Confirmar» puede quedar un
`guardar-borrador` en camino: si ese PATCH lee la fila **antes** de que la
confirmación se comprometa, `serializer.save()` reescribe todas las columnas
—incluida `estado`— y devuelve a borrador un documento ya confirmado.

Las dos peticiones responden 200 y el operador ve el mensaje de éxito. Lo que
falla aparece mucho después y en otra pantalla: al transferir un vale, con «el
silo no tiene un análisis confirmado vigente». Nada apunta a la confirmación
perdida.

Se vio ocurrir en el registro del servidor, en el mismo segundo:

    POST  /api/recepcion/analisis-silo/7/confirmar-borrador/  200
    PATCH /api/recepcion/analisis-silo/7/guardar-borrador/    200   ← lo deshizo

Qué se comprueba
----------------
El **bloqueo**, no la carrera. Lanzar dos hilos y mirar quién gana no delata
nada: sin bloqueo la carrera se pierde por milisegundos y la prueba pasaría casi
siempre. Es el mismo criterio que `calidad.tests_concurrencia`, y por el mismo
motivo hace falta `TransactionTestCase`: `TestCase` envuelve cada prueba en una
transacción que nunca se confirma, así que la segunda conexión no vería nada.
"""

import threading
import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection, connections
from django.test import TransactionTestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo
from recepcion.models import AnalisisSilo
from usuarios.models import PerfilUsuario, Rol


class ConfirmarBorradorBloqueaTests(TransactionTestCase):
    def setUp(self):
        usuario = User.objects.create_user("analista", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)
        self.usuario = usuario

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        self.silo = Silo.objects.create(
            codigo="SILO CARRERA", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("100000")
        )

        # Los tres últimos son los que `motivos_para_confirmar` exige: sin
        # ellos la confirmación responde 400 y la prueba mediría otra cosa.
        respuesta = self.cliente.post(
            "/api/recepcion/analisis-silo/crear-borrador/",
            {
                "silo": self.silo.id,
                "grasa": "3.60",
                "sng": "8.60",
                "inhibidores_resultado": "negativo",
                "metodo": "delvo_sp",
                "hora_lectura": "10:15",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.borrador_id = respuesta.data["id"]

    def _patch_tardio(self, resultado):
        """El autoguardado que llega tarde, por la API y en su propia conexión."""
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.get(user=self.usuario).key}"
        )
        try:
            respuesta = cliente.patch(
                f"/api/recepcion/analisis-silo/{self.borrador_id}/guardar-borrador/",
                {"silo": self.silo.id, "grasa": "9.99"},
                format="json",
            )
            resultado.append(respuesta.status_code)
        except Exception as error:  # pragma: no cover - solo para diagnosticar
            resultado.append(f"error inesperado: {error!r}")
        finally:
            connections.close_all()

    def test_un_autoguardado_en_vuelo_no_deshace_la_confirmacion(self):
        """
        Las dos peticiones **por la vista**, solapadas a propósito.

        La confirmación se ralentiza metiendo una pausa dentro de `confirmar`,
        que corre ya dentro de la transacción de la vista. Así el PATCH entra
        seguro en la ventana en que antes ganaba, en vez de depender de que la
        carrera caiga del lado malo.

        Sin `bloquear=True` en la vista, el PATCH lee la fila todavía en
        borrador, `serializer.save()` reescribe `estado` y el documento vuelve a
        borrador: comprobado quitando el argumento, la prueba falla con
        `estado == 'borrador'`. Con el bloqueo, el PATCH espera, relee y
        responde 409.
        """
        if not connection.features.has_select_for_update:
            self.skipTest(
                "este motor no bloquea filas: la protección NO existe aquí"
            )

        original = AnalisisSilo.confirmar
        arrancado = threading.Event()

        def confirmar_lento(self_analisis, usuario):
            arrancado.set()
            time.sleep(1.5)
            return original(self_analisis, usuario)

        resultado = []
        hilo = threading.Thread(target=self._patch_tardio, args=(resultado,))

        with patch.object(AnalisisSilo, "confirmar", confirmar_lento):
            lanzador = threading.Thread(
                target=lambda: (arrancado.wait(5), hilo.start()),
            )
            lanzador.start()

            confirmar = self.cliente.post(
                f"/api/recepcion/analisis-silo/{self.borrador_id}/confirmar-borrador/",
                {},
                format="json",
            )
            lanzador.join(timeout=10)
            hilo.join(timeout=15)

        self.assertEqual(confirmar.status_code, 200, confirmar.data)
        self.assertEqual(
            resultado,
            [409],
            "El autoguardado tardío fue aceptado mientras se confirmaba.",
        )

        analisis = AnalisisSilo.objects.get(pk=self.borrador_id)
        self.assertEqual(
            analisis.estado,
            AnalisisSilo.Estado.CONFIRMADO,
            "Un autoguardado en vuelo devolvió a borrador un análisis ya "
            "confirmado. El silo se queda sin análisis vigente y el vale no "
            "se puede transferir, sin que nada haya dado error.",
        )
        self.assertEqual(analisis.grasa, Decimal("3.60"))

    def test_confirmado_el_autoguardado_tardio_no_lo_revierte(self):
        """
        Lo que ve el cliente cuando llega tarde: 409, y el estado intacto.

        Esta mitad no necesita concurrencia. Comprueba la consecuencia
        observable —que la confirmación sobreviva— con la secuencia exacta que
        produce el formulario: confirmar y, acto seguido, el PATCH pendiente.
        """
        confirmar = self.cliente.post(
            f"/api/recepcion/analisis-silo/{self.borrador_id}/confirmar-borrador/",
            {},
            format="json",
        )
        self.assertEqual(confirmar.status_code, 200, confirmar.data)

        tardio = self.cliente.patch(
            f"/api/recepcion/analisis-silo/{self.borrador_id}/guardar-borrador/",
            {"silo": self.silo.id, "grasa": "9.99"},
            format="json",
        )

        self.assertEqual(tardio.status_code, 409, tardio.data)

        analisis = AnalisisSilo.objects.get(pk=self.borrador_id)
        self.assertEqual(analisis.estado, AnalisisSilo.Estado.CONFIRMADO)
        self.assertEqual(analisis.grasa, Decimal("3.60"))
