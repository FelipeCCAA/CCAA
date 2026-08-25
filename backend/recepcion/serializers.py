from decimal import Decimal

from rest_framework import serializers

from . import dominio
from .models import (
    CONTROLES_DECLARADOS,
    AnalisisSilo,
    CONTROLES_NUMERICOS,
    VALORES_ADMITIDOS,
    BusquedaProveedor,
    ControlInhibidores,
    ModuloRecepcion,
    MovimientoSilo,
    Recepcion,
)


class ModuloRecepcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuloRecepcion
        fields = ["id", "numero", "crioscopia", "carga_recoleccion"]


class BusquedaProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusquedaProveedor
        fields = [
            "id", "proveedor", "charm_bet", "charm_tetra",
            "delvo_sp", "hora_lectura", "resultado",
        ]


class ControlInhibidoresSerializer(serializers.ModelSerializer):
    busquedas = BusquedaProveedorSerializer(many=True, read_only=True)
    analista_nombre = serializers.CharField(
        source="analista.get_full_name", read_only=True
    )

    class Meta:
        model = ControlInhibidores
        fields = [
            "id", "recepcion", "metodo", "tiras_usadas", "hora_lectura",
            "resultado", "analista", "analista_nombre", "busquedas",
        ]


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

    # Los módulos se crean a mano en `registrar_llegada` (el bucle explícito
    # sobre `ModuloRecepcion.objects.create`). De solo lectura acá: un solo
    # camino para crearlos es mejor que dos, y evita que un `PATCH` a la
    # recepción los reescriba sin pasar por esas validaciones.
    modulos = ModuloRecepcionSerializer(many=True, read_only=True)
    controles_inhibidores = ControlInhibidoresSerializer(many=True, read_only=True)

    # Los diez derivados del formato: se calculan siempre, nunca se guardan.
    kg_guia = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    diferencia_kg = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    solidos_totales = serializers.FloatField(read_only=True)
    solidos_totales_kg = serializers.FloatField(read_only=True)
    crioscopia_pool = serializers.FloatField(read_only=True)
    # Misma forma que `litros` (`max_digits=12, decimal_places=2`): sin
    # declararlo explícito, DRF lo resuelve como `ReadOnlyField` y sale como
    # número JSON en vez de string, distinto de sus hermanas derivadas.
    diferencia_recoleccion_litros = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    permanencia_horas = serializers.FloatField(read_only=True)
    permanencia_motivo = serializers.CharField(read_only=True)
    horas_en_planta = serializers.FloatField(read_only=True)
    horas_a_pagar = serializers.IntegerField(read_only=True)
    tiempo_en_fabrica_horas = serializers.FloatField(read_only=True)
    tiempo_de_descarga_horas = serializers.FloatField(read_only=True)

    class Meta:
        model = Recepcion
        fields = [
            "id",
            "fecha",
            "hora",
            "guia",
            "vehiculo",
            "vehiculo_placa",
            "procedencia",
            "tipo_leche",
            "litros",
            "kg_romana",
            "certificada",
            "uso",
            "uso_numero",
            "hora_programa",
            "hora_arribo_porteria",
            "hora_ingreso",
            "hora_inicio_descarga",
            "hora_termino_descarga",
            "hora_inicio_cip",
            "hora_termino_cip",
            "hora_salida",
            "lavado_ruedas",
            "relavado",
            "recambio_dilucion",
            "ph_camion",
            "silo",
            "silo_codigo",
            "operador",
            "operador_nombre",
            "turno",
            "controles",
            "estado",
            "estado_etiqueta",
            "es_borrador",
            "abierto_por",
            "abierto_en",
            "actualizado_en",
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
            "modulos",
            "controles_inhibidores",
            "kg_guia",
            "diferencia_kg",
            "solidos_totales",
            "solidos_totales_kg",
            "crioscopia_pool",
            "diferencia_recoleccion_litros",
            "permanencia_horas",
            "permanencia_motivo",
            "horas_en_planta",
            "horas_a_pagar",
            "tiempo_en_fabrica_horas",
            "tiempo_de_descarga_horas",
        ]
        read_only_fields = [
            "silo",
            "operador",
            "controles",
            "estado",
            "es_borrador",
            "abierto_por",
            "abierto_en",
            "actualizado_en",
            "motivo",
            "codigo_muestra",
            "muestreado_por",
            "muestreado_en",
            "calidad_por",
            "calidad_en",
            "silo_asignado_por",
            "silo_asignado_en",
            "diferencia_recoleccion_litros",
        ]

    def get_evaluacion(self, recepcion):
        # `Recepcion.evaluar()` es el único lugar que arma crioscopías y pH
        # del camión para `dominio.evaluar_recepcion`: así esta vista previa
        # y `decidir-calidad` (que decide con el mismo cálculo) no pueden
        # divergir.
        evaluacion = recepcion.evaluar()

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
        sucursal = getattr(self.instance, "sucursal", None)

        vehiculo = datos.get("vehiculo", getattr(self.instance, "vehiculo", None))
        if sucursal and vehiculo and sucursal.pk != vehiculo.sucursal_id:
            raise serializers.ValidationError(
                {"vehiculo": "El vehículo debe pertenecer a la organización."}
            )

        estado = datos.get("estado", getattr(self.instance, "estado", None))
        motivo = datos.get("motivo", getattr(self.instance, "motivo", "") or "")

        if estado == Recepcion.Estado.RETENIDA and not motivo.strip():
            raise serializers.ValidationError(
                {"motivo": "Una recepción retenida debe indicar el motivo."}
            )

        # Misma regla que `Recepcion.clean()` (que DRF no llama: no hace
        # `full_clean()`), y la misma constante — duplicar el criterio sin
        # compartir la lista de usos numerados es la forma en que las dos
        # copias terminan diciendo cosas distintas.
        uso = datos.get("uso", getattr(self.instance, "uso", "") or "")
        uso_numero = datos.get("uso_numero", getattr(self.instance, "uso_numero", None))
        if uso_numero is not None and uso not in Recepcion.USOS_NUMERADOS:
            raise serializers.ValidationError(
                {
                    "uso_numero": (
                        "Solo los precondensados llevan número de destino. "
                        f"«{uso or 'sin uso'}» no."
                    )
                }
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
            "operacion_id",
            "silo_contraparte",
            "lote",
            "producto",
            "equipo",
            "usuario",
        ]
        read_only_fields = [
            "tipo", "fecha_hora", "origen_tipo", "origen_id", "operacion_id",
            "silo_contraparte", "lote", "producto", "equipo", "usuario",
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


class AjusteSiloSerializer(serializers.Serializer):
    silo = serializers.IntegerField(min_value=1)
    litros = serializers.DecimalField(max_digits=12, decimal_places=2)
    motivo = serializers.CharField(trim_whitespace=True)
    operacion_id = serializers.UUIDField()

    def validate_litros(self, valor):
        if valor == 0:
            raise serializers.ValidationError("El ajuste no puede ser cero.")
        return valor


class TransferenciaSiloSerializer(serializers.Serializer):
    silo_origen = serializers.IntegerField(min_value=1)
    silo_destino = serializers.IntegerField(min_value=1)
    litros = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    operacion_id = serializers.UUIDField()
    motivo = serializers.CharField(required=False, allow_blank=True, default="")
    lote = serializers.IntegerField(required=False, allow_null=True)
    producto = serializers.IntegerField(required=False, allow_null=True)
    equipo = serializers.IntegerField(required=False, allow_null=True)


class AnalisisSiloSerializer(serializers.ModelSerializer):
    silo_codigo = serializers.CharField(source="silo.codigo", read_only=True)
    # Método y no `source="analista.username"`: el analista es nulable, y una
    # travesía sobre `None` en DRF revienta en vez de devolver el vacío.
    analista_nombre = serializers.SerializerMethodField()
    vigente = serializers.BooleanField(read_only=True)
    motivo_vigencia = serializers.CharField(read_only=True)
    faltantes_para_vale = serializers.ListField(
        child=serializers.CharField(), read_only=True
    )

    class Meta:
        model = AnalisisSilo
        fields = [
            "id", "silo", "silo_codigo", "tomado_en", "hora_inicio_llenado",
            "ph", "acidez", "grasa", "sng", "proteina", "temperatura", "densidad",
            "certificada", "procedencia", "analista", "analista_nombre",
            "observacion", "creado_en",
            "vigente", "motivo_vigencia", "faltantes_para_vale",
        ]
        read_only_fields = ["analista", "creado_en"]

    def get_analista_nombre(self, obj):
        return obj.analista.username if obj.analista_id else ""
