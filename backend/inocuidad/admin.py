from django.contrib import admin

from .models import MonitoreoPPRO, PproLectura


class PproLecturaInline(admin.TabularInline):
    """Las lecturas se cargan desde su monitoreo: así llegan del formato."""

    model = PproLectura
    extra = 0
    fields = ["hora", "resultado", "detalle"]


@admin.register(MonitoreoPPRO)
class MonitoreoPPROAdmin(admin.ModelAdmin):
    # Sin columna de "resuelto": es un derivado de las lecturas y la accion
    # correctiva, no un campo de la tabla.
    list_display = ["lote", "tipo", "equipo", "fecha", "turno", "operador"]
    list_filter = ["tipo", "fecha", "turno"]
    search_fields = ["lote__codigo_lote", "equipo", "accion_correctiva"]
    date_hierarchy = "fecha"
    autocomplete_fields = ["lote"]
    inlines = [PproLecturaInline]


@admin.register(PproLectura)
class PproLecturaAdmin(admin.ModelAdmin):
    list_display = ["monitoreo", "hora", "resultado"]
    list_filter = ["resultado"]
    search_fields = ["monitoreo__lote__codigo_lote"]
