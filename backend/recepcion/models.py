"""
Recepción de leche y libro mayor de los silos.

Traducción de las entidades `recepcion` y `movimientoSilo` de
`prototipo/js/modelo/esquema.js`.

La decisión que gobierna este archivo (MODELO_DATOS.md §2.4): **la ocupación
de un silo es un saldo, no un acumulado**. `MovimientoSilo` es el libro mayor
—ingresos por recepción, salidas por consumo de lote, ajustes— y la ocupación
se obtiene sumándolo. No existe un campo `litros_actuales` en `Silo`, y no
debe existir: sería un dato que se desincroniza en cuanto alguien corrija un
movimiento, y un saldo negativo dejaría de ser lo que hoy es, la señal
automática de que el registro está descuadrado.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from usuarios.tenancy import sucursal_predeterminada_pruebas

from maestros.models import Silo, Vehiculo


CONTROLES_DECLARADOS = {
    "temperatura",
    "acidez",
    "ph",
    "delvo",
    "inhibidores",
    "organoleptico",
}

CONTROLES_NUMERICOS = {"temperatura", "acidez", "ph"}

VALORES_ADMITIDOS = {
    "delvo": {"Negativo", "Positivo"},
    "inhibidores": {"Negativo", "Positivo"},
    "organoleptico": {"Conforme", "No conforme"},
}


class Recepcion(models.Model):
    """
    Llegada de un camión.

    Los controles deciden si la leche se libera al silo o se retiene. El
    veredicto NO se guarda: se calcula desde los controles, igual que el
    resultado de calidad de un lote.
    """

    sucursal = models.ForeignKey(
        "usuarios.Sucursal", on_delete=models.PROTECT,
        related_name="recepciones_leche",
        default=sucursal_predeterminada_pruebas,
    )

    class Procedencia(models.TextChoices):
        NESTLE = "Nestlé", "Nestlé"
        P_UNION = "P. Unión", "P. Unión"

    class TipoLeche(models.TextChoices):
        ENTERA = "Entera", "Entera"
        DESCREMADA = "Descremada", "Descremada"

    class Turno(models.TextChoices):
        A = "A", "Turno A"
        B = "B", "Turno B"
        C = "C", "Turno C"

    class Estado(models.TextChoices):
        REGISTRADA = "registrada", "En espera de muestra"
        MUESTREADA = "muestreada", "Muestra tomada"
        ANALIZADA = "analizada", "Analizada"
        LIBERADA = "liberada", "Aprobada por Calidad"
        RETENIDA = "retenida", "Retenida"
        DESCARGADA = "descargada", "Descargada"
        CERRADA = "cerrada", "Cerrada"

    # Transiciones válidas, tal como las declara el esquema del prototipo.
    # Una retenida puede liberarse tras reanálisis, o cerrarse rechazada.
    TRANSICIONES = {
        Estado.REGISTRADA: [Estado.MUESTREADA, Estado.CERRADA],
        Estado.MUESTREADA: [Estado.ANALIZADA],
        Estado.ANALIZADA: [Estado.LIBERADA, Estado.RETENIDA],
        Estado.LIBERADA: [Estado.DESCARGADA],
        Estado.RETENIDA: [Estado.LIBERADA, Estado.CERRADA],
        Estado.DESCARGADA: [Estado.CERRADA],
        Estado.CERRADA: [],
    }

    fecha = models.DateField("Fecha")
    hora = models.TimeField("Hora", null=True, blank=True)
    guia = models.CharField("Guía", max_length=60, blank=True)
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.PROTECT,
        related_name="recepciones",
        null=True,
        blank=True,
        verbose_name="Camión",
    )
    procedencia = models.CharField(
        "Procedencia", max_length=20, choices=Procedencia.choices, blank=True
    )
    tipo_leche = models.CharField(
        "Tipo de leche", max_length=20, choices=TipoLeche.choices
    )
    litros = models.DecimalField("Litros", max_digits=12, decimal_places=2)
    silo = models.ForeignKey(
        Silo,
        on_delete=models.PROTECT,
        related_name="recepciones",
        null=True,
        blank=True,
        verbose_name="Silo de destino",
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recepciones",
        null=True,
        blank=True,
        verbose_name="Operador",
    )
    turno = models.CharField("Turno", max_length=5, choices=Turno.choices, blank=True)
    controles = models.JSONField(
        "Controles del camión",
        default=dict,
        blank=True,
        help_text='{"delvo": "Negativo", "acidez": 16.5, "ph": 6.7, ...}',
    )
    estado = models.CharField(
        "Estado", max_length=20, choices=Estado.choices, default=Estado.REGISTRADA
    )
    motivo = models.TextField(
        "Motivo", blank=True, help_text="Obligatorio si la recepción se retiene"
    )
    observacion = models.TextField("Observación", blank=True)
    codigo_muestra = models.CharField("Código de muestra", max_length=80, blank=True)
    muestreado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="muestras_recepcion_tomadas",
        null=True,
        blank=True,
        verbose_name="Muestreado por",
    )
    muestreado_en = models.DateTimeField("Fecha y hora de muestreo", null=True, blank=True)
    calidad_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="decisiones_calidad_recepcion",
        null=True,
        blank=True,
        verbose_name="Decisión de calidad por",
    )
    calidad_en = models.DateTimeField("Fecha y hora de decisión", null=True, blank=True)
    silo_asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="silos_recepcion_asignados",
        null=True,
        blank=True,
        verbose_name="Silo asignado por",
    )
    silo_asignado_en = models.DateTimeField("Fecha y hora de asignación", null=True, blank=True)

    class Meta:
        verbose_name = "Recepción de leche"
        verbose_name_plural = "Recepciones de leche"
        ordering = ["-fecha", "-hora"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros__gte=0), name="recepcion_litros_no_negativos"
            ),
            models.UniqueConstraint(
                fields=["codigo_muestra"],
                condition=~models.Q(codigo_muestra=""),
                name="codigo_muestra_recepcion_unico",
            ),
        ]

    def __str__(self):
        return f"{self.fecha} · {self.litros} L · {self.silo or 'sin silo'}"

    @property
    def diferencia_recoleccion_litros(self):
        """
        Litros del camión contra lo que Recolección esperaba.

        Compara contra la **suma** de las cargas de los módulos: la carga de
        recolección es por módulo y los litros son del camión. Sin ninguna
        carga vinculada devuelve None, que no es lo mismo que una diferencia
        de cero.
        """
        cargas = [
            modulo.carga_recoleccion
            for modulo in self.modulos.all()
            if modulo.carga_recoleccion_id
        ]

        if not cargas:
            return None

        return self.litros - sum(carga.litros for carga in cargas)

    def clean(self):
        if not isinstance(self.controles, dict):
            raise ValidationError({"controles": "Debe ser un objeto de controles."})

        desconocidos = set(self.controles) - CONTROLES_DECLARADOS
        if desconocidos:
            raise ValidationError(
                {"controles": f"Controles no reconocidos: {', '.join(sorted(desconocidos))}"}
            )

        for clave, valor in self.controles.items():
            if valor in (None, ""):
                continue

            if clave in CONTROLES_NUMERICOS and not isinstance(valor, (int, float)):
                raise ValidationError(
                    {"controles": f"El valor de '{clave}' debe ser numérico."}
                )

            admitidos = VALORES_ADMITIDOS.get(clave)
            if admitidos and valor not in admitidos:
                raise ValidationError(
                    {
                        "controles": (
                            f"'{clave}' admite {' o '.join(sorted(admitidos))}, "
                            f"no '{valor}'."
                        )
                    }
                )

        # Retener sin decir por qué deja el registro sin valor para auditar.
        if self.estado == self.Estado.RETENIDA and not self.motivo.strip():
            raise ValidationError(
                {"motivo": "Una recepción retenida debe indicar el motivo."}
            )

    def puede_pasar_a(self, estado) -> bool:
        return estado in self.TRANSICIONES.get(self.estado, [])


class ModuloRecepcion(models.Model):
    """
    Un compartimiento del camión.

    Lo único que se mide por módulo es la crioscopía: el formato la anota en
    las columnas M1 a M4 de la misma fila. Los litros, el silo y el destino
    son del camión, así que no están aquí — ponerlos abriría la puerta a que
    dos módulos del mismo camión declararan silos distintos.
    """

    recepcion = models.ForeignKey(
        Recepcion,
        on_delete=models.CASCADE,
        related_name="modulos",
        verbose_name="Recepción",
    )
    numero = models.PositiveSmallIntegerField(
        "Módulo",
        help_text="1 a 4, como las columnas M1-M4 del formato",
    )
    crioscopia = models.DecimalField(
        "Crioscopía",
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
        help_text="Un valor MENOS negativo que el límite sugiere agua añadida",
    )
    carga_recoleccion = models.ForeignKey(
        "recoleccion.CargaModulo",
        on_delete=models.PROTECT,
        related_name="modulos_recepcion",
        null=True,
        blank=True,
        verbose_name="Carga esperada de Recolección",
    )

    class Meta:
        verbose_name = "Módulo de la recepción"
        verbose_name_plural = "Módulos de la recepción"
        ordering = ["recepcion", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["recepcion", "numero"], name="modulo_unico_por_recepcion"
            ),
            models.CheckConstraint(
                condition=models.Q(numero__gte=1), name="modulo_numero_positivo"
            ),
        ]

    def __str__(self):
        return f"{self.recepcion_id} · M{self.numero}"


class MovimientoSilo(models.Model):
    """
    Un asiento del libro mayor de un silo.

    Nunca se edita la ocupación: se agrega un movimiento. Un error se corrige
    con un ajuste que deja rastro, no borrando el histórico.
    """

    class Tipo(models.TextChoices):
        INGRESO = "ingreso", "Ingreso"
        SALIDA = "salida", "Salida"
        AJUSTE = "ajuste", "Ajuste"

    class OrigenTipo(models.TextChoices):
        RECEPCION = "recepcion", "Recepción"
        ESTANDARIZACION = "estandarizacion", "Estandarización"
        LOTE = "lote", "Consumo de lote"
        TRANSFERENCIA = "transferencia", "Transferencia"
        PRODUCCION = "produccion", "Producción"
        MERMA = "merma", "Merma"
        DEVOLUCION = "devolucion", "Devolución"
        REWORK = "rework", "Reproceso"
        AJUSTE = "ajuste", "Ajuste manual"

    silo = models.ForeignKey(
        Silo, on_delete=models.PROTECT, related_name="movimientos", verbose_name="Silo"
    )
    tipo = models.CharField("Tipo", max_length=20, choices=Tipo.choices)
    # Los ajustes pueden ser negativos: corrigen en cualquier dirección.
    litros = models.DecimalField("Litros", max_digits=12, decimal_places=2)
    fecha_hora = models.DateTimeField("Fecha y hora")
    origen_tipo = models.CharField(
        "Origen", max_length=20, choices=OrigenTipo.choices, blank=True
    )
    origen_id = models.PositiveIntegerField(
        "Registro de origen",
        null=True,
        blank=True,
        help_text="Id de la recepción o del lote que provocó el movimiento",
    )
    motivo = models.TextField(
        "Motivo", blank=True, help_text="Obligatorio en los ajustes"
    )
    operacion_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text="Clave idempotente compartida por los asientos de una operación.",
    )
    silo_contraparte = models.ForeignKey(
        Silo, on_delete=models.PROTECT, related_name="movimientos_contraparte",
        null=True, blank=True,
    )
    lote = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT,
        related_name="movimientos_silo", null=True, blank=True,
    )
    producto = models.ForeignKey(
        "maestros.Producto", on_delete=models.PROTECT,
        related_name="movimientos_silo", null=True, blank=True,
    )
    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT,
        related_name="movimientos_silo", null=True, blank=True,
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="movimientos_silo", null=True, blank=True,
    )

    class Meta:
        verbose_name = "Movimiento de silo"
        verbose_name_plural = "Movimientos de silo"
        ordering = ["-fecha_hora"]
        indexes = [models.Index(fields=["silo", "fecha_hora"])]
        constraints = [
            models.UniqueConstraint(
                fields=["origen_tipo", "origen_id"],
                condition=models.Q(origen_tipo="recepcion"),
                name="una_descarga_por_recepcion",
            ),
            models.UniqueConstraint(
                fields=["operacion_id", "silo", "tipo"],
                condition=models.Q(operacion_id__isnull=False),
                name="asiento_silo_unico_por_operacion",
            ),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.litros} L · {self.silo}"

    def clean(self):
        if self.tipo != self.Tipo.AJUSTE and self.litros is not None and self.litros < 0:
            raise ValidationError(
                {"litros": "Solo los ajustes pueden ser negativos."}
            )

        if self.tipo == self.Tipo.AJUSTE and not self.motivo.strip():
            raise ValidationError(
                {"motivo": "Un ajuste debe indicar el motivo: es lo que lo hace auditable."}
            )

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(
                "Los movimientos de silo son inmutables; corrige mediante un ajuste o reversa."
            )
        return super().save(*args, **kwargs)
