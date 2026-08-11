"""Validación explícita de la configuración que protege producción."""

from collections.abc import Mapping

from django.core.exceptions import ImproperlyConfigured


ENTORNOS_VALIDOS = {"development", "test", "ci", "staging", "production"}
ENTORNOS_ENDURECIDOS = {"staging", "production"}


def normalizar_entorno(valor: str | None) -> str:
    entorno = (valor or "development").strip().lower()
    if entorno not in ENTORNOS_VALIDOS:
        permitidos = ", ".join(sorted(ENTORNOS_VALIDOS))
        raise ImproperlyConfigured(
            f"DJANGO_ENV={entorno!r} no es válido. Use uno de: {permitidos}."
        )
    return entorno


def exigir_postgresql(engine_solicitado: str | None, engine_django: str) -> None:
    """Rechaza fallbacks que invalidan bloqueos y constraints del dominio."""
    solicitado = (engine_solicitado or "postgresql").strip().lower()
    if solicitado not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured(
            "CCAA requiere PostgreSQL. DB_ENGINE ya no admite SQLite ni otros "
            "motores porque select_for_update y las restricciones con NULL son "
            "parte de las garantías del sistema."
        )
    if engine_django not in {
        "django.db.backends.postgresql",
        "django.db.backends.postgresql_psycopg2",
    }:
        raise ImproperlyConfigured(
            "La conexión configurada no es PostgreSQL. Revise DATABASE_URL o "
            "las variables DB_*."
        )


def errores_entorno_endurecido(config: Mapping[str, object]) -> list[str]:
    """Devuelve todos los errores para no obligar a corregirlos uno por uno."""
    errores: list[str] = []
    clave = str(config.get("SECRET_KEY") or "")
    hosts = list(config.get("ALLOWED_HOSTS") or [])
    csrf = list(config.get("CSRF_TRUSTED_ORIGINS") or [])

    if bool(config.get("DEBUG")):
        errores.append("DJANGO_DEBUG debe ser false")
    if len(clave) < 50 or clave.startswith("django-insecure"):
        errores.append("DJANGO_SECRET_KEY debe ser aleatoria y tener al menos 50 caracteres")
    if not hosts or "*" in hosts:
        errores.append("DJANGO_ALLOWED_HOSTS debe contener hosts explícitos")
    if not bool(config.get("SECURE_SSL_REDIRECT")):
        errores.append("DJANGO_SECURE_SSL_REDIRECT debe ser true")
    if not bool(config.get("SESSION_COOKIE_SECURE")):
        errores.append("SESSION_COOKIE_SECURE debe estar activo")
    if not bool(config.get("CSRF_COOKIE_SECURE")):
        errores.append("CSRF_COOKIE_SECURE debe estar activo")
    if int(config.get("SECURE_HSTS_SECONDS") or 0) <= 0:
        errores.append("DJANGO_SECURE_HSTS_SECONDS debe ser mayor que cero")
    if not csrf:
        errores.append("CSRF_TRUSTED_ORIGINS debe contener orígenes HTTPS explícitos")
    elif any(not str(origen).startswith("https://") for origen in csrf):
        errores.append("todos los CSRF_TRUSTED_ORIGINS deben usar HTTPS")
    if not bool(config.get("DATABASE_CONFIGURED")):
        errores.append("configure DATABASE_URL o todas las variables DB_*")

    return errores


def validar_entorno_endurecido(entorno: str, config: Mapping[str, object]) -> None:
    if entorno not in ENTORNOS_ENDURECIDOS:
        return
    errores = errores_entorno_endurecido(config)
    if errores:
        detalle = "\n- ".join(errores)
        raise ImproperlyConfigured(
            f"Configuración insegura para DJANGO_ENV={entorno}:\n- {detalle}"
        )
