from django.contrib import admin

from .models import FallaEquipo, OrdenTrabajo, PlanPreventivo, RepuestoUtilizado


class RepuestoInline(admin.TabularInline):
    model = RepuestoUtilizado
    extra = 0


@admin.register(OrdenTrabajo)
class OrdenTrabajoAdmin(admin.ModelAdmin):
    list_display = ("numero", "tipo", "estado", "equipo", "prioridad", "responsable", "programada_para")
    list_filter = ("tipo", "estado", "prioridad", "equipo")
    search_fields = ("numero", "descripcion", "equipo__nombre")
    inlines = (RepuestoInline,)
    list_select_related = ("equipo", "responsable")


admin.site.register([PlanPreventivo, FallaEquipo])
