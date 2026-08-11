"""
Comprobación de arranque: que el motor sepa bloquear filas.

Existe como defensa en profundidad. `settings.py` ya rechaza cualquier motor
que no sea PostgreSQL, pero este check evita una degradación silenciosa si una
suite o configuración dinámica reemplaza `DATABASES` después de cargar los
settings. Un motor sin bloqueo siempre es un error.

El motivo largo está en DECISIONES.md.
"""

from django.core.checks import Error
from django.db import connection


MENSAJE = (
    "El motor de base de datos '%s' no soporta el bloqueo de filas "
    "(select_for_update)."
)

PISTA = (
    "La firma de una liberación lee el checklist, decide y escribe. Sin "
    "bloqueo, otro usuario puede desmarcar un documento entre la lectura y la "
    "escritura, y la liberación queda firmada contra un checklist que ya no "
    "está completo. Configure PostgreSQL: copie backend/.env.example a "
    "backend/.env. El detalle está en DECISIONES.md."
)


def motor_soporta_bloqueo(app_configs, **kwargs):
    """Registrada en `CalidadConfig.ready()`."""
    try:
        soportado = connection.features.has_select_for_update
    except Exception:
        # Un check no debe impedir arrancar por no poder averiguar esto: si la
        # base no responde, ya hay un problema más grande y más visible.
        return []

    if soportado:
        return []

    return [
        Error(
            MENSAJE % connection.vendor,
            hint=PISTA,
            id="calidad.E001",
        )
    ]
