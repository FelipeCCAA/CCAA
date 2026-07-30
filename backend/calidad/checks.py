"""
Comprobación de arranque: que el motor sepa bloquear filas.

Existe por un problema concreto. `select_for_update()` en un backend que no lo
soporta —SQLite— no falla ni avisa: Django simplemente no emite el `FOR UPDATE`
y la llamada se compila a nada. El código queda idéntico y la garantía
desaparece, que es la peor forma de perder una protección.

Aquí se convierte ese silencio en un mensaje. La severidad depende de si el
motor sin bloqueo fue una decisión o un descuido:

- Con `DB_ENGINE=sqlite` puesto a mano es un **aviso**: alguien lo pidió y
  conviene que vea qué pierde, pero puede trabajar.
- Sin haberlo pedido y con DEBUG apagado es un **error** que impide arrancar,
  porque es una configuración equivocada operando la planta, y operar sin ese
  bloqueo significa poder firmar la liberación de un lote cuyo checklist dejó
  de estar completo mientras se decidía.

La severidad no se decide solo por DEBUG porque el runner de pruebas lo apaga
siempre: eso convertiría el aviso en un error que impide correr las pruebas en
cualquier equipo sin PostgreSQL.

El motivo largo está en DECISIONES.md.
"""

import os

from django.conf import settings
from django.core.checks import Error, Warning
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


def se_pidio_sqlite_a_proposito() -> bool:
    """¿Alguien puso `DB_ENGINE=sqlite`, o esto es un descuido?"""
    return os.getenv("DB_ENGINE", "").strip().lower() == "sqlite"


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

    grave = not se_pidio_sqlite_a_proposito() and not settings.DEBUG

    problema = Error if grave else Warning

    return [
        problema(
            MENSAJE % connection.vendor,
            hint=PISTA,
            id="calidad.E001" if grave else "calidad.W001",
        )
    ]
