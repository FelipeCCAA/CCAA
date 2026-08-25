from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CorridaCondensacionViewSet, CorridaDescremacionViewSet,
    CorridaMantequillaViewSet, EjecucionProcesoViewSet,
    EntradaProcesoViewSet, EtapaProcesoViewSet,
    ProcesoViewSet, RutaProductoViewSet, SalidaProcesoViewSet, trazabilidad,
)

router = DefaultRouter()
router.register("procesos", ProcesoViewSet)
router.register("etapas", EtapaProcesoViewSet)
router.register("rutas-producto", RutaProductoViewSet)
router.register("condensaciones", CorridaCondensacionViewSet)
router.register("descremaciones", CorridaDescremacionViewSet)
router.register("mantequillas", CorridaMantequillaViewSet)
router.register("ejecuciones", EjecucionProcesoViewSet, basename="ejecucion-proceso")
router.register("entradas", EntradaProcesoViewSet)
router.register("salidas", SalidaProcesoViewSet)

urlpatterns = [
    # <str:> y no <int:>: acepta el código de lote además del id, porque el id
    # es de la base y nadie en planta lo conoce.
    path("trazabilidad/lotes/<str:lote>/", trazabilidad, name="trazabilidad-lote"),
    path("", include(router.urls)),
]
