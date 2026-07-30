from django.contrib import admin

from .models import Liberacion, RegistroCalidad


@admin.register(RegistroCalidad)
class RegistroCalidadAdmin(admin.ModelAdmin):
    """
    Los valores se ven como JSON crudo a propósito: el formulario dibujado
    desde la plantilla es la pantalla de Calidad, no el admin de Django. Esto
    es la puerta trasera para revisar o corregir un expediente.
    """

    list_display = ["lote", "documento", "estado", "completado_por", "completado_en"]
    list_filter = ["estado", "documento", "lote__producto__familia"]
    search_fields = ["lote__codigo_lote", "documento__nombre", "referencia"]
    autocomplete_fields = ["lote", "documento"]
    date_hierarchy = "completado_en"


@admin.register(Liberacion)
class LiberacionAdmin(admin.ModelAdmin):
    # Sin columna de avance documental ni de resultado de calidad: ambos son
    # derivados que calcula la capa de dominio, no campos de la tabla.
    list_display = ["lote", "estado", "concesion", "autorizada_por", "autorizada_en"]
    list_filter = ["estado", "concesion", "lote__producto__familia"]
    search_fields = ["lote__codigo_lote", "motivo_concesion"]
    autocomplete_fields = ["lote"]
    date_hierarchy = "autorizada_en"
