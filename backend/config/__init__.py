"""
Se importa la aplicación Celery al arrancar Django.

Sin esto, `@shared_task` no encuentra a qué aplicación registrarse y las tareas
quedan mudas: `delay()` no falla, simplemente no llega a ninguna parte. Es de
los fallos más difíciles de ver, porque todo parece funcionar.
"""

from .celery import app as celery_app

__all__ = ("celery_app",)
