from copy import copy
from decimal import Decimal

from django.db.models import Count, Q
from rest_framework import serializers
from maestros.catalogos import CLAVES_PARAMETROS
from maestros.models import Equipo, Especificacion, Producto
from usuarios.tenancy import filtrar_por_scope, scope_de, sucursal_para_escritura

from . import dominio
from .models import (
    Analisis, ControlProceso, ControlProcesoLectura, CorreccionLote, Lote,
    OrdenProduccion, PalletProducto, RegistroEnvase,
)


class PalletProductoSerializer(serializers.ModelSerializer):
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    lote_codigo = serializers.CharField(source="envase.lote.codigo_lote", read_only=True)
    producto_nombre = serializers.CharField(source="envase.lote.producto.nombre", read_only=True)

    class Meta:
        model = PalletProducto
        fields = [
            "id", "codigo", "unidades", "kg_neto", "estado", "estado_etiqueta",
            "lote_codigo", "producto_nombre",
        ]
        read_only_fields = ["estado"]


class PalletEntradaSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=80, trim_whitespace=True)
    unidades = serializers.IntegerField(min_value=1)
    kg_neto = serializers.DecimalField(
        max_digits=14, decimal_places=3, min_value=Decimal("0.001"),
        max_value=Decimal("500"),
    )


class RegistroEnvaseSerializer(serializers.ModelSerializer):
    pallets = PalletProductoSerializer(many=True, read_only=True)
    pallets_datos = PalletEntradaSerializer(many=True, write_only=True)
    lote_codigo = serializers.CharField(source="lote.codigo_lote", read_only=True)
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    formato_nombre = serializers.CharField(source="formato.nombre", read_only=True)
    operador_nombre = serializers.CharField(source="operador.get_full_name", read_only=True)
    operacion_id = serializers.UUIDField(required=False)

    class Meta:
        model = RegistroEnvase
        fields = [
            "id", "lote", "lote_codigo", "equipo", "equipo_nombre", "formato",
            "formato_nombre", "formato_kg",
            "unidades", "kg_envasados", "controles", "operador", "inicio", "termino",
            "observacion", "operacion_id", "creado_en", "pallets", "pallets_datos",
            "operador_nombre",
        ]
        read_only_fields = [
            "formato_kg", "unidades", "kg_envasados", "operador", "creado_en"
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
        self.fields["equipo"].queryset = filtrar_por_scope(
            Equipo.objects.filter(activo=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        from maestros.models import FormatoEnvasado
        self.fields["formato"].queryset = filtrar_por_scope(
            FormatoEnvasado.objects.filter(activo=True), request.user,
            campo_empresa="producto__mandante__empresa_id",
        )

    def create(self, datos):
        from .servicios import registrar_envasado

        pallets = datos.pop("pallets_datos")
        lote = datos.pop("lote")
        return registrar_envasado(
            lote_id=lote.pk, pallets=pallets,
            usuario=self.context["request"].user, **datos,
        )


class OrdenProduccionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    responsable_nombre = serializers.CharField(
        source="responsable.get_full_name", read_only=True
    )

    class Meta:
        model = OrdenProduccion
        fields = [
            "id", "semana", "codigo", "producto", "producto_nombre",
            "cantidad_planificada", "unidad", "linea", "equipo", "equipo_nombre",
            "destino", "responsable", "responsable_nombre", "estado",
            "estado_etiqueta", "observacion", "creada_por", "creada_en",
        ]
        read_only_fields = ["creada_por", "creada_en"]

    def validate(self, datos):
        if self.instance is None:
            request = self.context.get("request")
            datos["sucursal"] = sucursal_para_escritura(
                getattr(request, "user", None), datos
            )
        if self.instance and "estado" in datos and datos["estado"] != self.instance.estado:
            if datos["estado"] not in OrdenProduccion.TRANSICIONES[self.instance.estado]:
                raise serializers.ValidationError({"estado": "Transición de orden no permitida."})
            if datos["estado"] == OrdenProduccion.Estado.CANCELADA:
                motivo = datos.get("observacion", "").strip()
                if not motivo or motivo == self.instance.observacion.strip():
                    raise serializers.ValidationError({
                        "observacion": "Indica el motivo de cancelación de la orden."
                    })
        candidato = OrdenProduccion(
            **{
                **{
                    campo: getattr(self.instance, campo, None)
                    for campo in ("sucursal", "semana", "producto", "equipo")
                },
                **datos,
            }
        )
        candidato.clean()
        return datos


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

        if lote is not None:
            if self.instance is None and lote.analisis.count() >= 2:
                raise serializers.ValidationError({
                    "lote": "El lote ya tiene el máximo de 2 análisis permitidos."
                })
            vigente = dominio.especificacion_vigente(
                Especificacion.objects.filter(producto_id=lote.producto_id),
                lote.producto_id,
                lote.fecha,
            )
            if vigente is None:
                raise serializers.ValidationError({
                    "especificacion": (
                        "El producto no tiene una especificación vigente para la fecha del lote."
                    )
                })
            valores = datos.get("valores", getattr(self.instance, "valores", {})) or {}
            faltantes = [
                clave
                for clave, rango in (vigente.rangos or {}).items()
                if rango.get("obligatorio") and valores.get(clave) is None
            ]
            if faltantes:
                raise serializers.ValidationError({
                    "valores": (
                        "Faltan parámetros obligatorios: " + ", ".join(faltantes) + "."
                    )
                })
            datos["especificacion"] = vigente
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
    motivo_anulacion = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
        trim_whitespace=True,
    )
    producto_nombre = serializers.CharField(
        source="producto.nombre", read_only=True, allow_null=True
    )
    motivo_correccion = serializers.CharField(
        write_only=True, required=False, allow_blank=False, min_length=5,
        trim_whitespace=True,
    )
    mandante_nombre = serializers.CharField(
        source="producto.mandante.nombre", read_only=True, allow_null=True
    )
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)
    vale_codigo = serializers.CharField(source="vale.codigo", read_only=True)
    silo_estandarizado_codigo = serializers.CharField(
        source="vale.silo_destino.codigo", read_only=True
    )
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    ejecucion_codigo = serializers.CharField(source="ejecucion.codigo", read_only=True)
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    litros_estandarizados = serializers.DecimalField(
        max_digits=12, decimal_places=2, write_only=True, required=False
    )
    litros_procesados = serializers.SerializerMethodField()
    habilitado_envasado = serializers.SerializerMethodField()
    bloqueo_envasado = serializers.SerializerMethodField()

    # El resultado de calidad se calcula, nunca se lee de la base
    # (MODELO_DATOS.md §2.2).
    calidad = serializers.SerializerMethodField()

    class Meta:
        model = Lote
        fields = [
            "id",
            "codigo_lote",
            "codigo_lote_propuesto",
            "op",
            "orden",
            "orden_codigo",
            "producto",
            "producto_nombre",
            "mandante_nombre",
            "vale",
            "vale_codigo",
            "silo_estandarizado_codigo",
            "litros_estandarizados",
            "litros_estandarizados_borrador",
            "litros_procesados",
            "habilitado_envasado",
            "bloqueo_envasado",
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
            "lote_anterior",
            "motivo_corte",
            "motivo_anulacion",
            "motivo_correccion",
            "calidad",
            "es_borrador",
            "abierto_por",
            "abierto_en",
            "actualizado_en",
        ]
        read_only_fields = [
            "ejecucion", "lote_anterior", "motivo_corte", "es_borrador",
            "abierto_por", "abierto_en", "actualizado_en",
        ]
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

    def get_bloqueo_envasado(self, lote):
        from .servicios import bloqueo_calidad_para_envasado

        return bloqueo_calidad_para_envasado(lote)

    def get_habilitado_envasado(self, lote):
        return not self.get_bloqueo_envasado(lote)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        scope = scope_de(request.user)
        productos = Producto.objects.all()
        if scope is None:
            productos = productos.none()
        elif not scope.es_global:
            productos = productos.filter(mandante__empresa_id=scope.empresa_id)
        self.fields["producto"].queryset = productos
        self.fields["equipo"].queryset = filtrar_por_scope(
            Equipo.objects.filter(activo=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        self.fields["orden"].queryset = filtrar_por_scope(
            OrdenProduccion.objects.all(), request.user,
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

        if self.instance is None:
            datos["sucursal"] = sucursal_para_escritura(
                getattr(request, "user", None), datos
            )

        # Una anulación sustituye al borrado físico: conserva el lote, sus
        # análisis, movimientos y genealogía. Por eso exige un motivo nuevo
        # para esta acción; una observación antigua no sirve como justificación.
        if (
            self.instance is not None
            and datos.get("estado") == Lote.Estado.ANULADO
            and self.instance.estado != Lote.Estado.ANULADO
            and not datos.get("motivo_anulacion", "").strip()
        ):
            raise serializers.ValidationError(
                {"motivo_anulacion": "Indica el motivo de la anulación. El historial no se elimina."}
            )
        sucursal = datos.get("sucursal", getattr(self.instance, "sucursal", None))
        producto = datos.get("producto", getattr(self.instance, "producto", None))
        vale = datos.get("vale", getattr(self.instance, "vale", None))
        equipo = datos.get("equipo", getattr(self.instance, "equipo", None))
        orden = datos.get("orden", getattr(self.instance, "orden", None))

        # El vale liberado es la fuente de verdad del producto. Produccion no
        # vuelve a decidir que fabricar: solo toma el saldo preparado por
        # Estandarizacion. Se tolera el campo en clientes antiguos, pero nunca
        # puede contradecir al vale.
        if vale is not None:
            producto_enviado = datos.get("producto")
            if producto_enviado and producto_enviado.pk != vale.producto_id:
                raise serializers.ValidationError({
                    "producto": (
                        f"El vale {vale.codigo} fue estandarizado para "
                        f"{vale.producto.nombre}."
                    )
                })
            datos["producto"] = vale.producto
            producto = vale.producto

        if self.instance is None and orden is not None:
            datos["op"] = orden.codigo
            if producto and orden.producto_id != producto.id:
                raise serializers.ValidationError({"orden": "La orden corresponde a otro producto."})
            if sucursal and orden.sucursal_id != sucursal.id:
                raise serializers.ValidationError({"orden": "La orden pertenece a otra organización."})
        if sucursal and producto and producto.mandante.empresa_id != sucursal.empresa_id:
            raise serializers.ValidationError(
                {"producto": "El producto y la orden deben pertenecer a la misma organización."}
            )

        if self.instance is None and not self.partial and vale is not None:
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
                    {"codigo_lote": "Ya existe ese lote para el producto y la fecha."}
                )

        if self.instance is None:
            return datos

        cambios = [
            campo
            for campo in self.CAMPOS_SUSTANTIVOS
            if campo in datos and datos[campo] != getattr(self.instance, campo)
        ]

        # Un borrador todavía no es un hecho productivo ni tiene una firma
        # que proteger. El autoguardado debe poder completar sus campos sin
        # pedir ``motivo_correccion`` en cada tecla; ese motivo solo aplica a
        # corregir un lote ya abierto en producción.
        if self.instance.estado == Lote.Estado.BORRADOR:
            return datos

        self._rechazar_si_no_puede_declararse_producido(datos)

        if not cambios:
            return datos

        self._rechazar_si_es_final()
        self._rechazar_si_esta_liberado(cambios)

        es_cierre_normal = (
            self.instance.estado == Lote.Estado.EN_PROCESO
            and datos.get("estado") == Lote.Estado.PRODUCIDO
        )
        if not es_cierre_normal:
            from recepcion.models import MovimientoSilo

            campos_de_libro = set(cambios) & set(Lote.CAMPOS_QUE_MUEVEN_LIBRO)
            if campos_de_libro and MovimientoSilo.objects.filter(
                origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                origen_id=self.instance.id,
            ).exists():
                raise serializers.ValidationError({
                    campo: (
                        "Este dato ya quedó reflejado en el movimiento de leche. "
                        "Anula y rehace el lote con motivo."
                    )
                    for campo in campos_de_libro
                })
            if (
                self.instance.estado == Lote.Estado.PRODUCIDO
                and "kg_producidos" in cambios
            ):
                raise serializers.ValidationError({
                    "kg_producidos": (
                        "Los kilos ya cerraron producción e inventario; corrige "
                        "con un ajuste, no editando el lote."
                    )
                })
            if not datos.get("motivo_correccion", "").strip():
                raise serializers.ValidationError({
                    "motivo_correccion": "Indica por qué corriges un paso anterior."
                })

        return datos

    def update(self, instancia, datos_validados):
        motivo = datos_validados.pop("motivo_anulacion", "").strip()
        motivo_correccion = datos_validados.pop("motivo_correccion", "").strip()
        if motivo:
            marca = f"[ANULACIÓN] {motivo}"
            anterior = datos_validados.get("observacion", instancia.observacion).strip()
            datos_validados["observacion"] = "\n".join(
                parte for parte in (anterior, marca) if parte
            )
        antes = {
            campo: getattr(instancia, campo)
            for campo in self.CAMPOS_SUSTANTIVOS
            if campo in datos_validados
        }
        actualizada = super().update(instancia, datos_validados)
        if motivo_correccion:
            def serializable(valor):
                if valor is None or isinstance(valor, (bool, int, float, str)):
                    return valor
                return str(valor)

            diferencias = {
                campo: [serializable(anterior), serializable(getattr(actualizada, campo))]
                for campo, anterior in antes.items()
                if anterior != getattr(actualizada, campo)
            }
            if diferencias:
                CorreccionLote.objects.create(
                    lote=actualizada,
                    usuario=self.context["request"].user,
                    motivo=motivo_correccion,
                    cambios=diferencias,
                )
        return actualizada

    def create(self, datos):
        datos.pop("motivo_anulacion", None)
        datos.pop("motivo_correccion", None)
        litros = datos.pop("litros_estandarizados", None)
        vale = datos.pop("vale", None)
        codigo = datos.pop("codigo_lote")
        datos.pop("codigo_lote_propuesto", None)

        # Los registros históricos pueden no tener vale. La operación normal
        # de planta entra siempre por el servicio transaccional.
        if vale is None:
            return super().create({
                **datos,
                "codigo_lote": codigo,
                "codigo_lote_propuesto": codigo,
            })

        from django.core.exceptions import ValidationError as DjangoValidationError
        from .servicios import abrir_lote_desde_vale

        datos.pop("sucursal", None)
        try:
            return abrir_lote_desde_vale(
                vale=vale,
                codigo_lote=codigo,
                fecha=datos.pop("fecha"),
                litros=litros,
                usuario=getattr(self.context.get("request"), "user", None),
                producto=datos.pop("producto", None),
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

        # El listado trae este dato con una subconsulta correlacionada. Las
        # instancias sueltas (por ejemplo, la respuesta inmediata de crear)
        # conservan el cálculo original como respaldo.
        if hasattr(lote, "litros_procesados_anotados"):
            litros = lote.litros_procesados_anotados
            return float(litros) if litros is not None else None

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
        if lote.estado == Lote.Estado.BORRADOR:
            return {
                "resultado": "sin_analisis", "etiqueta": "Borrador",
                "evaluados": 0, "desviaciones": [], "especificacion_id": None,
            }

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
    recepciones_origen = serializers.SerializerMethodField()
    pallets_resumen = serializers.SerializerMethodField()

    class Meta(LoteSerializer.Meta):
        fields = LoteSerializer.Meta.fields + [
            "analisis",
            "liberacion",
            "consumo_inventario",
            "recepciones_origen",
            "pallets_resumen",
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

        consumos = list(
            ConsumoLoteProduccion.objects.filter(lote_produccion=lote).order_by(
                "registrado_en"
            )
        )
        consumo = next(
            (
                item
                for item in consumos
                if item.fase
                in {
                    ConsumoLoteProduccion.Fase.PROCESO,
                    ConsumoLoteProduccion.Fase.COMPLETO_LEGACY,
                }
            ),
            None,
        )
        consumos_envase = [
            item
            for item in consumos
            if item.fase == ConsumoLoteProduccion.Fase.ENVASADO
        ]

        return {
            "registrado": consumo is not None,
            "registrado_en": consumo.registrado_en if consumo else None,
            "kg_base": consumo.kg_base if consumo else None,
            "pendiente": dominio.consumo_de_inventario_pendiente(lote, consumo),
            "envasado": {
                "operaciones": len(consumos_envase),
                "kg_base_total": sum(
                    (item.kg_base for item in consumos_envase), Decimal("0")
                ),
            },
        }

    def get_pallets_resumen(self, lote):
        return PalletProducto.objects.filter(envase__lote=lote).aggregate(
            total=Count("id"),
            pendientes_calidad=Count(
                "id", filter=Q(estado=PalletProducto.Estado.PENDIENTE_CALIDAD)
            ),
            liberados=Count("id", filter=Q(estado=PalletProducto.Estado.LIBERADO)),
            en_inventario=Count(
                "id", filter=Q(estado=PalletProducto.Estado.EN_INVENTARIO)
            ),
        )

    def get_recepciones_origen(self, lote):
        """Camiones que aportaron al lote, incluidos saldos no atribuibles."""
        from recepcion.models import AtribucionRecepcion, MovimientoSilo

        atribuciones = (
            AtribucionRecepcion.objects.filter(
                movimiento__tipo=MovimientoSilo.Tipo.SALIDA,
                movimiento__origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                movimiento__origen_id=lote.id,
            )
            .select_related("recepcion__vehiculo")
            .order_by("movimiento__fecha_hora", "orden")
        )
        total = sum((item.litros for item in atribuciones), Decimal("0"))
        agrupadas = {}
        for item in atribuciones:
            clave = (item.recepcion_id, item.origen_no_atribuible)
            if clave not in agrupadas:
                agrupadas[clave] = {
                    "recepcion_id": item.recepcion_id,
                    "guia": item.recepcion.guia if item.recepcion_id else None,
                    "camion": (
                        str(item.recepcion.vehiculo)
                        if item.recepcion_id and item.recepcion.vehiculo_id else None
                    ),
                    "origen_no_atribuible": item.origen_no_atribuible,
                    "litros": Decimal("0"),
                }
            agrupadas[clave]["litros"] += item.litros
        resultado = []
        for fila in agrupadas.values():
            fila["porcentaje"] = (
                (fila["litros"] * 100 / total).quantize(Decimal("0.01"))
                if total else Decimal("0")
            )
            resultado.append(fila)
        return resultado


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
