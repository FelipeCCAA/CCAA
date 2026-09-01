from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .catalogos_vista import catalogos
from .views import (
    BalanceDiaViewSet,
    BloquePlanViewSet,
    CapacidadProcesoViewSet,
    CodigoProduccionViewSet,
    MovimientoPlanViewSet,
    SemanaPlanViewSet,
    StockSeguridadPlanViewSet,
    TipoActividadPlanViewSet,
    VersionSemanaPlanViewSet,
    cerrar,
    contraste,
    programa,
    publicar,
    reabrir,
)

router = DefaultRouter()
router.register("codigos", CodigoProduccionViewSet)
router.register("semanas", SemanaPlanViewSet)
router.register("bloques", BloquePlanViewSet)
router.register("balances", BalanceDiaViewSet)
router.register("tipos-actividad", TipoActividadPlanViewSet, basename="tipo-actividad-plan")
router.register("capacidades", CapacidadProcesoViewSet)
router.register("movimientos", MovimientoPlanViewSet)
router.register("stocks-seguridad", StockSeguridadPlanViewSet)
router.register("versiones", VersionSemanaPlanViewSet)

urlpatterns = [
    path("catalogos/", catalogos, name="planificacion-catalogos"),
    path("semanas/<int:semana_id>/programa/", programa, name="programa"),
    path("semanas/<int:semana_id>/publicar/", publicar, name="publicar-semana"),
    path("semanas/<int:semana_id>/reabrir/", reabrir, name="reabrir-semana"),
    path("semanas/<int:semana_id>/cerrar/", cerrar, name="cerrar-semana"),
    path("semanas/<int:semana_id>/contraste/", contraste, name="contraste-semana"),
    path("", include(router.urls)),
]
