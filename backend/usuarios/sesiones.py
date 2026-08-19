"""Operaciones transaccionales de sesiones y su auditoría de seguridad."""

import hashlib
import logging
import secrets

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .models import EventoSeguridad, SesionUsuario

logger = logging.getLogger(__name__)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def nueva_credencial() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def datos_cliente(request) -> tuple[str | None, str]:
    # Importación tardía para evitar un ciclo con views.
    from .views import _direccion

    return _direccion(request), request.META.get("HTTP_USER_AGENT", "")[:500]


def registrar_evento(accion, *, request=None, usuario=None, actor=None, motivo=""):
    """La bitácora no puede dejar indisponible una operación de seguridad."""
    ip, agente = datos_cliente(request) if request is not None else (None, "")
    try:
        # El savepoint impide que un fallo de auditoría contamine la
        # transacción de login/cierre que la contiene.
        with transaction.atomic():
            EventoSeguridad.objects.create(
                accion=accion,
                usuario=usuario,
                actor=actor,
                ip=ip,
                user_agent=agente,
                motivo=str(motivo or "")[:250],
            )
    except (DatabaseError, ValueError):
        logger.warning("No se pudo registrar el evento de seguridad %s", accion, exc_info=True)


def motivo_expiracion(sesion, ahora=None):
    ahora = ahora or timezone.now()
    inactividad = getattr(settings, "SESSION_IDLE_TIMEOUT_MINUTES", 60)
    absoluta = getattr(settings, "SESSION_ABSOLUTE_TIMEOUT_HOURS", 12)
    if absoluta > 0 and ahora - sesion.fecha_inicio >= timezone.timedelta(hours=absoluta):
        return SesionUsuario.MotivoCierre.ABSOLUTA
    if inactividad > 0 and ahora - sesion.ultima_actividad >= timezone.timedelta(minutes=inactividad):
        return SesionUsuario.MotivoCierre.INACTIVIDAD
    return None


def cerrar_sesion(sesion, motivo, *, actor=None, ahora=None):
    if sesion.fecha_cierre is not None:
        return False
    sesion.fecha_cierre = ahora or timezone.now()
    sesion.motivo_cierre = motivo
    sesion.cerrada_por = actor
    sesion.save(update_fields=["fecha_cierre", "motivo_cierre", "cerrada_por"])
    return True


def revocar_sesiones(usuario, motivo, *, actor=None):
    ahora = timezone.now()
    return SesionUsuario.objects.filter(
        usuario=usuario, fecha_cierre__isnull=True
    ).update(fecha_cierre=ahora, motivo_cierre=motivo, cerrada_por=actor)
