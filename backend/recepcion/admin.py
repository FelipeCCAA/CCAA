from django.contrib import admin

from .models import (
    AnalisisSilo, BusquedaProveedor, ControlInhibidores, ModuloRecepcion,
    MovimientoSilo, Recepcion,
)


class ModuloRecepcionInline(admin.TabularInline):
    model = ModuloRecepcion
    extra = 1


class BusquedaProveedorInline(admin.TabularInline):
    model = BusquedaProveedor
    extra = 0


@admin.register(ControlInhibidores)
class ControlInhibidoresAdmin(admin.ModelAdmin):
    list_display = ("recepcion", "metodo", "resultado", "tiras_usadas", "hora_lectura")
    list_filter = ("metodo", "resultado")
    inlines = [BusquedaProveedorInline]


@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    # Sin columna de veredicto: se calcula desde los controles, no es un campo.
    list_display = [
        "fecha",
        "hora",
        "guia",
        "codigo_muestra",
        "tipo_leche",
        "litros",
        "silo",
        "estado",
    ]
    list_filter = ["estado", "procedencia", "tipo_leche", "turno", "silo"]
    search_fields = ["guia", "codigo_muestra", "vehiculo__placa", "observacion"]
    date_hierarchy = "fecha"
    autocomplete_fields = [
        "vehiculo",
        "silo",
        "operador",
        "muestreado_por",
        "calidad_por",
        "silo_asignado_por",
    ]
    readonly_fields = [
        "muestreado_por",
        "muestreado_en",
        "calidad_por",
        "calidad_en",
        "silo_asignado_por",
        "silo_asignado_en",
    ]
    inlines = [ModuloRecepcionInline]


@admin.register(MovimientoSilo)
class MovimientoSiloAdmin(admin.ModelAdmin):
    list_display = ["fecha_hora", "silo", "tipo", "litros", "origen_tipo", "origen_id"]
    list_filter = ["tipo", "silo", "origen_tipo"]
    date_hierarchy = "fecha_hora"
    autocomplete_fields = ["silo"]


@admin.register(AnalisisSilo)
class AnalisisSiloAdmin(admin.ModelAdmin):
    list_display = ("silo", "tomado_en", "grasa", "sng", "ph", "acidez", "analista")
    list_filter = ("silo", "certificada", "procedencia")
    date_hierarchy = "tomado_en"
    search_fields = ("silo__codigo", "observacion")
    autocomplete_fields = ("silo",)
