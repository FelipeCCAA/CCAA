from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentoLiberacionViewSet,
    EquipoViewSet,
    EspecificacionViewSet,
    FormatoEnvasadoViewSet,
    MandanteViewSet,
    ProductoViewSet,
    RecetaViewSet,
    SiloViewSet,
    VehiculoViewSet,
    catalogos,
    parametros,
)

router = DefaultRouter()
router.register("mandantes", MandanteViewSet)
router.register("productos", ProductoViewSet)
router.register("recetas", RecetaViewSet)
router.register("especificaciones", EspecificacionViewSet)
router.register("equipos", EquipoViewSet)
router.register("formatos-envasado", FormatoEnvasadoViewSet)
router.register("silos", SiloViewSet)
router.register("vehiculos", VehiculoViewSet)
router.register("documentos", DocumentoLiberacionViewSet)

urlpatterns = [
    path("parametros/", parametros, name="parametros"),
    path("catalogos/", catalogos, name="catalogos"),
    path("", include(router.urls)),
]
