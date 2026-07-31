"""
API de liberación de producto.

Dos clases de endpoint, y la diferencia importa:

- Los ViewSets (`registros`, `liberaciones`) guardan hechos: un formulario
  completado, una autorización firmada.
- Los `expedientes` no guardan nada: arman lo que hay que mirar para decidir.
  El avance documental y el veredicto de calidad se calculan en cada llamada
  (MODELO_DATOS.md §2.2 y §2.6), así que no hay nada que sincronizar ni que
  pueda quedar desactualizado.

Firmar una liberación es lo único que cambia el estado del mundo, y por eso es
lo único que va en una transacción.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from inocuidad.models import MonitoreoPPRO
from maestros.models import DocumentoLiberacion, Especificacion
from produccion.models import (
    Analisis,
    ControlProceso,
    ControlProcesoLectura,
    Lote,
)
from recepcion.models import MovimientoSilo
from usuarios.models import rol_de
from usuarios.permisos import EscribeCalidad

from . import dominio
from .models import Liberacion, RegistroCalidad
from .serializers import (
    ConcesionSerializer,
    FirmaSerializer,
    LiberacionSerializer,
    RegistroCalidadSerializer,
    ahora,
    serializar_avance,
    serializar_calidad,
    serializar_decision,
    serializar_discrepancias,
)


class RegistroCalidadViewSet(viewsets.ModelViewSet):
    queryset = RegistroCalidad.objects.select_related(
        "lote", "documento", "completado_por"
    )
    serializer_class = RegistroCalidadSerializer
    permission_classes = [EscribeCalidad]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        lote = parametros.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        return consulta

    def perform_create(self, serializer):
        self._guardar_con_firma(serializer)

    def perform_update(self, serializer):
        self._guardar_con_firma(serializer)

    def _guardar_con_firma(self, serializer):
        """
        Quien completa el formulario queda registrado, con la hora del
        servidor. Es el dato que una auditoría pide primero, y teclearlo a mano
        solo lo haría menos fiable.

        Al volver a borrador se limpia la firma: si el formulario dejó de estar
        completado, decir que alguien lo completó sería falso.
        """
        completado = (
            serializer.validated_data.get(
                "estado", getattr(serializer.instance, "estado", None)
            )
            == RegistroCalidad.Estado.COMPLETADO
        )

        if completado:
            serializer.save(completado_por=self.request.user, completado_en=ahora())
        else:
            serializer.save(completado_por=None, completado_en=None)


class LiberacionViewSet(viewsets.ModelViewSet):
    """
    El expediente de autorización de cada lote.

    Se puede consultar y anotar, pero **no se firma desde aquí**: para eso
    están `expedientes/<lote>/liberar/` y `/conceder/`, que aplican la regla
    antes de estampar la firma. Escribir `estado` a mano por esta vía la
    saltaría.
    """

    queryset = Liberacion.objects.select_related(
        "lote", "lote__producto", "autorizada_por"
    )
    serializer_class = LiberacionSerializer
    permission_classes = [EscribeCalidad]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        lote = parametros.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        return consulta


# --------------------------------------------------------------- expedientes

def _contexto_del_lote(lote, bloquear=False):
    """
    Todo lo que el dominio necesita para juzgar un lote.

    Se carga de una vez y se pasa entero, en lugar de que el dominio consulte:
    así sigue sin depender de la base de datos y se puede probar sin ella.

    `bloquear` es para el camino de la firma. Toma un bloqueo de fila sobre lo
    que la decisión va a leer —los formularios y los análisis— de modo que
    nadie pueda desmarcar un documento o corregir un análisis entre la
    comprobación y el guardado. Sin él, `transaction.atomic()` garantiza que la
    escritura sea todo-o-nada, pero NO que lo leído siga siendo cierto al
    escribir: la liberación quedaría firmada contra un checklist que ya cambió.

    Solo se usa dentro de una transacción; fuera, Django lo rechaza. Y en un
    motor que no sepa bloquear filas no hace nada en absoluto, en silencio: de
    eso avisa el check `calidad.E001`.
    """
    registros = RegistroCalidad.objects.filter(lote=lote)
    analisis = Analisis.objects.filter(lote=lote)

    # Inocuidad: el PCC 1 de uperización y los monitoreos PPRO. Entran al
    # contexto porque ahora deciden, y se bloquean por la misma razón que los
    # formularios: entre la comprobación y la firma nadie puede corregir una
    # lectura fuera de límite ni borrar la acción correctiva que resolvía un
    # No-OK.
    controles = ControlProceso.objects.filter(lote=lote)
    lecturas_control = ControlProcesoLectura.objects.filter(control__lote=lote)
    monitoreos = MonitoreoPPRO.objects.filter(lote=lote)

    if bloquear:
        # Sin `select_related` a propósito: con el JOIN, el FOR UPDATE
        # bloquearía también las filas del catálogo de documentos, que es un
        # maestro compartido por todos los lotes. El dominio no necesita el
        # documento del registro —usa `documento_id`— así que no hace falta.
        registros = registros.select_for_update()
        analisis = analisis.select_for_update()
        controles = controles.select_for_update()
        # `lecturas_control` filtra por `control__lote`, así que su FOR UPDATE
        # arrastraría también la tabla de controles por el JOIN. Se acota a las
        # filas de lectura con `of`, que es lo que se quiere proteger.
        lecturas_control = lecturas_control.select_for_update(of=("self",))
        monitoreos = monitoreos.select_for_update()
    else:
        registros = registros.select_related("documento")

    # `resuelto` recorre las lecturas del monitoreo: sin esto sería una
    # consulta por monitoreo dentro del dominio.
    monitoreos = monitoreos.prefetch_related("lecturas")

    documentos = list(DocumentoLiberacion.objects.all())

    # Los documentos que el propio dato del sistema da por cumplidos: el PCC 1
    # lo cumple su control de proceso, no una casilla. Se calcula aquí y se
    # pasa al dominio, que sigue sin consultar la base.
    movimientos = MovimientoSilo.objects.filter(
        tipo=MovimientoSilo.Tipo.SALIDA,
        origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        origen_id=lote.id,
    )

    lista_controles = list(controles)
    lista_monitoreos = list(monitoreos)
    lista_analisis = list(analisis)

    cumplidos_por_dato = dominio.documentos_con_evidencia(
        documentos,
        lote.id,
        controles=lista_controles,
        monitoreos=lista_monitoreos,
        analisis=lista_analisis,
        movimientos=list(movimientos),
    )

    return {
        "lote": lote,
        "producto": lote.producto,
        "documentos": documentos,
        "cumplidos_por_dato": cumplidos_por_dato,
        "registros": list(registros),
        "analisis": lista_analisis,
        "especificaciones": list(Especificacion.objects.filter(producto=lote.producto)),
        "controles": lista_controles,
        "lecturas_control": list(lecturas_control),
        "monitoreos": lista_monitoreos,
    }


@api_view(["GET"])
@permission_classes([EscribeCalidad])
def expedientes(request):
    """
    Listado de lotes con su estado de liberación.

    Es la pantalla de Calidad: qué hay pendiente y qué falta en cada caso.
    Excluye los lotes en proceso y los anulados, que no son liberables todavía
    o ya nunca lo serán.

    Acepta `estado` (el de la liberación), `producto`, `desde` y `hasta`.
    """
    lotes = (
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis", "registros_calidad", "liberacion")
        .exclude(estado__in=[Lote.Estado.EN_PROCESO, Lote.Estado.ANULADO])
    )

    parametros = request.query_params

    producto = parametros.get("producto")
    if producto:
        lotes = lotes.filter(producto_id=producto)

    desde = parametros.get("desde")
    if desde:
        lotes = lotes.filter(fecha__gte=desde)

    hasta = parametros.get("hasta")
    if hasta:
        lotes = lotes.filter(fecha__lte=hasta)

    # Los maestros se cargan una vez y los comparten todos los lotes: sin esto
    # cada lote dispararía sus propias consultas.
    documentos = list(DocumentoLiberacion.objects.all())
    especificaciones = list(Especificacion.objects.all())

    # Lo que la inocuidad y la evidencia necesitan, para TODOS los lotes de la
    # página en una consulta por tabla.
    #
    # El listado tiene que contar igual que el detalle. Si aquí no entrara la
    # evidencia, la lista diría «faltan 18 de 19» y la ficha del mismo lote
    # diría otra cosa — dos números para el mismo hecho, y el usuario sin saber
    # cuál creer.
    ids = [lote.id for lote in lotes]

    controles = list(ControlProceso.objects.filter(lote_id__in=ids))
    lecturas_control = list(
        ControlProcesoLectura.objects.filter(control__lote_id__in=ids)
    )
    monitoreos = list(
        MonitoreoPPRO.objects.filter(lote_id__in=ids).prefetch_related("lecturas")
    )
    movimientos = list(
        MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id__in=ids,
        )
    )

    def _del_lote(registros, lote_id, campo="lote_id"):
        return [r for r in registros if getattr(r, campo, None) == lote_id]

    filas = []
    for lote in lotes:
        registros = list(lote.registros_calidad.all())
        analisis = list(lote.analisis.all())
        exigibles = dominio.documentos_aplicables(documentos, lote.producto)

        suyos_control = _del_lote(controles, lote.id)
        suyos_monitoreo = _del_lote(monitoreos, lote.id)
        suyos_movimiento = _del_lote(movimientos, lote.id, "origen_id")

        cumplidos_por_dato = dominio.documentos_con_evidencia(
            documentos,
            lote.id,
            controles=suyos_control,
            monitoreos=suyos_monitoreo,
            analisis=analisis,
            movimientos=suyos_movimiento,
        )

        avance = dominio.avance_checklist(
            registros, exigibles, lote.id, cumplidos_por_dato
        )

        decision = dominio.puede_liberar(
            lote=lote,
            producto=lote.producto,
            documentos=documentos,
            registros=registros,
            analisis=analisis,
            especificaciones=especificaciones,
            controles=suyos_control,
            lecturas_control=lecturas_control,
            monitoreos=suyos_monitoreo,
            cumplidos_por_dato=cumplidos_por_dato,
        )

        liberacion = getattr(lote, "liberacion", None)

        filas.append(
            {
                "lote": {
                    "id": lote.id,
                    "codigo_lote": lote.codigo_lote,
                    "fecha": lote.fecha,
                    "producto_nombre": lote.producto.nombre,
                    "mandante_nombre": lote.producto.mandante.nombre,
                    "familia": lote.producto.familia,
                    "kg_producidos": lote.kg_producidos,
                    "estado": lote.estado,
                },
                "liberacion": (
                    LiberacionSerializer(liberacion).data if liberacion else None
                ),
                "avance": {
                    "completados": avance.completados,
                    "total": avance.total,
                    "pct": avance.pct,
                    "completo": avance.completo,
                },
                "calidad": serializar_calidad(decision.calidad),
                "permitido": decision.permitido,
                "via_concesion": decision.via_concesion,
                "bloqueos": decision.bloqueos,
            }
        )

    estado = parametros.get("estado")
    if estado:
        filas = [
            f
            for f in filas
            if (f["liberacion"]["estado"] if f["liberacion"] else "pendiente") == estado
        ]

    return Response({"resultados": filas, "total": len(filas)})


@api_view(["GET"])
@permission_classes([EscribeCalidad])
def expediente(request, lote_id):
    """
    El expediente completo de un lote: qué documentos exige, cómo va cada uno,
    qué dice el laboratorio y si se puede liberar.

    Es lo que la pantalla necesita para dibujar los formularios y explicar por
    qué el botón está apagado. El rol de quien pregunta entra en la decisión:
    la respuesta no es la misma para Calidad que para Producción.
    """
    lote = get_object_or_404(
        Lote.objects.select_related("producto", "producto__mandante"), pk=lote_id
    )
    contexto = _contexto_del_lote(lote)

    decision = dominio.puede_liberar(**contexto, rol=rol_de(request.user))
    liberacion = Liberacion.objects.filter(lote=lote).first()

    # El cotejo de cada formulario contra el laboratorio: es lo que en papel no
    # se cruza nunca (MODELO_DATOS.md §2.6).
    discrepancias = {}
    for registro in contexto["registros"]:
        encontradas = dominio.cotejar_con_analisis(
            registro, registro.documento, decision.calidad, contexto["analisis"]
        )
        if encontradas:
            discrepancias[registro.documento_id] = serializar_discrepancias(encontradas)

    return Response(
        {
            "lote": {
                "id": lote.id,
                "codigo_lote": lote.codigo_lote,
                "fecha": lote.fecha,
                "producto_nombre": lote.producto.nombre,
                "mandante_nombre": lote.producto.mandante.nombre,
                "familia": lote.producto.familia,
                "kg_producidos": lote.kg_producidos,
                "estado": lote.estado,
            },
            "liberacion": LiberacionSerializer(liberacion).data if liberacion else None,
            "decision": serializar_decision(decision),
            "discrepancias": discrepancias,
            # Lo que el sistema ya sabe, para no volver a teclearlo.
            "prellenado": {
                d.documento.id: dominio.prellenar(d.documento, {"lote": lote})
                for d in (decision.avance.detalle if decision.avance else [])
            },
        }
    )


def _firmar(request, lote_id, concesion, motivo="", observacion=""):
    """
    Estampa la firma después de comprobar la regla.

    La comprobación y el guardado van en una transacción **y con bloqueo de
    fila** sobre lo que se leyó. Las dos cosas hacen falta y no son la misma:
    la transacción hace que la escritura sea todo-o-nada; el bloqueo hace que
    lo leído siga siendo cierto al escribir. Sin lo segundo, otro usuario puede
    desmarcar un documento entre la comprobación y el guardado, y la
    liberación queda firmada contra un checklist que ya no está completo.
    """
    lote = get_object_or_404(Lote.objects.select_related("producto"), pk=lote_id)
    rol = rol_de(request.user)

    with transaction.atomic():
        contexto = _contexto_del_lote(lote, bloquear=True)

        if concesion:
            validacion = dominio.validar_concesion(
                motivo, autorizador_identificado=True, **contexto, rol=rol
            )
            permitido, bloqueos = validacion.permitido, validacion.bloqueos
        else:
            decision = dominio.puede_liberar(**contexto, rol=rol)
            permitido, bloqueos = decision.permitido, decision.bloqueos

        if not permitido:
            return Response(
                {"detail": "No se puede liberar este lote.", "bloqueos": bloqueos},
                status=status.HTTP_409_CONFLICT,
            )

        liberacion, _ = Liberacion.objects.get_or_create(lote=lote)

        destino = (
            Liberacion.Estado.CONCESION if concesion else Liberacion.Estado.LIBERADO
        )

        # Un expediente que nadie ha abierto está en `pendiente`, y desde ahí
        # no se firma: se pasa antes por revisión, que es lo que significa que
        # alguien lo está mirando. Firmar directamente saltaría la máquina de
        # estados que el modelo declara.
        if liberacion.estado == Liberacion.Estado.PENDIENTE:
            liberacion.estado = Liberacion.Estado.EN_REVISION

        if not liberacion.puede_pasar_a(destino):
            return Response(
                {
                    "detail": (
                        f"Un expediente {liberacion.get_estado_display().lower()} "
                        f"no puede pasar a {destino.label.lower()}."
                    ),
                    "bloqueos": [],
                },
                status=status.HTTP_409_CONFLICT,
            )

        liberacion.estado = destino
        liberacion.concesion = concesion
        liberacion.motivo_concesion = motivo
        liberacion.observacion = observacion
        liberacion.autorizada_por = request.user
        liberacion.autorizada_en = ahora()
        liberacion.save()

    return Response(LiberacionSerializer(liberacion).data)


@api_view(["POST"])
@permission_classes([EscribeCalidad])
def liberar(request, lote_id):
    """Liberación normal: exige checklist completo y calidad conforme."""
    datos = FirmaSerializer(data=request.data)
    datos.is_valid(raise_exception=True)

    return _firmar(
        request, lote_id, concesion=False, observacion=datos.validated_data["observacion"]
    )


@api_view(["POST"])
@permission_classes([EscribeCalidad])
def revisar(request, lote_id):
    """
    Devuelve el expediente a revisión.

    Es la transición legítima que faltaba y que antes se hacía escribiendo
    `estado` a mano. Sirve para dos cosas: abrir un expediente pendiente, y
    retirar una liberación ya firmada cuando algo deja de sostenerla —al
    desmarcar un documento, por ejemplo, el checklist ya no está completo y la
    autorización tampoco.

    La firma anterior se borra: dejarla puesta sobre un expediente que volvió
    a revisión diría que alguien autorizó algo que ya no está autorizado.
    """
    lote = get_object_or_404(Lote, pk=lote_id)

    with transaction.atomic():
        liberacion, _ = Liberacion.objects.get_or_create(lote=lote)

        if liberacion.estado == Liberacion.Estado.EN_REVISION:
            return Response(LiberacionSerializer(liberacion).data)

        if not liberacion.puede_pasar_a(Liberacion.Estado.EN_REVISION):
            return Response(
                {
                    "detail": (
                        f"Un expediente {liberacion.get_estado_display().lower()} "
                        "no puede volver a revisión."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        liberacion.estado = Liberacion.Estado.EN_REVISION
        liberacion.concesion = False
        liberacion.motivo_concesion = ""
        liberacion.autorizada_por = None
        liberacion.autorizada_en = None
        liberacion.save()

    return Response(LiberacionSerializer(liberacion).data)


@api_view(["POST"])
@permission_classes([EscribeCalidad])
def conceder(request, lote_id):
    """
    Liberación bajo concesión: producto no conforme que igual sale.

    Exige motivo escrito y deja marca permanente. No salta las demás
    condiciones: un checklist incompleto sigue bloqueando, y un lote sin
    análisis también, porque no se concede una excepción sobre algo que nunca
    se midió.
    """
    datos = ConcesionSerializer(data=request.data)
    datos.is_valid(raise_exception=True)

    return _firmar(
        request,
        lote_id,
        concesion=True,
        motivo=datos.validated_data["motivo"],
        observacion=datos.validated_data["observacion"],
    )
