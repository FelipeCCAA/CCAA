from django.contrib import admin

from .models import Especificacion, Mandante, Producto


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


@admin.register(Especificacion)
class EspecificacionAdmin(admin.ModelAdmin):
    list_display = ["producto", "version", "vigente_desde", "vigente_hasta", "fuente"]
    list_filter = ["producto__familia", "producto__mandante"]
    search_fields = ["producto__nombre", "fuente"]
    autocomplete_fields = ["producto"]
