"""Catálogo y límites de asignación para permisos industriales Django."""

from django.contrib.auth.models import Permission

from .models import PerfilUsuario


PERMISOS_POR_AREA: dict[str, set[str]] = {
    PerfilUsuario.Area.CONDENSACION: {
        "produccion_orden_crear", "produccion_orden_editar",
        "produccion_lote_cerrar", "produccion_lote_anular",
    },
    PerfilUsuario.Area.SECADO: {
        "produccion_orden_crear", "produccion_orden_editar",
        "produccion_lote_cerrar", "produccion_lote_anular",
        "secado_proceso_iniciar", "secado_proceso_cerrar",
    },
    PerfilUsuario.Area.ENVASE: {
        "produccion_lote_cerrar", "produccion_lote_anular",
    },
    PerfilUsuario.Area.CALIDAD: {
        "calidad_lote_liberar", "calidad_lote_bloquear",
    },
    PerfilUsuario.Area.BODEGA: {
        "inventario_transferir", "inventario_ajustar",
    },
    PerfilUsuario.Area.DESPACHO: {"despacho_crear"},
}

TODOS_LOS_PERMISOS = set().union(
    *PERMISOS_POR_AREA.values(),
    {
        "despacho_autorizar", "auditoria_exportar", "reset_password",
        "manage_sessions", "force_logout", "change_roles",
    },
)

PERMISOS_SENSIBLES = {
    "reset_password", "manage_sessions", "force_logout", "change_roles",
}


def queryset_permisos_industriales():
    """Queryset compartido para precargar solo los permisos que expone la API."""
    return Permission.objects.filter(
        content_type__app_label="usuarios",
        content_type__model="perfilusuario",
    ).only("id", "codename", "content_type_id")


def permisos_industriales_de(usuario) -> list[str]:
    """Permisos directos, usando la precarga del listado cuando está presente."""
    precargados = getattr(usuario, "permisos_industriales_precargados", None)
    if precargados is not None:
        return sorted(permiso.codename for permiso in precargados)
    return sorted(
        queryset_permisos_industriales()
        .filter(user=usuario)
        .values_list("codename", flat=True)
    )


def permisos_asignables_por(usuario) -> set[str]:
    """Solo capacidades que el actor puede delegar sin escalar privilegios."""
    if not usuario or not usuario.is_authenticated:
        return set()
    if usuario.is_superuser:
        return TODOS_LOS_PERMISOS
    perfil = getattr(usuario, "perfil", None)
    if not perfil or not perfil.es_admin_de_area:
        return set()
    propios_sensibles = {
        codigo for codigo in PERMISOS_SENSIBLES
        if usuario.has_perm(f"usuarios.{codigo}")
    }
    if perfil.area == PerfilUsuario.Area.ADMINISTRACION:
        return (TODOS_LOS_PERMISOS - PERMISOS_SENSIBLES) | propios_sensibles
    return PERMISOS_POR_AREA.get(perfil.area, set()) | propios_sensibles


def capacidades_de(usuario) -> list[str]:
    if not usuario or not usuario.is_authenticated:
        return []
    if usuario.is_superuser:
        return sorted(TODOS_LOS_PERMISOS)
    return permisos_industriales_de(usuario)
