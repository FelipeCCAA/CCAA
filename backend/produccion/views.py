from collections import Counter, defaultdict

from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import api_view
from rest_framework.response import Response

from maestros.models import Especificacion

from . import dominio
from .models import Analisis, Lote
from .serializers import AnalisisSerializer, LoteDetalleSerializer, LoteSerializer


class LoteViewSet(viewsets.ModelViewSet):
    # `prefetch_related` trae los análisis de todos los lotes en una sola
    # consulta. Sin esto, calcular la calidad de un listado dispararía una
    # consulta por lote.
    queryset = (
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis")
    )
    serializer_class = LoteSerializer

    def get_serializer_class(self):
        if self.action == "retrieve":
            return LoteDetalleSerializer

        return super().get_serializer_class()

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        # Las especificaciones se cargan una vez y las comparten todos los
        # lotes del listado.
        contexto["especificaciones"] = list(Especificacion.objects.all())
        return contexto

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        producto = parametros.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        desde = parametros.get("desde")
        if desde:
            consulta = consulta.filter(fecha__gte=desde)

        hasta = parametros.get("hasta")
        if hasta:
            consulta = consulta.filter(fecha__lte=hasta)

        return consulta


class AnalisisViewSet(viewsets.ModelViewSet):
    queryset = Analisis.objects.select_related("lote")
    serializer_class = AnalisisSerializer

    def get_queryset(self):
        consulta = super().get_queryset()

        lote = self.request.query_params.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        return consulta


@api_view(["GET"])
def resumen(request):
    """
    Indicadores del panel general.

    Acepta `desde` y `hasta` (YYYY-MM-DD) para acotar el periodo.

    El cumplimiento de calidad viaja SIEMPRE con su cobertura: un 90 % sobre 3
    lotes de 40 no es una buena noticia, y el panel tiene que poder decirlo.
    """
    lotes = (
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis")
        .exclude(estado=Lote.Estado.ANULADO)
    )

    desde = request.query_params.get("desde")
    if desde:
        lotes = lotes.filter(fecha__gte=desde)

    hasta = request.query_params.get("hasta")
    if hasta:
        lotes = lotes.filter(fecha__lte=hasta)

    lotes = list(lotes)
    especificaciones = list(Especificacion.objects.all())

    por_resultado = Counter()
    kg_por_producto = defaultdict(float)
    kg_por_mandante = defaultdict(float)

    for lote in lotes:
        resultado = dominio.resultado_calidad_lote(
            lote, list(lote.analisis.all()), especificaciones
        )
        por_resultado[resultado.resultado] += 1

        kilos = float(lote.kg_producidos)
        kg_por_producto[lote.producto.nombre] += kilos
        kg_por_mandante[lote.producto.mandante.nombre] += kilos

    evaluados = por_resultado[dominio.CONFORME] + por_resultado[dominio.NO_CONFORME]

    return Response(
        {
            "lotes": len(lotes),
            "kg_producidos": float(
                Lote.objects.filter(id__in=[l.id for l in lotes]).aggregate(
                    total=Sum("kg_producidos")
                )["total"]
                or 0
            ),
            "calidad": {
                "conforme": por_resultado[dominio.CONFORME],
                "no_conforme": por_resultado[dominio.NO_CONFORME],
                "sin_analisis": por_resultado[dominio.SIN_ANALISIS],
                "sin_especificacion": por_resultado[dominio.SIN_ESPECIFICACION],
                # Cobertura: sobre cuántos lotes se pudo emitir un veredicto.
                "evaluados": evaluados,
                "cobertura": round(evaluados / len(lotes) * 100, 1) if lotes else None,
                "cumplimiento": (
                    round(por_resultado[dominio.CONFORME] / evaluados * 100, 1)
                    if evaluados
                    else None
                ),
            },
            "kg_por_producto": [
                {"nombre": nombre, "kg": kg}
                for nombre, kg in sorted(
                    kg_por_producto.items(), key=lambda par: -par[1]
                )
            ],
            "kg_por_mandante": [
                {"nombre": nombre, "kg": kg}
                for nombre, kg in sorted(
                    kg_por_mandante.items(), key=lambda par: -par[1]
                )
            ],
        }
    )
