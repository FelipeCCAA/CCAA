from rest_framework import serializers

from .catalogos import PARAMETROS
from .models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    Mandante,
    Producto,
    Silo,
    Vehiculo,
)


class MandanteSerializer(serializers.ModelSerializer):
    codigo_cliente_etiqueta = serializers.CharField(
        source="get_codigo_cliente_display", read_only=True
    )

    class Meta:
        model = Mandante
        fields = [
            "id",
            "nombre",
            "codigo_cliente",
            "codigo_cliente_etiqueta",
            "activo",
        ]


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
            "tipo",
            "tipo_etiqueta",
            "consume_leche",
            "orden",
            "activo",
        ]


class SiloSerializer(serializers.ModelSerializer):
    tipo_etiqueta = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        # Sin campo de ocupación: es un saldo que se calcula desde el libro de
        # movimientos. Vive en /api/recepcion/ocupacion/.
        model = Silo
        fields = ["id", "codigo", "tipo", "tipo_etiqueta", "capacidad_l", "activo"]


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
            "version",
            "vigente_desde",
            "vigente_hasta",
            "rangos",
            "fuente",
            "es_vigente",
        ]

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

    def get_campos(self, documento):
        """Cuántos campos tiene el formulario. Cero significa solo atestación."""
        return len(documento.plantilla or [])

    def validate(self, datos):
        """
        Delega en el `clean()` del modelo para no escribir dos veces las mismas
        reglas. Sin esto, la API podría guardar una plantilla que el admin
        rechaza, y la pantalla la dibujaría a medias sin avisar a nadie.
        """
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
