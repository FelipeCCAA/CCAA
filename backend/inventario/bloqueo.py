"""
Un candado para operaciones caras que no deben solaparse.

El MRP semanal explota las recetas multinivel de toda una semana **dentro de la
petición HTTP**. Sacarlo a una cola es lo correcto, pero exige mantener un
proceso trabajador de Celery. Mientras ese worker no esté habilitado, el riesgo
concreto no
es que tarde: es que **se apile**.

Basta con que tres personas pulsen «calcular» —o que una pulse tres veces
porque no ve respuesta— para tener tres explosiones completas compitiendo por
las mismas conexiones a PostgreSQL. Este candado convierte eso en una espera
educada y un mensaje.

Se apoya en `cache.add`, que es atómico: o lo pone quien llega primero, o no lo
pone nadie más. Por eso la caché tiene que ser **compartida entre instancias**
—hoy es la base de datos—; con una caché local a cada proceso, cada instancia
tendría su propio candado y no habría candado en absoluto.
"""

from contextlib import contextmanager

from django.core.cache import cache


class YaEnCurso(RuntimeError):
    """Otra ejecución de lo mismo está corriendo ahora."""


@contextmanager
def solo_uno(clave, segundos=300):
    """
    Deja pasar una sola ejecución de `clave` a la vez.

    `segundos` es el plazo tras el cual el candado se suelta solo. Existe
    porque un proceso que muere a mitad no alcanza a soltarlo, y sin caducidad
    la operación quedaría bloqueada para siempre — hay que elegir entre un
    reintento prematuro y un bloqueo eterno, y lo segundo es peor.
    """
    if not cache.add(clave, True, segundos):
        raise YaEnCurso(clave)

    try:
        yield
    finally:
        # Se suelta pase lo que pase: si el cálculo falla, el siguiente intento
        # no tiene por qué esperar los cinco minutos.
        cache.delete(clave)
