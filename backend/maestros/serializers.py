from django.db import transaction
from rest_framework import serializers

from usuarios.models import Empresa
from usuarios.tenancy import scope_de, unica_empresa_activa

from .catalogos import PARAMETROS
from .models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    FormatoEnvasado,
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
    Silo,
    Vehiculo,
)


class RecetaComponenteSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    insumo_nombre = serializers.CharField(source="insumo.nombre", read_only=True)
    fase_etiqueta = serializers.CharField(source="get_fase_display", read_only=True)

    class Meta:
        model = RecetaComponente
        fields = [
            "id", "producto", "producto_nombre", "insumo", "insumo_nombre",
            "fase", "fase_etiqueta", "cantidad", "unidad", "merma",
        ]


class RecetaSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    componentes = RecetaComponenteSerializer(many=True)

    class Meta:
        model = Receta
        fields = [
            "id", "producto", "producto_nombre", "version", "cantidad_base",
            "vigente_desde", "vigente_hasta", "fuente", "componentes",
        ]

    def validate(self, attrs):
        componentes = attrs.get("componentes") or []
        if not componentes:
            raise serializers.ValidationError({"componentes": "Agrega al menos un componente."})
        empresa_id = attrs["producto"].mandante.empresa_id
        scope = _scope_del_contexto(self)
        if scope is not None and not scope.es_global and scope.empresa_id != empresa_id:
            raise serializers.ValidationError({"producto": "El producto no pertenece a tu organización."})
        for indice, componente in enumerate(componentes, start=1):
            producto = componente.get("producto")
            insumo = componente.get("insumo")
            if bool(producto) == bool(insumo):
                raise serializers.ValidationError({
                    "componentes": f"Fila {indice}: selecciona un producto o un insumo."
                })
            if producto and producto.mandante.empresa_id != empresa_id:
                raise serializers.ValidationError({
                    "componentes": f"Fila {indice}: el producto pertenece a otra organización."
                })
            if insumo and insumo.empresa_id != empresa_id:
                raise serializers.ValidationError({
                    "componentes": f"Fila {indice}: el insumo pertenece a otra organización."
                })
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        componentes = validated_data.pop("componentes")
        receta = Receta(**validated_data)
        receta.full_clean()
        receta.save()
        for datos in componentes:
            componente = RecetaComponente(receta=receta, **datos)
            componente.full_clean()
            componente.save()
        return receta


def _scope_del_contexto(serializer):
    request = serializer.context.get("request")
    return scope_de(getattr(request, "user", None)) if request else None


def _restringir_empresa(serializer, campo="empresa"):
    scope = _scope_del_contexto(serializer)
    queryset = Empresa.objects.filter(activa=True)
    if scope is None:
        queryset = queryset.none()
    elif not scope.es_global:
        queryset = queryset.filter(pk=scope.empresa_id)
    serializer.fields[campo].queryset = queryset

    # Y además se resuelve, no solo se restringe. Ninguna pantalla pide la
    # empresa —CCAA es una—, así que sin esto el campo no llega a
    # `validated_data` y **los validadores de unicidad de DRF no se ejecutan**:
    # la restricción la acababa aplicando PostgreSQL, o sea un `IntegrityError`
    # y un error 500 donde correspondía un mensaje. Con el valor puesto, la
    # comprobación ocurre antes de escribir y en todos los entornos.
    serializer.fields[campo].default = lambda: _empresa_del_actor(scope)


def _empresa_del_actor(scope):
    """La empresa en la que escribe este actor, o `None` si es ambiguo."""
    if scope is None:
        return None

    if not scope.es_global:
        return Empresa.objects.filter(pk=scope.empresa_id).first()

    # El superusuario no está acotado a ninguna: se resuelve si hay una sola
    # activa, y si hay varias se deja vacía para que el viewset lo diga.
    return unica_empresa_activa()


def _restringir_relacion_empresa(serializer, campo, queryset, lookup):
    scope = _scope_del_contexto(serializer)
    if scope is None:
        queryset = queryset.none()
    elif not scope.es_global:
        queryset = queryset.filter(**{lookup: scope.empresa_id})
    serializer.fields[campo].queryset = queryset


class MandanteSerializer(serializers.ModelSerializer):
    codigo_cliente_etiqueta = serializers.CharField(
        source="get_codigo_cliente_display", read_only=True
    )

    class Meta:
        model = Mandante
        fields = [
            "id",
            "empresa",
            "nombre",
            "codigo_cliente",
            "codigo_cliente_etiqueta",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _restringir_empresa(self)

        # DRF genera solo un `UniqueTogetherValidator` para esta restricción, y
        # dice «Los campos empresa, codigo_cliente deben formar un conjunto
        # único»: cierto, y sin utilidad para quien lo lee —no nombra al que ya
        # lo tiene ni dice cómo seguir—. Se retira para que la regla la explique
        # `validate()` una sola vez. El de `(empresa, nombre)` se queda: ahí el
        # mensaje genérico sí basta.
        self.validators = [
            validador
            for validador in self.validators
            if set(getattr(validador, "fields", ())) != {"empresa", "codigo_cliente"}
        ]

    def validate(self, attrs):
        """
        «Un código de cliente, un mandante», explicado.

        Dos mandantes que compartan el código sacan productos con SKU idénticos
        —y con el mismo código de lote, que lleva el SKU dentro—. La base lo
        impide con `mandante_unico_por_codigo_cliente`; esto lo cuenta antes, y
        con nombre y apellido.
        """
        codigo = attrs.get(
            "codigo_cliente", getattr(self.instance, "codigo_cliente", "")
        )
        empresa = attrs.get("empresa") or getattr(self.instance, "empresa", None)

        if not codigo or empresa is None:
            return attrs

        ocupado = Mandante.objects.filter(empresa=empresa, codigo_cliente=codigo)

        if self.instance is not None:
            ocupado = ocupado.exclude(pk=self.instance.pk)

        duenio = ocupado.first()

        if duenio is not None:
            raise serializers.ValidationError({
                "codigo_cliente": (
                    f"Ese código de cliente ya es de «{duenio.nombre}». Dos "
                    "mandantes que lo compartan sacan productos con el mismo "
                    "SKU —y con el mismo código de lote, que lleva el SKU "
                    "dentro—. Déjalo vacío si todavía no genera SKU."
                )
            })

        return attrs


class ProductoSerializer(serializers.ModelSerializer):
    mandante_nombre = serializers.CharField(source="mandante.nombre", read_only=True)
    familia_etiqueta = serializers.CharField(source="get_familia_display", read_only=True)

    # El SKU se deriva de los atributos en `Producto.save()`: mandarlo desde
    # el cliente sería teclear un código que puede contradecirlos, que es el
    # defecto que trae el archivo de origen (SKU_PRODUCTOS.md §4.2).
    codigo = serializers.CharField(read_only=True)
    sku_legible = serializers.SerializerMethodField()

    class Meta:
        model = Producto
        fields = [
            "id",
            "codigo",
            "sku_legible",
            "nombre",
            "familia",
            "familia_etiqueta",
            "naturaleza",
            "unidad_base",
            "mandante",
            "mandante_nombre",
            "naturaleza_comercial",
            "categoria",
            "tipo",
            "formato",
            "mercado",
            "variante",
            "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _restringir_relacion_empresa(
            self, "mandante", Mandante.objects.all(), "empresa_id"
        )

    def get_sku_legible(self, producto):
        """
        El SKU descompuesto en sus valores, para poder contrastarlo con los
        atributos sin descomponerlo a mano. `None` si el código no tiene la
        forma de un SKU — que es lo normal en los códigos antiguos.
        """
        from .dominio import describir_sku

        return describir_sku(producto.codigo)

    def validate(self, datos):
        """
        Traduce el rechazo del generador a un error de campo.

        Sin esto, una combinación imposible —producto propio con cliente—
        reventaría con un 500 en vez de decir qué está mal.
        """
        from .dominio import SkuInvalido

        candidato = Producto(**{**self._actuales(), **datos})

        try:
            candidato.sku_derivado()
        except SkuInvalido as e:
            raise serializers.ValidationError({"naturaleza_comercial": str(e)}) from e

        return datos

    def _actuales(self):
        """Lo que ya tiene el producto, para validar un PATCH parcial."""
        if self.instance is None:
            return {}

        campos = [
            f.name
            for f in Producto._meta.concrete_fields
            if f.name != "id"
        ]

        return {campo: getattr(self.instance, campo) for campo in campos}


class EquipoSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Equipo
        fields = [
            "id",
            "codigo",
            "nombre",
            "sigla",
            "tipo",
            "tipo_etiqueta",
            "consume_leche",
            "consume_materiales",
            "orden",
            "activo",
        ]


class FormatoEnvasadoSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    maximo_pallet_kg = serializers.DecimalField(
        max_digits=14, decimal_places=3, read_only=True
    )
    equipos_detalle = EquipoSerializer(source="equipos", many=True, read_only=True)

    class Meta:
        model = FormatoEnvasado
        fields = [
            "id", "producto", "producto_nombre", "codigo", "nombre", "kg_neto",
            "unidades_maximas_pallet", "maximo_pallet_kg", "equipos",
            "equipos_detalle", "activo",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _restringir_relacion_empresa(
            self, "producto", Producto.objects.all(), "mandante__empresa_id"
        )
        scope = _scope_del_contexto(self)
        equipos = Equipo.objects.filter(
            activo=True, tipo__in=[Equipo.Tipo.ENVASADORA, Equipo.Tipo.LINEA]
        )
        if scope is None:
            equipos = equipos.none()
        elif not scope.es_global:
            equipos = equipos.filter(sucursal__empresa_id=scope.empresa_id)
        self.fields["equipos"].queryset = equipos

    def validate(self, attrs):
        producto = attrs.get("producto") or getattr(self.instance, "producto", None)
        equipos = attrs.get("equipos")
        if equipos is None and self.instance is not None:
            equipos = list(self.instance.equipos.all())
        if not equipos:
            raise serializers.ValidationError({
                "equipos": "Selecciona al menos una envasadora o línea autorizada."
            })
        incompatibles = [
            equipo.nombre for equipo in equipos
            if equipo.tipo not in {Equipo.Tipo.ENVASADORA, Equipo.Tipo.LINEA}
            or equipo.sucursal.empresa_id != producto.mandante.empresa_id
        ]
        if incompatibles:
            raise serializers.ValidationError({
                "equipos": "Equipos incompatibles: " + ", ".join(incompatibles)
            })
        candidato = FormatoEnvasado(
            **{
                "producto": producto,
                "codigo": attrs.get("codigo", getattr(self.instance, "codigo", "")),
                "nombre": attrs.get("nombre", getattr(self.instance, "nombre", "")),
                "kg_neto": attrs.get("kg_neto", getattr(self.instance, "kg_neto", None)),
                "unidades_maximas_pallet": attrs.get(
                    "unidades_maximas_pallet",
                    getattr(self.instance, "unidades_maximas_pallet", None),
                ),
                "activo": attrs.get("activo", getattr(self.instance, "activo", True)),
            }
        )
        candidato.clean()
        return attrs

class SiloSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    class Meta:
        # Sin campo de ocupación: es un saldo que se calcula desde el libro de
        # movimientos. Vive en /api/recepcion/ocupacion/.
        model = Silo
        fields = [
            "id", "codigo", "tipo", "tipo_etiqueta", "capacidad_l",
            "estado", "estado_etiqueta", "producto_actual", "temperatura_actual",
            "ultima_limpieza", "activo",
        ]

class VehiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehiculo
        fields = [
            "id",
            "numero",
            "placa",
            "tipo",
            "capacidad_l",
            "transportista",
            "chofer_am",
            "chofer_pm",
            "activo",
        ]

class EspecificacionSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    es_vigente = serializers.SerializerMethodField()

    class Meta:
        model = Especificacion
        fields = [
            "id",
            "producto",
            "producto_nombre",
            "tipo_analisis",
            "version",
            "vigente_desde",
            "vigente_hasta",
            "rangos",
            "fuente",
            "es_vigente",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _restringir_relacion_empresa(
            self,
            "producto",
            Producto.objects.all(),
            "mandante__empresa_id",
        )

    def get_es_vigente(self, especificacion) -> bool:
        """
        Si esta versión es la que hoy manda para su producto.

        **La resuelve el backend con la misma función que el veredicto**
        (`produccion.dominio.especificacion_vigente`). Calcularlo en la pantalla
        pediría reimplementar la regla de solape —gana la vigencia más reciente
        y, a igualdad, la versión mayor—, y una lista que marca «vigente» a una
        versión distinta de la que audita el lote miente justo donde importa.

        Sin ese contexto responde `False` en vez de adivinar: el viewset
        siempre lo provee, pero el serializador se puede usar suelto —desde el
        shell, desde otra vista— y ahí «no sé» tiene que leerse como «no
        afirmo», no como «sí».
        """
        vigentes = self.context.get("vigentes_hoy")

        # `in` y no una comparación de conjuntos: el viewset entrega un objeto
        # que resuelve la pregunta la primera vez que se le hace, para que un
        # alta se responda con el estado de **después** de guardar.
        return especificacion.id in vigentes if vigentes is not None else False

    def validate(self, datos):
        """
        Delega en el `clean()` del modelo para no escribir dos veces las mismas
        reglas. Sin esto, la API podría guardar rangos que el admin rechaza.
        """
        instancia = Especificacion(**{**self._datos_actuales(), **datos})
        instancia.clean()
        return datos

    def _datos_actuales(self):
        if self.instance is None:
            return {}

        return {
            "producto": self.instance.producto,
            "version": self.instance.version,
            "vigente_desde": self.instance.vigente_desde,
            "vigente_hasta": self.instance.vigente_hasta,
            "rangos": self.instance.rangos,
            "fuente": self.instance.fuente,
        }


class DocumentoLiberacionSerializer(serializers.ModelSerializer):
    """
    El catálogo del checklist, con la plantilla de cada formulario.

    La plantilla viaja entera: es lo que la pantalla dibuja. Cambiarla desde
    aquí cambia el formulario, sin desplegar (MODELO_DATOS.md §2.6).
    """

    campos = serializers.SerializerMethodField()
    frecuencia_etiqueta = serializers.CharField(
        source="get_frecuencia_display", read_only=True
    )
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)

    class Meta:
        model = DocumentoLiberacion
        fields = [
            "id",
            "empresa",
            "codigo",
            "area",
            "area_etiqueta",
            "frecuencia",
            "frecuencia_etiqueta",
            "nombre",
            "aplica_a",
            "instruccion",
            "plantilla",
            "campos",
            "fuente",
            "orden",
            "activo",
        ]
        extra_kwargs = {"codigo": {"required": False, "default": ""}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _restringir_empresa(self)

    def get_campos(self, documento):
        """Cuántos campos tiene el formulario. Cero significa solo atestación."""
        return len(documento.plantilla or [])

    def validate(self, datos):
        """
        Delega en el `clean()` del modelo para no escribir dos veces las mismas
        reglas. Sin esto, la API podría guardar una plantilla que el admin
        rechaza, y la pantalla la dibujaría a medias sin avisar a nadie.
        """
        empresa = datos.get("empresa")
        if empresa is not None and not isinstance(empresa, Empresa):
            datos["empresa"] = Empresa.objects.get(pk=empresa)
        instancia = DocumentoLiberacion(**{**self._datos_actuales(), **datos})
        instancia.clean()
        return datos

    def _datos_actuales(self):
        if self.instance is None:
            return {}

        return {
            "codigo": self.instance.codigo,
            "nombre": self.instance.nombre,
            "aplica_a": self.instance.aplica_a,
            "instruccion": self.instance.instruccion,
            "plantilla": self.instance.plantilla,
            "fuente": self.instance.fuente,
            "orden": self.instance.orden,
            "activo": self.instance.activo,
        }


class ParametroSerializer(serializers.Serializer):
    """Catálogo de parámetros medibles, para que el frontend arme formularios."""

    clave = serializers.CharField()
    etiqueta = serializers.CharField()
    unidad = serializers.CharField(allow_blank=True)

    @staticmethod
    def catalogo():
        return [
            {"clave": clave, "etiqueta": meta["etiqueta"], "unidad": meta["unidad"]}
            for clave, meta in PARAMETROS.items()
        ]
