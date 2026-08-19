from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication

from .models import SesionUsuario
from .sesiones import cerrar_sesion, hash_token, motivo_expiracion, registrar_evento


class TokenAuthenticationConScope(TokenAuthentication):
    """Autenticación por una credencial opaca cuyo valor nunca se guarda."""

    RUTAS_CAMBIO_PASSWORD = {
        "/api/usuarios/cambiar-password/",
        "/api/usuarios/logout/",
        "/api/usuarios/yo/",
    }

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if not resultado:
            return None
        usuario, _ = resultado
        perfil = getattr(usuario, "perfil", None)
        if (
            perfil
            and perfil.debe_cambiar_password
            and request.path not in self.RUTAS_CAMBIO_PASSWORD
        ):
            raise exceptions.PermissionDenied({
                "code": "PASSWORD_CHANGE_REQUIRED",
                "error": "Debes cambiar tu contraseña antes de continuar.",
            })
        return resultado

    def authenticate_credentials(self, key):
        digest = hash_token(key)
        try:
            sesion = SesionUsuario.objects.select_related("usuario", "usuario__perfil").get(
                token_hash=digest
            )
        except SesionUsuario.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                {"code": "SESSION_REVOKED", "error": "La sesión ya no es válida."}
            )

        if not sesion.usuario.is_active:
            raise exceptions.AuthenticationFailed(
                {"code": "USER_DISABLED", "error": "La cuenta está desactivada."}
            )

        if sesion.fecha_cierre is not None:
            codigo = (
                "SESSION_EXPIRED"
                if sesion.motivo_cierre
                in (SesionUsuario.MotivoCierre.INACTIVIDAD, SesionUsuario.MotivoCierre.ABSOLUTA)
                else "PASSWORD_CHANGED"
                if sesion.motivo_cierre
                in (SesionUsuario.MotivoCierre.PASSWORD, SesionUsuario.MotivoCierre.RESET_PASSWORD)
                else "SESSION_REVOKED"
            )
            raise exceptions.AuthenticationFailed(
                {"code": codigo, "error": "La sesión terminó. Vuelve a iniciar sesión."}
            )

        ahora = timezone.now()
        expiracion = motivo_expiracion(sesion, ahora)
        if expiracion:
            with transaction.atomic():
                bloqueada = SesionUsuario.objects.select_for_update().get(pk=sesion.pk)
                if cerrar_sesion(bloqueada, expiracion, ahora=ahora):
                    registrar_evento("SESION_EXPIRADA", usuario=sesion.usuario, motivo=expiracion)
            raise exceptions.AuthenticationFailed(
                {"code": "SESSION_EXPIRED", "error": "La sesión expiró por inactividad."}
            )

        intervalo = getattr(settings, "SESSION_ACTIVITY_UPDATE_SECONDS", 120)
        limite = ahora - timezone.timedelta(seconds=max(intervalo, 0))
        if intervalo <= 0 or sesion.ultima_actividad <= limite:
            SesionUsuario.objects.filter(
                pk=sesion.pk, fecha_cierre__isnull=True, ultima_actividad__lte=limite
            ).update(ultima_actividad=ahora)

        return sesion.usuario, sesion
