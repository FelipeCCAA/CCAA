from rest_framework import serializers

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion


class CargaModuloSerializer(serializers.ModelSerializer):
    # La idempotencia la resuelve el servicio: reenviar el mismo código
    # devuelve la carga existente en vez de fallar por la validación única.
    codigo = serializers.CharField(validators=[])
    recoleccion = serializers.PrimaryKeyRelatedField(read_only=True)
    estanque_origen = serializers.CharField(required=False, allow_blank=True)
    vehiculo = serializers.IntegerField(
        source="recoleccion.parada.ruta.vehiculo_id", read_only=True
    )
    vehiculo_placa = serializers.CharField(
        source="recoleccion.parada.ruta.vehiculo.placa", read_only=True
    )
    proveedor = serializers.CharField(source="recoleccion.parada.proveedor", read_only=True)
    predio = serializers.CharField(source="recoleccion.parada.predio", read_only=True)
    recepcionada = serializers.SerializerMethodField()

    class Meta:
        model = CargaModulo
        fields = [
            "id", "codigo", "recoleccion", "modulo", "estanque_origen", "litros",
            "cargada_en", "vehiculo", "vehiculo_placa", "proveedor", "predio",
            "recepcionada",
        ]
        read_only_fields = ["cargada_en"]

    def get_recepcionada(self, carga):
        return carga.modulos_recepcion.exists()


class RecoleccionSerializer(serializers.ModelSerializer):
    cargas = CargaModuloSerializer(many=True, read_only=True)
    proveedor = serializers.CharField(source="parada.proveedor", read_only=True)
    predio = serializers.CharField(source="parada.predio", read_only=True)

    class Meta:
        model = Recoleccion
        fields = [
            "id", "idempotencia", "parada", "proveedor", "predio", "fecha_hora",
            "litros_medidos", "temperatura", "alcohol", "codigo_muestra", "estado",
            "operador", "observacion", "creada_en", "cargas",
        ]
        read_only_fields = ["estado", "operador", "creada_en"]

    def validate(self, attrs):
        parada = attrs.get("parada", getattr(self.instance, "parada", None))
        if parada and parada.ruta.estado not in {
            RutaRecoleccion.Estado.PROGRAMADA,
            RutaRecoleccion.Estado.EN_CURSO,
        }:
            raise serializers.ValidationError(
                {"parada": "La ruta ya está cerrada o cancelada."}
            )
        if self.instance and self.instance.estado in {
            Recoleccion.Estado.CARGADA,
            Recoleccion.Estado.RECHAZADA,
        }:
            raise serializers.ValidationError("Una recolección finalizada no se edita.")
        instancia = Recoleccion(**attrs)
        instancia.clean()
        return attrs


class ParadaRutaSerializer(serializers.ModelSerializer):
    recoleccion_id = serializers.IntegerField(source="recoleccion.id", read_only=True)

    class Meta:
        model = ParadaRuta
        fields = [
            "id", "ruta", "orden", "proveedor", "predio", "sala", "estado",
            "llegada", "salida", "observacion", "recoleccion_id",
        ]
        read_only_fields = ["estado", "llegada", "salida"]

    def validate(self, attrs):
        ruta = attrs.get("ruta", getattr(self.instance, "ruta", None))
        if ruta and ruta.estado not in {
            RutaRecoleccion.Estado.PROGRAMADA,
            RutaRecoleccion.Estado.EN_CURSO,
        }:
            raise serializers.ValidationError({"ruta": "La ruta ya está finalizada."})
        return attrs


class RutaRecoleccionSerializer(serializers.ModelSerializer):
    paradas = ParadaRutaSerializer(many=True, read_only=True)
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    conductor_nombre = serializers.CharField(source="conductor.get_full_name", read_only=True)

    class Meta:
        model = RutaRecoleccion
        fields = [
            "id", "codigo", "fecha", "conductor", "conductor_nombre", "vehiculo",
            "vehiculo_placa", "estado", "observacion", "creada_por", "creada_en",
            "actualizada_en", "paradas",
        ]
        read_only_fields = ["estado", "creada_por", "creada_en", "actualizada_en"]

    def validate(self, attrs):
        if self.instance and self.instance.estado in {
            RutaRecoleccion.Estado.CERRADA,
            RutaRecoleccion.Estado.CANCELADA,
        }:
            raise serializers.ValidationError("Una ruta finalizada no se edita.")
        return attrs
