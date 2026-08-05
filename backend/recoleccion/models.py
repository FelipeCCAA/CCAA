"""
Recolección de leche en predios: el primer eslabón de la cadena.

Hasta aquí el sistema sabía de la leche recién cuando el camión llegaba a
fábrica. Todo lo anterior —qué predio, de qué proveedor, quién la midió, si
pasó la prueba de alcohol antes de subir al camión— no existía, y por eso la
trazabilidad hacia atrás (`docs/REGLAS_DE_PLANTA.md` §6) se cortaba.

**Por qué una app propia y no `maestros`.** Los proveedores, predios y
conductores son maestros, sí, pero nacen de este proceso y van a crecer con él
—rutas, programación, vouchers, sincronización desde el camión—. Es el mismo
criterio con que `inocuidad` se separó de `produccion`: mover modelos entre
apps de Django después obliga a renombrar tablas a mano, así que la separación
se hace ahora, con cinco modelos, en vez de cuando haya doce.

**Lo que sí se reutiliza es `maestros.Vehiculo`**: el camión y el carro son los
mismos vehículos que ya usa la recepción. Crear un `Camion` aquí habría dejado
la misma placa en dos tablas, y con dos tablas hay dos verdades.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ProveedorLeche(models.Model):
    """
    Quien entrega la leche cruda.

    No es `inventario.Proveedor`: aquel vende materiales contra una orden de
    compra y este entrega materia prima que se paga por litro y calidad. Meter
    los dos en la misma tabla dejaría la mitad de los campos en blanco en cada
    fila, y haría convivir un bloqueo por antibióticos con un plazo de
    reposición.
    """

    rut = models.CharField("RUT", max_length=20, unique=True)
    nombre = models.CharField("Nombre", max_length=160)
    activo = models.BooleanField("Activo", default=True)

    # Un proveedor bloqueado no puede entregar leche. Lo activará la cadena de
    # antibióticos del flujo de fábrica (§1.2 de las reglas de planta), que
    # todavía no está implementada: el campo existe ahora para que cuando lo
    # esté no haya que migrar, y porque un bloqueo escrito en una observación
    # no bloquea nada.
    bloqueado = models.BooleanField("Bloqueado", default=False)
    motivo_bloqueo = models.TextField("Motivo del bloqueo", blank=True)

    class Meta:
        verbose_name = "Proveedor de leche"
        verbose_name_plural = "Proveedores de leche"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.bloqueado and not self.motivo_bloqueo.strip():
            raise ValidationError({
                "motivo_bloqueo": (
                    "Un proveedor bloqueado sin motivo no se puede desbloquear "
                    "con criterio: nadie sabe qué tendría que corregirse."
                )
            })


class Predio(models.Model):
    """
    El campo donde está la leche. Un proveedor puede tener varios.

    Es la unidad de la que se recolecta, y el eslabón que la trazabilidad hacia
    atrás necesita para llegar del lote al origen.
    """

    proveedor = models.ForeignKey(
        ProveedorLeche, on_delete=models.PROTECT, related_name="predios"
    )
    codigo = models.CharField("Código", max_length=40)
    nombre = models.CharField("Nombre", max_length=160)
    comuna = models.CharField("Comuna", max_length=120, blank=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Predio"
        verbose_name_plural = "Predios"
        ordering = ["proveedor", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["proveedor", "codigo"], name="predio_codigo_unico_proveedor"
            )
        ]

    def __str__(self):
        return f"{self.nombre} · {self.proveedor.nombre}"


class Conductor(models.Model):
    """
    Quien conduce y mide en el predio.

    Es un modelo y no un texto libre porque **firma**: el registro que se llena
    frente al estanque lo respalda una persona, y «Juan» escrito a mano no es
    nadie. `maestros.Vehiculo` guarda hoy los choferes como texto
    (`chofer_am`, `chofer_pm`); esos campos siguen ahí para la recepción, y
    esta es la referencia real de aquí en adelante.

    No es un `User`: la mayoría de los conductores no entra al sistema.
    """

    rut = models.CharField("RUT", max_length=20, unique=True)
    nombre = models.CharField("Nombre", max_length=160)
    telefono = models.CharField("Teléfono", max_length=40, blank=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Conductor"
        verbose_name_plural = "Conductores"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Modulo(models.Model):
    """
    Estanque del camión donde se carga la leche.

    Es la unidad que la recepción muestrea, y la que se bloquea cuando un
    análisis sale positivo («bloquear módulos asociados», §1.2 de las reglas de
    planta). Sin él, esa regla no se puede ni expresar.
    """

    vehiculo = models.ForeignKey(
        "maestros.Vehiculo", on_delete=models.PROTECT, related_name="modulos"
    )
    numero = models.CharField("Número", max_length=20)
    capacidad_l = models.DecimalField(
        "Capacidad", max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="En litros",
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Módulo"
        verbose_name_plural = "Módulos"
        ordering = ["vehiculo", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehiculo", "numero"], name="modulo_numero_unico_vehiculo"
            )
        ]

    def __str__(self):
        return f"{self.vehiculo.placa} · módulo {self.numero}"


class Recoleccion(models.Model):
    """
    Una salida del camión a recolectar: su ruta del día.

    Agrupa las cargas de todos los predios que visita. El código es lo que
    después viaja a recepción para enlazar el camión que llegó con lo que
    recogió.
    """

    class Estado(models.TextChoices):
        PROGRAMADA = "programada", "Programada"
        EN_RUTA = "en_ruta", "En ruta"
        COMPLETADA = "completada", "Completada"
        CANCELADA = "cancelada", "Cancelada"

    codigo = models.CharField("Código de recolección", max_length=40, unique=True)
    fecha = models.DateField("Fecha")
    conductor = models.ForeignKey(
        Conductor, on_delete=models.PROTECT, related_name="recolecciones"
    )
    camion = models.ForeignKey(
        "maestros.Vehiculo", on_delete=models.PROTECT, related_name="recolecciones"
    )
    carro = models.ForeignKey(
        "maestros.Vehiculo", on_delete=models.PROTECT,
        related_name="recolecciones_carro", null=True, blank=True,
        help_text="El acoplado, si lo lleva.",
    )
    estado = models.CharField(
        "Estado", max_length=20, choices=Estado.choices, default=Estado.PROGRAMADA
    )
    observaciones = models.TextField("Observaciones", blank=True)
    registrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="recolecciones_registradas", null=True, blank=True,
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Recolección"
        verbose_name_plural = "Recolecciones"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.codigo} · {self.fecha}"

    @property
    def litros_cargados(self):
        """Solo lo que efectivamente subió al camión. Se calcula del detalle."""
        return sum((c.litros for c in self.cargas.all() if c.cargada), Decimal("0"))

    @property
    def predios_rechazados(self):
        """Dónde se dejó la leche. Es lo que hay que informarle al proveedor."""
        return [c.predio.nombre for c in self.cargas.all() if not c.cargada]

    def clean(self):
        if self.carro_id and self.carro_id == self.camion_id:
            raise ValidationError({
                "carro": "El carro no puede ser el mismo vehículo que el camión."
            })


class CargaPredio(models.Model):
    """
    Lo medido en un predio, y si se cargó o no.

    Es el registro que el conductor llena frente al estanque: litros,
    temperatura, prueba de alcohol y evaluación visual.

    **La prueba de alcohol decide si la leche sube al camión.** Con resultado
    positivo no se carga — pero sí se toma muestra y se registra la desviación,
    porque el problema hay que poder reconstruirlo después aunque la leche se
    haya quedado en el predio.
    """

    class Alcohol(models.TextChoices):
        NEGATIVA = "negativa", "Negativa (conforme)"
        POSITIVA = "positiva", "Positiva (no conforme)"

    class Visual(models.TextChoices):
        CONFORME = "conforme", "Conforme"
        NO_CONFORME = "no_conforme", "No conforme"

    recoleccion = models.ForeignKey(
        Recoleccion, on_delete=models.CASCADE, related_name="cargas"
    )
    predio = models.ForeignKey(
        Predio, on_delete=models.PROTECT, related_name="cargas"
    )
    modulo = models.ForeignKey(
        Modulo, on_delete=models.PROTECT, related_name="cargas",
        null=True, blank=True,
        help_text="En qué módulo se cargó. Vacío si no se cargó.",
    )

    litros = models.DecimalField("Litros", max_digits=12, decimal_places=2)
    temperatura = models.DecimalField(
        "Temperatura", max_digits=5, decimal_places=2,
        help_text="En °C. El objetivo en predio es ~4 °C.",
    )
    alcohol = models.CharField(
        "Prueba de alcohol", max_length=10, choices=Alcohol.choices
    )
    visual = models.CharField(
        "Evaluación visual", max_length=15, choices=Visual.choices,
        default=Visual.CONFORME,
    )

    # Se toma muestra en los dos casos: si está conforme, para el análisis de
    # recepción; si no, para poder demostrar por qué se rechazó.
    muestra_tomada = models.BooleanField("Muestra tomada", default=False)

    cargada = models.BooleanField(
        "Se cargó al camión", default=True,
        help_text="Falso cuando la leche se quedó en el predio.",
    )
    observaciones = models.TextField("Observaciones", blank=True)
    registrada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Carga en predio"
        verbose_name_plural = "Cargas en predio"
        ordering = ["recoleccion", "id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(litros__gt=0), name="carga_litros_positivos"
            ),
            # Cargada exige módulo: leche que subió al camión y no sabe a qué
            # estanque rompe la trazabilidad justo donde empieza.
            models.CheckConstraint(
                condition=models.Q(cargada=False) | models.Q(modulo__isnull=False),
                name="carga_cargada_indica_modulo",
            ),
        ]

    def __str__(self):
        return f"{self.predio.nombre} · {self.litros} L"

    def clean(self):
        # La regla dura del proceso: alcohol positivo, no se carga.
        if self.alcohol == self.Alcohol.POSITIVA and self.cargada:
            raise ValidationError({
                "cargada": (
                    "La prueba de alcohol salió positiva: esa leche no sube al "
                    "camión. Regístrala como no cargada y deja la desviación en "
                    "las observaciones."
                )
            })

        if self.visual == self.Visual.NO_CONFORME and self.cargada:
            raise ValidationError({
                "cargada": (
                    "La evaluación visual salió no conforme: la leche no se "
                    "carga sin que Calidad lo autorice."
                )
            })

        # Sin motivo escrito no se puede explicar después por qué se dejó la
        # leche, que es justo lo que hay que informarle al proveedor.
        if not self.cargada and not self.observaciones.strip():
            raise ValidationError({
                "observaciones": (
                    "Si la leche no se cargó hay que decir por qué: es la "
                    "desviación que después se le informa al proveedor."
                )
            })

        if self.predio_id and self.predio.proveedor.bloqueado and self.cargada:
            raise ValidationError({
                "predio": (
                    f"El proveedor {self.predio.proveedor.nombre} está "
                    "bloqueado: no se le puede recolectar."
                )
            })
