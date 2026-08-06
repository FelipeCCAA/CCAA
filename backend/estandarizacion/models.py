"""
El vale de estandarización: la hoja RC, con su ciclo.

Es el documento que dice qué leche se mezcló para llegar al RC de un producto,
y el eslabón que la trazabilidad hacia atrás necesita entre el precondensado y
los silos de leche fresca.

El ciclo viene del flujo de fábrica §10.3–10.4:

    calculado → transferido → agitando → muestreado
                                            ├── conforme → liberado
                                            └── no conforme → corrigiendo → …

La matemática vive en `dominio.py`, sin ORM. Aquí solo está el documento y las
reglas de su ciclo — las que dependen del tiempo y del estado, que el dominio
puro no puede conocer.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from . import dominio


#: Minutos de agitación antes de poder muestrear (§10.3).
#:
#: Es un mínimo físico: una muestra tomada antes mide una mezcla que todavía
#: no es homogénea, y el RC que devuelve no es el del silo. Va como constante
#: con nombre y no como número suelto porque quien lo cambie tiene que saber
#: qué está cambiando.
MINUTOS_DE_AGITACION = 30


class ValeEstandarizacion(models.Model):

    class Estado(models.TextChoices):
        CALCULADO = "calculado", "Calculado"
        TRANSFERIDO = "transferido", "Transferido"
        AGITANDO = "agitando", "En agitación"
        MUESTREADO = "muestreado", "Muestreado"
        CORRIGIENDO = "corrigiendo", "En corrección"
        LIBERADO = "liberado", "Liberado"
        ANULADO = "anulado", "Anulado"

    TRANSICIONES = {
        Estado.CALCULADO: {Estado.TRANSFERIDO, Estado.ANULADO},
        Estado.TRANSFERIDO: {Estado.AGITANDO, Estado.ANULADO},
        Estado.AGITANDO: {Estado.MUESTREADO, Estado.ANULADO},
        # Del muestreo sale conforme (liberado) o no (corrigiendo).
        Estado.MUESTREADO: {Estado.LIBERADO, Estado.CORRIGIENDO, Estado.ANULADO},
        # Corregir es agregar leche y volver a agitar.
        Estado.CORRIGIENDO: {Estado.AGITANDO, Estado.ANULADO},
        Estado.LIBERADO: set(),
        Estado.ANULADO: set(),
    }

    codigo = models.CharField("Código de vale", max_length=40, unique=True)
    fecha = models.DateField("Fecha")

    producto = models.ForeignKey(
        "maestros.Producto", on_delete=models.PROTECT,
        related_name="vales_estandarizacion",
        help_text="El producto al que se estandariza. De él sale el RC objetivo.",
    )
    rc_objetivo = models.DecimalField(
        "RC objetivo", max_digits=6, decimal_places=4,
        help_text="Materia grasa dividida por sólidos no grasos.",
    )
    volumen = models.DecimalField(
        "Volumen a preparar", max_digits=12, decimal_places=2, help_text="En litros"
    )

    silo_entera = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="vales_como_entera"
    )
    silo_descremada = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT,
        related_name="vales_como_descremada", null=True, blank=True,
    )
    silo_destino = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="vales_como_destino"
    )

    # Composición con la que se calculó. Se guarda **en el vale** y no se lee
    # del silo al mirarlo: el silo cambia con cada ingreso, y un vale de mayo
    # tiene que poder auditarse contra la leche que había en mayo. Es el mismo
    # criterio que los límites del PCC en `ControlProceso`.
    entera_grasa = models.DecimalField("Grasa de la entera", max_digits=5, decimal_places=2)
    entera_sng = models.DecimalField("SNG de la entera", max_digits=5, decimal_places=2)
    descremada_grasa = models.DecimalField(
        "Grasa de la descremada", max_digits=5, decimal_places=2
    )
    descremada_sng = models.DecimalField(
        "SNG de la descremada", max_digits=5, decimal_places=2
    )

    litros_entera = models.DecimalField(
        "Litros de entera", max_digits=12, decimal_places=2
    )
    litros_descremada = models.DecimalField(
        "Litros de descremada", max_digits=12, decimal_places=2
    )

    estado = models.CharField(
        "Estado", max_length=20, choices=Estado.choices,
        default=Estado.CALCULADO, db_index=True,
    )
    agitacion_desde = models.DateTimeField(
        "Inicio de la agitación", null=True, blank=True
    )

    # Lo que dio el análisis después de agitar. Nulos hasta que se muestrea.
    grasa_real = models.DecimalField(
        "Grasa medida", max_digits=5, decimal_places=2, null=True, blank=True
    )
    sng_real = models.DecimalField(
        "SNG medido", max_digits=5, decimal_places=2, null=True, blank=True
    )

    observaciones = models.TextField("Observaciones", blank=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="vales_estandarizacion", null=True, blank=True,
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vale de estandarización"
        verbose_name_plural = "Vales de estandarización"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(volumen__gt=0), name="vale_volumen_positivo"
            ),
            models.CheckConstraint(
                condition=models.Q(rc_objetivo__gt=0), name="vale_rc_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.codigo} · RC {self.rc_objetivo}"

    # ------------------------------------------------------------ cálculos

    @property
    def rc_real(self):
        """
        El RC que dio el análisis. Se calcula, no se guarda.

        Un RC almacenado se desincroniza en cuanto alguien corrige la grasa
        mal tecleada, que es justo el número del que depende liberar o no.
        """
        if self.grasa_real is None or not self.sng_real:
            return None

        return float(self.grasa_real) / float(self.sng_real)

    @property
    def minutos_agitando(self):
        """Cuánto lleva agitando. `None` si todavía no empezó."""
        if self.agitacion_desde is None:
            return None

        return (timezone.now() - self.agitacion_desde).total_seconds() / 60

    @property
    def puede_muestrear(self) -> bool:
        """
        Solo después de los 30 minutos. Antes, la mezcla no es homogénea y la
        muestra mide otra cosa.
        """
        minutos = self.minutos_agitando

        return (
            self.estado == self.Estado.AGITANDO
            and minutos is not None
            and minutos >= MINUTOS_DE_AGITACION
        )

    def evaluacion(self):
        """Si el RC medido cumple, y qué agregar si no. Delega en el dominio."""
        if self.grasa_real is None or self.sng_real is None:
            return None

        return dominio.evaluar_rc(
            grasa=float(self.grasa_real),
            sng=float(self.sng_real),
            rc_objetivo=float(self.rc_objetivo),
        )

    # ------------------------------------------------------------- reglas

    def clean(self):
        if self.silo_destino_id and self.silo_destino_id == self.silo_entera_id:
            raise ValidationError({
                "silo_destino": "El destino no puede ser el mismo silo de origen."
            })

        if (
            self.silo_descremada_id
            and self.silo_descremada_id == self.silo_destino_id
        ):
            raise ValidationError({
                "silo_destino": "El destino no puede ser el silo de la descremada."
            })
