from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    catalogos,
    AdjuntoViewSet, AjusteInventarioViewSet, AlertaViewSet, BodegaViewSet, CicloCIPViewSet,
    DetalleOrdenCompraViewSet,
    DetalleSolicitudCompraViewSet, DetalleSolicitudMaterialViewSet,
    DevolucionProduccionViewSet, EjecucionMRPViewSet, ExistenciaViewSet,
    InspeccionMaterialViewSet, InsumoProveedorViewSet, InsumoViewSet,
    LoteInventarioViewSet, MovimientoViewSet, NotificacionViewSet,
    LiberacionExcepcionalViewSet, NoConformidadViewSet, OrdenCompraViewSet,
    PlantillaInspeccionViewSet, ProveedorViewSet, RecepcionCompraViewSet,
    SolicitudCompraViewSet, SolicitudMaterialViewSet, UbicacionViewSet,
    calcular_mrp,
)

router = DefaultRouter()
router.register("insumos", InsumoViewSet)
router.register("cip", CicloCIPViewSet)
router.register("proveedores", ProveedorViewSet)
router.register("insumo-proveedores", InsumoProveedorViewSet)
router.register("bodegas", BodegaViewSet)
router.register("ubicaciones", UbicacionViewSet)
router.register("lotes", LoteInventarioViewSet)
router.register("existencias", ExistenciaViewSet)
router.register("movimientos", MovimientoViewSet)
router.register("ajustes", AjusteInventarioViewSet)
router.register("devoluciones-produccion", DevolucionProduccionViewSet)
router.register("solicitudes-compra", SolicitudCompraViewSet)
router.register("ordenes-compra", OrdenCompraViewSet)
router.register("detalles-solicitud-compra", DetalleSolicitudCompraViewSet)
router.register("detalles-orden-compra", DetalleOrdenCompraViewSet)
router.register("recepciones-compra", RecepcionCompraViewSet)
router.register("inspecciones", InspeccionMaterialViewSet)
router.register("mrq", SolicitudMaterialViewSet)
router.register("detalles-mrq", DetalleSolicitudMaterialViewSet)
router.register("notificaciones", NotificacionViewSet, basename="notificaciones")
router.register("ejecuciones-mrp", EjecucionMRPViewSet)
router.register("plantillas-inspeccion", PlantillaInspeccionViewSet)
router.register("no-conformidades", NoConformidadViewSet)
router.register("liberaciones-excepcionales", LiberacionExcepcionalViewSet)
router.register("adjuntos", AdjuntoViewSet)
router.register("alertas", AlertaViewSet)

urlpatterns = [
    path("mrp/", calcular_mrp),
    path("catalogos/", catalogos),
    path("", include(router.urls)),
]
