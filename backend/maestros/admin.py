from django.contrib import admin

from .models import Especificacion, Mandante, Producto, Silo, Vehiculo


@admin.register(Mandante)
class MandanteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = [
        "nombre",
        "codigo",
        "mandante",
        "familia",
        "naturaleza",
        "unidad_base",
        "activo",
    ]
    list_filter = ["familia", "naturaleza", "mandante", "activo"]
    search_fields = ["nombre", "codigo"]
    autocomplete_fields = ["mandante"]


@admin.register(Silo)
class SiloAdmin(admin.ModelAdmin):
    # Sin columna de ocupación: es un saldo del libro de movimientos.
    list_display = ["codigo", "tipo", "capacidad_l", "activo"]
    list_filter = ["tipo", "activo"]
    search_fields = ["codigo"]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["placa", "numero", "transportista", "capacidad_l", "chofer_am", "chofer_pm", "activo"]
    list_filter = ["activo", "transportista"]
    search_fields = ["placa", "numero", "transportista", "chofer_am", "chofer_pm"]


@admin.register(Especificacion)
class EspecificacionAdmin(admin.ModelAdmin):
    list_display = ["producto", "version", "vigente_desde", "vigente_hasta", "fuente"]
    list_filter = ["producto__familia", "producto__mandante"]
    search_fields = ["producto__nombre", "fuente"]
    autocomplete_fields = ["producto"]
