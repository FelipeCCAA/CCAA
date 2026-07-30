from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from maestros.models import Silo
from usuarios.permisos import EscribeRecepcion

from . import dominio
from .models import MovimientoSilo, Recepcion
from .serializers import MovimientoSiloSerializer, RecepcionSerializer


class RecepcionViewSet(viewsets.ModelViewSet):
    queryset = Recepcion.objects.select_related("vehiculo", "silo", "operador")
    serializer_class = RecepcionSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        silo = parametros.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)

        procedencia = parametros.get("procedencia")
        if procedencia:
            consulta = consulta.filter(procedencia=procedencia)

        desde = parametros.get("desde")
        if desde:
            consulta = consulta.filter(fecha__gte=desde)

        hasta = parametros.get("hasta")
        if hasta:
            consulta = consulta.filter(fecha__lte=hasta)

        return consulta

    def perform_create(self, serializer):
        # Quien registra queda como operador si no se indicó otro: el dato es
        # para auditoría y teclearlo a mano solo lo hace menos fiable.
        extra = {}

        if serializer.validated_data.get("operador") is None:
            extra["operador"] = self.request.user

        estado = self._estado_segun_controles(serializer)
        if estado is not None:
            extra["estado"] = estado

        serializer.save(**extra)

    def perform_update(self, serializer):
        """
        Los controles pueden llegar después de registrar el camión, así que al
        editarlos el estado vuelve a derivarse. Una recepción ya descargada o
        cerrada no se toca: su leche ya entró al silo.
        """
        estado = self._estado_segun_controles(serializer)

        intocables = (Recepcion.Estado.DESCARGADA, Recepcion.Estado.CERRADA)

        if estado is not None and serializer.instance.estado not in intocables:
            serializer.save(estado=estado)
        else:
            serializer.save()

    @staticmethod
    def _estado_segun_controles(serializer):
        """
        El estado que corresponde a los controles informados, o None si no hay
        con qué decidir todavía.

        Es lo que faltaba para que el flujo funcione: el veredicto se calculaba
        y se mostraba en pantalla, pero no movía la recepción. Quedaba en
        `registrada` para siempre, el botón de descargar nunca aparecía, y por
        tanto la ocupación del silo no cambiaba nunca.

        Si quien llama manda un `estado` explícito, manda el suyo: la pantalla
        de Recepción puede necesitar retener a mano por algo que los controles
        no capturan.
        """
        if "estado" in serializer.initial_data:
            return None

        controles = serializer.validated_data.get(
            "controles", getattr(serializer.instance, "controles", None)
        )

        evaluacion = dominio.evaluar_recepcion(controles)

        if not evaluacion.analizada:
            return None

        return (
            Recepcion.Estado.LIBERADA
            if evaluacion.liberable
            else Recepcion.Estado.RETENIDA
        )

    @action(detail=True, methods=["post"])
    def descargar(self, request, pk=None):
        """
        Descarga la recepción al silo.

        Es lo que convierte una recepción en litros dentro de un silo: crea el
        asiento de ingreso en el libro mayor. Se hace en una transacción junto
        al cambio de estado, porque una descarga sin su movimiento dejaría el
        saldo del silo mintiendo.
        """
        recepcion = self.get_object()

        if recepcion.silo is None:
            return Response(
                {"detail": "La recepción no tiene silo de destino asignado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not recepcion.puede_pasar_a(Recepcion.Estado.DESCARGADA):
            return Response(
                {
                    "detail": (
                        f"Una recepción {recepcion.get_estado_display().lower()} no "
                        "puede descargarse. Debe estar liberada."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            MovimientoSilo.objects.create(
                silo=recepcion.silo,
                tipo=MovimientoSilo.Tipo.INGRESO,
                litros=recepcion.litros,
                fecha_hora=timezone.now(),
                origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
                origen_id=recepcion.id,
            )

            recepcion.estado = Recepcion.Estado.DESCARGADA
            recepcion.save(update_fields=["estado"])

        return Response(self.get_serializer(recepcion).data)


class MovimientoSiloViewSet(viewsets.ModelViewSet):
    queryset = MovimientoSilo.objects.select_related("silo")
    serializer_class = MovimientoSiloSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset()

        silo = self.request.query_params.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)

        return consulta


@api_view(["GET"])
def ocupacion(request):
    """
    Ocupación de cada silo.

    Es un saldo: ingresos menos consumo, calculado desde el libro de
    movimientos (MODELO_DATOS.md §2.4). Por eso no existe como campo.

    Un saldo negativo se informa tal cual: significa que el registro está
    descuadrado, y ocultarlo haría que el error nunca se descubriera.
    """
    silos = list(Silo.objects.filter(activo=True))
    # Todos los movimientos de una vez: son pocos por silo y evita una
    # consulta por cada uno.
    movimientos = list(MovimientoSilo.objects.all())

    ocupaciones = [dominio.ocupacion_silo(silo, movimientos) for silo in silos]

    return Response(
        {
            "silos": [
                {
                    "silo_id": o.silo_id,
                    "codigo": o.codigo,
                    "litros": o.litros,
                    "capacidad": o.capacidad,
                    "pct": o.pct,
                    "excedido": o.excedido,
                    "negativo": o.negativo,
                }
                for o in ocupaciones
            ],
            "litros_totales": sum(o.litros for o in ocupaciones),
            "alertas": {
                "excedidos": [o.codigo for o in ocupaciones if o.excedido],
                "negativos": [o.codigo for o in ocupaciones if o.negativo],
            },
        }
    )
