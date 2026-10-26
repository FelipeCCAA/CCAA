"""Recorre vínculos explícitos entre salidas, incluso las que no tienen lote.

Cada tramo conserva las cantidades de la entrada y de ambas salidas. Esas
cantidades describen hechos distintos: no son una atribución proporcional de
los componentes de una mezcla a cada lote que la consume después.
"""

from collections import deque
from heapq import heappop, heappush

from .models import EntradaProceso, SalidaProceso


def _salidas(ids):
    return SalidaProceso.objects.filter(pk__in=ids).select_related(
        "lote__producto", "silo", "ejecucion__etapa", "ejecucion__equipo",
        "ejecucion__vale",
    ).order_by("pk")


def _salida_dato(salida):
    ejecucion = salida.ejecucion
    return {
        "id": salida.pk,
        "lote_id": salida.lote_id,
        "silo_id": salida.silo_id,
        "cantidad": salida.cantidad,
        "unidad": salida.unidad,
        "ejecucion": {
            "id": ejecucion.pk,
            "codigo": ejecucion.codigo,
            "etapa": ejecucion.etapa.nombre,
            "tipo": ejecucion.etapa.tipo,
            "vale_id": ejecucion.vale_id,
            "vale_codigo": ejecucion.vale.codigo if ejecucion.vale_id else None,
        },
    }


def _nodo_lote(lote):
    return {
        "id": lote.pk,
        "codigo": lote.codigo_lote,
        "producto": lote.producto.nombre,
        "fecha": lote.fecha,
        "estado": lote.get_estado_display(),
        "cantidad": lote.kg_producidos,
        "unidad": "kg" if lote.kg_producidos is not None else None,
    }


def _tramo(entrada, origen, destino):
    return {
        "origen": _salida_dato(origen),
        "entrada": {
            "id": entrada.pk,
            "ejecucion_id": entrada.ejecucion_id,
            "salida_origen_id": entrada.salida_origen_id,
            "silo_id": entrada.silo_id,
            "tipo": entrada.get_tipo_display(),
            "cantidad": entrada.cantidad,
            "unidad": entrada.unidad,
        },
        "destino": _salida_dato(destino),
    }


def _distancias_lotes(raiz_id, enlaces):
    """Distancia mínima desde la raíz en los enlaces directos ya confirmados."""
    vecinos = {}
    for enlace in enlaces:
        vecinos.setdefault(enlace["origen"], []).append(enlace["destino"])
    distancias = {raiz_id: 0}
    cola = deque([raiz_id])
    while cola:
        actual = cola.popleft()
        for vecino in vecinos.get(actual, []):
            if vecino not in distancias:
                distancias[vecino] = distancias[actual] + 1
                cola.append(vecino)
    return distancias


def _clave_enlace(enlace):
    return (
        enlace["origen"], enlace["destino"], enlace["ejecucion"]["id"],
        enlace["entrada"]["id"], enlace["salida"]["id"],
    )


def ampliar_genealogia_intermedios(lote_id, direccion, resultado, profundidad_maxima=12):
    """Añade tramos enlazados por FK, sin inferir parentesco por silo o código.

    ``nodos`` contiene sólo lotes reales. ``enlaces`` conserva el contrato
    anterior entre lotes; ``tramos`` expone también las salidas intermedias sin
    lote. Una entrada sin ``salida_origen`` no prueba el origen de ese material.
    """
    if direccion not in {"atras", "adelante"}:
        raise ValueError("Dirección inválida.")

    # La genealogía directa ya recorrió parte del grafo. Sus distancias son el
    # presupuesto inicial de cada lote; no se reinicia el máximo al cruzar un
    # vale ni al descubrir un lote por una entrada ligada a una salida.
    from .servicios import _genealogia_lotes_directa

    limite = max(0, profundidad_maxima)
    ampliado = dict(resultado)
    nodos = list(resultado.get("nodos", []))
    enlaces = list(resultado.get("enlaces", []))
    tramos = list(resultado.get("tramos", []))
    ampliado.update(nodos=nodos, enlaces=enlaces, tramos=tramos)
    nodos_vistos = {nodo["id"] for nodo in nodos}
    enlaces_vistos = {_clave_enlace(enlace) for enlace in enlaces}
    tramos_vistos = {
        (tramo["entrada"]["id"], tramo["destino"]["id"])
        for tramo in tramos
    }

    # En dirección «atrás» se camina desde destino a origen.
    orientados = [
        {**enlace, "origen": enlace["destino"], "destino": enlace["origen"]}
        if direccion == "atras" else enlace
        for enlace in enlaces
    ]
    distancias = _distancias_lotes(int(lote_id), orientados)
    pendientes = []
    distancia_salida = {}
    directa_explorada = dict(distancias)

    def agendar_salidas(lote, distancia):
        for salida_id in SalidaProceso.objects.filter(lote_id=lote).values_list(
            "pk", flat=True
        ):
            if distancia < distancia_salida.get(salida_id, limite + 1):
                distancia_salida[salida_id] = distancia
                heappush(pendientes, (distancia, salida_id))

    for lote, distancia in distancias.items():
        if distancia <= limite:
            agendar_salidas(lote, distancia)

    def registrar_lote(lote, distancia, nodo=None, *, reabrir=False):
        if distancia > limite:
            return
        anterior = distancias.get(lote)
        if anterior is not None and anterior <= distancia:
            return
        distancias[lote] = distancia
        if lote not in nodos_vistos:
            nodos.append(nodo)
            nodos_vistos.add(lote)
        agendar_salidas(lote, distancia)
        if reabrir and distancia < directa_explorada.get(lote, limite + 1):
            expandir_directa(lote, distancia)

    def expandir_directa(lote, distancia):
        directa_explorada[lote] = distancia
        parcial = _genealogia_lotes_directa(
            lote, direccion, profundidad_maxima=limite - distancia,
        )
        orientados_parciales = [
            {**enlace, "origen": enlace["destino"], "destino": enlace["origen"]}
            if direccion == "atras" else enlace
            for enlace in parcial["enlaces"]
        ]
        locales = _distancias_lotes(lote, orientados_parciales)
        for enlace in parcial["enlaces"]:
            clave = _clave_enlace(enlace)
            if clave not in enlaces_vistos:
                enlaces.append(enlace)
                enlaces_vistos.add(clave)
        for nodo in parcial["nodos"]:
            local = locales.get(nodo["id"])
            if local is None:
                continue
            global_ = distancia + local
            registrar_lote(nodo["id"], global_, nodo)
            if global_ < directa_explorada.get(nodo["id"], limite + 1):
                directa_explorada[nodo["id"]] = global_

    def agregar(entrada, origen, destino, distancia):
        clave = (entrada.pk, destino.pk)
        if clave not in tramos_vistos:
            tramos.append(_tramo(entrada, origen, destino))
            tramos_vistos.add(clave)
        vecino = origen if direccion == "atras" else destino
        if vecino.lote_id:
            registrar_lote(
                vecino.lote_id, distancia, _nodo_lote(vecino.lote), reabrir=True,
            )
        if distancia < distancia_salida.get(vecino.pk, limite + 1):
            distancia_salida[vecino.pk] = distancia
            heappush(pendientes, (distancia, vecino.pk))

    while pendientes:
        distancia = pendientes[0][0]
        if distancia >= limite:
            break
        ids = set()
        while pendientes and pendientes[0][0] == distancia:
            actual, salida_id = heappop(pendientes)
            if distancia_salida.get(salida_id) == actual:
                ids.add(salida_id)
        if not ids:
            continue
        frontera = list(_salidas(ids))
        siguiente_distancia = distancia + 1
        if direccion == "atras":
            entradas = EntradaProceso.objects.filter(
                ejecucion_id__in={salida.ejecucion_id for salida in frontera},
                salida_origen_id__isnull=False,
            ).select_related(
                "salida_origen__lote__producto", "salida_origen__silo",
                "salida_origen__ejecucion__etapa",
                "salida_origen__ejecucion__equipo",
                "salida_origen__ejecucion__vale",
            ).order_by("pk")
            por_ejecucion = {}
            for entrada in entradas:
                por_ejecucion.setdefault(entrada.ejecucion_id, []).append(entrada)
            for destino in frontera:
                for entrada in por_ejecucion.get(destino.ejecucion_id, []):
                    agregar(entrada, entrada.salida_origen, destino, siguiente_distancia)
        else:
            entradas = list(EntradaProceso.objects.filter(
                salida_origen_id__in={salida.pk for salida in frontera},
            ).order_by("pk"))
            destinos = {}
            for salida in _salidas(SalidaProceso.objects.filter(
                ejecucion_id__in={entrada.ejecucion_id for entrada in entradas}
            ).values_list("pk", flat=True)):
                destinos.setdefault(salida.ejecucion_id, []).append(salida)
            por_origen = {}
            for entrada in entradas:
                por_origen.setdefault(entrada.salida_origen_id, []).append(entrada)
            for origen in frontera:
                for entrada in por_origen.get(origen.pk, []):
                    for destino in destinos.get(entrada.ejecucion_id, []):
                        agregar(entrada, origen, destino, siguiente_distancia)

    return ampliado
