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

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from produccion.models import Lote
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.permisos import EscribeProduccion
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, SucursalTenantViewSetMixin,
    filtrar_por_scope,
)

from . import contraste as contraste_dominio
from . import dominio
from .models import BalanceDia, BloquePlan, CodigoProduccion, SemanaPlan
from .serializers import (
    BalanceDiaSerializer,
    BloquePlanSerializer,
    CodigoProduccionSerializer,
    SemanaPlanSerializer,
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
    }
    # `equipo` va en el select_related porque el balance consulta
    # `bloque.equipo.consume_leche` por cada bloque: sin esto, una consulta
    # por fila.
    queryset = BloquePlan.objects.select_related("codigo", "equipo")
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

    return Response(
        {
            "semana": SemanaPlanSerializer(semana).data,
            "bloques": BloquePlanSerializer(bloques, many=True).data,
            "balance": [serializar_balance(f) for f in filas],
            "fechas": [semana.fecha_del_dia(d) for d in range(7)],
            "publicable": validacion.permitido,
            "bloqueos": validacion.bloqueos,
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
