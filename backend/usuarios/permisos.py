"""
Permisos por rol.

El criterio, acordado con el prototipo: **todos los roles leen todo, y cada
uno escribe en lo suyo**.

Que Recepción pueda consultar los lotes de Producción no es una concesión:
es necesario para trabajar. Lo que no puede es editarlos. Ocultar
información entre áreas de la misma planta genera más errores de los que
evita.

`lectura` y los usuarios sin perfil no escriben en ninguna parte.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Rol, rol_de


class PermisoPorRol(BasePermission):
    """
    Base: lectura para cualquiera autenticado, escritura solo para los roles
    declarados en `roles_escritura`.

    Las subclases declaran quién escribe. Una que no declare nada no deja
    escribir a nadie, que es el fallo seguro.
    """

    roles_escritura: tuple[str, ...] = ()
    mensaje_escritura = "Tu rol no permite modificar esta información."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.method in SAFE_METHODS:
            return True

        permitido = rol_de(request.user) in self.roles_escritura

        if not permitido:
            self.message = self.mensaje_escritura

        return permitido


class EscribeAdministracion(PermisoPorRol):
    """
    Maestros: productos, mandantes y especificaciones.

    Solo Administración. Una especificación decide qué producto sale como
    conforme: cambiarla reevalúa el histórico completo.
    """

    roles_escritura = (Rol.ADMIN,)
    mensaje_escritura = (
        "Solo Administración puede modificar los maestros. "
        "Una especificación decide qué producto sale como conforme."
    )


class EscribeProduccion(PermisoPorRol):
    """Lotes y análisis: los registra Producción."""

    roles_escritura = (Rol.PRODUCCION, Rol.ADMIN)
    mensaje_escritura = "Solo Producción puede registrar o modificar lotes."


class EscribeRecepcion(PermisoPorRol):
    """Recepciones de leche y movimientos de silo. Aún sin módulo."""

    roles_escritura = (Rol.RECEPCION, Rol.ADMIN)
    mensaje_escritura = "Solo Recepción puede registrar recepciones de leche."


class EscribeCalidad(PermisoPorRol):
    """
    Liberación de producto. Aún sin módulo.

    Es la regla que justifica el sistema (MODELO_DATOS.md §1): un despacho
    exige un lote liberado, y quien libera es Calidad.
    """

    roles_escritura = (Rol.CALIDAD, Rol.ADMIN)
    mensaje_escritura = "Solo Calidad puede autorizar la liberación de un lote."
