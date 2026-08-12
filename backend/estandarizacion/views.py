from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EscribeEstandarizacion
from usuarios.tenancy import QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope
from maestros.models import Silo

from . import servicios
from .dominio import Leche, calcular_mezcla
from .models import MINUTOS_DE_AGITACION, ValeEstandarizacion
from .serializers import (
    CalculoMezclaSerializer,
    MuestraSerializer,
    ValeEstandarizacionSerializer,
)


def _conflicto(error):
    return Response({"detail": error.messages[0]}, status=status.HTTP_409_CONFLICT)


class ValeEstandarizacionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "silo_destino__sucursal_id"
    tenant_lookup_empresa = "silo_destino__sucursal__empresa_id"
    tenant_relation_fields = {
        "producto": (None, "mandante__empresa_id"),
        "silo_entera": ("sucursal_id", "sucursal__empresa_id"),
        "silo_descremada": ("sucursal_id", "sucursal__empresa_id"),
        "silo_destino": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = ValeEstandarizacion.objects.select_related(
        "producto", "silo_entera", "silo_descremada", "silo_destino", "responsable"
    )
    serializer_class = ValeEstandarizacionSerializer
    permission_classes = [EscribeEstandarizacion]

    def get_queryset(self):
        consulta = super().get_queryset()

        estado = self.request.query_params.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)

        if self.request.query_params.get("abiertos") in {"1", "true"}:
            consulta = consulta.exclude(
                estado__in=[
                    ValeEstandarizacion.Estado.LIBERADO,
                    ValeEstandarizacion.Estado.ANULADO,
                ]
            )

        return consulta

    def perform_create(self, serializer):
        serializer.save(responsable=self.request.user)

    # ------------------------------------------------------ cálculo previo

    @action(detail=False, methods=["post"], url_path="calcular")
    def calcular(self, request):
        """
        Cuánto de cada leche, **sin crear el vale**.

        Es el paso que el operador repite variando el volumen antes de decidir;
        obligarlo a guardar para verlo llenaría la tabla de vales de tanteo.
        """
        entrada = CalculoMezclaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data

        mezcla = calcular_mezcla(
            entera=Leche(
                cantidad=datos["entera_disponible"],
                grasa=datos["entera_grasa"],
                sng=datos["entera_sng"],
            ),
            descremada=Leche(
                cantidad=datos["descremada_disponible"],
                grasa=datos["descremada_grasa"],
                sng=datos["descremada_sng"],
            ),
            rc_objetivo=datos["rc_objetivo"],
            volumen=datos["volumen"],
        )

        return Response({
            "posible": mezcla.posible,
            "motivo": mezcla.motivo,
            "entera": mezcla.entera,
            "descremada": mezcla.descremada,
            "rc_esperado": mezcla.rc_esperado,
            "grasa_esperada": mezcla.grasa_esperada,
            "sng_esperado": mezcla.sng_esperado,
            "avisos": mezcla.avisos,
        })

    # -------------------------------------------------------------- ciclo

    @action(detail=True, methods=["post"])
    def transferir(self, request, pk=None):
        try:
            vale = servicios.transferir(
                vale_id=self.get_object().pk, usuario=request.user
            )
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"], url_path="agitar")
    def agitar(self, request, pk=None):
        try:
            vale = servicios.iniciar_agitacion(vale_id=self.get_object().pk)
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"], url_path="muestrear")
    def muestrear(self, request, pk=None):
        entrada = MuestraSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            vale = servicios.registrar_muestra(
                vale_id=self.get_object().pk,
                grasa=entrada.validated_data["grasa"],
                sng=entrada.validated_data["sng"],
            )
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        try:
            vale, _ = servicios.decidir(
                vale_id=self.get_object().pk, usuario=request.user
            )
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"], url_path="reagitar")
    def reagitar(self, request, pk=None):
        try:
            vale = servicios.reagitar(vale_id=self.get_object().pk)
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"])
    def anular(self, request, pk=None):
        try:
            vale = servicios.anular(
                vale_id=self.get_object().pk,
                motivo=request.data.get("motivo", ""),
            )
        except DjangoValidationError as error:
            return _conflicto(error)

        return Response(self.get_serializer(vale).data)

    # ---------------------------------------------------------- catálogos

    @action(detail=False, methods=["get"], url_path="catalogos")
    def catalogos(self, request):
        """
        Los desplegables y las constantes del ciclo, desde el backend.

        Los minutos de agitación se sirven en vez de escribirse en la pantalla:
        el frontend muestra la cuenta regresiva contra el mismo número que el
        servidor usa para aceptar la muestra, y una copia terminaría ofreciendo
        el botón antes de tiempo.
        """
        silos = filtrar_por_scope(
            Silo.objects.filter(activo=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        ).annotate(
            litros_disponibles=Coalesce(
                Sum(Case(
                    When(movimientos__tipo="salida", then=-F("movimientos__litros")),
                    default=F("movimientos__litros"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )),
                Value(0),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )
        )

        return Response({
            "estados": [
                {"valor": valor, "etiqueta": etiqueta}
                for valor, etiqueta in ValeEstandarizacion.Estado.choices
            ],
            "minutos_agitacion": MINUTOS_DE_AGITACION,
            "transiciones": {
                estado: sorted(destinos)
                for estado, destinos in ValeEstandarizacion.TRANSICIONES.items()
            },
            "silos": [
                {
                    "id": silo.id,
                    "codigo": silo.codigo,
                    "tipo": silo.tipo,
                    "tipo_etiqueta": silo.get_tipo_display(),
                    "capacidad_l": silo.capacidad_l,
                    "litros_disponibles": silo.litros_disponibles,
                    "capacidad_disponible": silo.capacidad_l - silo.litros_disponibles,
                    "activo": silo.activo,
                }
                for silo in silos
            ],
        })
