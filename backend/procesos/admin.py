from django.contrib import admin

from .models import (
    EjecucionProceso, EntradaProceso, EtapaProceso, EventoProceso, Proceso,
    SalidaProceso,
)
from usuarios.admin_helpers import OrganizacionInternaAdminMixin


class EntradaInline(admin.TabularInline):
    model = EntradaProceso
    extra = 0


class SalidaInline(admin.TabularInline):
    model = SalidaProceso
    extra = 0


@admin.register(EjecucionProceso)
class EjecucionProcesoAdmin(OrganizacionInternaAdminMixin, admin.ModelAdmin):
    exclude = ("sucursal",)
    list_display = ("codigo", "etapa", "estado", "equipo", "responsable", "inicio", "termino")
    list_filter = ("estado", "etapa__tipo")
    search_fields = ("codigo", "etapa__nombre", "responsable__username")
    inlines = (EntradaInline, SalidaInline)
    list_select_related = ("etapa", "equipo", "responsable")


admin.site.register([Proceso, EtapaProceso, EventoProceso])
