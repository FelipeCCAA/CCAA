from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalisisSiloViewSet, DespachoLecheViewSet, MovimientoSiloViewSet,
    RecepcionViewSet, ocupacion,
    sugerencia_silos,
)

router = DefaultRouter()
router.register("recepciones", RecepcionViewSet)
router.register("movimientos", MovimientoSiloViewSet)
router.register("analisis-silo", AnalisisSiloViewSet)
router.register("despachos-leche", DespachoLecheViewSet)

urlpatterns = [
    path("ocupacion/", ocupacion, name="ocupacion"),
    path("silos/sugerencia/", sugerencia_silos, name="sugerencia-silos"),
    path("", include(router.urls)),
]
