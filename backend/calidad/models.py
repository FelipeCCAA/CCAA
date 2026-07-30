"""
Liberación de producto: los formularios completados y la autorización final.

Traducción de las entidades `registroCalidad` y `liberacion` de
`prototipo/js/modelo/esquema.js`. El catálogo de documentos vive en `maestros`,
porque es un maestro que administra Calidad, no un dato transaccional.

Aquí se materializa la regla que justifica el sistema (MODELO_DATOS.md §1):

    Un despacho exige un lote liberado. Un lote se libera si todos sus
    formularios están completos y firmados Y su calidad es conforme contra la
    especificación vigente a la fecha del lote. Si no es conforme, solo puede
    salir como liberación bajo concesión: con motivo escrito, autorizador
    identificado y marca permanente.

Dos ausencias deliberadas, que son decisiones y no olvidos:

1. `Liberacion` no guarda el avance documental. Se deriva de los
   `RegistroCalidad` del lote (MODELO_DATOS.md §2.6). Si se guardara, cambiar
   la plantilla de un documento dejaría el avance mintiendo: diría "completo"
   sobre un formulario al que ahora le faltan campos.

2. `Liberacion` tampoco guarda el resultado de calidad. Se recalcula siempre
   desde los análisis y la especificación vigente (§2.2), igual que en
   `produccion`.

Lo que sí se guarda es lo que constituye el acto: quién autorizó, cuándo, y con
qué motivo si fue por concesión. Eso no se deriva de nada — es la firma.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from maestros.models import DocumentoLiberacion
from produccion.models import Lote


class RegistroCalidad(models.Model):
    """
    Un formulario del checklist ya completado para un lote concreto.

    Es el documento digitalizado: guarda los valores tal como se ingresaron,
    quién los firmó y cuándo. Se guardan por la `clave` de cada campo de la
    plantilla del documento.

    El estado no es decorativo. Un registro en `borrador` u `observado` NO
    cuenta como cumplido, y un `observado` bloquea la liberación aunque el
    resto del checklist esté completo: una observación sin resolver es
    justamente el motivo por el que alguien no debería firmar.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        COMPLETADO = "completado", "Completado"
        OBSERVADO = "observado", "Observado"

    lote = models.ForeignKey(
        Lote,
        on_delete=models.CASCADE,
        related_name="registros_calidad",
        verbose_name="Lote",
    )
    documento = models.ForeignKey(
        DocumentoLiberacion,
        on_delete=models.PROTECT,
        related_name="registros",
        verbose_name="Documento",
    )
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.BORRADOR,
    )
    valores = models.JSONField(
        "Valores del formulario",
        default=dict,
        blank=True,
        help_text="{clave del campo de la plantilla: valor}",
    )
    referencia = models.CharField(
        "Referencia",
        max_length=120,
        blank=True,
        help_text="N.º del documento físico o externo, si lo hay",
    )
    completado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_calidad",
        null=True,
        blank=True,
        verbose_name="Completado por",
    )
    completado_en = models.DateTimeField("Completado en", null=True, blank=True)
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Registro de calidad"
        verbose_name_plural = "Registros de calidad"
        ordering = ["lote", "documento__orden"]
        constraints = [
            # Un documento se completa una vez por lote. Sin esto, dos
            # registros del mismo documento se pisarían al calcular el avance,
            # y el checklist podría darse por cumplido con el borrador
            # equivocado.
            models.UniqueConstraint(
                fields=["lote", "documento"],
                name="registro_calidad_unico_por_lote_y_documento",
            )
        ]

    def __str__(self):
        return f"{self.documento} · {self.lote.codigo_lote}"

    def clean(self):
        if not isinstance(self.valores, dict):
            raise ValidationError({"valores": "Debe ser un objeto de valores por clave."})

        # Un formulario observado sin decir qué se observó no le sirve a nadie:
        # quien lo lea después no sabe qué hay que resolver para liberar.
        if self.estado == self.Estado.OBSERVADO and not self.observacion.strip():
            raise ValidationError(
                {"observacion": "Un formulario observado debe decir qué se observó."}
            )


class Liberacion(models.Model):
    """
    La autorización de Calidad para despachar un lote, y su firma.

    Hay una por lote. El expediente existe desde que el lote se produce (en
    `pendiente`): que un lote no tenga liberación no significa que no la
    necesite, sino que nadie la ha tramitado, y esa distinción se pierde si la
    fila no existe.
    """

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_REVISION = "en_revision", "En revisión"
        LIBERADO = "liberado", "Liberado"
        CONCESION = "liberado_concesion", "Liberado bajo concesión"
        RECHAZADO = "rechazado", "Rechazado"

    # Transiciones válidas, tal como las declara el esquema del prototipo.
    # Un lote liberado puede volver a revisión: al desmarcar un documento el
    # checklist deja de estar completo y la autorización ya no se sostiene.
    TRANSICIONES = {
        Estado.PENDIENTE: [Estado.EN_REVISION, Estado.RECHAZADO],
        Estado.EN_REVISION: [
            Estado.LIBERADO,
            Estado.CONCESION,
            Estado.RECHAZADO,
            Estado.PENDIENTE,
        ],
        Estado.LIBERADO: [Estado.EN_REVISION],
        Estado.CONCESION: [Estado.EN_REVISION],
        Estado.RECHAZADO: [Estado.EN_REVISION],
    }

    # Estados en que el producto puede salir de la planta.
    ESTADOS_LIBERADO = (Estado.LIBERADO, Estado.CONCESION)

    lote = models.OneToOneField(
        Lote,
        on_delete=models.CASCADE,
        related_name="liberacion",
        verbose_name="Lote",
    )
    estado = models.CharField(
        "Estado",
        max_length=25,
        choices=Estado.choices,
        default=Estado.PENDIENTE,
    )
    autorizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="liberaciones",
        null=True,
        blank=True,
        verbose_name="Autorizada por",
        help_text="Rol calidad o admin",
    )
    autorizada_en = models.DateTimeField("Autorizada en", null=True, blank=True)
    concesion = models.BooleanField(
        "Bajo concesión",
        default=False,
        help_text="Marca permanente: el producto salió sin ser conforme",
    )
    motivo_concesion = models.TextField(
        "Motivo de la concesión",
        blank=True,
        help_text="Obligatorio si es una concesión",
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Liberación de producto"
        verbose_name_plural = "Liberaciones de producto"
        ordering = ["-autorizada_en", "lote"]

    def __str__(self):
        return f"{self.lote.codigo_lote} · {self.get_estado_display()}"

    @property
    def liberado(self) -> bool:
        """¿El producto puede salir? Es lo único que Despachos necesita saber."""
        return self.estado in self.ESTADOS_LIBERADO

    def clean(self):
        # La concesión sin motivo es la que hay que impedir: es la firma que
        # deja salir producto no conforme sin dejar dicho por qué. La regla
        # completa (largo mínimo, rol autorizador) vive en el dominio; esto es
        # la red de seguridad de la base.
        if self.concesion and not self.motivo_concesion.strip():
            raise ValidationError(
                {"motivo_concesion": "Una liberación bajo concesión exige un motivo escrito."}
            )

        if self.estado == self.Estado.CONCESION and not self.concesion:
            raise ValidationError(
                {"concesion": "El estado dice concesión: la marca permanente debe quedar puesta."}
            )

        if self.estado in self.ESTADOS_LIBERADO and self.autorizada_por is None:
            raise ValidationError(
                {"autorizada_por": "Una liberación sin autorizador identificado no es una firma."}
            )

    def puede_pasar_a(self, estado: str) -> bool:
        """¿Es válido el salto desde el estado actual al pedido?"""
        return estado in self.TRANSICIONES.get(self.estado, [])
