"""
Quién trabaja en cada área. Una sola respuesta, y no dos.

La pregunta aparece en todo el flujo de planta: a quién ofrecer como responsable
de una muestra, a quién avisar de que llegó leche, a quién avisar de que ya hay
leche disponible en el silo. Se respondía **de dos maneras distintas en el mismo
archivo** —una miraba `area` o `rol`, la otra solo `area`— y el resultado era que
una persona podía figurar en el desplegable de responsables y no recibir ningún
aviso.

Tres cosas componen la respuesta:

1. **El área principal** (`PerfilUsuario.area`), que además es la que concede
   permisos.
2. **Las áreas adicionales** (`AreaDePerfil`), porque en CCAA la misma persona
   opera en Recepción y en Fabricación. Suman presencia, no permisos.
3. **El rol, solo cuando nombra un área** — el respaldo para los perfiles
   antiguos que se cargaron sin área. `operario` no cuenta: es un comodín y no
   dice dónde trabaja nadie.

El punto 3 es el que evita romper lo que hoy funciona: en la base de desarrollo
**ningún perfil tiene un área válida**, y sin ese respaldo el desplegable de
responsables se quedaría vacío de golpe.
"""

from django.contrib.auth.models import User
from django.db.models import Q

from .models import AREAS_QUE_NOMBRA_EL_ROL, PerfilUsuario


def roles_que_cubren(area: str) -> tuple[str, ...]:
    """Los roles antiguos que implican trabajar en esta área."""
    return tuple(
        rol for rol, areas in AREAS_QUE_NOMBRA_EL_ROL.items() if area in areas
    )


def condicion_de_area(area: str, prefijo: str = "") -> Q:
    """
    La condición «este perfil cubre `area`», reutilizable desde cualquier
    queryset.

    `prefijo` permite aplicarla desde `User` (`"perfil__"`) o desde el propio
    `PerfilUsuario` (vacío), que son los dos sitios donde hace falta. Sin esto
    habría que escribir la misma regla dos veces con distinta ruta, que es
    exactamente como empezó el problema.
    """
    condicion = Q(**{f"{prefijo}area": area}) | Q(
        **{f"{prefijo}areas_adicionales__area": area}
    )

    roles = roles_que_cubren(area)

    if roles:
        condicion |= Q(**{f"{prefijo}rol__in": roles})

    return condicion


def perfiles_del_area(area: str, *, empresa_id=None, sucursal_id=None):
    """Los perfiles activos que cubren un área, acotados al tenant que se pida."""
    consulta = PerfilUsuario.objects.filter(
        condicion_de_area(area), usuario__is_active=True
    )

    if empresa_id is not None:
        consulta = consulta.filter(empresa_id=empresa_id)

    if sucursal_id is not None:
        consulta = consulta.filter(sucursal_id=sucursal_id)

    # `distinct` porque el JOIN con las áreas adicionales duplica al que está
    # en varias: sin esto, quien trabaja en dos áreas recibiría dos avisos.
    return consulta.distinct()


def usuarios_del_area(area: str, *, empresa_id=None, sucursal_id=None):
    """Igual, pero como `User` — que es lo que necesitan los desplegables."""
    consulta = User.objects.filter(
        condicion_de_area(area, prefijo="perfil__"), is_active=True
    )

    if empresa_id is not None:
        consulta = consulta.filter(perfil__empresa_id=empresa_id)

    if sucursal_id is not None:
        consulta = consulta.filter(perfil__sucursal_id=sucursal_id)

    return consulta.distinct()


def areas_fuera_de_catalogo():
    """
    Los perfiles cuyo `area` no está en el catálogo.

    `choices` no valida en la base, así que el campo admite cualquier texto: la
    base de desarrollo llegó a tener «Gestion TI» y «Sistemas», que no
    corresponden a ninguna de las diez áreas. Un área así **no la encuentra
    ninguna consulta** —ni permisos, ni avisos— y no da ningún error: la persona
    simplemente no existe para el sistema.
    """
    validas = {valor for valor, _ in PerfilUsuario.Area.choices}

    return PerfilUsuario.objects.exclude(area="").exclude(area__in=validas)
