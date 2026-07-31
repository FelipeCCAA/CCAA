from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auditoria"
    verbose_name = "Auditoría"

    def ready(self):
        # Conecta las señales que capturan los cambios. Va aquí y no en
        # `models.py` para que se registren una sola vez.
        from . import registro  # noqa: F401
