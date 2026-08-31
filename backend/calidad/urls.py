from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    LiberacionViewSet,
    RegistroCalidadViewSet,
    RegistroEquipoViewSet,
    conceder,
    bloquear,
    documentos_periodicos,
    expediente,
    expedientes,
    liberar,
    enviar_pallets_bodega,
    liberar_resultado_proceso,
    rechazar_resultado_proceso,
    revisar,
)

router = DefaultRouter()
router.register("registros-equipo", RegistroEquipoViewSet)
router.register("registros", RegistroCalidadViewSet)
router.register("liberaciones", LiberacionViewSet)

urlpatterns = [
    path(
        "documentos-periodicos/",
        documentos_periodicos,
        name="documentos-periodicos",
    ),
    path("expedientes/", expedientes, name="expedientes"),
    path("expedientes/<int:lote_id>/", expediente, name="expediente"),
    path("expedientes/<int:lote_id>/liberar/", liberar, name="liberar"),
    path("expedientes/<int:lote_id>/enviar-bodega/", enviar_pallets_bodega, name="enviar-pallets-bodega"),
    path("expedientes/<int:lote_id>/conceder/", conceder, name="conceder"),
    path("expedientes/<int:lote_id>/bloquear/", bloquear, name="bloquear"),
    path("expedientes/<int:lote_id>/revisar/", revisar, name="revisar"),
    path("resultados-proceso/<int:salida_id>/liberar/", liberar_resultado_proceso),
    path("resultados-proceso/<int:salida_id>/rechazar/", rechazar_resultado_proceso),
    path("", include(router.urls)),
]
