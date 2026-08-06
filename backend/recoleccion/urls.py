from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CargaModuloViewSet, ParadaRutaViewSet, RecoleccionViewSet, RutaRecoleccionViewSet

router = DefaultRouter()
router.register("rutas", RutaRecoleccionViewSet)
router.register("paradas", ParadaRutaViewSet)
router.register("recolecciones", RecoleccionViewSet)
router.register("cargas", CargaModuloViewSet)

urlpatterns = [path("", include(router.urls))]
