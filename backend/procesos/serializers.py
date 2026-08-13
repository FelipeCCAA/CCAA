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
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)

    class Meta:
        model = EntradaProceso
        fields = "__all__"

    def validate(self, attrs):
        instancia = EntradaProceso(**attrs)
        instancia.clean()
        return attrs


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
        fields = "__all__"
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
