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

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from usuarios.tenancy import sucursal_predeterminada_pruebas
from usuarios.documentos import DocumentoBorradorMixin

from maestros.models import Silo, Vehiculo

from . import dominio


CONTROLES_DECLARADOS = {
    "temperatura",
    "acidez",
    "ph",
    "delvo",
    "inhibidores",
    "grasa",
    "sng",
    # Los cuatro ítems que el formato pide por separado (columnas AC-AF).
    "sangre",
    "pus",
    "materias_extranas",
    "aroma",
    # Clave histórica: dejó de escribirse pero se sigue leyendo, porque las
    # filas anteriores al formato ampliado la tienen y siguen valiendo.
    "organoleptico",
}

CONTROLES_NUMERICOS = {"temperatura", "acidez", "ph", "grasa", "sng"}

ITEMS_ORGANOLEPTICOS = ("sangre", "pus", "materias_extranas", "aroma")

VALORES_ADMITIDOS = {
    "delvo": {"Negativo", "Positivo"},
    "inhibidores": {"Negativo", "Positivo"},
    "organoleptico": {"Conforme", "No conforme"},
    **{item: {"Conforme", "No conforme"} for item in ITEMS_ORGANOLEPTICOS},
}


class Recepcion(DocumentoBorradorMixin, models.Model):
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
        CCAA = "CCAA", "CCAA"
        NESTLE = "Nestlé", "Nestlé"
        COLUN = "Colun", "Colun"
        P_UNION = "P. Unión", "P. Unión"

    class Uso(models.TextChoices):
        """
        A qué va la leche del camión. El comentario de la celda O15 del
        formato lo explica: «a qué n° de precondensado va ir esta leche, sirve
        para llevar trazabilidad y desviación de uso».

        Se guarda la familia aparte del número (`uso_numero`) porque la
        pregunta que motiva el campo —qué entró al Semi n°2— no se puede
        hacer contra un texto libre que además viene con variantes de tipeo.
        """

        DESPACHO = "despacho", "Despacho"
        STOCK = "stock", "Stock"
        SEMI = "semi", "Precondensado semidescremado"
        ENTERO = "entero", "Precondensado entero"
        LE = "le", "Leche entera"
        SUERO = "suero", "Suero"
        ANTIBIOTICO = "antibiotico", "Antibiótico"

    class RecambioDilucion(models.TextChoices):
        RECAMBIO = "recambio", "Recambio"
        OK = "ok", "OK"

    # Familias que numeran su destino. `Despacho` o `Stock` con un número
    # detrás no significaría nada.
    USOS_NUMERADOS = ("semi", "entero")

    class TipoLeche(models.TextChoices):
        ENTERA = "Entera", "Entera"
        DESCREMADA = "Descremada", "Descremada"

    class Turno(models.TextChoices):
        A = "A", "Turno A"
        B = "B", "Turno B"
        C = "C", "Turno C"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        REGISTRADA = "registrada", "En espera de muestra"
        MUESTREADA = "muestreada", "Muestra tomada"
        ANALIZADA = "analizada", "Analizada"
        LIBERADA = "liberada", "Aprobada por Calidad"
        RETENIDA = "retenida", "Retenida"
        DESCARGADA = "descargada", "Descargada"
        CERRADA = "cerrada", "Cerrada"
        ANULADA = "anulada", "Anulada"

    # Transiciones válidas, tal como las declara el esquema del prototipo.
    # Una retenida puede liberarse tras reanálisis, o cerrarse rechazada.
    TRANSICIONES = {
        Estado.BORRADOR: [Estado.REGISTRADA, Estado.ANULADA],
        Estado.REGISTRADA: [Estado.MUESTREADA, Estado.CERRADA],
        Estado.MUESTREADA: [Estado.ANALIZADA],
        Estado.ANALIZADA: [Estado.LIBERADA, Estado.RETENIDA],
        Estado.LIBERADA: [Estado.DESCARGADA],
        Estado.RETENIDA: [Estado.LIBERADA, Estado.CERRADA],
        Estado.DESCARGADA: [Estado.CERRADA],
        Estado.CERRADA: [],
        Estado.ANULADA: [],
    }

    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "fecha", "vehiculo", "tipo_leche", "litros",
    )
    ESTADO_BORRADOR = Estado.BORRADOR
    ESTADO_CONFIRMADO = Estado.REGISTRADA
    CAMPOS_POR_PASO = {
        "llegada": (
            "fecha", "hora", "guia", "vehiculo", "procedencia", "tipo_leche",
            "litros", "kg_romana", "certificada", "uso", "uso_numero",
            "modulos.crioscopia",
        ),
        "muestreo": ("codigo_muestra", "muestreado_por", "muestreado_en"),
        "calidad": ("controles", "ph_camion", "calidad_por", "calidad_en"),
        "destino": ("silo", "silo_asignado_por", "silo_asignado_en"),
    }
    CAMPOS_QUE_MUEVEN_LIBRO = ("litros", "silo")

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
    kg_romana = models.DecimalField(
        "Kilos (romana)",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="El pesaje real. Los kilos de guía se derivan de los litros.",
    )
    certificada = models.BooleanField(
        "Leche certificada",
        null=True,
        blank=True,
        help_text="Nulo = no se registró, que no es lo mismo que no certificada",
    )
    uso = models.CharField("Uso", max_length=20, choices=Uso.choices, blank=True)
    uso_numero = models.PositiveSmallIntegerField(
        "N° de destino", null=True, blank=True
    )

    # Las ocho marcas horarias del formato. Son fijas y una sola vez por
    # camión, así que van aquí y no en un modelo hijo.
    hora_programa = models.TimeField("Hora programa", null=True, blank=True)
    hora_arribo_porteria = models.TimeField("Arribo a portería", null=True, blank=True)
    hora_ingreso = models.TimeField("Hora de ingreso", null=True, blank=True)
    hora_inicio_descarga = models.TimeField("Inicio de descarga", null=True, blank=True)
    hora_termino_descarga = models.TimeField("Término de descarga", null=True, blank=True)
    hora_inicio_cip = models.TimeField("Inicio del lavado CIP", null=True, blank=True)
    hora_termino_cip = models.TimeField("Término del lavado CIP", null=True, blank=True)
    hora_salida = models.TimeField("Hora de salida", null=True, blank=True)

    # Higiene del camión.
    lavado_ruedas = models.BooleanField("Lavado de ruedas", null=True, blank=True)
    relavado = models.BooleanField(
        "Vuelve a lavarse e ingresa", null=True, blank=True
    )
    recambio_dilucion = models.CharField(
        "Cambio de dilución", max_length=20, choices=RecambioDilucion.choices, blank=True
    )
    ph_camion = models.DecimalField(
        "pH del camión",
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Del enjuague del camión (5,5 a 8,5), NO de la leche. Mezclarlo con "
            "el pH de la leche haría que el agua retuviera un camión conforme."
        ),
    )
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
        "Estado", max_length=20, choices=Estado.choices, default=Estado.BORRADOR
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

    @property
    def kg_guia(self):
        return dominio.kilos_desde_litros(self.litros)

    @property
    def diferencia_kg(self):
        return dominio.diferencia_pesaje(self.kg_guia, self.kg_romana)

    @property
    def solidos_totales(self):
        controles = self.controles or {}
        return dominio.solidos_totales(controles.get("grasa"), controles.get("sng"))

    @property
    def solidos_totales_kg(self):
        return dominio.solidos_totales_kg(self.kg_romana, self.solidos_totales)

    @property
    def crioscopia_pool(self):
        return dominio.crioscopia_pool(
            [modulo.crioscopia for modulo in self.modulos.all()]
        )

    def evaluar(self, controles=None):
        """
        Evalúa los controles del camión contra `dominio.evaluar_recepcion`,
        con la crioscopía de cada módulo y el pH del camión — el único lugar
        que arma esos dos argumentos, para que el serializer (que muestra la
        evaluación) y `decidir-calidad` (que decide con ella) no puedan
        divergir. `controles` por defecto usa los ya guardados; `decidir-
        calidad` la llama con los que está a punto de guardar, todavía sin
        persistir.
        """
        return dominio.evaluar_recepcion(
            controles if controles is not None else self.controles,
            # Pares (numero, crioscopia): el número lo pone el módulo, no la
            # posición en la lista. Los números registrados no tienen por qué
            # ser contiguos, y con `enumerate` el módulo 3 saldría acusado
            # como «M2» — el motivo es lo que le dice a Calidad qué
            # compartimiento re-muestrear.
            crioscopias=[
                (modulo.numero, modulo.crioscopia)
                for modulo in self.modulos.all()
            ],
            ph_camion=self.ph_camion,
        )

    @property
    def _permanencia(self):
        return dominio.permanencia(self.hora_arribo_porteria, self.hora_termino_cip)

    @property
    def permanencia_horas(self):
        return self._permanencia.horas

    @property
    def permanencia_motivo(self):
        """
        Por qué `permanencia_horas` salió `None` (qué marca horaria falta).
        Vacío cuando sí se pudo calcular: la decisión devuelve motivo, no
        solo un booleano, igual que el resto del sistema.
        """
        return self._permanencia.motivo

    @property
    def horas_en_planta(self):
        return self._permanencia.horas_en_planta

    @property
    def horas_a_pagar(self):
        return dominio.horas_a_pagar(self.permanencia_horas)

    @property
    def tiempo_en_fabrica_horas(self):
        return dominio.horas_entre(self.hora_ingreso, self.hora_termino_cip)

    @property
    def tiempo_de_descarga_horas(self):
        return dominio.horas_entre(
            self.hora_inicio_descarga, self.hora_termino_descarga
        )

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

        # Un número de destino sin familia no dice de qué es, y una familia sin
        # número que la admita convierte el número en ruido.
        if self.uso_numero is not None and self.uso not in self.USOS_NUMERADOS:
            raise ValidationError(
                {
                    "uso_numero": (
                        "Solo los precondensados llevan número de destino. "
                        f"«{self.get_uso_display() or 'sin uso'}» no."
                    )
                }
            )

    def puede_pasar_a(self, estado) -> bool:
        return estado in self.TRANSICIONES.get(self.estado, [])

    def motivos_para_confirmar(self):
        motivos = super().motivos_para_confirmar()
        if self.litros is None or self.litros <= 0:
            motivos = [m for m in motivos if "litros" not in m]
            motivos.append("Los litros deben ser mayores que cero.")
        if not self.modulos.exists():
            motivos.append("Declara al menos un compartimiento del camión.")
        return motivos


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
            # El formato solo tiene cuatro columnas (M1-M4): un número fuera
            # de 1-4 no representa ningún compartimiento real.
            models.CheckConstraint(
                condition=models.Q(numero__gte=1) & models.Q(numero__lte=4),
                name="modulo_numero_en_rango",
            ),
            # Una carga de Recolección se recibe una sola vez. Lo garantizaba
            # el OneToOneField de `Recepcion`; al bajar el vínculo al módulo
            # como FK, sin esto dos módulos podrían apuntar a la misma carga y
            # sus litros se contarían dos veces. Parcial porque los módulos sin
            # carga vinculada son la mayoría y todos son NULL.
            models.UniqueConstraint(
                fields=["carga_recoleccion"],
                condition=models.Q(carga_recoleccion__isnull=False),
                name="una_recepcion_por_carga_recoleccion",
            ),
        ]

    def __str__(self):
        return f"{self.recepcion_id} · M{self.numero}"


class CorreccionRecepcion(models.Model):
    """Edición justificada de un paso ya recorrido por la recepción."""

    recepcion = models.ForeignKey(
        Recepcion, on_delete=models.PROTECT, related_name="correcciones"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="correcciones_recepcion",
    )
    paso = models.CharField(max_length=30)
    motivo = models.TextField()
    cambios = models.JSONField(default=dict)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en", "-id"]


class AlertaCalidadSilo(models.Model):
    """Silo potencialmente afectado; informa sin bloquearlo automáticamente."""

    recepcion = models.ForeignKey(
        Recepcion, on_delete=models.PROTECT, related_name="alertas_calidad_silo"
    )
    silo = models.ForeignKey(
        Silo, on_delete=models.PROTECT, related_name="alertas_calidad_recepcion"
    )
    motivo = models.TextField()
    activa = models.BooleanField(default=True, db_index=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en", "-id"]


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
        self.litros = Decimal(str(self.litros))
        with transaction.atomic():
            resultado = super().save(*args, **kwargs)
            if (
                self.tipo == self.Tipo.SALIDA
                or (
                    self.tipo == self.Tipo.AJUSTE
                    and Decimal(str(self.litros)) < 0
                )
            ):
                # Import local para evitar el ciclo models -> servicios -> models.
                from .servicios import atribuir_salida
                atribuir_salida(self)
        return resultado


class AtribucionRecepcion(models.Model):
    """Parte de un movimiento explicada por una recepción, en orden FIFO."""

    movimiento = models.ForeignKey(
        MovimientoSilo, on_delete=models.PROTECT,
        related_name="atribuciones_recepcion",
    )
    recepcion = models.ForeignKey(
        Recepcion, on_delete=models.PROTECT, null=True, blank=True,
        related_name="atribuciones_silo",
    )
    litros = models.DecimalField(max_digits=12, decimal_places=2)
    orden = models.PositiveSmallIntegerField()
    origen_no_atribuible = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["movimiento_id", "orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["movimiento", "orden"],
                name="atribucion_orden_unico_por_movimiento",
            ),
            models.CheckConstraint(
                condition=models.Q(litros__gt=0),
                name="atribucion_litros_positivos",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(recepcion__isnull=False, origen_no_atribuible="")
                    | (
                        models.Q(recepcion__isnull=True)
                        & ~models.Q(origen_no_atribuible="")
                    )
                ),
                name="atribucion_recepcion_o_motivo",
            ),
        ]

    def __str__(self):
        origen = self.recepcion_id or self.origen_no_atribuible
        return f"{self.litros} L de {origen}"


class ControlInhibidores(models.Model):
    """
    PPRO N°1 — control de inhibidores en leche fresca.

    Origen: hoja `Inhibidores` del Instructivo (`CCAA.REC.FORM.002.01`), que
    la rotula «PPRO N°1» en su encabezado.

    No usa `inocuidad.MonitoreoPPRO` porque ese modelo exige un lote, y esto
    cuelga de un camión y una fecha: la leche todavía no es un lote.
    """

    class Metodo(models.TextChoices):
        TRI_SENSOR = "tri_sensor", "Tri Sensor"
        CHARM = "charm", "Charm"
        DELVO_SP = "delvo_sp", "Delvo SP"

    class Resultado(models.TextChoices):
        NEGATIVO = "negativo", "Negativo"
        POSITIVO = "positivo", "Positivo"

    recepcion = models.ForeignKey(
        Recepcion,
        on_delete=models.CASCADE,
        related_name="controles_inhibidores",
        verbose_name="Recepción",
    )
    metodo = models.CharField(
        "Método", max_length=20, choices=Metodo.choices, default=Metodo.TRI_SENSOR
    )
    tiras_usadas = models.PositiveSmallIntegerField(
        "Tiras usadas",
        default=0,
        help_text="El formato las totaliza al pie: es control de consumo",
    )
    hora_lectura = models.TimeField("Hora de lectura", null=True, blank=True)
    resultado = models.CharField(
        "Resultado", max_length=20, choices=Resultado.choices
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="controles_inhibidores",
        null=True,
        blank=True,
        verbose_name="Analista",
    )

    class Meta:
        verbose_name = "Control de inhibidores (PPRO N°1)"
        verbose_name_plural = "Controles de inhibidores (PPRO N°1)"
        ordering = ["recepcion", "hora_lectura"]

    def __str__(self):
        return f"{self.recepcion_id} · {self.get_metodo_display()} · {self.resultado}"


class BusquedaProveedor(models.Model):
    """
    Búsqueda del proveedor responsable tras un positivo.

    Es el paso siguiente al positivo, que hasta ahora no existía: la recepción
    quedaba retenida y el registro no decía de quién venía la leche.
    """

    control = models.ForeignKey(
        ControlInhibidores,
        on_delete=models.CASCADE,
        related_name="busquedas",
        verbose_name="Control de inhibidores",
    )
    proveedor = models.CharField("Proveedor", max_length=160)
    charm_bet = models.CharField(
        "Charm rosa Bet",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    charm_tetra = models.CharField(
        "Charm rosa Tetra",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    delvo_sp = models.CharField(
        "Delvo SP",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    hora_lectura = models.TimeField("Hora de lectura", null=True, blank=True)
    resultado = models.CharField(
        "Resultado", max_length=20, choices=ControlInhibidores.Resultado.choices
    )

    class Meta:
        verbose_name = "Búsqueda a proveedor"
        verbose_name_plural = "Búsquedas a proveedores"
        ordering = ["control", "proveedor"]

    def __str__(self):
        return f"{self.proveedor} · {self.resultado}"


class AnalisisSilo(DocumentoBorradorMixin, models.Model):
    """
    El análisis de la leche que hay en un silo.

    Origen: el vale `CCAA.REC.FORM.005.01` («Trazabilidad de leche en silos»),
    que trae pH, acidez, grasa, SNG, proteína, temperatura y densidad por silo.

    No se confunde con `Recepcion.controles`, que son los del **camión**: el
    silo mezcla varios camiones, y es esta mezcla —no cada camión— la que
    alimenta el cálculo del RC. Con un solo registro para los dos, un vale
    compuesto desde el análisis de un camión describiría una leche que no
    está en ninguna parte.

    Los siete parámetros son nulables porque el formato se llena por partes:
    la temperatura y el pH se miden al llenar, la grasa y el SNG cuando el
    laboratorio devuelve la muestra. Qué falta para componer un vale lo
    responde `dominio.parametros_faltantes`, no el esquema.
    """

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        CONFIRMADO = "confirmado", "Confirmado"
        ANULADO = "anulado", "Anulado"

    CAMPOS_OBLIGATORIOS_AL_CONFIRMAR = (
        "silo", "tomado_en", "grasa", "sng",
        "inhibidores_resultado", "metodo", "hora_lectura",
    )
    ESTADO_BORRADOR = Estado.BORRADOR
    ESTADO_CONFIRMADO = Estado.CONFIRMADO

    silo = models.ForeignKey(
        Silo, on_delete=models.PROTECT, related_name="analisis", verbose_name="Silo"
    )
    tomado_en = models.DateTimeField(
        "Hora de toma de muestra",
        help_text="Fecha y hora en que se muestreó el silo. Fija la vigencia del análisis.",
    )
    hora_inicio_llenado = models.TimeField(
        "Hora de inicio de llenado", null=True, blank=True
    )

    ph = models.DecimalField("pH", max_digits=4, decimal_places=2, null=True, blank=True)
    acidez = models.DecimalField(
        "Acidez (°Th)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    grasa = models.DecimalField(
        "Grasa (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    sng = models.DecimalField(
        "SNG (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    proteina = models.DecimalField(
        "Proteína (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    temperatura = models.DecimalField(
        "Temperatura (°C)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    densidad = models.DecimalField(
        "Densidad (kg/m³)", max_digits=7, decimal_places=2, null=True, blank=True
    )
    inhibidores_resultado = models.CharField(
        "Resultado de inhibidores",
        max_length=20,
        choices=ControlInhibidores.Resultado.choices,
        blank=True,
    )
    metodo = models.CharField(
        "Método de inhibidores",
        max_length=20,
        choices=ControlInhibidores.Metodo.choices,
        blank=True,
    )
    hora_lectura = models.TimeField("Hora de lectura", null=True, blank=True)
    alcohol_75_conforme = models.BooleanField(
        "Prueba de alcohol 75° conforme", null=True, blank=True
    )
    hervor_conforme = models.BooleanField(
        "Prueba de hervor conforme", null=True, blank=True
    )
    organoleptico_conforme = models.BooleanField(
        "Control organoléptico conforme", null=True, blank=True
    )

    certificada = models.BooleanField(
        "Leche certificada",
        null=True,
        blank=True,
        help_text="Nulo = no se registró, que no es lo mismo que no certificada",
    )
    procedencia = models.CharField(
        "Procedencia", max_length=20, choices=Recepcion.Procedencia.choices, blank=True
    )
    analista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="analisis_silo",
        null=True,
        blank=True,
        verbose_name="Analista",
    )
    visualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="analisis_silo_visualizados",
        null=True,
        blank=True,
        verbose_name="Visualizado por",
    )
    visualizado_en = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField("Observación", blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(
        max_length=15, choices=Estado.choices, default=Estado.BORRADOR
    )

    class Meta:
        verbose_name = "Análisis de silo"
        verbose_name_plural = "Análisis de silo"
        ordering = ["-tomado_en"]
        indexes = [models.Index(fields=["silo", "-tomado_en"])]
        constraints = [
            models.UniqueConstraint(
                fields=["silo", "tomado_en"], name="analisis_silo_unico_por_momento"
            ),
        ]

    def __str__(self):
        return f"{self.silo} · {self.tomado_en:%Y-%m-%d %H:%M}"

    #: Lo mínimo que un vale de estandarización necesita del silo.
    REQUERIDOS_PARA_VALE = ("grasa", "sng")

    @property
    def vigencia(self):
        """
        Si el análisis todavía describe lo que hay en el silo.

        Solo los **ingresos** cuentan: una salida no cambia la composición de
        la leche que queda, e invalidar por salida obligaría a re-muestrear
        cada vez que una línea consume.
        """
        ingresos = MovimientoSilo.objects.filter(
            silo_id=self.silo_id,
            tipo=MovimientoSilo.Tipo.INGRESO,
            fecha_hora__gt=self.tomado_en,
        ).values_list("fecha_hora", "litros")

        return dominio.analisis_vigente(self.tomado_en, ingresos)

    @property
    def vigente(self):
        return self.vigencia.vigente

    @property
    def motivo_vigencia(self):
        return self.vigencia.motivo

    @property
    def faltantes_para_vale(self):
        valores = {
            nombre: getattr(self, nombre)
            for nombre in dominio.PARAMETROS_ANALISIS_SILO
        }
        return dominio.parametros_faltantes(valores, self.REQUERIDOS_PARA_VALE)

    @property
    def apto_inocuidad(self):
        return (
            self.inhibidores_resultado == ControlInhibidores.Resultado.NEGATIVO
            and bool(self.metodo)
            and self.hora_lectura is not None
        )
