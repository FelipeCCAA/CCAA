from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from usuarios.permisos import EscribeEstandarizacion
from usuarios.tenancy import QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope
from maestros.models import Silo
from recepcion.models import AnalisisSilo

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
            if estado == ValeEstandarizacion.Estado.BORRADOR:
                consulta = consulta.filter(abierto_por=self.request.user)
        else:
            consulta = consulta.exclude(estado=ValeEstandarizacion.Estado.BORRADOR)

        if self.request.query_params.get("abiertos") in {"1", "true"}:
            consulta = consulta.exclude(
                estado__in=[
                    ValeEstandarizacion.Estado.LIBERADO,
                    ValeEstandarizacion.Estado.ANULADO,
                ]
            )

        return consulta

    def perform_create(self, serializer):
        serializer.save(
            responsable=self.request.user,
            estado=ValeEstandarizacion.Estado.CALCULADO,
            codigo_propuesto=serializer.validated_data["codigo"],
        )

    # --------------------------------------------------------- borradores

    def _borrador_del_usuario(self, request, pk=None):
        consulta = ValeEstandarizacion.objects.select_related(
            "producto", "silo_entera", "silo_descremada", "silo_destino",
            "responsable",
        ).filter(
            estado=ValeEstandarizacion.Estado.BORRADOR,
            abierto_por=request.user,
        )
        if pk is not None:
            consulta = consulta.filter(pk=pk)
        return consulta.order_by("-actualizado_en", "-id").first()

    @action(detail=False, methods=["get"], url_path="mi-borrador")
    def mi_borrador(self, request):
        borrador = self._borrador_del_usuario(request)
        if borrador is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(self.get_serializer(borrador).data)

    @action(detail=False, methods=["post"], url_path="crear-borrador")
    def crear_borrador(self, request):
        existente = self._borrador_del_usuario(request)
        if existente is not None:
            return Response(
                {
                    "detail": "Ya tienes un borrador de vale abierto.",
                    "borrador": self.get_serializer(existente).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        datos = request.data.copy()
        datos.pop("codigo", None)
        serializer = self.get_serializer(data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        vale = serializer.save(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            fecha=serializer.validated_data.get("fecha", timezone.localdate()),
            responsable=request.user,
            abierto_por=request.user,
            abierto_en=timezone.now(),
            estado=ValeEstandarizacion.Estado.BORRADOR,
        )
        return Response(self.get_serializer(vale).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="guardar-borrador")
    def guardar_borrador(self, request, pk=None):
        vale = self._borrador_del_usuario(request, pk)
        if vale is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        datos = request.data.copy()
        datos.pop("codigo", None)
        serializer = self.get_serializer(vale, data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="confirmar-borrador")
    def confirmar_borrador(self, request, pk=None):
        vale = self._borrador_del_usuario(request, pk)
        if vale is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        motivos = vale.confirmar(request.user)
        if motivos:
            return Response({"motivos": motivos}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(vale).data)

    @action(detail=True, methods=["post"], url_path="descartar-borrador")
    def descartar_borrador(self, request, pk=None):
        vale = self._borrador_del_usuario(request, pk)
        if vale is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        vale.estado = ValeEstandarizacion.Estado.ANULADO
        vale.save(update_fields=["estado", "actualizado_en"])
        return Response(status=status.HTTP_204_NO_CONTENT)

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

    @action(detail=False, methods=["get"], url_path="composicion-silos")
    def composicion_silos(self, request):
        """
        La composición de cada silo según su **último** análisis.

        Es lo que el operador copiaba a mano del vale de trazabilidad. No
        crea nada ni decide nada: devuelve el dato con su vigencia y con lo
        que falte, y quien compone el vale sigue siendo quien decide.

        Un silo sin análisis o con uno vencido **no es un error**: devuelve
        el motivo. Rechazar con 400 dejaría a la pantalla sin poder mostrar
        por qué no hay número que ofrecer.
        """
        respuesta = {}

        for rol in ("entera", "descremada"):
            silo_id = request.query_params.get(rol)

            if not silo_id:
                respuesta[rol] = self._sin_analisis("No se indicó el silo.")
                continue

            analisis = (
                AnalisisSilo.objects.filter(silo_id=silo_id)
                .select_related("silo")
                .order_by("-tomado_en")
                .first()
            )

            if analisis is None:
                respuesta[rol] = self._sin_analisis(
                    "El silo está sin análisis registrado."
                )
                continue

            vigencia = analisis.vigencia
            respuesta[rol] = {
                "analisis": analisis.id,
                "silo": analisis.silo_id,
                "silo_codigo": analisis.silo.codigo,
                "tomado_en": analisis.tomado_en,
                "grasa": str(analisis.grasa) if analisis.grasa is not None else None,
                "sng": str(analisis.sng) if analisis.sng is not None else None,
                "vigente": vigencia.vigente,
                "motivo": vigencia.motivo,
                "faltantes": analisis.faltantes_para_vale,
            }

        return Response(respuesta)

    @staticmethod
    def _sin_analisis(motivo):
        return {
            "analisis": None,
            "silo": None,
            "silo_codigo": "",
            "tomado_en": None,
            "grasa": None,
            "sng": None,
            "vigente": False,
            "motivo": motivo,
            "faltantes": ["grasa", "sng"],
        }

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
            vale, _ = servicios.registrar_muestra(
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
        el frontend arma la cuenta regresiva del cronómetro contra el mismo
        número que el servidor usa para armar el aviso de muestreo temprano, y
        una copia terminaría mostrando una cuenta que no coincide con la que
        dispara el aviso.
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
