from copy import copy

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from maestros.catalogos import CLAVES_PARAMETROS

from . import dominio
from .models import Analisis, ControlProceso, ControlProcesoLectura, Lote


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

    def validate_estado(self, estado):
        """
        Aplica las transiciones que el modelo declara.

        Estaban escritas en `Lote.TRANSICIONES` desde el primer día pero no las
        comprobaba nadie: por la API se podía pasar de `en_proceso` a `cerrado`
        saltándose `producido`, o resucitar un lote anulado. Un lote anulado
        que vuelve a producción es un registro que dice algo falso sobre lo que
        pasó en planta, y el histórico se audita.
        """
        if self.instance is None or estado == self.instance.estado:
            return estado

        permitidos = Lote.TRANSICIONES.get(self.instance.estado, [])

        if estado not in permitidos:
            actual = self.instance.get_estado_display().lower()
            destinos = (
                ", ".join(Lote.Estado(e).label.lower() for e in permitidos)
                if permitidos
                else "ninguno: es un estado final"
            )
            raise serializers.ValidationError(
                f"Un lote {actual} no puede pasar a "
                f"{Lote.Estado(estado).label.lower()}. Desde {actual} solo se "
                f"puede pasar a: {destinos}."
            )

        return estado

    # Lo que define QUÉ se produjo. Si el lote ya está liberado, cambiarlo
    # deja la firma de Calidad respaldando algo distinto de lo que se firmó.
    # La observación queda fuera a propósito: anotar siempre se puede.
    CAMPOS_SUSTANTIVOS = (
        "codigo_lote",
        "op",
        "producto",
        "fecha",
        "linea",
        "turno",
        "kg_producidos",
        "bultos",
        "hora_inicio",
        "hora_termino",
        "vencimiento",
    )

    def validate(self, datos):
        """
        Dos guardas sobre la edición de un lote ya existente.

        No son burocracia: un lote es la unidad de liberación y de despacho, y
        editarlo después de que alguien firmó por él cambia el significado de
        esa firma sin que nadie se entere.
        """
        if self.instance is None:
            return datos

        cambios = [
            campo
            for campo in self.CAMPOS_SUSTANTIVOS
            if campo in datos and datos[campo] != getattr(self.instance, campo)
        ]

        self._rechazar_si_no_puede_declararse_producido(datos)

        if not cambios:
            return datos

        self._rechazar_si_es_final()
        self._rechazar_si_esta_liberado(cambios)

        return datos

    def _rechazar_si_no_puede_declararse_producido(self, datos):
        """
        Un lote se declara producido con sus kilos, no sin ellos.

        El lote se abre al empezar la corrida, cuando los kilos todavía no
        existen; este es el momento en que sí tienen que estar. La regla vive
        en `dominio.puede_declarar_producido` para que se pueda probar sola y
        para que endurecerla —por ejemplo, exigir también la leche asignada—
        sea editar una función pura y no la vista.
        """
        if datos.get("estado") != Lote.Estado.PRODUCIDO:
            return

        if self.instance.estado == Lote.Estado.PRODUCIDO:
            return

        # Los kilos pueden venir en la misma llamada que el cambio de estado.
        candidato = copy(self.instance)
        if "kg_producidos" in datos:
            candidato.kg_producidos = datos["kg_producidos"]

        decision = dominio.puede_declarar_producido(
            candidato, self._asignaciones_del_lote()
        )

        if not decision.permitido:
            raise serializers.ValidationError({"estado": decision.bloqueos})

    def _asignaciones_del_lote(self):
        """Las salidas de silo que este lote consumió."""
        from recepcion.models import MovimientoSilo

        return list(
            MovimientoSilo.objects.filter(
                tipo=MovimientoSilo.Tipo.SALIDA,
                origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                origen_id=self.instance.id,
            )
        )

    def _rechazar_si_es_final(self):
        """Un lote cerrado o anulado es histórico, y el histórico se audita."""
        if not Lote.TRANSICIONES.get(self.instance.estado, []):
            raise serializers.ValidationError(
                f"Un lote {self.instance.get_estado_display().lower()} ya no se "
                "edita: es un registro histórico."
            )

    def _rechazar_si_esta_liberado(self, cambios):
        # Import local: `calidad` importa `produccion`, así que hacerlo arriba
        # cerraría el círculo.
        from calidad.models import Liberacion

        liberacion = Liberacion.objects.filter(lote=self.instance).first()

        if liberacion is None or not liberacion.liberado:
            return

        raise serializers.ValidationError(
            {
                campo: (
                    "El lote está liberado: cambiarlo dejaría la firma de "
                    "Calidad respaldando otra cosa. Retira antes la liberación "
                    f"en expedientes/{self.instance.id}/revisar/."
                )
                for campo in cambios
            }
        )

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

    # Si Calidad ya lo firmó, el lote no se edita. Viaja en la ficha para que
    # la pantalla lo diga por adelantado en vez de dejar que alguien llene el
    # formulario y descubra el rechazo al guardar.
    liberacion = serializers.SerializerMethodField()

    class Meta(LoteSerializer.Meta):
        fields = LoteSerializer.Meta.fields + ["analisis", "liberacion"]

    def get_liberacion(self, lote):
        # Import local: `calidad` importa `produccion`.
        from calidad.models import Liberacion

        liberacion = Liberacion.objects.filter(lote=lote).first()

        if liberacion is None:
            return None

        return {
            "estado": liberacion.estado,
            "estado_etiqueta": liberacion.get_estado_display(),
            "liberado": liberacion.liberado,
            "autorizada_por_nombre": (
                liberacion.autorizada_por.get_full_name()
                if liberacion.autorizada_por
                else None
            ),
        }


class ControlProcesoLecturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlProcesoLectura
        fields = ["id", "control", "hora", "valores", "observacion"]

    def validate_valores(self, valores):
        if not isinstance(valores, dict):
            raise serializers.ValidationError("Debe ser un objeto de valores medidos.")

        for parametro, valor in valores.items():
            if valor is not None and not isinstance(valor, (int, float)):
                raise serializers.ValidationError(
                    f"El valor de '{parametro}' debe ser numérico."
                )

        return valores


class ControlProcesoSerializer(serializers.ModelSerializer):
    equipo_etiqueta = serializers.CharField(source="get_equipo_display", read_only=True)
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    lecturas = ControlProcesoLecturaSerializer(many=True, read_only=True)

    # El veredicto del PCC 1 se recalcula desde las lecturas y su límite; no se
    # guarda (MODELO_DATOS.md §2.2).
    pcc1 = serializers.SerializerMethodField()

    class Meta:
        model = ControlProceso
        fields = [
            "id",
            "lote",
            "lote_codigo",
            "equipo",
            "equipo_etiqueta",
            "turno",
            "fecha",
            "hora_arranque",
            "hora_inicio_produccion",
            "hora_termino_produccion",
            "pcc1_temp_min",
            "pcc1_caudal_max",
            "operador",
            "observacion",
            "lecturas",
            "pcc1",
        ]
        # `turno` y `equipo` son opcionales en el modelo pero entran en la
        # clave de unicidad, y DRF exige **todos** los campos de una clave
        # única aunque el modelo los declare `blank=True`. Con `required=False`
        # a secas el validador los vuelve a pedir; hace falta el valor por
        # defecto para que la pantalla pueda omitirlos.
        extra_kwargs = {
            "turno": {"required": False, "default": ""},
        }

    def get_pcc1(self, control):
        """
        Cómo quedó el punto crítico, con el detalle de cada incumplimiento.

        Se devuelve entero y no solo un booleano porque la pantalla tiene que
        poder decir *qué* lectura se salió y de cuánto: un «no cumple» sin
        detalle obliga a buscar el problema a mano.
        """
        evaluacion = dominio.evaluar_pcc1(control, list(control.lecturas.all()))

        return {
            "cumple": evaluacion.cumple,
            "sin_limites": evaluacion.sin_limites,
            "sin_lecturas": evaluacion.sin_lecturas,
            "incumplimientos": [
                {
                    "hora": str(i.hora),
                    "parametro": i.parametro,
                    "valor": i.valor,
                    "limite": i.limite,
                    "sentido": i.sentido,
                    "descripcion": i.descripcion,
                }
                for i in evaluacion.incumplimientos
            ],
        }
