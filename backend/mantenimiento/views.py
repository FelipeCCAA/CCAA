from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeMantenimiento
from .models import FallaEquipo, OrdenTrabajo, PlanPreventivo, RepuestoUtilizado
from .serializers import (
    FallaEquipoSerializer, OrdenTrabajoSerializer, PlanPreventivoSerializer,
    RepuestoUtilizadoSerializer,
)
from .servicios import transicionar_orden


class PlanPreventivoViewSet(viewsets.ModelViewSet):
    queryset = PlanPreventivo.objects.select_related("equipo")
    serializer_class = PlanPreventivoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]


class OrdenTrabajoViewSet(viewsets.ModelViewSet):
    serializer_class = OrdenTrabajoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = OrdenTrabajo.objects.select_related(
            "equipo", "plan", "responsable", "creada_por"
        ).prefetch_related("fallas", "repuestos__insumo")
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


class FallaEquipoViewSet(viewsets.ModelViewSet):
    queryset = FallaEquipo.objects.select_related("equipo", "orden", "reportada_por")
    serializer_class = FallaEquipoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(reportada_por=self.request.user)


class RepuestoUtilizadoViewSet(viewsets.ModelViewSet):
    queryset = RepuestoUtilizado.objects.select_related("orden", "insumo")
    serializer_class = RepuestoUtilizadoSerializer
    permission_classes = [EscribeMantenimiento]
    http_method_names = ["get", "post", "head", "options"]


@api_view(["GET"])
def resumen(request):
    hoy = timezone.localdate()
    return Response({
        "ordenes_abiertas": OrdenTrabajo.objects.exclude(
            estado__in=[OrdenTrabajo.Estado.CERRADA, OrdenTrabajo.Estado.CANCELADA]
        ).count(),
        "planes_vencidos": PlanPreventivo.objects.filter(
            activo=True, proxima_ejecucion__lt=hoy
        ).count(),
        "fallas_criticas_abiertas": FallaEquipo.objects.filter(
            severidad=FallaEquipo.Severidad.CRITICA, cerrada_en__isnull=True
        ).count(),
    })
