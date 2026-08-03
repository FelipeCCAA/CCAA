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

from .models import PerfilUsuario
from .serializers import (
    ConfirmacionRecuperacionSerializer,
    SolicitudRecuperacionSerializer,
    TrabajadorSerializer,
    UsuarioSerializer,
)
from .permisos import EsAdministrador


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


@api_view(["GET", "POST"])
@permission_classes([EsAdministrador])
def trabajadores(request):
    """Lista de usuarios y perfiles para el panel propio de Administración."""
    if request.method == "POST":
        datos = request.data
        if not datos.get("username"):
            return Response({"error": "El nombre de usuario es obligatorio."}, status=400)
        password = datos.get("password", "")
        if not password:
            return Response({"error": "La contraseña inicial es obligatoria."}, status=400)
        try:
            validate_password(password)
        except DjangoValidationError as error:
            return Response({"error": " ".join(error.messages)}, status=400)
        perfil_actor = getattr(request.user, "perfil", None)
        es_general = request.user.is_superuser or (
            perfil_actor and perfil_actor.area == PerfilUsuario.Area.ADMINISTRACION
        )
        area = datos.get("area") if es_general else perfil_actor.area
        nivel = datos.get("nivel", PerfilUsuario.Nivel.TRABAJADOR) if es_general else PerfilUsuario.Nivel.TRABAJADOR
        if area not in PerfilUsuario.Area.values or nivel not in PerfilUsuario.Nivel.values:
            return Response({"error": "Área o nivel inválido."}, status=400)
        try:
            with transaction.atomic():
                usuario = User.objects.create_user(
                    username=datos["username"], email=datos.get("email", ""),
                    first_name=datos.get("nombre", ""), last_name=datos.get("apellido", ""),
                    password=password,
                )
                PerfilUsuario.objects.create(
                    usuario=usuario, area=area, nivel=nivel,
                    empresa_id=datos.get("empresa") if es_general else perfil_actor.empresa_id,
                    sucursal_id=datos.get("sucursal") if es_general else perfil_actor.sucursal_id,
                    cargo=datos.get("cargo", ""), turno=datos.get("turno", ""),
                )
        except DatabaseError:
            return Response({"error": "No se pudo crear el usuario."}, status=400)
        return Response(TrabajadorSerializer(usuario).data, status=201)

    usuarios = User.objects.select_related("perfil").order_by(
        "first_name", "last_name", "username"
    )
    perfil = getattr(request.user, "perfil", None)
    if not request.user.is_superuser and perfil.area != perfil.Area.ADMINISTRACION:
        usuarios = usuarios.filter(perfil__area=perfil.area)
    if not request.user.is_superuser and perfil:
        if perfil.empresa_id:
            usuarios = usuarios.filter(perfil__empresa_id=perfil.empresa_id)
        if perfil.sucursal_id:
            usuarios = usuarios.filter(perfil__sucursal_id=perfil.sucursal_id)
    return Response(TrabajadorSerializer(usuarios, many=True).data)


@api_view(["PATCH"])
@permission_classes([EsAdministrador])
def actualizar_trabajador(request, usuario_id):
    actor = request.user
    perfil_actor = getattr(actor, "perfil", None)
    usuario = User.objects.select_related("perfil").filter(pk=usuario_id).first()
    if not usuario:
        return Response({"error": "El usuario no existe."}, status=404)
    perfil = getattr(usuario, "perfil", None)
    es_general = actor.is_superuser or (
        perfil_actor and perfil_actor.area == PerfilUsuario.Area.ADMINISTRACION
    )
    if not es_general and (
        not perfil or perfil.area != perfil_actor.area
        or perfil.empresa_id != perfil_actor.empresa_id
        or perfil.sucursal_id != perfil_actor.sucursal_id
    ):
        return Response({"error": "No puedes administrar usuarios de otra área."}, status=403)
    if usuario == actor and any(campo in request.data for campo in ("nivel", "area", "empresa", "sucursal")):
        return Response({"error": "No puedes modificar tus propios permisos."}, status=403)
    usuario.is_active = request.data.get("activo", usuario.is_active)
    usuario.email = request.data.get("email", usuario.email)
    usuario.first_name = request.data.get("nombre", usuario.first_name)
    usuario.last_name = request.data.get("apellido", usuario.last_name)
    usuario.save(update_fields=["is_active", "email", "first_name", "last_name"])
    if perfil:
        perfil.cargo = request.data.get("cargo", perfil.cargo)
        perfil.turno = request.data.get("turno", perfil.turno)
        if es_general:
            perfil.area = request.data.get("area", perfil.area)
            perfil.nivel = request.data.get("nivel", perfil.nivel)
        perfil.full_clean()
        perfil.save()
    return Response(TrabajadorSerializer(usuario).data)


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
