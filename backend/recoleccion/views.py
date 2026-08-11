from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EscribeRecepcion
from usuarios.tenancy import QuerysetTenantMixin, RelacionesTenantMixin

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion
from .serializers import ParadaRutaSerializer, RecoleccionSerializer, RutaRecoleccionSerializer, CargaModuloSerializer
from .services import agregar_carga, cerrar_ruta


class RutaRecoleccionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "vehiculo__sucursal_id"
    tenant_lookup_empresa = "vehiculo__sucursal__empresa_id"
    tenant_relation_fields = {
        "vehiculo": ("sucursal_id", "sucursal__empresa_id"),
        "conductor": ("perfil__sucursal_id", "perfil__empresa_id"),
    }
    queryset = RutaRecoleccion.objects.select_related(
        "vehiculo", "conductor", "creada_por"
    ).prefetch_related(
        Prefetch("paradas", queryset=ParadaRuta.objects.select_related("recoleccion"))
    )
    serializer_class = RutaRecoleccionSerializer
    permission_classes = [EscribeRecepcion]

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        try:
            ruta = cerrar_ruta(self.get_object().pk)
        except DjangoValidationError as error:
            return Response({"detail": error.messages[0]}, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(ruta).data)


class ParadaRutaViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ruta__vehiculo__sucursal_id"
    tenant_lookup_empresa = "ruta__vehiculo__sucursal__empresa_id"
    tenant_relation_fields = {
        "ruta": ("vehiculo__sucursal_id", "vehiculo__sucursal__empresa_id")
    }
    queryset = ParadaRuta.objects.select_related("ruta")
    serializer_class = ParadaRutaSerializer
    permission_classes = [EscribeRecepcion]


class RecoleccionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "parada__ruta__vehiculo__sucursal_id"
    tenant_lookup_empresa = "parada__ruta__vehiculo__sucursal__empresa_id"
    tenant_relation_fields = {
        "parada": ("ruta__vehiculo__sucursal_id", "ruta__vehiculo__sucursal__empresa_id")
    }
    queryset = Recoleccion.objects.select_related(
        "parada__ruta__vehiculo", "operador"
    ).prefetch_related("cargas")
    serializer_class = RecoleccionSerializer
    permission_classes = [EscribeRecepcion]

    def create(self, request, *args, **kwargs):
        idempotencia = request.data.get("idempotencia")
        if idempotencia:
            existente = self.get_queryset().filter(idempotencia=idempotencia).first()
            if existente:
                return Response(self.get_serializer(existente).data, status=status.HTTP_200_OK)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        recoleccion = serializer.save(operador=self.request.user)
        parada = recoleccion.parada
        if recoleccion.alcohol == Recoleccion.Alcohol.NO_CONFORME:
            recoleccion.estado = Recoleccion.Estado.RECHAZADA
            parada.estado = ParadaRuta.Estado.NO_CARGADA
            parada.salida = timezone.now()
            recoleccion.save(update_fields=["estado"])
            parada.save(update_fields=["estado", "salida"])
        elif parada.ruta.estado == RutaRecoleccion.Estado.PROGRAMADA:
            parada.ruta.estado = RutaRecoleccion.Estado.EN_CURSO
            parada.ruta.save(update_fields=["estado", "actualizada_en"])

    @action(detail=True, methods=["post"], url_path="cargas")
    def cargas(self, request, pk=None):
        serializer = CargaModuloSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            carga, creada = agregar_carga(
                recoleccion_id=self.get_object().pk,
                codigo=serializer.validated_data["codigo"],
                modulo=serializer.validated_data["modulo"],
                estanque_origen=serializer.validated_data.get("estanque_origen", ""),
                litros=serializer.validated_data["litros"],
            )
        except DjangoValidationError as error:
            return Response({"detail": error.messages[0]}, status=status.HTTP_409_CONFLICT)
        return Response(
            CargaModuloSerializer(carga).data,
            status=status.HTTP_201_CREATED if creada else status.HTTP_200_OK,
        )


class CargaModuloViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "recoleccion__parada__ruta__vehiculo__sucursal_id"
    tenant_lookup_empresa = "recoleccion__parada__ruta__vehiculo__sucursal__empresa_id"
    queryset = CargaModulo.objects.select_related(
        "recoleccion__parada__ruta__vehiculo", "recepcion_planta"
    )
    serializer_class = CargaModuloSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset()
        if self.request.query_params.get("pendientes") in {"1", "true"}:
            consulta = consulta.filter(recepcion_planta__isnull=True)
        return consulta
