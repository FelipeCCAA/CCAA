"""
Reglas de recepción y silos. Traducción de `prototipo/js/modelo/dominio.js`.

Funciones puras, como las de calidad: reciben datos y devuelven datos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Iterable


# Límites de control del camión.
#
# Son REFERENCIALES y están pendientes de confirmar con Calidad
# (MODELO_DATOS.md §8.5). Se declaran aquí, en un solo lugar, para que
# cambiarlos sea editar una línea y no buscar números por el código.
LIMITES = {
    "acidez_max": 18.0,
    "ph_min": 6.5,
    "ph_max": 6.9,
    "temperatura_max": 8.0,
    # La crioscopía detecta aguado: un valor MENOS negativo que este es
    # sospechoso, porque el agua sube el punto de congelación.
    "crioscopia_max": -0.510,
    # pH del enjuague del CAMIÓN, no de la leche. El formato declara el rango
    # en el propio encabezado de la columna AO.
    "ph_camion_min": 5.5,
    "ph_camion_max": 8.5,
}


# Factor de conversión de litros a kilos del formato CCAA.REC.FORM.002.02
# (columna I = H × 1,03).
#
# La hoja `Litros-kilos` (0082.MAN.FORM.000112) del mismo libro usa `/0,97`,
# que es 1,030928: no es el mismo número. Manda el de la hoja operativa,
# porque es el que produjo las cifras que la planta reportó. Si Calidad
# resuelve la discrepancia, se cambia aquí y en ningún otro lugar.
FACTOR_LITROS_A_KILOS = Decimal("1.03")


@dataclass(frozen=True)
class CapaSilo:
    recepcion_id: int | None
    litros: Decimal
    orden: int
    origen_no_atribuible: str = ""


@dataclass(frozen=True)
class ParteFIFO:
    recepcion_id: int | None
    litros: Decimal
    orden: int
    origen_no_atribuible: str = ""


@dataclass(frozen=True)
class ResultadoFIFO:
    partes: list[ParteFIFO]
    remanente_no_atribuible: Decimal


@dataclass(frozen=True)
class SugerenciaOrigen:
    silo_id: int
    litros_disponibles: Decimal
    leche_mas_antigua_en: Any
    antiguedad_horas: Decimal | None
    motivos_no_disponible: tuple[str, ...]
    litros_sugeridos: Decimal
    sugerido: bool


def _dato(objeto, nombre, defecto=None):
    return objeto.get(nombre, defecto) if isinstance(objeto, dict) else getattr(
        objeto, nombre, defecto
    )


def atribuir_fifo(capas, litros) -> ResultadoFIFO:
    """Consume las capas más antiguas y declara cualquier remanente sin origen."""
    pendiente = Decimal(str(litros))
    partes = []
    for capa in capas:
        if pendiente <= 0:
            break
        disponible = Decimal(str(capa.litros))
        if disponible <= 0:
            continue
        tomado = min(disponible, pendiente)
        partes.append(ParteFIFO(
            recepcion_id=capa.recepcion_id,
            litros=tomado,
            orden=len(partes) + 1,
            origen_no_atribuible=capa.origen_no_atribuible,
        ))
        pendiente -= tomado
    return ResultadoFIFO(partes=partes, remanente_no_atribuible=max(pendiente, Decimal("0")))


def sugerir_origenes(silos, volumen) -> list[SugerenciaOrigen]:
    """Ordena silos utilizables por su capa más antigua y reparte el volumen."""
    pendiente = max(Decimal(str(volumen or 0)), Decimal("0"))
    ordenados = sorted(
        silos,
        key=lambda silo: (
            bool(_dato(silo, "motivos_no_disponible", [])),
            _dato(silo, "leche_mas_antigua_en") is None,
            _dato(silo, "leche_mas_antigua_en") or "9999-12-31",
            _dato(silo, "silo_id"),
        ),
    )
    resultado = []
    for silo in ordenados:
        disponible = max(
            Decimal(str(_dato(silo, "litros_disponibles", 0))), Decimal("0")
        )
        motivos = tuple(_dato(silo, "motivos_no_disponible", []))
        tomado = min(disponible, pendiente) if not motivos else Decimal("0")
        antiguedad = _dato(silo, "antiguedad_horas")
        resultado.append(SugerenciaOrigen(
            silo_id=_dato(silo, "silo_id"),
            litros_disponibles=disponible,
            leche_mas_antigua_en=_dato(silo, "leche_mas_antigua_en"),
            antiguedad_horas=(Decimal(str(antiguedad)) if antiguedad is not None else None),
            motivos_no_disponible=motivos,
            litros_sugeridos=tomado,
            sugerido=tomado > 0,
        ))
        pendiente -= tomado
    return resultado


def saldo_por_recepcion(movimientos, atribuciones) -> list[CapaSilo]:
    """Reconstruye las capas disponibles sin reemplazar el saldo contable."""
    atribuciones_por_movimiento = {}
    for atribucion in atribuciones:
        atribuciones_por_movimiento.setdefault(
            _dato(atribucion, "movimiento_id"), []
        ).append(atribucion)

    capas = []
    orden = 0

    def agregar(recepcion_id, litros, origen=""):
        nonlocal orden
        cantidad = Decimal(str(litros))
        if cantidad <= 0:
            return
        orden += 1
        capas.append({
            "recepcion_id": recepcion_id,
            "litros": cantidad,
            "orden": orden,
            "origen_no_atribuible": origen,
        })

    def descontar(recepcion_id, litros, origen=""):
        pendiente = Decimal(str(litros))
        candidatas = [
            capa for capa in capas
            if capa["litros"] > 0 and (
                (recepcion_id is not None and capa["recepcion_id"] == recepcion_id)
                or (
                    recepcion_id is None
                    and capa["recepcion_id"] is None
                    and (not origen or capa["origen_no_atribuible"] == origen)
                )
            )
        ]
        for capa in candidatas:
            tomado = min(capa["litros"], pendiente)
            capa["litros"] -= tomado
            pendiente -= tomado
            if pendiente <= 0:
                break
        return pendiente

    ordenados = sorted(
        movimientos,
        key=lambda mov: (
            _dato(mov, "fecha_hora"), _dato(mov, "id", 0)
        ),
    )
    for movimiento in ordenados:
        cantidad = Decimal(str(_dato(movimiento, "litros", 0)))
        tipo = _dato(movimiento, "tipo")
        es_ingreso = tipo == "ingreso" or (tipo == "ajuste" and cantidad > 0)
        atribuidas = sorted(
            atribuciones_por_movimiento.get(_dato(movimiento, "id"), []),
            key=lambda item: _dato(item, "orden", 0),
        )
        if es_ingreso:
            if atribuidas:
                for item in atribuidas:
                    agregar(
                        _dato(item, "recepcion_id"), _dato(item, "litros"),
                        _dato(item, "origen_no_atribuible", ""),
                    )
            elif _dato(movimiento, "origen_tipo") == "recepcion":
                agregar(_dato(movimiento, "origen_id"), cantidad)
            else:
                agregar(None, cantidad, _dato(movimiento, "motivo") or "saldo sin recepción")
            continue

        consumo = abs(cantidad)
        if atribuidas:
            remanente = Decimal("0")
            for item in atribuidas:
                remanente += descontar(
                    _dato(item, "recepcion_id"), _dato(item, "litros"),
                    _dato(item, "origen_no_atribuible", ""),
                )
        else:
            resultado = atribuir_fifo([
                CapaSilo(**capa) for capa in capas if capa["litros"] > 0
            ], consumo)
            for parte in resultado.partes:
                descontar(
                    parte.recepcion_id, parte.litros, parte.origen_no_atribuible
                )

    return [CapaSilo(**capa) for capa in capas if capa["litros"] > 0]


def kilos_desde_litros(litros) -> Decimal | None:
    """Kilos de la guía. Sin litros devuelve None, que no es cero."""
    if litros in (None, ""):
        return None

    return (Decimal(str(litros)) * FACTOR_LITROS_A_KILOS).quantize(Decimal("0.01"))


def diferencia_pesaje(kg_guia, kg_romana) -> Decimal | None:
    """
    Romana menos guía, con su signo (columna M del formato).

    Falta cualquiera de los dos y devuelve None: un cero diría que
    coincidieron, y nadie las comparó.
    """
    if kg_guia in (None, "") or kg_romana in (None, ""):
        return None

    return Decimal(str(kg_romana)) - Decimal(str(kg_guia))


def solidos_totales(grasa, sng) -> float | None:
    """Sólidos totales = grasa + SNG (columna S)."""
    valor_grasa = _numero(grasa)
    valor_sng = _numero(sng)

    if valor_grasa is None or valor_sng is None:
        return None

    return round(valor_grasa + valor_sng, 2)


def solidos_totales_kg(kilos, ts) -> float | None:
    """Kilos de sólidos totales sobre el pesaje real (columna BF)."""
    valor_kilos = _numero(kilos)
    valor_ts = _numero(ts)

    if valor_kilos is None or valor_ts is None:
        return None

    return round(valor_kilos * valor_ts / 100, 3)


# Controles sin los cuales no se puede liberar.
#
# El Delvo detecta antibióticos, y esa leche no entra a la planta bajo ningún
# criterio: sin ese resultado no hay nada que autorizar. Que falte no es
# "conforme", es que nadie lo midió — la misma distinción que hace Calidad
# entre un lote conforme y uno sin análisis (MODELO_DATOS.md §2.2).
#
# Qué controles son obligatorios está pendiente de definir con Calidad (§8.5).
# Este es el piso de seguridad, no la lista final: agregar `inhibidores` u
# `organoleptico` es añadirlos a esta tupla.
CONTROLES_DECISIVOS = ("delvo",)


@dataclass(frozen=True)
class EvaluacionRecepcion:
    # ¿Lo que se midió está dentro de límites? NO significa que se pueda
    # liberar: para eso hay que haber medido lo decisivo. Las dos cosas se
    # separan a propósito, porque confundirlas es lo que dejaba pasar leche
    # sin analizar como si estuviera conforme.
    conforme: bool
    # liberada | retenida | sin_analisis
    estado: str
    motivos: list[str] = field(default_factory=list)
    faltantes: list[str] = field(default_factory=list)

    @property
    def analizada(self) -> bool:
        """¿Hay con qué decidir? Sin esto no se libera ni se retiene."""
        return self.estado != SIN_ANALISIS

    @property
    def liberable(self) -> bool:
        return self.estado == LIBERADA


LIBERADA = "liberada"
RETENIDA = "retenida"
SIN_ANALISIS = "sin_analisis"


@dataclass(frozen=True)
class Ocupacion:
    silo_id: int
    codigo: str
    litros: float
    capacidad: float
    pct: int
    excedido: bool
    negativo: bool


def _numero(valor: Any) -> float | None:
    if valor is None or valor == "" or isinstance(valor, bool):
        return None

    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None

    return None if numero != numero else numero


def crioscopia_pool(valores) -> float | None:
    """
    Promedio de las crioscopías de los módulos que sí se midieron.

    Es lo que la hoja `Pool Crioscopia` calcula. Sirve para informar, no para
    decidir: el veredicto lo da cada módulo por separado, porque un promedio
    esconde el compartimiento aguado entre los que no lo están.
    """
    medidos = [numero for numero in (_numero(v) for v in valores or []) if numero is not None]

    if not medidos:
        return None

    return round(sum(medidos) / len(medidos), 3)


def evaluar_recepcion(
    controles: dict[str, Any],
    *,
    crioscopias: Iterable[tuple[Any, Any]] = (),
    ph_camion: Any = None,
    limites: dict | None = None,
) -> EvaluacionRecepcion:
    """
    ¿La leche del camión puede liberarse al silo?

    Delvo o inhibidores positivos retienen automáticamente: son presencia de
    antibióticos, y esa leche no entra a la planta.

    Devuelve los motivos, no solo un booleano, para que la pantalla pueda
    explicar por qué se retuvo (MODELO_DATOS.md §2.10).

    Sin los controles decisivos NO devuelve "liberada": devuelve
    `sin_analisis`. Antes, una recepción con los controles vacíos salía
    conforme —no había motivos que informar— y la pantalla decía "Sin
    alertas" sobre leche que nadie había medido.

    `crioscopias` recibe pares `(numero, crioscopia)`, uno por
    `ModuloRecepcion` medido — no una lista posicional. El número lo pone el
    módulo (`ModuloRecepcion.numero`, 1 a 4, único por recepción pero sin
    garantía de ser contiguo: un camión puede traer registrados los módulos 1
    y 3, sin el 2). Enumerar la lista por posición etiquetaría el motivo con
    el índice equivocado — "M2" sobre lo que en realidad es el módulo 3—, y
    ese motivo es lo que le dice a Calidad qué compartimiento re-muestrear.
    """
    c = controles or {}
    lim = {**LIMITES, **(limites or {})}
    motivos: list[str] = []

    faltantes = [
        control
        for control in CONTROLES_DECISIVOS
        if c.get(control) in (None, "")
    ]

    if c.get("delvo") == "Positivo":
        motivos.append("Delvo Test positivo (presencia de antibióticos).")

    if c.get("inhibidores") == "Positivo":
        motivos.append("Inhibidores positivos.")

    if c.get("organoleptico") == "No conforme":
        motivos.append("Evaluación organoléptica no conforme.")

    etiquetas = {
        "sangre": "sangre",
        "pus": "pus",
        "materias_extranas": "materias extrañas",
        "aroma": "aroma",
    }
    for clave, etiqueta in etiquetas.items():
        if c.get(clave) == "No conforme":
            motivos.append(f"Inspección visual no conforme: {etiqueta}.")

    acidez = _numero(c.get("acidez"))
    if acidez is not None and acidez > lim["acidez_max"]:
        motivos.append(
            f"Acidez {acidez} °D sobre el máximo ({lim['acidez_max']} °D)."
        )

    ph = _numero(c.get("ph"))
    if ph is not None and not (lim["ph_min"] <= ph <= lim["ph_max"]):
        motivos.append(f"pH {ph} fuera del rango {lim['ph_min']}–{lim['ph_max']}.")

    temperatura = _numero(c.get("temperatura"))
    if temperatura is not None and temperatura > lim["temperatura_max"]:
        motivos.append(
            f"Temperatura {temperatura} °C sobre el máximo "
            f"({lim['temperatura_max']} °C)."
        )

    for numero, valor in crioscopias or []:
        medida = _numero(valor)
        if medida is not None and medida > lim["crioscopia_max"]:
            motivos.append(
                f"Crioscopía del módulo M{numero} ({medida}) indica posible aguado."
            )

    ph_del_camion = _numero(ph_camion)
    if ph_del_camion is not None and not (
        lim["ph_camion_min"] <= ph_del_camion <= lim["ph_camion_max"]
    ):
        motivos.append(
            f"pH del camión {ph_del_camion} fuera del rango "
            f"{lim['ph_camion_min']}–{lim['ph_camion_max']}."
        )

    # Un motivo manda sobre la falta de datos: si el Delvo salió positivo, la
    # leche se retiene aunque falten los demás controles.
    if motivos:
        estado = RETENIDA
    elif faltantes:
        estado = SIN_ANALISIS
    else:
        estado = LIBERADA

    return EvaluacionRecepcion(
        # `conforme` sigue significando lo mismo que antes: nada de lo medido
        # se salió de rango. Lo que cambia es `estado`, que es el que decide.
        conforme=not motivos,
        estado=estado,
        motivos=motivos,
        faltantes=faltantes,
    )


def ocupacion_silo(silo: Any, movimientos: Iterable[Any], hasta=None) -> Ocupacion:
    """
    Ocupación real de un silo: la suma de su libro de movimientos.

    No es el acumulado histórico de recepciones — descuenta lo consumido
    (MODELO_DATOS.md §2.4).

    Un saldo negativo no se corrige aquí: se informa. Significa que el
    registro está descuadrado, y esconderlo con un max(0, …) haría que el
    error nunca se descubriera.
    """
    litros = Decimal("0")

    for movimiento in movimientos or []:
        if movimiento.silo_id != silo.id:
            continue

        if hasta is not None and movimiento.fecha_hora > hasta:
            continue

        valor = Decimal(str(movimiento.litros or 0))

        if movimiento.tipo == "ingreso":
            litros += valor
        elif movimiento.tipo == "salida":
            litros -= valor
        else:
            # Ajuste: suma con su signo, que puede ser negativo.
            litros += valor

    capacidad = Decimal(str(silo.capacidad_l or 0))

    return Ocupacion(
        silo_id=silo.id,
        codigo=silo.codigo,
        litros=float(litros),
        capacidad=float(capacidad),
        pct=int(round(litros / capacidad * 100)) if capacidad else 0,
        excedido=capacidad > 0 and litros > capacidad,
        negativo=litros < 0,
    )


def trazabilidad_lote(lote_id: int, movimientos: Iterable[Any]) -> list[dict]:
    """
    De qué silos consumió un lote y qué recepciones habían ingresado a esos
    silos antes del consumo.

    Devuelve un CONJUNTO de recepciones candidatas, no una cadena uno a uno
    (MODELO_DATOS.md §2.5): la leche se mezcla dentro del silo, así que
    prometer un vínculo exacto sería falso.
    """
    movimientos = list(movimientos or [])

    consumos = [
        m
        for m in movimientos
        if m.tipo == "salida" and m.origen_tipo == "lote" and m.origen_id == lote_id
    ]

    resultado = []

    for consumo in consumos:
        ids_recepcion = [
            m.origen_id
            for m in movimientos
            if m.silo_id == consumo.silo_id
            and m.tipo == "ingreso"
            and m.origen_tipo == "recepcion"
            and m.fecha_hora <= consumo.fecha_hora
        ]

        resultado.append(
            {
                "silo_id": consumo.silo_id,
                "litros": float(consumo.litros or 0),
                "fecha_hora": consumo.fecha_hora,
                "recepciones": ids_recepcion,
            }
        )

    return resultado


# Horas de permanencia libres antes de que empiece a contar la sobreestadía.
# Es el valor de la celda AI14 del formato (0,0833 de día = 2 h).
LIMITE_PERMANENCIA_HORAS = 2.0


@dataclass(frozen=True)
class Permanencia:
    # Horas por sobre el límite libre. None cuando falta una marca horaria:
    # nunca cero, porque un cero se suma y una ausencia no.
    horas: float | None
    horas_en_planta: float | None
    motivo: str = ""


def horas_entre(inicio, fin) -> float | None:
    """
    Horas entre dos marcas del reloj.

    Si el fin es anterior al inicio, cruzó la medianoche y se suman 24 h: el
    turno C existe, y un camión que arriba 23:30 y termina 01:00 estuvo hora y
    media, no menos veintidós.
    """
    if inicio is None or fin is None:
        return None

    minutos = (fin.hour * 60 + fin.minute) - (inicio.hour * 60 + inicio.minute)

    if minutos < 0:
        minutos += 24 * 60

    return minutos / 60


def permanencia(
    arribo, termino_cip, limite_horas: float = LIMITE_PERMANENCIA_HORAS
) -> Permanencia:
    """
    Horas de permanencia por sobre el límite libre.

    Se cuenta desde el **arribo a portería** hasta el término del lavado CIP.
    El formato la cuenta desde la «hora programa», que en los 26 libros de
    julio está llena en 1 de 603 filas: restaba contra cero y devolvía la hora
    del reloj menos dos. Por eso aquí un dato ausente devuelve None con su
    motivo, y no un número que alguien va a sumar.
    """
    if arribo is None:
        return Permanencia(None, None, "Falta la hora de arribo a portería.")

    if termino_cip is None:
        return Permanencia(None, None, "Falta la hora de término del lavado CIP.")

    en_planta = horas_entre(arribo, termino_cip)

    return Permanencia(
        horas=round(max(0.0, en_planta - limite_horas), 2),
        horas_en_planta=round(en_planta, 2),
    )


def bloqueos_de_cierre(
    controles: dict[str, Any], *, busquedas_a_proveedor: int = 0
) -> list[str]:
    """
    Qué impide cerrar la recepción.

    Devuelve motivos y no un booleano, igual que el resto de las decisiones
    del sistema: la pantalla tiene que poder decir por qué no se pudo.
    """
    c = controles or {}
    bloqueos: list[str] = []

    positivo = c.get("delvo") == "Positivo" or c.get("inhibidores") == "Positivo"

    if positivo and busquedas_a_proveedor == 0:
        bloqueos.append(
            "Inhibidores positivos: falta registrar la búsqueda a proveedores "
            "antes de cerrar la recepción."
        )

    return bloqueos


def horas_a_pagar(horas) -> int | None:
    """
    Redondeo comercial del formato (columna AT): sube solo si la fracción
    **supera** la media hora. Exactamente 0,5 no sube.
    """
    if horas is None:
        return None

    entero = int(horas)

    return entero + (1 if horas - entero > 0.5 else 0)


#: Los siete parámetros que el vale de trazabilidad pide por silo.
PARAMETROS_ANALISIS_SILO = (
    "ph", "acidez", "grasa", "sng", "proteina", "temperatura", "densidad",
)


@dataclass(frozen=True)
class Vigencia:
    """Si un análisis todavía describe lo que hay en el silo, y por qué no."""

    vigente: bool
    motivo: str


def analisis_vigente(tomado_en, ingresos) -> Vigencia:
    """
    Un análisis vale mientras nadie haya agregado leche después de la muestra.

    `ingresos` son pares `(fecha_hora, litros)` de los ingresos del silo, ya
    filtrados por quien llama: esta función no consulta la base.

    Devuelve motivo y no solo un booleano porque quien lo lee necesita saber
    qué hacer —y lo que hay que hacer es volver a muestrear.
    """
    if tomado_en is None:
        return Vigencia(False, "El análisis no tiene hora de muestreo.")

    posteriores = [
        (cuando, litros) for cuando, litros in ingresos if cuando > tomado_en
    ]

    return analisis_vigente_resumido(
        tomado_en,
        cantidad_ingresos=len(posteriores),
        litros_ingresados=sum((litros for _, litros in posteriores), 0),
    )


def analisis_vigente_resumido(
    tomado_en, *, cantidad_ingresos: int, litros_ingresados
) -> Vigencia:
    """Misma decisión a partir de un resumen calculado por la base."""
    if tomado_en is None:
        return Vigencia(False, "El análisis no tiene hora de muestreo.")

    if not cantidad_ingresos:
        return Vigencia(True, "")

    palabra = "ingreso" if cantidad_ingresos == 1 else "ingresos"

    return Vigencia(
        False,
        f"Entraron {litros_ingresados:g} L al silo después de la muestra "
        f"({cantidad_ingresos} {palabra}); vuelve a muestrear.",
    )


def motivos_silo_no_disponible(silo, analisis, ciclo_cip, ahora, *, para) -> list[str]:
    """Razones operativas; una lista vacía habilita la operación solicitada."""
    if para not in {"proceso", "descarga"}:
        raise ValueError("La disponibilidad solo se evalúa para proceso o descarga.")

    motivos = []
    estado = _dato(silo, "estado")
    if not _dato(silo, "activo", True) or estado == "fuera_servicio":
        motivos.append("El silo está fuera de servicio.")
    if estado == "bloqueado_calidad":
        motivos.append("El silo está bloqueado por Calidad.")
    cip_en_curso = ciclo_cip and _dato(ciclo_cip, "estado") == "en_curso"
    if estado == "en_cip" or cip_en_curso:
        motivos.append("El silo tiene un ciclo CIP en curso.")

    # Descargar un camión solo se detiene por seguridad operacional. La
    # muestra describe el contenido después de descargar, no antes.
    if para == "descarga" or motivos:
        return motivos

    if analisis is None:
        return ["El silo no tiene un análisis confirmado vigente."]
    if not _dato(analisis, "vigente", False):
        motivos.append(
            _dato(analisis, "motivo_vigencia")
            or "El análisis del silo perdió vigencia; vuelve a muestrear."
        )
    faltantes = [
        nombre for nombre in ("grasa", "sng")
        if _dato(analisis, nombre) is None
    ]
    if faltantes:
        motivos.append(
            "Falta composición del silo: " + ", ".join(faltantes) + "."
        )
    if _dato(analisis, "inhibidores_resultado") == "positivo":
        motivos.append("El análisis del silo detectó inhibidores positivos.")
    elif not _dato(analisis, "apto_inocuidad", False):
        motivos.append("Falta completar el control de inhibidores del silo.")
    if not _dato(analisis, "analista_id") or not _dato(analisis, "visualizado_por_id"):
        motivos.append("El análisis requiere firma de realización y visualización.")

    leche_mas_antigua_en = _dato(silo, "leche_mas_antigua_en")
    if leche_mas_antigua_en is not None and ahora - leche_mas_antigua_en > timedelta(hours=48):
        revalidaciones = (
            _dato(analisis, "alcohol_75_conforme"),
            _dato(analisis, "hervor_conforme"),
            _dato(analisis, "organoleptico_conforme"),
        )
        if not all(valor is True for valor in revalidaciones):
            motivos.append(
                "La leche supera 48 h y requiere alcohol 75°, hervor y control organoléptico conformes."
            )
    return motivos


def parametros_faltantes(valores, requeridos) -> list[str]:
    """
    Cuáles de `requeridos` no están cargados en `valores`.

    Un parámetro ausente y uno en `None` son lo mismo: no se midió.
    """
    return [nombre for nombre in requeridos if valores.get(nombre) is None]
