from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla, CorridaSecado,
    EjecucionProceso, EntradaProceso,
    EtapaProceso, EventoProceso, Proceso,
    RutaProducto, SalidaProceso,
)


def _error_de_dominio(error):
    detalle = (
        error.message_dict
        if hasattr(error, "message_dict")
        else {"non_field_errors": error.messages}
    )
    raise serializers.ValidationError(detalle) from error


class CierreCondensacionSerializer(serializers.Serializer):
    litros_precondensado = serializers.DecimalField(max_digits=14, decimal_places=2)
    flujo_promedio = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    densidad_salida = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    solidos_salida = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    temperatura_salida = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    vacio_promedio = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    presion_promedio = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)


class CrearCondensacionGuiadaSerializer(serializers.Serializer):
    lote = serializers.IntegerField(min_value=1)
    silo_destino = serializers.IntegerField(min_value=1)


class CrearMantequillaGuiadaSerializer(serializers.Serializer):
    orden = serializers.IntegerField(min_value=1)
    lote_crema = serializers.IntegerField(min_value=1)
    equipo = serializers.IntegerField(min_value=1)
    codigo_lote_mantequilla = serializers.CharField(max_length=60)
    lote_suero = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    kg_crema = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=1)


class CrearDescremacionGuiadaSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=60)
    etapa = serializers.IntegerField(min_value=1)
    equipo = serializers.IntegerField(min_value=1)
    silo_entera = serializers.IntegerField(min_value=1)
    analisis_entrada = serializers.IntegerField(min_value=1)
    litros_entrada = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=1)
    silo_descremada = serializers.IntegerField(min_value=1)
    estanque_crema = serializers.IntegerField(min_value=1)
    producto_descremada = serializers.IntegerField(min_value=1)
    producto_crema = serializers.IntegerField(min_value=1)
    litros_descremada_plan = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=1,
    )
    litros_crema_plan = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=1,
    )
    plan_confirmado = serializers.BooleanField()
    ruta_descremada = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    ruta_crema = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    destino_descremada = serializers.ChoiceField(
        choices=CorridaDescremacion.DestinoRama.choices,
        default=CorridaDescremacion.DestinoRama.PENDIENTE,
    )
    destino_crema = serializers.ChoiceField(
        choices=CorridaDescremacion.DestinoRama.choices,
        default=CorridaDescremacion.DestinoRama.PENDIENTE,
    )

    def validate(self, attrs):
        if not attrs.get("plan_confirmado"):
            raise serializers.ValidationError({
                "plan_confirmado": "El operador debe confirmar la sugerencia."
            })
        if attrs["litros_descremada_plan"] + attrs["litros_crema_plan"] > attrs["litros_entrada"]:
            raise serializers.ValidationError(
                "Los volúmenes planificados superan los litros de entrada."
            )
        return attrs


class SugerirDescremacionSerializer(serializers.Serializer):
    analisis_entrada = serializers.IntegerField(min_value=1)
    litros_entrada = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=1,
    )
    producto_descremada = serializers.IntegerField(min_value=1)
    producto_crema = serializers.IntegerField(min_value=1)


class CierreSecadoSerializer(serializers.Serializer):
    kg_alimentacion = serializers.DecimalField(max_digits=14, decimal_places=3)
    solidos_entrada_pct = serializers.DecimalField(
        max_digits=6, decimal_places=2,
        min_value=Decimal("0.01"), max_value=Decimal("100"),
    )
    kg_polvo = serializers.DecimalField(max_digits=14, decimal_places=3)
    kg_finos = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=0, required=False, default=0
    )
    kg_merma = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=0, required=False, default=0
    )
    controles = serializers.JSONField(required=False, default=dict)


class IncorporarReworkSerializer(serializers.Serializer):
    lote = serializers.IntegerField(min_value=1)
    unidad_rework = serializers.IntegerField(min_value=1, required=False)
    cantidad = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0.001")
    )
    motivo = serializers.CharField(max_length=250, allow_blank=False)
    operacion_id = serializers.UUIDField(required=False)


class CorridaCondensacionSerializer(serializers.ModelSerializer):
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    equipo_nombre = serializers.CharField(source="ejecucion.equipo.nombre", read_only=True)
    equipo_id = serializers.IntegerField(source="ejecucion.equipo_id", read_only=True)
    silo_origen_codigo = serializers.CharField(source="silo_origen.codigo", read_only=True)
    silo_destino_codigo = serializers.CharField(source="silo_destino.codigo", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        model = CorridaCondensacion
        fields = "__all__"
        read_only_fields = [
            "estado", "operacion_id", "iniciada_por", "iniciada_en",
            "finalizada_por", "finalizada_en", "litros_precondensado",
            "flujo_promedio", "densidad_salida", "solidos_salida",
            "temperatura_salida", "vacio_promedio", "presion_promedio",
            "motivo_cancelacion",
        ]

    def validate(self, attrs):
        candidato = CorridaCondensacion(
            **{
                **{
                    campo: getattr(self.instance, campo, None)
                    for campo in (
                        "ejecucion", "orden", "lote", "silo_origen", "silo_destino",
                        "litros_entrada",
                    )
                },
                **attrs,
            }
        )
        candidato.clean()
        return attrs


class CierreDescremacionSerializer(serializers.Serializer):
    litros_descremada = serializers.DecimalField(max_digits=14, decimal_places=2)
    grasa_descremada = serializers.DecimalField(max_digits=6, decimal_places=3)
    litros_crema = serializers.DecimalField(max_digits=14, decimal_places=2)
    grasa_crema = serializers.DecimalField(max_digits=6, decimal_places=3)
    controles = serializers.JSONField(required=False, default=dict)


class CorridaDescremacionSerializer(serializers.ModelSerializer):
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    equipo_nombre = serializers.CharField(source="ejecucion.equipo.nombre", read_only=True)
    silo_entera_codigo = serializers.CharField(source="silo_entera.codigo", read_only=True)
    silo_descremada_codigo = serializers.CharField(source="silo_descremada.codigo", read_only=True)
    estanque_crema_codigo = serializers.CharField(source="estanque_crema.codigo", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    iniciada_por_nombre = serializers.CharField(source="iniciada_por.get_full_name", read_only=True)
    finalizada_por_nombre = serializers.CharField(source="finalizada_por.get_full_name", read_only=True)
    producto_descremada_nombre = serializers.CharField(source="producto_descremada.nombre", read_only=True)
    producto_crema_nombre = serializers.CharField(source="producto_crema.nombre", read_only=True)
    iniciada_por_nombre = serializers.CharField(source="iniciada_por.get_full_name", read_only=True)
    finalizada_por_nombre = serializers.CharField(source="finalizada_por.get_full_name", read_only=True)

    class Meta:
        model = CorridaDescremacion
        fields = "__all__"
        read_only_fields = [
            "estado", "operacion_id", "litros_descremada", "grasa_descremada",
            "litros_crema", "grasa_crema", "controles", "iniciada_por",
            "iniciada_en", "finalizada_por", "finalizada_en", "motivo_anulacion",
            "litros_descremada_plan", "litros_crema_plan", "fuente_plan",
            "plan_confirmado_por", "plan_confirmado_en",
        ]

    def validate(self, attrs):
        candidato = CorridaDescremacion(**{
            **{
                campo: getattr(self.instance, campo, None)
                for campo in (
                    "ejecucion", "orden", "producto_descremada", "producto_crema",
                    "silo_entera", "analisis_entrada",
                    "litros_entrada", "grasa_entrada", "sng_entrada",
                    "silo_descremada", "estanque_crema",
                )
            },
            **attrs,
        })
        if self.instance is None:
            faltantes = [
                campo for campo in ("producto_descremada", "producto_crema")
                if attrs.get(campo) is None
            ]
            if faltantes:
                raise serializers.ValidationError({
                    campo: "Selecciona el producto intermedio generado."
                    for campo in faltantes
                })
        candidato.clean()
        return attrs

    def create(self, validated_data):
        from .servicios import crear_corrida_descremacion

        try:
            return crear_corrida_descremacion(datos=validated_data)
        except DjangoValidationError as error:
            _error_de_dominio(error)


class CierreMantequillaSerializer(serializers.Serializer):
    kg_mantequilla = serializers.DecimalField(max_digits=14, decimal_places=3)
    kg_suero = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, default=0)
    kg_merma = serializers.DecimalField(max_digits=14, decimal_places=3, required=False, default=0)
    controles = serializers.JSONField(required=False, default=dict)


class CorridaMantequillaSerializer(serializers.ModelSerializer):
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    crema_codigo = serializers.CharField(source="lote_crema.codigo_lote", read_only=True)
    mantequilla_codigo = serializers.CharField(source="lote_mantequilla.codigo_lote", read_only=True)
    equipo_nombre = serializers.CharField(source="ejecucion.equipo.nombre", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    iniciada_por_nombre = serializers.CharField(source="iniciada_por.get_full_name", read_only=True)
    finalizada_por_nombre = serializers.CharField(source="finalizada_por.get_full_name", read_only=True)

    class Meta:
        model = CorridaMantequilla
        fields = "__all__"
        read_only_fields = [
            "estado", "kg_mantequilla", "kg_suero", "kg_merma", "controles",
            "iniciada_por", "iniciada_en", "finalizada_por", "finalizada_en",
        ]

    def validate(self, attrs):
        candidato = CorridaMantequilla(**{
            **{
                campo: getattr(self.instance, campo, None)
                for campo in (
                    "ejecucion", "orden", "lote_crema", "lote_mantequilla",
                    "lote_suero", "kg_crema",
                )
            },
            **attrs,
        })
        candidato.clean()
        return attrs


class ProcesoSerializer(serializers.ModelSerializer):
    etapas = serializers.SerializerMethodField()

    class Meta:
        model = Proceso
        fields = "__all__"

    @staticmethod
    def get_etapas(proceso):
        return [
            {
                "id": etapa.pk,
                "nombre": etapa.nombre,
                "tipo": etapa.tipo,
                "activa": etapa.activa,
                "orden": etapa.orden,
            }
            for etapa in proceso.etapas.all()
        ]


class EtapaProcesoSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = EtapaProceso
        fields = "__all__"


class RutaProductoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    proceso_nombre = serializers.CharField(source="proceso.nombre", read_only=True)
    etapas = EtapaProcesoSerializer(source="proceso.etapas", many=True, read_only=True)

    class Meta:
        model = RutaProducto
        exclude = ["sucursal"]

    def validate(self, attrs):
        candidato = RutaProducto(
            **{
                **{
                    campo: getattr(self.instance, campo, None)
                    for campo in ("sucursal", "producto", "proceso")
                },
                **attrs,
            }
        )
        candidato.clean()
        return attrs


class EntradaProcesoSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)
    salida_origen_codigo = serializers.CharField(
        source="salida_origen.ejecucion.codigo", read_only=True
    )

    class Meta:
        model = EntradaProceso
        fields = "__all__"

    def validate(self, attrs):
        instancia = EntradaProceso(**attrs)
        instancia.clean()
        return attrs


class CorridaSecadoSerializer(serializers.ModelSerializer):
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    estado = serializers.CharField(source="ejecucion.estado", read_only=True)
    estado_etiqueta = serializers.CharField(
        source="ejecucion.get_estado_display", read_only=True
    )
    equipo_id = serializers.IntegerField(source="ejecucion.equipo_id", read_only=True)
    equipo_nombre = serializers.CharField(source="ejecucion.equipo.nombre", read_only=True)
    iniciada_en = serializers.DateTimeField(source="ejecucion.inicio", read_only=True)
    requiere_calidad = serializers.BooleanField(
        source="ejecucion.etapa.requiere_calidad", read_only=True
    )
    estado_calidad = serializers.SerializerMethodField()
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    producto_nombre = serializers.CharField(source="lote.producto.nombre", read_only=True)
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    rendimiento_recuperacion_pct = serializers.DecimalField(
        max_digits=7, decimal_places=2, read_only=True
    )

    def get_estado_calidad(self, corrida):
        if not corrida.ejecucion.etapa.requiere_calidad:
            return "no_requerida"
        salida = next(
            (
                salida for salida in corrida.ejecucion.salidas.all()
                if salida.lote_id == corrida.lote_id
                and salida.naturaleza == SalidaProceso.Naturaleza.PRINCIPAL
            ),
            None,
        )
        decision = getattr(salida, "liberacion_calidad", None) if salida else None
        return decision.estado if decision else "pendiente"

    class Meta:
        model = CorridaSecado
        fields = "__all__"
        read_only_fields = [
            "ejecucion", "orden", "lote", "kg_alimentacion",
            "solidos_entrada_pct", "kg_polvo", "kg_finos", "kg_merma",
            "controles", "operacion_id", "finalizada_por", "finalizada_en",
        ]

    def create(self, validated_data):
        from .servicios import crear_entrada_proceso

        try:
            return crear_entrada_proceso(datos=validated_data)
        except DjangoValidationError as error:
            _error_de_dominio(error)


class SalidaProcesoSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)

    class Meta:
        model = SalidaProceso
        fields = "__all__"

    def validate(self, attrs):
        instancia = SalidaProceso(**attrs)
        instancia.clean()
        return attrs

    def create(self, validated_data):
        from .servicios import crear_salida_proceso

        try:
            return crear_salida_proceso(datos=validated_data)
        except DjangoValidationError as error:
            _error_de_dominio(error)


class EventoProcesoSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.CharField(source="usuario.username", read_only=True)

    class Meta:
        model = EventoProceso
        fields = "__all__"


class EjecucionProcesoSerializer(serializers.ModelSerializer):
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    etapa_nombre = serializers.CharField(source="etapa.nombre", read_only=True)
    etapa_tipo = serializers.CharField(source="etapa.tipo", read_only=True)
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    vale_codigo = serializers.CharField(source="vale.codigo", read_only=True)
    lote_codigo = serializers.CharField(
        source="lote_produccion.codigo_lote", read_only=True
    )
    producto_nombre = serializers.CharField(
        source="lote_produccion.producto.nombre", read_only=True
    )
    entradas = EntradaProcesoSerializer(many=True, read_only=True)
    salidas = SalidaProcesoSerializer(many=True, read_only=True)
    eventos = EventoProcesoSerializer(many=True, read_only=True)
    acciones_permitidas = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = EjecucionProceso
        exclude = ["sucursal"]
        read_only_fields = ["estado", "version", "inicio", "termino", "responsable"]

    def get_acciones_permitidas(self, ejecucion):
        return sorted(EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set()))

    def create(self, validated_data):
        from .servicios import crear_ejecucion_proceso

        try:
            return crear_ejecucion_proceso(datos=validated_data)
        except DjangoValidationError as error:
            _error_de_dominio(error)

    def validate(self, attrs):
        if self.instance is not None and "etapa" in attrs:
            raise serializers.ValidationError({
                "etapa": "La etapa de una ejecucion existente no se puede reemplazar."
            })
        if (
            self.instance is not None
            and "equipo" in attrs
            and self.instance.estado != EjecucionProceso.Estado.BORRADOR
        ):
            raise serializers.ValidationError({
                "equipo": "El equipo solo puede cambiar mientras la ejecucion esta en borrador."
            })
        return attrs

    def get_balance(self, ejecucion):
        """
        Cuánto entró y cuánto salió, **por unidad**.

        Se agrupa por unidad porque una evaporación entra en litros y sale en
        kilos: sumarlo todo junto daría un número que no significa nada.
        `convertible` marca las unidades que aparecen en los dos lados, que son
        las únicas donde la comparación tiene sentido —y las únicas donde el
        modelo impide que salga más de lo que entró—.
        """
        entradas: dict[str, float] = {}
        salidas: dict[str, float] = {}

        for entrada in ejecucion.entradas.all():
            clave = (entrada.unidad or "").strip().lower()
            entradas[clave] = entradas.get(clave, 0) + float(entrada.cantidad)

        for salida in ejecucion.salidas.all():
            clave = (salida.unidad or "").strip().lower()
            salidas[clave] = salidas.get(clave, 0) + float(salida.cantidad)

        return [
            {
                "unidad": unidad,
                "entro": entradas.get(unidad, 0),
                "salio": salidas.get(unidad, 0),
                "comparable": unidad in entradas and unidad in salidas,
            }
            for unidad in sorted(set(entradas) | set(salidas))
        ]
