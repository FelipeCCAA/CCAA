from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EspecificacionViewSet,
    MandanteViewSet,
    ProductoViewSet,
    parametros,
)

router = DefaultRouter()
router.register("mandantes", MandanteViewSet)
router.register("productos", ProductoViewSet)
router.register("especificaciones", EspecificacionViewSet)

urlpatterns = [
    path("parametros/", parametros, name="parametros"),
    path("", include(router.urls)),
]
