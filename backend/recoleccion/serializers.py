from rest_framework import serializers

from .models import (
    CargaPredio, Conductor, Modulo, Predio, ProveedorLeche, Recoleccion,
)


class ProveedorLecheSerializer(serializers.ModelSerializer):
    predios = serializers.IntegerField(source="predios.count", read_only=True)

    class Meta:
        model = ProveedorLeche
        fields = "__all__"

    def validate(self, datos):
        instancia = self.instance or ProveedorLeche()

        for campo, valor in datos.items():
            setattr(instancia, campo, valor)

        instancia.clean()

        return datos


class PredioSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(
        source="proveedor.nombre", read_only=True
    )
    # Que el proveedor esté bloqueado se ve en el predio, que es donde el
    # conductor lo mira antes de bajarse del camión.
    proveedor_bloqueado = serializers.BooleanField(
        source="proveedor.bloqueado", read_only=True
    )

    class Meta:
        model = Predio
        fields = "__all__"


class ConductorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conductor
        fields = "__all__"


class ModuloSerializer(serializers.ModelSerializer):
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)

    class Meta:
        model = Modulo
        fields = "__all__"


class CargaPredioSerializer(serializers.ModelSerializer):
    predio_nombre = serializers.CharField(source="predio.nombre", read_only=True)
    proveedor_nombre = serializers.CharField(
        source="predio.proveedor.nombre", read_only=True
    )
    modulo_numero = serializers.CharField(
        source="modulo.numero", read_only=True, allow_null=True
    )
    alcohol_etiqueta = serializers.CharField(
        source="get_alcohol_display", read_only=True
    )

    class Meta:
        model = CargaPredio
        fields = "__all__"

    def validate(self, datos):
        """
        El modelo valida y aquí se le llama.

        DRF no ejecuta `Model.clean()` por su cuenta, así que sin esto la regla
        que importa —alcohol positivo, no se carga— quedaría escrita y sin
        efecto.
        """
        instancia = self.instance or CargaPredio()

        for campo, valor in datos.items():
            setattr(instancia, campo, valor)

        instancia.clean()

        return datos


class RecoleccionSerializer(serializers.ModelSerializer):
    conductor_nombre = serializers.CharField(
        source="conductor.nombre", read_only=True
    )
    camion_placa = serializers.CharField(source="camion.placa", read_only=True)
    carro_placa = serializers.CharField(
        source="carro.placa", read_only=True, allow_null=True
    )
    estado_etiqueta = serializers.CharField(
        source="get_estado_display", read_only=True
    )
    cargas = CargaPredioSerializer(many=True, read_only=True)

    # Los dos se calculan del detalle. Un total guardado se desincroniza en
    # cuanto alguien corrige una carga.
    litros_cargados = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    predios_rechazados = serializers.ListField(read_only=True)

    class Meta:
        model = Recoleccion
        fields = "__all__"
        read_only_fields = ["registrada_por", "creada_en"]

    def validate(self, datos):
        instancia = self.instance or Recoleccion()

        for campo, valor in datos.items():
            setattr(instancia, campo, valor)

        instancia.clean()

        return datos
