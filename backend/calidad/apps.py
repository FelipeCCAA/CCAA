from django.apps import AppConfig
from django.core.checks import register


class CalidadConfig(AppConfig):
    name = 'calidad'
    verbose_name = 'Liberación de producto'

    def ready(self):
        # Avisa si el motor no sabe bloquear filas. Sin ese bloqueo, la firma
        # de una liberación no está protegida de una modificación concurrente
        # (ver checks.py y DECISIONES.md).
        from .checks import motor_soporta_bloqueo

        register(motor_soporta_bloqueo)
