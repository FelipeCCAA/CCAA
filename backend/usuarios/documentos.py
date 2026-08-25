"""Comportamiento común de documentos operacionales persistidos a medias."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class DocumentoBorradorMixin(models.Model):
    abierto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_borradores",
    )
    abierto_en = models.DateTimeField(null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR: tuple[str, ...] = ()
    ESTADO_BORRADOR = "borrador"
    ESTADO_CONFIRMADO = ""

    class Meta:
        abstract = True

    @property
    def es_borrador(self):
        return self.estado == self.ESTADO_BORRADOR

    def motivos_para_confirmar(self):
        motivos = []
        for campo in self.CAMPOS_OBLIGATORIOS_AL_CONFIRMAR:
            valor = getattr(self, campo)
            if valor in (None, "") or (
                isinstance(valor, (int, float, Decimal)) and valor <= 0
            ):
                etiqueta = self._meta.get_field(campo).verbose_name
                motivos.append(f"Falta {str(etiqueta).lower()}.")
        return motivos

    def confirmar(self, usuario):
        if not self.es_borrador:
            return ["El documento ya no está en borrador."]

        motivos = self.motivos_para_confirmar()
        if motivos:
            return motivos

        self.estado = self.ESTADO_CONFIRMADO
        if self.abierto_por_id is None:
            self.abierto_por = usuario
        if self.abierto_en is None:
            self.abierto_en = timezone.now()
        self.save()
        return []
