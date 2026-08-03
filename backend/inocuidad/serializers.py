from rest_framework import serializers

from .models import MonitoreoPPRO, PproLectura


class PproLecturaSerializer(serializers.ModelSerializer):
    resultado_etiqueta = serializers.CharField(
        source="get_resultado_display", read_only=True
    )

    class Meta:
        model = PproLectura
        fields = ["id", "monitoreo", "hora", "resultado", "resultado_etiqueta", "detalle"]


class MonitoreoPPROSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    # `allow_null` en los dos: el detector de metales no cuelga de una máquina.
    equipo_etiqueta = serializers.CharField(
        source="equipo.nombre", read_only=True, allow_null=True
    )
    equipo_codigo = serializers.CharField(
        source="equipo.codigo", read_only=True, allow_null=True
    )
    lecturas = PproLecturaSerializer(many=True, read_only=True)

    # Se calculan, no se guardan: un veredicto persistido se desincroniza en
    # cuanto alguien corrige una lectura (MODELO_DATOS.md §2.2).
    tiene_no_ok = serializers.BooleanField(read_only=True)
    resuelto = serializers.BooleanField(read_only=True)

    class Meta:
        model = MonitoreoPPRO
        fields = [
            "id",
            "lote",
            "lote_codigo",
            "tipo",
            "tipo_etiqueta",
            "equipo",
            "equipo_etiqueta",
            "equipo_codigo",
            "turno",
            "fecha",
            "accion_correctiva",
            "operador",
            "lecturas",
            "tiene_no_ok",
            "resuelto",
        ]
        # `turno` y `equipo` son opcionales en el modelo pero entran en la
        # clave de unicidad, y DRF exige **todos** los campos de una clave
        # única aunque el modelo los declare `blank=True`. Con `required=False`
        # a secas el validador los vuelve a pedir; hace falta el valor por
        # defecto para que la pantalla pueda omitirlos.
        extra_kwargs = {
            "equipo": {"required": False, "default": None},
            "turno": {"required": False, "default": ""},
        }
