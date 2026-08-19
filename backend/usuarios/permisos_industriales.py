"""Catálogo y límites de asignación para permisos industriales Django."""

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
    {"despacho_autorizar", "auditoria_exportar"},
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
    if perfil.area == PerfilUsuario.Area.ADMINISTRACION:
        return TODOS_LOS_PERMISOS
    return PERMISOS_POR_AREA.get(perfil.area, set())


def capacidades_de(usuario) -> list[str]:
    if not usuario or not usuario.is_authenticated:
        return []
    if usuario.is_superuser:
        return sorted(TODOS_LOS_PERMISOS)
    return sorted(
        usuario.user_permissions.filter(
            content_type__app_label="usuarios",
            content_type__model="perfilusuario",
        ).values_list("codename", flat=True)
    )
