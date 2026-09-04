"""
Los cálculos de la medición. Sin ORM, sin Django, sin reloj.

El tiempo entra como número en la muestra en vez de leerse aquí: una función
que consulta el reloj no se puede probar dos veces con el mismo resultado.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class Muestra:
    ruta: str
    metodo: str
    estado: int
    ms: float
    consultas: int
    ms_sql: float
    t: float
    usuario: str


@dataclass(frozen=True)
class Resumen:
    ruta: str
    llamadas: int
    p50: float | None
    p95: float | None
    p99: float | None
    ms_total: float
    consultas_media: float
    ms_sql_media: float


def percentil(valores, p: float) -> float | None:
    """
    Percentil por rango más cercano.

    Devuelve `None` sin valores, y no cero: cero es un percentil bajísimo, y
    leerlo como tal haría pasar por rapidísimo a un endpoint que nadie llamó.
    """
    if not valores:
        return None

    ordenados = sorted(valores)

    if p <= 0:
        return ordenados[0]

    indice = math.ceil(p / 100 * len(ordenados)) - 1

    return ordenados[max(0, min(indice, len(ordenados) - 1))]


def resumir(muestras) -> list[Resumen]:
    """
    Una fila por ruta, ordenadas por **tiempo total** descendente.

    Por total y no por el más lento: un endpoint de 20 ms llamado 300 veces
    cuesta más que uno de 900 ms llamado una vez, y es el que hay que mirar
    primero.
    """
    por_ruta = defaultdict(list)

    for muestra in muestras:
        por_ruta[muestra.ruta].append(muestra)

    filas = []

    for ruta, grupo in por_ruta.items():
        tiempos = [m.ms for m in grupo]
        filas.append(
            Resumen(
                ruta=ruta,
                llamadas=len(grupo),
                p50=percentil(tiempos, 50),
                p95=percentil(tiempos, 95),
                p99=percentil(tiempos, 99),
                ms_total=sum(tiempos),
                consultas_media=sum(m.consultas for m in grupo) / len(grupo),
                ms_sql_media=sum(m.ms_sql for m in grupo) / len(grupo),
            )
        )

    return sorted(filas, key=lambda f: f.ms_total, reverse=True)


def repeticiones(muestras, ventana_seg: float) -> list[tuple[str, int]]:
    """
    Rutas que el **mismo usuario** pidió más de una vez dentro de la ventana.

    Se agrupa por usuario porque dos operadores abriendo la misma pantalla es
    uso normal; lo que se busca es una pantalla pidiendo lo mismo dos veces.

    Devuelve la racha **más larga** de cada ruta, no el total de llamadas: un
    endpoint pedido tres veces seguidas al montar una pantalla es un problema
    distinto —y peor— que uno pedido treinta veces repartidas en una jornada.
    """
    por_clave = defaultdict(list)

    for muestra in muestras:
        por_clave[(muestra.usuario, muestra.ruta)].append(muestra.t)

    encontradas = defaultdict(int)

    for (_, ruta), tiempos in por_clave.items():
        tiempos.sort()
        inicio = 0
        for fin in range(len(tiempos)):
            # La ventana se arrastra: `inicio` avanza hasta que la distancia
            # con `fin` cabe dentro de `ventana_seg`.
            while tiempos[fin] - tiempos[inicio] > ventana_seg:
                inicio += 1
            racha = fin - inicio + 1
            if racha > 1:
                encontradas[ruta] = max(encontradas[ruta], racha)

    return sorted(encontradas.items(), key=lambda par: par[1], reverse=True)


def conflictos(muestras) -> list[tuple[str, str, int]]:
    """Cantidad de respuestas 409 por ruta y método, de mayor a menor."""
    encontrados = defaultdict(int)

    for muestra in muestras:
        if muestra.estado == 409:
            encontrados[(muestra.ruta, muestra.metodo)] += 1

    return sorted(
        ((ruta, metodo, cantidad) for (ruta, metodo), cantidad in encontrados.items()),
        key=lambda fila: fila[2],
        reverse=True,
    )
