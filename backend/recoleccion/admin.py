from django.contrib import admin

from .models import (
    CargaPredio, Conductor, Modulo, Predio, ProveedorLeche, Recoleccion,
)


@admin.register(ProveedorLeche)
class ProveedorLecheAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rut", "activo", "bloqueado"]
    list_filter = ["activo", "bloqueado"]
    search_fields = ["nombre", "rut"]


@admin.register(Predio)
class PredioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "codigo", "proveedor", "comuna", "activo"]
    list_filter = ["activo", "comuna"]
    search_fields = ["nombre", "codigo", "proveedor__nombre"]


@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = ["nombre", "rut", "telefono", "activo"]
    search_fields = ["nombre", "rut"]


@admin.register(Modulo)
class ModuloAdmin(admin.ModelAdmin):
    list_display = ["vehiculo", "numero", "capacidad_l", "activo"]
    list_filter = ["activo"]


class CargaPredioInline(admin.TabularInline):
    model = CargaPredio
    extra = 0


@admin.register(Recoleccion)
class RecoleccionAdmin(admin.ModelAdmin):
    list_display = ["codigo", "fecha", "conductor", "camion", "estado"]
    list_filter = ["estado", "fecha"]
    search_fields = ["codigo"]
    inlines = [CargaPredioInline]
