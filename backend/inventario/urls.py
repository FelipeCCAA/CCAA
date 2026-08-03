from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CicloCIPViewSet, ConsumoProductoViewSet, InsumoViewSet, calcular_mrp

router = DefaultRouter()
router.register("insumos", InsumoViewSet)
router.register("consumos", ConsumoProductoViewSet)
router.register("cip", CicloCIPViewSet)

urlpatterns = [path("mrp/", calcular_mrp), path("", include(router.urls))]
