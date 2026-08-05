"""
Reglas de liberación. Traducción de `prototipo/js/modelo/dominio.js`.

Funciones puras: no tocan la base de datos, no importan modelos y no dependen
de Django. Reciben datos y devuelven datos. Por eso se pueden probar solas y
por eso el prototipo las pudo trasladar aquí sin reescribirlas.

La regla que gobierna este archivo (MODELO_DATOS.md §1):

    Un despacho exige un lote liberado. Un lote se libera si su checklist está
    completo Y su calidad es conforme. Si no lo es, solo puede salir como
    concesión, con motivo y autorizador registrados.

Las decisiones NUNCA devuelven un booleano suelto (§2.10): devuelven la
decisión junto con sus `bloqueos`, para que la pantalla pueda explicarle a
quien está esperando por qué no puede avanzar. Un "no se puede liberar" sin
motivo obliga a llamar por teléfono a alguien, que es justo lo que este
sistema existe para evitar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# El dominio de producción: de ahí salen el veredicto de calidad del lote
# y la evaluación del PCC 1.
from produccion import dominio as produccion_dominio


# Roles que pueden firmar una liberación.
#
# Van como texto y no importando `usuarios.models.Rol` a propósito: este módulo
# no depende de Django, que es lo que lo hace probable sin base de datos. La
# duplicación es deliberada y hay una prueba que la vigila, de modo que si
# alguien renombra un rol, la prueba lo detiene.
ROLES_AUTORIZADORES = ("calidad", "admin")

# Estados de `RegistroCalidad`, por el mismo motivo.
BORRADOR = "borrador"
COMPLETADO = "completado"
OBSERVADO = "observado"

# Diferencia por debajo de la cual un valor declarado en un formulario se
# considera el mismo que midió el laboratorio. Un formulario redondea a un
# decimal donde el análisis guarda dos; eso no es una discrepancia.
TOLERANCIA_COTEJO = 0.05

# Largo mínimo del motivo de una concesión. No es un número arbitrario: es lo
# que impide que "ok" o "autorizado" pasen por justificación. Quien lea el
# expediente dentro de dos años necesita entender por qué salió este producto.
LARGO_MINIMO_MOTIVO = 10


# ------------------------------------------------------------------ resultados

@dataclass(frozen=True)
class EstadoDocumento:
    """Cómo quedó un documento exigible frente a su registro, si lo hay."""

    documento: Any
    registro: Any | None
    completo: bool
    observado: bool
    iniciado: bool
    faltantes: list[dict[str, Any]] = field(default_factory=list)
    #: Lo cumple el registro del sistema y no una casilla. Se distingue para
    #: que el expediente pueda decir de dónde viene el cumplimiento: «hay
    #: control de proceso» no es lo mismo que «alguien lo marcó».
    cumplido_por_dato: bool = False
    #: El registro periódico que lo cubre, si lo hay. Va el objeto y no un
    #: booleano porque el expediente tiene que poder decir CUÁL lo cubre —«el
    #: aseo semanal del 28-07»—, o quien audita no llega al papel.
    cubierto_por: Any = None


@dataclass(frozen=True)
class AvanceChecklist:
    """Avance documental de un lote. Derivado, nunca persistido (§2.6)."""

    detalle: list[EstadoDocumento] = field(default_factory=list)
    completados: int = 0
    total: int = 0
    faltantes: list[Any] = field(default_factory=list)
    observados: list[Any] = field(default_factory=list)

    @property
    def pct(self) -> int:
        return round(self.completados / self.total * 100) if self.total else 0

    @property
    def completo(self) -> bool:
        """Sin documentos exigibles no hay checklist completo, hay checklist vacío."""
        return self.total > 0 and not self.faltantes


@dataclass(frozen=True)
class Validacion:
    """Una decisión con sus motivos."""

    permitido: bool
    bloqueos: list[str] = field(default_factory=list)
    faltantes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Discrepancia:
    """Algo que el formulario dice y los datos del sistema contradicen."""

    # fuera_de_especificacion | discrepa_del_analisis
    tipo: str
    parametro: str
    etiqueta: str
    declarado: float
    mensaje: str
    minimo: float | None = None
    maximo: float | None = None
    medidos: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class DecisionLiberacion:
    """
    Veredicto sobre si un lote puede liberarse.

    `permitido` y `via_concesion` son excluyentes: un lote no conforme nunca se
    libera por la vía normal, y uno conforme no necesita concesión.
    """

    permitido: bool
    via_concesion: bool
    bloqueos: list[str] = field(default_factory=list)
    calidad: Any = None
    avance: AvanceChecklist | None = None


# ------------------------------------------------------------------- ayudantes

def _es_vacio(valor: Any) -> bool:
    return valor is None or valor == ""


def _numero(valor: Any) -> float | None:
    """Cada dominio lleva el suyo, sin importarse los privados entre módulos."""
    if _es_vacio(valor) or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    # NaN no es comparable: se trata como "no medido".
    return None if numero != numero else numero


def _plantilla_de(documento: Any) -> list[dict[str, Any]]:
    return list(getattr(documento, "plantilla", None) or [])


def _valores_de(registro: Any) -> dict[str, Any]:
    return getattr(registro, "valores", None) or {}


# -------------------------------------------------------- documentos exigibles

def documentos_aplicables(documentos: Iterable[Any], producto: Any) -> list[Any]:
    """
    Documentos que un lote debe cumplir, según la familia de su producto.

    A la crema no se le piden los documentos de las líneas de polvo. Exigir un
    formulario que no aplica es tan dañino como no exigir el que sí: el
    checklist nunca se completa y la gente aprende a ignorarlo.
    """
    if producto is None:
        return []

    aplicables = [
        d
        for d in (documentos or [])
        if getattr(d, "activo", True) and producto.familia in (d.aplica_a or [])
    ]

    return sorted(aplicables, key=lambda d: (d.orden or 0, d.nombre))


# -------------------------------------------------------- formularios digitales

def campos_faltantes(registro: Any, documento: Any) -> list[dict[str, Any]]:
    """Campos obligatorios de la plantilla que el registro dejó vacíos."""
    valores = _valores_de(registro)

    return [
        campo
        for campo in _plantilla_de(documento)
        if campo.get("req") and _es_vacio(valores.get(campo["clave"]))
    ]


def registro_completo(registro: Any, documento: Any) -> bool:
    """
    Un documento cuenta como cumplido solo si su formulario está completado y
    no le falta ningún campo obligatorio.

    Marcar una casilla ya no basta: esa era justamente la debilidad del
    checklist en papel, donde el visto bueno no probaba que el dato existiera.
    """
    if registro is None or registro.estado != COMPLETADO:
        return False

    return not campos_faltantes(registro, documento)


def validar_registro(registro: Any, documento: Any) -> Validacion:
    """Comprueba un formulario contra su plantilla antes de darlo por completado."""
    bloqueos: list[str] = []
    faltantes = campos_faltantes(registro, documento)

    if faltantes:
        etiquetas = ", ".join(c["etiqueta"] for c in faltantes)
        bloqueos.append(f"Faltan {len(faltantes)} campo(s) obligatorio(s): {etiquetas}.")

    valores = _valores_de(registro)

    for campo in _plantilla_de(documento):
        valor = _numero(valores.get(campo["clave"]))
        if valor is None:
            continue

        minimo, maximo = campo.get("min"), campo.get("max")

        if minimo is not None and valor < minimo:
            bloqueos.append(f"{campo['etiqueta']}: no puede ser menor que {minimo}.")
        if maximo is not None and valor > maximo:
            bloqueos.append(f"{campo['etiqueta']}: no puede ser mayor que {maximo}.")

    return Validacion(permitido=not bloqueos, bloqueos=bloqueos, faltantes=faltantes)


def prellenar(documento: Any, contexto: Any) -> dict[str, Any]:
    """
    Valores que el sistema ya conoce y no hay que volver a teclear.

    Un campo con `origen: "lote.codigo_lote"` se rellena solo. Nadie vuelve a
    escribir el lote ni la fecha, y por tanto nadie los escribe mal.

    El contexto admite tanto diccionarios como objetos, para que la vista pueda
    pasarle el lote del ORM sin convertirlo antes.
    """
    valores: dict[str, Any] = {}

    for campo in _plantilla_de(documento):
        origen = campo.get("origen")
        if not origen:
            continue

        valor: Any = contexto
        for tramo in str(origen).split("."):
            if valor is None:
                break
            valor = valor.get(tramo) if isinstance(valor, dict) else getattr(valor, tramo, None)

        if not _es_vacio(valor):
            valores[campo["clave"]] = valor

    return valores


def cotejar_con_analisis(
    registro: Any,
    documento: Any,
    resultado_lote: Any,
    analisis: Sequence[Any] = (),
) -> list[Discrepancia]:
    """
    Coteja lo escrito en un formulario contra los análisis del lote.

    Un campo con `parametro: "humedad"` se compara con lo que midió el
    laboratorio y con la especificación vigente. Es la ventaja de tener el
    formulario dentro del sistema: el dato se contrasta solo, en vez de quedar
    en un papel que nadie vuelve a cruzar.

    No bloquea nada por sí mismo: avisa. Que el formulario y el análisis
    discrepen puede ser un error de tipeo o puede ser un problema real, y esa
    diferencia la juzga una persona.

    Los análisis se filtran por el lote del registro, por la misma razón que
    `avance_checklist` filtra los registros: cotejar contra la muestra de otro
    lote produciría una discrepancia inventada, o peor, ocultaría una real.
    """
    discrepancias: list[Discrepancia] = []
    valores = _valores_de(registro)

    spec = getattr(resultado_lote, "especificacion", None)
    rangos = (getattr(spec, "rangos", None) or {}) if spec is not None else {}

    lote_id = getattr(registro, "lote_id", None)
    del_lote = [
        a for a in (analisis or []) if lote_id is None or a.lote_id == lote_id
    ]

    for campo in _plantilla_de(documento):
        parametro = campo.get("parametro")
        if not parametro:
            continue

        declarado = _numero(valores.get(campo["clave"]))
        if declarado is None:
            continue

        etiqueta = campo["etiqueta"]

        # ¿Se sale de la especificación vigente?
        rango = rangos.get(parametro)
        if rango:
            minimo = _numero(rango.get("min"))
            maximo = _numero(rango.get("max"))

            if (minimo is not None and declarado < minimo) or (
                maximo is not None and declarado > maximo
            ):
                discrepancias.append(
                    Discrepancia(
                        tipo="fuera_de_especificacion",
                        parametro=parametro,
                        etiqueta=etiqueta,
                        declarado=declarado,
                        minimo=minimo,
                        maximo=maximo,
                        mensaje=(
                            f"{etiqueta}: {declarado} está fuera de la especificación "
                            f"({minimo if minimo is not None else '—'} a "
                            f"{maximo if maximo is not None else '—'})."
                        ),
                    )
                )

        # ¿Coincide con lo que dice el análisis de laboratorio?
        medidos = [
            valor
            for valor in (_numero((a.valores or {}).get(parametro)) for a in del_lote)
            if valor is not None
        ]

        if medidos:
            tolerancia = campo.get("tolerancia", TOLERANCIA_COTEJO)

            if not any(abs(v - declarado) <= tolerancia for v in medidos):
                medidos_texto = " / ".join(str(v) for v in medidos)
                discrepancias.append(
                    Discrepancia(
                        tipo="discrepa_del_analisis",
                        parametro=parametro,
                        etiqueta=etiqueta,
                        declarado=declarado,
                        medidos=medidos,
                        mensaje=(
                            f"{etiqueta}: el formulario dice {declarado} y "
                            f"el análisis del lote, {medidos_texto}."
                        ),
                    )
                )

    return discrepancias


# -------------------------------------------------------------------- checklist

#: Fuentes de datos que pueden dar por cumplido un documento del Dossier.
#: El nombre es el que va en `DocumentoLiberacion.evidencia["fuente"]`.
FUENTE_CONTROL_PROCESO = "control_proceso"
FUENTE_MONITOREO_PPRO = "monitoreo_ppro"
FUENTE_ANALISIS = "analisis"
FUENTE_ASIGNACION_LECHE = "asignacion_leche"


def _coincide(registro: Any, criterio: dict) -> bool:
    """
    ¿Este registro satisface el criterio del documento?

    Compara **solo las claves que el criterio declara**, y todas tienen que
    coincidir. Un criterio vacío lo cumple cualquier registro de la fuente;
    uno que declara `equipo` exige ese equipo.

    Se compara en minúsculas y sin espacios porque `equipo` viaja como texto
    libre en los monitoreos, y «E1 » no debería fallar contra «e1».
    """
    def normal(valor):
        return str(valor or "").strip().lower()

    for campo, esperado in criterio.items():
        if campo == "fuente":
            continue

        # `campo_en` acepta varios valores: el PCC 1 de uperización se registra
        # en cualquiera de los tres evaporadores, y exigir uno concreto dejaría
        # el documento sin cumplir según en cuál se corrió.
        if campo.endswith("_en"):
            valor = getattr(registro, campo[:-3], None)

            if normal(valor) not in {normal(e) for e in (esperado or [])}:
                return False

            continue

        if normal(getattr(registro, campo, None)) != normal(esperado):
            return False

    return True


def documentos_con_evidencia(
    documentos: Iterable[Any],
    lote_id: int,
    controles: Iterable[Any] = (),
    monitoreos: Iterable[Any] = (),
    analisis: Iterable[Any] = (),
    movimientos: Iterable[Any] = (),
) -> set[int]:
    """
    Documentos del checklist que el propio dato del sistema da por cumplidos.

    Once de los diecinueve registros del Dossier son datos que la aplicación
    ya captura: el PCC 1 vive en `ControlProceso`, los PPRO en
    `MonitoreoPPRO`, el fisicoquímico en `Analisis`, la trazabilidad en la
    asignación de silos. Pedir además una casilla es doble digitación — y algo
    peor: la casilla puede decir «cumplido» sobre un PCC 1 incumplido.

    Un documento se cumple con su dato cuando **existe al menos un registro
    del lote** que coincide con el criterio. Que ese registro además esté
    conforme es otra pregunta y la responden las reglas de inocuidad, que
    bloquean por su cuenta. Aquí solo se responde si el registro existe: es
    exactamente lo que la casilla afirmaba.

    Devuelve ids y no objetos porque es lo que `avance_checklist` necesita
    para cruzarlo con los registros manuales.
    """
    por_fuente = {
        FUENTE_CONTROL_PROCESO: [
            c for c in (controles or []) if getattr(c, "lote_id", None) == lote_id
        ],
        FUENTE_MONITOREO_PPRO: [
            m for m in (monitoreos or []) if getattr(m, "lote_id", None) == lote_id
        ],
        FUENTE_ANALISIS: [
            a for a in (analisis or []) if getattr(a, "lote_id", None) == lote_id
        ],
        # La asignación de leche son las salidas de silo con origen en el lote.
        FUENTE_ASIGNACION_LECHE: [
            m
            for m in (movimientos or [])
            if getattr(m, "tipo", None) == "salida"
            and getattr(m, "origen_tipo", None) == "lote"
            and getattr(m, "origen_id", None) == lote_id
        ],
    }

    cumplidos = set()

    for documento in documentos or []:
        criterio = getattr(documento, "evidencia", None) or {}
        candidatos = por_fuente.get(criterio.get("fuente"))

        # Sin fuente declarada, o con una que no existe, el documento sigue
        # siendo manual. No se inventa una equivalencia.
        if not candidatos:
            continue

        if any(_coincide(registro, criterio) for registro in candidatos):
            cumplidos.add(documento.id)

    return cumplidos


# ------------------------------------------------- registros por período

#: Frecuencias que NO producen un formulario por lote. El registro pertenece
#: al equipo y a su período, y el lote lo consume si su fecha cae dentro.
FRECUENCIA_POR_LOTE = "por_lote"


def _misma_semana(una, otra) -> bool:
    """Semana ISO: el aseo del lunes cubre hasta el domingo."""
    return una.isocalendar()[:2] == otra.isocalendar()[:2]


def cubre_al_lote(registro: Any, documento: Any, lote: Any) -> bool:
    """
    ¿Este registro periódico cubre al lote?

    La ventana sale de la frecuencia del documento y **no se guarda**: un
    `vigente_hasta` almacenado se desincroniza en cuanto alguien corrige la
    fecha del registro, y entonces un lote quedaría cubierto por un aseo que
    ya no lo alcanza.

    - `diaria`, `por_ciclo`, `por_turno`: el mismo día. Además, si el
      documento es por turno y ambos lo declaran, tienen que coincidir — un
      aseo del turno A no dice nada del turno B.
    - `semanal`: la misma semana ISO.
    - `segun_programa`: no hay período deducible, así que el registro tiene
      que declarar hasta cuándo cubre. Sin `vigente_hasta` no cubre nada: es
      preferible pedir el dato a inventar una vigencia.
    """
    if registro is None or lote is None:
        return False

    fecha_lote = getattr(lote, "fecha", None)
    fecha_registro = getattr(registro, "fecha", None)

    if fecha_lote is None or fecha_registro is None:
        return False

    frecuencia = getattr(documento, "frecuencia", FRECUENCIA_POR_LOTE)

    if frecuencia == "semanal":
        return _misma_semana(fecha_registro, fecha_lote)

    if frecuencia == "segun_programa":
        hasta = getattr(registro, "vigente_hasta", None)

        return hasta is not None and fecha_registro <= fecha_lote <= hasta

    # Diaria, por ciclo y por turno: el mismo día.
    if fecha_registro != fecha_lote:
        return False

    if frecuencia == "por_turno":
        turno_registro = (getattr(registro, "turno", "") or "").strip()
        turno_lote = (getattr(lote, "turno", "") or "").strip()

        # Si alguno no declara turno no se puede afirmar que coincidan, pero
        # tampoco que no: el registro del día se acepta. Exigirlo dejaría sin
        # cubrir lotes que en planta sí lo están.
        if turno_registro and turno_lote:
            return turno_registro == turno_lote

    return True


def documentos_cubiertos_por_periodo(
    documentos: Iterable[Any],
    lote: Any,
    registros_equipo: Iterable[Any] = (),
) -> dict[int, Any]:
    """
    Documentos que un registro periódico da por cumplidos, y cuál los cumple.

    Devuelve el registro y no solo el id porque el expediente tiene que poder
    decir **cuál** lo cubre: «el aseo semanal del 28-07», no «está cubierto».
    Sin eso, quien audita no puede llegar al papel.

    Solo cuentan los registros completados. Uno en borrador es trabajo a
    medias, y uno observado es una alerta abierta — igual que en el checklist
    por lote.
    """
    por_documento = {}

    for documento in documentos or []:
        if getattr(documento, "frecuencia", FRECUENCIA_POR_LOTE) == FRECUENCIA_POR_LOTE:
            continue

        for registro in registros_equipo or []:
            if getattr(registro, "documento_id", None) != documento.id:
                continue

            if getattr(registro, "estado", None) != COMPLETADO:
                continue

            if cubre_al_lote(registro, documento, lote):
                por_documento[documento.id] = registro
                break

    return por_documento


def avance_checklist(
    registros: Iterable[Any],
    documentos_exigibles: Sequence[Any],
    lote_id: int | None = None,
    cumplidos_por_dato: set[int] | None = None,
    cubiertos_por_periodo: dict[int, Any] | None = None,
) -> AvanceChecklist:
    """
    Avance documental de un lote, derivado de sus registros de calidad.

    No se persiste: cambiar la plantilla de un documento recalcula el avance
    (MODELO_DATOS.md §2.6).

    CUIDADO con `lote_id`. Es opcional en la firma, pero quien no lo pase debe
    haber filtrado ya los registros de ESE lote. Un registro de otro lote
    colándose aquí daría por cumplido un documento que nadie completó para
    este — y como el checklist completo es lo que habilita la liberación, el
    error deja salir producto. Lo detectó una prueba del prototipo y hay una de
    regresión que lo cubre.

    `cumplidos_por_dato` son los documentos que el propio registro del sistema
    satisface (`documentos_con_evidencia`): el PCC 1 lo cumple su control de
    proceso, no una casilla. Se pasa aparte y no se mezcla con los registros
    manuales para que se vea de dónde viene cada cumplimiento — en el
    expediente y aquí.

    `cubiertos_por_periodo` son los que cubre un registro del equipo
    (`documentos_cubiertos_por_periodo`): el aseo semanal de la torre cubre
    todos los lotes de su semana, y por eso no se llena uno por lote.
    """
    exigibles = list(documentos_exigibles or [])

    por_documento = {
        r.documento_id: r
        for r in (registros or [])
        if lote_id is None or r.lote_id == lote_id
    }

    por_dato = cumplidos_por_dato or set()
    por_periodo = cubiertos_por_periodo or {}

    detalle = []
    for documento in exigibles:
        registro = por_documento.get(documento.id)

        # El dato del sistema cumple el documento por sí solo. Una
        # observación manual sigue pesando: si alguien abrió el registro y lo
        # marcó observado, eso es una alerta que el dato no borra.
        lo_cumple_el_dato = documento.id in por_dato
        cubierto = por_periodo.get(documento.id)

        resuelto = lo_cumple_el_dato or cubierto is not None

        detalle.append(
            EstadoDocumento(
                documento=documento,
                registro=registro,
                completo=resuelto or registro_completo(registro, documento),
                observado=getattr(registro, "estado", None) == OBSERVADO,
                iniciado=resuelto or registro is not None,
                faltantes=[] if resuelto else campos_faltantes(registro, documento),
                cumplido_por_dato=lo_cumple_el_dato,
                cubierto_por=cubierto,
            )
        )

    return AvanceChecklist(
        detalle=detalle,
        completados=sum(1 for d in detalle if d.completo),
        total=len(exigibles),
        faltantes=[d.documento for d in detalle if not d.completo],
        observados=[d.documento for d in detalle if d.observado],
    )


# ---------------------------------------------------------- regla de liberación

def bloqueos_de_inocuidad(
    controles: Iterable[Any] = (),
    lecturas_control: Iterable[Any] = (),
    monitoreos: Iterable[Any] = (),
) -> list[str]:
    """
    Lo que la inocuidad impide, con su motivo.

    Son dos reglas y las dos son de HACCP, no de calidad de producto:

    - Una lectura fuera del límite del **PCC 1** de uperización significa que
      la leche pasó sin el tratamiento térmico que garantiza su inocuidad. No
      hay concesión posible: una concesión asume un riesgo conocido sobre el
      producto, y aquí lo que falló es la barrera que lo hace seguro.
    - Un **PPRO** con lecturas No-OK y sin acción correctiva escrita es un
      incidente abierto. Lo que bloquea no es el No-OK —eso pasa y se corrige—
      sino que nadie haya dejado constancia de qué se hizo.

    Recibe las lecturas aparte de los controles para no tocar la base desde
    aquí: quien llama las trae en una consulta.
    """
    bloqueos: list[str] = []

    for control in controles or []:
        evaluacion = produccion_dominio.evaluar_pcc1(control, lecturas_control)

        if evaluacion.incumplimientos:
            detalle = "; ".join(
                i.descripcion for i in evaluacion.incumplimientos[:3]
            )
            resto = len(evaluacion.incumplimientos) - 3
            if resto > 0:
                detalle += f"; y {resto} más"

            bloqueos.append(
                f"PCC 1 incumplido en {control.equipo}: {detalle}. "
                "La uperización no alcanzó el límite crítico."
            )

    for monitoreo in monitoreos or []:
        # `resuelto` es False solo cuando hay No-OK **y** falta la acción
        # correctiva: el modelo ya distingue las dos cosas.
        if not monitoreo.resuelto:
            bloqueos.append(
                f"{monitoreo.get_tipo_display()} con lecturas No-OK y sin acción "
                "correctiva registrada."
            )

    return bloqueos


def puede_liberar(
    lote: Any,
    producto: Any,
    documentos: Iterable[Any] = (),
    registros: Iterable[Any] = (),
    analisis: Sequence[Any] = (),
    especificaciones: Iterable[Any] = (),
    rol: str | None = None,
    controles: Iterable[Any] = (),
    lecturas_control: Iterable[Any] = (),
    monitoreos: Iterable[Any] = (),
    cumplidos_por_dato: set[int] | None = None,
    cubiertos_por_periodo: dict[int, Any] | None = None,
) -> DecisionLiberacion:
    """
    ¿Se puede liberar este lote?

    Devuelve tres cosas y no un booleano: si la liberación normal está
    disponible, si el lote solo puede salir por concesión, y los motivos
    legibles de todo lo que lo impide.

    `rol` es el de quien pretende firmar. Va como texto y no como usuario para
    que esta función no dependa de Django; quien llama lo resuelve con
    `usuarios.models.rol_de`. Si no se pasa, no se evalúa el permiso: sirve
    para consultar el estado de un lote sin estar autorizando nada.

    Los controles de proceso y los monitoreos PPRO llegan como argumentos por
    la misma razón: la función sigue sin consultar la base. Si no se pasan, no
    se evalúa la inocuidad — igual que con el rol.
    """
    if lote is None:
        return DecisionLiberacion(
            permitido=False, via_concesion=False, bloqueos=["No existe el lote."]
        )

    bloqueos: list[str] = []

    if lote.estado == "anulado":
        bloqueos.append("El lote está anulado.")
    if lote.estado == "en_proceso":
        bloqueos.append("El lote aún está en proceso: primero hay que cerrar la producción.")

    exigibles = documentos_aplicables(documentos, producto)
    avance = avance_checklist(
        registros, exigibles, lote.id, cumplidos_por_dato, cubiertos_por_periodo
    )

    if not avance.total:
        bloqueos.append("No hay documentos configurados para esta familia de producto.")
    elif not avance.completo:
        bloqueos.append(
            f"Faltan {len(avance.faltantes)} de {avance.total} formularios por completar."
        )

    if avance.observados:
        bloqueos.append(
            f"{len(avance.observados)} formulario(s) marcados con observación sin resolver."
        )

    if rol is not None and rol not in ROLES_AUTORIZADORES:
        bloqueos.append(f'El rol "{rol}" no puede autorizar liberaciones.')

    # Inocuidad. Van con el resto de bloqueos y no aparte porque comparten
    # consecuencia: mientras estén, no hay liberación normal.
    bloqueos.extend(bloqueos_de_inocuidad(controles, lecturas_control, monitoreos))

    calidad = produccion_dominio.resultado_calidad_lote(lote, analisis, especificaciones)

    bloqueos_calidad: list[str] = []
    if calidad.resultado == produccion_dominio.SIN_ESPECIFICACION:
        bloqueos_calidad.append(
            "El producto no tiene especificación de calidad vigente a la fecha del lote."
        )
    elif calidad.resultado == produccion_dominio.SIN_ANALISIS:
        bloqueos_calidad.append("El lote no tiene análisis de calidad completos.")

    # Sin especificación o sin análisis no hay liberación posible, ni siquiera
    # por concesión: no se puede conceder una excepción sobre algo que nunca se
    # midió. Una concesión es asumir un riesgo conocido, no uno ignorado.
    if bloqueos_calidad:
        return DecisionLiberacion(
            permitido=False,
            via_concesion=False,
            bloqueos=bloqueos + bloqueos_calidad,
            calidad=calidad,
            avance=avance,
        )

    no_conforme = calidad.resultado == produccion_dominio.NO_CONFORME

    # Un fallo de inocuidad no admite concesión, y no hace falta una rama
    # aparte para conseguirlo: sus motivos están dentro de `bloqueos`, así que
    # `resto_en_regla` ya es falso y con él caen las dos vías.
    #
    # Se escribe aquí porque la garantía importa y el mecanismo no es obvio:
    # la concesión existe para liberar un producto cuya calidad se salió de
    # especificación asumiendo un riesgo **conocido y medido**; un PCC 1
    # incumplido no es eso, es que la barrera que hace inocuo el producto no
    # actuó, y no hay medición que acote ese riesgo. Si alguien alguna vez
    # saca los bloqueos de inocuidad de esta lista, tiene que reponer la
    # exclusión a mano.
    resto_en_regla = not bloqueos

    if no_conforme:
        bloqueos = bloqueos + [
            f"Calidad no conforme: {len(calidad.desviaciones)} parámetro(s) fuera de rango. "
            "Requiere liberación bajo concesión."
        ]

    return DecisionLiberacion(
        permitido=resto_en_regla and not no_conforme,
        via_concesion=resto_en_regla and no_conforme,
        bloqueos=bloqueos,
        calidad=calidad,
        avance=avance,
    )


def validar_concesion(
    motivo: str | None,
    autorizador_identificado: bool,
    **contexto: Any,
) -> Validacion:
    """
    Valida una liberación bajo concesión: exige motivo escrito y firma.

    Acepta el mismo contexto que `puede_liberar` y lo evalúa primero: una
    concesión no salta las demás condiciones, solo la de conformidad. Un
    checklist incompleto sigue bloqueando, y un lote sin análisis también.
    """
    decision = puede_liberar(**contexto)
    bloqueos: list[str] = []

    if not decision.via_concesion and not decision.permitido:
        bloqueos.extend(decision.bloqueos)

    if _es_vacio(motivo) or len(str(motivo).strip()) < LARGO_MINIMO_MOTIVO:
        bloqueos.append(
            f"La concesión exige un motivo escrito de al menos "
            f"{LARGO_MINIMO_MOTIVO} caracteres."
        )

    if not autorizador_identificado:
        bloqueos.append("La concesión debe quedar firmada por un usuario identificado.")

    return Validacion(permitido=not bloqueos, bloqueos=bloqueos)
