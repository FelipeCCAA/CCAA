import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from maestros.models import Vehiculo


class RutaRecoleccion(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        EN_CURSO = "en_curso", "En curso"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    codigo = models.CharField(max_length=60, unique=True)
    fecha = models.DateField(db_index=True)
    conductor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rutas_recoleccion",
        null=True,
        blank=True,
    )
    vehiculo = models.ForeignKey(
        Vehiculo, on_delete=models.PROTECT, related_name="rutas_recoleccion"
    )
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PROGRAMADA, db_index=True
    )
    observacion = models.TextField(blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rutas_recoleccion_creadas",
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha", "codigo"]
        indexes = [models.Index(fields=["fecha", "estado"])]

    def __str__(self):
        return f"{self.codigo} · {self.fecha}"


class ParadaRuta(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        COMPLETADA = "completada", "Completada"
        NO_CARGADA = "no_cargada", "No cargada"

    ruta = models.ForeignKey(
        RutaRecoleccion, on_delete=models.PROTECT, related_name="paradas"
    )
    orden = models.PositiveSmallIntegerField()
    proveedor = models.CharField(max_length=160)
    predio = models.CharField(max_length=160)
    sala = models.CharField(max_length=120, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    llegada = models.DateTimeField(null=True, blank=True)
    salida = models.DateTimeField(null=True, blank=True)
    observacion = models.TextField(blank=True)

    class Meta:
        ordering = ["ruta", "orden"]
        constraints = [
            models.UniqueConstraint(
                fields=["ruta", "orden"], name="parada_orden_unico_por_ruta"
            )
        ]

    def __str__(self):
        return f"{self.ruta.codigo} · {self.orden} · {self.predio}"


class Recoleccion(models.Model):
    class Alcohol(models.TextChoices):
        CONFORME = "conforme", "Conforme"
        NO_CONFORME = "no_conforme", "No conforme"

    class Estado(models.TextChoices):
        REGISTRADA = "registrada", "Registrada"
        CARGADA = "cargada", "Cargada"
        RECHAZADA = "rechazada", "No cargada"

    idempotencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    parada = models.OneToOneField(
        ParadaRuta, on_delete=models.PROTECT, related_name="recoleccion"
    )
    fecha_hora = models.DateTimeField()
    litros_medidos = models.DecimalField(max_digits=12, decimal_places=2)
    temperatura = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    alcohol = models.CharField(max_length=20, choices=Alcohol.choices)
    codigo_muestra = models.CharField(max_length=80, blank=True)
    estado = models.CharField(
        max_length=20, choices=Estado.choices, default=Estado.REGISTRADA, db_index=True
    )
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recolecciones_registradas",
    )
    observacion = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_hora"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros_medidos__gt=0),
                name="recoleccion_litros_positivos",
            ),
            models.UniqueConstraint(
                fields=["codigo_muestra"],
                condition=~models.Q(codigo_muestra=""),
                name="muestra_recoleccion_unica",
            ),
        ]

    def clean(self):
        if self.alcohol == self.Alcohol.CONFORME and not self.codigo_muestra.strip():
            raise ValidationError(
                {"codigo_muestra": "Una carga conforme debe identificar su muestra."}
            )
        if self.alcohol == self.Alcohol.NO_CONFORME and self.estado == self.Estado.CARGADA:
            raise ValidationError("La leche con alcohol no conforme no puede cargarse.")

    def __str__(self):
        return f"{self.parada} · {self.litros_medidos} L"


class CargaModulo(models.Model):
    codigo = models.CharField(max_length=80, unique=True)
    recoleccion = models.ForeignKey(
        Recoleccion, on_delete=models.PROTECT, related_name="cargas"
    )
    modulo = models.CharField(max_length=40)
    estanque_origen = models.CharField(max_length=60, blank=True)
    litros = models.DecimalField(max_digits=12, decimal_places=2)
    cargada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recoleccion", "modulo", "estanque_origen"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros__gt=0), name="carga_modulo_litros_positivos"
            ),
            models.UniqueConstraint(
                fields=["recoleccion", "modulo", "estanque_origen"],
                name="carga_unica_modulo_estanque_recoleccion",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} · {self.modulo} · {self.litros} L"

