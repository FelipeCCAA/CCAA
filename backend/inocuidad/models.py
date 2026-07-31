"""
Capa de inocuidad: monitoreo de PPRO y PCC.

Por qué una app propia y no `produccion`: aquí vive lo que el sistema FSSC
22000 exige vigilar, y va a crecer con lo que el levantamiento ya identificó
—limpieza CIP/COP, no conformidades, calibración de instrumentos—. Mover
modelos entre apps de Django después es caro (obliga a renombrar tablas con
migraciones a mano), así que la separación se hace ahora, con dos modelos,
en vez de cuando haya seis.

`ControlProceso` se queda en `produccion` a propósito, aunque lleve el PCC 1:
es el registro de **cómo se produjo** —flujos, densidades, temperaturas— y el
límite crítico es un dato más dentro de él. Lo de aquí, en cambio, no mide
producción: son chequeos de inocuidad que solo existen para vigilar un
peligro.

Lo que no está todavía, y es lo siguiente: las dos reglas de bloqueo en
`calidad/dominio.py` —que un PPRO con lecturas No-OK sin acción correctiva
impida liberar el lote— con sus pruebas de regresión.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class MonitoreoPPRO(models.Model):
    """
    Monitoreo de un PPRO o PCC para un lote y turno.

    Origen: CCAA.Sec.FORM.022/007 y CCAA.ENV.FORM.001/003. Cubre presión de
    aire, roce de válvulas, cuerpos extraños y el detector de metales, que es
    un PCC.

    El detalle horario vive en `PproLectura`. La cabecera guarda la acción
    correctiva, que es lo que convierte un No-OK en un incidente resuelto:
    sin ella, el registro dice que algo falló y no dice qué se hizo.
    """

    class Tipo(models.TextChoices):
        AIRE_TRANSPORTE = "aire_transporte", "Presión aire transporte fluidizado"
        AIRE_SECUNDARIO = "aire_secundario", "Presión aire secundario"
        ROCE_VALVULAS = "roce_valvulas", "Roce válvulas fluidificadoras"
        CUERPOS_EXTRANOS = "cuerpos_extranos", "Cuerpos extraños"
        DETECTOR_METALES = "detector_metales", "Detector de metales (PCC)"

    lote = models.ForeignKey(
        "produccion.Lote",
        on_delete=models.CASCADE,
        related_name="monitoreos_ppro",
        verbose_name="Lote",
    )
    tipo = models.CharField("Tipo de PPRO", max_length=30, choices=Tipo.choices)
    equipo = models.CharField(
        "Equipo",
        max_length=20,
        blank=True,
        help_text="E1/E2, Rovema 3/4, etc.",
    )
    turno = models.CharField(
        "Turno",
        max_length=5,
        choices=[("A", "Turno A"), ("B", "Turno B"), ("C", "Turno C")],
        blank=True,
    )
    fecha = models.DateField("Fecha")
    accion_correctiva = models.TextField(
        "Acción correctiva",
        blank=True,
        help_text="Obligatoria si hubo alguna lectura No-OK",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="monitoreos_ppro",
        null=True,
        blank=True,
        verbose_name="Operador",
    )

    class Meta:
        verbose_name = "Monitoreo PPRO"
        verbose_name_plural = "Monitoreos PPRO"
        ordering = ["-fecha", "tipo"]
        constraints = [
            # Un monitoreo por lote, tipo, equipo, fecha y turno. Dos cabeceras
            # del mismo chequeo partirían las lecturas y la regla de bloqueo
            # miraría solo la mitad.
            models.UniqueConstraint(
                fields=["lote", "tipo", "equipo", "fecha", "turno"],
                name="monitoreo_ppro_unico_por_turno",
            )
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.lote.codigo_lote} · {self.fecha}"

    @property
    def tiene_no_ok(self) -> bool:
        """
        ¿Alguna lectura salió No-OK? Se calcula, no se guarda.

        Recorre `lecturas.all()` en vez de filtrar en la base para que un
        `prefetch_related("lecturas")` lo resuelva sin consultar: la
        liberación evalúa esto por cada monitoreo del lote, y un `.filter()`
        ignora el prefetch y dispara una consulta cada vez.
        """
        return any(
            lectura.resultado == PproLectura.Resultado.NO_OK
            for lectura in self.lecturas.all()
        )

    @property
    def resuelto(self) -> bool:
        """
        Un No-OK sin acción correctiva escrita es un incidente abierto, y es
        lo que debe bloquear la liberación del lote.
        """
        return not self.tiene_no_ok or bool(self.accion_correctiva.strip())


class PproLectura(models.Model):
    """
    Lectura horaria de un monitoreo.

    El resultado es OK o No-OK y nada más: así se registra en planta, y
    admitir un tercer valor invitaría a usarlo para evitar la acción
    correctiva que un No-OK exige.
    """

    class Resultado(models.TextChoices):
        OK = "ok", "OK"
        NO_OK = "no_ok", "No OK"

    monitoreo = models.ForeignKey(
        MonitoreoPPRO,
        on_delete=models.CASCADE,
        related_name="lecturas",
        verbose_name="Monitoreo",
    )
    hora = models.TimeField("Hora")
    resultado = models.CharField("Resultado", max_length=6, choices=Resultado.choices)
    detalle = models.JSONField(
        "Detalle",
        default=dict,
        blank=True,
        help_text='Para el detector de metales: {"rechazos": 2, "alarmas": 1}',
    )

    class Meta:
        verbose_name = "Lectura PPRO"
        verbose_name_plural = "Lecturas PPRO"
        ordering = ["hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["monitoreo", "hora"],
                name="lectura_ppro_unica_por_hora",
            )
        ]

    def __str__(self):
        return f"{self.hora} · {self.get_resultado_display()}"

    def clean(self):
        if not isinstance(self.detalle, dict):
            raise ValidationError({"detalle": "Debe ser un objeto de valores."})

        for clave, valor in self.detalle.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise ValidationError(
                    {"detalle": f"El valor de '{clave}' debe ser numérico."}
                )
