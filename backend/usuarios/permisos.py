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
from .tenancy import scope_de


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
        return bool(
            usuario.is_staff
            and perfil
            and perfil.es_admin_de_area
            and scope_de(usuario) is not None
        )


EsAdministrador = IsAdminDeArea


class PuedeGestionarSesiones(BasePermission):
    message = "No tienes permiso para consultar sesiones activas."

    def has_permission(self, request, view):
        usuario = request.user
        return bool(
            usuario
            and usuario.is_authenticated
            and (usuario.is_superuser or usuario.has_perm("usuarios.manage_sessions"))
        )


class PermisoPorRol(BasePermission):
    """
    Base: lectura para cualquiera autenticado, escritura solo para los roles
    declarados en `roles_escritura`.

    Las subclases declaran quién escribe. Una que no declare nada no deja
    escribir a nadie, que es el fallo seguro.
    """

    roles_escritura: tuple[str, ...] = ()
    roles_lectura: tuple[str, ...] = ()
    areas_lectura: tuple[str, ...] | None = None
    areas_escritura: tuple[str, ...] | None = None
    mensaje_escritura = "Tu rol no permite modificar esta información."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        perfil = getattr(request.user, "perfil", None)
        area = getattr(perfil, "area", "")
        rol = rol_de(request.user)

        if request.method in SAFE_METHODS:
            if scope_de(request.user) is None:
                return False
            if rol == Rol.ADMIN or self.areas_lectura is None:
                return True
            return area in self.areas_lectura or (
                not area and rol in self.roles_lectura
            )

        if rol == Rol.ADMIN:
            return True
        permitido = (
            area in self.areas_escritura
            if area and self.areas_escritura is not None
            else rol in self.roles_escritura
        )

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
    roles_lectura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (
        PerfilUsuario.Area.CONDENSACION, PerfilUsuario.Area.SECADO,
        PerfilUsuario.Area.ENVASE, PerfilUsuario.Area.CALIDAD,
    )
    areas_escritura = (
        PerfilUsuario.Area.CONDENSACION, PerfilUsuario.Area.SECADO,
    )
    mensaje_escritura = "Solo Producción puede registrar o modificar lotes."


class ConfiguraProcesos(PermisoPorRol):
    """Catalogo de rutas y etapas: lectura operativa, escritura administrativa."""

    roles_escritura = (Rol.ADMIN,)
    roles_lectura = EscribeProduccion.roles_lectura
    areas_lectura = EscribeProduccion.areas_lectura
    mensaje_escritura = (
        "Solo Administracion puede configurar procesos, etapas y rutas de producto."
    )


class EscribeAnalisisCalidad(PermisoPorRol):
    """Mediciones del producto: las registran Producción o Calidad."""

    roles_escritura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    roles_lectura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = EscribeProduccion.areas_lectura
    areas_escritura = (
        PerfilUsuario.Area.CONDENSACION, PerfilUsuario.Area.SECADO,
        PerfilUsuario.Area.CALIDAD,
    )
    mensaje_escritura = (
        "Solo Producción, Calidad o Administración pueden registrar análisis."
    )


class EscribeRecepcion(PermisoPorRol):
    """Recepciones de leche y movimientos de silo. Aún sin módulo."""

    roles_escritura = (Rol.RECEPCION, Rol.ADMIN)
    roles_lectura = (Rol.RECEPCION, Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (
        PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.CONDENSACION,
        PerfilUsuario.Area.SECADO, PerfilUsuario.Area.CALIDAD,
    )
    areas_escritura = (PerfilUsuario.Area.RECEPCION,)
    mensaje_escritura = "Solo Recepción puede registrar recepciones de leche."


class DecideCalidadRecepcion(PermisoPorRol):
    """La muestra puede decidirla Calidad o Recepción, según el turno."""

    roles_escritura = (Rol.RECEPCION, Rol.CALIDAD, Rol.ADMIN)
    roles_lectura = EscribeRecepcion.roles_lectura
    areas_lectura = EscribeRecepcion.areas_lectura
    areas_escritura = (PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.CALIDAD)
    mensaje_escritura = (
        "Solo Calidad, Recepción o Administración pueden decidir una muestra."
    )


class EscribePlanta(PermisoPorRol):
    """
    Registros de máquina: aseos, inspecciones preoperativas, calibraciones.

    Los llena quien opera el equipo —Producción— y Calidad los revisa y los
    marca observados cuando algo no cuadra. Las dos áreas escriben sobre el
    mismo registro a propósito: separarlas obligaría a Calidad a pedirle a
    Producción que corrija lo que Calidad detectó, y la auditoría ya deja
    constancia de quién tocó qué.
    """

    roles_escritura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    roles_lectura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = EscribeProduccion.areas_lectura
    areas_escritura = EscribeProduccion.areas_lectura
    mensaje_escritura = (
        "Solo Producción, Calidad y Administración registran los formularios "
        "de máquina."
    )


class EscribeEstandarizacion(PermisoPorRol):
    """
    Vales de estandarización: la mezcla de entera y descremada hasta el RC.

    Escriben **Recepción y Producción**, no una sola. El vale nace en el área
    de silos —que es de Recepción— y lo consume Condensación, que es
    Producción; el turno de noche lo llena quien está, y en planta esa persona
    no siempre es de la misma área. Separarlas obligaría a esperar a alguien
    para registrar una agitación que ya empezó.
    """

    roles_escritura = (Rol.RECEPCION, Rol.PRODUCCION, Rol.ADMIN)
    roles_lectura = (Rol.RECEPCION, Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (
        PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.CONDENSACION,
        PerfilUsuario.Area.CALIDAD,
    )
    areas_escritura = (
        PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.CONDENSACION,
    )
    mensaje_escritura = (
        "Solo Recepción, Producción o Administración registran vales de "
        "estandarización."
    )


class EscribeCalidad(PermisoPorRol):
    """
    Liberación de producto. Aún sin módulo.

    Es la regla que justifica el sistema (MODELO_DATOS.md §1): un despacho
    exige un lote liberado, y quien libera es Calidad.
    """

    roles_escritura = (Rol.CALIDAD, Rol.ADMIN)
    roles_lectura = (Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (PerfilUsuario.Area.CALIDAD,)
    areas_escritura = (PerfilUsuario.Area.CALIDAD,)
    mensaje_escritura = "Solo Calidad puede autorizar la liberación de un lote."


class EscribeEnvasado(PermisoPorRol):
    """Envases y pallets: Envase opera; Producción y Calidad consultan."""

    roles_escritura = (Rol.PRODUCCION, Rol.ADMIN)
    roles_lectura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (
        PerfilUsuario.Area.ENVASE, PerfilUsuario.Area.CONDENSACION,
        PerfilUsuario.Area.SECADO, PerfilUsuario.Area.CALIDAD,
    )
    areas_escritura = (PerfilUsuario.Area.ENVASE,)
    mensaje_escritura = "Solo el área de Envase puede registrar envases y pallets."


class EscribeInocuidad(PermisoPorRol):
    """PPRO y saneamiento: Operación registra y Calidad controla."""

    roles_escritura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    roles_lectura = (Rol.PRODUCCION, Rol.CALIDAD, Rol.ADMIN)
    areas_lectura = (
        PerfilUsuario.Area.ASEO, PerfilUsuario.Area.CONDENSACION,
        PerfilUsuario.Area.SECADO, PerfilUsuario.Area.ENVASE,
        PerfilUsuario.Area.CALIDAD,
    )
    areas_escritura = areas_lectura
    mensaje_escritura = "Solo Operación, Aseo o Calidad pueden modificar controles de inocuidad."


class PermisoPorArea(BasePermission):
    """Lectura autenticada; escritura para el área indicada o administración general."""

    areas_escritura: tuple[str, ...] = ()
    areas_lectura: tuple[str, ...] | None = None

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        if scope_de(request.user) is None:
            return False
        perfil = getattr(request.user, "perfil", None)
        if request.method in SAFE_METHODS:
            if self.areas_lectura is None:
                return True
            return bool(
                perfil and perfil.area in (
                    *self.areas_lectura, PerfilUsuario.Area.ADMINISTRACION,
                )
            )
        return bool(
            perfil
            and perfil.area
            in (*self.areas_escritura, PerfilUsuario.Area.ADMINISTRACION)
        )


class EscribeBodega(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.BODEGA,)
    areas_lectura = (
        PerfilUsuario.Area.BODEGA, PerfilUsuario.Area.COMPRAS,
        PerfilUsuario.Area.DESPACHO, PerfilUsuario.Area.CALIDAD,
    )
    message = "Solo Bodega puede mover, reservar o entregar inventario."


class EscribeCompras(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.COMPRAS,)
    areas_lectura = (PerfilUsuario.Area.COMPRAS, PerfilUsuario.Area.BODEGA)
    message = "Solo Compras puede administrar solicitudes y órdenes de compra."


class EscribeRecepcionCompra(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.BODEGA)
    areas_lectura = (
        PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.BODEGA,
        PerfilUsuario.Area.COMPRAS, PerfilUsuario.Area.CALIDAD,
    )
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
    areas_lectura = areas_escritura


class PuedeVerInventario(PermisoPorArea):
    areas_lectura = (
        PerfilUsuario.Area.BODEGA, PerfilUsuario.Area.COMPRAS,
        PerfilUsuario.Area.DESPACHO, PerfilUsuario.Area.CALIDAD,
    )
    message = "Tu área no tiene acceso al módulo de Inventario."


class PuedeVerAuditoria(BasePermission):
    message = "Solo Calidad o Administración pueden consultar la auditoría."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.user.is_superuser:
            return True
        return scope_de(request.user) is not None and rol_de(request.user) in (
            Rol.CALIDAD,
            Rol.ADMIN,
        )


class EscribeMantenimiento(PermisoPorArea):
    areas_escritura = (PerfilUsuario.Area.MANTENIMIENTO,)
    message = "Solo Mantenimiento puede modificar planes y órdenes de trabajo."
