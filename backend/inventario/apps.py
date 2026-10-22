from django.apps import AppConfig


class InventarioConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventario"

    def ready(self):
        from django.db.models.signals import pre_delete
        from .documentos_adjuntos import DOCUMENTOS, conservar_documento_con_adjuntos
        for modelo in DOCUMENTOS:
            pre_delete.connect(conservar_documento_con_adjuntos, sender=modelo, weak=False,
                               dispatch_uid=f"conservar_adjuntos_{modelo}")
