from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers

from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla,
    EjecucionProceso, EntradaProceso,
    EtapaProceso, EventoProceso, Proceso,
    RutaProducto, SalidaProceso,
)


class CierreCondensacionSerializer(serializers.Serializer):
    litros_precondensado = serializers.DecimalField(max_digits=14, decimal_places=2)
    flujo_promedio = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    densidad_salida = serializers.DecimalField(max_digits=10, decimal_places=3, required=False)
    solidos_salida = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    temperatura_salida = serializers.DecimalField(max_digits=6, decimal_places=2, required=False)
    vacio_promedio = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)
    presion_promedio = serializers.DecimalField(max_digits=8, decimal_places=2, required=False)


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

    class Meta:
        model = CorridaDescremacion
        fields = "__all__"
        read_only_fields = [
            "estado", "operacion_id", "litros_descremada", "grasa_descremada",
            "litros_crema", "grasa_crema", "controles", "iniciada_por",
            "iniciada_en", "finalizada_por", "finalizada_en", "motivo_anulacion",
        ]

    def validate(self, attrs):
        candidato = CorridaDescremacion(**{
            **{
                campo: getattr(self.instance, campo, None)
                for campo in (
                    "ejecucion", "orden", "silo_entera", "analisis_entrada",
                    "litros_entrada", "grasa_entrada", "sng_entrada",
                    "silo_descremada", "estanque_crema",
                )
            },
            **attrs,
        })
        candidato.clean()
        return attrs


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
    class Meta:
        model = Proceso
        fields = "__all__"


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

    @transaction.atomic
    def create(self, validated_data):
        salida = validated_data.get("salida_origen")
        if salida is not None:
            salida = SalidaProceso.objects.select_for_update(of=("self",)).select_related(
                "ejecucion__etapa", "silo"
            ).get(pk=salida.pk)
            usado = salida.usos_como_origen.aggregate(total=Sum("cantidad"))["total"] or 0
            cantidad = validated_data["cantidad"]
            if usado + cantidad > salida.cantidad:
                raise serializers.ValidationError({
                    "cantidad": (
                        f"La salida tiene {salida.cantidad - usado} {salida.unidad} disponibles."
                    )
                })
            validated_data["salida_origen"] = salida
            candidato = EntradaProceso(**validated_data)
            candidato.clean()
        return super().create(validated_data)


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
