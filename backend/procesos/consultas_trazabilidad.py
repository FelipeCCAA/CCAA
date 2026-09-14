"""Modelo de lectura bajo demanda para la trazabilidad operacional."""

from .models import EjecucionProceso, EntradaProceso, EventoProceso, SalidaProceso


TIPOS_REFERENCIA = {"lote", "ejecucion", "salida"}


def _por_id_o_codigo(queryset, referencia, campo_codigo="codigo"):
    referencia = str(referencia).strip()
    if referencia.isdigit():
        por_id = queryset.filter(pk=int(referencia)).first()
        if por_id is not None:
            return por_id
    coincidencias = list(queryset.filter(**{campo_codigo: referencia})[:2])
    if len(coincidencias) > 1:
        raise ValueError(
            f"La referencia «{referencia}» no es única; consulta por ID o pallet."
        )
    return coincidencias[0] if coincidencias else None


def resolver_referencia_trazabilidad(tipo, referencia):
    """Resuelve el lote raíz desde una referencia operacional real."""
    from produccion.models import Lote, PalletProducto

    if tipo not in TIPOS_REFERENCIA:
        raise ValueError("Tipo de referencia inválido.")

    lotes = Lote.objects.select_related(
        "producto", "equipo", "ejecucion", "vale__silo_destino",
        "vale__ejecucion", "liberacion__autorizada_por",
    )
    if tipo == "lote":
        lote = _por_id_o_codigo(lotes, referencia, "codigo_lote")
        if lote is None:
            pallet = _por_id_o_codigo(
                PalletProducto.objects.select_related("envase__lote"), referencia
            )
            lote = lotes.filter(pk=pallet.envase.lote_id).first() if pallet else None
        foco = {
            "tipo": "lote",
            "id": lote.pk if lote else None,
            "codigo": lote.codigo_lote if lote else str(referencia),
        }
    elif tipo == "ejecucion":
        ejecucion = _por_id_o_codigo(
            EjecucionProceso.objects.select_related("etapa"), referencia
        )
        lote = _lote_de_ejecucion(ejecucion, lotes) if ejecucion else None
        foco = {
            "tipo": "ejecucion",
            "id": ejecucion.pk if ejecucion else None,
            "codigo": ejecucion.codigo if ejecucion else str(referencia),
        }
    else:
        salida = (
            SalidaProceso.objects.select_related("ejecucion").filter(pk=referencia).first()
            if str(referencia).isdigit() else None
        )
        lote = _lote_de_salida(salida, lotes) if salida else None
        foco = {
            "tipo": "salida",
            "id": salida.pk if salida else None,
            "codigo": f"Salida {salida.pk}" if salida else str(referencia),
        }

    if lote is None:
        raise LookupError(
            f"No existe una referencia trazable de tipo {tipo} «{referencia}»."
        )
    return lote, foco


def _lote_de_ejecucion(ejecucion, lotes):
    lote_id = (
        ejecucion.salidas.filter(lote_id__isnull=False)
        .order_by("pk").values_list("lote_id", flat=True).first()
    )
    if lote_id is None:
        lote_id = (
            ejecucion.entradas.filter(lote_id__isnull=False)
            .order_by("pk").values_list("lote_id", flat=True).first()
        )
    return lotes.filter(pk=lote_id).first() if lote_id else None


def _lote_de_salida(salida, lotes):
    if salida.lote_id:
        return lotes.filter(pk=salida.lote_id).first()
    lote_id = (
        SalidaProceso.objects.filter(
            ejecucion__entradas__salida_origen=salida,
            lote_id__isnull=False,
        ).order_by("pk").values_list("lote_id", flat=True).first()
    )
    if lote_id is None:
        lote_id = (
            salida.ejecucion.entradas.filter(lote_id__isnull=False)
            .order_by("pk").values_list("lote_id", flat=True).first()
        )
    return lotes.filter(pk=lote_id).first() if lote_id else None


def construir_timeline_trazabilidad(lote, genealogia):
    """Ordena hechos persistidos; no inventa etapas futuras ni estados."""
    from calidad.models import LiberacionProceso
    from produccion.models import RegistroEnvase

    ejecucion_ids = {
        enlace["ejecucion"]["id"] for enlace in genealogia["enlaces"]
    }
    if lote.ejecucion_id:
        ejecucion_ids.add(lote.ejecucion_id)
    if lote.vale_id and getattr(lote.vale, "ejecucion", None):
        ejecucion_ids.add(lote.vale.ejecucion.pk)

    ejecuciones = {
        item.pk: item for item in EjecucionProceso.objects.filter(
            pk__in=ejecucion_ids
        ).select_related("etapa", "equipo", "responsable")
    }
    hechos = []

    def agregar(fecha, categoria, titulo, **detalle):
        if fecha is None:
            return
        hechos.append({
            "fecha_hora": fecha,
            "categoria": categoria,
            "titulo": titulo,
            "estado": detalle.get("estado"),
            "responsable": detalle.get("responsable"),
            "equipo": detalle.get("equipo"),
            "cantidad": detalle.get("cantidad"),
            "unidad": detalle.get("unidad"),
            "detalle": detalle.get("detalle", ""),
        })

    for ejecucion in ejecuciones.values():
        responsable = _nombre_usuario(ejecucion.responsable)
        equipo = ejecucion.equipo.nombre if ejecucion.equipo_id else None
        agregar(
            ejecucion.creada_en, "proceso", f"{ejecucion.etapa.nombre} registrada",
            estado=ejecucion.get_estado_display(), responsable=responsable, equipo=equipo,
            detalle=ejecucion.codigo,
        )
        agregar(
            ejecucion.inicio, "proceso", f"{ejecucion.etapa.nombre} iniciada",
            estado="En ejecución", responsable=responsable, equipo=equipo,
            detalle=ejecucion.codigo,
        )
        agregar(
            ejecucion.termino, "proceso", f"{ejecucion.etapa.nombre} terminada",
            estado=ejecucion.get_estado_display(), responsable=responsable, equipo=equipo,
            detalle=ejecucion.codigo,
        )

    for entrada in EntradaProceso.objects.filter(
        ejecucion_id__in=ejecucion_ids
    ).select_related("ejecucion__etapa", "lote", "silo", "lote_inventario"):
        origen = (
            entrada.lote.codigo_lote if entrada.lote_id
            else entrada.silo.codigo if entrada.silo_id
            else entrada.lote_inventario.codigo
        )
        agregar(
            entrada.registrada_en, "entrada", f"Entrada a {entrada.ejecucion.etapa.nombre}",
            cantidad=entrada.cantidad, unidad=entrada.unidad,
            detalle=f"{origen} · {entrada.get_tipo_display()}",
        )

    salidas = list(SalidaProceso.objects.filter(
        ejecucion_id__in=ejecucion_ids
    ).select_related("ejecucion__etapa", "lote", "silo"))
    for salida in salidas:
        destino_fisico = (
            salida.lote.codigo_lote if salida.lote_id
            else salida.silo.codigo if salida.silo_id else "Sin ubicación registrada"
        )
        agregar(
            salida.registrada_en, "salida", f"Salida de {salida.ejecucion.etapa.nombre}",
            cantidad=salida.cantidad, unidad=salida.unidad,
            detalle=(f"{destino_fisico} · {salida.get_naturaleza_display()} · "
                     f"{salida.get_destino_display()}"),
        )

    for evento in EventoProceso.objects.filter(
        ejecucion_id__in=ejecucion_ids
    ).select_related("ejecucion", "usuario"):
        agregar(
            evento.fecha_hora, "estado", f"Estado de {evento.ejecucion.codigo}",
            estado=evento.estado_nuevo or None,
            responsable=_nombre_usuario(evento.usuario), detalle=evento.motivo,
        )

    for decision in LiberacionProceso.objects.filter(
        salida_id__in=[salida.pk for salida in salidas]
    ).select_related("salida__ejecucion", "decidida_por"):
        analisis = (
            f"Análisis de silo {decision.analisis_silo_id}"
            if decision.analisis_silo_id else
            f"Análisis de lote {decision.analisis_lote_id}"
            if decision.analisis_lote_id else "Sin análisis asociado"
        )
        agregar(
            decision.decidida_en, "calidad",
            f"Calidad: {decision.get_estado_display()}",
            estado=decision.estado, responsable=_nombre_usuario(decision.decidida_por),
            detalle=f"{decision.salida.ejecucion.codigo} · {analisis} · {decision.observacion}",
        )

    for envase in RegistroEnvase.objects.filter(lote=lote).select_related(
        "equipo", "operador"
    ):
        agregar(
            envase.termino, "envasado", "Envasado terminado",
            responsable=_nombre_usuario(envase.operador), equipo=envase.equipo.nombre,
            cantidad=envase.kg_envasados, unidad="kg",
            detalle=f"{envase.unidades} unidades",
        )

    return sorted(hechos, key=lambda hecho: hecho["fecha_hora"])


def ubicacion_actual_lote(lote):
    """Prioriza la ubicación física más reciente conocida del lote."""
    from produccion.models import PalletProducto

    pallet = PalletProducto.objects.filter(
        envase__lote=lote,
        existencia_producto__activo=True,
    ).select_related("existencia_producto__ubicacion").order_by("-creado_en").first()
    if pallet:
        return {
            "tipo": "inventario",
            "codigo": pallet.existencia_producto.ubicacion.codigo,
            "detalle": f"{pallet.codigo} · {pallet.get_estado_display()}",
        }
    salida = lote.salidas_proceso.filter(silo_id__isnull=False).select_related(
        "silo"
    ).order_by("-registrada_en").first()
    if salida:
        return {
            "tipo": "silo",
            "codigo": salida.silo.codigo,
            "detalle": salida.get_destino_display(),
        }
    if lote.ejecucion_id and lote.ejecucion.equipo_id:
        return {
            "tipo": "equipo",
            "codigo": lote.ejecucion.equipo.nombre,
            "detalle": lote.ejecucion.get_estado_display(),
        }
    return {"tipo": "sin_registro", "codigo": "Sin ubicación", "detalle": ""}


def _nombre_usuario(usuario):
    if usuario is None:
        return None
    return usuario.get_full_name() or usuario.username
