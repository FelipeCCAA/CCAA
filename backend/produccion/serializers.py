from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from maestros.catalogos import CLAVES_PARAMETROS

from . import dominio
from .models import Analisis, Lote


class AnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = Analisis
        fields = [
            "id",
            "lote",
            "fecha",
            "muestra",
            "valores",
            "especificacion",
            "observacion",
        ]

    def validate_valores(self, valores):
        if not isinstance(valores, dict):
            raise serializers.ValidationError("Debe ser un objeto de parámetros.")

        desconocidos = set(valores) - CLAVES_PARAMETROS
        if desconocidos:
            raise serializers.ValidationError(
                f"Parámetros no reconocidos: {', '.join(sorted(desconocidos))}"
            )

        for parametro, valor in valores.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise serializers.ValidationError(
                    f"El valor de '{parametro}' debe ser numérico."
                )

        return valores


class LoteSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    mandante_nombre = serializers.CharField(
        source="producto.mandante.nombre", read_only=True
    )
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    # El resultado de calidad se calcula, nunca se lee de la base
    # (MODELO_DATOS.md §2.2).
    calidad = serializers.SerializerMethodField()

    class Meta:
        model = Lote
        fields = [
            "id",
            "codigo_lote",
            "op",
            "producto",
            "producto_nombre",
            "mandante_nombre",
            "fecha",
            "linea",
            "turno",
            "kg_producidos",
            "bultos",
            "hora_inicio",
            "hora_termino",
            "vencimiento",
            "estado",
            "estado_etiqueta",
            "observacion",
            "calidad",
        ]
        validators = [
            # El mensaje por defecto de DRF viene en inglés y lo lee quien
            # carga lotes en planta. El código de lote SÍ se repite entre
            # productos y días; lo que no puede repetirse es la combinación.
            UniqueTogetherValidator(
                queryset=Lote.objects.all(),
                fields=["codigo_lote", "producto", "fecha"],
                message=(
                    "Ya existe un lote con ese código para el mismo producto "
                    "y la misma fecha."
                ),
            )
        ]

    def get_calidad(self, lote):
        """
        Evalúa el lote contra la especificación vigente en su fecha.

        Los análisis y las especificaciones llegan por el contexto, cargados
        una sola vez en la vista. Consultarlos aquí por cada lote convertiría
        un listado de 50 lotes en más de 100 consultas.
        """
        especificaciones = self.context.get("especificaciones")

        if especificaciones is None:
            from maestros.models import Especificacion

            especificaciones = list(Especificacion.objects.all())

        resultado = dominio.resultado_calidad_lote(
            lote,
            list(lote.analisis.all()),
            especificaciones,
        )

        return {
            "resultado": resultado.resultado,
            "etiqueta": resultado.etiqueta,
            "evaluados": resultado.evaluados,
            "desviaciones": resultado.desviaciones,
            "especificacion_id": (
                resultado.especificacion.id if resultado.especificacion else None
            ),
        }


class LoteDetalleSerializer(LoteSerializer):
    """El lote con sus análisis, para la ficha de un lote concreto."""

    analisis = AnalisisSerializer(many=True, read_only=True)

    class Meta(LoteSerializer.Meta):
        fields = LoteSerializer.Meta.fields + ["analisis"]
