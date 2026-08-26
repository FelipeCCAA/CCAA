from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeMantenimiento
from usuarios.tenancy import QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope
from .models import FallaEquipo, OrdenTrabajo, PlanPreventivo, RepuestoUtilizado
from .serializers import (
    FallaEquipoSerializer, OrdenTrabajoSerializer, PlanPreventivoSerializer,
    RepuestoUtilizadoSerializer,
)
from .servicios import transicionar_orden


class PlanPreventivoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "equipo__sucursal_id"
    tenant_lookup_empresa = "equipo__sucursal__empresa_id"
    tenant_relation_fields = {"equipo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = PlanPreventivo.objects.select_related("equipo")
    serializer_class = PlanPreventivoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]


class OrdenTrabajoViewSet(RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_relation_fields = {
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
        "plan": ("equipo__sucursal_id", "equipo__sucursal__empresa_id"),
        "responsable": ("perfil__sucursal_id", "perfil__empresa_id"),
    }
    serializer_class = OrdenTrabajoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = filtrar_por_scope(OrdenTrabajo.objects.select_related(
            "equipo", "plan", "responsable", "creada_por"
        ).prefetch_related(
            "fallas",
            Prefetch(
                "repuestos",
                queryset=RepuestoUtilizado.objects.select_related(
                    "insumo", "entrega__lote"
                ),
            ),
        ), self.request.user,
            campo_sucursal="equipo__sucursal_id",
            campo_empresa="equipo__sucursal__empresa_id",
        )
        estado = self.request.query_params.get("estado")
        equipo = self.request.query_params.get("equipo")
        if estado:
            queryset = queryset.filter(estado=estado)
        if equipo:
            queryset = queryset.filter(equipo_id=equipo)
        return queryset

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.estado in {
            OrdenTrabajo.Estado.CERRADA, OrdenTrabajo.Estado.CANCELADA,
        }:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Una orden finalizada es inmutable.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def transicionar(self, request, pk=None):
        try:
            orden = transicionar_orden(
                orden_id=self.get_object().pk,
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
        return Response(self.get_serializer(orden).data)


class FallaEquipoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "equipo__sucursal_id"
    tenant_lookup_empresa = "equipo__sucursal__empresa_id"
    tenant_relation_fields = {
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
        "orden": ("equipo__sucursal_id", "equipo__sucursal__empresa_id"),
    }
    queryset = FallaEquipo.objects.select_related("equipo", "orden", "reportada_por")
    serializer_class = FallaEquipoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(reportada_por=self.request.user)


class RepuestoUtilizadoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "orden__equipo__sucursal_id"
    tenant_lookup_empresa = "orden__equipo__sucursal__empresa_id"
    tenant_relation_fields = {
        "orden": ("equipo__sucursal_id", "equipo__sucursal__empresa_id")
    }
    queryset = RepuestoUtilizado.objects.select_related(
        "orden", "insumo", "entrega__lote"
    )
    serializer_class = RepuestoUtilizadoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "head", "options"]


@api_view(["GET"])
def resumen(request):
    hoy = timezone.localdate()
    ordenes = filtrar_por_scope(
        OrdenTrabajo.objects.all(), request.user,
        campo_sucursal="equipo__sucursal_id", campo_empresa="equipo__sucursal__empresa_id",
    )
    planes = filtrar_por_scope(
        PlanPreventivo.objects.all(), request.user,
        campo_sucursal="equipo__sucursal_id", campo_empresa="equipo__sucursal__empresa_id",
    )
    fallas = filtrar_por_scope(
        FallaEquipo.objects.all(), request.user,
        campo_sucursal="equipo__sucursal_id", campo_empresa="equipo__sucursal__empresa_id",
    )
    return Response({
        "ordenes_abiertas": ordenes.exclude(
            estado__in=[OrdenTrabajo.Estado.CERRADA, OrdenTrabajo.Estado.CANCELADA]
        ).count(),
        "planes_vencidos": planes.filter(
            activo=True, proxima_ejecucion__lt=hoy
        ).count(),
        "fallas_criticas_abiertas": fallas.filter(
            severidad=FallaEquipo.Severidad.CRITICA, cerrada_en__isnull=True
        ).count(),
    })
