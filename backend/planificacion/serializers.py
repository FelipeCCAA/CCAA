from rest_framework import serializers

from . import dominio
from .models import BalanceDia, BloquePlan, CodigoProduccion, SemanaPlan


class CodigoProduccionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    mandante_nombre = serializers.CharField(source="mandante.nombre", read_only=True)
    categoria_etiqueta = serializers.CharField(
        source="get_categoria_display", read_only=True
    )

    class Meta:
        model = CodigoProduccion
        fields = [
            "id",
            "codigo",
            "nombre",
            "producto",
            "producto_nombre",
            "mandante",
            "mandante_nombre",
            "formato",
            "categoria",
            "categoria_etiqueta",
            "rendimiento_lh",
            "activo",
        ]


class BloquePlanSerializer(serializers.ModelSerializer):
    codigo_texto = serializers.CharField(source="codigo.codigo", read_only=True)
    categoria = serializers.CharField(source="codigo.categoria", read_only=True)
    equipo_etiqueta = serializers.CharField(source="equipo.nombre", read_only=True)
    equipo_codigo = serializers.CharField(source="equipo.codigo", read_only=True)
    horas = serializers.FloatField(read_only=True)
    consume_leche = serializers.BooleanField(read_only=True)

    class Meta:
        model = BloquePlan
        fields = [
            "id",
            "semana",
            "equipo",
            "equipo_codigo",
            "equipo_etiqueta",
            "dia",
            "hora_inicio",
            "hora_fin",
            "horas",
            "tipo",
            "codigo",
            "codigo_texto",
            "categoria",
            "estado_equipo",
            "cantidad_kg",
            "observacion",
            "consume_leche",
        ]

    def validate(self, datos):
        """
        Delega en el dominio, que es quien sabe de solapamientos.

        La comprobación necesita ver los demás bloques del mismo equipo y día,
        cosa que ni el modelo ni una restricción de base pueden hacer: un
        solapamiento no es un duplicado, es un intervalo que pisa a otro.
        """
        propuesto = BloquePlan(
            **{
                **{
                    campo: getattr(self.instance, campo, None)
                    for campo in ("semana", "equipo", "dia", "hora_inicio", "hora_fin",
                                  "tipo", "codigo", "estado_equipo")
                },
                **{k: v for k, v in datos.items()},
            }
        )
        propuesto.pk = getattr(self.instance, "pk", None)

        hermanos = BloquePlan.objects.filter(
            semana=propuesto.semana, equipo=propuesto.equipo, dia=propuesto.dia
        )

        validacion = dominio.validar_bloque(propuesto, list(hermanos))

        if not validacion.permitido:
            raise serializers.ValidationError({"bloqueos": validacion.bloqueos})

        return datos


class BalanceDiaSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceDia
        fields = [
            "id",
            "semana",
            "dia",
            "stock_inicial",
            "recepcion_ccaa",
            "recepcion_nestle",
            "recepcion_punion",
            "trasvasije",
            "crema_disponible_ton",
            "ajustes",
            "observacion",
        ]

    def validate_ajustes(self, ajustes):
        if not isinstance(ajustes, dict):
            raise serializers.ValidationError("Debe ser un objeto de ajustes por origen.")

        desconocidos = set(ajustes) - set(dominio.ORIGENES)
        if desconocidos:
            raise serializers.ValidationError(
                f"Orígenes no reconocidos: {', '.join(sorted(desconocidos))}"
            )

        return ajustes


class SemanaPlanSerializer(serializers.ModelSerializer):
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    publicada_por_nombre = serializers.CharField(
        source="publicada_por.get_full_name", read_only=True
    )

    class Meta:
        model = SemanaPlan
        fields = [
            "id",
            "codigo",
            "anio",
            "fecha_inicio",
            "estado",
            "estado_etiqueta",
            "publicada_por",
            "publicada_por_nombre",
            "publicada_en",
            "observacion",
        ]
        # Publicar es un acto: se firma por su endpoint, que comprueba que el
        # plan cuadre. Escribir `estado` a mano lo saltaría.
        read_only_fields = ["estado", "publicada_por", "publicada_en"]

    def validate(self, datos):
        prohibidos = {"estado", "publicada_por", "publicada_en"}
        intentados = sorted(prohibidos & set(self.initial_data or {}))

        if intentados:
            raise serializers.ValidationError(
                {
                    campo: (
                        "No se escribe por aquí. La semana se publica en "
                        "semanas/<id>/publicar/, que comprueba que el plan cuadre."
                    )
                    for campo in intentados
                }
            )

        return datos


# --------------------------------------------------------- salidas derivadas

def serializar_consumo(consumo):
    return {
        "por_categoria": consumo.por_categoria,
        "trasvasije": consumo.trasvasije,
        "derivado": consumo.derivado,
        "total": consumo.total,
    }


def serializar_balance(fila):
    """Una fila del balance con todo lo derivado ya calculado."""
    return {
        "dia": fila.dia,
        "stock_inicial": fila.stock_inicial,
        "recepciones": fila.recepciones,
        "total_recepciones": fila.total_recepciones,
        "total_disponible": fila.total_disponible,
        "consumo": serializar_consumo(fila.consumo),
        "stock_final": fila.stock_final,
        "stock_por_origen": fila.stock_por_origen,
        # Un saldo negativo por origen es una alarma: se programó más leche de
        # la que se espera recibir.
        "origenes_negativos": fila.origenes_negativos,
    }


def serializar_desviacion(desviacion):
    return {
        "plan": desviacion.plan,
        "real": desviacion.real,
        "diferencia": desviacion.diferencia,
        "pct": desviacion.pct,
    }


def serializar_contraste(fila):
    return {
        "dia": fila.dia,
        "fecha": fila.fecha,
        "leche_recibida": serializar_desviacion(fila.leche_recibida),
        "leche_consumida": serializar_desviacion(fila.leche_consumida),
        "kilos": serializar_desviacion(fila.kilos),
        "lotes": fila.lotes,
        "hubo_actividad": fila.hubo_actividad,
    }
