from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeProduccion
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope, scope_de,
    sucursal_para_escritura,
)
from .models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, SalidaProceso
from .serializers import (
    EjecucionProcesoSerializer, EntradaProcesoSerializer, EtapaProcesoSerializer,
    ProcesoSerializer, SalidaProcesoSerializer,
)
from .servicios import genealogia_lote, transicionar_ejecucion


class ProcesoViewSet(viewsets.ModelViewSet):
    queryset = Proceso.objects.prefetch_related("etapas")
    serializer_class = ProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]


class EtapaProcesoViewSet(viewsets.ModelViewSet):
    queryset = EtapaProceso.objects.select_related("proceso")
    serializer_class = EtapaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]


class EjecucionProcesoViewSet(RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_relation_fields = {
        "sucursal": ("pk", "empresa_id"),
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
    }
    serializer_class = EjecucionProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = EjecucionProceso.objects.select_related(
            "etapa__proceso", "equipo", "responsable", "sucursal"
        ).prefetch_related(
            "entradas__lote__producto", "salidas__lote__producto", "eventos__usuario"
        )
        estado = self.request.query_params.get("estado")
        etapa = self.request.query_params.get("etapa")
        if estado:
            queryset = queryset.filter(estado=estado)
        if etapa:
            queryset = queryset.filter(etapa_id=etapa)
        return filtrar_por_scope(
            queryset, self.request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    def perform_create(self, serializer):
        serializer.save(
            responsable=self.request.user,
            sucursal=sucursal_para_escritura(
                self.request.user, serializer.validated_data
            ),
        )

    def perform_update(self, serializer):
        if not serializer.instance.editable:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Una ejecución cerrada o cancelada es inmutable.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def transicionar(self, request, pk=None):
        try:
            ejecucion = transicionar_ejecucion(
                ejecucion_id=self.get_object().pk,
                estado_nuevo=request.data.get("estado", ""),
                motivo=request.data.get("motivo", ""),
                usuario=request.user,
            )
        except DjangoValidationError as error:
            # `.messages[0]` y no `.message`: el segundo solo existe cuando el
            # error se levantó con un string suelto. Con un dict o una lista
            # —como los que levanta `SalidaProceso.clean()` en este mismo
            # módulo— no existe, y el 400 se convertiría en un 500.
            return Response(
                {"error": error.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(self.get_serializer(ejecucion).data)


class EntradaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = EntradaProceso.objects.select_related("ejecucion", "lote__producto")
    serializer_class = EntradaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]


class SalidaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = SalidaProceso.objects.select_related("ejecucion", "lote__producto")
    serializer_class = SalidaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]


@api_view(["GET"])
def trazabilidad(request, lote):
    """
    Genealogía de un lote, hacia atrás o hacia adelante.

    Acepta el **código de lote** además del id. El id es de la base de datos y
    nadie en planta lo conoce: quien pregunta de dónde salió un saco tiene en
    la mano un `CCAA6212010102010201-01`, no un 47. Pedirle el id volvía la
    pantalla inservible para quien la necesita.
    """
    from produccion.models import Lote

    direccion = request.query_params.get("direccion", "atras")

    lotes = filtrar_por_scope(
        Lote.objects.all(), request.user,
        campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    )
    if str(lote).isdigit():
        encontrado = lotes.filter(pk=int(lote)).first()
    else:
        encontrado = lotes.filter(codigo_lote=lote).first()

    if encontrado is None:
        return Response(
            {"error": f"No existe un lote «{lote}»."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        scope = scope_de(request.user, requerido=True)
        datos = genealogia_lote(
            encontrado.pk, direccion,
            sucursal_id=scope.sucursal_id if scope.es_sucursal else None,
            empresa_id=scope.empresa_id if scope.es_empresa else None,
        )
    except ValueError as error:
        return Response({"error": str(error)}, status=400)

    return Response({**datos, "raiz": encontrado.pk})
