from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from produccion.dominio import especificacion_vigente
from usuarios.permisos import EscribeAdministracion, EscribeCalidad
from usuarios.tenancy import (
    EmpresaTenantViewSetMixin,
    QuerysetTenantMixin,
    SucursalTenantViewSetMixin,
)

from .models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    Mandante,
    Producto,
    Silo,
    Vehiculo,
)
from .serializers import (
    DocumentoLiberacionSerializer,
    EquipoSerializer,
    EspecificacionSerializer,
    MandanteSerializer,
    ParametroSerializer,
    ProductoSerializer,
    SiloSerializer,
    VehiculoSerializer,
)


class MandanteViewSet(EmpresaTenantViewSetMixin, viewsets.ModelViewSet):
    queryset = Mandante.objects.all()
    serializer_class = MandanteSerializer
    permission_classes = [EscribeAdministracion]
    tenant_lookup_empresa = "empresa_id"


class ProductoViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    queryset = Producto.objects.select_related("mandante")
    serializer_class = ProductoSerializer
    permission_classes = [EscribeAdministracion]
    tenant_lookup_empresa = "mandante__empresa_id"

    def get_queryset(self):
        consulta = super().get_queryset()

        familia = self.request.query_params.get("familia")
        if familia:
            consulta = consulta.filter(familia=familia)

        mandante = self.request.query_params.get("mandante")
        if mandante:
            consulta = consulta.filter(mandante_id=mandante)

        return consulta


class VigentesHoy:
    """
    Qué versión de cada especificación manda hoy, resuelto **al usarse**.

    Se calculaba al armar el serializador, o sea **antes** de guardar: la
    respuesta de crear una especificación decía `es_vigente: false` sobre una
    que sí lo era, porque cuando se resolvió el conjunto la fila todavía no
    existía. Se veía bien igual solo porque la pantalla recarga la lista
    después de guardar — un acierto por accidente.

    Aplazarlo hasta la primera consulta lo arregla: en un listado esa primera
    consulta ocurre al serializar la primera fila, y en un alta ocurre después
    del `save()`. El resultado se guarda, así que un listado de cincuenta
    filas sigue costando una sola consulta.
    """

    def __init__(self, queryset):
        self.queryset = queryset
        self._ids: set[int] | None = None

    def __contains__(self, especificacion_id) -> bool:
        if self._ids is None:
            todas = list(self.queryset)
            hoy = timezone.localdate()

            ganadoras = {
                especificacion_vigente(todas, producto_id, hoy, tipo_analisis)
                for producto_id, tipo_analisis in {
                    (e.producto_id, e.tipo_analisis) for e in todas
                }
            }

            self._ids = {e.id for e in ganadoras if e is not None}

        return especificacion_id in self._ids


class EspecificacionViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    """
    Los rangos de calidad de un producto, versionados.

    **La escribe Calidad, no Administración** (desde 2026-08-06). Es la misma
    corrección que ya se hizo con el checklist de liberación y con las recetas:
    una especificación decide qué producto sale como conforme, y quien responde
    por eso es Calidad. Que Administración pudiera moverle los rangos a un
    producto le dejaría cambiar el veredicto de un lote sin medirlo de nuevo.
    """

    queryset = Especificacion.objects.select_related("producto")
    serializer_class = EspecificacionSerializer
    permission_classes = [EscribeCalidad]
    tenant_lookup_empresa = "producto__mandante__empresa_id"

    def get_queryset(self):
        consulta = super().get_queryset()

        producto = self.request.query_params.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        tipo_analisis = self.request.query_params.get("tipo_analisis")
        if tipo_analisis:
            consulta = consulta.filter(tipo_analisis=tipo_analisis)

        return consulta

    def get_serializer_context(self):
        """
        Cuáles son las versiones vigentes hoy, con la misma función que usa el
        veredicto del lote.

        Se resuelve aquí y no fila por fila porque la regla necesita ver todas
        las versiones del producto a la vez —gana la de vigencia más reciente—
        y por fila sería una consulta por especificación.
        """
        contexto = super().get_serializer_context()
        contexto["vigentes_hoy"] = VigentesHoy(self.get_queryset())

        return contexto


class EquipoViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    """
    Máquinas de la planta.

    Las lee cualquier rol —la carta Gantt las necesita para dibujar sus
    filas— y solo Administración las modifica: `consume_leche` cambia cuánta
    leche resta el plan del balance.
    """

    queryset = Equipo.objects.all()
    serializer_class = EquipoSerializer
    permission_classes = [EscribeAdministracion]
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"


class SiloViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    queryset = Silo.objects.all()
    serializer_class = SiloSerializer
    permission_classes = [EscribeAdministracion]
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"


class VehiculoViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    queryset = Vehiculo.objects.all()
    serializer_class = VehiculoSerializer
    permission_classes = [EscribeAdministracion]
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"


class DocumentoLiberacionViewSet(EmpresaTenantViewSetMixin, viewsets.ModelViewSet):
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
    tenant_lookup_empresa = "empresa_id"

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
def catalogos(request):
    """
    Los valores que admite cada campo de opciones de los maestros.

    Se sirven desde aquí en vez de escribirlos en la pantalla: el modelo es la
    fuente de verdad, y una copia en el frontend ofrecería tarde o temprano un
    valor que el backend rechaza. Es el mismo criterio que `/parametros/`.
    """
    from .models import Producto

    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    return Response(
        {
            "silo_tipo": opciones(Silo.Tipo.choices),
            "equipo_tipo": opciones(Equipo.Tipo.choices),
            "area_documento": opciones(DocumentoLiberacion.Area.choices),
            "frecuencia_documento": opciones(DocumentoLiberacion.Frecuencia.choices),
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
