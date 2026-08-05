from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CargaPredioViewSet, ConductorViewSet, ModuloViewSet, PredioViewSet,
    ProveedorLecheViewSet, RecoleccionViewSet,
)

router = DefaultRouter()
router.register("proveedores", ProveedorLecheViewSet)
router.register("predios", PredioViewSet)
router.register("conductores", ConductorViewSet)
router.register("modulos", ModuloViewSet)
router.register("recolecciones", RecoleccionViewSet, basename="recoleccion")
router.register("cargas", CargaPredioViewSet, basename="carga-predio")

urlpatterns = [path("", include(router.urls))]
