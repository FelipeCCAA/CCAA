"""
API del planificador.

Dos clases de endpoint, como en Liberación:

- Los ViewSets guardan hechos: un código, una semana, un bloque, un balance.
- `programa` y `contraste` no guardan nada: calculan. El consumo, el stock y
  las desviaciones se derivan en cada llamada, así que no hay nada que
  sincronizar ni que pueda quedar desactualizado.

Publicar es lo único que cambia el estado del mundo, y por eso es lo único
que va en una transacción y comprueba la regla antes.
"""

import json
from datetime import timedelta

from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from produccion.models import Lote
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.permisos import EscribeProduccion
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, SucursalTenantViewSetMixin,
    filtrar_por_scope,
)

from . import contraste as contraste_dominio
from . import dominio
from .models import (
    BalanceDia, BloquePlan, CapacidadProceso, CodigoProduccion, MovimientoPlan,
    SemanaPlan, StockSeguridadPlan, TipoActividadPlan, VersionSemanaPlan,
)
from .serializers import (
    BalanceDiaSerializer,
    BloquePlanSerializer,
    CapacidadProcesoSerializer,
    CodigoProduccionSerializer,
    MovimientoPlanSerializer,
    SemanaPlanSerializer,
    StockSeguridadPlanSerializer,
    TipoActividadPlanSerializer,
    VersionSemanaPlanSerializer,
    serializar_balance,
    serializar_contraste,
    serializar_desviacion,
)


class CodigoProduccionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "producto__mandante__empresa_id"
    tenant_relation_fields = {
        "producto": (None, "mandante__empresa_id"),
        "mandante": (None, "empresa_id"),
    }
    queryset = CodigoProduccion.objects.select_related("producto", "mandante")
    serializer_class = CodigoProduccionSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        activo = self.request.query_params.get("activo")
        if activo is not None:
            consulta = consulta.filter(activo=activo.lower() not in ("false", "0"))

        return consulta


class SemanaPlanViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = SemanaPlan.objects.select_related("publicada_por")
    serializer_class = SemanaPlanSerializer
    permission_classes = [EscribeProduccion]

    def destroy(self, request, *args, **kwargs):
        semana = self.get_object()
        if semana.estado != SemanaPlan.Estado.BORRADOR:
            return Response(
                {"detail": "Una semana publicada, cerrada o cancelada conserva su historial."},
                status=status.HTTP_405_METHOD_NOT_ALLOWED,
            )
        if semana.bloques.exists() or semana.balances.exists():
            return Response(
                {"detail": "La semana ya tiene planificación. Cancélala en lugar de borrarla."},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        motivo = str(request.data.get("motivo", "")).strip()
        if not motivo:
            return Response(
                {"motivo": "Indica el motivo de la cancelación."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            semana = SemanaPlan.objects.select_for_update().get(pk=self.get_object().pk)
            if not semana.puede_pasar_a(SemanaPlan.Estado.CANCELADA):
                return Response(
                    {"detail": f"Una semana {semana.get_estado_display().lower()} no se puede cancelar."},
                    status=status.HTTP_409_CONFLICT,
                )
            semana.estado = SemanaPlan.Estado.CANCELADA
            semana.cancelada_por = request.user
            semana.cancelada_en = timezone.now()
            semana.motivo_cancelacion = motivo
            semana.save(update_fields=[
                "estado", "cancelada_por", "cancelada_en", "motivo_cancelacion"
            ])
        return Response(self.get_serializer(semana).data)

    @action(detail=True, methods=["post"])
    def duplicar(self, request, pk=None):
        origen = self.get_object()
        codigo = str(request.data.get("codigo", "")).strip()
        fecha_inicio = request.data.get("fecha_inicio")
        anio = request.data.get("anio")
        if not codigo or not fecha_inicio or not anio:
            return Response(
                {"detail": "Indica código, año y fecha de inicio para la copia."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(data={
            "sucursal": origen.sucursal_id,
            "codigo": codigo,
            "anio": anio,
            "fecha_inicio": fecha_inicio,
            "observacion": f"Copia de {origen.codigo}/{origen.anio}",
        })
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            copia = serializer.save()
            BalanceDia.objects.bulk_create([
                BalanceDia(
                    semana=copia, dia=item.dia, stock_inicial=item.stock_inicial,
                    recepcion_ccaa=item.recepcion_ccaa,
                    recepcion_nestle=item.recepcion_nestle,
                    recepcion_punion=item.recepcion_punion,
                    trasvasije=item.trasvasije,
                    crema_disponible_ton=item.crema_disponible_ton,
                    ajustes=item.ajustes, observacion=item.observacion,
                ) for item in origen.balances.all()
            ])
            BloquePlan.objects.bulk_create([
                BloquePlan(
                    semana=copia, equipo=item.equipo, dia=item.dia,
                    hora_inicio=item.hora_inicio, hora_fin=item.hora_fin,
                    tipo=item.tipo, codigo=item.codigo,
                    estado_equipo=item.estado_equipo, cantidad_kg=item.cantidad_kg,
                    observacion=item.observacion, tipo_actividad=item.tipo_actividad,
                    fecha_hora_inicio=(item.fecha_hora_inicio + timedelta(days=(copia.fecha_inicio - origen.fecha_inicio).days)) if item.fecha_hora_inicio else None,
                    fecha_hora_fin=(item.fecha_hora_fin + timedelta(days=(copia.fecha_inicio - origen.fecha_inicio).days)) if item.fecha_hora_fin else None,
                    producto=item.producto, orden_produccion=None,
                    origen_leche=item.origen_leche, cliente=item.cliente,
                    capacidad_hora=item.capacidad_hora, color=item.color,
                    creado_por=request.user,
                ) for item in origen.bloques.all()
            ])
            MovimientoPlan.objects.bulk_create([
                MovimientoPlan(
                    semana=copia,
                    fecha_hora=item.fecha_hora + timedelta(days=(copia.fecha_inicio - origen.fecha_inicio).days),
                    propietario=item.propietario, tipo=item.tipo, cantidad=item.cantidad,
                    documento=item.documento, observacion=item.observacion,
                    creado_por=request.user,
                ) for item in origen.movimientos_plan.all()
            ])
        return Response(self.get_serializer(copia).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="comparar-versiones")
    def comparar_versiones(self, request, pk=None):
        semana = self.get_object()
        try:
            desde = semana.versiones.get(numero=int(request.query_params.get("desde", 0)))
            hasta = semana.versiones.get(numero=int(request.query_params.get("hasta", 0)))
        except (ValueError, VersionSemanaPlan.DoesNotExist):
            return Response({"detail": "Indica dos versiones existentes."}, status=400)

        def indexar(version, clave):
            return {str(item["id"]): item for item in version.instantanea.get(clave, [])}

        resultado = {}
        for clave in ("actividades", "movimientos"):
            anterior, nuevo = indexar(desde, clave), indexar(hasta, clave)
            resultado[clave] = {
                "agregados": [nuevo[id_] for id_ in nuevo.keys() - anterior.keys()],
                "eliminados": [anterior[id_] for id_ in anterior.keys() - nuevo.keys()],
                "modificados": [
                    {"id": id_, "anterior": anterior[id_], "nuevo": nuevo[id_]}
                    for id_ in anterior.keys() & nuevo.keys() if anterior[id_] != nuevo[id_]
                ],
            }
        return Response({"desde": desde.numero, "hasta": hasta.numero, **resultado})

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        anio = parametros.get("anio")
        if anio:
            consulta = consulta.filter(anio=anio)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        return consulta


class BloquePlanViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "semana__sucursal_id"
    tenant_lookup_empresa = "semana__sucursal__empresa_id"
    tenant_relation_fields = {
        "semana": ("sucursal_id", "sucursal__empresa_id"),
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
        "codigo": (None, "producto__mandante__empresa_id"),
        "producto": (None, "mandante__empresa_id"),
        "orden_produccion": ("sucursal_id", "sucursal__empresa_id"),
        "origen_leche": (None, "empresa_id"),
        "cliente": (None, "empresa_id"),
    }
    # `equipo` va en el select_related porque el balance consulta
    # `bloque.equipo.consume_leche` por cada bloque: sin esto, una consulta
    # por fila.
    queryset = BloquePlan.objects.select_related(
        "semana", "codigo", "codigo__producto", "codigo__mandante", "equipo",
        "tipo_actividad", "producto", "orden_produccion", "origen_leche", "cliente",
    )
    serializer_class = BloquePlanSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        semana = parametros.get("semana")
        if semana:
            consulta = consulta.filter(semana_id=semana)

        equipo = parametros.get("equipo")
        if equipo:
            # Por código y no por id: la pantalla habla de "scheffers2".
            consulta = consulta.filter(equipo__codigo=equipo)

        return consulta


class TipoActividadPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TipoActividadPlan.objects.filter(activo=True)
    serializer_class = TipoActividadPlanSerializer
    permission_classes = [EscribeProduccion]
    pagination_class = None


class CapacidadProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "equipo__sucursal_id"
    tenant_lookup_empresa = "equipo__sucursal__empresa_id"
    tenant_relation_fields = {"equipo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = CapacidadProceso.objects.select_related("equipo")
    serializer_class = CapacidadProcesoSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        equipo = self.request.query_params.get("equipo")
        return consulta.filter(equipo_id=equipo) if equipo else consulta


class MovimientoPlanViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "semana__sucursal_id"
    tenant_lookup_empresa = "semana__sucursal__empresa_id"
    tenant_relation_fields = {
        "semana": ("sucursal_id", "sucursal__empresa_id"),
        "propietario": (None, "empresa_id"),
    }
    queryset = MovimientoPlan.objects.select_related("semana", "propietario", "actividad")
    serializer_class = MovimientoPlanSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        semana = self.request.query_params.get("semana")
        return consulta.filter(semana_id=semana) if semana else consulta


class StockSeguridadPlanViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "propietario__empresa_id"
    tenant_relation_fields = {"propietario": (None, "empresa_id")}
    queryset = StockSeguridadPlan.objects.select_related("propietario")
    serializer_class = StockSeguridadPlanSerializer
    permission_classes = [EscribeProduccion]


class VersionSemanaPlanViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "semana__sucursal_id"
    tenant_lookup_empresa = "semana__sucursal__empresa_id"
    queryset = VersionSemanaPlan.objects.select_related("semana", "publicada_por")
    serializer_class = VersionSemanaPlanSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        semana = self.request.query_params.get("semana")
        return consulta.filter(semana_id=semana) if semana else consulta


class BalanceDiaViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "semana__sucursal_id"
    tenant_lookup_empresa = "semana__sucursal__empresa_id"
    tenant_relation_fields = {
        "semana": ("sucursal_id", "sucursal__empresa_id")
    }
    queryset = BalanceDia.objects.all()
    serializer_class = BalanceDiaSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        semana = self.request.query_params.get("semana")
        if semana:
            consulta = consulta.filter(semana_id=semana)

        return consulta


# ----------------------------------------------------------------- derivados

def _contexto(semana):
    """Lo que el dominio necesita, cargado de una vez."""
    return (
        list(
            BloquePlan.objects.filter(semana=semana).select_related(
                "codigo", "equipo"
            )
        ),
        list(CodigoProduccion.objects.filter(
            producto__mandante__empresa_id=semana.sucursal.empresa_id
        )),
        list(BalanceDia.objects.filter(semana=semana)),
    )


def _movimientos_y_seguridad(semana):
    movimientos = list(
        MovimientoPlan.objects.filter(semana=semana).select_related("propietario")
    )
    seguridad = {}
    for item in StockSeguridadPlan.objects.filter(
        propietario__empresa_id=semana.sucursal.empresa_id,
        vigente_desde__lte=semana.fecha_inicio,
    ).order_by("propietario_id", "-vigente_desde"):
        seguridad.setdefault(item.propietario_id, float(item.cantidad))
    return movimientos, seguridad


def _indicadores(semana, bloques):
    movimientos, seguridad = _movimientos_y_seguridad(semana)
    return dominio.balance_por_movimientos(semana, bloques, movimientos, seguridad), movimientos


def _crear_version(semana, usuario, bloques, codigos, balances):
    indicadores, movimientos = _indicadores(semana, bloques)
    payload = {
        "semana": SemanaPlanSerializer(semana).data,
        "actividades": BloquePlanSerializer(bloques, many=True).data,
        "movimientos": MovimientoPlanSerializer(movimientos, many=True).data,
        "balance_legacy": [serializar_balance(f) for f in dominio.balance_semana(bloques, codigos, balances)],
        "indicadores": indicadores,
    }
    instantanea = json.loads(JSONRenderer().render(payload))
    numero = (semana.versiones.aggregate(maximo=Max("numero"))["maximo"] or 0) + 1
    return VersionSemanaPlan.objects.create(
        semana=semana, numero=numero, instantanea=instantanea, publicada_por=usuario
    )


def _semanas_permitidas(request):
    return filtrar_por_scope(
        SemanaPlan.objects.all(), request.user,
        campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    )


@api_view(["GET"])
@permission_classes([EscribeProduccion])
def programa(request, semana_id):
    """
    El programa completo de una semana: bloques, balance derivado y estado.

    Es lo que la pantalla dibuja. El balance viene calculado —consumo, stock
    arrastrado, saldos por origen— porque nada de eso se guarda: mover un
    bloque de evaporador cambia el stock del resto de la semana, y un número
    persistido dejaría de ser cierto sin avisar.
    """
    semana = get_object_or_404(_semanas_permitidas(request), pk=semana_id)
    bloques, codigos, balances = _contexto(semana)

    filas = dominio.balance_semana(bloques, codigos, balances)
    validacion = dominio.puede_publicar(semana, bloques, codigos, balances)
    indicadores, movimientos = _indicadores(semana, bloques)

    return Response(
        {
            "semana": SemanaPlanSerializer(semana).data,
            "bloques": BloquePlanSerializer(bloques, many=True).data,
            "balance": [serializar_balance(f) for f in filas],
            "fechas": [semana.fecha_del_dia(d) for d in range(7)],
            "publicable": validacion.permitido,
            "bloqueos": validacion.bloqueos,
            "movimientos": MovimientoPlanSerializer(movimientos, many=True).data,
            "indicadores": indicadores,
            "alertas": indicadores["alertas"],
            "versiones": VersionSemanaPlanSerializer(
                semana.versiones.select_related("publicada_por"), many=True
            ).data,
        }
    )


@api_view(["POST"])
@permission_classes([EscribeProduccion])
def publicar(request, semana_id):
    """
    Publica la semana: la compromete con planta.

    Se exige que el plan cuadre —cada día hábil con su balance y sin saldos
    negativos por origen—, porque publicar un programa con más leche
    programada de la que va a llegar es mandar a planta algo que no se puede
    cumplir.
    """
    semana = get_object_or_404(_semanas_permitidas(request), pk=semana_id)

    with transaction.atomic():
        bloques, codigos, balances = _contexto(semana)
        validacion = dominio.puede_publicar(semana, bloques, codigos, balances)

        if not validacion.permitido:
            return Response(
                {
                    "detail": "No se puede publicar esta semana.",
                    "bloqueos": validacion.bloqueos,
                },
                status=status.HTTP_409_CONFLICT,
            )

        semana.estado = SemanaPlan.Estado.PUBLICADA
        semana.publicada_por = request.user
        semana.publicada_en = timezone.now()
        semana.save()
        _crear_version(semana, request.user, bloques, codigos, balances)

    return Response(SemanaPlanSerializer(semana).data)


@api_view(["POST"])
@permission_classes([EscribeProduccion])
def reabrir(request, semana_id):
    """
    Devuelve una semana publicada a borrador.

    Existe porque el programa cambia: se rompe una máquina y hay que
    reprogramar la semana en curso. Se retira la firma de publicación, porque
    dejarla diría que alguien comprometió un programa que ya no es ese.
    """
    semana = get_object_or_404(_semanas_permitidas(request), pk=semana_id)

    if not semana.puede_pasar_a(SemanaPlan.Estado.BORRADOR):
        return Response(
            {
                "detail": (
                    f"Una semana {semana.get_estado_display().lower()} no vuelve "
                    "a borrador."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    semana.estado = SemanaPlan.Estado.BORRADOR
    semana.publicada_por = None
    semana.publicada_en = None
    semana.save()

    return Response(SemanaPlanSerializer(semana).data)


@api_view(["POST"])
@permission_classes([EscribeProduccion])
def cerrar(request, semana_id):
    """Cierra la semana: pasa a histórico y ya solo se contrasta."""
    semana = get_object_or_404(_semanas_permitidas(request), pk=semana_id)

    if not semana.puede_pasar_a(SemanaPlan.Estado.CERRADA):
        return Response(
            {
                "detail": (
                    f"Una semana {semana.get_estado_display().lower()} no se "
                    "puede cerrar. Antes hay que publicarla."
                )
            },
            status=status.HTTP_409_CONFLICT,
        )

    semana.estado = SemanaPlan.Estado.CERRADA
    semana.save()

    return Response(SemanaPlanSerializer(semana).data)


@api_view(["GET"])
@permission_classes([EscribeProduccion])
def contraste(request, semana_id):
    """
    Lo planificado frente a lo que realmente pasó, día a día.

    Los dos lados se miden con datos distintos y esa es toda la idea: el plan
    sale del programa y del balance; lo real, del libro mayor de silos y de
    los lotes. Si el lado real se copiara del plan, siempre cuadraría.
    """
    semana = get_object_or_404(_semanas_permitidas(request), pk=semana_id)
    bloques, codigos, balances = _contexto(semana)

    desde = semana.fecha_inicio
    hasta = semana.fecha_del_dia(6)

    filas = contraste_dominio.contrastar_semana(
        semana,
        bloques,
        codigos,
        balances,
        # Solo lo descargado: una recepción registrada todavía no entró al silo.
        Recepcion.objects.filter(
            vehiculo__sucursal_id=semana.sucursal_id,
            fecha__gte=desde, fecha__lte=hasta, estado=Recepcion.Estado.DESCARGADA
        ),
        MovimientoSilo.objects.filter(
            silo__sucursal_id=semana.sucursal_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        ),
        Lote.objects.filter(sucursal_id=semana.sucursal_id, fecha__gte=desde, fecha__lte=hasta).exclude(
            estado=Lote.Estado.ANULADO
        ),
    )

    resumen = contraste_dominio.resumir(filas)

    return Response(
        {
            "semana": SemanaPlanSerializer(semana).data,
            "dias": [serializar_contraste(f) for f in filas],
            "resumen": {
                "leche_recibida": serializar_desviacion(resumen.leche_recibida),
                "leche_consumida": serializar_desviacion(resumen.leche_consumida),
                "kilos": serializar_desviacion(resumen.kilos),
                "dias_con_actividad": resumen.dias_con_actividad,
            },
        }
    )
