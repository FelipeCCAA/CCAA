from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeAdministracion

from .models import Especificacion, Mandante, Producto, Silo, Vehiculo
from .serializers import (
    EspecificacionSerializer,
    MandanteSerializer,
    ParametroSerializer,
    ProductoSerializer,
    SiloSerializer,
    VehiculoSerializer,
)


class MandanteViewSet(viewsets.ModelViewSet):
    queryset = Mandante.objects.all()
    serializer_class = MandanteSerializer
    permission_classes = [EscribeAdministracion]


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related("mandante")
    serializer_class = ProductoSerializer
    permission_classes = [EscribeAdministracion]

    def get_queryset(self):
        consulta = super().get_queryset()

        familia = self.request.query_params.get("familia")
        if familia:
            consulta = consulta.filter(familia=familia)

        mandante = self.request.query_params.get("mandante")
        if mandante:
            consulta = consulta.filter(mandante_id=mandante)

        return consulta


class EspecificacionViewSet(viewsets.ModelViewSet):
    queryset = Especificacion.objects.select_related("producto")
    serializer_class = EspecificacionSerializer
    permission_classes = [EscribeAdministracion]

    def get_queryset(self):
        consulta = super().get_queryset()

        producto = self.request.query_params.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        return consulta


class SiloViewSet(viewsets.ModelViewSet):
    queryset = Silo.objects.all()
    serializer_class = SiloSerializer
    permission_classes = [EscribeAdministracion]


class VehiculoViewSet(viewsets.ModelViewSet):
    queryset = Vehiculo.objects.all()
    serializer_class = VehiculoSerializer
    permission_classes = [EscribeAdministracion]


@api_view(["GET"])
def parametros(request):
    """Catálogo de parámetros fisicoquímicos medibles."""
    return Response(ParametroSerializer(ParametroSerializer.catalogo(), many=True).data)
