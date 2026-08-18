"""
Maestros del proceso productivo: mandantes, productos, especificaciones y el
catálogo de documentos de liberación.

Traducción de las entidades `mandante`, `producto`, `especificacion` y
`documentoLiberacion` de `prototipo/js/modelo/esquema.js`. Las decisiones de
modelado y su justificación están en `prototipo/MODELO_DATOS.md`.
"""

from django.core.exceptions import ValidationError
from django.db import models

from usuarios.models import Empresa, Sucursal
from usuarios.tenancy import (
    empresa_predeterminada_pruebas,
    sucursal_predeterminada_pruebas,
)

from .catalogos import CLAVES_PARAMETROS


class Mandante(models.Model):
    """Empresa dueña del producto elaborado. Incluye la marca propia CCAA."""

    class Cliente(models.TextChoices):
        """Segmento «cliente» del SKU. Las claves son las de `catalogos_sku`."""

        NO_DEFINIDO = "no_definido", "Cliente no definido (producto propio CCAA)"
        NESTLE = "nestle", "Nestlé"
        COLUN = "colun", "Colun"
        SOPROLE = "soprole", "Soprole"

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="mandantes",
        default=empresa_predeterminada_pruebas,
    )
    nombre = models.CharField("Nombre", max_length=120)
    codigo_cliente = models.CharField(
        "Código de cliente (SKU)",
        max_length=20,
        choices=Cliente.choices,
        blank=True,
        help_text=(
            "Qué cliente representa este mandante dentro del SKU. Sin esto, "
            "sus productos no pueden generar SKU."
        ),
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Mandante"
        verbose_name_plural = "Mandantes"
        ordering = ["nombre"]
        constraints = [
            # Un código de cliente, un mandante. El segmento del SKU no tiene
            # forma de distinguir dos mandantes que lo compartan: sus productos
            # saldrían con SKU idénticos —y con el mismo código de lote, que
            # lleva el SKU dentro—. La base de desarrollo llegó a tener
            # «Nestle» y «Nestlé» a la vez, y los productos de un mismo cliente
            # quedaron repartidos entre las dos fichas.
            #
            # Los vacíos sí se repiten: un mandante sin código es uno que
            # todavía no genera SKU, y puede haber varios así.
            models.UniqueConstraint(
                fields=["empresa", "codigo_cliente"],
                condition=~models.Q(codigo_cliente=""),
                name="mandante_unico_por_codigo_cliente",
            ),
            models.UniqueConstraint(
                fields=["empresa", "nombre"],
                name="mandante_nombre_unico_empresa",
            ),
        ]

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

    # ------------------------------------------------ segmentos del SKU
    #
    # Las claves son las de `catalogos_sku`, no un juego paralelo:
    # `tests_sku_modelo` comprueba que no se separen. Si divergieran, el
    # desplegable de la pantalla ofrecería valores que el generador rechaza.

    class NaturalezaComercial(models.TextChoices):
        """
        Para quién se fabrica. **No** es `Producto.naturaleza`, que dice dónde
        está el producto en la cadena (materia prima / intermedio / terminado).
        Comparten nombre y no significan lo mismo.
        """

        SERVICIO_TERCEROS = "servicio_terceros", "Servicio a terceros"
        PRODUCTO_PROPIO = "producto_propio", "Producto propio"

    class Categoria(models.TextChoices):
        LECHE_POLVO = "leche_polvo", "Leche en polvo"
        PRECONDENSADO = "precondensado", "Precondensado"
        CREMA = "crema", "Crema"
        MANTEQUILLA = "mantequilla", "Mantequilla"
        MATERIALES_DIVERSOS = "materiales_diversos", "Materiales diversos"
        LECHE_FRESCA_EST = "leche_fresca_est", "Leche fresca estandarizada"
        SUERO = "suero", "Suero"
        EXTRACTO_MALTA = "extracto_malta", "Extracto de malta"
        LP_INSTANTANEA = "lp_instantanea", "Leche en polvo instantánea"
        LP_CON_LECITINA = "lp_con_lecitina", "Leche en polvo con lecitina"
        LECHE_FLUIDA = "leche_fluida", "Leche fluida"

    class TipoProducto(models.TextChoices):
        ENTERA = "entera", "Entera"
        SEMIDESCREMADA = "semidescremada", "Semidescremada"
        DESCREMADA = "descremada", "Descremada"
        CON_SAL = "con_sal", "Con sal"
        SIN_SAL = "sin_sal", "Sin sal"
        SIN_ESPECIFICAR = "sin_especificar", "Sin especificar"
        NO_DEFINIDO = "no_definido", "No definido"
        ESTANDARIZADA = "estandarizada", "Estandarizada"

    class Formato(models.TextChoices):
        GRANEL = "granel", "Granel"
        SACO_25KG = "saco_25kg", "Saco 25 kg"
        CAJA_20KG = "caja_20kg", "Caja 20 kg"

    class Mercado(models.TextChoices):
        LOCAL = "local", "Local"
        EXPORTACION = "exportacion", "Exportación"

    codigo = models.CharField(
        "SKU",
        max_length=60,
        blank=True,
        help_text=(
            "Derivado de los atributos de abajo; se recalcula al guardar. Un "
            "producto sin ellos conserva el código que tenga, para poder "
            "registrar los códigos antiguos de planta."
        ),
    )
    naturaleza_comercial = models.CharField(
        "Naturaleza comercial (SKU)",
        max_length=20,
        choices=NaturalezaComercial.choices,
        blank=True,
    )
    categoria = models.CharField(
        "Categoría (SKU)", max_length=25, choices=Categoria.choices, blank=True
    )
    tipo = models.CharField(
        "Tipo (SKU)", max_length=20, choices=TipoProducto.choices, blank=True
    )
    formato = models.CharField(
        "Formato (SKU)", max_length=15, choices=Formato.choices, blank=True
    )
    mercado = models.CharField(
        "Mercado (SKU)",
        max_length=15,
        choices=Mercado.choices,
        default=Mercado.LOCAL,
        blank=True,
    )
    variante = models.PositiveSmallIntegerField(
        "Variante (SKU)",
        null=True,
        blank=True,
        help_text=(
            "Correlativo de dos dígitos para desempatar dos productos que "
            "comparten los seis segmentos. Déjalo vacío salvo que haga falta."
        ),
    )
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

    # ----------------------------------------------------------------- SKU

    #: Los cuatro que el operador elige. `mercado` trae valor por defecto y
    #: el cliente sale del mandante, así que ninguno de los dos entra aquí.
    ATRIBUTOS_SKU = ("naturaleza_comercial", "categoria", "tipo", "formato")

    def atributos_sku_completos(self) -> bool:
        return all(getattr(self, campo) for campo in self.ATRIBUTOS_SKU) and bool(
            self.mandante_id and self.mandante.codigo_cliente
        )

    def sku_derivado(self) -> str | None:
        """
        El SKU que le corresponde según sus atributos, o `None` si faltan.

        No levanta cuando falta un atributo —eso es un producto a medio
        cargar, no un error— pero sí deja pasar el `SkuInvalido` de una
        combinación imposible: un producto propio con cliente describe algo
        que no existe, y guardarlo callando dejaría el maestro mintiendo.
        """
        from .dominio import generar_sku

        if not self.atributos_sku_completos():
            return None

        return generar_sku(
            self.naturaleza_comercial,
            self.mandante.codigo_cliente,
            self.categoria,
            self.tipo,
            self.formato,
            self.mercado or self.Mercado.LOCAL,
            variante=self.variante,
        )

    def clean(self):
        """
        Traduce el rechazo del generador a un error de formulario.

        Sin esto, una combinación imposible reventaría al guardar con una
        traza de 500 en vez de decir en pantalla qué está mal.
        """
        from .dominio import SkuInvalido

        super().clean()

        try:
            self.sku_derivado()
        except SkuInvalido as e:
            raise ValidationError({"naturaleza_comercial": str(e)}) from e

    def save(self, *args, **kwargs):
        """
        El SKU se deriva de los atributos: son la fuente de verdad.

        Un producto sin los atributos cargados conserva el código que tenga
        —el histórico está lleno de códigos escritos a mano y hay que poder
        registrarlos—, pero en cuanto se completan, el generador manda. Es lo
        que evita que el maestro y los atributos se contradigan, que es
        justamente el error que trae el archivo de origen.
        """
        derivado = self.sku_derivado()

        if derivado is not None:
            self.codigo = derivado

        super().save(*args, **kwargs)


class Equipo(models.Model):
    """
    Máquina programable de la planta: evaporadores, líneas de secado, etc.

    Era una lista fija en `planificacion.models.Equipo` y agregar una máquina
    exigía editar código y desplegar, que es lo contrario de que el maestro se
    configure. Vive en `maestros` porque es configuración del entorno, no un
    hecho de una corrida.

    **`consume_leche` es una regla de negocio, no una etiqueta.** Un mismo
    código de producción —LNSH2, por ejemplo— se programa en el evaporador
    *y* en la línea que lo recibe; si los dos bloques restaran leche, el
    balance la contaría dos veces. Solo los evaporadores la consumen. Marcar
    de más aquí hace desaparecer leche del balance sin que nadie lo note.

    **`consume_materiales` es la misma regla por el otro extremo.** El saco y
    la etiqueta los consume el equipo del final de la cadena —la torre, la
    línea de mantequilla—, no el evaporador que la alimenta. Son dos banderas
    y no una sola invertida porque hay equipos que no son ninguna de las dos
    cosas: la carga de precondensado no resta leche ni pide envases.

    Las dos son campos del maestro y no una comparación contra `tipo` en el
    código, y hay motivo: el MRP filtraba `tipo == "linea"`, y cuando las
    líneas 1 y 2 se reconocieron como las torres Egron y cambiaron de tipo,
    sus bloques dejaron de contar. El MRP siguió corriendo y devolviendo
    cifras, solo que cortas — que es la peor forma de fallar.
    """

    class Tipo(models.TextChoices):
        EVAPORADOR = "evaporador", "Evaporador"
        TORRE = "torre", "Torre de secado"
        ENVASADORA = "envasadora", "Envasadora"
        LINEA = "linea", "Línea"
        CARGA = "carga", "Carga"
        OTRO = "otro", "Otro"

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="equipos",
        default=sucursal_predeterminada_pruebas,
    )
    codigo = models.SlugField(
        "Código",
        max_length=40,
        help_text="Identificador estable. No se cambia: la planificación lo referencia.",
    )
    nombre = models.CharField("Nombre", max_length=120)
    tipo = models.CharField("Tipo", max_length=20, choices=Tipo.choices)
    consume_leche = models.BooleanField(
        "Consume leche del balance",
        default=False,
        help_text=(
            "Solo los evaporadores. Marcarlo en una línea que recibe lo que "
            "el evaporador ya produjo restaría la misma leche dos veces."
        ),
    )
    consume_materiales = models.BooleanField(
        "Consume materiales del MRP",
        default=False,
        help_text=(
            "Solo el equipo del final de la cadena: la torre o la línea que "
            "envasa. Marcarlo también en el evaporador que la alimenta haría "
            "que el MRP pidiera los sacos dos veces."
        ),
    )
    orden = models.PositiveSmallIntegerField(
        "Orden",
        default=0,
        help_text="Posición en la carta Gantt, de arriba hacia abajo.",
    )
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Equipo / máquina"
        verbose_name_plural = "Equipos y máquinas"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo"], name="equipo_codigo_unico_sucursal"
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

    class Estado(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        RECIBIENDO = "recibiendo", "Recibiendo"
        EN_USO = "en_uso", "En uso"
        RESERVADO = "reservado", "Reservado"
        BLOQUEADO_CALIDAD = "bloqueado_calidad", "Bloqueado por Calidad"
        PENDIENTE_CIP = "pendiente_cip", "Pendiente de CIP"
        EN_CIP = "en_cip", "En CIP"
        FUERA_SERVICIO = "fuera_servicio", "Fuera de servicio"

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="silos",
        default=sucursal_predeterminada_pruebas,
    )
    codigo = models.CharField("Código", max_length=40)
    tipo = models.CharField("Tipo", max_length=20, choices=Tipo.choices)
    capacidad_l = models.DecimalField(
        "Capacidad", max_digits=12, decimal_places=2, help_text="En litros"
    )
    estado = models.CharField(
        "Estado operacional", max_length=30, choices=Estado.choices,
        default=Estado.DISPONIBLE, db_index=True,
    )
    producto_actual = models.ForeignKey(
        "maestros.Producto", on_delete=models.PROTECT,
        related_name="silos_actuales", null=True, blank=True,
        help_text="Producto declarado; el volumen siempre se deriva de movimientos.",
    )
    temperatura_actual = models.DecimalField(
        "Temperatura actual (°C)", max_digits=6, decimal_places=2,
        null=True, blank=True,
    )
    ultima_limpieza = models.DateTimeField(null=True, blank=True)
    activo = models.BooleanField("Activo", default=True)

    class Meta:
        verbose_name = "Silo / estanque"
        verbose_name_plural = "Silos y estanques"
        ordering = ["codigo"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacidad_l__gt=0),
                name="silo_capacidad_positiva",
            ),
            models.UniqueConstraint(
                fields=["sucursal", "codigo"], name="silo_codigo_unico_sucursal"
            ),
        ]

    def __str__(self):
        return self.codigo


class Vehiculo(models.Model):
    """Camión de transporte de leche, con sus choferes por turno."""

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="vehiculos",
        default=sucursal_predeterminada_pruebas,
    )
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

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="documentos_liberacion",
        default=empresa_predeterminada_pruebas,
    )
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
    class Frecuencia(models.TextChoices):
        """
        Cada cuánto se llena el registro. **No es un detalle administrativo:**
        decide dónde vive el dato.

        Solo `POR_LOTE` produce un formulario por lote (`RegistroCalidad`).
        Los demás pertenecen al equipo y a su período, y un lote los *consume*
        si su fecha cae dentro: un aseo semanal hecho el lunes cubre todos los
        lotes de esa semana. Guardarlo por lote obligaría a teclear la misma
        limpieza una vez por lote —y cinco copias del mismo hecho pueden
        acabar diciendo cosas distintas—.

        En el catálogo de planta, solo 12 de 204 documentos son por lote.
        """

        POR_LOTE = "por_lote", "Por lote"
        POR_TURNO = "por_turno", "Por turno"
        POR_CICLO = "por_ciclo", "Por ciclo"
        DIARIA = "diaria", "Diaria"
        SEMANAL = "semanal", "Semanal"
        SEGUN_PROGRAMA = "segun_programa", "Según programa"

    frecuencia = models.CharField(
        "Frecuencia",
        max_length=20,
        choices=Frecuencia.choices,
        default=Frecuencia.POR_LOTE,
        help_text=(
            "Decide dónde vive el registro: por lote va en el expediente del "
            "lote; el resto pertenece al equipo y su período."
        ),
    )
    evidencia = models.JSONField(
        "Se cumple con el dato",
        default=dict,
        blank=True,
        help_text=(
            'Qué registro del sistema da por cumplido este documento: '
            '{"fuente": "monitoreo_ppro", "tipo": "detector_metales"}. '
            "Vacío = lo marca una persona."
        ),
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
                fields=["empresa", "codigo"],
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


class Receta(models.Model):
    """
    Qué se necesita para obtener un producto. Multinivel y versionada.

    La decisión que la justifica (MODELO_DATOS.md §2.7): una tabla plana
    "producto → litros de leche" no basta, porque **la mantequilla no se hace
    con leche, se hace con crema**. El modelo encadena transformaciones y las
    resuelve recorriendo el árbol:

        mantequilla 1 kg ──► crema 2 kg ──► leche fresca 8 L
        crema       1 kg ──► leche fresca 4 L

    Versionada por la misma razón que las especificaciones (§2.3): un lote de
    mayo se explota con la receta de mayo. Cambiar el rendimiento hoy no debe
    reescribir lo que costó producir hace seis meses.

    La explosión vive en `maestros/recetas.py`, sin ORM, para poder probarla
    sola.
    """

    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="recetas",
        verbose_name="Producto",
    )
    version = models.PositiveIntegerField("Versión", default=1)
    cantidad_base = models.DecimalField(
        "Cantidad base",
        max_digits=12,
        decimal_places=3,
        default=1,
        help_text="Los componentes rinden esta cantidad de producto",
    )
    vigente_desde = models.DateField("Vigente desde")
    vigente_hasta = models.DateField(
        "Vigente hasta",
        null=True,
        blank=True,
        help_text="Vacío = vigente indefinidamente",
    )
    fuente = models.CharField(
        "Fuente",
        max_length=250,
        blank=True,
        help_text="Documento o acuerdo que respalda la receta",
    )

    class Meta:
        verbose_name = "Receta"
        verbose_name_plural = "Recetas"
        ordering = ["producto__nombre", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "version"],
                name="receta_version_unica_por_producto",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad_base__gt=0),
                name="receta_cantidad_base_positiva",
            ),
        ]

    def __str__(self):
        return f"{self.producto} · v{self.version}"

    def clean(self):
        if (
            self.vigente_hasta is not None
            and self.vigente_desde is not None
            and self.vigente_hasta < self.vigente_desde
        ):
            raise ValidationError(
                {"vigente_hasta": "No puede ser anterior a la fecha de inicio de vigencia."}
            )

        # Una materia prima es el final de la cadena: si llevara receta, la
        # explosión no sabría dónde detenerse.
        if (
            self.producto_id
            and self.producto.naturaleza == Producto.Naturaleza.MATERIA_PRIMA
        ):
            raise ValidationError(
                {
                    "producto": (
                        "Una materia prima no lleva receta: es donde la "
                        "explosión se detiene."
                    )
                }
            )


class RecetaComponente(models.Model):
    """
    Un ingrediente de una receta, con su merma.

    La merma va en el componente y no en la receta porque se pierde distinto
    según lo que se transforma: la leche que se evapora no es lo mismo que el
    envase que se rompe.

    **Un componente es un producto o un insumo, nunca los dos.** Los productos
    encadenan transformaciones —la mantequilla lleva crema, y la crema leche—
    y por eso la explosión recurre sobre ellos. Los insumos son hojas: un saco
    o un litro de soda cáustica no se fabrican aquí, se compran, y quien los
    descuenta es bodega.

    Los dos viven en la misma tabla a propósito. Antes había un segundo
    maestro, `inventario.ConsumoProducto`, que respondía la misma pregunta
    —cuánto lleva un kilo de producto— sobre el otro catálogo: dos lugares
    donde declarar la fórmula, libres de discrepar, y solo uno de ellos
    versionado. El descuento de bodega usaba el plano, así que un lote de mayo
    se descontaba con las cantidades de hoy, que es justo lo que `Receta` está
    versionada para impedir.
    """

    class Unidad(models.TextChoices):
        """
        Cubre las unidades de los dos catálogos.

        `Producto` mide en kilos y litros; un insumo de empaque se cuenta en
        unidades —sacos, etiquetas— y sin `un` no habría forma de declararlo.
        No se reutiliza `Producto.Unidad` porque agregarle «unidades» ahí
        haría que el maestro de productos ofreciera una base que ningún
        producto lácteo tiene.
        """

        KG = "kg", "Kilogramos"
        L = "L", "Litros"
        UN = "un", "Unidades"

    receta = models.ForeignKey(
        Receta,
        on_delete=models.CASCADE,
        related_name="componentes",
        verbose_name="Receta",
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name="usos_en_recetas",
        verbose_name="Componente",
        null=True,
        blank=True,
        help_text="Si el componente se transforma aquí. Deja vacío si es un insumo.",
    )
    insumo = models.ForeignKey(
        "inventario.Insumo",
        on_delete=models.PROTECT,
        related_name="usos_en_recetas",
        verbose_name="Insumo",
        null=True,
        blank=True,
        help_text="Si el componente se compra y se descuenta de bodega.",
    )
    cantidad = models.DecimalField("Cantidad", max_digits=12, decimal_places=4)
    unidad = models.CharField(
        "Unidad",
        max_length=5,
        choices=Unidad.choices,
        help_text="Debe coincidir con la unidad base del componente",
    )
    merma = models.DecimalField(
        "Merma",
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="En %. Aumenta la cantidad necesaria del componente",
    )

    class Meta:
        verbose_name = "Componente de receta"
        verbose_name_plural = "Componentes de receta"
        ordering = ["receta", "producto__nombre", "insumo__nombre"]
        constraints = [
            # Los NULL se dejan **distintos**, que es lo que PostgreSQL hace
            # por omisión, y es imprescindible: los componentes que son insumo
            # llevan `producto` nulo, así que con `nulls_distinct=False` la
            # primera restricción los haría colisionar entre sí y una receta
            # admitiría un solo insumo. Pasó: se escribió al revés y ninguna
            # prueba lo notó porque todas cargaban un componente de cada tipo.
            #
            # Lo que cada una impide sigue en pie: no repetir el mismo
            # producto ni el mismo insumo dentro de una receta, que es como se
            # duplicaría una cantidad sin que nadie lo viera.
            models.UniqueConstraint(
                fields=["receta", "producto"],
                name="componente_unico_por_receta",
            ),
            models.UniqueConstraint(
                fields=["receta", "insumo"],
                name="componente_insumo_unico_por_receta",
            ),
            # Uno de los dos, y solo uno. Un componente con ambos tendría dos
            # cantidades para el mismo renglón; uno sin ninguno es una
            # cantidad de nada.
            models.CheckConstraint(
                condition=(
                    models.Q(producto__isnull=False, insumo__isnull=True)
                    | models.Q(producto__isnull=True, insumo__isnull=False)
                ),
                name="componente_es_producto_o_insumo",
            ),
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0),
                name="componente_cantidad_positiva",
            ),
            models.CheckConstraint(
                condition=models.Q(merma__gte=0),
                name="componente_merma_no_negativa",
            ),
        ]

    def __str__(self):
        return f"{self.cantidad} {self.unidad} de {self.producto or self.insumo}"

    def clean(self):
        if bool(self.producto_id) == bool(self.insumo_id):
            raise ValidationError(
                "Un componente es un producto o un insumo, no los dos ni ninguno."
            )

        # Un producto que se lleva a sí mismo cuelga la explosión. El ciclo
        # indirecto lo detecta el dominio, que ve el árbol entero; este es el
        # caso directo, que se puede atajar aquí.
        if self.receta_id and self.producto_id == self.receta.producto_id:
            raise ValidationError(
                {"producto": "Una receta no puede llevarse a sí misma como componente."}
            )

        # La unidad declarada tiene que ser la del componente: mezclar litros
        # y kilos en la explosión da un número que parece bueno y no lo es.
        if self.producto_id and self.unidad != self.producto.unidad_base:
            raise ValidationError(
                {
                    "unidad": (
                        f"{self.producto} se mide en "
                        f"{self.producto.get_unidad_base_display().lower()}."
                    )
                }
            )

        if self.insumo_id and self.unidad != self.insumo.unidad:
            raise ValidationError(
                {
                    "unidad": (
                        f"{self.insumo} se mide en "
                        f"{self.insumo.get_unidad_display().lower()}."
                    )
                }
            )
