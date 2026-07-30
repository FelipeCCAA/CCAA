from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LiberacionViewSet,
    RegistroCalidadViewSet,
    conceder,
    expediente,
    expedientes,
    liberar,
    revisar,
)

router = DefaultRouter()
router.register("registros", RegistroCalidadViewSet)
router.register("liberaciones", LiberacionViewSet)

urlpatterns = [
    path("expedientes/", expedientes, name="expedientes"),
    path("expedientes/<int:lote_id>/", expediente, name="expediente"),
    path("expedientes/<int:lote_id>/liberar/", liberar, name="liberar"),
    path("expedientes/<int:lote_id>/conceder/", conceder, name="conceder"),
    path("expedientes/<int:lote_id>/revisar/", revisar, name="revisar"),
    path("", include(router.urls)),
]
