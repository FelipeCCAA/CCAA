from django.contrib import admin
from .models import Empresa, PerfilUsuario, Sucursal


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nivel", "empresa", "sucursal", "area", "cargo", "turno")
    list_filter = ("nivel", "empresa", "sucursal", "area")
    exclude = ("rol",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "cargo")
    autocomplete_fields = ("usuario",)


admin.site.register([Empresa, Sucursal])
