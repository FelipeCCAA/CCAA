"""
Deja en el contexto quién está haciendo la petición, para que las señales de
auditoría puedan atribuir el cambio.
"""

from .contexto import Actor, fijar_actor, restaurar_actor


def _ip_de(request):
    """
    IP del cliente. Detrás de un proxy la real va en `X-Forwarded-For`.

    Se toma la **primera** de la lista, que es la del cliente; las siguientes
    las agregan los proxies intermedios.
    """
    reenviada = request.META.get("HTTP_X_FORWARDED_FOR")

    if reenviada:
        return reenviada.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


class AuditoriaMiddleware:
    """
    Fija el actor durante la petición y lo suelta al terminar.

    El usuario se lee **tarde**, dentro de `get_response`, no aquí: con token
    de DRF la autenticación ocurre en la vista, así que en este punto
    `request.user` todavía sería anónimo. Por eso se guarda el `request` y el
    usuario se resuelve al consultarlo.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origen = "admin" if request.path.startswith("/api/admin/") else "api"
        testigo = fijar_actor(Actor(usuario=_UsuarioDiferido(request), ip=_ip_de(request), origen=origen))

        try:
            return self.get_response(request)
        finally:
            restaurar_actor(testigo)


class _UsuarioDiferido:
    """
    El usuario de la petición, resuelto en el momento de leerlo.

    DRF autentica dentro de la vista, después de que este middleware corrió.
    Guardar `request.user` al entrar dejaría a todos los cambios de la API
    como anónimos.
    """

    def __init__(self, request):
        self._request = request

    def resolver(self):
        usuario = getattr(self._request, "user", None)

        if usuario is None or not getattr(usuario, "is_authenticated", False):
            return None

        return usuario
