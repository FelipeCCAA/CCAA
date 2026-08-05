from rest_framework import viewsets

from usuarios.permisos import EscribeRecepcion

from .models import (
    CargaPredio, Conductor, Modulo, Predio, ProveedorLeche, Recoleccion,
)
from .serializers import (
    CargaPredioSerializer, ConductorSerializer, ModuloSerializer,
    PredioSerializer, ProveedorLecheSerializer, RecoleccionSerializer,
)


# La recolección la lleva Recepción: es quien recibe el camión y quien tiene
# que poder contrastar lo que se cargó en el predio con lo que llegó.
class ProveedorLecheViewSet(viewsets.ModelViewSet):
    queryset = ProveedorLeche.objects.prefetch_related("predios")
    serializer_class = ProveedorLecheSerializer
    permission_classes = [EscribeRecepcion]


class PredioViewSet(viewsets.ModelViewSet):
    queryset = Predio.objects.select_related("proveedor")
    serializer_class = PredioSerializer
    permission_classes = [EscribeRecepcion]


class ConductorViewSet(viewsets.ModelViewSet):
    queryset = Conductor.objects.all()
    serializer_class = ConductorSerializer
    permission_classes = [EscribeRecepcion]


class ModuloViewSet(viewsets.ModelViewSet):
    queryset = Modulo.objects.select_related("vehiculo")
    serializer_class = ModuloSerializer
    permission_classes = [EscribeRecepcion]


class RecoleccionViewSet(viewsets.ModelViewSet):
    serializer_class = RecoleccionSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = Recoleccion.objects.select_related(
            "conductor", "camion", "carro"
        ).prefetch_related("cargas__predio__proveedor", "cargas__modulo")

        fecha = self.request.query_params.get("fecha")
        estado = self.request.query_params.get("estado")

        if fecha:
            consulta = consulta.filter(fecha=fecha)
        if estado:
            consulta = consulta.filter(estado=estado)

        return consulta

    def perform_create(self, serializer):
        serializer.save(registrada_por=self.request.user)


class CargaPredioViewSet(viewsets.ModelViewSet):
    serializer_class = CargaPredioSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = CargaPredio.objects.select_related(
            "predio__proveedor", "modulo", "recoleccion"
        )
        recoleccion = self.request.query_params.get("recoleccion")

        return consulta.filter(recoleccion_id=recoleccion) if recoleccion else consulta
