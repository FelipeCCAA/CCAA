from rest_framework import serializers

from . import dominio
from .models import (
    CONTROLES_DECLARADOS,
    CONTROLES_NUMERICOS,
    VALORES_ADMITIDOS,
    MovimientoSilo,
    Recepcion,
)


class RecepcionSerializer(serializers.ModelSerializer):
    vehiculo_placa = serializers.CharField(source="vehiculo.placa", read_only=True)
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)
    operador_nombre = serializers.CharField(
        source="operador.get_full_name", read_only=True
    )
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    muestreado_por_nombre = serializers.CharField(
        source="muestreado_por.get_full_name", read_only=True
    )
    calidad_por_nombre = serializers.CharField(
        source="calidad_por.get_full_name", read_only=True
    )
    silo_asignado_por_nombre = serializers.CharField(
        source="silo_asignado_por.get_full_name", read_only=True
    )

    # El veredicto de los controles se calcula, no se guarda: al corregir un
    # límite, todas las recepciones quedan reevaluadas.
    evaluacion = serializers.SerializerMethodField()

    class Meta:
        model = Recepcion
        fields = [
            "id",
            "fecha",
            "hora",
            "guia",
            "vehiculo",
            "vehiculo_placa",
            "modulo",
            "procedencia",
            "tipo_leche",
            "litros",
            "silo",
            "silo_codigo",
            "operador",
            "operador_nombre",
            "turno",
            "controles",
            "estado",
            "estado_etiqueta",
            "motivo",
            "observacion",
            "codigo_muestra",
            "muestreado_por",
            "muestreado_por_nombre",
            "muestreado_en",
            "calidad_por",
            "calidad_por_nombre",
            "calidad_en",
            "silo_asignado_por",
            "silo_asignado_por_nombre",
            "silo_asignado_en",
            "evaluacion",
        ]
        read_only_fields = [
            "silo",
            "operador",
            "controles",
            "estado",
            "motivo",
            "codigo_muestra",
            "muestreado_por",
            "muestreado_en",
            "calidad_por",
            "calidad_en",
            "silo_asignado_por",
            "silo_asignado_en",
        ]

    def get_evaluacion(self, recepcion):
        evaluacion = dominio.evaluar_recepcion(recepcion.controles)

        return {
            "conforme": evaluacion.conforme,
            "estado_sugerido": evaluacion.estado,
            "motivos": evaluacion.motivos,
            # Controles decisivos sin informar. Con alguno pendiente no se
            # puede liberar: no es que esté conforme, es que nadie lo midió.
            "faltantes": evaluacion.faltantes,
            "analizada": evaluacion.analizada,
        }

    def validate_controles(self, controles):
        if not isinstance(controles, dict):
            raise serializers.ValidationError("Debe ser un objeto de controles.")

        desconocidos = set(controles) - CONTROLES_DECLARADOS
        if desconocidos:
            raise serializers.ValidationError(
                f"Controles no reconocidos: {', '.join(sorted(desconocidos))}"
            )

        for clave, valor in controles.items():
            if valor in (None, ""):
                continue

            if clave in CONTROLES_NUMERICOS and not isinstance(valor, (int, float)):
                raise serializers.ValidationError(
                    f"El valor de '{clave}' debe ser numérico."
                )

            admitidos = VALORES_ADMITIDOS.get(clave)
            if admitidos and valor not in admitidos:
                raise serializers.ValidationError(
                    f"'{clave}' admite {' o '.join(sorted(admitidos))}, no '{valor}'."
                )

        return controles

    def validate(self, datos):
        estado = datos.get("estado", getattr(self.instance, "estado", None))
        motivo = datos.get("motivo", getattr(self.instance, "motivo", "") or "")

        if estado == Recepcion.Estado.RETENIDA and not motivo.strip():
            raise serializers.ValidationError(
                {"motivo": "Una recepción retenida debe indicar el motivo."}
            )

        return datos


class MovimientoSiloSerializer(serializers.ModelSerializer):
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = MovimientoSilo
        validators = []
        fields = [
            "id",
            "silo",
            "silo_codigo",
            "tipo",
            "tipo_etiqueta",
            "litros",
            "fecha_hora",
            "origen_tipo",
            "origen_id",
            "motivo",
        ]

    def validate(self, datos):
        tipo = datos.get("tipo", getattr(self.instance, "tipo", None))
        litros = datos.get("litros", getattr(self.instance, "litros", None))
        motivo = datos.get("motivo", getattr(self.instance, "motivo", "") or "")

        if tipo != MovimientoSilo.Tipo.AJUSTE and litros is not None and litros < 0:
            raise serializers.ValidationError(
                {"litros": "Solo los ajustes pueden ser negativos."}
            )

        if tipo == MovimientoSilo.Tipo.AJUSTE and not motivo.strip():
            raise serializers.ValidationError(
                {
                    "motivo": (
                        "Un ajuste debe indicar el motivo: es lo que lo hace "
                        "auditable."
                    )
                }
            )

        return datos
