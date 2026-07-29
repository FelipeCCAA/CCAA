from django.contrib import admin

from .models import MovimientoSilo, Recepcion


@admin.register(Recepcion)
class RecepcionAdmin(admin.ModelAdmin):
    # Sin columna de veredicto: se calcula desde los controles, no es un campo.
    list_display = ["fecha", "hora", "guia", "procedencia", "tipo_leche", "litros", "silo", "estado"]
    list_filter = ["estado", "procedencia", "tipo_leche", "turno", "silo"]
    search_fields = ["guia", "vehiculo__placa", "observacion"]
    date_hierarchy = "fecha"
    autocomplete_fields = ["vehiculo", "silo", "operador"]


@admin.register(MovimientoSilo)
class MovimientoSiloAdmin(admin.ModelAdmin):
    list_display = ["fecha_hora", "silo", "tipo", "litros", "origen_tipo", "origen_id"]
    list_filter = ["tipo", "silo", "origen_tipo"]
    date_hierarchy = "fecha_hora"
    autocomplete_fields = ["silo"]
