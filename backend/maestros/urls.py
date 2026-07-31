from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    DocumentoLiberacionViewSet,
    EspecificacionViewSet,
    MandanteViewSet,
    ProductoViewSet,
    SiloViewSet,
    VehiculoViewSet,
    catalogos_sku,
    parametros,
)

router = DefaultRouter()
router.register("mandantes", MandanteViewSet)
router.register("productos", ProductoViewSet)
router.register("especificaciones", EspecificacionViewSet)
router.register("silos", SiloViewSet)
router.register("vehiculos", VehiculoViewSet)
router.register("documentos", DocumentoLiberacionViewSet)

urlpatterns = [
    path("parametros/", parametros, name="parametros"),
    path("catalogos-sku/", catalogos_sku, name="catalogos-sku"),
    path("", include(router.urls)),
]
