from rest_framework import serializers

from .models import (
    EjecucionProceso, EntradaProceso, EtapaProceso, EventoProceso, Proceso,
    SalidaProceso,
)


class ProcesoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proceso
        fields = "__all__"


class EtapaProcesoSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = EtapaProceso
        fields = "__all__"


class EntradaProcesoSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)

    class Meta:
        model = EntradaProceso
        fields = "__all__"

    def validate(self, attrs):
        instancia = EntradaProceso(**attrs)
        instancia.clean()
        return attrs


class SalidaProcesoSerializer(serializers.ModelSerializer):
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)

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
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    entradas = EntradaProcesoSerializer(many=True, read_only=True)
    salidas = SalidaProcesoSerializer(many=True, read_only=True)
    eventos = EventoProcesoSerializer(many=True, read_only=True)
    acciones_permitidas = serializers.SerializerMethodField()

    class Meta:
        model = EjecucionProceso
        fields = "__all__"
        read_only_fields = ["estado", "version", "inicio", "termino", "responsable"]

    def get_acciones_permitidas(self, ejecucion):
        return sorted(EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set()))
