from rest_framework import serializers

from .models import CicloCIP, ConsumoProducto, Insumo


class InsumoSerializer(serializers.ModelSerializer):
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)
    unidad_etiqueta = serializers.CharField(source="get_unidad_display", read_only=True)
    eoq = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    punto_reposicion = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)

    class Meta:
        model = Insumo
        fields = "__all__"


class ConsumoProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = ConsumoProducto
        fields = "__all__"


class CicloCIPSerializer(serializers.ModelSerializer):
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = CicloCIP
        fields = "__all__"
