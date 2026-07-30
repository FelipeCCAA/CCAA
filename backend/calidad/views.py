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

from maestros.models import DocumentoLiberacion, Especificacion
from produccion.models import Analisis, Lote
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

    if bloquear:
        # Sin `select_related` a propósito: con el JOIN, el FOR UPDATE
        # bloquearía también las filas del catálogo de documentos, que es un
        # maestro compartido por todos los lotes. El dominio no necesita el
        # documento del registro —usa `documento_id`— así que no hace falta.
        registros = registros.select_for_update()
        analisis = analisis.select_for_update()
    else:
        registros = registros.select_related("documento")

    return {
        "lote": lote,
        "producto": lote.producto,
        "documentos": list(DocumentoLiberacion.objects.all()),
        "registros": list(registros),
        "analisis": list(analisis),
        "especificaciones": list(Especificacion.objects.filter(producto=lote.producto)),
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

    filas = []
    for lote in lotes:
        registros = list(lote.registros_calidad.all())
        exigibles = dominio.documentos_aplicables(documentos, lote.producto)
        avance = dominio.avance_checklist(registros, exigibles, lote.id)

        decision = dominio.puede_liberar(
            lote=lote,
            producto=lote.producto,
            documentos=documentos,
            registros=registros,
            analisis=list(lote.analisis.all()),
            especificaciones=especificaciones,
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
        liberacion.estado = (
            Liberacion.Estado.CONCESION if concesion else Liberacion.Estado.LIBERADO
        )
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
