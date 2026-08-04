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

from .models import PerfilUsuario, Rol, rol_de


class IsAdminDeArea(BasePermission):
    """Autoriza superusuarios y administradores de área habilitados."""

    message = "Solo un administrador de área puede gestionar trabajadores."

    def has_permission(self, request, view):
        usuario = request.user
        if not usuario or not usuario.is_authenticated:
            return False
        if usuario.is_superuser:
            return True
        perfil = getattr(usuario, "perfil", None)
        return bool(usuario.is_staff and perfil and perfil.es_admin_de_area)


EsAdministrador = IsAdminDeArea


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


class PermisoPorArea(BasePermission):
    """Lectura autenticada; escritura para el área indicada o administración general."""

    areas_escritura: tuple[str, ...] = ()

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS or request.user.is_superuser:
            return True
        perfil = getattr(request.user, "perfil", None)
        return bool(
            perfil
            and perfil.area
            in (*self.areas_escritura, PerfilUsuario.Area.ADMINISTRACION)
        )


class EscribeBodega(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.BODEGA,)
    message = "Solo Bodega puede mover, reservar o entregar inventario."


class EscribeCompras(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.COMPRAS,)
    message = "Solo Compras puede administrar solicitudes y órdenes de compra."


class EscribeRecepcionCompra(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.BODEGA)
    message = "Solo Recepción o Bodega puede registrar compras recibidas."


class EscribeMRQ(PermisoPorArea):
    areas_escritura = (
        PerfilUsuario.Area.RECEPCION,
        PerfilUsuario.Area.CONDENSACION,
        PerfilUsuario.Area.SECADO,
        PerfilUsuario.Area.ENVASE,
        PerfilUsuario.Area.CALIDAD,
        PerfilUsuario.Area.BODEGA,
    )
    message = "Tu área no puede crear o modificar solicitudes de materiales."


class EscribeMantenimiento(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.MANTENIMIENTO,)
    message = "Solo Mantenimiento puede modificar planes y órdenes de trabajo."
