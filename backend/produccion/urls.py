from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AnalisisViewSet,
    ControlProcesoLecturaViewSet,
    ControlProcesoViewSet,
    LoteViewSet,
    catalogos_inocuidad,
    resumen,
)

router = DefaultRouter()
router.register("lotes", LoteViewSet)
router.register("analisis", AnalisisViewSet)
router.register("controles", ControlProcesoViewSet)
router.register("lecturas-control", ControlProcesoLecturaViewSet)

urlpatterns = [
    path("resumen/", resumen, name="resumen"),
    path(
        "catalogos-inocuidad/",
        catalogos_inocuidad,
        name="catalogos-inocuidad",
    ),
    path("", include(router.urls)),
]
