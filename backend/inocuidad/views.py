"""
API de inocuidad: monitoreos PPRO y sus lecturas.

Escriben Producción y Calidad —quien está en la línea toma la lectura, quien
audita escribe la acción correctiva—; el resto consulta.
"""

from rest_framework import viewsets

from usuarios.permisos import EscribeProduccion

from .models import MonitoreoPPRO, PproLectura
from .serializers import MonitoreoPPROSerializer, PproLecturaSerializer


class MonitoreoPPROViewSet(viewsets.ModelViewSet):
    # `lecturas` se prefetch-ea porque `resuelto` las recorre: sin esto, una
    # consulta por monitoreo en cada listado.
    queryset = MonitoreoPPRO.objects.select_related("lote", "equipo").prefetch_related(
        "lecturas"
    )
    serializer_class = MonitoreoPPROSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        lote = parametros.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        tipo = parametros.get("tipo")
        if tipo:
            consulta = consulta.filter(tipo=tipo)

        fecha = parametros.get("fecha")
        if fecha:
            consulta = consulta.filter(fecha=fecha)

        return consulta


class PproLecturaViewSet(viewsets.ModelViewSet):
    queryset = PproLectura.objects.select_related("monitoreo")
    serializer_class = PproLecturaSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        monitoreo = self.request.query_params.get("monitoreo")
        if monitoreo:
            consulta = consulta.filter(monitoreo_id=monitoreo)

        return consulta
