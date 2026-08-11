from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class TokenAuthenticationConScope(TokenAuthentication):
    """
    Autentica, trae el scope tenant en la misma consulta del token y **le pone
    plazo**.

    El token de DRF no caduca solo: una vez emitido sirve para siempre.
    Combinado con un login sin límite de intentos —el estado anterior— el
    vector completo era «fuerza bruta sin freno → acceso perpetuo». El límite
    ya está; el plazo cierra la otra mitad.

    Lo que esto **no** da: una clave robada sigue sirviendo hasta que venza el
    plazo. Para revocarla antes están el logout, el restablecimiento de
    contraseña y la desactivación del trabajador, que ya borran el token.
    """

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related("user", "user__perfil").get(key=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid token."))

        if not token.user.is_active:
            raise exceptions.AuthenticationFailed(_("User inactive or deleted."))

        self._exigir_vigencia(token)

        return token.user, token

    @staticmethod
    def _exigir_vigencia(token):
        horas = getattr(settings, "TOKEN_TTL_HORAS", 0)

        # Cero desactiva la caducidad. Existe como salida de emergencia, no
        # como valor recomendado: el ajuste por omisión sí caduca.
        if horas <= 0:
            return

        if timezone.now() - token.created <= timezone.timedelta(hours=horas):
            return

        # Se borra en vez de dejarlo pudrirse: si no, la tabla acumula claves
        # muertas que siguen apareciendo en el admin como si fueran sesiones
        # vivas.
        token.delete()

        raise exceptions.AuthenticationFailed(
            "La sesión expiró por antigüedad. Vuelve a iniciar sesión."
        )
