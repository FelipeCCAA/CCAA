from django.contrib import admin

from .models import (
    Adjunto, AjusteInventario, Alerta, Aprobacion, Bodega, CicloCIP, ConsumoLoteProduccion, DetalleOrdenCompra, EtapaCIP,
    DetalleRecepcionCompra, DetalleSolicitudMaterial, EjecucionMRP,
    DevolucionProduccion, EntregaProduccion, Existencia, InspeccionMaterial, Insumo,
    InsumoProveedor, LiberacionExcepcionalMaterial, LoteInventario,
    MovimientoInventario, NoConformidadMaterial, Notificacion,
    OrdenCompra, PlantillaInspeccion, Proveedor, RecepcionCompra,
    ReservaInventario, ResultadoMRP,
    SolicitudCompra, SolicitudMaterial, Ubicacion,
)


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    # Sin columna de stock: el saldo no vive aquí, se calcula desde el libro
    # de existencias. Mostrar un número de esta tabla lo daría por bueno.
    list_display = ["codigo", "nombre", "area", "unidad", "activo"]
    list_filter = ["area", "activo"]
    search_fields = ["codigo", "nombre"]


@admin.register(CicloCIP)
class CicloCIPAdmin(admin.ModelAdmin):
    list_display = ["objetivo_nombre", "tipo_aseo", "area", "inicio", "estado", "responsable"]
    list_filter = ["tipo_aseo", "tipo_objetivo", "area", "estado"]


@admin.register(LoteInventario)
class LoteInventarioAdmin(admin.ModelAdmin):
    list_display = ["codigo", "insumo", "estado_calidad", "vencimiento", "recibido_en"]
    list_filter = ["estado_calidad", "insumo__categoria"]
    readonly_fields = ["estado_calidad"]


@admin.register(Existencia)
class ExistenciaAdmin(admin.ModelAdmin):
    list_display = ["lote", "ubicacion", "cantidad_fisica", "cantidad_reservada"]
    readonly_fields = ["lote", "ubicacion", "cantidad_fisica", "cantidad_reservada"]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ["fecha", "tipo", "lote", "cantidad", "origen", "destino", "usuario"]
    readonly_fields = [field.name for field in MovimientoInventario._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([
    Proveedor, InsumoProveedor, Bodega, Ubicacion, SolicitudCompra,
    OrdenCompra, DetalleOrdenCompra, RecepcionCompra, DetalleRecepcionCompra,
    InspeccionMaterial, SolicitudMaterial, DetalleSolicitudMaterial,
    ReservaInventario, EntregaProduccion, EjecucionMRP, ResultadoMRP,
    Notificacion,
    Aprobacion,
    PlantillaInspeccion, NoConformidadMaterial, LiberacionExcepcionalMaterial,
    Adjunto, Alerta, AjusteInventario, DevolucionProduccion, ConsumoLoteProduccion,
    EtapaCIP,
])
