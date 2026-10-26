"""Vigencia de firmas: misma evidencia, mismo sujeto y nuevo acto al renovar.

Los snapshots son evidencia del acto, no un veredicto de calidad persistido.
El veredicto continúa calculándose en el dominio al aprobar. Las escrituras
normales invalidan de forma persistente; comparar la foto es defensa adicional.
"""

import json
from uuid import uuid4

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DEFAULT_DB_ALIAS
from django.db.models import Q

from .evidencia import bloquear_catalogo


CAMPOS = {
    "procesos.EtapaProceso": ("id", "proceso_id", "codigo", "tipo", "orden", "requiere_calidad"),
    "procesos.EjecucionProceso": ("id", "etapa_id", "sucursal_id", "equipo_id", "ruta_producto_id", "vale_id"),
    "procesos.EntradaProceso": (
        "id", "ejecucion_id", "lote_id", "silo_id", "lote_inventario_id",
        "salida_origen_id", "tipo", "cantidad", "unidad",
    ),
    "produccion.Lote": (
        "id", "sucursal_id", "codigo_lote", "producto_id", "fecha", "equipo_id", "linea", "turno",
        "kg_producidos", "bultos", "estado",
    ),
    "produccion.Analisis": ("id", "lote_id", "fecha", "muestra", "valores", "especificacion_id"),
    "maestros.Producto": ("id", "mandante_id", "familia", "formato"),
    "maestros.Equipo": ("id", "sucursal_id", "codigo", "tipo"),
    "maestros.Especificacion": (
        "id", "producto_id", "tipo_analisis", "version", "vigente_desde", "vigente_hasta", "rangos",
    ),
    "maestros.DocumentoLiberacion": (
        "id", "empresa_id", "codigo", "aplica_a", "plantilla", "frecuencia", "evidencia", "activo",
    ),
    # Ubicación y destino son logística: cambiar solo el silo no altera el
    # material aprobado. La hoja sí captura y vuelve a validar ese origen.
    "procesos.SalidaProceso": (
        "id", "ejecucion_id", "lote_id", "producto_id", "naturaleza",
        "clasificacion", "cantidad", "unidad", "registrada_en",
    ),
}
CATALOGOS = {
    "maestros.Producto", "maestros.Especificacion",
    "maestros.DocumentoLiberacion", "calidad.RegistroEquipo", "maestros.Equipo", "procesos.EtapaProceso",
}
FUENTES = CATALOGOS | {
    "produccion.Lote", "produccion.Analisis", "produccion.ControlProceso",
    "produccion.ControlProcesoLectura", "produccion.RegistroEnvase",
    "calidad.RegistroCalidad", "inocuidad.MonitoreoPPRO", "inocuidad.PproLectura",
    "recepcion.AnalisisSilo", "procesos.SalidaProceso", "procesos.AutorizacionReproceso",
    "procesos.EjecucionProceso", "procesos.EntradaProceso",
}


def campos_evidencia(etiqueta):
    if etiqueta in CAMPOS:
        return CAMPOS[etiqueta]
    return tuple(
        campo.attname for campo in apps.get_model(etiqueta)._meta.concrete_fields
        if campo.name not in {"observacion", "abierto_por", "abierto_en"}
        and not getattr(campo, "auto_now", False)
    )


def _json(valor):
    return json.loads(json.dumps(valor, cls=DjangoJSONEncoder, sort_keys=True))


def _filas(consulta, bloquear=False):
    # El cerrojo compartido del catálogo ya protege sus filas y las altas.
    # No serializar lotes independientes por un producto/equipo compartido.
    if bloquear and consulta.model._meta.label not in CATALOGOS:
        consulta = consulta.select_for_update(of=("self",))
    return _json(list(consulta.order_by("pk").values(*campos_evidencia(consulta.model._meta.label))))


def _fila(objeto):
    return _json({campo: getattr(objeto, campo) for campo in campos_evidencia(objeto._meta.label)})


def preparar_escritura(objeto, anterior, *, using=DEFAULT_DB_ALIAS):
    """Protege también altas, que todavía no tienen una fila para bloquear."""
    etiqueta = objeto._meta.label
    if etiqueta in CATALOGOS:
        bloquear_catalogo(escritura=True, using=using)
        return
    if etiqueta == "recepcion.AnalisisSilo":
        # Los consumos/FIFO mantienen el silo bloqueado hasta confirmar.
        # Una corrección del análisis debe compartir esa frontera antes de
        # escribir: bloquear sólo la muestra deja cambiar Calidad en vuelo.
        ids = {objeto.silo_id, (anterior or {}).get("silo_id")} - {None}
        list(apps.get_model("maestros.Silo")._base_manager.using(using)
             .select_for_update().filter(pk__in=ids).order_by("pk"))
        return
    padres = {
        "procesos.EntradaProceso": ("procesos.EjecucionProceso", "ejecucion_id"),
        "produccion.Analisis": ("produccion.Lote", "lote_id"),
        "calidad.RegistroCalidad": ("produccion.Lote", "lote_id"),
        "produccion.ControlProceso": ("produccion.Lote", "lote_id"),
        "inocuidad.MonitoreoPPRO": ("produccion.Lote", "lote_id"),
        "produccion.RegistroEnvase": ("produccion.Lote", "lote_id"),
        "procesos.AutorizacionReproceso": ("produccion.Lote", "lote_id"),
        "produccion.ControlProcesoLectura": ("produccion.ControlProceso", "control_id"),
        "inocuidad.PproLectura": ("inocuidad.MonitoreoPPRO", "monitoreo_id"),
    }
    if etiqueta in padres:
        modelo, campo = padres[etiqueta]
        nuevo = getattr(objeto, campo)
        # Una actualización normal bloquea su propia fuente. Tomar después el
        # padre invertiría el orden del lector. Las altas/reasignaciones toman
        # el padre ANTES del INSERT/UPDATE para cerrar el hueco de filas nuevas.
        if anterior is None or anterior.get(campo) != nuevo:
            ids = {nuevo, (anterior or {}).get(campo)} - {None}
            list(apps.get_model(modelo)._base_manager.using(using).select_for_update().filter(pk__in=ids).order_by("pk"))


def evidencia_lote_v1(lote_id, *, bloquear=False):
    from maestros.models import DocumentoLiberacion, Equipo, Especificacion, Producto
    from produccion import dominio as dominio_produccion
    from produccion.models import Analisis, ControlProceso, ControlProcesoLectura, Lote, RegistroEnvase
    from inocuidad.models import MonitoreoPPRO, PproLectura
    from procesos.models import AutorizacionReproceso
    from recepcion.models import MovimientoSilo
    from . import dominio
    from .models import RegistroCalidad, RegistroEquipo

    consulta = Lote.objects.filter(pk=lote_id)
    if bloquear:
        consulta = consulta.select_for_update()
    lote = consulta.get()
    documentos = list(DocumentoLiberacion.objects.order_by("pk"))
    documentos = dominio.documentos_aplicables(documentos, lote.producto)
    ids_documentos = [documento.pk for documento in documentos]
    especificaciones = list(Especificacion.objects.filter(producto_id=lote.producto_id))
    especificacion = dominio_produccion.especificacion_vigente(especificaciones, lote.producto_id, lote.fecha)
    controles = ControlProceso.objects.filter(lote_id=lote_id)
    monitoreos = MonitoreoPPRO.objects.filter(lote_id=lote_id)
    periodicos = RegistroEquipo.objects.filter(documento_id__in=ids_documentos)
    cubren = [
        registro for registro in periodicos.order_by("pk").select_related("documento")
        if dominio.cubre_al_lote(registro, registro.documento, lote)
    ]
    equipos_id = {lote.equipo_id} - {None}
    equipos_id.update(controles.values_list("equipo_id", flat=True))
    equipos_id.update(monitoreos.exclude(equipo_id=None).values_list("equipo_id", flat=True))
    equipos_id.update(registro.equipo_id for registro in cubren if registro.equipo_id)
    return {
        "formato": 1, "sujeto": {"lote": lote.pk}, "lote": _fila(lote),
        "producto": _filas(Producto.objects.filter(pk=lote.producto_id), bloquear),
        "especificacion": _fila(especificacion) if especificacion else None,
        "documentos": [_fila(documento) for documento in documentos],
        "analisis": _filas(Analisis.objects.filter(lote_id=lote_id), bloquear),
        "registros": _filas(RegistroCalidad.objects.filter(lote_id=lote_id, documento_id__in=ids_documentos), bloquear),
        "controles": _filas(controles, bloquear),
        "lecturas_control": _filas(ControlProcesoLectura.objects.filter(control__lote_id=lote_id), bloquear),
        "monitoreos": _filas(monitoreos, bloquear),
        "lecturas_ppro": _filas(PproLectura.objects.filter(monitoreo__lote_id=lote_id), bloquear),
        "periodicos": [_fila(registro) for registro in cubren],
        "equipos": _filas(Equipo.objects.filter(pk__in=equipos_id), bloquear),
        "envases": _filas(RegistroEnvase.objects.filter(lote_id=lote_id), bloquear),
        "disposicion_excedente": _filas(AutorizacionReproceso.objects.filter(lote_id=lote_id, origen=AutorizacionReproceso.Origen.EXCEDENTE), bloquear),
        # El libro es inmutable. Cambios de origen/cantidad por SQL directo no
        # son una vía de corrección del sistema; esta foto también los rechaza.
        "consumos": _json(list(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA, origen_tipo=MovimientoSilo.OrigenTipo.LOTE, origen_id=lote_id,
        ).order_by("pk").values("id", "silo_id", "litros", "fecha_hora", "origen_id"))),
    }


def evidencia_salida_v1(salida_id, *, bloquear=False, analisis_silo_id=None, analisis_lote_id=None):
    from maestros.models import Especificacion, Producto
    from procesos.models import SalidaProceso
    from produccion import dominio as dominio_produccion
    from produccion.models import Analisis
    from recepcion.models import AnalisisSilo
    from django.utils import timezone
    from .models import LiberacionProceso

    salidas = SalidaProceso.objects.filter(pk=salida_id)
    if bloquear:
        salidas = salidas.select_for_update()
    salida = salidas.get()
    # Leer el vínculo no toma todavía el lock de aprobación: fuentes primero.
    decision = LiberacionProceso.objects.filter(salida_id=salida_id).first()
    producto_id = salida.producto_id or (salida.lote.producto_id if salida.lote_id else None)
    producto_evaluado = salida.lote.producto_id if salida.lote_id else None
    tipo = Especificacion.TipoAnalisis.SILO if salida.silo_id else Especificacion.TipoAnalisis.LOTE
    fecha = timezone.localdate(salida.registrada_en)
    especificacion = None
    if salida.silo_id and producto_evaluado:
        especificacion = dominio_produccion.especificacion_vigente(
            Especificacion.objects.filter(producto_id=producto_evaluado), producto_evaluado, fecha, tipo,
        )
    if not salida.silo_id:
        analisis = Analisis.objects.filter(pk=analisis_lote_id or getattr(decision, "analisis_lote_id", None)).select_related("especificacion").first()
        if analisis is not None:
            especificacion = analisis.especificacion or dominio_produccion.especificacion_vigente(
                Especificacion.objects.filter(producto_id=producto_evaluado), producto_evaluado, analisis.fecha, tipo,
            )
    evidencia = {
        "formato": 1, "sujeto": {"salida": salida_id}, "salida": _fila(salida),
        "lote": _fila(salida.lote) if salida.lote_id else None,
        "producto": _filas(Producto.objects.filter(pk=producto_id), bloquear),
        "especificacion": _fila(especificacion) if especificacion else None,
        "analisis_silo": _filas(AnalisisSilo.objects.filter(pk=analisis_silo_id or getattr(decision, "analisis_silo_id", None)), bloquear),
        "analisis_lote": _filas(Analisis.objects.filter(pk=analisis_lote_id or getattr(decision, "analisis_lote_id", None)), bloquear),
    }
    if salida.ejecucion.vale_id:
        actos = salida.ejecucion.vale.actos.filter(tipo__in=["adicion", "retiro"])
        if actos.exists():
            evidencia["actos_estandarizacion"] = _json(list(actos.order_by("pk").values("clave", "tipo", "litros", "silo_contraparte_id", "creado_en")))
    return evidencia


def _evidencia_etapa(salida_id, *, bloquear=False, **analisis):
    from maestros.models import Equipo
    from procesos.models import EntradaProceso, SalidaProceso

    foto = evidencia_salida_v1(salida_id, bloquear=bloquear, **analisis)
    salida = SalidaProceso.objects.select_related("ejecucion__etapa").get(pk=salida_id)
    # El lote es identidad compartida. Su equipo/masa/estado actuales no son
    # los del material intermedio: pertenecen a la etapa que está operando.
    if foto["lote"]:
        foto["lote"] = {k: v for k, v in foto["lote"].items() if k not in {"equipo_id", "kg_producidos", "bultos", "estado"}}
    foto.update({
        "formato": 2,
        "ejecucion": _fila(salida.ejecucion), "etapa": _fila(salida.ejecucion.etapa),
        "equipo": _filas(Equipo.objects.filter(pk=salida.ejecucion.equipo_id), bloquear),
        "entradas": _filas(EntradaProceso.objects.filter(ejecucion_id=salida.ejecucion_id), bloquear),
    })
    if salida.ejecucion.vale_id:
        # El vale tiene su propio acto de decisión, no una liberación de lote
        # inventada. Su estado y muestra forman parte de la evidencia material.
        from estandarizacion.models import ValeEstandarizacion
        consulta = ValeEstandarizacion.objects.filter(pk=salida.ejecucion.vale_id)
        if bloquear:
            consulta = consulta.select_for_update()
        foto["vale_estandarizacion"] = _json(consulta.values(
            "id", "estado", "ejecutado_en", "muestreado_en", "grasa_real", "sng_real",
        ).get())
    return foto


def evidencia_salida(salida_id, *, bloquear=False, analisis_silo_id=None, analisis_lote_id=None):
    from .etapas import cadena_salidas, decision_material

    cadena = cadena_salidas(salida_id, bloquear=bloquear)
    foto = _evidencia_etapa(salida_id, bloquear=bloquear, analisis_silo_id=analisis_silo_id, analisis_lote_id=analisis_lote_id)
    foto["antecedentes"] = [
        {"evidencia": _evidencia_etapa(pk, bloquear=bloquear), "aprobacion": decision_material(pk)}
        for pk in cadena if pk != salida_id
    ]
    return foto


def evidencia_lote(lote_id, *, bloquear=False):
    from procesos.models import SalidaProceso
    from .etapas import decision_material

    foto = evidencia_lote_v1(lote_id, bloquear=bloquear)
    foto["formato"] = 2
    foto["procesos"] = [
        {"evidencia": evidencia_salida(pk, bloquear=bloquear), "aprobacion": decision_material(pk)}
        for pk in SalidaProceso.objects.filter(lote_id=lote_id).order_by("pk").values_list("pk", flat=True)
    ]
    return foto


def _foto_actual(decision, calculador, identificador, *, bloquear=False):
    # Un histórico no se convierte en una aprobación nueva. Mientras coincida
    # exactamente con v1 sigue siendo válido; si caduca, sólo Calidad lo renueva.
    if decision.evidencia_firmada.get("formato") == 1:
        calculador = evidencia_lote_v1 if calculador == evidencia_lote else evidencia_salida_v1
    return calculador(identificador, bloquear=bloquear)


def exigir_antecedentes_salida_vigentes(salida_id, *, bloquear=True):
    from procesos.models import SalidaProceso
    from .etapas import cadena_salidas
    from .models import LiberacionProceso

    if bloquear:
        bloquear_catalogo()
    for pk in cadena_salidas(salida_id, bloquear=bloquear):
        if pk == salida_id:
            continue
        fuente = SalidaProceso.objects.select_related("ejecucion__vale", "ejecucion__etapa").get(pk=pk)
        if fuente.ejecucion.vale_id:
            from estandarizacion.balance import balance_vale
            vale = fuente.ejecucion.vale
            if vale.estado != vale.Estado.LIBERADO or balance_vale(vale)["pendiente"]:
                raise ValidationError("El vale de origen requiere revisión y liberación antes de continuar.")
        elif fuente.ejecucion.etapa.requiere_calidad:
            _exigir(LiberacionProceso, "salida_id", pk, evidencia_salida, bloquear=bloquear)


def registrar_firma_lote(liberacion, *, evidencia=None):
    liberacion.evidencia_firmada = evidencia if evidencia is not None else evidencia_lote(liberacion.lote_id, bloquear=True)
    _registrar_firma(liberacion)


def registrar_firma_salida(liberacion, *, evidencia=None):
    exigir_antecedentes_salida_vigentes(liberacion.salida_id)
    liberacion.evidencia_firmada = evidencia if evidencia is not None else evidencia_salida(liberacion.salida_id, bloquear=True)
    _registrar_firma(liberacion)


def _registrar_firma(liberacion):
    liberacion.firma_id = uuid4()
    liberacion.version_firmada = liberacion.version_evidencia
    liberacion.save(update_fields=["firma_id", "version_firmada", "evidencia_firmada"])


def _exigir(modelo, campo, identificador, calculador, *, bloquear):
    if bloquear:
        bloquear_catalogo()
    # Fuentes antes que decisiones, también para las firmas históricas.
    calculador(identificador, bloquear=bloquear)
    consulta = modelo.objects.filter(**{campo: identificador})
    if bloquear:
        consulta = consulta.select_for_update()
    decision = consulta.first()
    evidencia = _foto_actual(decision, calculador, identificador, bloquear=bloquear) if decision else None
    estados = getattr(modelo, "ESTADOS_LIBERADO", (modelo.Estado.LIBERADO,))
    if (
        decision is None or decision.estado not in estados or not decision.firma_vigente
        or decision.evidencia_firmada != evidencia
    ):
        raise ValidationError("La aprobación de Calidad no está vigente. Calidad debe revisar y firmar nuevamente.")
    return str(decision.firma_id)


def exigir_liberacion_lote_vigente(lote_id, *, bloquear=True):
    from .models import Liberacion
    if bloquear:
        bloquear_catalogo()
        apps.get_model("produccion.Lote").objects.select_for_update().get(pk=lote_id)
    exigir_etapas_lote_vigentes(lote_id, bloquear=bloquear)
    return _exigir(Liberacion, "lote_id", lote_id, evidencia_lote, bloquear=bloquear)


def exigir_liberacion_salida_vigente(salida_id, *, bloquear=True):
    from .models import LiberacionProceso
    exigir_antecedentes_salida_vigentes(salida_id, bloquear=bloquear)
    return _exigir(LiberacionProceso, "salida_id", salida_id, evidencia_salida, bloquear=bloquear)


def exigir_etapas_lote_vigentes(lote_id, *, bloquear=True):
    from procesos.models import SalidaProceso
    if bloquear:
        from .etapas import bloquear_cadenas
        bloquear_cadenas(SalidaProceso.objects.filter(lote_id=lote_id).values_list("pk", flat=True))

    for pk in SalidaProceso.objects.filter(
        lote_id=lote_id, naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        ejecucion__etapa__requiere_calidad=True,
    ).order_by("pk").values_list("pk", flat=True):
        exigir_liberacion_salida_vigente(pk, bloquear=bloquear)


def bloquear_evidencias_despacho(lote_ids, salida_ids):
    """Todos los materiales se leen antes de tomar la primera aprobación."""
    bloquear_catalogo()
    from procesos.models import SalidaProceso
    from .etapas import bloquear_cadenas
    bloquear_cadenas(set(salida_ids) | set(SalidaProceso.objects.filter(lote_id__in=lote_ids).values_list("pk", flat=True)))
    for lote_id in sorted(set(lote_ids)):
        evidencia_lote(lote_id, bloquear=True)
    for salida_id in sorted(set(salida_ids)):
        evidencia_salida(salida_id, bloquear=True)


def invalidar_por_cambio(objeto, anterior, despues, *, using=DEFAULT_DB_ALIAS):
    """Nunca toma Lote/Salida ni escribe hojas: fuente → aprobación solamente."""
    from .models import Liberacion, LiberacionProceso

    etiqueta = objeto._meta.label
    valores = [dato for dato in (anterior, despues) if dato]
    lotes = set()
    for dato in valores:
        if dato.get("lote_id"):
            lotes.add(dato["lote_id"])
    if etiqueta == "produccion.Lote":
        lotes.add(objeto.pk)
    if etiqueta == "produccion.ControlProcesoLectura":
        lotes.update(apps.get_model("produccion.ControlProceso").objects.filter(pk__in=[v["control_id"] for v in valores]).values_list("lote_id", flat=True))
    if etiqueta == "inocuidad.PproLectura":
        lotes.update(apps.get_model("inocuidad.MonitoreoPPRO").objects.filter(pk__in=[v["monitoreo_id"] for v in valores]).values_list("lote_id", flat=True))

    candidatos = Liberacion.objects.using(using).filter(estado__in=Liberacion.ESTADOS_LIBERADO, firma_id__isnull=False)
    procesos = LiberacionProceso.objects.using(using).filter(estado=LiberacionProceso.Estado.LIBERADO, firma_id__isnull=False)
    if etiqueta == "maestros.Producto":
        candidatos = candidatos.filter(lote__producto_id=objeto.pk)
        procesos = procesos.filter(Q(salida__producto_id=objeto.pk) | Q(salida__lote__producto_id=objeto.pk))
    elif etiqueta == "maestros.Especificacion":
        productos = {v["producto_id"] for v in valores}
        candidatos = candidatos.filter(lote__producto_id__in=productos)
        procesos = procesos.filter(Q(salida__producto_id__in=productos) | Q(salida__lote__producto_id__in=productos))
    elif etiqueta in {"maestros.DocumentoLiberacion", "calidad.RegistroEquipo", "maestros.Equipo"}:
        procesos = procesos.none()
    else:
        candidatos = candidatos.filter(lote_id__in=lotes)
        if etiqueta == "procesos.SalidaProceso":
            procesos = procesos.filter(salida_id=objeto.pk)
        elif etiqueta == "recepcion.AnalisisSilo":
            procesos = procesos.filter(analisis_silo_id=objeto.pk)
        elif etiqueta == "produccion.Analisis":
            procesos = procesos.filter(analisis_lote_id=objeto.pk)
        elif etiqueta == "produccion.Lote":
            procesos = procesos.filter(salida__lote_id=objeto.pk)
        else:
            procesos = procesos.none()

    # Compara fotos de etapas, incluidas las que consumieron material de otra
    # ejecución/lote. Sólo se retira una firma cuya evidencia cambió o que
    # desciende realmente de un material corregido, nunca por compartir silo.
    from procesos.models import EntradaProceso, SalidaProceso
    from .etapas import cadena_salidas

    afectadas = set()
    potenciales = set()
    if etiqueta == "procesos.SalidaProceso":
        afectadas.add(objeto.pk)
    elif etiqueta in {"procesos.EjecucionProceso", "procesos.EntradaProceso"}:
        ids = {objeto.pk} if etiqueta.endswith("EjecucionProceso") else {v["ejecucion_id"] for v in valores}
        afectadas.update(SalidaProceso.objects.filter(ejecucion_id__in=ids).values_list("pk", flat=True))
    elif etiqueta == "procesos.EtapaProceso":
        afectadas.update(SalidaProceso.objects.filter(ejecucion__etapa_id=objeto.pk).values_list("pk", flat=True))
    elif etiqueta in {"recepcion.AnalisisSilo", "produccion.Analisis"}:
        campo = "analisis_silo_id" if etiqueta.startswith("recepcion.") else "analisis_lote_id"
        afectadas.update(LiberacionProceso.objects.filter(**{campo: objeto.pk}).values_list("salida_id", flat=True))
    elif etiqueta == "produccion.Lote":
        estables = set(CAMPOS[etiqueta]) - {"equipo_id", "kg_producidos", "bultos", "estado"}
        if anterior is None or despues is None or any(anterior[k] != despues[k] for k in estables):
            afectadas.update(SalidaProceso.objects.filter(lote_id=objeto.pk).values_list("pk", flat=True))
    elif etiqueta == "maestros.Producto":
        afectadas.update(SalidaProceso.objects.filter(
            Q(producto_id=objeto.pk) | Q(lote__producto_id=objeto.pk),
        ).values_list("pk", flat=True))
    elif etiqueta == "maestros.Equipo":
        afectadas.update(SalidaProceso.objects.filter(ejecucion__equipo_id=objeto.pk).values_list("pk", flat=True))
    elif etiqueta == "maestros.Especificacion":
        productos = {v["producto_id"] for v in valores}
        potenciales.update(SalidaProceso.objects.filter(
            Q(producto_id__in=productos) | Q(lote__producto_id__in=productos),
        ).values_list("pk", flat=True))
    if etiqueta in {"procesos.EjecucionProceso", "procesos.EntradaProceso", "procesos.EtapaProceso"}:
        procesos = LiberacionProceso.objects.using(using).filter(salida_id__in=afectadas)
    elif etiqueta == "maestros.Equipo":
        procesos = LiberacionProceso.objects.using(using).filter(
            Q(salida__ejecucion__equipo_id=objeto.pk) | Q(salida__lote__equipo_id=objeto.pk),
        )
    # Una especificación futura no cambia necesariamente la evidencia. Revisar
    # las fotos consumidoras permite distinguirla aun si el origen no requiere
    # firma propia. No se presupone una aprobación inexistente en ese origen.
    frontera = set(potenciales)
    while frontera:
        ejecuciones = EntradaProceso.objects.filter(salida_origen_id__in=frontera).values_list("ejecucion_id", flat=True)
        nuevas = set(SalidaProceso.objects.filter(ejecucion_id__in=ejecuciones).values_list("pk", flat=True)) - potenciales
        potenciales.update(nuevas)
        frontera = nuevas
    if potenciales:
        procesos = LiberacionProceso.objects.using(using).filter(
            Q(pk__in=procesos.values("pk")) | Q(salida_id__in=potenciales),
            estado=LiberacionProceso.Estado.LIBERADO, firma_id__isnull=False,
        )
    for decision in procesos.order_by("pk"):
        if decision.evidencia_firmada != _foto_actual(decision, evidencia_salida, decision.salida_id):
            afectadas.add(decision.salida_id)
    frontera = set(afectadas)
    while frontera:
        ejecuciones = EntradaProceso.objects.filter(salida_origen_id__in=frontera).values_list("ejecucion_id", flat=True)
        nuevas = set(SalidaProceso.objects.filter(ejecucion_id__in=ejecuciones).values_list("pk", flat=True)) - afectadas
        afectadas.update(nuevas)
        frontera = nuevas

    # Ancestros antes que descendientes, igual que al exigir o renovar firmas.
    # post_delete conserva el ID anterior para localizar el lote, pero la
    # salida borrada ya no puede formar parte de una cadena consultable.
    afectadas.intersection_update(SalidaProceso.objects.filter(pk__in=afectadas).values_list("pk", flat=True))
    orden, vistos = [], set()
    for pk in sorted(afectadas):
        for material_id in cadena_salidas(pk):
            if material_id in afectadas and material_id not in vistos:
                vistos.add(material_id)
                orden.append(material_id)
    for material_id in orden:
        actual = LiberacionProceso.objects.using(using).select_for_update().filter(
            salida_id=material_id, estado=LiberacionProceso.Estado.LIBERADO, firma_id__isnull=False,
        ).first()
        if actual:
            actual.estado = LiberacionProceso.Estado.PENDIENTE
            actual.version_evidencia += 1
            actual.save(update_fields=["estado", "version_evidencia"])

    lotes_afectados = set(SalidaProceso.objects.filter(pk__in=afectadas).exclude(lote_id=None).values_list("lote_id", flat=True))
    if etiqueta == "procesos.SalidaProceso":
        lotes_afectados.update(lotes)
    candidatos = Liberacion.objects.using(using).filter(
        estado__in=Liberacion.ESTADOS_LIBERADO, firma_id__isnull=False,
    ).filter(Q(pk__in=candidatos.values("pk")) | Q(lote_id__in=lotes_afectados))
    for decision in candidatos.order_by("pk"):
        if decision.lote_id not in lotes_afectados and decision.evidencia_firmada == _foto_actual(decision, evidencia_lote, decision.lote_id):
            continue
        actual = Liberacion.objects.using(using).select_for_update().get(pk=decision.pk)
        if actual.estado != decision.estado or actual.firma_id != decision.firma_id:
            continue
        actual.estado = Liberacion.Estado.EN_REVISION
        actual.version_evidencia += 1
        actual.save(update_fields=["estado", "version_evidencia"])
