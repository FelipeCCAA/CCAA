from rest_framework import serializers

from .catalogos import PARAMETROS
from .models import (
    DocumentoLiberacion,
    Especificacion,
    Mandante,
    Producto,
    Silo,
    Vehiculo,
)


class MandanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mandante
        fields = ["id", "nombre", "activo"]


class ProductoSerializer(serializers.ModelSerializer):
    mandante_nombre = serializers.CharField(source="mandante.nombre", read_only=True)
    familia_etiqueta = serializers.CharField(source="get_familia_display", read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id",
            "codigo",
            "nombre",
            "familia",
            "familia_etiqueta",
            "naturaleza",
            "unidad_base",
            "mandante",
            "mandante_nombre",
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
        ]

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

    class Meta:
        model = DocumentoLiberacion
        fields = [
            "id",
            "codigo",
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
