from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MovimientoSiloViewSet, RecepcionViewSet, ocupacion

router = DefaultRouter()
router.register("recepciones", RecepcionViewSet)
router.register("movimientos", MovimientoSiloViewSet)

urlpatterns = [
    path("ocupacion/", ocupacion, name="ocupacion"),
    path("", include(router.urls)),
]
