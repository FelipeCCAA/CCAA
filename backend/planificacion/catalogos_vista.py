"""Los valores que admiten los campos de opciones de la planificación."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from usuarios.permisos import EscribeProduccion

from .models import (
    BloquePlan,
    CategoriaConsumo,
    CodigoProduccion,
    EstadoEquipo,
    MovimientoPlan,
    SemanaPlan,
)


@api_view(["GET"])
@permission_classes([EscribeProduccion])
def catalogos(request):
    """
    Igual que en maestros: el modelo es la fuente de verdad y la pantalla no
    lleva su propia copia de las opciones.
    """

    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    return Response(
        {
            "categoria_consumo": opciones(CategoriaConsumo.choices),
            "formato": opciones(CodigoProduccion.Formato.choices),
            "estado_semana": opciones(SemanaPlan.Estado.choices),
            "tipo_bloque": opciones(BloquePlan.Tipo.choices),
            "estado_equipo": opciones(EstadoEquipo.choices),
            "tipo_movimiento": opciones(MovimientoPlan.Tipo.choices),
        }
    )
