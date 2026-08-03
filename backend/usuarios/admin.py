from django.contrib import admin
from .models import PerfilUsuario


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = ("usuario", "nivel", "area", "cargo", "turno")
    list_filter = ("nivel", "area")
    exclude = ("rol",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "cargo")
    autocomplete_fields = ("usuario",)
