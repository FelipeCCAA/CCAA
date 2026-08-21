"""
Mide cada request: latencia, consultas SQL y tiempo en SQL.

**Cuenta con `connection.execute_wrapper` y no con `connection.queries`.**
`connection.queries` solo se llena con `DEBUG=True`; en producción devolvería
cero consultas por request y la medición diría que no hay N+1 en ninguna
parte — que es justo la conclusión que no queremos sacar por accidente.

Escribe una línea JSON por request a un logger y no a la base: guardar la
medición en PostgreSQL agregaría escrituras a cada request y distorsionaría
exactamente lo que se está midiendo.
"""

import json
import logging
import time

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from django.db import connection

registro = logging.getLogger("metricas")


class _Contador:
    """
    Cuenta consultas y su tiempo, sin depender de `DEBUG`.

    Es un `execute_wrapper`: Django lo llama alrededor de cada consulta que
    pasa por esta conexión, en cualquier entorno.
    """

    def __init__(self):
        self.consultas = 0
        self.segundos = 0.0

    def __call__(self, ejecutar, sql, parametros, muchos, contexto):
        inicio = time.perf_counter()
        try:
            return ejecutar(sql, parametros, muchos, contexto)
        finally:
            # En el `finally` para que una consulta que revienta también
            # cuente: un endpoint que falla consultando cuesta igual.
            self.consultas += 1
            self.segundos += time.perf_counter() - inicio


def _ruta_de(peticion):
    """
    El **patrón** de la ruta, no la URL.

    Sin esto cada id sería un endpoint distinto y el resumen tendría una fila
    por lote en vez de una por endpoint. `resolver_match` solo existe después
    de resolver la vista; si no está —un 404 sin ruta, por ejemplo— se cae a
    la ruta literal, que es lo único que hay.
    """
    coincidencia = getattr(peticion, "resolver_match", None)

    if coincidencia is None or not coincidencia.route:
        return peticion.path

    # Los routers de DRF arman las rutas con expresiones regulares, así que
    # `route` viene con los anclajes puestos. Se quitan para que la tabla del
    # resumen se pueda leer.
    return "/" + coincidencia.route.lstrip("^").rstrip("$")


class MetricasMiddleware:
    def __init__(self, obtener_respuesta):
        if not getattr(settings, "METRICAS_ACTIVAS", False):
            # Django lo saca de la cadena: apagado cuesta cero, no una
            # llamada por request.
            raise MiddlewareNotUsed

        self.obtener_respuesta = obtener_respuesta

    def __call__(self, peticion):
        contador = _Contador()
        inicio = time.perf_counter()

        with connection.execute_wrapper(contador):
            respuesta = self.obtener_respuesta(peticion)

        transcurrido = (time.perf_counter() - inicio) * 1000

        usuario = getattr(peticion, "user", None)

        registro.info(
            json.dumps(
                {
                    "ruta": _ruta_de(peticion),
                    "metodo": peticion.method,
                    "estado": respuesta.status_code,
                    "ms": round(transcurrido, 2),
                    "consultas": contador.consultas,
                    "ms_sql": round(contador.segundos * 1000, 2),
                    "t": round(time.time(), 3),
                    "usuario": (
                        usuario.username
                        if usuario is not None and usuario.is_authenticated
                        else ""
                    ),
                }
            )
        )

        return respuesta
