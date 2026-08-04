from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    EjecucionProcesoViewSet, EntradaProcesoViewSet, EtapaProcesoViewSet,
    ProcesoViewSet, SalidaProcesoViewSet, trazabilidad,
)

router = DefaultRouter()
router.register("procesos", ProcesoViewSet)
router.register("etapas", EtapaProcesoViewSet)
router.register("ejecuciones", EjecucionProcesoViewSet, basename="ejecucion-proceso")
router.register("entradas", EntradaProcesoViewSet)
router.register("salidas", SalidaProcesoViewSet)

urlpatterns = [
    path("trazabilidad/lotes/<int:lote_id>/", trazabilidad, name="trazabilidad-lote"),
    path("", include(router.urls)),
]
