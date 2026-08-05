from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class PlanPreventivo(models.Model):
    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT, related_name="planes_preventivos"
    )
    nombre = models.CharField(max_length=160)
    frecuencia_dias = models.PositiveIntegerField()
    duracion_estimada_min = models.PositiveIntegerField(default=60)
    ultima_ejecucion = models.DateField(null=True, blank=True)
    proxima_ejecucion = models.DateField(db_index=True)
    instrucciones = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["proxima_ejecucion", "equipo"]
        constraints = [
            models.UniqueConstraint(
                fields=["equipo", "nombre"], name="plan_preventivo_unico_equipo"
            ),
            models.CheckConstraint(
                condition=models.Q(frecuencia_dias__gt=0), name="plan_frecuencia_positiva"
            ),
        ]

    def __str__(self):
        return f"{self.equipo} · {self.nombre}"


class OrdenTrabajo(models.Model):
    class Tipo(models.TextChoices):
        PREVENTIVA = "preventiva", "Preventiva"
        CORRECTIVA = "correctiva", "Correctiva"
        INSPECCION = "inspeccion", "Inspección"

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        PROGRAMADA = "programada", "Programada"
        ASIGNADA = "asignada", "Asignada"
        EJECUCION = "ejecucion", "En ejecución"
        ESPERA = "espera", "En espera"
        PRUEBA = "prueba", "En prueba"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    TRANSICIONES = {
        Estado.BORRADOR: {Estado.PROGRAMADA, Estado.CANCELADA},
        Estado.PROGRAMADA: {Estado.ASIGNADA, Estado.CANCELADA},
        Estado.ASIGNADA: {Estado.EJECUCION, Estado.CANCELADA},
        Estado.EJECUCION: {Estado.ESPERA, Estado.PRUEBA},
        Estado.ESPERA: {Estado.EJECUCION, Estado.CANCELADA},
        Estado.PRUEBA: {Estado.CERRADA, Estado.EJECUCION},
        Estado.CERRADA: set(),
        Estado.CANCELADA: set(),
    }

    numero = models.CharField(max_length=40, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.BORRADOR, db_index=True
    )
    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT, related_name="ordenes_trabajo"
    )
    plan = models.ForeignKey(
        PlanPreventivo, on_delete=models.PROTECT, related_name="ordenes",
        null=True, blank=True,
    )
    descripcion = models.TextField()
    prioridad = models.PositiveSmallIntegerField(default=3)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ordenes_mantenimiento", null=True, blank=True,
    )
    programada_para = models.DateTimeField(null=True, blank=True, db_index=True)
    inicio = models.DateTimeField(null=True, blank=True)
    termino = models.DateTimeField(null=True, blank=True)
    minutos_parada = models.PositiveIntegerField(default=0)
    prueba_conforme = models.BooleanField(null=True, blank=True)
    motivo_cierre = models.TextField(blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="ordenes_mantenimiento_creadas", null=True, blank=True,
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["estado", "-prioridad", "programada_para"]
        indexes = [models.Index(fields=["equipo", "estado", "programada_para"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(prioridad__gte=1) & models.Q(prioridad__lte=5),
                name="ot_prioridad_entre_1_y_5",
            ),
            models.CheckConstraint(
                condition=models.Q(termino__isnull=True) | models.Q(inicio__isnull=True)
                | models.Q(termino__gt=models.F("inicio")),
                name="ot_termino_posterior_inicio",
            ),
        ]

    def __str__(self):
        return f"{self.numero} · {self.equipo}"


class FallaEquipo(models.Model):
    class Severidad(models.TextChoices):
        BAJA = "baja", "Baja"
        MEDIA = "media", "Media"
        ALTA = "alta", "Alta"
        CRITICA = "critica", "Crítica"

    equipo = models.ForeignKey(
        "maestros.Equipo", on_delete=models.PROTECT, related_name="fallas"
    )
    orden = models.ForeignKey(
        OrdenTrabajo, on_delete=models.PROTECT, related_name="fallas",
        null=True, blank=True,
    )
    detectada_en = models.DateTimeField(db_index=True)
    severidad = models.CharField(max_length=10, choices=Severidad.choices)
    descripcion = models.TextField()
    detuvo_produccion = models.BooleanField(default=False)
    reportada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="fallas_reportadas", null=True, blank=True,
    )
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detectada_en"]


class RepuestoUtilizado(models.Model):
    """
    Repuesto consumido en una orden de trabajo.

    **El repuesto pasa por bodega**: se pide por MRQ, bodega lo reserva y lo
    entrega, y es esa entrega la que mueve el stock. Este registro no descuenta
    nada — descontarlo aquí lo restaría dos veces.

    Por eso lleva `entrega`: es la línea de entrega que lo respalda, y sin ella
    no hay forma de saber si el material salió por bodega o alguien lo tomó del
    pañol. Las dos cosas se ven idénticas en la orden de trabajo, y en el
    segundo caso el saldo de bodega queda mintiendo sin que nadie se entere.

    Se admite sin respaldo a propósito —una urgencia de madrugada no se detiene
    porque bodega esté cerrada— pero queda marcado. Lo que no se puede es no
    distinguirlo.
    """

    orden = models.ForeignKey(
        OrdenTrabajo, on_delete=models.PROTECT, related_name="repuestos"
    )
    insumo = models.ForeignKey(
        "inventario.Insumo", on_delete=models.PROTECT, related_name="usos_mantenimiento"
    )
    entrega = models.ForeignKey(
        "inventario.DetalleEntregaProduccion",
        on_delete=models.PROTECT,
        related_name="repuestos_mantenimiento",
        null=True,
        blank=True,
        verbose_name="Entrega de bodega que lo respalda",
        help_text=(
            "La línea de entrega con que bodega lo despachó. Sin ella el "
            "consumo no tiene respaldo en el libro de inventario."
        ),
    )
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0), name="repuesto_cantidad_positiva"
            )
        ]

    @property
    def respaldado(self) -> bool:
        """¿Salió por bodega? Se calcula, no se guarda."""
        return self.entrega_id is not None

    def clean(self):
        if self.orden.estado in {OrdenTrabajo.Estado.CERRADA, OrdenTrabajo.Estado.CANCELADA}:
            raise ValidationError("No se agregan repuestos a una orden finalizada.")

        if self.entrega_id is None:
            return

        # El insumo tiene que ser el que bodega entregó. Si no coinciden, uno
        # de los dos está mal y no hay forma de saber cuál — así que ninguno
        # sirve como respaldo del otro.
        entregado = self.entrega.lote.insumo_id

        if self.insumo_id and self.insumo_id != entregado:
            raise ValidationError({
                "entrega": (
                    f"Esa entrega es de {self.entrega.lote.insumo.nombre}, no del "
                    "repuesto indicado."
                )
            })

        # No se puede consumir más de lo que bodega despachó en esa línea. Una
        # entrega puede cubrir varias órdenes, así que se suma lo ya imputado.
        ya_usado = (
            RepuestoUtilizado.objects.filter(entrega_id=self.entrega_id)
            .exclude(pk=self.pk)
            .aggregate(total=models.Sum("cantidad"))["total"]
            or 0
        )

        if ya_usado + (self.cantidad or 0) > self.entrega.cantidad:
            disponible = self.entrega.cantidad - ya_usado
            raise ValidationError({
                "cantidad": (
                    f"Esa entrega despachó {self.entrega.cantidad} y ya tiene "
                    f"{ya_usado} imputado: quedan {disponible}."
                )
            })
