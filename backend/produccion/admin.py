from django.contrib import admin

from .models import Analisis, Lote


class AnalisisInline(admin.TabularInline):
    """Los análisis se cargan desde el lote: es como llegan desde el laboratorio."""

    model = Analisis
    extra = 0
    fields = ["fecha", "muestra", "valores", "especificacion", "observacion"]
    autocomplete_fields = ["especificacion"]


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    # Sin columna de resultado de calidad: es un valor derivado que se calcula
    # en la capa de dominio (fase siguiente), no un campo de la tabla.
    list_display = [
        "codigo_lote",
        "producto",
        "fecha",
        "linea",
        "turno",
        "kg_producidos",
        "estado",
    ]
    list_filter = ["estado", "linea", "turno", "producto__familia", "producto__mandante"]
    search_fields = ["codigo_lote", "op", "producto__nombre"]
    date_hierarchy = "fecha"
    autocomplete_fields = ["producto"]
    inlines = [AnalisisInline]


@admin.register(Analisis)
class AnalisisAdmin(admin.ModelAdmin):
    list_display = ["lote", "fecha", "muestra", "especificacion"]
    list_filter = ["fecha", "lote__producto__familia"]
    search_fields = ["lote__codigo_lote", "muestra"]
    date_hierarchy = "fecha"
    autocomplete_fields = ["lote", "especificacion"]
