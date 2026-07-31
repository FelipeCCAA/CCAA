from django.contrib import admin

from .models import CicloCIP, ConsumoProducto, Insumo


@admin.register(Insumo)
class InsumoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "area", "stock_actual", "unidad", "activo"]
    list_filter = ["area", "activo"]
    search_fields = ["codigo", "nombre"]


@admin.register(ConsumoProducto)
class ConsumoProductoAdmin(admin.ModelAdmin):
    list_display = ["producto", "insumo", "cantidad_por_kg"]


@admin.register(CicloCIP)
class CicloCIPAdmin(admin.ModelAdmin):
    list_display = ["equipo", "area", "inicio", "estado", "responsable"]
    list_filter = ["area", "estado"]
