"""
Maestros del proceso productivo: mandantes, productos, especificaciones y el
catálogo de documentos de liberación.

Traducción de las entidades `mandante`, `producto`, `especificacion` y
`documentoLiberacion` de `prototipo/js/modelo/esquema.js`. Las decisiones de
modelado y su justificación están en `prototipo/MODELO_DATOS.md`.
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


class Silo(models.Model):
    """
    Silo o estanque de leche o crema.

    La capacidad permite avisar cuando la ocupación la supera. La ocupación
    NO es un campo: se calcula sumando el libro de movimientos
    (MODELO_DATOS.md §2.4).
    """

    class Tipo(models.TextChoices):
        SILO = "silo", "Silo"
        TK_LD = "tk_ld", "TK Leche descremada"
        TK_CREMA = "tk_crema", "TK Crema"

    codigo = models.CharField("Código", max_length=40, unique=True)
    tipo = models.CharField("Tipo", max_length=20, choices=Tipo.choices)
    capacidad_l = models.DecimalField(
        "Capacidad", max_digits=12, decimal_places=2, help_text="En litros"
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Silo / estanque"
        verbose_name_plural = "Silos y estanques"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacidad_l__gte=0),
                name="silo_capacidad_no_negativa",
            )
        ]

    def __str__(self):
        return self.codigo


class Vehiculo(models.Model):
    """Camión de transporte de leche, con sus choferes por turno."""

    numero = models.CharField("Número", max_length=40, blank=True)
    placa = models.CharField("Placa", max_length=20, unique=True)
    tipo = models.CharField("Tipo", max_length=60, default="Camión")
    capacidad_l = models.DecimalField(
        "Capacidad",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="En litros",
    )
    transportista = models.CharField("Transportista", max_length=150, blank=True)
    chofer_am = models.CharField("Chofer A.M.", max_length=150, blank=True)
    chofer_pm = models.CharField("Chofer P.M.", max_length=150, blank=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Camión"
        verbose_name_plural = "Camiones"
        ordering = ["placa"]

    def __str__(self):
        return f"{self.placa} · {self.transportista}" if self.transportista else self.placa


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


class DocumentoLiberacion(models.Model):
    """
    Un documento del checklist de liberación y, en `plantilla`, los campos de
    su formulario.

    La decisión que gobierna este modelo (MODELO_DATOS.md §2.6): los
    formularios son DATOS, no código. La interfaz dibuja la plantilla, así que
    Calidad cambia un campo desde Administración y el formulario cambia, sin
    tocar código ni volver a desplegar. No hay diecinueve formularios escritos
    a mano esperando a que alguien los mantenga.

    Dos atributos de un campo hacen el trabajo que el papel no puede:

    - `origen` ("lote.codigo_lote") lo rellena con lo que el sistema ya sabe.
      Nadie vuelve a teclear el lote ni la fecha, y por tanto nadie los teclea
      mal.
    - `parametro` ("mg") lo ata a un fisicoquímico, y al escribirlo se coteja
      contra el análisis del lote y la especificación vigente. Un formulario
      que no cuadra con el laboratorio es exactamente lo que una auditoría
      busca y lo que en papel no aparece nunca.

    Qué documentos aplican a qué familia está pendiente de definir con Calidad
    (MODELO_DATOS.md §8.3). Es una pregunta de datos, no de código: se responde
    cargando el catálogo, no modificando este archivo.
    """

    class Area(models.TextChoices):
        """
        Etapa del flujo que genera el registro.

        Reproduce el orden del Dossier de Liberación (CCAA.Calidad.FORM.023):
        Recepción → Condensación → Secado → Envase. Sirve para saber **qué
        área tiene el registro pendiente**, que es la pregunta que hoy se
        responde llamando por teléfono.
        """

        RECEPCION = "recepcion", "Recepción"
        CONDENSACION = "condensacion", "Condensación"
        SECADO = "secado", "Secado"
        ENVASE = "envase", "Envase"
        CALIDAD = "calidad", "Calidad"

    # Tipos que la interfaz sabe dibujar. `id` y `ref` del esquema del
    # prototipo quedan fuera a propósito: un campo de formulario no es una
    # identidad ni una llave foránea.
    TIPOS_CAMPO = {
        "texto",
        "entero",
        "decimal",
        "fecha",
        "fechaHora",
        "hora",
        "booleano",
        "enum",
        "lista",
        "objeto",
    }

    codigo = models.CharField(
        "Código",
        max_length=80,
        blank=True,
        help_text="Ej: CCAA.Calidad.FORM.016.02",
    )
    nombre = models.CharField("Nombre", max_length=200)
    area = models.CharField(
        "Área de origen",
        max_length=20,
        choices=Area.choices,
        blank=True,
        help_text="Etapa del flujo que genera el registro",
    )
    aplica_a = models.JSONField(
        "Aplica a",
        default=list,
        help_text='Familias de producto que lo exigen: ["polvo", "crema"]',
    )
    instruccion = models.TextField(
        "Instrucción",
        blank=True,
        help_text="Qué debe verificar quien lo completa",
    )
    plantilla = models.JSONField(
        "Plantilla del formulario",
        default=list,
        blank=True,
        help_text=(
            '[{"clave": "mg", "etiqueta": "Materia grasa", "tipo": "decimal", '
            '"req": true, "parametro": "mg"}, ...]. Vacía = solo atestación'
        ),
    )
    fuente = models.CharField(
        "Fuente",
        max_length=250,
        blank=True,
        help_text="De dónde salió la plantilla. Marque las provisorias",
    )
    orden = models.PositiveIntegerField(
        "Orden", default=0, help_text="Posición en el checklist"
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Documento de liberación"
        verbose_name_plural = "Documentos de liberación"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["codigo"],
                condition=~models.Q(codigo=""),
                name="documento_liberacion_codigo_unico",
            )
        ]

    def __str__(self):
        return f"{self.codigo} · {self.nombre}" if self.codigo else self.nombre

    def clean(self):
        """
        Valida `aplica_a` y `plantilla`, que por ser JSON la base no valida.

        Se valida aquí y no al dibujar el formulario porque una plantilla mal
        escrita no falla: se muestra a medias. Un campo con el `tipo` mal
        tecleado simplemente no aparece, y quien completa el registro en planta
        no tiene forma de notar que falta.
        """
        self._validar_aplica_a()
        self._validar_plantilla()

    def _validar_aplica_a(self):
        if not isinstance(self.aplica_a, list):
            raise ValidationError({"aplica_a": "Debe ser una lista de familias."})

        if not self.aplica_a:
            raise ValidationError(
                {"aplica_a": "Debe indicar al menos una familia; si no, no se exige nunca."}
            )

        familias = set(Producto.Familia.values)
        desconocidas = [f for f in self.aplica_a if f not in familias]

        if desconocidas:
            raise ValidationError(
                {
                    "aplica_a": (
                        f"Familias no reconocidas: {', '.join(map(str, desconocidas))}. "
                        f"Las válidas son: {', '.join(sorted(familias))}."
                    )
                }
            )

    def _validar_plantilla(self):
        if not isinstance(self.plantilla, list):
            raise ValidationError({"plantilla": "Debe ser una lista de campos."})

        claves = []

        for posicion, campo in enumerate(self.plantilla, start=1):
            if not isinstance(campo, dict):
                raise ValidationError(
                    {"plantilla": f"El campo {posicion} debe ser un objeto."}
                )

            clave = campo.get("clave")
            if not clave:
                raise ValidationError(
                    {"plantilla": f"El campo {posicion} no tiene 'clave'."}
                )
            claves.append(clave)

            if not campo.get("etiqueta"):
                raise ValidationError(
                    {"plantilla": f"El campo '{clave}' no tiene 'etiqueta' que mostrar."}
                )

            tipo = campo.get("tipo")
            if tipo not in self.TIPOS_CAMPO:
                raise ValidationError(
                    {
                        "plantilla": (
                            f"El campo '{clave}' tiene un tipo no reconocido: {tipo!r}. "
                            f"Los válidos son: {', '.join(sorted(self.TIPOS_CAMPO))}."
                        )
                    }
                )

            if tipo == "enum" and not campo.get("valores"):
                raise ValidationError(
                    {"plantilla": f"El campo '{clave}' es 'enum' y no declara sus 'valores'."}
                )

            # MODELO_DATOS.md §2.6: un campo objeto sin `campos` declarados cae
            # en un cuadro de JSON crudo, inservible para quien lo completa en
            # planta.
            if tipo == "objeto" and not campo.get("campos"):
                raise ValidationError(
                    {
                        "plantilla": (
                            f"El campo '{clave}' es 'objeto' y no declara sus 'campos'. "
                            "Sin ellos la interfaz solo puede mostrar JSON crudo."
                        )
                    }
                )

            parametro = campo.get("parametro")
            if parametro is not None and parametro not in CLAVES_PARAMETROS:
                raise ValidationError(
                    {
                        "plantilla": (
                            f"El campo '{clave}' se ata al parámetro '{parametro}', "
                            "que no existe en el catálogo de fisicoquímicos."
                        )
                    }
                )

            for limite in ("min", "max"):
                valor = campo.get(limite)
                if valor is not None and not isinstance(valor, (int, float)):
                    raise ValidationError(
                        {"plantilla": f"El '{limite}' del campo '{clave}' debe ser numérico."}
                    )

            minimo, maximo = campo.get("min"), campo.get("max")
            if minimo is not None and maximo is not None and minimo > maximo:
                raise ValidationError(
                    {"plantilla": f"En el campo '{clave}' el mínimo es mayor que el máximo."}
                )

        repetidas = {c for c in claves if claves.count(c) > 1}
        if repetidas:
            raise ValidationError(
                {
                    "plantilla": (
                        f"Claves repetidas: {', '.join(sorted(repetidas))}. "
                        "Los valores se guardan por clave, así que una repetida se pisa."
                    )
                }
            )
