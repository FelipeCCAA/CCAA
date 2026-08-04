from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    FallaEquipoViewSet, OrdenTrabajoViewSet, PlanPreventivoViewSet,
    RepuestoUtilizadoViewSet, resumen,
)

router = DefaultRouter()
router.register("planes", PlanPreventivoViewSet)
router.register("ordenes", OrdenTrabajoViewSet, basename="orden-trabajo")
router.register("fallas", FallaEquipoViewSet)
router.register("repuestos", RepuestoUtilizadoViewSet)

urlpatterns = [path("resumen/", resumen), path("", include(router.urls))]
