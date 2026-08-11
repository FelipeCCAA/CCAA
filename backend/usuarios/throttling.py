"""
Límites de peticiones del acceso.

El login no tenía ninguno: se podían probar miles de contraseñas por minuto
contra `/api/usuarios/login/` sin freno, sin bloqueo y sin dejar rastro, y el
token que se obtuviera no caducaba nunca.

Se ponen **dos** límites porque protegen de cosas distintas y ninguno de los
dos basta solo:

- **Por dirección**, holgado. La planta sale a internet por una sola IP, así
  que treinta personas comparten cuota. Un límite estricto aquí deja al turno
  entero fuera por culpa de un atacante — que es una denegación de servicio
  servida en bandeja.
- **Por nombre de usuario**, estricto. Una persona no falla quince veces en una
  hora contra su propia cuenta. Es el límite que sobrevive a un atacante que
  rota direcciones, que es lo habitual, y el que no se puede evadir desde una
  botnet.
"""

import time

from django.core.cache import cache
from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    """Cuántos intentos admite una misma dirección."""

    scope = "login_ip"

    def get_cache_key(self, request, view):
        # Por IP incluso si quien llama trae una sesión: el login es
        # justamente el endpoint donde todavía no hay usuario de confianza.
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginUsuarioThrottle(SimpleRateThrottle):
    """
    Cuántos intentos admite una misma cuenta, venga de donde venga.

    El nombre se normaliza —minúsculas y sin espacios— porque `Usuario`,
    `usuario ` y `USUARIO` son tres formas de atacar la misma cuenta, y con la
    clave sin normalizar cada una tendría su propia cuota.
    """

    scope = "login_usuario"

    def get_cache_key(self, request, view):
        usuario = request.data.get("username") if hasattr(request, "data") else None

        if not usuario:
            # Sin nombre no hay cuenta que proteger; del volumen se ocupa el
            # límite por dirección. Devolver `None` deja pasar la petición sin
            # contarla, que es lo correcto: la rechazará la validación.
            return None

        return self.cache_format % {
            "scope": self.scope,
            "ident": str(usuario).strip().lower()[:150],
        }


# ---------------------------------------------------------------- desbloqueo
#
# El límite sin forma de levantarlo es media herramienta. «Abre una shell de
# Django dentro del contenedor y borra una clave de caché» no es algo que se le
# pueda pedir al turno de noche cuando el jefe de planta no puede entrar.
#
# Estas funciones son el único sitio que conoce el formato de la clave. El
# comando y el admin las usan; si el formato cambia, cambia aquí y no en tres
# lugares que se enteran tarde.


def normalizar(nombre) -> str:
    """El nombre tal como lo indexa el límite: minúsculas y sin espacios."""
    return str(nombre or "").strip().lower()[:150]


def clave_de_usuario(nombre) -> str:
    return LoginUsuarioThrottle.cache_format % {
        "scope": LoginUsuarioThrottle.scope,
        "ident": normalizar(nombre),
    }


def clave_de_ip(direccion) -> str:
    return LoginIPThrottle.cache_format % {
        "scope": LoginIPThrottle.scope,
        "ident": str(direccion or "").strip(),
    }


def estado_del_limite(clave, throttle):
    """
    Cuántos intentos lleva esa clave y si está bloqueada.

    Se descartan los caducados igual que hace el throttle: DRF guarda una lista
    de marcas de tiempo y va soltando las más viejas que la ventana. Contarlas
    todas diría que alguien sigue bloqueado cuando ya no lo está — y el aviso
    equivocado es peor que ninguno, porque manda a desbloquear lo que no toca.
    """
    historial = cache.get(clave) or []
    ahora = time.time()
    vigentes = [marca for marca in historial if marca > ahora - throttle.duration]

    return {
        "clave": clave,
        "usados": len(vigentes),
        "limite": throttle.num_requests,
        "bloqueado": len(vigentes) >= throttle.num_requests,
        # Cuándo se libera el hueco más viejo. La ventana es deslizante: no hay
        # que esperar una hora completa, solo a que caduque el primer intento.
        "libre_en": (
            max(0, int(vigentes[-1] + throttle.duration - ahora)) if vigentes else 0
        ),
    }


def desbloquear(clave) -> bool:
    """Borra el contador. Devuelve si había algo que borrar."""
    habia = cache.get(clave) is not None
    cache.delete(clave)

    return habia
