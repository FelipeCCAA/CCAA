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
    "maestros.DocumentoLiberacion", "calidad.RegistroEquipo", "maestros.Equipo",
}
FUENTES = CATALOGOS | {
    "produccion.Lote", "produccion.Analisis", "produccion.ControlProceso",
    "produccion.ControlProcesoLectura", "produccion.RegistroEnvase",
    "calidad.RegistroCalidad", "inocuidad.MonitoreoPPRO", "inocuidad.PproLectura",
    "recepcion.AnalisisSilo", "procesos.SalidaProceso", "procesos.AutorizacionReproceso",
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
    padres = {
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


def evidencia_lote(lote_id, *, bloquear=False):
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


def evidencia_salida(salida_id, *, bloquear=False, analisis_silo_id=None, analisis_lote_id=None):
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
    return {
        "formato": 1, "sujeto": {"salida": salida_id}, "salida": _fila(salida),
        "lote": _fila(salida.lote) if salida.lote_id else None,
        "producto": _filas(Producto.objects.filter(pk=producto_id), bloquear),
        "especificacion": _fila(especificacion) if especificacion else None,
        "analisis_silo": _filas(AnalisisSilo.objects.filter(pk=analisis_silo_id or getattr(decision, "analisis_silo_id", None)), bloquear),
        "analisis_lote": _filas(Analisis.objects.filter(pk=analisis_lote_id or getattr(decision, "analisis_lote_id", None)), bloquear),
    }


def registrar_firma_lote(liberacion, *, evidencia=None):
    liberacion.evidencia_firmada = evidencia if evidencia is not None else evidencia_lote(liberacion.lote_id, bloquear=True)
    _registrar_firma(liberacion)


def registrar_firma_salida(liberacion, *, evidencia=None):
    liberacion.evidencia_firmada = evidencia if evidencia is not None else evidencia_salida(liberacion.salida_id, bloquear=True)
    _registrar_firma(liberacion)


def _registrar_firma(liberacion):
    liberacion.firma_id = uuid4()
    liberacion.version_firmada = liberacion.version_evidencia
    liberacion.save(update_fields=["firma_id", "version_firmada", "evidencia_firmada"])


def _exigir(modelo, campo, identificador, calculador, *, bloquear):
    if bloquear:
        bloquear_catalogo()
    evidencia = calculador(identificador, bloquear=bloquear)
    consulta = modelo.objects.filter(**{campo: identificador})
    if bloquear:
        consulta = consulta.select_for_update()
    decision = consulta.first()
    estados = getattr(modelo, "ESTADOS_LIBERADO", (modelo.Estado.LIBERADO,))
    if (
        decision is None or decision.estado not in estados or not decision.firma_vigente
        or decision.evidencia_firmada != evidencia
    ):
        raise ValidationError("La aprobación de Calidad no está vigente. Calidad debe revisar y firmar nuevamente.")
    return str(decision.firma_id)


def exigir_liberacion_lote_vigente(lote_id, *, bloquear=True):
    from .models import Liberacion
    return _exigir(Liberacion, "lote_id", lote_id, evidencia_lote, bloquear=bloquear)


def exigir_liberacion_salida_vigente(salida_id, *, bloquear=True):
    from .models import LiberacionProceso
    return _exigir(LiberacionProceso, "salida_id", salida_id, evidencia_salida, bloquear=bloquear)


def bloquear_evidencias_despacho(lote_ids, salida_ids):
    """Todos los materiales se leen antes de tomar la primera aprobación."""
    bloquear_catalogo()
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

    # Compara primero sin locks adicionales: conserva la dirección del escritor.
    # Al actualizar, relee bajo lock la aprobación por si otro escritor ya retiró
    # su vigencia. No importa cuántos cambios sigan: nunca se reactiva por hash.
    for consulta, calculador, campo, estado in (
        (candidatos, evidencia_lote, "lote_id", Liberacion.Estado.EN_REVISION),
        (procesos, evidencia_salida, "salida_id", LiberacionProceso.Estado.PENDIENTE),
    ):
        for decision in consulta.order_by("pk"):
            if decision.evidencia_firmada == calculador(getattr(decision, campo)):
                continue
            actual = type(decision).objects.using(using).select_for_update().get(pk=decision.pk)
            if actual.estado != decision.estado or actual.firma_id != decision.firma_id:
                continue
            actual.estado = estado
            actual.version_evidencia += 1
            actual.save(update_fields=["estado", "version_evidencia"])
