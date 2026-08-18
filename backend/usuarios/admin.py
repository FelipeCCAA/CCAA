from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import AreaDePerfil, Empresa, IntentoAcceso, PerfilUsuario
from .throttling import (
    LoginUsuarioThrottle,
    clave_de_ip,
    clave_de_usuario,
    desbloquear,
    estado_del_limite,
)


class PerfilUsuarioInline(admin.StackedInline):
    model = PerfilUsuario
    extra = 0
    can_delete = False
    autocomplete_fields = ("empresa",)
    exclude = ("rol", "sucursal", "alcance")


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
        "perfil__empresa",
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


class AreaDePerfilInline(admin.TabularInline):
    """
    Las otras áreas en las que trabaja esta persona.

    Va aquí dentro y no en su propia pantalla porque no es una entidad del
    negocio: es un atributo del perfil, y editarlo aparte obligaría a buscar dos
    veces a la misma persona.
    """

    model = AreaDePerfil
    extra = 0
    verbose_name = "Área adicional"
    verbose_name_plural = "Otras áreas en las que trabaja"


@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "usuario", "administrador_de_area", "nivel", "empresa",
        "area", "otras_areas", "cargo", "turno",
    )
    list_filter = ("nivel", "empresa", "area")
    exclude = ("rol", "sucursal", "alcance")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "cargo")
    autocomplete_fields = ("usuario",)
    list_select_related = ("usuario", "empresa")
    inlines = [AreaDePerfilInline]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("areas_adicionales")

    @admin.display(boolean=True, description="Admin. de área")
    def administrador_de_area(self, perfil):
        return perfil.es_admin_de_area

    @admin.display(description="Otras áreas")
    def otras_areas(self, perfil):
        return ", ".join(
            extra.get_area_display() for extra in perfil.areas_adicionales.all()
        ) or "—"


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "rut", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "rut")


admin.site.site_header = "Administración CCAA"
admin.site.site_title = "CCAA"
admin.site.index_title = "Gestión de la planta"
@admin.register(IntentoAcceso)
class IntentoAccesoAdmin(admin.ModelAdmin):
    """
    Los intentos de acceso, de solo lectura.

    Es un registro de hechos: poder editarlo o crearlo a mano lo invalidaría
    como evidencia, que es lo único para lo que sirve.
    """

    list_display = ("fecha_hora", "usuario", "ip", "exito", "motivo", "limite")
    list_filter = ("exito", "motivo", "fecha_hora")
    search_fields = ("usuario", "ip")
    date_hierarchy = "fecha_hora"
    actions = ["desbloquear_usuario", "desbloquear_direccion"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Límite")
    def limite(self, intento):
        """
        Cómo va el contador de esa cuenta ahora mismo.

        Se muestra aquí porque es donde alguien mira cuando le dicen «no puedo
        entrar»: sin esto habría que adivinar si el rechazo fue por contraseña
        o por bloqueo, que son dos problemas con dos soluciones distintas.
        """
        estado = estado_del_limite(
            clave_de_usuario(intento.usuario), LoginUsuarioThrottle()
        )

        if estado["bloqueado"]:
            return f"BLOQUEADO {estado['usados']}/{estado['limite']}"

        return f"{estado['usados']}/{estado['limite']}"

    # Las dos acciones se declaran sin `allowed_permissions`: este modelo no
    # admite cambios —es un registro de hechos— así que exigir permiso de
    # cambio las escondería siempre. Quien puede ver esta pantalla es
    # administrador, y desbloquear no altera el registro: solo borra un
    # contador de la caché.

    @admin.action(description="Desbloquear el acceso de estas cuentas")
    def desbloquear_usuario(self, request, queryset):
        nombres = {intento.usuario for intento in queryset if intento.usuario}
        soltadas = [n for n in nombres if desbloquear(clave_de_usuario(n))]

        self._informar(request, soltadas, nombres, "cuenta", "cuentas")

    @admin.action(description="Desbloquear el acceso de estas direcciones")
    def desbloquear_direccion(self, request, queryset):
        direcciones = {intento.ip for intento in queryset if intento.ip}
        soltadas = [d for d in direcciones if desbloquear(clave_de_ip(d))]

        self._informar(request, soltadas, direcciones, "dirección", "direcciones")

    def _informar(self, request, soltadas, todas, singular, plural):
        if soltadas:
            self.message_user(
                request,
                f"Desbloqueadas {len(soltadas)} {plural}: {', '.join(sorted(soltadas))}.",
                messages.SUCCESS,
            )

        # Que no estuvieran bloqueadas no es un fallo, pero decirlo evita que
        # alguien siga buscando un bloqueo que ya había caducado solo.
        sin_bloqueo = sorted(set(todas) - set(soltadas))

        if sin_bloqueo:
            self.message_user(
                request,
                f"Sin bloqueo activo: {', '.join(sin_bloqueo)}. "
                f"Si esa {singular} no puede entrar, el motivo es otro.",
                messages.INFO,
            )
