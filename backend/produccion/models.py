"""
Registro de producción: lotes y sus análisis de calidad.

Traducción de las entidades `lote` y `analisis` de
`prototipo/js/modelo/esquema.js`.

Dos decisiones del modelo original que se respetan aquí y conviene tener
presentes al leer el código:

1. El resultado de calidad NO se guarda (MODELO_DATOS.md §2.2). No existe un
   campo `resultado` en `Lote`: se recalcula siempre desde los análisis y la
   especificación vigente. Así, al corregir una especificación, todo el
   histórico queda reevaluado sin migraciones ni recálculos manuales.

2. El código de lote NO es la identidad del lote (MODELO_DATOS.md §2.1). En
   planta es un correlativo diario que se repite entre productos y entre días.
   La identidad la asigna la base; lo que se controla como único es la clave
   natural `codigo_lote + producto + fecha`.
"""

from django.core.exceptions import ValidationError
from django.db import models

from maestros.catalogos import CLAVES_PARAMETROS
from maestros.models import Especificacion, Producto


class Lote(models.Model):
    """Unidad de producción y de liberación."""

    class Linea(models.TextChoices):
        E1 = "E1", "Línea 1 · E1"
        E2 = "E2", "Línea 2 · E2"

    class Turno(models.TextChoices):
        A = "A", "Turno A"
        B = "B", "Turno B"
        C = "C", "Turno C"

    class Estado(models.TextChoices):
        EN_PROCESO = "en_proceso", "En proceso"
        PRODUCIDO = "producido", "Producido"
        CERRADO = "cerrado", "Cerrado"
        ANULADO = "anulado", "Anulado"

    # Transiciones válidas entre estados, tal como las declara el esquema del
    # prototipo. Por ahora solo documentan; el bloqueo real vive en la capa de
    # dominio, que se porta en la fase siguiente.
    TRANSICIONES = {
        Estado.EN_PROCESO: [Estado.PRODUCIDO, Estado.ANULADO],
        Estado.PRODUCIDO: [Estado.CERRADO, Estado.ANULADO],
        Estado.CERRADO: [],
        Estado.ANULADO: [],
    }

    codigo_lote = models.CharField(
        "Código de lote",
        max_length=60,
        help_text="Correlativo de planta. No es único: se repite entre productos y días",
    )
    op = models.CharField(
        "OP",
        max_length=60,
        blank=True,
        help_text="Orden de producción, si existe",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="lotes",
        verbose_name="Producto",
    )
    fecha = models.DateField("Fecha de producción")
    linea = models.CharField("Línea", max_length=5, choices=Linea.choices, blank=True)
    turno = models.CharField("Turno", max_length=5, choices=Turno.choices, blank=True)
    kg_producidos = models.DecimalField(
        "Kilos producidos", max_digits=12, decimal_places=2
    )
    bultos = models.PositiveIntegerField(
        "Bultos", null=True, blank=True, help_text="Bolsas o cajas"
    )
    hora_inicio = models.TimeField("Hora de inicio", null=True, blank=True)
    hora_termino = models.TimeField("Hora de término", null=True, blank=True)
    vencimiento = models.DateField("Vencimiento", null=True, blank=True)
    estado = models.CharField(
        "Estado",
        max_length=20,
        choices=Estado.choices,
        default=Estado.EN_PROCESO,
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Lote de producción"
        verbose_name_plural = "Lotes de producción"
        ordering = ["-fecha", "codigo_lote"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo_lote", "producto", "fecha"],
                name="lote_clave_natural_unica",
            ),
            models.CheckConstraint(
                condition=models.Q(kg_producidos__gte=0),
                name="lote_kg_no_negativos",
            ),
        ]

    def __str__(self):
        return f"{self.codigo_lote} · {self.producto} · {self.fecha}"

    def clean(self):
        if (
            self.hora_inicio is not None
            and self.hora_termino is not None
            and self.hora_termino == self.hora_inicio
        ):
            raise ValidationError(
                {"hora_termino": "La hora de término no puede ser igual a la de inicio."}
            )


class Analisis(models.Model):
    """
    Medición fisicoquímica de un lote.

    Puede haber varias por lote (una por muestra o por despacho); el veredicto
    del lote las agrega por el peor caso. Ese criterio está pendiente de
    confirmar con Calidad (MODELO_DATOS.md §8.2).
    """

    lote = models.ForeignKey(
        Lote,
        on_delete=models.CASCADE,
        related_name="analisis",
        verbose_name="Lote",
    )
    fecha = models.DateField("Fecha del análisis")
    muestra = models.CharField(
        "Muestra",
        max_length=120,
        blank=True,
        help_text="Identificador de la muestra o del despacho analizado",
    )
    valores = models.JSONField(
        "Parámetros medidos",
        default=dict,
        help_text='{"humedad": 3.2, "mg": 26.5, ...}',
    )
    especificacion = models.ForeignKey(
        Especificacion,
        on_delete=models.PROTECT,
        related_name="analisis",
        null=True,
        blank=True,
        verbose_name="Especificación aplicada",
        help_text="Versión usada al evaluar. Se congela para auditoría",
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Análisis de calidad"
        verbose_name_plural = "Análisis de calidad"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Análisis de {self.lote.codigo_lote} · {self.fecha}"

    def clean(self):
        """Valida la forma de `valores`, que por ser JSON la base no valida."""
        if not isinstance(self.valores, dict):
            raise ValidationError({"valores": "Debe ser un objeto de parámetros."})

        desconocidos = set(self.valores) - CLAVES_PARAMETROS
        if desconocidos:
            raise ValidationError(
                {"valores": f"Parámetros no reconocidos: {', '.join(sorted(desconocidos))}"}
            )

        for parametro, valor in self.valores.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise ValidationError(
                    {"valores": f"El valor de '{parametro}' debe ser numérico."}
                )
