from django.utils import timezone
from rest_framework import serializers

from maestros.serializers import DocumentoLiberacionSerializer

from . import dominio
from .models import Liberacion, RegistroCalidad


class RegistroCalidadSerializer(serializers.ModelSerializer):
    """
    Un formulario completado. Los valores viajan como los tecleó quien lo
    llenó; la validación contra la plantilla se hace aquí, no en la pantalla.
    """

    documento_nombre = serializers.CharField(source="documento.nombre", read_only=True)
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    completado_por_nombre = serializers.CharField(
        source="completado_por.get_full_name", read_only=True
    )

    # Derivados: si al documento le cambian la plantilla, esto cambia solo.
    completo = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()

    class Meta:
        model = RegistroCalidad
        fields = [
            "id",
            "lote",
            "lote_codigo",
            "documento",
            "documento_nombre",
            "estado",
            "estado_etiqueta",
            "valores",
            "referencia",
            "completado_por",
            "completado_por_nombre",
            "completado_en",
            "observacion",
            "completo",
            "faltantes",
        ]
        # Quién firmó y cuándo los pone el servidor, no el cliente: son el
        # dato de auditoría y aceptarlos del navegador los haría inútiles.
        read_only_fields = ["completado_por", "completado_en"]

    def get_completo(self, registro):
        return dominio.registro_completo(registro, registro.documento)

    def get_faltantes(self, registro):
        return [c["etiqueta"] for c in dominio.campos_faltantes(registro, registro.documento)]

    def validate_valores(self, valores):
        if not isinstance(valores, dict):
            raise serializers.ValidationError("Debe ser un objeto de valores por clave.")

        return valores

    def validate(self, datos):
        estado = datos.get("estado", getattr(self.instance, "estado", None))
        documento = datos.get("documento", getattr(self.instance, "documento", None))
        valores = datos.get("valores", getattr(self.instance, "valores", None) or {})
        observacion = datos.get(
            "observacion", getattr(self.instance, "observacion", "") or ""
        )

        if estado == RegistroCalidad.Estado.OBSERVADO and not observacion.strip():
            raise serializers.ValidationError(
                {"observacion": "Un formulario observado debe decir qué se observó."}
            )

        # Solo se comprueba al darlo por completado. En borrador se guarda a
        # medias a propósito: un formulario de planta se llena por partes, y
        # obligar a terminarlo de una sentada lo empujaría de vuelta al papel.
        if estado == RegistroCalidad.Estado.COMPLETADO and documento is not None:
            validacion = dominio.validar_registro(
                _RegistroEnMemoria(estado, valores), documento
            )

            if not validacion.permitido:
                raise serializers.ValidationError({"valores": validacion.bloqueos})

        return datos


class _RegistroEnMemoria:
    """
    Lo mínimo que el dominio necesita para validar: estado y valores.

    Existe porque al crear todavía no hay instancia que pasarle, y construir un
    `RegistroCalidad` sin guardar exigiría el lote y el documento resueltos.
    """

    def __init__(self, estado, valores):
        self.estado = estado
        self.valores = valores


class LiberacionSerializer(serializers.ModelSerializer):
    """
    El expediente de autorización.

    Todo lo que constituye la firma es de solo lectura: el estado, quién
    autorizó, cuándo, la marca de concesión y su motivo. Se escriben por
    `expedientes/<lote>/liberar/`, `/conceder/` y `/revisar/`, que comprueban
    la regla antes de tocar nada.

    No basta con dejarlos fuera de `fields`. Un campo de solo lectura que
    llega en el cuerpo, DRF lo descarta en silencio y responde 200: quien lo
    intentó se queda creyendo que funcionó. Por eso `validate` lo rechaza con
    un mensaje que dice por dónde se hace.
    """

    # Campos que definen la firma. Escribirlos por esta vía saltaría la regla
    # que justifica el sistema: se probó, y dejaba un lote despachable sin
    # checklist, sin autorizador y sin fecha.
    DE_LA_FIRMA = (
        "estado",
        "concesion",
        "motivo_concesion",
        "autorizada_por",
        "autorizada_en",
    )

    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    producto_nombre = serializers.CharField(
        source="lote.producto.nombre", read_only=True
    )
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    autorizada_por_nombre = serializers.CharField(
        source="autorizada_por.get_full_name", read_only=True
    )
    liberado = serializers.BooleanField(read_only=True)

    class Meta:
        model = Liberacion
        fields = [
            "id",
            "lote",
            "lote_codigo",
            "producto_nombre",
            "estado",
            "estado_etiqueta",
            "autorizada_por",
            "autorizada_por_nombre",
            "autorizada_en",
            "concesion",
            "motivo_concesion",
            "observacion",
            "liberado",
        ]
        # La firma la estampa el servidor al liberar, nunca el cliente.
        read_only_fields = [
            "estado",
            "autorizada_por",
            "autorizada_en",
            "concesion",
            "motivo_concesion",
        ]

    def validate(self, datos):
        intentados = sorted(set(self.DE_LA_FIRMA) & set(self.initial_data or {}))

        if intentados:
            raise serializers.ValidationError(
                {
                    campo: (
                        "No se escribe por aquí. La liberación se firma en "
                        "expedientes/<lote>/liberar/ o /conceder/, que "
                        "comprueban el checklist y la calidad antes de "
                        "estampar la firma."
                    )
                    for campo in intentados
                }
            )

        return datos


# ------------------------------------------------------- salidas derivadas

def serializar_avance(avance):
    """El avance documental de un lote, con el detalle de cada documento."""
    return {
        "completados": avance.completados,
        "total": avance.total,
        "pct": avance.pct,
        "completo": avance.completo,
        "detalle": [
            {
                "documento": DocumentoLiberacionSerializer(d.documento).data,
                "registro": (
                    RegistroCalidadSerializer(d.registro).data if d.registro else None
                ),
                "completo": d.completo,
                "observado": d.observado,
                "iniciado": d.iniciado,
                # De dónde viene el cumplimiento. La pantalla lo distingue
                # porque no es lo mismo «hay control de proceso» que «alguien
                # marcó la casilla».
                "cumplido_por_dato": d.cumplido_por_dato,
                # El registro periódico que lo cubre, si lo hay. Va con su
                # fecha y su equipo para que el expediente pueda decir CUÁL
                # —«el aseo del 27-07 en el VEB»— y quien audita llegue al
                # papel.
                "cubierto_por": (
                    {
                        "id": d.cubierto_por.id,
                        "fecha": d.cubierto_por.fecha,
                        "equipo": (
                            d.cubierto_por.equipo.nombre
                            if d.cubierto_por.equipo_id
                            else None
                        ),
                        "turno": d.cubierto_por.turno,
                        "vigente_hasta": d.cubierto_por.vigente_hasta,
                    }
                    if d.cubierto_por is not None
                    else None
                ),
                "faltantes": [c["etiqueta"] for c in d.faltantes],
            }
            for d in avance.detalle
        ],
    }


def serializar_calidad(resultado):
    """El veredicto de calidad. Recalculado siempre, nunca leído de una tabla."""
    if resultado is None:
        return None

    return {
        "resultado": resultado.resultado,
        "etiqueta": resultado.etiqueta,
        "evaluados": resultado.evaluados,
        "desviaciones": resultado.desviaciones,
        "especificacion_id": getattr(resultado.especificacion, "id", None),
    }


def serializar_decision(decision):
    """
    El veredicto de liberación, con sus motivos.

    Los bloqueos van siempre, incluso cuando está permitido (donde van vacíos):
    la pantalla no debería tener que adivinar por qué no puede avanzar.
    """
    return {
        "permitido": decision.permitido,
        "via_concesion": decision.via_concesion,
        "bloqueos": decision.bloqueos,
        "calidad": serializar_calidad(decision.calidad),
        "avance": serializar_avance(decision.avance) if decision.avance else None,
    }


def serializar_discrepancias(discrepancias):
    return [
        {
            "tipo": d.tipo,
            "parametro": d.parametro,
            "etiqueta": d.etiqueta,
            "declarado": d.declarado,
            "min": d.minimo,
            "max": d.maximo,
            "medidos": d.medidos,
            "mensaje": d.mensaje,
        }
        for d in discrepancias
    ]


class FirmaSerializer(serializers.Serializer):
    """Lo que se envía al firmar una liberación normal."""

    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class ConcesionSerializer(serializers.Serializer):
    """
    Lo que se envía al liberar bajo concesión.

    El motivo es obligatorio aquí y su largo mínimo lo pone el dominio: es lo
    que impide que "ok" pase por justificación de un producto no conforme.
    """

    motivo = serializers.CharField()
    observacion = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_motivo(self, motivo):
        if len(motivo.strip()) < dominio.LARGO_MINIMO_MOTIVO:
            raise serializers.ValidationError(
                f"La concesión exige un motivo escrito de al menos "
                f"{dominio.LARGO_MINIMO_MOTIVO} caracteres."
            )

        return motivo


def ahora():
    """`timezone.now()`, no `date.today()`: la firma sin zona horaria no se defiende."""
    return timezone.now()
