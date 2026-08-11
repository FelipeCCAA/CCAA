"""
Planificación semanal de producción.

Traducción de `prototipo/PLANIFICADOR.md` y de las entidades `semanaPlan`,
`codigoProduccion`, `bloquePlan` y `balanceDia` de `esquema.js`. Reproduce lo
que hoy se hace a mano en el Excel `Programa Campos Australes W7.xlsx`.

Lo que hay que preservar, y que es la razón de ser de la herramienta: **el
programa horario y el balance de leche están acoplados**. La grilla de
equipos × horas *genera* el consumo del balance; no son dos tablas
independientes. Mover un bloque de evaporador recalcula el stock proyectado
del resto de la semana.

De ahí la ausencia deliberada más importante: `BalanceDia` guarda **solo lo
que se teclea** —stock inicial, recepciones esperadas, trasvasije— y nunca el
consumo ni los saldos. Persistirlos los congelaría, y el plan mentiría en
cuanto alguien corriera un bloque media hora (mismo principio que
MODELO_DATOS.md §2.2).
"""

from django.core.exceptions import ValidationError
from django.db import models
from usuarios.tenancy import sucursal_predeterminada_pruebas

from maestros.models import Equipo, Mandante, Producto


class CategoriaConsumo(models.TextChoices):
    """Las filas de CONSUMO del balance."""

    PREC_NESTLE = "prec_nestle", "Precondensado Nestlé"
    PREC_CCAA = "prec_ccaa", "Precondensado CCAA"
    SECADO_CCAA = "secado_ccaa", "Secado CCAA"
    SECADO_NESTLE = "secado_nestle", "Secado Nestlé"
    SECADO_COLUN = "secado_colun", "Secado Colún"


class EstadoEquipo(models.TextChoices):
    """Leyenda de la hoja BD: qué pasa en un equipo cuando no produce."""

    ASEO = "A", "Aseo"
    PNP = "P", "PNP"
    MANTENIMIENTO = "M", "Mantenimiento"
    PREPARACION = "X", "Preparación"
    ATRASO_PARTIDA = "AP", "Atraso de partida"


class CodigoProduccion(models.Model):
    """
    Receta programable: qué se produce, dónde, y cuánta leche consume por hora.

    Origen: la hoja `BD` del Excel. Es el maestro que convierte una franja de
    la grilla en litros: horas × `rendimiento_lh`.

    No duplica el catálogo de productos — lo referencia. Un código es una
    *forma de programar* un producto en un equipo concreto, no un producto
    nuevo.
    """

    class Formato(models.TextChoices):
        SH2 = "SH2", "Scheffers 2"
        SH3 = "SH3", "Scheffers 3"
        VEB = "VEB", "VEB"

    codigo = models.CharField("Código", max_length=20, unique=True)
    nombre = models.CharField("Nombre", max_length=150, blank=True)
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="codigos_produccion",
        null=True,
        blank=True,
        verbose_name="Producto",
    )
    mandante = models.ForeignKey(
        Mandante,
        on_delete=models.PROTECT,
        related_name="codigos_produccion",
        null=True,
        blank=True,
        verbose_name="Mandante",
    )
    formato = models.CharField(
        "Formato", max_length=5, choices=Formato.choices, blank=True
    )
    categoria = models.CharField(
        "Categoría de consumo",
        max_length=20,
        choices=CategoriaConsumo.choices,
        help_text="A qué fila de CONSUMO del balance suma",
    )
    rendimiento_lh = models.DecimalField(
        "Rendimiento",
        max_digits=12,
        decimal_places=2,
        help_text="Litros de leche por hora de corrida (columna C de la hoja BD)",
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Código de producción"
        verbose_name_plural = "Códigos de producción"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rendimiento_lh__gte=0),
                name="codigo_produccion_rendimiento_no_negativo",
            )
        ]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}" if self.nombre else self.codigo


class SemanaPlan(models.Model):
    """
    Cabecera de una semana programada.

    El estado gobierna qué se puede tocar: en `borrador` se arma, al
    `publicar` queda comprometida con planta, y `cerrada` es histórico contra
    el que se contrasta lo que realmente se produjo.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PUBLICADA = "publicada", "Publicada"
        CERRADA = "cerrada", "Cerrada"

    sucursal = models.ForeignKey(
        "usuarios.Sucursal", on_delete=models.PROTECT,
        related_name="semanas_planificacion",
        default=sucursal_predeterminada_pruebas,
    )

    TRANSICIONES = {
        Estado.BORRADOR: [Estado.PUBLICADA],
        # Volver a borrador existe porque el programa cambia: se rompe una
        # máquina y hay que reprogramar la semana en curso.
        Estado.PUBLICADA: [Estado.BORRADOR, Estado.CERRADA],
        Estado.CERRADA: [],
    }

    codigo = models.CharField("Código", max_length=10, help_text="Ej. W7")
    anio = models.PositiveIntegerField("Año")
    fecha_inicio = models.DateField("Lunes de la semana")
    estado = models.CharField(
        "Estado", max_length=10, choices=Estado.choices, default=Estado.BORRADOR
    )
    publicada_por = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        related_name="semanas_publicadas",
        null=True,
        blank=True,
        verbose_name="Publicada por",
    )
    publicada_en = models.DateTimeField("Publicada en", null=True, blank=True)
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Semana de planificación"
        verbose_name_plural = "Semanas de planificación"
        ordering = ["-anio", "-fecha_inicio"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo", "anio"], name="semana_plan_unica_por_anio"
            )
        ]

    def __str__(self):
        return f"{self.codigo} · {self.anio}"

    def clean(self):
        # El lunes es el ancla de toda la semana: los bloques y el balance se
        # ubican por número de día desde ahí.
        if self.fecha_inicio and self.fecha_inicio.weekday() != 0:
            raise ValidationError(
                {"fecha_inicio": "Debe ser un lunes: es el primer día de la semana."}
            )

    def puede_pasar_a(self, estado: str) -> bool:
        return estado in self.TRANSICIONES.get(self.estado, [])

    def fecha_del_dia(self, dia: int):
        """Fecha real de un día de la semana (0 = lunes)."""
        from datetime import timedelta

        return self.fecha_inicio + timedelta(days=dia)


class BloquePlan(models.Model):
    """
    Una corrida programada: un tramo de horas en un equipo.

    Sustituye a las celdas pintadas del Excel por un intervalo explícito. Es
    lo que el propio PLANIFICADOR.md pide no replicar: 156 columnas de grilla
    en el modelo serían un infierno de celdas.

    Las horas van como decimal para admitir medias horas (8.5 = 08:30), que
    es como se programa en planta.
    """

    class Tipo(models.TextChoices):
        PRODUCCION = "produccion", "Producción"
        ESTADO = "estado", "Estado del equipo"

    semana = models.ForeignKey(
        SemanaPlan,
        on_delete=models.CASCADE,
        related_name="bloques",
        verbose_name="Semana",
    )
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.PROTECT,
        related_name="bloques",
        verbose_name="Equipo",
    )
    dia = models.PositiveSmallIntegerField(
        "Día", help_text="0 = lunes … 6 = domingo"
    )
    hora_inicio = models.DecimalField("Hora de inicio", max_digits=4, decimal_places=2)
    hora_fin = models.DecimalField("Hora de término", max_digits=4, decimal_places=2)
    tipo = models.CharField("Tipo", max_length=12, choices=Tipo.choices)
    codigo = models.ForeignKey(
        CodigoProduccion,
        on_delete=models.PROTECT,
        related_name="bloques",
        null=True,
        blank=True,
        verbose_name="Código de producción",
    )
    estado_equipo = models.CharField(
        "Estado del equipo", max_length=3, choices=EstadoEquipo.choices, blank=True
    )
    cantidad_kg = models.DecimalField(
        "Kilos objetivo", max_digits=12, decimal_places=2, null=True, blank=True
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Bloque de programa"
        verbose_name_plural = "Bloques de programa"
        ordering = ["dia", "equipo", "hora_inicio"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(dia__gte=0) & models.Q(dia__lte=6),
                name="bloque_plan_dia_de_la_semana",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_inicio__gte=0) & models.Q(hora_inicio__lte=24),
                name="bloque_plan_hora_inicio_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_fin__gte=0) & models.Q(hora_fin__lte=24),
                name="bloque_plan_hora_fin_valida",
            ),
            models.CheckConstraint(
                condition=models.Q(hora_fin__gt=models.F("hora_inicio")),
                name="bloque_plan_termina_despues_de_empezar",
            ),
        ]

    def __str__(self):
        etiqueta = self.codigo.codigo if self.codigo else self.estado_equipo
        return f"{self.equipo} · día {self.dia} · {etiqueta}"

    @property
    def horas(self) -> float:
        return float(self.hora_fin) - float(self.hora_inicio)

    @property
    def consume_leche(self) -> bool:
        """
        Solo los evaporadores restan del balance (PLANIFICADOR.md §4.1).

        Quién es evaporador lo dice el maestro de equipos, no una lista en el
        código: un mismo código de producción se programa en el evaporador y
        en la línea que lo recibe, y si los dos restaran, el balance contaría
        la misma leche dos veces.
        """
        return (
            self.tipo == self.Tipo.PRODUCCION
            and self.equipo_id is not None
            and self.equipo.consume_leche
        )

    def clean(self):
        # La coherencia tipo ↔ contenido: un bloque de producción sin código
        # no dice qué se produce, y uno de estado sin estado no dice qué pasa.
        if self.tipo == self.Tipo.PRODUCCION and self.codigo_id is None:
            raise ValidationError(
                {"codigo": "Un bloque de producción debe decir qué código produce."}
            )

        if self.tipo == self.Tipo.ESTADO and not self.estado_equipo:
            raise ValidationError(
                {"estado_equipo": "Un bloque de estado debe decir qué pasa en el equipo."}
            )

        if self.tipo == self.Tipo.ESTADO and self.codigo_id is not None:
            raise ValidationError(
                {"codigo": "Un bloque de estado no produce: no lleva código."}
            )
        if self.semana_id and self.equipo_id and self.semana.sucursal_id != self.equipo.sucursal_id:
            raise ValidationError({"equipo": "El equipo debe pertenecer a la sucursal de la semana."})
        if self.codigo_id and self.codigo.producto_id:
            if self.codigo.producto.mandante.empresa_id != self.semana.sucursal.empresa_id:
                raise ValidationError({"codigo": "El código debe pertenecer a la empresa de la semana."})


class BalanceDia(models.Model):
    """
    Lo que se teclea del balance de leche de un día. Nada más.

    El consumo, el total disponible y el stock final son **derivados** y se
    calculan en `dominio.py`. Guardarlos los congelaría: bastaría mover un
    bloque de evaporador para que el número guardado dejara de ser cierto sin
    que nadie lo note.

    `stock_inicial` solo se teclea el primer día; el resto se arrastra del
    día anterior.
    """

    semana = models.ForeignKey(
        SemanaPlan,
        on_delete=models.CASCADE,
        related_name="balances",
        verbose_name="Semana",
    )
    dia = models.PositiveSmallIntegerField("Día", help_text="0 = lunes … 6 = domingo")

    stock_inicial = models.DecimalField(
        "Stock a las 8 AM",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Solo el del primer día; los demás se arrastran",
    )

    # Recepciones ESPERADAS. El plan se hace contra la leche que se calcula
    # que va a llegar, no contra la que ya llegó: por eso son un dato del
    # plan y no se leen de Recepción.
    recepcion_ccaa = models.DecimalField(
        "Recepción CCAA", max_digits=12, decimal_places=2, default=0
    )
    recepcion_nestle = models.DecimalField(
        "Recepción Nestlé", max_digits=12, decimal_places=2, default=0
    )
    recepcion_punion = models.DecimalField(
        "Recepción P. Unión", max_digits=12, decimal_places=2, default=0
    )

    trasvasije = models.DecimalField(
        "Trasvasije",
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Traspaso puntual. No sale de ningún bloque: se teclea",
    )
    crema_disponible_ton = models.DecimalField(
        "Crema disponible",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="En toneladas",
    )
    ajustes = models.JSONField(
        "Ajustes por origen",
        default=dict,
        blank=True,
        help_text='Correcciones puntuales en litros: {"ccaa": -5800, "nestle": 40040}',
    )
    observacion = models.TextField("Observación", blank=True)

    class Meta:
        verbose_name = "Balance de leche del día"
        verbose_name_plural = "Balances de leche"
        ordering = ["semana", "dia"]
        constraints = [
            models.UniqueConstraint(
                fields=["semana", "dia"], name="balance_dia_unico_por_semana"
            ),
            models.CheckConstraint(
                condition=models.Q(dia__gte=0) & models.Q(dia__lte=6),
                name="balance_dia_de_la_semana",
            ),
        ]

    def __str__(self):
        return f"{self.semana.codigo} · día {self.dia}"

    def clean(self):
        if not isinstance(self.ajustes, dict):
            raise ValidationError({"ajustes": "Debe ser un objeto de ajustes por origen."})

        origenes = {"ccaa", "nestle", "punion"}
        desconocidos = set(self.ajustes) - origenes

        if desconocidos:
            raise ValidationError(
                {
                    "ajustes": (
                        f"Orígenes no reconocidos: {', '.join(sorted(desconocidos))}. "
                        f"Los válidos son: {', '.join(sorted(origenes))}."
                    )
                }
            )

        for origen, valor in self.ajustes.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise ValidationError(
                    {"ajustes": f"El ajuste de '{origen}' debe ser numérico."}
                )
