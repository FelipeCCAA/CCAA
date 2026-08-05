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
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    insumo_codigo = serializers.CharField(source="insumo.codigo", read_only=True)
    insumo_unidad = serializers.CharField(source="insumo.unidad", read_only=True)

    class Meta:
        model = InsumoProveedor
        fields = "__all__"

    def validate(self, datos):
        """
        Traduce el choque de la restricción a un mensaje que dice qué hacer.

        Sin esto, marcar un segundo proveedor como principal revienta con un
        error de base de datos: el operador ve un 500 y no que ya hay uno.
        """
        principal = datos.get(
            "principal", getattr(self.instance, "principal", False)
        )
        insumo = datos.get("insumo", getattr(self.instance, "insumo", None))

        if not principal or insumo is None:
            return datos

        otros = InsumoProveedor.objects.filter(insumo=insumo, principal=True)

        if self.instance is not None:
            otros = otros.exclude(pk=self.instance.pk)

        actual = otros.select_related("proveedor").first()

        if actual is not None:
            raise serializers.ValidationError({
                "principal": (
                    f"{insumo.nombre} ya tiene a {actual.proveedor.nombre} como "
                    "proveedor principal. Quítaselo antes de marcar otro: el "
                    "MRP calcula con sus condiciones y la orden se emite a él."
                )
            })

        return datos


class BodegaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bodega
        fields = "__all__"


class UbicacionSerializer(serializers.ModelSerializer):
    bodega_nombre = serializers.CharField(source="bodega.nombre", read_only=True)
    # El tipo decide qué puede entrar: `registrar_entrada` manda a cuarentena
    # lo que requiere Calidad y a disponible lo que no. Viaja rotulado para
    # que la pantalla no tenga que traducir los códigos por su cuenta.
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

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
    insumo_unidad = serializers.CharField(source="insumo.unidad", read_only=True)

    # Qué exige este material al recibirlo. Viaja con la línea para que la
    # pantalla pida solo lo que corresponde: `recibir_detalle_compra` rechaza
    # la recepción si falta el lote, el vencimiento, la temperatura o el
    # certificado que el material declara, y descubrirlo al enviar el
    # formulario obliga a rehacerlo con el camión esperando.
    requiere_lote = serializers.BooleanField(source="insumo.requiere_lote", read_only=True)
    requiere_vencimiento = serializers.BooleanField(
        source="insumo.requiere_vencimiento", read_only=True
    )
    requiere_temperatura = serializers.BooleanField(
        source="insumo.requiere_temperatura", read_only=True
    )
    requiere_certificado = serializers.BooleanField(
        source="insumo.requiere_certificado", read_only=True
    )
    requiere_calidad = serializers.BooleanField(
        source="insumo.requiere_calidad", read_only=True
    )

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
    destino_etiqueta = serializers.CharField(source="get_destino_display", read_only=True)
    lote_codigo = serializers.CharField(source="inspeccion.lote.codigo", read_only=True)
    insumo_nombre = serializers.CharField(
        source="inspeccion.lote.insumo.nombre", read_only=True
    )
    cerrada_por_nombre = serializers.CharField(
        source="cerrada_por.username", read_only=True, allow_null=True
    )
    # Si la concesión que la resolvió sigue amparando algo. Se calcula desde su
    # vencimiento, no se guarda.
    liberacion_vigente = serializers.BooleanField(
        source="liberacion.vigente", read_only=True, allow_null=True
    )

    class Meta:
        model = NoConformidadMaterial
        fields = "__all__"
        # El cierre pasa por `cerrar_no_conformidad`, que exige decir qué se
        # hizo. Dejarlos escribibles permitiría marcarla cerrada por PATCH
        # saltándose esa regla.
        read_only_fields = [
            "creada_por", "creada_en", "cerrada", "cerrada_por", "cerrada_en",
            "accion_tomada",
        ]


class LiberacionExcepcionalSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo", read_only=True)
    insumo_nombre = serializers.CharField(source="lote.insumo.nombre", read_only=True)
    solicitante_nombre = serializers.CharField(
        source="solicitante.username", read_only=True
    )
    calidad_nombre = serializers.CharField(
        source="aprobada_calidad_por.username", read_only=True
    )
    jefatura_nombre = serializers.CharField(
        source="aprobada_jefatura_por.username", read_only=True, allow_null=True
    )
    # `activa` dice lo que alguien marcó; `vigente` dice si además no ha
    # vencido. `vence_en` existía desde el principio y nadie lo miraba.
    vigente = serializers.BooleanField(read_only=True)

    class Meta:
        model = LiberacionExcepcionalMaterial
        fields = "__all__"
        read_only_fields = ["aprobada_calidad_por", "autorizada_en"]

    def validate(self, datos):
        """
        El modelo valida y aquí se le llama.

        Antes esto repetía a mano dos de las reglas del modelo y se saltaba las
        otras —la segregación de firmas—, así que quien solicitaba la concesión
        podía aprobarla por Calidad. Es lo mismo que las solicitudes de compra
        ya impedían, y aquí pesa más: lo que se autoriza es usar material que
        Calidad no aprobó.
        """
        instancia = self.instance or LiberacionExcepcionalMaterial()

        for campo, valor in datos.items():
            setattr(instancia, campo, valor)

        # `aprobada_calidad_por` es de solo lectura y lo pone la vista con el
        # usuario de la sesión, así que hay que ponerlo antes de validar.
        usuario = getattr(self.context.get("request"), "user", None)

        if instancia.aprobada_calidad_por_id is None and usuario is not None:
            instancia.aprobada_calidad_por = usuario

        instancia.clean()

        return datos
        return datos


class AdjuntoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Adjunto
        fields = "__all__"
        read_only_fields = ["autor", "hash_sha256", "creado_en"]

    def validate_archivo(self, archivo):
        from pathlib import Path
        from django.conf import settings

        extensiones = {".pdf", ".xlsx", ".xls", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
        extension = Path(archivo.name).suffix.lower()
        if extension not in extensiones:
            raise serializers.ValidationError(
                "Formato no permitido. Usa PDF, Excel, CSV o una imagen JPG/PNG/WEBP."
            )
        if archivo.size > settings.MAX_UPLOAD_SIZE:
            limite_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise serializers.ValidationError(f"El archivo supera el límite de {limite_mb} MB.")
        return archivo


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
