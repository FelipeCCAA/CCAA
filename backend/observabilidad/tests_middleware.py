"""
El middleware mide sin estorbar.

Dos propiedades que hay que fijar: que cuente las consultas **con
`DEBUG=False`** —que es como corre en producción— y que apagado no exista.

El middleware se inyecta aquí con `override_settings` y no se apoya en el
`settings.py` del proyecto: la conexión real es de otra tarea, y una prueba
que dependa de ella mediría el cableado en vez del middleware.
"""

import json

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import MiddlewareNotUsed
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from observabilidad.middleware import MetricasMiddleware
from usuarios.models import PerfilUsuario, Rol


CON_METRICAS = override_settings(
    METRICAS_ACTIVAS=True,
    DEBUG=False,
    MIDDLEWARE=list(settings.MIDDLEWARE)
    + ["observabilidad.middleware.MetricasMiddleware"],
)


@CON_METRICAS
class MetricasMiddlewareTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user("medido", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

    def _medicion(self, salida):
        """La línea del registro viene como `INFO:metricas:{json}`."""
        return json.loads(salida[0].split(":", 2)[2])

    def test_registra_una_linea_por_request_con_consultas_contadas(self):
        with self.assertLogs("metricas", level="INFO") as registro:
            respuesta = self.cliente.get("/api/recepcion/analisis-silo/")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(registro.output), 1)

        datos = self._medicion(registro.output)
        self.assertEqual(datos["metodo"], "GET")
        self.assertEqual(datos["estado"], 200)
        self.assertEqual(datos["usuario"], "medido")
        self.assertGreater(datos["ms"], 0)
        self.assertGreater(
            datos["consultas"], 0,
            "Con DEBUG=False, `connection.queries` está vacío: hay que contar "
            "con execute_wrapper o esto sale en cero y la medición miente.",
        )
        self.assertGreater(datos["ms_sql"], 0)

    def test_la_ruta_agrupa_los_detalles_por_su_patron(self):
        """
        Sin esto, cada id sería un endpoint distinto y el resumen tendría
        una fila por registro en vez de una por endpoint.
        """
        from datetime import datetime, timezone as tz
        from decimal import Decimal

        from maestros.models import Silo
        from recepcion.models import AnalisisSilo

        silo = Silo.objects.create(
            codigo="SILO 7", tipo=Silo.Tipo.SILO, capacidad_l=Decimal("1000")
        )
        analisis = AnalisisSilo.objects.create(
            silo=silo, tomado_en=datetime(2026, 8, 20, 9, 0, tzinfo=tz.utc)
        )

        with self.assertLogs("metricas", level="INFO") as registro:
            self.cliente.get(f"/api/recepcion/analisis-silo/{analisis.id}/")

        datos = self._medicion(registro.output)
        self.assertNotIn(f"/{analisis.id}/", datos["ruta"])
        self.assertIn("analisis-silo", datos["ruta"])

    def test_un_error_tambien_se_mide(self):
        """
        Un 4xx que consulta la base cuesta lo mismo que uno que responde. Si
        solo se midieran los 200, un endpoint que falla en bucle sería
        invisible justo cuando más importa.
        """
        with self.assertLogs("metricas", level="INFO") as registro:
            self.cliente.get("/api/recepcion/analisis-silo/999999/")

        datos = self._medicion(registro.output)
        self.assertEqual(datos["estado"], 404)


class MiddlewareApagadoTests(TestCase):
    @override_settings(METRICAS_ACTIVAS=False)
    def test_apagado_django_lo_descarta(self):
        """
        `MiddlewareNotUsed` hace que Django lo saque de la cadena: apagado no
        cuesta una llamada por request, cuesta cero.
        """
        with self.assertRaises(MiddlewareNotUsed):
            MetricasMiddleware(lambda peticion: None)
