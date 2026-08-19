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


#: Minutos de agitación que pide el procedimiento antes de muestrear (§10.3).
#:
#: Es un mínimo físico: una muestra tomada antes mide una mezcla que todavía no
#: es homogénea, y el RC que devuelve no es el del silo.
#:
#: **Avisa, no bloquea** desde 2026-08-17, por decisión de planta: el sistema
#: advierte y deja constancia en `muestreado_en`, pero no detiene la operación.
#: Antes rechazaba la muestra, y entonces no quedaba registro de nada; ahora no
#: la impide pero sí queda escrito cuánto agitó cada vale.
#:
#: Constante con nombre y no un número suelto en medio del cálculo: quien lo
#: cambie tiene que saber qué está cambiando, y no se toca ni se hace
#: configurable.
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

    # De dónde salieron los cuatro números de arriba. Es **procedencia**, no
    # fuente de verdad: la composición sigue congelada en las columnas del
    # vale, porque el análisis se puede corregir y un vale de mayo tiene que
    # seguir auditándose contra lo que se usó en mayo. Sin estas dos claves,
    # «4,35» era un número tecleado sin origen.
    #
    # Los `related_name` **no** son `vales_como_entera` / `vales_como_descremada`:
    # esos ya los usan `silo_entera` y `silo_descremada` sobre `maestros.Silo`.
    # Django lo permitiría —el modelo de destino es otro— pero dos accesores
    # con el mismo nombre devolviendo cosas distintas no hay forma de leerlos.
    analisis_entera = models.ForeignKey(
        "recepcion.AnalisisSilo", on_delete=models.PROTECT,
        related_name="vales_con_esta_entera", null=True, blank=True,
        verbose_name="Análisis de la entera",
    )
    analisis_descremada = models.ForeignKey(
        "recepcion.AnalisisSilo", on_delete=models.PROTECT,
        related_name="vales_con_esta_descremada", null=True, blank=True,
        verbose_name="Análisis de la descremada",
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
    muestreado_en = models.DateTimeField(
        "Hora del muestreo", null=True, blank=True,
        help_text=(
            "Cuándo se tomó la muestra. Congela «minutos agitando»: sin este "
            "sello el contador sigue creciendo contra el reloj actual y "
            "después no hay forma de saber si la muestra fue temprana."
        ),
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
        """
        Cuánto agitó. Mientras no se muestrea cuenta contra el reloj actual;
        una vez muestreado se congela en la hora de la muestra.

        Congelarlo es lo que hace auditable el aviso de muestreo temprano: sin
        el sello, un vale mirado al día siguiente informa mil cuatrocientos
        minutos y el aviso ya no se puede contrastar con nada.
        """
        if self.agitacion_desde is None:
            return None

        hasta = self.muestreado_en or timezone.now()

        return (hasta - self.agitacion_desde).total_seconds() / 60

    @property
    def avisos_de_muestreo(self) -> list[str]:
        """
        Qué advertir sobre la agitación. Lista vacía: nada que advertir.

        **Avisa, no bloquea** (decisión de planta, 2026-08-17). Antes de los
        treinta minutos la mezcla no es homogénea y el RC medido puede no ser
        el del silo, pero detener la operación por eso lo decide la planta y no
        el sistema. Mismo criterio que `codigo_lote_valido` y que la leche
        asignada del lote, que avisan sin frenar.

        Sirve en los dos momentos sin ramificar, porque se apoya en
        `minutos_agitando`: **antes** de muestrear cuenta contra el reloj actual
        y dice cuánto lleva; **después** cuenta contra `muestreado_en` y dice a
        los cuántos minutos se muestreó. Es la misma frase leída en dos
        instantes, no dos cálculos.

        Devuelve motivos y no un booleano porque un `False` no le dice al
        operador qué pasó, y es la convención del resto del proyecto.
        """
        minutos = self.minutos_agitando

        # Sin reloj arrancado no hay nada que advertir: muestrear sin agitar ya
        # lo impide la transición de estado.
        if minutos is None or minutos >= MINUTOS_DE_AGITACION:
            return []

        return [
            f"Agitó {int(minutos)} minutos de los {MINUTOS_DE_AGITACION} que "
            "pide el procedimiento: antes de eso la mezcla no es homogénea y "
            "la muestra puede no medir el silo."
        ]

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
