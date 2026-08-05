from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


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
        null=True, blank=True,
    )
    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT, related_name="ejecuciones_proceso",
        null=True, blank=True,
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ejecuciones_proceso", null=True, blank=True,
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
        "produccion.Lote", on_delete=models.PROTECT, related_name="entradas_proceso"
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
        ]

    def clean(self):
        if not self.ejecucion.editable:
            raise ValidationError("No se pueden agregar entradas a una ejecución cerrada o cancelada.")

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
        if self.naturaleza != self.Naturaleza.MERMA and not self.lote_id:
            raise ValidationError({"lote": "Toda salida inventariable debe identificar un lote."})
        if self.naturaleza == self.Naturaleza.MERMA and not self.motivo.strip():
            raise ValidationError({"motivo": "Toda merma requiere un motivo."})

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
