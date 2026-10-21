from django.contrib import admin, messages
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, Permission, User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters

from .models import (
    AreaDePerfil, Empresa, EventoSeguridad, IntentoAcceso, PerfilUsuario,
    SesionUsuario,
)
from .permisos_industriales import permisos_asignables_por
from .sesiones import revocar_sesiones
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

    def get_min_num(self, request, obj=None, **kwargs):
        return 1 if obj is None else 0

    def get_extra(self, request, obj=None, **kwargs):
        return 1 if obj is None else 0

    def get_formset(self, request, obj=None, **kwargs):
        kwargs["validate_min"] = obj is None
        return super().get_formset(request, obj, **kwargs)


def _identidad_guardada(usuario_id):
    """Lee permisos y perfil de BD tras guardar también los inlines y M2M."""
    usuario = User.objects.get(pk=usuario_id)
    perfil = PerfilUsuario.objects.filter(usuario_id=usuario_id).values(
        "area", "nivel", "rol",
    ).first()
    return {
        "activo": usuario.is_active,
        "staff": usuario.is_staff,
        "superusuario": usuario.is_superuser,
        "password": usuario.password,
        "perfil": perfil,
        "permisos": frozenset(usuario.user_permissions.values_list("pk", flat=True)),
        "grupos": frozenset(usuario.groups.values_list("pk", flat=True)),
    }


def _exigir_ambito_admin(request, identidad, *, antes=False):
    """Aplica al panel el mismo ámbito de trabajador que protege la API."""
    if request.user.is_superuser:
        return
    actor = getattr(request.user, "perfil", None)
    if not request.user.is_staff or not actor or not actor.es_admin_de_area:
        raise PermissionDenied("No puedes administrar esa cuenta.")
    if identidad["superusuario"]:
        raise PermissionDenied("No puedes administrar una cuenta superusuario.")
    perfil = identidad["perfil"]
    if antes and perfil and perfil["nivel"] == PerfilUsuario.Nivel.ADMIN:
        raise PermissionDenied("No puedes modificar a otro administrador.")
    if actor.area != PerfilUsuario.Area.ADMINISTRACION:
        if not perfil or perfil["area"] != actor.area:
            raise PermissionDenied("La cuenta está fuera de tu área.")


def _confirmar_identidad_admin(
    request, usuario_id, anterior, puede_cambiar_roles, permisos_asignables,
):
    """Autoriza la identidad efectiva y cierra tokens dentro de la misma transacción."""
    actual = _identidad_guardada(usuario_id)
    perfil_antes = anterior["perfil"] if anterior else None
    perfil_ahora = actual["perfil"]
    area_antes = perfil_antes["area"] if perfil_antes else ""
    nivel_antes = perfil_antes["nivel"] if perfil_antes else PerfilUsuario.Nivel.TRABAJADOR
    rol_antes = perfil_antes["rol"] if perfil_antes else ""
    area_ahora = perfil_ahora["area"] if perfil_ahora else ""
    nivel_ahora = perfil_ahora["nivel"] if perfil_ahora else PerfilUsuario.Nivel.TRABAJADOR
    rol_ahora = perfil_ahora["rol"] if perfil_ahora else ""

    _exigir_ambito_admin(request, actual)
    if not request.user.is_superuser:
        actor = request.user.perfil
        if actor.area != PerfilUsuario.Area.ADMINISTRACION and (
            not anterior
            or area_antes != area_ahora
            or nivel_antes != nivel_ahora
            or rol_antes != rol_ahora
        ):
            raise PermissionDenied("No puedes cambiar el área ni el nivel del trabajador.")
        grupos_antes = anterior["grupos"] if anterior else frozenset()
        if actual["grupos"] != grupos_antes:
            raise PermissionDenied("Solo un superusuario puede asignar grupos.")
        permisos_antes = anterior["permisos"] if anterior else frozenset()
        agregados = actual["permisos"] - permisos_antes
        for permiso in Permission.objects.filter(pk__in=agregados).select_related("content_type"):
            if (
                permiso.content_type.app_label != "usuarios"
                or permiso.content_type.model != "perfilusuario"
                or permiso.codename not in permisos_asignables
            ):
                raise PermissionDenied("No puedes asignar ese permiso.")
        if actual["superusuario"] and (not anterior or not anterior["superusuario"]):
            raise PermissionDenied("Solo un superusuario puede conceder superusuario.")
        administracion_nueva = not anterior and (
            actual["staff"] or actual["superusuario"]
            or area_ahora == PerfilUsuario.Area.ADMINISTRACION
            or nivel_ahora == PerfilUsuario.Nivel.ADMIN
        )
        cambia_rol = bool(anterior) and (
            area_antes != area_ahora or nivel_antes != nivel_ahora
            or rol_antes != rol_ahora
            or (not anterior["staff"] and actual["staff"])
        )
        if (administracion_nueva or cambia_rol) and not puede_cambiar_roles:
            raise PermissionDenied("No tienes permiso para cambiar roles o área.")

    if not anterior:
        return
    desactivado = anterior["activo"] and not actual["activo"]
    cambio_password = anterior["password"] != actual["password"]
    identidad_cambiada = (
        desactivado or cambio_password
        or anterior["staff"] != actual["staff"]
        or anterior["superusuario"] != actual["superusuario"]
        or perfil_antes != perfil_ahora
        or anterior["permisos"] != actual["permisos"]
        or anterior["grupos"] != actual["grupos"]
    )
    if identidad_cambiada:
        motivo = (
            SesionUsuario.MotivoCierre.DESACTIVACION if desactivado
            else SesionUsuario.MotivoCierre.RESET_PASSWORD if cambio_password
            else SesionUsuario.MotivoCierre.ADMIN
        )
        revocar_sesiones(User.objects.get(pk=usuario_id), motivo, actor=request.user)


def _miembros_grupos_bloqueados(grupos_ids):
    ids = list(User.objects.filter(groups__pk__in=grupos_ids).order_by("pk")
               .values_list("pk", flat=True).distinct())
    return list(User.objects.select_for_update().filter(pk__in=ids).order_by("pk"))


admin.site.unregister(Group)


@admin.register(Group)
class GrupoAdmin(GroupAdmin):
    """Un cambio de permisos del grupo invalida las sesiones de sus miembros."""

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST" or object_id is None:
            return super().changeform_view(request, object_id, form_url, extra_context)
        if not request.user.is_superuser:
            raise PermissionDenied("Solo un superusuario puede cambiar grupos.")
        with transaction.atomic():
            grupo = Group.objects.select_for_update().filter(pk=object_id).first()
            miembros = _miembros_grupos_bloqueados([grupo.pk]) if grupo else []
            anteriores = set(grupo.permissions.values_list("pk", flat=True)) if grupo else set()
            respuesta = super().changeform_view(request, object_id, form_url, extra_context)
            if grupo and anteriores != set(grupo.permissions.values_list("pk", flat=True)):
                for usuario in miembros:
                    revocar_sesiones(
                        usuario, SesionUsuario.MotivoCierre.ADMIN, actor=request.user,
                    )
            return respuesta

    def delete_model(self, request, obj):
        if not request.user.is_superuser:
            raise PermissionDenied("Solo un superusuario puede borrar grupos.")
        with transaction.atomic():
            Group.objects.select_for_update().get(pk=obj.pk)
            miembros = _miembros_grupos_bloqueados([obj.pk])
            super().delete_model(request, obj)
            for usuario in miembros:
                revocar_sesiones(
                    usuario, SesionUsuario.MotivoCierre.ADMIN, actor=request.user,
                )

    def delete_queryset(self, request, queryset):
        if not request.user.is_superuser:
            raise PermissionDenied("Solo un superusuario puede borrar grupos.")
        with transaction.atomic():
            ids = list(queryset.order_by("pk").values_list("pk", flat=True))
            list(Group.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            miembros = _miembros_grupos_bloqueados(ids)
            super().delete_queryset(request, queryset)
            for usuario in miembros:
                revocar_sesiones(
                    usuario, SesionUsuario.MotivoCierre.ADMIN, actor=request.user,
                )


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

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        request._op06_usuario_guardado_id = obj.pk

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST":
            return super().changeform_view(request, object_id, form_url, extra_context)
        with transaction.atomic():
            grupos = []
            for valor in request.POST.getlist("groups"):
                try:
                    grupos.append(int(valor))
                except ValueError:
                    pass  # El formulario informa un grupo inválido.
            list(Group.objects.select_for_update().filter(pk__in=grupos).order_by("pk"))
            puede_roles = request.user.is_superuser or request.user.has_perm("usuarios.change_roles")
            asignables = permisos_asignables_por(request.user)
            es_alta = object_id is None or "_saveasnew" in request.POST
            anterior = None
            if not es_alta:
                objetivo = User.objects.select_for_update().filter(pk=object_id).first()
                if objetivo:
                    anterior = _identidad_guardada(objetivo.pk)
                    _exigir_ambito_admin(request, anterior, antes=True)
            request._op06_usuario_guardado_id = None
            respuesta = super().changeform_view(request, object_id, form_url, extra_context)
            usuario_id = request._op06_usuario_guardado_id
            if usuario_id:
                if es_alta:
                    if not PerfilUsuario.objects.filter(usuario_id=usuario_id).exists():
                        raise PermissionDenied("El alta requiere un perfil de usuario.")
                    PerfilUsuario.objects.filter(usuario_id=usuario_id).update(
                        debe_cambiar_password=True,
                    )
                _confirmar_identidad_admin(
                    request, usuario_id, anterior, puede_roles, asignables,
                )
            return respuesta

    @method_decorator(sensitive_post_parameters())
    def user_change_password(self, request, id, form_url=""):
        if request.method != "POST":
            return super().user_change_password(request, id, form_url)
        with transaction.atomic():
            usuario = User.objects.select_for_update().filter(pk=id).first()
            anterior = _identidad_guardada(usuario.pk) if usuario else None
            if anterior:
                _exigir_ambito_admin(request, anterior, antes=True)
            if not request.user.is_superuser and not request.user.has_perm(
                "usuarios.reset_password"
            ):
                raise PermissionDenied("No tienes permiso para restablecer contraseñas.")
            respuesta = super().user_change_password(request, id, form_url)
            if usuario and anterior["password"] != User.objects.get(pk=id).password:
                if usuario.pk != request.user.pk:
                    PerfilUsuario.objects.filter(usuario_id=id).update(
                        debe_cambiar_password=True,
                    )
                _confirmar_identidad_admin(
                    request, usuario.pk, anterior,
                    request.user.is_superuser or request.user.has_perm("usuarios.change_roles"),
                    permisos_asignables_por(request.user),
                )
            return respuesta

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

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        return (*campos, "usuario") if obj else campos

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        request._op06_perfil_guardado_id = obj.pk

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        if request.method != "POST":
            return super().changeform_view(request, object_id, form_url, extra_context)
        if "_saveasnew" in request.POST:
            raise PermissionDenied("No puedes copiar un perfil a otra cuenta.")
        with transaction.atomic():
            puede_roles = request.user.is_superuser or request.user.has_perm("usuarios.change_roles")
            asignables = permisos_asignables_por(request.user)
            previo = PerfilUsuario.objects.filter(pk=object_id).values("usuario_id").first() if object_id else None
            ids = {previo["usuario_id"]} if previo else set()
            if not previo:
                try:
                    ids.add(int(request.POST.get("usuario", "")))
                except ValueError:
                    pass  # El formulario informa un usuario ausente o inválido.
            anteriores = {}
            for usuario_id in sorted(ids):
                usuario = User.objects.select_for_update().filter(pk=usuario_id).first()
                if usuario:
                    anteriores[usuario_id] = _identidad_guardada(usuario_id)
                    _exigir_ambito_admin(
                        request, anteriores[usuario_id], antes=bool(previo),
                    )
            request._op06_perfil_guardado_id = None
            respuesta = super().changeform_view(request, object_id, form_url, extra_context)
            perfil_id = request._op06_perfil_guardado_id
            if perfil_id:
                perfil = PerfilUsuario.objects.get(pk=perfil_id)
                if not previo:
                    PerfilUsuario.objects.filter(pk=perfil_id).update(
                        debe_cambiar_password=True,
                    )
                for usuario_id in sorted(ids | {perfil.usuario_id}):
                    _confirmar_identidad_admin(
                        request, usuario_id, anteriores.get(usuario_id), puede_roles,
                        asignables,
                    )
            return respuesta

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


class SoloLecturaAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SesionUsuario)
class SesionUsuarioAdmin(SoloLecturaAdmin):
    exclude = ("token_hash",)
    list_display = (
        "usuario", "fecha_inicio", "ultima_actividad", "fecha_cierre", "motivo_cierre", "ip"
    )
    list_filter = ("motivo_cierre", "fecha_cierre")
    search_fields = ("usuario__username", "identificador", "ip")
    list_select_related = ("usuario", "cerrada_por")


@admin.register(EventoSeguridad)
class EventoSeguridadAdmin(SoloLecturaAdmin):
    list_display = ("fecha", "accion", "usuario", "actor", "ip", "motivo")
    list_filter = ("accion", "fecha")
    search_fields = ("usuario__username", "actor__username", "ip", "motivo")
    list_select_related = ("usuario", "actor")
