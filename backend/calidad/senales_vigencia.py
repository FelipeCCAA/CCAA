"""Borrados normales/QuerySet: Collector ya ejecuta el borrado en atomic."""

from django.db.models.signals import post_delete, pre_delete

from .evidencia import bloquear_catalogo
from .vigencia import CATALOGOS, FUENTES, campos_evidencia, invalidar_por_cambio


def antes_de_borrar(sender, instance, using, **kwargs):
    instance._evidencia_antes_de_borrar = {
        campo: getattr(instance, campo) for campo in campos_evidencia(sender._meta.label)
    }
    if sender._meta.label in CATALOGOS:
        bloquear_catalogo(escritura=True, using=using)


def despues_de_borrar(sender, instance, using, **kwargs):
    invalidar_por_cambio(instance, instance._evidencia_antes_de_borrar, None, using=using)


def registrar_senales():
    for etiqueta in sorted(FUENTES):
        pre_delete.connect(antes_de_borrar, sender=etiqueta, dispatch_uid=f"op01.pre_delete.{etiqueta}")
        post_delete.connect(despues_de_borrar, sender=etiqueta, dispatch_uid=f"op01.post_delete.{etiqueta}")
