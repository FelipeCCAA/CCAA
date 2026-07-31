"""
Quién está haciendo el cambio.

Las señales de Django (`pre_save`, `post_save`, `post_delete`) ven el objeto
pero no la petición, así que por sí solas no saben quién lo tocó. El
middleware deja el usuario aquí al empezar cada petición y las señales lo leen.

Es un `contextvars.ContextVar` y no una variable de módulo: aísla por hilo
**y** por tarea async, así que dos peticiones simultáneas no se pisan el
usuario — que atribuiría un cambio a la persona equivocada, el único error que
una auditoría no puede permitirse.
"""

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    """Quién y desde dónde."""

    usuario: object | None = None
    ip: str | None = None
    # 'api' | 'admin' | 'sistema'
    origen: str = "sistema"


_ACTUAL: ContextVar[Actor] = ContextVar("auditoria_actor", default=Actor())


def actor_actual() -> Actor:
    """
    Quién está actuando. Fuera de una petición devuelve el actor «sistema»:
    migraciones, scripts y shell también se registran, sin usuario.
    """
    return _ACTUAL.get()


def fijar_actor(actor: Actor):
    """Devuelve el testigo para restaurar el valor anterior."""
    return _ACTUAL.set(actor)


def restaurar_actor(testigo):
    _ACTUAL.reset(testigo)
