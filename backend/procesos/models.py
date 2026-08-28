from decimal import Decimal
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from usuarios.tenancy import sucursal_predeterminada_pruebas


class Proceso(models.Model):
    codigo = models.SlugField(max_length=50)
    nombre = models.CharField(max_length=160)
    version = models.PositiveSmallIntegerField(default=1)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo", "version"], name="proceso_codigo_version_unica"
            )
        ]

    def __str__(self):
        return f"{self.nombre} · v{self.version}"


class EtapaProceso(models.Model):
    class Tipo(models.TextChoices):
        RECEPCION = "recepcion", "Recepción"
        ESTANDARIZACION = "estandarizacion", "Estandarización"
        DESCREMACION = "descremacion", "Descremación"
        EVAPORACION = "evaporacion", "Evaporación"
        CONDENSACION = "condensacion", "Condensación"
        SECADO = "secado", "Secado"
        ENVASADO = "envasado", "Envasado"
        MANTEQUILLA = "mantequilla", "Mantequilla"
        TRANSFERENCIA = "transferencia", "Transferencia"
        OTRO = "otro", "Otro"

    proceso = models.ForeignKey(Proceso, on_delete=models.PROTECT, related_name="etapas")
    codigo = models.SlugField(max_length=50)
    nombre = models.CharField(max_length=160)
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    orden = models.PositiveSmallIntegerField()
    requiere_calidad = models.BooleanField(default=False)
    requiere_inocuidad = models.BooleanField(default=False)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["proceso", "orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["proceso", "codigo"], name="etapa_codigo_unico_proceso"
            ),
            models.UniqueConstraint(
                fields=["proceso", "orden"], name="etapa_orden_unico_proceso"
            ),
        ]

    def __str__(self):
        return f"{self.proceso.nombre} · {self.nombre}"


class RutaProducto(models.Model):
    """Proceso configurable permitido para un producto en una planta."""

    sucursal = models.ForeignKey(
        "usuarios.Sucursal", on_delete=models.PROTECT,
        related_name="rutas_producto", default=sucursal_predeterminada_pruebas,
    )
    producto = models.ForeignKey(
        "maestros.Producto", on_delete=models.PROTECT, related_name="rutas_proceso"
    )
    proceso = models.ForeignKey(
        Proceso, on_delete=models.PROTECT, related_name="rutas_producto"
    )
    prioridad = models.PositiveSmallIntegerField(default=1)
    destino = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["producto__nombre", "prioridad", "proceso__nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "producto", "proceso"],
                name="ruta_producto_proceso_unica_planta",
            ),
            models.CheckConstraint(
                condition=models.Q(prioridad__gt=0), name="ruta_prioridad_positiva"
            ),
        ]
        indexes = [models.Index(fields=["sucursal", "producto", "activa"])]

    def clean(self):
        if (
            self.sucursal_id and self.producto_id
            and self.producto.mandante.empresa_id != self.sucursal.empresa_id
        ):
            raise ValidationError(
                {"producto": "El producto y la ruta deben pertenecer a la misma empresa."}
            )

    def __str__(self):
        return f"{self.producto.nombre} → {self.proceso.nombre}"


class CorridaCondensacion(models.Model):
    """Ejecución especializada; conserva el lote maestro y su balance físico."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_PROCESO = "en_proceso", "En proceso"
        PENDIENTE_CALIDAD = "pendiente_calidad", "Pendiente de Calidad"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    ejecucion = models.OneToOneField(
        "procesos.EjecucionProceso", on_delete=models.PROTECT,
        related_name="corrida_condensacion",
    )
    orden = models.ForeignKey(
        "produccion.OrdenProduccion", on_delete=models.PROTECT,
        related_name="corridas_condensacion",
    )
    lote = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT,
        related_name="corridas_condensacion",
    )
    silo_origen = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT,
        related_name="condensaciones_origen",
    )
    silo_destino = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT,
        related_name="condensaciones_destino",
    )
    litros_entrada = models.DecimalField(max_digits=14, decimal_places=2)
    litros_precondensado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    flujo_promedio = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    densidad_salida = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    solidos_salida = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    temperatura_salida = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    vacio_promedio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    presion_promedio = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estado = models.CharField(
        max_length=25, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    operacion_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="condensaciones_iniciadas", null=True, blank=True,
    )
    iniciada_en = models.DateTimeField(null=True, blank=True)
    finalizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="condensaciones_finalizadas", null=True, blank=True,
    )
    finalizada_en = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros_entrada__gt=0),
                name="condensacion_entrada_positiva",
            ),
            models.CheckConstraint(
                condition=models.Q(litros_precondensado__isnull=True)
                | models.Q(litros_precondensado__gt=0),
                name="condensacion_salida_positiva",
            ),
        ]

    def clean(self):
        if self.silo_origen_id == self.silo_destino_id:
            raise ValidationError("Condensación requiere silos de origen y destino distintos.")
        if self.ejecucion_id and self.ejecucion.etapa.tipo not in {
            EtapaProceso.Tipo.EVAPORACION, EtapaProceso.Tipo.CONDENSACION,
        }:
            raise ValidationError({"ejecucion": "La ejecución no es de condensación/evaporación."})
        if self.orden_id and self.lote_id and self.lote.orden_id != self.orden_id:
            raise ValidationError({"lote": "El lote no pertenece a la orden seleccionada."})
        if self.ejecucion_id:
            sucursal_id = self.ejecucion.sucursal_id
            for campo in ("silo_origen", "silo_destino"):
                silo = getattr(self, campo, None)
                if silo and silo.sucursal_id != sucursal_id:
                    raise ValidationError({campo: "El silo pertenece a otra planta."})

    def __str__(self):
        return f"Condensación {self.ejecucion.codigo}"


class CorridaDescremacion(models.Model):
    """Una pasada de descremadora: leche entera entra; descremada y crema salen."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_CURSO = "en_curso", "En curso"
        CERRADA = "cerrada", "Cerrada"
        ANULADA = "anulada", "Anulada"

    ejecucion = models.OneToOneField(
        "procesos.EjecucionProceso", on_delete=models.PROTECT,
        related_name="corrida_descremacion",
    )
    orden = models.ForeignKey(
        "produccion.OrdenProduccion", on_delete=models.PROTECT,
        related_name="corridas_descremacion", null=True, blank=True,
    )
    silo_entera = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="descremaciones_origen"
    )
    analisis_entrada = models.ForeignKey(
        "recepcion.AnalisisSilo", on_delete=models.PROTECT,
        related_name="descremaciones",
    )
    litros_entrada = models.DecimalField(max_digits=14, decimal_places=2)
    grasa_entrada = models.DecimalField(max_digits=6, decimal_places=3)
    sng_entrada = models.DecimalField(max_digits=6, decimal_places=3)
    silo_descremada = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="descremaciones_salida"
    )
    litros_descremada = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    grasa_descremada = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    estanque_crema = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="crema_descremaciones"
    )
    litros_crema = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    grasa_crema = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    controles = models.JSONField(default=dict, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    operacion_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="descremaciones_iniciadas", null=True, blank=True,
    )
    iniciada_en = models.DateTimeField(null=True, blank=True)
    finalizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="descremaciones_finalizadas", null=True, blank=True,
    )
    finalizada_en = models.DateTimeField(null=True, blank=True)
    motivo_anulacion = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros_entrada__gt=0), name="descremacion_entrada_positiva"
            ),
            models.CheckConstraint(
                condition=models.Q(litros_descremada__isnull=True)
                | models.Q(litros_descremada__gt=0), name="descremacion_descremada_positiva"
            ),
            models.CheckConstraint(
                condition=models.Q(litros_crema__isnull=True)
                | models.Q(litros_crema__gt=0), name="descremacion_crema_positiva"
            ),
        ]

    def clean(self):
        if self.ejecucion_id and self.ejecucion.etapa.tipo != EtapaProceso.Tipo.DESCREMACION:
            raise ValidationError({"ejecucion": "La ejecución no corresponde a descremación."})
        ids = {self.silo_entera_id, self.silo_descremada_id, self.estanque_crema_id}
        if None not in ids and len(ids) != 3:
            raise ValidationError("La entrada, la descremada y la crema requieren estanques distintos.")
        if self.analisis_entrada_id and self.silo_entera_id:
            if self.analisis_entrada.silo_id != self.silo_entera_id:
                raise ValidationError({"analisis_entrada": "El análisis no pertenece al silo de leche entera."})
        if self.ejecucion_id:
            for campo in ("silo_entera", "silo_descremada", "estanque_crema"):
                silo = getattr(self, campo, None)
                if silo and silo.sucursal_id != self.ejecucion.sucursal_id:
                    raise ValidationError({campo: "El estanque pertenece a otra planta."})

    def __str__(self):
        return f"Descremación {self.ejecucion.codigo}"


class CorridaMantequilla(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        EN_PROCESO = "en_proceso", "En proceso"
        PENDIENTE_CALIDAD = "pendiente_calidad", "Pendiente de Calidad"
        CERRADA = "cerrada", "Cerrada"

    ejecucion = models.OneToOneField(
        "procesos.EjecucionProceso", on_delete=models.PROTECT,
        related_name="corrida_mantequilla"
    )
    orden = models.ForeignKey(
        "produccion.OrdenProduccion", on_delete=models.PROTECT,
        related_name="corridas_mantequilla",
    )
    lote_crema = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT,
        related_name="usos_en_mantequilla",
    )
    lote_mantequilla = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT,
        related_name="corridas_mantequilla",
    )
    lote_suero = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT,
        related_name="corridas_como_suero_mantequilla", null=True, blank=True,
    )
    kg_crema = models.DecimalField(max_digits=14, decimal_places=3)
    kg_mantequilla = models.DecimalField(max_digits=14, decimal_places=3, null=True, blank=True)
    kg_suero = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    kg_merma = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    controles = models.JSONField(default=dict, blank=True)
    estado = models.CharField(
        max_length=25, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    iniciada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mantequillas_iniciadas", null=True, blank=True,
    )
    iniciada_en = models.DateTimeField(null=True, blank=True)
    finalizada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="mantequillas_finalizadas", null=True, blank=True,
    )
    finalizada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(kg_crema__gt=0), name="mantequilla_crema_positiva"),
            models.CheckConstraint(condition=models.Q(kg_suero__gte=0), name="mantequilla_suero_no_negativo"),
            models.CheckConstraint(condition=models.Q(kg_merma__gte=0), name="mantequilla_merma_no_negativa"),
        ]

    def clean(self):
        if self.ejecucion_id and self.ejecucion.etapa.tipo != EtapaProceso.Tipo.MANTEQUILLA:
            raise ValidationError({"ejecucion": "La ejecución no corresponde a Mantequilla."})
        if self.lote_crema_id and self.lote_crema.producto.familia != "crema":
            raise ValidationError({"lote_crema": "La materia prima debe ser un lote de crema."})
        if self.lote_mantequilla_id and self.lote_mantequilla.producto.categoria != "mantequilla":
            raise ValidationError({"lote_mantequilla": "El lote de salida debe ser mantequilla."})
        if self.lote_crema_id and self.lote_mantequilla_id:
            if self.lote_crema.sucursal_id != self.lote_mantequilla.sucursal_id:
                raise ValidationError("Los lotes deben pertenecer a la misma planta.")
        if self.kg_suero and not self.lote_suero_id:
            raise ValidationError({"lote_suero": "Identifica el lote del suero generado."})
        if self.kg_mantequilla is not None:
            total = self.kg_mantequilla + self.kg_suero + self.kg_merma
            if total > self.kg_crema:
                raise ValidationError("Mantequilla, suero y merma superan la crema utilizada.")


class EjecucionProceso(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PREPARACION = "preparacion", "En preparación"
        EJECUCION = "ejecucion", "En ejecución"
        PAUSADA = "pausada", "Pausada"
        PENDIENTE_CONTROL = "pendiente_control", "Pendiente de control"
        BLOQUEADA = "bloqueada", "Bloqueada"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    TRANSICIONES = {
        Estado.BORRADOR: {Estado.PREPARACION, Estado.CANCELADA},
        Estado.PREPARACION: {Estado.EJECUCION, Estado.CANCELADA},
        Estado.EJECUCION: {
            Estado.PAUSADA, Estado.PENDIENTE_CONTROL, Estado.BLOQUEADA,
            Estado.CANCELADA,
        },
        Estado.PAUSADA: {Estado.EJECUCION, Estado.BLOQUEADA, Estado.CANCELADA},
        Estado.PENDIENTE_CONTROL: {Estado.CERRADA, Estado.BLOQUEADA, Estado.EJECUCION},
        Estado.BLOQUEADA: {Estado.EJECUCION, Estado.CANCELADA},
        Estado.CERRADA: set(),
        Estado.CANCELADA: set(),
    }

    codigo = models.CharField(max_length=60, unique=True)
    etapa = models.ForeignKey(EtapaProceso, on_delete=models.PROTECT, related_name="ejecuciones")
    sucursal = models.ForeignKey(
        "usuarios.Sucursal", on_delete=models.PROTECT, related_name="ejecuciones_proceso",
        default=sucursal_predeterminada_pruebas,
    )
    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT, related_name="ejecuciones_proceso",
        null=True, blank=True,
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ejecuciones_proceso", null=True, blank=True,
    )
    # **Un vale de estandarización ES una ejecución de esa etapa.** No es que
    # una la acompañe a la otra: son el mismo hecho de planta visto desde dos
    # sitios —el vale lleva la receta y el RC, la ejecución lleva el lugar en la
    # cadena—. Uno a uno para que no puedan contradecirse.
    vale = models.OneToOneField(
        "estandarizacion.ValeEstandarizacion", on_delete=models.PROTECT,
        related_name="ejecucion", null=True, blank=True,
        verbose_name="Vale de estandarización",
    )
    estado = models.CharField(
        max_length=25, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    inicio = models.DateTimeField(null=True, blank=True)
    termino = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-creada_en"]
        indexes = [
            models.Index(fields=["sucursal", "estado", "-creada_en"]),
            models.Index(fields=["etapa", "estado"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(termino__isnull=True) | models.Q(inicio__isnull=True)
                | models.Q(termino__gt=models.F("inicio")),
                name="ejecucion_termino_posterior_inicio",
            )
        ]

    def __str__(self):
        return f"{self.codigo} · {self.etapa.nombre}"

    def clean(self):
        if self.equipo_id and self.equipo.sucursal_id != self.sucursal_id:
            raise ValidationError({"equipo": "El equipo debe pertenecer a la sucursal de la ejecución."})

    @property
    def editable(self):
        return self.estado not in {self.Estado.CERRADA, self.Estado.CANCELADA}


class EntradaProceso(models.Model):
    class Tipo(models.TextChoices):
        PRINCIPAL = "principal", "Principal"
        MEZCLA = "mezcla", "Mezcla"
        RECIRCULACION = "recirculacion", "Recirculación"
        REPROCESO = "reproceso", "Reproceso"

    ejecucion = models.ForeignKey(
        EjecucionProceso, on_delete=models.PROTECT, related_name="entradas"
    )
    lote = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT, related_name="entradas_proceso",
        null=True, blank=True,
    )
    # Las primeras etapas de la planta no consumen lotes: la estandarización
    # toma leche de un silo y del TK de descremada, y esa leche no es de ningún
    # lote todavía. Con `lote` obligatorio, esas etapas no se podían registrar y
    # la cadena de trazabilidad empezaba a mitad del proceso.
    silo = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="entradas_proceso",
        null=True, blank=True, verbose_name="Silo de origen",
    )
    salida_origen = models.ForeignKey(
        "procesos.SalidaProceso", on_delete=models.PROTECT,
        related_name="usos_como_origen", null=True, blank=True,
        help_text="Resultado intermedio liberado que aporta esta entrada.",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.PRINCIPAL)
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    unidad = models.CharField(max_length=20, default="kg")
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="entrada_cantidad_positiva"),
            models.UniqueConstraint(
                fields=["ejecucion", "lote", "tipo"], name="entrada_unica_ejecucion_lote_tipo"
            ),
            # Uno de los dos, nunca los dos ni ninguno: una entrada que no dice
            # de dónde vino no es trazabilidad, y una que dice dos orígenes
            # obliga a cada consumidor a elegir cuál cree.
            models.CheckConstraint(
                condition=(
                    models.Q(lote__isnull=False, silo__isnull=True)
                    | models.Q(lote__isnull=True, silo__isnull=False)
                ),
                name="entrada_de_un_lote_o_de_un_silo",
            ),
        ]

    def clean(self):
        if not self.ejecucion.editable:
            raise ValidationError("No se pueden agregar entradas a una ejecución cerrada o cancelada.")

        if bool(self.lote_id) == bool(self.silo_id):
            raise ValidationError(
                "Una entrada viene de un lote o de un silo, y hay que decir de cuál."
            )

        if self.lote_id and self.lote.sucursal_id != self.ejecucion.sucursal_id:
            raise ValidationError({"lote": "El lote debe pertenecer a la sucursal de la ejecución."})

        if self.silo_id and self.silo.sucursal_id != self.ejecucion.sucursal_id:
            raise ValidationError({"silo": "El silo debe pertenecer a la sucursal de la ejecución."})

        if self.salida_origen_id:
            if not self.silo_id or self.salida_origen.silo_id != self.silo_id:
                raise ValidationError({
                    "salida_origen": "La salida debe corresponder al silo físico seleccionado."
                })
            if self.salida_origen.ejecucion_id == self.ejecucion_id:
                raise ValidationError({"salida_origen": "Una ejecución no puede consumirse a sí misma."})
            if self.salida_origen.unidad.lower() != self.unidad.lower():
                raise ValidationError({"unidad": "La unidad debe coincidir con la salida de origen."})
            from calidad.models import LiberacionProceso
            if not LiberacionProceso.objects.filter(
                salida_id=self.salida_origen_id,
                estado=LiberacionProceso.Estado.LIBERADO,
            ).exists():
                raise ValidationError({
                    "salida_origen": "El resultado todavía no está liberado por Calidad."
                })
            origen = self.salida_origen.ejecucion.etapa
            destino = self.ejecucion.etapa
            if origen.proceso_id != destino.proceso_id or destino.orden <= origen.orden:
                raise ValidationError({
                    "salida_origen": (
                        "La etapa destino debe ser una etapa posterior del proceso configurado."
                    )
                })

        self._validar_autorizacion_de_reproceso()

    def _validar_autorizacion_de_reproceso(self):
        """
        Regla de planta № 7: no se agrega rework sin autorización.

        Un reproceso es producto que ya falló una vez y vuelve a entrar a la
        cadena. Meterlo sin que Calidad lo haya evaluado arrastra el defecto
        al lote nuevo — y con la trazabilidad hacia adelante, a todos los que
        salgan de él.

        **La ausencia de liberación no es autorización.** Un lote sin
        expediente tramitado no es un lote aprobado: es uno que nadie miró. Es
        la misma distinción que hace la recepción con el Delvo, y la que
        `Liberacion` existe para no perder — por eso la fila se crea en
        `pendiente` desde que el lote se produce.

        La concesión sí autoriza: es Calidad diciendo «úsalo bajo estas
        condiciones», que es precisamente una autorización.
        """
        if self.tipo != self.Tipo.REPROCESO or not self.lote_id:
            return

        from calidad.models import Liberacion

        autorizado = Liberacion.objects.filter(
            lote_id=self.lote_id,
            estado__in=[Liberacion.Estado.LIBERADO, Liberacion.Estado.CONCESION],
        ).exists()

        if not autorizado:
            raise ValidationError({
                "lote": (
                    f"El lote {self.lote.codigo_lote} no está liberado por "
                    "Calidad: un reproceso sin autorización arrastra el defecto "
                    "al lote nuevo."
                )
            })


class SalidaProceso(models.Model):
    class Naturaleza(models.TextChoices):
        PRINCIPAL = "principal", "Producto principal"
        COPRODUCTO = "coproducto", "Coproducto"
        SUBPRODUCTO = "subproducto", "Subproducto"
        MERMA = "merma", "Merma"
        REPROCESO = "reproceso", "Destinado a reproceso"

    ejecucion = models.ForeignKey(
        EjecucionProceso, on_delete=models.PROTECT, related_name="salidas"
    )
    lote = models.ForeignKey(
        "produccion.Lote", on_delete=models.PROTECT, related_name="salidas_proceso",
        null=True, blank=True,
    )
    # La estandarización entrega su mezcla a un silo, no a un lote: la leche
    # queda ahí hasta que alguien declara a qué producto va. Mismo motivo que
    # en la entrada.
    silo = models.ForeignKey(
        "maestros.Silo", on_delete=models.PROTECT, related_name="salidas_proceso",
        null=True, blank=True, verbose_name="Silo de destino",
    )
    naturaleza = models.CharField(
        max_length=20, choices=Naturaleza.choices, default=Naturaleza.PRINCIPAL
    )
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)
    unidad = models.CharField(max_length=20, default="kg")
    motivo = models.CharField(max_length=250, blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="salida_cantidad_positiva"),
            models.CheckConstraint(
                condition=~models.Q(naturaleza="merma") | models.Q(lote__isnull=True),
                name="salida_merma_sin_lote",
            ),
        ]

    def clean(self):
        if not self.ejecucion.editable:
            raise ValidationError("No se pueden agregar salidas a una ejecución cerrada o cancelada.")
        if self.naturaleza != self.Naturaleza.MERMA and not (self.lote_id or self.silo_id):
            raise ValidationError({
                "lote": "Toda salida inventariable debe identificar un lote o un silo."
            })
        if self.lote_id and self.silo_id:
            raise ValidationError(
                "Una salida va a un lote o a un silo, no a los dos."
            )
        if self.naturaleza == self.Naturaleza.MERMA and not self.motivo.strip():
            raise ValidationError({"motivo": "Toda merma requiere un motivo."})

        if self.lote_id and self.lote.sucursal_id != self.ejecucion.sucursal_id:
            raise ValidationError({"lote": "El lote debe pertenecer a la sucursal de la ejecución."})
        self._validar_balance()

    def _validar_balance(self):
        """
        No puede salir más de lo que entró.

        La merma cuenta como salida: la pérdida también es masa que se fue, y
        excluirla dejaría el hueco por donde se cuadra cualquier diferencia.

        **Solo se comparan unidades que aparecen en los dos lados.** Una
        evaporación entra en litros y sale en kilos: ahí no hay exceso, hay una
        transformación, y sin un factor de conversión declarado cualquier
        comparación sería inventada. Cuando la unidad aparece solo en las
        salidas, el balance no dice nada — y decir nada es lo correcto, en vez
        de rechazar una corrida legítima.
        """
        from django.db.models import Sum

        if self.cantidad is None or not self.ejecucion_id:
            return

        unidad = (self.unidad or "").strip().lower()

        def total(consulta):
            return consulta.filter(unidad__iexact=unidad).aggregate(
                t=Sum("cantidad")
            )["t"] or Decimal("0")

        entro = total(self.ejecucion.entradas)

        # Sin entradas en esta unidad no hay con qué comparar: es el caso de
        # la transformación, no el de un exceso.
        if entro <= 0:
            return

        salio = total(self.ejecucion.salidas.exclude(pk=self.pk))

        if salio + self.cantidad > entro:
            raise ValidationError({
                "cantidad": (
                    f"Entraron {entro} {self.unidad} y ya salieron {salio}: "
                    f"quedan {entro - salio}. No puede salir más de lo que entró."
                )
            })


class EventoProceso(models.Model):
    ejecucion = models.ForeignKey(
        EjecucionProceso, on_delete=models.PROTECT, related_name="eventos"
    )
    tipo = models.CharField(max_length=40)
    estado_anterior = models.CharField(max_length=25, blank=True)
    estado_nuevo = models.CharField(max_length=25, blank=True)
    motivo = models.TextField(blank=True)
    datos = models.JSONField(default=dict, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha_hora"]
        indexes = [models.Index(fields=["ejecucion", "fecha_hora"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Los eventos de proceso son inmutables.")
        return super().save(*args, **kwargs)
