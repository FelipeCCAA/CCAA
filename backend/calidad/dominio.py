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

from produccion import dominio as calidad_producto


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

def avance_checklist(
    registros: Iterable[Any],
    documentos_exigibles: Sequence[Any],
    lote_id: int | None = None,
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
    """
    exigibles = list(documentos_exigibles or [])

    por_documento = {
        r.documento_id: r
        for r in (registros or [])
        if lote_id is None or r.lote_id == lote_id
    }

    detalle = []
    for documento in exigibles:
        registro = por_documento.get(documento.id)
        detalle.append(
            EstadoDocumento(
                documento=documento,
                registro=registro,
                completo=registro_completo(registro, documento),
                observado=getattr(registro, "estado", None) == OBSERVADO,
                iniciado=registro is not None,
                faltantes=campos_faltantes(registro, documento),
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

def puede_liberar(
    lote: Any,
    producto: Any,
    documentos: Iterable[Any] = (),
    registros: Iterable[Any] = (),
    analisis: Sequence[Any] = (),
    especificaciones: Iterable[Any] = (),
    rol: str | None = None,
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
    avance = avance_checklist(registros, exigibles, lote.id)

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

    calidad = calidad_producto.resultado_calidad_lote(lote, analisis, especificaciones)

    bloqueos_calidad: list[str] = []
    if calidad.resultado == calidad_producto.SIN_ESPECIFICACION:
        bloqueos_calidad.append(
            "El producto no tiene especificación de calidad vigente a la fecha del lote."
        )
    elif calidad.resultado == calidad_producto.SIN_ANALISIS:
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

    no_conforme = calidad.resultado == calidad_producto.NO_CONFORME
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
