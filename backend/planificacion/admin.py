from django.contrib import admin

from .models import BalanceDia, BloquePlan, CodigoProduccion, SemanaPlan


class BloquePlanInline(admin.TabularInline):
    model = BloquePlan
    extra = 0
    fields = [
        "dia",
        "equipo",
        "hora_inicio",
        "hora_fin",
        "tipo",
        "codigo",
        "estado_equipo",
        "cantidad_kg",
    ]
    autocomplete_fields = ["codigo"]


class BalanceDiaInline(admin.TabularInline):
    """
    Sin columnas de consumo ni de stock final: son derivados que calcula el
    dominio desde el programa horario. Aquí solo se teclea lo que no sale de
    ningún bloque.
    """

    model = BalanceDia
    extra = 0
    fields = [
        "dia",
        "stock_inicial",
        "recepcion_ccaa",
        "recepcion_nestle",
        "recepcion_punion",
        "trasvasije",
        "crema_disponible_ton",
    ]


@admin.register(CodigoProduccion)
class CodigoProduccionAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "nombre",
        "categoria",
        "rendimiento_lh",
        "producto",
        "mandante",
        "activo",
    ]
    list_filter = ["categoria", "formato", "activo", "mandante"]
    search_fields = ["codigo", "nombre"]
    autocomplete_fields = ["producto", "mandante"]


@admin.register(SemanaPlan)
class SemanaPlanAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "anio",
        "fecha_inicio",
        "estado",
        "publicada_por",
        "publicada_en",
    ]
    list_filter = ["estado", "anio"]
    search_fields = ["codigo", "observacion"]
    inlines = [BalanceDiaInline, BloquePlanInline]


@admin.register(BloquePlan)
class BloquePlanAdmin(admin.ModelAdmin):
    list_display = [
        "semana",
        "dia",
        "equipo",
        "hora_inicio",
        "hora_fin",
        "tipo",
        "codigo",
        "estado_equipo",
    ]
    list_filter = ["equipo", "tipo", "dia"]
    autocomplete_fields = ["equipo"]
    search_fields = ["semana__codigo", "codigo__codigo"]
    autocomplete_fields = ["codigo"]


@admin.register(BalanceDia)
class BalanceDiaAdmin(admin.ModelAdmin):
    list_display = [
        "semana",
        "dia",
        "stock_inicial",
        "recepcion_ccaa",
        "recepcion_nestle",
        "recepcion_punion",
        "trasvasije",
    ]
    list_filter = ["semana"]
