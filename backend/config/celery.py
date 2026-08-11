"""
La aplicación Celery del proyecto.

Existe para una sola cosa por ahora: sacar el MRP semanal de la petición HTTP.
La explosión multinivel de una semana entera ocupaba un worker de Gunicorn de
principio a fin, y con `sync` workers eso significa que tres cálculos dejan al
resto de la planta esperando —de ahí los `WORKER TIMEOUT` que aparecieron en la
prueba de carga—.

**Sin broker configurado, Celery corre en modo `eager`**: la tarea se ejecuta
en el momento, dentro de la misma petición, exactamente como antes. No es un
apaño, es la propiedad que permite desplegar este código sin tener todavía
Redis ni un worker, y que el entorno de desarrollo y las pruebas no necesiten
infraestructura para funcionar.

El contrato de la API es el mismo en los dos casos —siempre devuelve la
ejecución y la pantalla consulta su estado—, así que no hay dos caminos que
mantener ni dos comportamientos que probar.
"""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ccaa")

# Toda la configuración vive en settings.py con el prefijo CELERY_, para que no
# haya un segundo sitio donde mirar cuando algo no cuadra.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descubre `tareas.py` en cada app instalada.
app.autodiscover_tasks(related_name="tareas")
