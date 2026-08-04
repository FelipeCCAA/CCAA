from rest_framework import serializers

from .models import FallaEquipo, OrdenTrabajo, PlanPreventivo, RepuestoUtilizado


class PlanPreventivoSerializer(serializers.ModelSerializer):
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)

    class Meta:
        model = PlanPreventivo
        fields = "__all__"


class FallaEquipoSerializer(serializers.ModelSerializer):
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)

    class Meta:
        model = FallaEquipo
        fields = "__all__"
        read_only_fields = ["reportada_por"]


class RepuestoUtilizadoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)

    class Meta:
        model = RepuestoUtilizado
        fields = "__all__"


class OrdenTrabajoSerializer(serializers.ModelSerializer):
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    responsable_nombre = serializers.CharField(source="responsable.username", read_only=True)
    fallas = FallaEquipoSerializer(many=True, read_only=True)
    repuestos = RepuestoUtilizadoSerializer(many=True, read_only=True)
    acciones_permitidas = serializers.SerializerMethodField()

    class Meta:
        model = OrdenTrabajo
        fields = "__all__"
        read_only_fields = ["estado", "creada_por", "inicio", "termino"]

    def get_acciones_permitidas(self, orden):
        return sorted(OrdenTrabajo.TRANSICIONES.get(orden.estado, set()))
