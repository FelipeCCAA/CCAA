from decimal import Decimal
from math import sqrt

from django.conf import settings
from django.db import models

from usuarios.models import PerfilUsuario


class Insumo(models.Model):
    class Unidad(models.TextChoices):
        KG = "kg", "Kilogramos"
        L = "L", "Litros"
        UN = "un", "Unidades"

    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=150)
    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    unidad = models.CharField(max_length=5, choices=Unidad.choices)
    contenido_envase = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    stock_actual = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    demanda_anual = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    costo_por_pedido = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    costo_mantencion_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    plazo_reposicion_dias = models.PositiveIntegerField(default=0)
    consumo_diario = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["area", "nombre"]

    @property
    def eoq(self):
        if self.demanda_anual <= 0 or self.costo_por_pedido <= 0 or self.costo_mantencion_unitario <= 0:
            return None
        return Decimal(str(sqrt(float(2 * self.demanda_anual * self.costo_por_pedido / self.costo_mantencion_unitario))))

    @property
    def punto_reposicion(self):
        return self.consumo_diario * self.plazo_reposicion_dias

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class ConsumoProducto(models.Model):
    producto = models.ForeignKey("maestros.Producto", on_delete=models.CASCADE, related_name="consumos_inventario")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="consumos")
    cantidad_por_kg = models.DecimalField(max_digits=14, decimal_places=6)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["producto", "insumo"], name="consumo_unico_producto_insumo")]


class CicloCIP(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        EN_CURSO = "en_curso", "En curso"
        COMPLETADO = "completado", "Completado"
        OBSERVADO = "observado", "Observado"

    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    equipo = models.CharField(max_length=120)
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROGRAMADO)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-inicio"]
