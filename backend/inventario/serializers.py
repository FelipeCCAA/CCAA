from copy import copy

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from decimal import Decimal, ROUND_CEILING

from maestros.models import Silo
from produccion.models import PalletProducto

from .models import (
    Adjunto, AjusteInventario, Alerta, Bodega, CicloCIP, EtapaCIP,
    DetalleOrdenCompra, DevolucionProduccion,
    DetalleSolicitudCompra, EjecucionMRP, DetalleSolicitudMaterial, Existencia,
    InspeccionMaterial, Insumo,
    InsumoProveedor, LoteInventario, MovimientoInventario, Notificacion,
    LiberacionExcepcionalMaterial, NoConformidadMaterial, OrdenCompra,
    PlantillaInspeccion, Proveedor, RecepcionCompra, ResultadoMRP,
    SolicitudCompra, SolicitudMaterial, Ubicacion,
    ClienteDespacho, Despacho, DetalleDespacho, ExistenciaProductoTerminado,
    MovimientoProductoTerminado,
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

    def _saldos(self, insumo):
        """Calcula los saldos una vez durante la serialización de la fila."""
        cache = getattr(self, "_saldos_cache", None)
        if cache is None:
            cache = self._saldos_cache = {}
        clave = id(insumo)
        if clave not in cache:
            existencias = (
                existencia
                for lote in insumo.lotes.all()
                for existencia in lote.existencias.all()
            )
            fisico = Decimal("0")
            disponible = Decimal("0")
            for existencia in existencias:
                fisico += existencia.cantidad_fisica
                disponible += existencia.cantidad_disponible
            cache[clave] = (fisico, disponible)
        return cache[clave]

    def get_stock_fisico(self, insumo):
        return self._saldos(insumo)[0]

    def get_stock_disponible(self, insumo):
        return self._saldos(insumo)[1]

    def get_stock_bloqueado(self, insumo):
        fisico, disponible = self._saldos(insumo)
        return fisico - disponible

    def _eoq_ajuste(self, insumo):
        cache = getattr(self, "_eoq_cache", None)
        if cache is None:
            cache = self._eoq_cache = {}
        clave = id(insumo)
        if clave in cache:
            return cache[clave]

        if insumo.eoq is None:
            faltan = []
            if insumo.demanda_anual <= 0: faltan.append("demanda anual")
            if insumo.costo_por_pedido <= 0: faltan.append("costo por pedido")
            if insumo.costo_mantencion_unitario <= 0: faltan.append("costo de mantención")
            cache[clave] = (None, {"valido": False, "faltan": faltan})
            return cache[clave]
        cantidad = insumo.eoq
        motivos = []
        principales = getattr(insumo, "proveedores_principales", None)
        if principales is None:
            proveedor = (
                insumo.proveedores.filter(principal=True).order_by("id").first()
            )
        else:
            proveedor = principales[0] if principales else None
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
        cache[clave] = (
            cantidad,
            {
                "valido": True,
                "motivos": motivos or ["EOQ matemático"],
                "cobertura_dias": round(float(cobertura), 1) if cobertura else None,
            },
        )
        return cache[clave]

    def get_eoq_ajustado(self, insumo):
        return self._eoq_ajuste(insumo)[0]

    def get_explicacion_eoq(self, insumo):
        return self._eoq_ajuste(insumo)[1]


class EtapaCIPSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = EtapaCIP
        exclude = ["ciclo"]


class CicloCIPSerializer(serializers.ModelSerializer):
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    tipo_aseo_etiqueta = serializers.CharField(source="get_tipo_aseo_display", read_only=True)
    tipo_objetivo_etiqueta = serializers.CharField(source="get_tipo_objetivo_display", read_only=True)
    verificacion_etiqueta = serializers.CharField(source="get_verificacion_display", read_only=True)
    equipo_nombre = serializers.CharField(
        source="equipo.nombre", read_only=True, allow_null=True
    )
    silo_nombre = serializers.CharField(source="silo.codigo", read_only=True, allow_null=True)
    objetivo_nombre = serializers.CharField(read_only=True)
    responsable_nombre = serializers.SerializerMethodField()
    ejecutado_por_nombre = serializers.SerializerMethodField()
    verificado_por_nombre = serializers.SerializerMethodField()
    etapas = EtapaCIPSerializer(many=True, required=False)

    class Meta:
        model = CicloCIP
        exclude = ["sucursal"]
        read_only_fields = [
            "responsable", "ejecutado_por", "verificado_por", "inicio_real", "fin"
        ]

    def get_responsable_nombre(self, ciclo):
        if not ciclo.responsable:
            return ""
        return ciclo.responsable.get_full_name() or ciclo.responsable.username

    def get_ejecutado_por_nombre(self, ciclo):
        if not ciclo.ejecutado_por:
            return ""
        return ciclo.ejecutado_por.get_full_name() or ciclo.ejecutado_por.username

    def get_verificado_por_nombre(self, ciclo):
        if not ciclo.verificado_por:
            return ""
        return ciclo.verificado_por.get_full_name() or ciclo.verificado_por.username

    @staticmethod
    def _guardar_etapas(ciclo, etapas):
        if etapas is None:
            return
        ciclo.etapas.all().delete()
        EtapaCIP.objects.bulk_create(
            EtapaCIP(ciclo=ciclo, **etapa) for etapa in etapas
        )

    @transaction.atomic
    def create(self, validated_data):
        etapas = validated_data.pop("etapas", [])
        usuario = getattr(self.context.get("request"), "user", None)
        if validated_data.get("estado") == CicloCIP.Estado.EN_CURSO:
            validated_data["inicio_real"] = timezone.now()
            validated_data["ejecutado_por"] = usuario
        if validated_data.get("estado") in (CicloCIP.Estado.COMPLETADO, CicloCIP.Estado.OBSERVADO):
            validated_data["fin"] = timezone.now()
            validated_data["verificado_por"] = usuario
        ciclo = super().create(validated_data)
        self._sincronizar_silo(ciclo)
        self._guardar_etapas(ciclo, etapas)
        return ciclo

    @transaction.atomic
    def update(self, instance, validated_data):
        etapas = validated_data.pop("etapas", None)
        estado_anterior = instance.estado
        ciclo = super().update(instance, validated_data)
        usuario = getattr(self.context.get("request"), "user", None)
        if ciclo.estado == CicloCIP.Estado.EN_CURSO and not ciclo.inicio_real:
            ciclo.inicio_real = timezone.now()
            ciclo.ejecutado_por = usuario
            ciclo.save(update_fields=["inicio_real", "ejecutado_por"])
        if ciclo.estado in (CicloCIP.Estado.COMPLETADO, CicloCIP.Estado.OBSERVADO) and not ciclo.fin:
            ciclo.fin = timezone.now()
            ciclo.verificado_por = usuario
            ciclo.save(update_fields=["fin", "verificado_por"])
        if estado_anterior != CicloCIP.Estado.PROGRAMADO and ciclo.estado == CicloCIP.Estado.PROGRAMADO:
            raise serializers.ValidationError("Un aseo iniciado no puede volver a Programado.")
        self._sincronizar_silo(ciclo)
        self._guardar_etapas(ciclo, etapas)
        return ciclo

    @staticmethod
    def _sincronizar_silo(ciclo):
        if ciclo.tipo_objetivo != CicloCIP.TipoObjetivo.SILO or not ciclo.silo_id:
            return
        silo = ciclo.silo
        if ciclo.estado == CicloCIP.Estado.EN_CURSO:
            nuevo = Silo.Estado.EN_CIP
        elif ciclo.estado == CicloCIP.Estado.COMPLETADO:
            nuevo = Silo.Estado.DISPONIBLE
        elif ciclo.estado == CicloCIP.Estado.OBSERVADO:
            nuevo = Silo.Estado.PENDIENTE_CIP
        else:
            return
        if silo.estado != nuevo:
            silo.estado = nuevo
            silo.save(update_fields=["estado"])

    def validate(self, datos):
        """
        No se empieza un CIP sobre un equipo que está produciendo.

        Es la regla 15 por el otro lado. Con solo una de las dos direcciones,
        la regla se cumple o no según cuál de las dos acciones llegue primero:
        si producción arranca antes, el CIP entraría igual y quedarían las dos
        cosas ocurriendo a la vez sobre la misma máquina.
        """
        from .servicios import equipo_produciendo

        # Validar un PATCH no debe mutar la instancia antes de `update`: de lo
        # contrario se pierde el estado anterior y las transiciones dejan de
        # ser auditables incluso si la validación termina fallando.
        instancia = copy(self.instance) if self.instance else CicloCIP()

        for campo, valor in datos.items():
            if campo != "etapas":
                setattr(instancia, campo, valor)

        errores = {}
        if instancia.tipo_objetivo == CicloCIP.TipoObjetivo.EQUIPO:
            if not instancia.equipo:
                errores["equipo"] = "Selecciona la máquina o equipo que se aseará."
            instancia.silo = None
            instancia.seccion = ""
            datos["silo"] = None
            datos["seccion"] = ""
        elif instancia.tipo_objetivo == CicloCIP.TipoObjetivo.SILO:
            if not instancia.silo:
                errores["silo"] = "Selecciona el silo o tanque que se aseará."
            instancia.equipo = None
            instancia.seccion = ""
            datos["equipo"] = None
            datos["seccion"] = ""
        else:
            if not instancia.seccion.strip():
                errores["seccion"] = "Indica el área o sección donde se hará el aseo."
            instancia.equipo = None
            instancia.silo = None
            datos["equipo"] = None
            datos["silo"] = None

        if instancia.estado == CicloCIP.Estado.COMPLETADO:
            if instancia.verificacion != CicloCIP.Verificacion.CONFORME:
                errores["verificacion"] = "Para completar el aseo, la verificación final debe quedar Conforme."
            etapas = datos.get("etapas")
            hay_etapa_no_conforme = (
                any(etapa.get("cumple") is False for etapa in etapas)
                if etapas is not None
                else self.instance is not None and self.instance.etapas.filter(cumple=False).exists()
            )
            if hay_etapa_no_conforme:
                errores["etapas"] = "Hay etapas que no cumplen; cierra el aseo como Observado."
            if instancia.ph_final is not None and not (Decimal("5.5") <= instancia.ph_final <= Decimal("8.5")):
                errores["ph_final"] = "El pH final conforme debe estar entre 5,5 y 8,5."
        if instancia.estado == CicloCIP.Estado.OBSERVADO:
            datos["verificacion"] = CicloCIP.Verificacion.OBSERVADO
        if errores:
            raise serializers.ValidationError(errores)

        if instancia.estado != CicloCIP.Estado.EN_CURSO:
            return datos

        motivo = equipo_produciendo(instancia.equipo)

        if motivo:
            raise serializers.ValidationError({"equipo": motivo})

        return datos


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
        fields = ["id", "codigo", "nombre", "area", "activo"]


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
    ubicacion_tipo = serializers.CharField(source="ubicacion.tipo", read_only=True)
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
        read_only_fields = ["cantidad_aprobada", "cantidad_entregada"]


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
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    # La pantalla necesita una sola pregunta para saber si dejar de consultar.
    # Deducirlo de la lista de estados en el cliente obliga a mantener esa
    # lista en dos sitios.
    terminada = serializers.SerializerMethodField()

    class Meta:
        model = EjecucionMRP
        fields = "__all__"
        # El estado y el fallo los escribe la tarea. Escribibles desde la API,
        # cualquiera podría marcar como terminada una ejecución a medias — y
        # nadie vuelve a mirar algo que figura hecho.
        read_only_fields = [
            "creada_en", "ejecutada_por", "parametros",
            "estado", "error", "terminada_en",
        ]

    def get_terminada(self, ejecucion) -> bool:
        return ejecucion.estado in (
            EjecucionMRP.Estado.TERMINADA,
            EjecucionMRP.Estado.FALLIDA,
        )


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
    # Cuánto se ha consumido bajo ella y cuánto queda. Se suman del libro de
    # movimientos: un contador guardado se desincroniza, y lo que se estaría
    # desajustando es cuánto material no aprobado salió de bodega.
    cantidad_usada = serializers.DecimalField(
        max_digits=16, decimal_places=3, read_only=True
    )
    saldo = serializers.DecimalField(
        max_digits=16, decimal_places=3, read_only=True
    )

    class Meta:
        model = LiberacionExcepcionalMaterial
        fields = "__all__"
        read_only_fields = [
            "aprobada_calidad_por", "aprobada_jefatura_por", "autorizada_en",
            "activa",
        ]

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

        from .adjuntos import ContenidoNoCorresponde, verificar

        extensiones = {".pdf", ".xlsx", ".xls", ".csv", ".png", ".jpg", ".jpeg", ".webp"}
        extension = Path(archivo.name).suffix.lower()
        if extension not in extensiones:
            raise serializers.ValidationError(
                "Formato no permitido. Usa PDF, Excel, CSV o una imagen JPG/PNG/WEBP."
            )
        if archivo.size > settings.MAX_UPLOAD_SIZE:
            limite_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
            raise serializers.ValidationError(f"El archivo supera el límite de {limite_mb} MB.")

        # La extensión la elige quien sube: renombrar `payload.html` a
        # `guia.pdf` bastaba para almacenar HTML ejecutable y repartir el
        # enlace. Se comprueba lo que el archivo trae dentro.
        try:
            verificar(archivo)
        except ContenidoNoCorresponde as error:
            raise serializers.ValidationError(str(error)) from error

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


class ClienteDespachoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClienteDespacho
        fields = "__all__"
        read_only_fields = ["empresa"]


class ExistenciaProductoTerminadoSerializer(serializers.ModelSerializer):
    pallet_codigo = serializers.CharField(source="pallet.codigo", read_only=True)
    lote_codigo = serializers.CharField(source="pallet.envase.lote.codigo", read_only=True)
    producto_nombre = serializers.CharField(source="pallet.envase.lote.producto.nombre", read_only=True)
    ubicacion_codigo = serializers.CharField(source="ubicacion.codigo", read_only=True)
    kg_neto = serializers.DecimalField(source="pallet.kg_neto", max_digits=14, decimal_places=3, read_only=True)
    estado_inventario = serializers.SerializerMethodField()
    kg_disponible = serializers.SerializerMethodField()

    def get_estado_inventario(self, obj):
        from produccion.models import PalletProducto
        return {
            PalletProducto.Estado.PENDIENTE_CALIDAD: "cuarentena",
            PalletProducto.Estado.BLOQUEADO: "bloqueado",
            PalletProducto.Estado.LIBERADO: "disponible",
            PalletProducto.Estado.EN_INVENTARIO: "disponible",
            PalletProducto.Estado.DESPACHADO: "despachado",
            PalletProducto.Estado.ANULADO: "anulado",
        }.get(obj.pallet.estado, "cuarentena")

    def get_kg_disponible(self, obj):
        return obj.pallet.kg_neto if self.get_estado_inventario(obj) == "disponible" else 0

    class Meta:
        model = ExistenciaProductoTerminado
        fields = "__all__"
        read_only_fields = ["pallet", "ubicacion", "activo", "actualizado_en"]


class MovimientoProductoTerminadoSerializer(serializers.ModelSerializer):
    pallet_codigo = serializers.CharField(source="pallet.codigo", read_only=True)

    class Meta:
        model = MovimientoProductoTerminado
        fields = "__all__"


class DetalleDespachoSerializer(serializers.ModelSerializer):
    pallet_codigo = serializers.CharField(source="pallet.codigo", read_only=True)
    lote_codigo = serializers.CharField(source="pallet.envase.lote.codigo", read_only=True)
    kg_neto = serializers.DecimalField(source="pallet.kg_neto", max_digits=14, decimal_places=3, read_only=True)

    class Meta:
        model = DetalleDespacho
        fields = "__all__"
        read_only_fields = ["despacho"]


class DespachoSerializer(serializers.ModelSerializer):
    detalles = DetalleDespachoSerializer(many=True, read_only=True)
    pallet_ids = serializers.PrimaryKeyRelatedField(
        source="pallets_solicitados", queryset=PalletProducto.objects.all(),
        many=True, write_only=True,
    )
    cliente_nombre = serializers.CharField(source="cliente.nombre", read_only=True)

    class Meta:
        model = Despacho
        exclude = ["sucursal"]
        read_only_fields = ["sucursal", "creado_por", "autorizado_por", "estado", "creado_en", "autorizado_en", "despachado_en"]

    def validate_pallet_ids(self, pallets):
        ids = [p.pk for p in pallets]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Un pallet no puede repetirse en el mismo despacho.")
        if not ids:
            raise serializers.ValidationError("Selecciona al menos un pallet.")
        return pallets

    def create(self, validated_data):
        pallets = validated_data.pop("pallets_solicitados")
        despacho = super().create(validated_data)
        DetalleDespacho.objects.bulk_create([DetalleDespacho(despacho=despacho, pallet=p) for p in pallets])
        return despacho
