"""Comprobaciones de arranque sobre los perfiles."""

from django.core.checks import Warning


def areas_dentro_del_catalogo(app_configs, **kwargs):
    """
    Avisa de los perfiles con un `area` que no está en el catálogo.

    `choices` **no valida en la base**: el campo admite cualquier texto, y la
    base de desarrollo llegó a tener «Gestion TI» y «Sistemas». Un área así no
    la encuentra ninguna consulta —ni los permisos por área, ni los avisos de
    planta— y no produce ningún error: la persona simplemente deja de existir
    para el sistema, en silencio.

    Es un aviso y no un error: la instalación funciona, y bloquear el arranque
    por un dato corregible dejaría la planta parada por algo que no lo merece.

    Registrada en `UsuariosConfig.ready()`.
    """
    from django.db import DatabaseError, connection

    try:
        # Antes de migrar, la tabla no existe y preguntar sería ruido.
        if "usuarios_perfilusuario" not in connection.introspection.table_names():
            return []

        from .areas import areas_fuera_de_catalogo

        sueltos = list(
            areas_fuera_de_catalogo().values_list("usuario__username", "area")[:20]
        )
    except (DatabaseError, Exception):
        # Un check no debe impedir arrancar por no poder averiguarlo: si la base
        # no responde, ya hay un problema más grande y más visible.
        return []

    if not sueltos:
        return []

    detalle = ", ".join(f"{usuario} → «{area}»" for usuario, area in sueltos)

    return [
        Warning(
            f"Hay perfiles con un área fuera del catálogo: {detalle}.",
            hint=(
                "Ese perfil no aparece en ninguna consulta por área: no recibe "
                "los avisos de planta ni obtiene los permisos del área. "
                "Corrígelo en Usuarios › Perfiles de usuario, eligiendo una de "
                "las diez áreas del catálogo."
            ),
            id="usuarios.W001",
        )
    ]
