from decimal import Decimal
from math import ceil

from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from usuarios.models import PerfilUsuario
from usuarios.permisos import EsAdministrador

from .models import CicloCIP, ConsumoProducto, Insumo
from .serializers import CicloCIPSerializer, ConsumoProductoSerializer, InsumoSerializer


class FiltroAreaAdminMixin:
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        qs = super().get_queryset()
        perfil = getattr(self.request.user, "perfil", None)
        if self.request.user.is_superuser or perfil.area == PerfilUsuario.Area.ADMINISTRACION:
            return qs
        return qs.filter(area=perfil.area)


class InsumoViewSet(FiltroAreaAdminMixin, viewsets.ModelViewSet):
    queryset = Insumo.objects.all()
    serializer_class = InsumoSerializer


class ConsumoProductoViewSet(viewsets.ModelViewSet):
    queryset = ConsumoProducto.objects.select_related("producto", "insumo")
    serializer_class = ConsumoProductoSerializer
    permission_classes = [EsAdministrador]


class CicloCIPViewSet(FiltroAreaAdminMixin, viewsets.ModelViewSet):
    queryset = CicloCIP.objects.select_related("responsable")
    serializer_class = CicloCIPSerializer


@api_view(["POST"])
@permission_classes([EsAdministrador])
def calcular_mrp(request):
    try:
        producto_id = int(request.data["producto"])
        kilos = Decimal(str(request.data["kilos_producir"]))
        if kilos <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return Response({"error": "Producto y kilos a producir son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

    consumos = ConsumoProducto.objects.filter(producto_id=producto_id).select_related("insumo")
    resultado = []
    for consumo in consumos:
        requerido = kilos * consumo.cantidad_por_kg
        disponible = consumo.insumo.stock_actual
        comprar = max(Decimal("0"), requerido - disponible)
        envase = consumo.insumo.contenido_envase or Decimal("1")
        resultado.append({
            "insumo": consumo.insumo.nombre,
            "unidad": consumo.insumo.unidad,
            "requerido": requerido,
            "stock": disponible,
            "faltante": comprar,
            "envases_a_pedir": ceil(comprar / envase),
            "eoq": consumo.insumo.eoq,
        })
    return Response({"kilos_producir": kilos, "materiales": resultado})
