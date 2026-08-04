from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Empresa, PerfilUsuario, Sucursal


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    extra = 0
    can_delete = False
    exclude = ("rol",)
    autocomplete_fields = ("empresa", "sucursal")


admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    inlines = (PerfilUsuarioInline,)
    list_display = (
        "username", "email", "first_name", "last_name", "area", "nivel",
        "is_active", "is_superuser",
    )
    list_filter = (
        "is_active", "is_superuser", "perfil__nivel", "perfil__area",
        "perfil__empresa", "perfil__sucursal",
    )
    list_select_related = ("perfil",)

    @admin.display(description="Área", ordering="perfil__area")
    def area(self, usuario):
        perfil = getattr(usuario, "perfil", None)
        return perfil.get_area_display() if perfil else "—"

    @admin.display(description="Nivel", ordering="perfil__nivel")
    def nivel(self, usuario):
        perfil = getattr(usuario, "perfil", None)
        return perfil.get_nivel_display() if perfil else "—"


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "usuario", "administrador_de_area", "nivel", "empresa", "sucursal",
        "area", "cargo", "turno",
    )
    list_filter = ("nivel", "empresa", "sucursal", "area")
    exclude = ("rol",)
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "cargo")
    autocomplete_fields = ("usuario",)
    list_select_related = ("usuario", "empresa", "sucursal")

    @admin.display(boolean=True, description="Admin. de área")
    def administrador_de_area(self, perfil):
        return perfil.es_admin_de_area


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "rut")


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "empresa", "activa")
    list_filter = ("activa", "empresa")
    search_fields = ("nombre", "codigo", "empresa__nombre")
    autocomplete_fields = ("empresa",)
    list_select_related = ("empresa",)

admin.site.site_header = "Administración CCAA"
admin.site.site_title = "CCAA"
admin.site.index_title = "Gestión de la planta"
