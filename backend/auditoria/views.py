"""
Consulta del registro de auditoría.

**Solo lectura, para todos los roles.** Un registro de auditoría que se puede
editar o borrar no prueba nada: su valor entero está en que nadie pueda
cambiarlo después. Por eso es un `ReadOnlyModelViewSet` y no un
`ModelViewSet` — no existe el endpoint que lo modifique.
"""

from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import RegistroAuditoria
from .registro import APPS_AUDITADAS
from .serializers import RegistroAuditoriaSerializer


class RegistroAuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RegistroAuditoria.objects.select_related("usuario")
    serializer_class = RegistroAuditoriaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        usuario = parametros.get("usuario")
        if usuario:
            consulta = consulta.filter(usuario_nombre__icontains=usuario)

        modelo = parametros.get("modelo")
        if modelo:
            consulta = consulta.filter(modelo=modelo)

        accion = parametros.get("accion")
        if accion:
            consulta = consulta.filter(accion=accion)

        # Para reconstruir la historia de un registro concreto: qué le pasó a
        # ESTE lote, en orden.
        objeto = parametros.get("objeto")
        if objeto:
            consulta = consulta.filter(objeto_id=objeto)

        desde = parametros.get("desde")
        if desde:
            consulta = consulta.filter(fecha_hora__date__gte=desde)

        hasta = parametros.get("hasta")
        if hasta:
            consulta = consulta.filter(fecha_hora__date__lte=hasta)

        buscar = parametros.get("buscar")
        if buscar:
            consulta = consulta.filter(objeto_desc__icontains=buscar)

        return consulta


@api_view(["GET"])
def filtros(request):
    """
    Con qué se puede filtrar: los modelos que realmente tienen registros y los
    usuarios que aparecen.

    Se sacan de los datos y no de una lista fija: una lista fija ofrecería
    filtros que no devuelven nada y escondería los que sí.
    """
    modelos = (
        RegistroAuditoria.objects.values_list("modelo", "etiqueta_modelo")
        .distinct()
        .order_by("modelo")
    )
    usuarios = (
        RegistroAuditoria.objects.exclude(usuario_nombre="")
        .values_list("usuario_nombre", flat=True)
        .distinct()
        .order_by("usuario_nombre")
    )

    return Response(
        {
            "modelos": [
                {"valor": m, "etiqueta": e or m} for m, e in modelos
            ],
            "usuarios": list(usuarios),
            "acciones": [
                {"valor": v, "etiqueta": e}
                for v, e in RegistroAuditoria.Accion.choices
            ],
            "apps_auditadas": sorted(APPS_AUDITADAS),
        }
    )
