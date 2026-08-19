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
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle

from .models import IntentoAcceso, PerfilUsuario, SesionUsuario
from .serializers import (
    ConfirmacionRecuperacionSerializer,
    CambioPasswordSerializer,
    SesionUsuarioSerializer,
    SolicitudRecuperacionSerializer,
    TrabajadorSerializer,
    UsuarioSerializer,
)
from .permisos import IsAdminDeArea, PuedeGestionarSesiones
from .permisos_industriales import permisos_asignables_por
from .throttling import LoginIPThrottle, LoginUsuarioThrottle
from .tenancy import scope_de
from .sesiones import (
    cerrar_sesion,
    datos_cliente,
    motivo_expiracion,
    nueva_credencial,
    registrar_evento,
    revocar_sesiones,
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


def _direccion(request):
    """
    La dirección de quien llama, resuelta como la resuelve el throttle.

    Detrás de Nginx, `REMOTE_ADDR` es la del proxy —la misma para todo el
    mundo—, así que hay que leer `X-Forwarded-For`. Pero **no la primera
    entrada**: esa la escribe el cliente y es pura ficción. Cada proxy añade al
    final la dirección que él mismo vio, así que la última que puso un proxy de
    confianza es la única que no se puede falsificar.

    `PROXIES_DE_CONFIANZA` dice cuántos hay delante. Con 0 se ignora la
    cabecera entera y manda `REMOTE_ADDR`, que es el fallo seguro.

    Se cuenta desde el final igual que `SimpleRateThrottle.get_ident`: si el
    registro y el límite no coincidieran en qué dirección es cuál, investigar
    un bloqueo sería imposible.
    """
    proxies = getattr(settings, "PROXIES_DE_CONFIANZA", 0)
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR", "")

    if proxies and reenviada:
        direcciones = [parte.strip() for parte in reenviada.split(",") if parte.strip()]

        if direcciones:
            return direcciones[-min(proxies, len(direcciones))][:45] or None

    return request.META.get("REMOTE_ADDR") or None


def _anotar_intento(request, usuario, exito, motivo=""):
    """
    Deja constancia del intento.

    Nunca falla hacia fuera: si el registro no se puede escribir, el login
    tiene que seguir funcionando. Una auditoría que tumba el acceso es peor
    que no tenerla.
    """
    try:
        IntentoAcceso.objects.create(
            usuario=str(usuario or "")[:150],
            ip=_direccion(request),
            exito=exito,
            motivo=motivo,
        )
    except (DatabaseError, ValueError):
        logger.warning("No se pudo registrar el intento de acceso", exc_info=True)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([LoginIPThrottle, LoginUsuarioThrottle])
def login(request):
    """
    Valida las credenciales y entrega un token.

    Es el único endpoint abierto de la API: todo lo demás exige presentar
    ese token en la cabecera `Authorization: Token <valor>`.

    Los dos límites del decorador son lo que impide probar contraseñas en masa.
    Ver `usuarios/throttling.py`: uno por dirección y otro por cuenta, porque
    protegen de ataques distintos y ninguno basta solo.
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
        _anotar_intento(request, username, exito=False, motivo="credenciales")
        registrar_evento("LOGIN_FALLIDO", request=request, motivo="credenciales")

        # El mensaje es el mismo exista o no la cuenta: distinguirlos
        # convertiría el login en un comprobador de nombres de usuario.
        return Response(
            {"error": "Usuario o contraseña incorrectos"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not usuario.is_active:
        _anotar_intento(request, username, exito=False, motivo="desactivada")
        return Response(
            {"error": "La cuenta está desactivada"},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        with transaction.atomic():
            # La fila User serializa logins del mismo usuario entre workers.
            usuario = User.objects.select_for_update().get(pk=usuario.pk)
            activa = SesionUsuario.objects.select_for_update().filter(
                usuario=usuario, fecha_cierre__isnull=True
            ).first()
            if activa:
                expirada = motivo_expiracion(activa)
                if expirada:
                    cerrar_sesion(activa, expirada)
                    registrar_evento(
                        "SESION_EXPIRADA", request=request, usuario=usuario, motivo=expirada
                    )
                else:
                    _anotar_intento(request, username, exito=False, motivo="sesion_activa")
                    registrar_evento(
                        "LOGIN_RECHAZADO_SESION_ACTIVA", request=request, usuario=usuario
                    )
                    return Response(
                        {
                            "code": "SESSION_ALREADY_ACTIVE",
                            "error": "Este usuario ya tiene una sesión activa en otro equipo.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            token, digest = nueva_credencial()
            ip, agente = datos_cliente(request)
            SesionUsuario.objects.create(
                usuario=usuario, token_hash=digest, ip=ip, user_agent=agente
            )
            User.objects.filter(pk=usuario.pk).update(last_login=timezone.now())
    except IntegrityError:
        # Segunda barrera: el constraint parcial decide incluso si la base no
        # ofrece el mismo comportamiento de bloqueo que PostgreSQL.
        return Response(
            {
                "code": "SESSION_ALREADY_ACTIVE",
                "error": "Este usuario ya tiene una sesión activa en otro equipo.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    _anotar_intento(request, username, exito=True)
    registrar_evento("LOGIN_EXITOSO", request=request, usuario=usuario, actor=usuario)

    return Response({
        "mensaje": "Login correcto",
        "token": token,
        "usuario": UsuarioSerializer(usuario).data,
    })


@api_view(["POST"])
def logout(request):
    """
    Cierra la sesión invalidando el token.

    Sin esto, un token robado serviría para siempre: borrarlo en el navegador
    no lo desactiva en el servidor.
    """
    sesion = request.auth if isinstance(request.auth, SesionUsuario) else None
    if sesion and cerrar_sesion(sesion, SesionUsuario.MotivoCierre.LOGOUT):
        registrar_evento("LOGOUT", request=request, usuario=request.user, actor=request.user)

    return Response({"mensaje": "Sesión cerrada"})


@api_view(["GET"])
def yo(request):
    """
    Quién es el usuario del token.

    La interfaz la usa al arrancar para comprobar que la sesión guardada
    sigue siendo válida; si el token fue revocado, responde 401.
    """
    return Response(UsuarioSerializer(request.user).data)


class TrabajadorViewSet(viewsets.ModelViewSet):
    serializer_class = TrabajadorSerializer
    permission_classes = [IsAdminDeArea]
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    @action(detail=False, methods=["get"], url_path="permisos-disponibles")
    def permisos_disponibles(self, request):
        """Catálogo delegable para el actor; nunca incluye una escalada."""
        return Response([
            {"codigo": codigo, "nombre": codigo.replace("_", " ").capitalize()}
            for codigo in sorted(permisos_asignables_por(request.user))
        ])

    def get_queryset(self):
        usuarios = User.objects.select_related(
            "perfil", "perfil__empresa", "perfil__sucursal"
        ).order_by("first_name", "last_name", "username")
        if self.request.user.is_superuser:
            return usuarios

        perfil = self.request.user.perfil
        scope = scope_de(self.request.user, requerido=True)
        usuarios = usuarios.filter(is_superuser=False)
        if perfil.area == PerfilUsuario.Area.ADMINISTRACION:
            usuarios = usuarios.filter(perfil__empresa_id=scope.empresa_id)
            if scope.es_sucursal:
                usuarios = usuarios.filter(perfil__sucursal_id=scope.sucursal_id)
            return usuarios

        usuarios = usuarios.filter(perfil__area=perfil.area)
        usuarios = usuarios.filter(perfil__empresa_id=scope.empresa_id)
        if scope.es_sucursal:
            usuarios = usuarios.filter(perfil__sucursal_id=scope.sucursal_id)
        return usuarios

    def perform_create(self, serializer):
        perfil = getattr(self.request.user, "perfil", None)
        if self.request.user.is_superuser or (
            perfil and perfil.area == PerfilUsuario.Area.ADMINISTRACION
        ):
            serializer.save()
            return

        perfil = self.request.user.perfil
        serializer.save(
            area=perfil.area,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
            empresa=perfil.empresa,
            sucursal=None,
            alcance=PerfilUsuario.Alcance.EMPRESA,
        )

    def perform_update(self, serializer):
        objetivo = self.get_object()
        estaba_activo = objetivo.is_active
        perfil_actor = getattr(self.request.user, "perfil", None)
        es_general = self.request.user.is_superuser or (
            perfil_actor and perfil_actor.area == PerfilUsuario.Area.ADMINISTRACION
        )
        if not self.request.user.is_superuser and objetivo.perfil.es_admin_de_area:
            raise PermissionDenied(
                "Un administrador de área no puede modificar a otro administrador."
            )
        if not es_general:
            if {"area", "nivel", "empresa", "sucursal"}.intersection(self.request.data):
                raise PermissionDenied(
                    "No puedes modificar el área ni los permisos del trabajador."
                )
        if (
            not self.request.user.is_superuser
            and {"area", "nivel", "rol"}.intersection(self.request.data)
            and not self.request.user.has_perm("usuarios.change_roles")
        ):
            raise PermissionDenied("No tienes permiso para cambiar roles o permisos.")
        actualizado = serializer.save()
        if estaba_activo and not actualizado.is_active:
            revocar_sesiones(
                actualizado, SesionUsuario.MotivoCierre.DESACTIVACION, actor=self.request.user
            )
            registrar_evento(
                "USUARIO_DESACTIVADO", request=self.request, usuario=actualizado,
                actor=self.request.user,
            )

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise PermissionDenied("No puedes desactivar tu propia cuenta.")
        if not self.request.user.is_superuser and instance.perfil.es_admin_de_area:
            raise PermissionDenied(
                "Un administrador de área no puede desactivar a otro administrador."
            )
        instance.is_active = False
        instance.save(update_fields=["is_active"])
        revocar_sesiones(
            instance, SesionUsuario.MotivoCierre.DESACTIVACION, actor=self.request.user
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="restablecer-contrasena",
        throttle_classes=[SolicitudRecuperacionThrottle],
    )
    def restablecer_contrasena(self, request, pk=None):
        usuario = self.get_object()
        if not request.user.is_superuser and usuario.perfil.es_admin_de_area:
            return Response(
                {"error": "Un administrador de área no puede restablecer a otro administrador."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not usuario.is_active or not usuario.email:
            return Response(
                {"error": "El trabajador debe estar activo y tener un correo registrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not (
            request.user.is_superuser or request.user.has_perm("usuarios.reset_password")
        ):
            raise PermissionDenied("No tienes permiso para restablecer contraseñas.")

        formulario = PasswordResetForm(data={"email": usuario.email})
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
                extra_email_context={"reset_url": settings.PASSWORD_RESET_FRONTEND_URL},
            )
        except ImproperlyConfigured as error:
            logger.error("El correo no está configurado: %s", error)
            return Response(
                {"error": "El servicio de correo no está disponible."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except DatabaseError:
            logger.exception("No se pudo solicitar el restablecimiento administrado")
            return Response(
                {"error": "No se pudo procesar la solicitud."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        revocar_sesiones(
            usuario, SesionUsuario.MotivoCierre.RESET_PASSWORD, actor=request.user
        )
        registrar_evento(
            "PASSWORD_RESTABLECIDA", request=request, usuario=usuario, actor=request.user,
            motivo="Restablecimiento administrativo solicitado",
        )
        return Response(
            {"mensaje": "Se enviaron las instrucciones de restablecimiento."},
            status=status.HTTP_202_ACCEPTED,
        )


@api_view(["POST"])
@authentication_classes([])
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
@authentication_classes([])
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
            revocar_sesiones(usuario, SesionUsuario.MotivoCierre.RESET_PASSWORD)
            registrar_evento("PASSWORD_RESTABLECIDA", request=request, usuario=usuario)
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


@api_view(["POST"])
def cambiar_password(request):
    serializer = CambioPasswordSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    datos = serializer.validated_data
    with transaction.atomic():
        usuario = User.objects.select_for_update().get(pk=request.user.pk)
        if not usuario.check_password(datos["password_actual"]):
            return Response(
                {"password_actual": ["La contraseña actual no es correcta."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            validate_password(datos["nueva_contrasena"], user=usuario)
        except DjangoValidationError as error:
            return Response(
                {"nueva_contrasena": error.messages}, status=status.HTTP_400_BAD_REQUEST
            )
        usuario.set_password(datos["nueva_contrasena"])
        usuario.save(update_fields=["password"])
        PerfilUsuario.objects.filter(usuario=usuario).update(debe_cambiar_password=False)
        revocar_sesiones(usuario, SesionUsuario.MotivoCierre.PASSWORD)
        registrar_evento(
            "PASSWORD_CAMBIADA", request=request, usuario=usuario, actor=usuario
        )
    return Response(
        {"code": "PASSWORD_CHANGED", "mensaje": "Contraseña cambiada. Inicia sesión nuevamente."}
    )


class SesionUsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SesionUsuarioSerializer
    permission_classes = [PuedeGestionarSesiones]
    lookup_field = "identificador"
    pagination_class = None

    def get_queryset(self):
        return SesionUsuario.objects.filter(fecha_cierre__isnull=True).select_related(
            "usuario", "usuario__perfil"
        )

    @action(detail=True, methods=["post"], url_path="cerrar")
    def cerrar(self, request, identificador=None):
        if not (request.user.is_superuser or request.user.has_perm("usuarios.force_logout")):
            raise PermissionDenied("No tienes permiso para cerrar sesiones ajenas.")
        with transaction.atomic():
            sesion = SesionUsuario.objects.select_for_update().select_related("usuario").get(
                identificador=identificador, fecha_cierre__isnull=True
            )
            cerrar_sesion(sesion, SesionUsuario.MotivoCierre.ADMIN, actor=request.user)
            registrar_evento(
                "SESION_CERRADA_ADMIN", request=request, usuario=sesion.usuario,
                actor=request.user, motivo=str(request.data.get("motivo", "")),
            )
        return Response({"mensaje": "Sesión cerrada correctamente."})
