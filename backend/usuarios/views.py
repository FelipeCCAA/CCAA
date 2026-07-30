import logging

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import get_connection
from django.db import DatabaseError, transaction
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import (
    api_view,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .serializers import (
    ConfirmacionRecuperacionSerializer,
    SolicitudRecuperacionSerializer,
    UsuarioSerializer,
)


logger = logging.getLogger(__name__)

MENSAJE_SOLICITUD_RECUPERACION = (
    "Si existe una cuenta activa asociada a ese correo, "
    "recibirás instrucciones para restablecer la contraseña."
)
MENSAJE_TOKEN_INVALIDO = "El enlace de recuperación es inválido o ha expirado."


class RecuperacionThrottle(SimpleRateThrottle):
    """Limita por IP incluso si quien llama ya tiene una sesión abierta."""

    def get_cache_key(self, request, view):
        identificador = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": identificador}


class SolicitudRecuperacionThrottle(RecuperacionThrottle):
    scope = "password_reset_request"


class ConfirmacionRecuperacionThrottle(RecuperacionThrottle):
    scope = "password_reset_confirm"


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    """
    Valida las credenciales y entrega un token.

    Es el único endpoint abierto de la API: todo lo demás exige presentar
    ese token en la cabecera `Authorization: Token <valor>`.
    """
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return Response(
            {"error": "Usuario y contraseña son obligatorios"},
            status=status.HTTP_400_BAD_REQUEST
        )

    usuario = authenticate(
        username=username,
        password=password
    )

    if usuario is None:
        return Response(
            {"error": "Usuario o contraseña incorrectos"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not usuario.is_active:
        return Response(
            {"error": "La cuenta está desactivada"},
            status=status.HTTP_403_FORBIDDEN
        )

    token, _ = Token.objects.get_or_create(user=usuario)

    return Response({
        "mensaje": "Login correcto",
        "token": token.key,
        "usuario": UsuarioSerializer(usuario).data,
    })


@api_view(["POST"])
def logout(request):
    """
    Cierra la sesión invalidando el token.

    Sin esto, un token robado serviría para siempre: borrarlo en el navegador
    no lo desactiva en el servidor.
    """
    Token.objects.filter(user=request.user).delete()

    return Response({"mensaje": "Sesión cerrada"})


@api_view(["GET"])
def yo(request):
    """
    Quién es el usuario del token.

    La interfaz la usa al arrancar para comprobar que la sesión guardada
    sigue siendo válida; si el token fue revocado, responde 401.
    """
    return Response(UsuarioSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([SolicitudRecuperacionThrottle])
def solicitar_recuperacion(request):
    """
    Envía un enlace de recuperación sin revelar si el correo está registrado.

    ``PasswordResetForm`` aplica las protecciones nativas de Django: solo
    considera usuarios activos con contraseña utilizable y genera tokens de
    un solo uso mediante ``default_token_generator``.
    """
    serializer = SolicitudRecuperacionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    # Se comprueba siempre, antes de buscar el correo. Así una configuración
    # incompleta no engaña al usuario con un mensaje de envío exitoso y la
    # respuesta sigue sin revelar si la cuenta existe.
    conexion = get_connection()
    validar_correo = getattr(conexion, "validate_configuration", None)
    if validar_correo:
        try:
            validar_correo()
        except ImproperlyConfigured as error:
            logger.error("Microsoft Graph no está configurado: %s", error)
            return Response(
                {"error": "El servicio de correo no está disponible."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    formulario = PasswordResetForm(data={"email": serializer.validated_data["email"]})
    formulario.is_valid()

    try:
        formulario.save(
            request=request._request,
            use_https=request.is_secure(),
            token_generator=default_token_generator,
            from_email=settings.DEFAULT_FROM_EMAIL,
            subject_template_name="usuarios/password_reset_subject.txt",
            email_template_name="usuarios/password_reset_email.txt",
            html_email_template_name="usuarios/password_reset_email.html",
            extra_email_context={
                "reset_url": settings.PASSWORD_RESET_FRONTEND_URL,
            },
        )
    except DatabaseError:
        logger.exception("Fallo de base de datos al solicitar recuperación")
        return Response(
            {"error": "No se pudo procesar la solicitud en este momento."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"mensaje": MENSAJE_SOLICITUD_RECUPERACION})


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([ConfirmacionRecuperacionThrottle])
def confirmar_recuperacion(request):
    """
    Cambia la contraseña si el UID y el token siguen siendo válidos.

    La operación bloquea la fila del usuario y vuelve a comprobar el token
    dentro de una transacción. Al guardar la nueva contraseña, Django
    invalida automáticamente el token de recuperación. También se elimina el
    token DRF anterior para cerrar sesiones API que pudieran estar expuestas.
    """
    serializer = ConfirmacionRecuperacionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    datos = serializer.validated_data

    try:
        uid = force_str(urlsafe_base64_decode(datos["uid"]))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return Response(
            {"error": MENSAJE_TOKEN_INVALIDO},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            usuario = User.objects.select_for_update().get(pk=uid)

            if (
                not usuario.is_active
                or not usuario.has_usable_password()
                or not default_token_generator.check_token(usuario, datos["token"])
            ):
                return Response(
                    {"error": MENSAJE_TOKEN_INVALIDO},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validate_password(datos["nueva_contrasena"], user=usuario)
            except DjangoValidationError as error:
                return Response(
                    {"nueva_contrasena": error.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            usuario.set_password(datos["nueva_contrasena"])
            usuario.save(update_fields=["password"])
            Token.objects.filter(user=usuario).delete()
    except (User.DoesNotExist, ValueError, OverflowError):
        return Response(
            {"error": MENSAJE_TOKEN_INVALIDO},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except DatabaseError:
        logger.exception("Fallo de base de datos al confirmar recuperación")
        return Response(
            {"error": "No se pudo restablecer la contraseña en este momento."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return Response({"mensaje": "Contraseña restablecida correctamente."})
