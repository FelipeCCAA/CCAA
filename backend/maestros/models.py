"""
Maestros del proceso productivo: mandantes, productos y especificaciones.

Traducción de las entidades `mandante`, `producto` y `especificacion` de
`prototipo/js/modelo/esquema.js`. Las decisiones de modelado y su justificación
están en `prototipo/MODELO_DATOS.md`.
"""

from django.core.exceptions import ValidationError
from django.db import models

from .catalogos import CLAVES_PARAMETROS


class Mandante(models.Model):
    """Empresa dueña del producto elaborado. Incluye la marca propia CCAA."""

    nombre = models.CharField("Nombre", max_length=120, unique=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Mandante"
        verbose_name_plural = "Mandantes"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """
    Producto terminado, intermedio o materia prima.

    El mandante es un campo propio: no se deduce del nombre del producto.
    """

    class Familia(models.TextChoices):
        POLVO = "polvo", "Polvo"
        CREMA = "crema", "Crema"
        LIQUIDO = "liquido", "Líquido"
        OTRO = "otro", "Otro"

    class Naturaleza(models.TextChoices):
        """Dónde está el producto en la cadena de transformación."""

        MATERIA_PRIMA = "materia_prima", "Materia prima"
        INTERMEDIO = "intermedio", "Intermedio"
        TERMINADO = "terminado", "Terminado"

    class Unidad(models.TextChoices):
        KG = "kg", "Kilogramos"
        L = "L", "Litros"

    codigo = models.CharField("Código", max_length=60, blank=True)
    nombre = models.CharField("Nombre", max_length=180)
    familia = models.CharField("Familia", max_length=20, choices=Familia.choices)
    naturaleza = models.CharField(
        "Naturaleza",
        max_length=20,
        choices=Naturaleza.choices,
        default=Naturaleza.TERMINADO,
        help_text="Dónde está en la cadena: materia prima, intermedio o terminado",
    )
    unidad_base = models.CharField(
        "Unidad base",
        max_length=5,
        choices=Unidad.choices,
        default=Unidad.KG,
        help_text="Unidad en que se mide: la leche en litros, el polvo y la crema en kilos",
    )
    mandante = models.ForeignKey(
        Mandante,
        on_delete=models.PROTECT,
        related_name="productos",
        verbose_name="Mandante",
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["nombre", "mandante"],
                name="producto_unico_por_mandante",
            )
        ]

    def __str__(self):
        return self.nombre


class Especificacion(models.Model):
    """
    Rangos de calidad aceptables de un producto, versionados en el tiempo.

    Un lote se audita contra la versión vigente en SU fecha de producción, no
    contra la actual (MODELO_DATOS.md §2.3). Sin esto no se puede responder a
    una auditoría que pregunte por qué se liberó un lote de hace seis meses.
    """

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="especificaciones",
        verbose_name="Producto",
    )
    version = models.PositiveIntegerField("Versión", default=1)
    vigente_desde = models.DateField("Vigente desde")
    vigente_hasta = models.DateField(
        "Vigente hasta",
        null=True,
        blank=True,
        help_text="Vacío = vigente indefinidamente",
    )
    rangos = models.JSONField(
        "Rangos por parámetro",
        default=dict,
        help_text='{"humedad": {"min": 2.5, "max": 4.0, "obligatorio": true}, ...}',
    )
    fuente = models.CharField(
        "Fuente",
        max_length=250,
        blank=True,
        help_text="Documento o acuerdo que respalda la especificación",
    )

    class Meta:
        verbose_name = "Especificación de calidad"
        verbose_name_plural = "Especificaciones de calidad"
        ordering = ["producto__nombre", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "version"],
                name="especificacion_version_unica_por_producto",
            )
        ]

    def __str__(self):
        return f"{self.producto} · v{self.version}"

    def clean(self):
        """Valida la forma de `rangos`, que por ser JSON la base no valida."""
        if not isinstance(self.rangos, dict):
            raise ValidationError({"rangos": "Debe ser un objeto de parámetros."})

        desconocidos = set(self.rangos) - CLAVES_PARAMETROS
        if desconocidos:
            raise ValidationError(
                {"rangos": f"Parámetros no reconocidos: {', '.join(sorted(desconocidos))}"}
            )

        for parametro, rango in self.rangos.items():
            if not isinstance(rango, dict):
                raise ValidationError(
                    {"rangos": f"El rango de '{parametro}' debe ser un objeto."}
                )

            minimo, maximo = rango.get("min"), rango.get("max")

            for etiqueta, valor in (("min", minimo), ("max", maximo)):
                if valor is not None and not isinstance(valor, (int, float)):
                    raise ValidationError(
                        {"rangos": f"El '{etiqueta}' de '{parametro}' debe ser numérico."}
                    )

            if minimo is not None and maximo is not None and minimo > maximo:
                raise ValidationError(
                    {"rangos": f"En '{parametro}' el mínimo es mayor que el máximo."}
                )

        if (
            self.vigente_hasta is not None
            and self.vigente_desde is not None
            and self.vigente_hasta < self.vigente_desde
        ):
            raise ValidationError(
                {"vigente_hasta": "No puede ser anterior a la fecha de inicio de vigencia."}
            )
