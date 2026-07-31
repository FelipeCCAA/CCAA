"""
Explosión de recetas. Traducción de `prototipo/js/modelo/recetas.js`.

Funciones puras: no tocan la base de datos, no importan modelos y no dependen
de Django. Reciben datos y devuelven datos, igual que los demás dominios.

La decisión que las justifica (MODELO_DATOS.md §2.7): una tabla plana
"producto → litros de leche" no basta, porque la mantequilla no se hace con
leche, se hace con crema. La explosión encadena transformaciones:

    mantequilla 1 kg ──► crema 2 kg ──► leche fresca 8 L

Y se detiene en las materias primas. Si llega a un producto sin receta que
**no** es materia prima, lo informa en vez de devolver un número incompleto:
un requerimiento a medias se parece demasiado a uno completo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Iterable


MATERIA_PRIMA = "materia_prima"


@dataclass
class Nodo:
    """Un producto dentro del árbol de necesidades, con su cantidad escalada."""

    producto_id: int
    producto: Any
    nombre: str
    cantidad: float
    unidad: str
    naturaleza: str | None
    receta: Any = None
    hijos: list["Nodo"] = field(default_factory=list)
    # El producto ya estaba en la rama: seguir colgaría el cálculo.
    ciclo: bool = False
    # No tiene receta y no es materia prima: la cadena queda incompleta.
    sin_receta: bool = False
    merma: float = 0.0


@dataclass
class Explosion:
    """Necesidades totales para producir una cantidad de un producto."""

    arbol: Nodo
    # {producto_id: cantidad} de todo lo que hace falta, a cualquier nivel.
    requerimientos: dict[int, float] = field(default_factory=dict)
    # Solo las hojas que son materia prima. Es lo que consume la planta.
    materia_prima: dict[int, float] = field(default_factory=dict)
    ciclo: bool = False
    sin_receta: list[int] = field(default_factory=list)

    @property
    def total_materia_prima(self) -> float:
        return sum(self.materia_prima.values())

    @property
    def completa(self) -> bool:
        """¿Se pudo llegar hasta las materias primas sin cortar la cadena?"""
        return not self.ciclo and not self.sin_receta


def _numero(valor: Any) -> float:
    if valor is None or valor == "":
        return 0.0

    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def receta_vigente(recetas: Iterable[Any], producto_id: int, fecha: date) -> Any | None:
    """
    Receta vigente de un producto en una fecha.

    Un lote de mayo se explota con la receta de mayo, aunque hoy rija otra
    (MODELO_DATOS.md §2.3, mismo criterio que las especificaciones). Si dos
    versiones se solaparan, gana la de vigencia más reciente y, a igualdad de
    fecha, la de versión mayor.
    """
    candidatas = [
        r
        for r in (recetas or [])
        if r.producto_id == producto_id
        and r.vigente_desde <= fecha
        and (r.vigente_hasta is None or r.vigente_hasta >= fecha)
    ]

    if not candidatas:
        return None

    return max(candidatas, key=lambda r: (r.vigente_desde, r.version or 0))


def _arbol(
    productos: dict[int, Any],
    recetas: Iterable[Any],
    producto_id: int,
    cantidad: float,
    fecha: date,
    visitados: tuple[int, ...] = (),
) -> Nodo:
    """
    Árbol de necesidades para obtener `cantidad` de un producto.

    `visitados` corta los ciclos: una receta que se necesita a sí misma
    —directa o indirectamente— colgaría el cálculo, así que se marca el nodo
    y se detiene la rama.
    """
    producto = productos.get(producto_id)

    nodo = Nodo(
        producto_id=producto_id,
        producto=producto,
        nombre=producto.nombre if producto else "(producto desconocido)",
        cantidad=_numero(cantidad),
        unidad=(producto.unidad_base if producto else ""),
        naturaleza=(producto.naturaleza if producto else None),
    )

    if producto_id in visitados:
        nodo.ciclo = True
        return nodo

    receta = receta_vigente(recetas, producto_id, fecha)

    if receta is None:
        # Hoja del árbol. Que una materia prima no tenga receta es lo normal;
        # que la tenga un intermedio o un terminado significa que falta.
        nodo.sin_receta = nodo.naturaleza != MATERIA_PRIMA
        return nodo

    nodo.receta = receta

    base = _numero(receta.cantidad_base) or 1.0
    factor = nodo.cantidad / base

    for componente in receta.componentes.all():
        merma = _numero(componente.merma)
        # La merma aumenta lo que hay que meter para sacar lo mismo.
        necesario = _numero(componente.cantidad) * factor * (1 + merma / 100)

        hijo = _arbol(
            productos,
            recetas,
            componente.producto_id,
            necesario,
            fecha,
            visitados + (producto_id,),
        )
        hijo.merma = merma
        nodo.hijos.append(hijo)

    return nodo


def _acumular(nodo: Nodo, explosion: Explosion) -> None:
    if nodo.ciclo:
        explosion.ciclo = True

    if nodo.sin_receta and nodo.producto_id not in explosion.sin_receta:
        explosion.sin_receta.append(nodo.producto_id)

    for hijo in nodo.hijos:
        explosion.requerimientos[hijo.producto_id] = (
            explosion.requerimientos.get(hijo.producto_id, 0.0) + hijo.cantidad
        )

        if hijo.naturaleza == MATERIA_PRIMA:
            explosion.materia_prima[hijo.producto_id] = (
                explosion.materia_prima.get(hijo.producto_id, 0.0) + hijo.cantidad
            )

        _acumular(hijo, explosion)


def explosionar(
    productos: Iterable[Any],
    recetas: Iterable[Any],
    producto_id: int,
    cantidad: float,
    fecha: date,
) -> Explosion:
    """
    Todo lo que hace falta para producir `cantidad` de un producto.

    `productos` y `recetas` llegan cargados por quien llama —una vez, no uno
    por nodo— para que esta función no consulte la base.
    """
    indice = {p.id: p for p in productos}

    raiz = _arbol(indice, recetas, producto_id, cantidad, fecha)

    explosion = Explosion(arbol=raiz)
    _acumular(raiz, explosion)

    return explosion


def insumo_por_unidad(
    productos: Iterable[Any],
    recetas: Iterable[Any],
    producto_id: int,
    fecha: date,
) -> Explosion:
    """
    Materia prima que consume UNA unidad de producto.

    Es el número que hace útil al planificador: para la crema devuelve 4, los
    litros de leche que cuesta un kilo.
    """
    return explosionar(productos, recetas, producto_id, 1, fecha)


def rendimiento_desde_materia_prima(
    productos: Iterable[Any],
    recetas: Iterable[Any],
    producto_id: int,
    cantidad_materia_prima: float,
    fecha: date,
) -> float | None:
    """
    Cuánto producto sale de una cantidad de materia prima. El inverso.

    Devuelve None si la cadena está incompleta: inventar un rendimiento sobre
    una receta rota daría un número que parece bueno y no lo es.
    """
    explosion = insumo_por_unidad(productos, recetas, producto_id, fecha)

    if not explosion.completa or not explosion.total_materia_prima:
        return None

    return _numero(cantidad_materia_prima) / explosion.total_materia_prima


def litros_de_leche(
    productos: Iterable[Any],
    recetas: Iterable[Any],
    producto_id: int,
    kilos: float | Decimal,
    fecha: date,
    materia_prima_id: int | None = None,
) -> float | None:
    """
    Litros de leche que consume producir `kilos` de un producto.

    Es lo que conecta el lote con el libro mayor del silo: sin esto, producir
    no descuenta nada y la ocupación de los silos solo sube.

    Devuelve None si la cadena está incompleta —un producto intermedio sin
    receta, o un ciclo—, porque descontar una cantidad inventada de un silo
    es peor que no descontar nada: el saldo mentiría sin que nadie lo note.

    `materia_prima_id` acota a una materia prima concreta cuando la receta
    consume varias.
    """
    explosion = explosionar(productos, recetas, producto_id, _numero(kilos), fecha)

    if not explosion.completa:
        return None

    if materia_prima_id is not None:
        return explosion.materia_prima.get(materia_prima_id)

    return explosion.total_materia_prima


# ------------------------------------------------------------------ validación

@dataclass(frozen=True)
class Validacion:
    permitido: bool
    bloqueos: list[str] = field(default_factory=list)


def validar_receta(
    receta: Any,
    productos: Iterable[Any],
    recetas: Iterable[Any],
    fecha: date,
) -> Validacion:
    """
    Comprueba una receta antes de darla por buena.

    Detecta el ciclo indirecto —A necesita B, B necesita A—, que el `clean()`
    del modelo no puede ver porque solo mira un componente a la vez.
    """
    bloqueos: list[str] = []
    indice = {p.id: p for p in productos}

    producto = indice.get(receta.producto_id)

    if producto is None:
        bloqueos.append("La receta no apunta a un producto existente.")
        return Validacion(permitido=False, bloqueos=bloqueos)

    if producto.naturaleza == MATERIA_PRIMA:
        bloqueos.append(
            f"{producto.nombre} es materia prima: es donde la explosión se detiene."
        )

    componentes = list(receta.componentes.all())

    if not componentes:
        bloqueos.append("La receta no declara componentes.")

    for componente in componentes:
        hijo = indice.get(componente.producto_id)

        if hijo is None:
            bloqueos.append("Un componente no apunta a un producto existente.")
            continue

        if componente.producto_id == receta.producto_id:
            bloqueos.append(f"{producto.nombre} se lleva a sí mismo como componente.")
            continue

        if componente.unidad != hijo.unidad_base:
            bloqueos.append(
                f"{hijo.nombre} se mide en {hijo.unidad_base}, "
                f"no en {componente.unidad}."
            )

        # Ciclo indirecto: se explota el componente y se mira si vuelve al
        # producto de esta receta.
        rama = explosionar(productos, recetas, componente.producto_id, 1, fecha)
        if receta.producto_id in rama.requerimientos or rama.ciclo:
            bloqueos.append(
                f"Ciclo: {hijo.nombre} termina necesitando {producto.nombre}."
            )

    return Validacion(permitido=not bloqueos, bloqueos=bloqueos)
