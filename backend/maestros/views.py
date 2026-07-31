from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeAdministracion, EscribeCalidad

from .models import (
    DocumentoLiberacion,
    Especificacion,
    Mandante,
    Producto,
    Silo,
    Vehiculo,
)
from .serializers import (
    DocumentoLiberacionSerializer,
    EspecificacionSerializer,
    MandanteSerializer,
    ParametroSerializer,
    ProductoSerializer,
    SiloSerializer,
    VehiculoSerializer,
)


class MandanteViewSet(viewsets.ModelViewSet):
    queryset = Mandante.objects.all()
    serializer_class = MandanteSerializer
    permission_classes = [EscribeAdministracion]


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.select_related("mandante")
    serializer_class = ProductoSerializer
    permission_classes = [EscribeAdministracion]

    def get_queryset(self):
        consulta = super().get_queryset()

        familia = self.request.query_params.get("familia")
        if familia:
            consulta = consulta.filter(familia=familia)

        mandante = self.request.query_params.get("mandante")
        if mandante:
            consulta = consulta.filter(mandante_id=mandante)

        return consulta


class EspecificacionViewSet(viewsets.ModelViewSet):
    queryset = Especificacion.objects.select_related("producto")
    serializer_class = EspecificacionSerializer
    permission_classes = [EscribeAdministracion]

    def get_queryset(self):
        consulta = super().get_queryset()

        producto = self.request.query_params.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        return consulta


class SiloViewSet(viewsets.ModelViewSet):
    queryset = Silo.objects.all()
    serializer_class = SiloSerializer
    permission_classes = [EscribeAdministracion]


class VehiculoViewSet(viewsets.ModelViewSet):
    queryset = Vehiculo.objects.all()
    serializer_class = VehiculoSerializer
    permission_classes = [EscribeAdministracion]


class DocumentoLiberacionViewSet(viewsets.ModelViewSet):
    """
    El catálogo del checklist de liberación.

    Lo escribe **Calidad**, no Administración, aunque sea un maestro. El
    módulo promete que Calidad cambia un campo y el formulario cambia sin
    desplegar (MODELO_DATOS.md §2.6); si para eso hubiera que pedírselo a un
    administrador, la promesa quedaría vacía y los formularios volverían a
    envejecer en papel, que es el problema que se vino a resolver.
    """

    queryset = DocumentoLiberacion.objects.all()
    serializer_class = DocumentoLiberacionSerializer
    permission_classes = [EscribeCalidad]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        # `familia` filtra por el contenido de una lista JSON. Es una búsqueda
        # de subcadena, así que se comprueba en Python: son pocos documentos y
        # un `icontains` daría falsos positivos entre familias con nombres
        # parecidos.
        familia = parametros.get("familia")
        if familia:
            consulta = consulta.filter(
                id__in=[d.id for d in consulta if familia in (d.aplica_a or [])]
            )

        activo = parametros.get("activo")
        if activo is not None:
            consulta = consulta.filter(activo=activo.lower() not in ("false", "0"))

        return consulta


@api_view(["GET"])
def parametros(request):
    """Catálogo de parámetros fisicoquímicos medibles."""
    return Response(ParametroSerializer(ParametroSerializer.catalogo(), many=True).data)


@api_view(["GET"])
def catalogos_sku(request):
    """
    Valores que admite cada segmento del SKU, con su etiqueta.

    Se sirven desde aquí en vez de escribirlos en la pantalla: los catálogos
    son la fuente de verdad del generador, y una copia en el frontend
    ofrecería tarde o temprano un valor que el backend rechaza. Es el mismo
    criterio que `/parametros/`.
    """
    from .models import Producto

    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    return Response(
        {
            "naturaleza_comercial": opciones(Producto.NaturalezaComercial.choices),
            "categoria": opciones(Producto.Categoria.choices),
            "tipo": opciones(Producto.TipoProducto.choices),
            "formato": opciones(Producto.Formato.choices),
            "mercado": opciones(Producto.Mercado.choices),
            "cliente": opciones(Mandante.Cliente.choices),
            "familia": opciones(Producto.Familia.choices),
            "naturaleza": opciones(Producto.Naturaleza.choices),
            "unidad_base": opciones(Producto.Unidad.choices),
        }
    )
