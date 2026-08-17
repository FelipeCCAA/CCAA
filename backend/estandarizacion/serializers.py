from rest_framework import serializers
from maestros.models import Silo

from .models import ValeEstandarizacion


class ValeEstandarizacionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    silo_entera_codigo = serializers.CharField(
        source="silo_entera.codigo", read_only=True
    )
    # `allow_null` y no `default`: sin él la clave desaparece del JSON cuando el
    # silo es nulo, y una clave ausente y una nula se leen distinto en el
    # frontend.
    silo_descremada_codigo = serializers.CharField(
        source="silo_descremada.codigo", read_only=True, allow_null=True
    )
    silo_destino_codigo = serializers.CharField(
        source="silo_destino.codigo", read_only=True
    )
    responsable_nombre = serializers.CharField(
        source="responsable.get_full_name", read_only=True, allow_null=True
    )

    # Todo lo derivado sale calculado y de solo lectura. Un RC real escribible
    # sería un número que contradice a los dos que lo componen.
    rc_real = serializers.FloatField(read_only=True)
    minutos_agitando = serializers.FloatField(read_only=True)
    # Motivos y no un booleano: un `False` no le dice al operador qué pasó.
    avisos = serializers.ListField(
        source="avisos_de_muestreo",
        child=serializers.CharField(),
        read_only=True,
    )
    evaluacion = serializers.SerializerMethodField()

    class Meta:
        model = ValeEstandarizacion
        fields = [
            "id", "codigo", "fecha",
            "producto", "producto_nombre", "rc_objetivo", "volumen",
            "silo_entera", "silo_entera_codigo",
            "silo_descremada", "silo_descremada_codigo",
            "silo_destino", "silo_destino_codigo",
            "entera_grasa", "entera_sng", "descremada_grasa", "descremada_sng",
            "litros_entera", "litros_descremada",
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "rc_real", "minutos_agitando", "avisos", "evaluacion",
            "observaciones", "responsable", "responsable_nombre", "creado_en",
        ]
        # El estado lo mueven las acciones del ciclo, no un PATCH: liberar
        # exige que el RC cumpla, y con un campo escribible eso se salta.
        read_only_fields = [
            "estado", "agitacion_desde", "muestreado_en",
            "grasa_real", "sng_real",
            "responsable", "creado_en",
        ]

    def get_evaluacion(self, vale):
        evaluacion = vale.evaluacion()

        if evaluacion is None:
            return None

        return {
            "cumple": evaluacion.cumple,
            "rc_real": evaluacion.rc_real,
            "desvio": evaluacion.desvio,
            "agregar": evaluacion.agregar,
            "motivo": evaluacion.motivo,
        }

    def validate(self, attrs):
        # DRF no llama a `Model.clean()`: hay que invocarlo a mano o las reglas
        # del modelo solo protegen al admin. Se arma un vale desechable con los
        # tres silos —lo único que `clean` mira— para no ensuciar la instancia
        # real cuando la validación falla.
        silos = {
            campo: attrs.get(campo, getattr(self.instance, campo, None))
            for campo in ("silo_entera", "silo_descremada", "silo_destino")
        }
        ValeEstandarizacion(**silos).clean()

        presentes = [s for s in silos.values() if s is not None]
        if len({s.sucursal_id for s in presentes}) > 1:
            raise serializers.ValidationError(
                {"silo_destino": "Todos los silos deben pertenecer a la misma sucursal."}
            )
        producto = attrs.get("producto", getattr(self.instance, "producto", None))
        if presentes and producto and producto.mandante.empresa_id != presentes[0].sucursal.empresa_id:
            raise serializers.ValidationError(
                {"producto": "El producto debe pertenecer a la empresa de los silos."}
            )

        entera = silos["silo_entera"]
        descremada = silos["silo_descremada"]
        destino = silos["silo_destino"]
        if entera and entera.tipo != Silo.Tipo.SILO:
            raise serializers.ValidationError(
                {"silo_entera": "Selecciona un silo de leche entera."}
            )
        if descremada and descremada.tipo != Silo.Tipo.TK_LD:
            raise serializers.ValidationError(
                {"silo_descremada": "Selecciona un TK de leche descremada."}
            )
        if destino and destino.tipo != Silo.Tipo.SILO:
            raise serializers.ValidationError(
                {"silo_destino": "El destino debe ser un silo de leche."}
            )

        litros_descremada = attrs.get(
            "litros_descremada", getattr(self.instance, "litros_descremada", 0)
        )
        if litros_descremada and not descremada:
            raise serializers.ValidationError(
                {"silo_descremada": "La mezcla requiere un TK de leche descremada."}
            )

        return attrs


class CalculoMezclaSerializer(serializers.Serializer):
    """Entrada del cálculo previo: no crea nada, solo responde cuánto de cada."""

    entera_grasa = serializers.FloatField()
    entera_sng = serializers.FloatField()
    entera_disponible = serializers.FloatField(required=False, default=0.0)
    descremada_grasa = serializers.FloatField()
    descremada_sng = serializers.FloatField()
    descremada_disponible = serializers.FloatField(required=False, default=0.0)
    rc_objetivo = serializers.FloatField()
    volumen = serializers.FloatField()


class MuestraSerializer(serializers.Serializer):
    grasa = serializers.FloatField()
    sng = serializers.FloatField()
