from copy import copy

from rest_framework import serializers
from maestros.catalogos import CLAVES_PARAMETROS
from maestros.models import Equipo, Especificacion, Producto
from usuarios.models import Sucursal
from usuarios.tenancy import filtrar_por_scope, scope_de

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        self.fields["lote"].queryset = filtrar_por_scope(
            Lote.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        scope = scope_de(request.user)
        specs = Especificacion.objects.all()
        if scope is None:
            specs = specs.none()
        elif not scope.es_global:
            specs = specs.filter(producto__mandante__empresa_id=scope.empresa_id)
        self.fields["especificacion"].queryset = specs

    def validate(self, datos):
        lote = datos.get("lote", getattr(self.instance, "lote", None))
        especificacion = datos.get(
            "especificacion", getattr(self.instance, "especificacion", None)
        )
        if especificacion and lote and especificacion.producto_id != lote.producto_id:
            raise serializers.ValidationError(
                {"especificacion": "La especificación debe corresponder al producto del lote."}
            )
        return datos

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
    vale_codigo = serializers.CharField(source="vale.codigo", read_only=True)
    silo_estandarizado_codigo = serializers.CharField(
        source="vale.silo_destino.codigo", read_only=True
    )
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    litros_estandarizados = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False
    )
    litros_procesados = serializers.SerializerMethodField()

    # El resultado de calidad se calcula, nunca se lee de la base
    # (MODELO_DATOS.md §2.2).
    calidad = serializers.SerializerMethodField()

    class Meta:
        model = Lote
        fields = [
            "id",
            "sucursal",
            "codigo_lote",
            "op",
            "producto",
            "producto_nombre",
            "mandante_nombre",
            "vale",
            "vale_codigo",
            "silo_estandarizado_codigo",
            "litros_estandarizados",
            "litros_procesados",
            "equipo",
            "equipo_nombre",
            "ejecucion",
            "ejecucion_codigo",
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
        read_only_fields = ["ejecucion"]
        validators = []
        """validators = [
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
        ]"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        scope = scope_de(request.user)
        sucursales = Sucursal.objects.filter(activa=True)
        productos = Producto.objects.all()
        if scope is None:
            sucursales = sucursales.none()
            productos = productos.none()
        elif not scope.es_global:
            sucursales = sucursales.filter(empresa_id=scope.empresa_id)
            productos = productos.filter(mandante__empresa_id=scope.empresa_id)
            if scope.es_sucursal:
                sucursales = sucursales.filter(pk=scope.sucursal_id)
        self.fields["sucursal"].queryset = sucursales
        self.fields["producto"].queryset = productos
        self.fields["equipo"].queryset = filtrar_por_scope(
            Equipo.objects.filter(activo=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

        from estandarizacion.models import ValeEstandarizacion

        self.fields["vale"].queryset = filtrar_por_scope(
            ValeEstandarizacion.objects.select_related("silo_destino"),
            request.user,
            campo_sucursal="silo_destino__sucursal_id",
            campo_empresa="silo_destino__sucursal__empresa_id",
        )

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
        "equipo",
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
        request = self.context.get("request")
        scope = scope_de(getattr(request, "user", None)) if request else None
        if self.instance is None and scope and scope.es_sucursal:
            datos["sucursal"] = Sucursal.objects.get(pk=scope.sucursal_id)

        sucursal = datos.get("sucursal", getattr(self.instance, "sucursal", None))
        producto = datos.get("producto", getattr(self.instance, "producto", None))
        vale = datos.get("vale", getattr(self.instance, "vale", None))
        equipo = datos.get("equipo", getattr(self.instance, "equipo", None))
        if sucursal and producto and producto.mandante.empresa_id != sucursal.empresa_id:
            raise serializers.ValidationError(
                {"producto": "El producto y la sucursal deben pertenecer a la misma empresa."}
            )

        if self.instance is None and vale is not None:
            if producto and vale.producto_id != producto.id:
                raise serializers.ValidationError({
                    "producto": (
                        f"El vale {vale.codigo} fue estandarizado para "
                        f"{vale.producto.nombre}."
                    )
                })
            if "litros_estandarizados" not in datos:
                raise serializers.ValidationError({
                    "litros_estandarizados": (
                        "Indica cuántos litros del vale entran a la corrida."
                    )
                })
            if not datos.get("linea"):
                raise serializers.ValidationError({
                    "linea": "Selecciona la línea de producción."
                })
            if equipo is None:
                raise serializers.ValidationError({
                    "equipo": "Selecciona la máquina de la corrida."
                })
            datos["sucursal"] = vale.silo_destino.sucursal
            sucursal = datos["sucursal"]

        if equipo and vale and equipo.sucursal_id != vale.silo_destino.sucursal_id:
            raise serializers.ValidationError({
                "equipo": "La máquina debe pertenecer a la planta del vale."
            })

        codigo = datos.get("codigo_lote", getattr(self.instance, "codigo_lote", None))
        fecha = datos.get("fecha", getattr(self.instance, "fecha", None))
        if sucursal and producto and codigo and fecha:
            repetido = Lote.objects.filter(
                sucursal=sucursal, codigo_lote=codigo, producto=producto, fecha=fecha
            )
            if self.instance:
                repetido = repetido.exclude(pk=self.instance.pk)
            if repetido.exists():
                raise serializers.ValidationError(
                    {"codigo_lote": "Ya existe ese lote para el producto, fecha y sucursal."}
                )

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

    def create(self, datos):
        litros = datos.pop("litros_estandarizados", None)
        vale = datos.pop("vale", None)

        # Los registros históricos pueden no tener vale. La operación normal
        # de planta entra siempre por el servicio transaccional.
        if vale is None:
            return super().create(datos)

        from django.core.exceptions import ValidationError as DjangoValidationError
        from .servicios import abrir_lote_desde_vale

        datos.pop("sucursal", None)
        try:
            return abrir_lote_desde_vale(
                vale=vale,
                producto=datos.pop("producto"),
                codigo_lote=datos.pop("codigo_lote"),
                fecha=datos.pop("fecha"),
                litros=litros,
                usuario=getattr(self.context.get("request"), "user", None),
                **datos,
            )
        except DjangoValidationError as error:
            detalle = (
                error.message_dict
                if hasattr(error, "message_dict")
                else {"detail": error.messages}
            )
            raise serializers.ValidationError(detalle)

    def get_litros_procesados(self, lote):
        if not lote.vale_id:
            return None

        from recepcion.models import MovimientoSilo

        movimiento = MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.pk,
            silo=lote.vale.silo_destino,
        ).first()
        return float(movimiento.litros) if movimiento else None

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

    # Si el material del lote se descontó de bodega o quedó pendiente. Va en
    # la ficha porque un descuento que falló y no se ve es peor que uno que no
    # se intentó: el saldo de bodega queda alto y nadie lo sabe.
    consumo_inventario = serializers.SerializerMethodField()

    class Meta(LoteSerializer.Meta):
        fields = LoteSerializer.Meta.fields + [
            "analisis",
            "liberacion",
            "consumo_inventario",
        ]

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

    def get_consumo_inventario(self, lote):
        # Import local: `inventario` importa `produccion`, así que hacerlo
        # arriba cerraría el círculo.
        from inventario.models import ConsumoLoteProduccion

        consumo = ConsumoLoteProduccion.objects.filter(lote_produccion=lote).first()

        return {
            "registrado": consumo is not None,
            "registrado_en": consumo.registrado_en if consumo else None,
            "kg_base": consumo.kg_base if consumo else None,
            "pendiente": dominio.consumo_de_inventario_pendiente(lote, consumo),
        }


class ControlProcesoLecturaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlProcesoLectura
        fields = ["id", "control", "hora", "valores", "observacion"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request:
            self.fields["control"].queryset = filtrar_por_scope(
                ControlProceso.objects.all(), request.user,
                campo_sucursal="lote__sucursal_id",
                campo_empresa="lote__sucursal__empresa_id",
            )

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
    equipo_etiqueta = serializers.CharField(source="equipo.nombre", read_only=True)
    # El código del maestro viaja además del nombre porque es lo que los
    # criterios de evidencia del checklist comparan; el nombre es para leer.
    equipo_codigo = serializers.CharField(source="equipo.codigo", read_only=True)
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
            "equipo_codigo",
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
            "operador": {"read_only": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        self.fields["lote"].queryset = filtrar_por_scope(
            Lote.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        self.fields["equipo"].queryset = filtrar_por_scope(
            Equipo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    def validate(self, datos):
        lote = datos.get("lote", getattr(self.instance, "lote", None))
        equipo = datos.get("equipo", getattr(self.instance, "equipo", None))
        if lote and equipo and lote.sucursal_id != equipo.sucursal_id:
            raise serializers.ValidationError(
                {"equipo": "El equipo debe pertenecer a la sucursal del lote."}
            )
        return datos

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
