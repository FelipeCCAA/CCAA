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
    # De qué lote salió, cuando bodega lo respalda. Es lo que permite responder
    # «qué empaquetadura se le puso a esta máquina» sin ir a buscarlo.
    lote_codigo = serializers.CharField(
        source="entrega.lote.codigo", read_only=True, allow_null=True
    )
    # Se calcula desde `entrega`, no se guarda: un booleano aparte se
    # desincroniza en cuanto alguien corrige el enlace.
    respaldado = serializers.BooleanField(read_only=True)

    class Meta:
        model = RepuestoUtilizado
        fields = "__all__"

    def validate(self, attrs):
        """
        El modelo valida y aquí se le llama.

        DRF no ejecuta `Model.clean()` por su cuenta, así que sin esto las
        reglas del modelo —no imputar más de lo que bodega entregó, no mezclar
        el insumo con el de otra entrega— quedaban escritas y sin efecto.
        """
        instancia = self.instance or RepuestoUtilizado()

        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)

        instancia.clean()

        return attrs


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
