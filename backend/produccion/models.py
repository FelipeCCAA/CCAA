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

from django.conf import settings
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


class Equipo(models.TextChoices):
    """
    Equipos que registran control de proceso.

    Provisional como `choices`. El backlog prevé un maestro `Equipo` con sus
    límites críticos por producto (P1 #11); mientras eso no exista, los
    límites viajan en cada `ControlProceso` y esta lista basta.
    """

    VEB = "VEB", "Evaporador VEB"
    SCH2 = "SCH2", "Evaporador Scheffers 2"
    SCH3 = "SCH3", "Evaporador Scheffers 3"
    E1 = "E1", "Torre de secado Egron 1"
    E2 = "E2", "Torre de secado Egron 2"


class ControlProceso(models.Model):
    """
    Control de proceso de un equipo para un lote: condensación o secado.

    Traducción de los formatos de planta CCAA.Cond.FORM.001/006/010–012 y
    CCAA.Sec.FORM.002/025/026. La cabecera va aquí y el detalle horario en
    `ControlProcesoLectura`, que es el mismo patrón que `Recepcion` y
    `MovimientoSilo`: un registro y su libro.

    Reúne el **PCC 1 de uperización**, que es lo que hace de este modelo un
    registro de inocuidad y no solo de producción. Los límites (temperatura
    mínima, caudal máximo) se guardan **por registro** y no en un maestro
    porque cambian por equipo y por producto: el VEB trabaja a 80,0 °C y
    14.175 kg/h, el Scheffers 2 a 81,2 °C y 17.100 kg/h.

    Lo que NO se guarda es si el control cumplió: eso se recalcula desde las
    lecturas, igual que el resultado de calidad de un lote (MODELO_DATOS.md
    §2.2). Guardarlo dejaría un veredicto que se desincroniza en cuanto
    alguien corrige una lectura mal tecleada.
    """

    lote = models.ForeignKey(
        Lote,
        on_delete=models.CASCADE,
        related_name="controles_proceso",
        verbose_name="Lote",
    )
    equipo = models.CharField("Equipo", max_length=10, choices=Equipo.choices)
    turno = models.CharField("Turno", max_length=5, choices=Lote.Turno.choices, blank=True)
    fecha = models.DateField("Fecha")

    hora_arranque = models.TimeField("Hora de arranque", null=True, blank=True)
    hora_inicio_produccion = models.TimeField(
        "Inicio de producción", null=True, blank=True
    )
    hora_termino_produccion = models.TimeField(
        "Término de producción", null=True, blank=True
    )

    # PCC 1 · Uperización. Los límites del formato, para poder auditar cada
    # lectura contra lo que regía ese día y no contra lo que rige hoy.
    pcc1_temp_min = models.DecimalField(
        "PCC1 · Temperatura mínima",
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="En °C. Una lectura por debajo incumple el PCC",
    )
    pcc1_caudal_max = models.DecimalField(
        "PCC1 · Caudal máximo",
        max_digits=10,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="En kg/h. Una lectura por encima incumple el PCC",
    )

    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="controles_proceso",
        null=True,
        blank=True,
        verbose_name="Operador",
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Control de proceso"
        verbose_name_plural = "Controles de proceso"
        ordering = ["-fecha", "equipo"]
        constraints = [
            # Un equipo lleva un control por lote, fecha y turno. Sin esto, dos
            # cabeceras del mismo turno partirían las lecturas en dos y el
            # cumplimiento del PCC se evaluaría sobre la mitad de los datos.
            models.UniqueConstraint(
                fields=["lote", "equipo", "fecha", "turno"],
                name="control_proceso_unico_por_lote_equipo_fecha_turno",
            )
        ]

    def __str__(self):
        return f"Control {self.equipo} · {self.lote.codigo_lote} · {self.fecha}"

    def clean(self):
        if (
            self.hora_inicio_produccion is not None
            and self.hora_termino_produccion is not None
            and self.hora_termino_produccion == self.hora_inicio_produccion
        ):
            raise ValidationError(
                {
                    "hora_termino_produccion": (
                        "No puede ser igual a la hora de inicio."
                    )
                }
            )


class ControlProcesoLectura(models.Model):
    """
    Una lectura horaria de un control de proceso.

    Los parámetros medidos cambian por equipo —el VEB no mide lo mismo que la
    torre Egron—, así que van como JSON igual que `Analisis.valores`. Poner
    una columna por parámetro obligaría a migrar la base cada vez que un
    formato de planta agrega una medición.
    """

    control = models.ForeignKey(
        ControlProceso,
        on_delete=models.CASCADE,
        related_name="lecturas",
        verbose_name="Control de proceso",
    )
    hora = models.TimeField("Hora")
    valores = models.JSONField(
        "Valores medidos",
        default=dict,
        help_text='{"flujo_entrada": 13500, "densidad": 1020, "t_dsi": 82.1, ...}',
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Lectura de control de proceso"
        verbose_name_plural = "Lecturas de control de proceso"
        ordering = ["hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["control", "hora"],
                name="lectura_control_unica_por_hora",
            )
        ]

    def __str__(self):
        return f"{self.control.equipo} · {self.hora}"

    def clean(self):
        if not isinstance(self.valores, dict):
            raise ValidationError({"valores": "Debe ser un objeto de valores medidos."})

        for parametro, valor in self.valores.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise ValidationError(
                    {"valores": f"El valor de '{parametro}' debe ser numérico."}
                )
