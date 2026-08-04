from rest_framework import serializers
from decimal import Decimal, ROUND_CEILING

from .models import (
    Adjunto, AjusteInventario, Alerta, Bodega, CicloCIP,
    DetalleOrdenCompra, DevolucionProduccion,
    DetalleSolicitudCompra, EjecucionMRP, DetalleSolicitudMaterial, Existencia,
    InspeccionMaterial, Insumo,
    InsumoProveedor, LoteInventario, MovimientoInventario, Notificacion,
    LiberacionExcepcionalMaterial, NoConformidadMaterial, OrdenCompra,
    PlantillaInspeccion, Proveedor, RecepcionCompra, ResultadoMRP,
    SolicitudCompra, SolicitudMaterial, Ubicacion,
)


class InsumoSerializer(serializers.ModelSerializer):
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)
    unidad_etiqueta = serializers.CharField(source="get_unidad_display", read_only=True)
    eoq = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    punto_reposicion = serializers.DecimalField(max_digits=14, decimal_places=3, read_only=True)
    stock_fisico = serializers.SerializerMethodField()
    stock_disponible = serializers.SerializerMethodField()
    stock_bloqueado = serializers.SerializerMethodField()
    eoq_ajustado = serializers.SerializerMethodField()
    explicacion_eoq = serializers.SerializerMethodField()

    class Meta:
        model = Insumo
        fields = "__all__"

    def _existencias(self, insumo):
        return [e for lote in insumo.lotes.all() for e in lote.existencias.all()]

    def get_stock_fisico(self, insumo):
        return sum((e.cantidad_fisica for e in self._existencias(insumo)), 0)

    def get_stock_disponible(self, insumo):
        return sum((e.cantidad_disponible for e in self._existencias(insumo)), 0)

    def get_stock_bloqueado(self, insumo):
        return self.get_stock_fisico(insumo) - self.get_stock_disponible(insumo)

    def _eoq_ajuste(self, insumo):
        if insumo.eoq is None:
            faltan = []
            if insumo.demanda_anual <= 0: faltan.append("demanda anual")
            if insumo.costo_por_pedido <= 0: faltan.append("costo por pedido")
            if insumo.costo_mantencion_unitario <= 0: faltan.append("costo de mantención")
            return None, {"valido": False, "faltan": faltan}
        cantidad = insumo.eoq
        motivos = []
        proveedor = insumo.proveedores.filter(principal=True).order_by("id").first()
        if proveedor:
            if cantidad < proveedor.compra_minima:
                cantidad = proveedor.compra_minima; motivos.append("mínimo del proveedor")
            multiplo = proveedor.multiplo_compra or Decimal("1")
            ajustada = (cantidad / multiplo).to_integral_value(rounding=ROUND_CEILING) * multiplo
            if ajustada != cantidad: motivos.append("múltiplo de compra")
            cantidad = ajustada
        if insumo.stock_maximo > 0 and cantidad > insumo.stock_maximo:
            cantidad = insumo.stock_maximo; motivos.append("capacidad/stock máximo")
        if insumo.vida_util_dias > 0 and insumo.demanda_anual > 0:
            consumible = insumo.demanda_anual / Decimal("365") * insumo.vida_util_dias
            if cantidad > consumible:
                cantidad = consumible; motivos.append("vida útil")
        cobertura = cantidad / (insumo.demanda_anual / Decimal("365")) if insumo.demanda_anual > 0 else None
        return cantidad, {"valido": True, "motivos": motivos or ["EOQ matemático"], "cobertura_dias": round(float(cobertura), 1) if cobertura else None}

    def get_eoq_ajustado(self, insumo):
        return self._eoq_ajuste(insumo)[0]

    def get_explicacion_eoq(self, insumo):
        return self._eoq_ajuste(insumo)[1]


class CicloCIPSerializer(serializers.ModelSerializer):
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = CicloCIP
        fields = "__all__"


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = "__all__"


class InsumoProveedorSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)

    class Meta:
        model = InsumoProveedor
        fields = "__all__"


class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = "__all__"


class UbicacionSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)

    class Meta:
        model = Ubicacion
        fields = "__all__"


class LoteInventarioSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    insumo_codigo = serializers.CharField(source="insumo.codigo", read_only=True)
    insumo_unidad = serializers.CharField(source="insumo.unidad", read_only=True)
    proveedor_nombre = serializers.CharField(
        source="proveedor.nombre", read_only=True, allow_null=True
    )
    estado_etiqueta = serializers.CharField(source="get_estado_calidad_display", read_only=True)
    # Los dos se calculan y no se guardan. `utilizable` es el que decide si el
    # material puede salir: aprobado, vigente y no vencido.
    vencido = serializers.BooleanField(read_only=True)
    utilizable = serializers.BooleanField(read_only=True)

    class Meta:
        model = LoteInventario
        fields = "__all__"
        read_only_fields = ["estado_calidad"]


class ExistenciaSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo", read_only=True)
    insumo_nombre = serializers.CharField(source="lote.insumo.nombre", read_only=True)
    ubicacion_codigo = serializers.CharField(source="ubicacion.codigo", read_only=True)
    estado_calidad = serializers.CharField(source="lote.estado_calidad", read_only=True)
    cantidad_disponible = serializers.DecimalField(max_digits=16, decimal_places=3, read_only=True)

    class Meta:
        model = Existencia
        fields = "__all__"
        read_only_fields = ["cantidad_fisica", "cantidad_reservada"]


class MovimientoSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo", read_only=True)
    insumo_nombre = serializers.CharField(source="lote.insumo.nombre", read_only=True)
    origen_codigo = serializers.CharField(source="origen.codigo", read_only=True, allow_null=True)
    destino_codigo = serializers.CharField(source="destino.codigo", read_only=True, allow_null=True)

    class Meta:
        model = MovimientoInventario
        fields = "__all__"
        read_only_fields = [campo.name for campo in MovimientoInventario._meta.fields]


class SolicitudCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudCompra
        fields = "__all__"
        read_only_fields = ["solicitante", "estado", "creada_en"]


class DetalleSolicitudCompraSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = DetalleSolicitudCompra
        fields = "__all__"


class DetalleOrdenCompraSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = DetalleOrdenCompra
        fields = "__all__"
        read_only_fields = ["cantidad_recibida"]


class OrdenCompraSerializer(serializers.ModelSerializer):
    detalles = DetalleOrdenCompraSerializer(many=True, read_only=True)
    proveedor_nombre = serializers.CharField(source="proveedor.nombre", read_only=True)

    class Meta:
        model = OrdenCompra
        fields = "__all__"
        read_only_fields = ["estado"]


class RecepcionCompraSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecepcionCompra
        fields = "__all__"
        read_only_fields = ["receptor", "recibida_en"]


class InspeccionMaterialSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo", read_only=True)
    insumo_nombre = serializers.CharField(source="lote.insumo.nombre", read_only=True)

    class Meta:
        model = InspeccionMaterial
        fields = "__all__"
        read_only_fields = ["estado", "responsable", "decidida_en", "creada_en"]


class DetalleSolicitudMaterialSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = DetalleSolicitudMaterial
        fields = "__all__"


class SolicitudMaterialSerializer(serializers.ModelSerializer):
    detalles = DetalleSolicitudMaterialSerializer(many=True, read_only=True)

    class Meta:
        model = SolicitudMaterial
        fields = "__all__"
        read_only_fields = ["solicitante", "estado", "creada_en"]


class NotificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificacion
        fields = "__all__"
        read_only_fields = ["destinatario", "tipo", "titulo", "mensaje", "documento_tipo", "documento_id", "creada_en"]


class ResultadoMRPSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = ResultadoMRP
        fields = "__all__"


class EjecucionMRPSerializer(serializers.ModelSerializer):
    resultados = ResultadoMRPSerializer(many=True, read_only=True)

    class Meta:
        model = EjecucionMRP
        fields = "__all__"
        read_only_fields = ["creada_en", "ejecutada_por", "parametros"]


class PlantillaInspeccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlantillaInspeccion
        fields = "__all__"


class NoConformidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = NoConformidadMaterial
        fields = "__all__"
        read_only_fields = ["creada_por", "creada_en"]


class LiberacionExcepcionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiberacionExcepcionalMaterial
        fields = "__all__"
        read_only_fields = ["aprobada_calidad_por", "autorizada_en"]

    def validate(self, datos):
        if datos.get("cantidad", 0) <= 0:
            raise serializers.ValidationError({"cantidad": "Debe ser mayor que cero."})
        if not str(datos.get("justificacion", "")).strip() or not str(datos.get("uso_especifico", "")).strip():
            raise serializers.ValidationError("La justificación y el uso específico son obligatorios.")
        return datos


class AdjuntoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adjunto
        fields = "__all__"
        read_only_fields = ["autor", "hash_sha256", "creado_en"]


class AlertaSerializer(serializers.ModelSerializer):
    """
    Una alerta se lee de un vistazo o no sirve.

    Por eso viajan los nombres y no solo las claves foráneas: el panel la
    muestra sin una segunda consulta, y una alerta que dice «insumo 47» obliga
    a ir a buscar cuál es justo cuando lo urgente es actuar.
    """

    insumo_nombre = serializers.CharField(
        source="insumo.nombre", read_only=True, allow_null=True
    )
    insumo_codigo = serializers.CharField(
        source="insumo.codigo", read_only=True, allow_null=True
    )
    lote_codigo = serializers.CharField(
        source="lote.codigo", read_only=True, allow_null=True
    )
    severidad_etiqueta = serializers.CharField(
        source="get_severidad_display", read_only=True
    )

    class Meta:
        model = Alerta
        fields = "__all__"


class AjusteInventarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = AjusteInventario
        fields = "__all__"
        read_only_fields = ["solicitante", "aprobador", "estado", "creado_en", "aplicado_en"]


class DevolucionProduccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = DevolucionProduccion
        fields = "__all__"
        read_only_fields = ["registrada_por", "fecha"]
