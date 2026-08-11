from decimal import Decimal
from math import ceil

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from usuarios.models import PerfilUsuario
from usuarios.permisos import (
    EsAdministrador, EscribeBodega, EscribeCalidad, EscribeCompras,
    EscribeMRQ, EscribeRecepcionCompra,
)
from usuarios.tenancy import (
    EmpresaTenantViewSetMixin, QuerysetTenantMixin, RelacionesTenantMixin,
    SucursalTenantViewSetMixin, filtrar_por_scope, scope_de, sucursal_para_escritura,
)

from .models import (
    Adjunto, AjusteInventario, Alerta, Bodega, CicloCIP, DetalleEntregaProduccion, DetalleOrdenCompra,
    DetalleSolicitudCompra, DetalleSolicitudMaterial, EjecucionMRP, Existencia,
    DevolucionProduccion, InspeccionMaterial, Insumo, InsumoProveedor, LiberacionExcepcionalMaterial,
    LoteInventario, MovimientoInventario, NoConformidadMaterial, Notificacion,
    OrdenCompra, PlantillaInspeccion, Proveedor, RecepcionCompra,
    SolicitudCompra, SolicitudMaterial, Ubicacion,
)
from .serializers import (
    AdjuntoSerializer, AjusteInventarioSerializer, AlertaSerializer, BodegaSerializer, CicloCIPSerializer,
    DetalleOrdenCompraSerializer,
    DetalleSolicitudCompraSerializer, DetalleSolicitudMaterialSerializer, DevolucionProduccionSerializer,
    EjecucionMRPSerializer, ExistenciaSerializer, InspeccionMaterialSerializer, InsumoProveedorSerializer,
    InsumoSerializer, LoteInventarioSerializer, MovimientoSerializer,
    LiberacionExcepcionalSerializer, NoConformidadSerializer,
    NotificacionSerializer, OrdenCompraSerializer, PlantillaInspeccionSerializer, ProveedorSerializer,
    RecepcionCompraSerializer, SolicitudCompraSerializer,
    SolicitudMaterialSerializer, UbicacionSerializer,
)
from .bloqueo import YaEnCurso, solo_uno
from .servicios import (
    cerrar_no_conformidad, consumir_receta_produccion, crear_ajuste,
    decidir_inspeccion, decidir_solicitud_compra,
    decidir_y_aplicar_ajuste, entregar_solicitud_material,
    convertir_solicitud_en_ordenes, crear_solicitud_desde_mrp,
    ejecutar_mrp_semana, encolar_mrp_semana, enviar_orden_compra, insumos_requeridos, recibir_detalle_compra, registrar_devolucion,
    ingresar_material_manual, registrar_entrada, registrar_salida, reservar_solicitud_material, trasladar_existencia,
)


def _tenant_get(modelo, usuario, pk, *, sucursal, empresa):
    return filtrar_por_scope(
        modelo.objects.all(), usuario,
        campo_sucursal=sucursal, campo_empresa=empresa,
    ).get(pk=pk)


class FiltroAreaAdminMixin:
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        qs = super().get_queryset()
        perfil = getattr(self.request.user, "perfil", None)
        if self.request.user.is_superuser or (perfil and perfil.area == PerfilUsuario.Area.ADMINISTRACION):
            return qs
        return qs.filter(area=perfil.area) if perfil else qs.none()


class InsumoViewSet(FiltroAreaAdminMixin, EmpresaTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "empresa_id"
    queryset = Insumo.objects.prefetch_related("lotes__existencias", "proveedores__proveedor")
    serializer_class = InsumoSerializer
    permission_classes = [EscribeBodega]


class CicloCIPViewSet(FiltroAreaAdminMixin, SucursalTenantViewSetMixin, RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    tenant_relation_fields = {"equipo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = CicloCIP.objects.select_related("responsable", "equipo")
    serializer_class = CicloCIPSerializer

    def perform_create(self, serializer):
        serializer.save(
            responsable=self.request.user,
            sucursal=sucursal_para_escritura(self.request.user, serializer.validated_data),
        )


class ProveedorViewSet(EmpresaTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "empresa_id"
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [EscribeCompras]


class InsumoProveedorViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "insumo__empresa_id"
    tenant_relation_fields = {
        "insumo": (None, "empresa_id"), "proveedor": (None, "empresa_id"),
    }
    queryset = InsumoProveedor.objects.select_related("insumo", "proveedor")
    serializer_class = InsumoProveedorSerializer
    permission_classes = [EscribeCompras]


class BodegaViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = Bodega.objects.order_by("pk")
    serializer_class = BodegaSerializer
    permission_classes = [EscribeBodega]


class UbicacionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "bodega__sucursal_id"
    tenant_lookup_empresa = "bodega__sucursal__empresa_id"
    tenant_relation_fields = {"bodega": ("sucursal_id", "sucursal__empresa_id")}
    queryset = Ubicacion.objects.select_related("bodega")
    serializer_class = UbicacionSerializer
    permission_classes = [EscribeBodega]


class LoteInventarioViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = LoteInventario.objects.select_related("insumo", "proveedor")
    serializer_class = LoteInventarioSerializer
    permission_classes = [EscribeBodega]


class FiltraPorLoteMixin:
    """
    `?lote=<id>` acota el listado a un lote.

    Lo necesita la ficha del lote: sin filtro habría que traer la tabla entera
    y descartar en el cliente, que además está paginada — o sea que el
    movimiento que se busca puede no venir en la primera página.
    """

    def get_queryset(self):
        consulta = super().get_queryset()
        lote = self.request.query_params.get("lote")

        return consulta.filter(lote_id=lote) if lote else consulta


class ExistenciaViewSet(FiltraPorLoteMixin, QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "ubicacion__bodega__sucursal_id"
    tenant_lookup_empresa = "ubicacion__bodega__sucursal__empresa_id"
    queryset = Existencia.objects.select_related("lote__insumo", "ubicacion__bodega")
    serializer_class = ExistenciaSerializer
    permission_classes = [EscribeBodega]


class MovimientoViewSet(FiltraPorLoteMixin, QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    queryset = MovimientoInventario.objects.select_related("lote__insumo", "origen", "destino", "usuario")
    serializer_class = MovimientoSerializer
    permission_classes = [EscribeBodega]

    @action(detail=False, methods=["post"], url_path="entrada")
    def entrada(self, request):
        try:
            movimiento = registrar_entrada(
                lote=_tenant_get(LoteInventario, request.user, request.data.get("lote"), sucursal="sucursal_id", empresa="sucursal__empresa_id"),
                ubicacion=_tenant_get(Ubicacion, request.user, request.data.get("ubicacion"), sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id"),
                cantidad=request.data.get("cantidad"), usuario=request.user,
                documento_tipo=request.data.get("documento_tipo", "inventario.EntradaManual"),
                documento_id=request.data.get("documento_id") or 0,
            )
        except (LoteInventario.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=400)
        return Response(self.get_serializer(movimiento).data, status=201)

    @action(detail=False, methods=["post"], url_path="ingresar-material")
    def ingresar_material(self, request):
        try:
            movimiento = ingresar_material_manual(
                insumo=_tenant_get(Insumo, request.user, request.data.get("insumo"), sucursal=None, empresa="empresa_id"),
                codigo_lote=request.data.get("codigo_lote", ""),
                ubicacion=_tenant_get(Ubicacion, request.user, request.data.get("ubicacion"), sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id"),
                cantidad=request.data.get("cantidad"), usuario=request.user,
                elaboracion=request.data.get("elaboracion"), vencimiento=request.data.get("vencimiento"),
            )
        except (Insumo.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=400)
        return Response(self.get_serializer(movimiento).data, status=201)

    @action(detail=False, methods=["post"], url_path="salida")
    def salida(self, request):
        try:
            existencia = _tenant_get(Existencia, request.user, request.data.get("existencia"), sucursal="ubicacion__bodega__sucursal_id", empresa="ubicacion__bodega__sucursal__empresa_id")
            movimiento = registrar_salida(
                existencia_id=existencia.pk, cantidad=request.data.get("cantidad"),
                usuario=request.user,
                documento_tipo=request.data.get("documento_tipo", "inventario.SalidaManual"),
                documento_id=request.data.get("documento_id") or 0,
                motivo=request.data.get("motivo", ""),
                consumo=request.data.get("tipo") == "consumo",
                # Único camino para sacar material que Calidad no aprobó, y
                # solo por la cantidad que la concesión autorizó.
                liberacion=(
                    filtrar_por_scope(LiberacionExcepcionalMaterial.objects.all(), request.user, campo_sucursal="lote__sucursal_id", campo_empresa="lote__sucursal__empresa_id").filter(pk=request.data.get("liberacion")).first()
                    if request.data.get("liberacion")
                    else None
                ),
            )
        except (Existencia.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=409)
        return Response(self.get_serializer(movimiento).data, status=201)

    @action(detail=False, methods=["post"], url_path="consumir-receta")
    def consumir_receta(self, request):
        from produccion.models import Lote
        try:
            cabecera, movimientos = consumir_receta_produccion(
                lote_produccion=_tenant_get(Lote, request.user, request.data.get("lote_produccion"), sucursal="sucursal_id", empresa="sucursal__empresa_id"),
                usuario=request.user,
            )
        except (Lote.DoesNotExist, DjangoValidationError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else "El lote de Producción no existe."
            return Response({"error": mensaje}, status=409)
        return Response({
            "consumo": cabecera.pk,
            "lote_produccion": cabecera.lote_produccion_id,
            "movimientos": self.get_serializer(movimientos, many=True).data,
        }, status=201)

    @action(detail=False, methods=["post"], url_path="trasladar")
    def trasladar(self, request):
        try:
            existencia = _tenant_get(Existencia, request.user, request.data.get("existencia"), sucursal="ubicacion__bodega__sucursal_id", empresa="ubicacion__bodega__sucursal__empresa_id")
            movimiento = trasladar_existencia(
                existencia_id=existencia.pk,
                destino=_tenant_get(Ubicacion, request.user, request.data.get("destino"), sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id"),
                cantidad=request.data.get("cantidad"), usuario=request.user,
                documento_tipo=request.data.get("documento_tipo", "inventario.TrasladoManual"),
                documento_id=request.data.get("documento_id") or 0,
                motivo=request.data.get("motivo", ""),
            )
        except (Existencia.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=409)
        return Response(self.get_serializer(movimiento).data, status=201)


class AjusteInventarioViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "existencia__ubicacion__bodega__sucursal_id"
    tenant_lookup_empresa = "existencia__ubicacion__bodega__sucursal__empresa_id"
    queryset = AjusteInventario.objects.select_related("existencia__lote__insumo", "solicitante", "aprobador")
    serializer_class = AjusteInventarioSerializer
    permission_classes = [EscribeBodega]

    def create(self, request, *args, **kwargs):
        try:
            ajuste = crear_ajuste(
                existencia=_tenant_get(Existencia, request.user, request.data.get("existencia"), sucursal="ubicacion__bodega__sucursal_id", empresa="ubicacion__bodega__sucursal__empresa_id"),
                tipo=request.data.get("tipo"), cantidad=request.data.get("cantidad"),
                motivo=request.data.get("motivo", ""), solicitante=request.user,
            )
        except (Existencia.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=400)
        return Response(self.get_serializer(ajuste).data, status=201)

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        try:
            ajuste = decidir_y_aplicar_ajuste(
                ajuste=self.get_object(), aprobador=request.user,
                aprobar=request.data.get("decision") == "aprobar",
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)
        return Response(self.get_serializer(ajuste).data)


class DevolucionProduccionViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "detalle_entrega__entrega__solicitud__sucursal_id"
    tenant_lookup_empresa = "detalle_entrega__entrega__solicitud__sucursal__empresa_id"
    queryset = DevolucionProduccion.objects.select_related("detalle_entrega__lote__insumo", "registrada_por")
    serializer_class = DevolucionProduccionSerializer
    permission_classes = [EscribeBodega]

    def create(self, request, *args, **kwargs):
        try:
            estado = request.data.get("estado_material")
            destino = None
            if estado != DevolucionProduccion.EstadoMaterial.MERMA:
                destino = _tenant_get(Ubicacion, request.user, request.data.get("ubicacion_destino"), sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id")
                tipo_esperado = (
                    Ubicacion.Tipo.DISPONIBLE if estado == DevolucionProduccion.EstadoMaterial.UTILIZABLE
                    else Ubicacion.Tipo.RECHAZADO
                )
                if destino.tipo != tipo_esperado:
                    raise DjangoValidationError(
                        "El material utilizable debe volver a Disponible y el dañado a Rechazados."
                    )
            devolucion = registrar_devolucion(
                detalle_entrega=_tenant_get(DetalleEntregaProduccion, request.user, request.data.get("detalle_entrega"), sucursal="entrega__solicitud__sucursal_id", empresa="entrega__solicitud__sucursal__empresa_id"),
                cantidad=request.data.get("cantidad"), estado_material=estado,
                motivo=request.data.get("motivo", ""), usuario=request.user,
                ubicacion_destino=destino,
            )
        except (DetalleEntregaProduccion.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=400)
        return Response(self.get_serializer(devolucion).data, status=201)


class SolicitudCompraViewSet(SucursalTenantViewSetMixin, RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = SolicitudCompra.objects.select_related("solicitante")
    serializer_class = SolicitudCompraSerializer
    permission_classes = [EscribeCompras]

    def perform_create(self, serializer):
        serializer.save(
            solicitante=self.request.user,
            sucursal=sucursal_para_escritura(self.request.user, serializer.validated_data),
        )

    @action(detail=True, methods=["post"], url_path="enviar")
    def enviar(self, request, pk=None):
        solicitud = self.get_object()
        if solicitud.estado != solicitud.Estado.BORRADOR:
            return Response({"error": "Solo puede enviarse una solicitud en borrador."}, status=409)
        solicitud.estado = solicitud.Estado.PENDIENTE
        solicitud.save(update_fields=["estado"])
        return Response(self.get_serializer(solicitud).data)

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        try:
            solicitud = decidir_solicitud_compra(
                solicitud=self.get_object(), aprobador=request.user,
                decision=request.data.get("decision"),
                comentario=request.data.get("comentario", ""),
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)
        return Response(self.get_serializer(solicitud).data)

    @action(detail=True, methods=["post"], url_path="convertir")
    def convertir(self, request, pk=None):
        """
        Emite las órdenes de compra de esta solicitud, una por proveedor.

        El estado `convertida` existía en el modelo y no era alcanzable: nada
        convertía nada, así que una solicitud aprobada se quedaba aprobada
        para siempre y la orden se tecleaba aparte.
        """
        try:
            ordenes = convertir_solicitud_en_ordenes(
                solicitud=self.get_object(),
                usuario=request.user,
                bodega=_tenant_get(Bodega, request.user, request.data.get("bodega"), sucursal="sucursal_id", empresa="sucursal__empresa_id"),
            )
        except Bodega.DoesNotExist:
            return Response(
                {"error": "Indica la bodega donde se recibe el material."}, status=400
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)

        return Response(OrdenCompraSerializer(ordenes, many=True).data, status=201)


class OrdenCompraViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "bodega_entrega__sucursal_id"
    tenant_lookup_empresa = "bodega_entrega__sucursal__empresa_id"
    tenant_relation_fields = {
        "solicitud": ("sucursal_id", "sucursal__empresa_id"),
        "proveedor": (None, "empresa_id"),
        "bodega_entrega": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = OrdenCompra.objects.select_related("proveedor", "bodega_entrega").prefetch_related("detalles__insumo")
    serializer_class = OrdenCompraSerializer
    permission_classes = [EscribeCompras]

    @action(detail=True, methods=["post"], url_path="enviar")
    def enviar(self, request, pk=None):
        """
        La manda al proveedor. Hasta aquí era un borrador, y el MRP no cuenta
        un borrador como recepción programada: no compromete a nadie.
        """
        try:
            orden = enviar_orden_compra(orden=self.get_object())
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)

        return Response(self.get_serializer(orden).data)


class DetalleSolicitudCompraViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "solicitud__sucursal_id"
    tenant_lookup_empresa = "solicitud__sucursal__empresa_id"
    tenant_relation_fields = {"solicitud": ("sucursal_id", "sucursal__empresa_id"), "insumo": (None, "empresa_id")}
    queryset = DetalleSolicitudCompra.objects.select_related("solicitud", "insumo")
    serializer_class = DetalleSolicitudCompraSerializer
    permission_classes = [EscribeCompras]


class DetalleOrdenCompraViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "orden__bodega_entrega__sucursal_id"
    tenant_lookup_empresa = "orden__bodega_entrega__sucursal__empresa_id"
    tenant_relation_fields = {"orden": ("bodega_entrega__sucursal_id", "bodega_entrega__sucursal__empresa_id"), "insumo": (None, "empresa_id")}
    queryset = DetalleOrdenCompra.objects.select_related("orden", "insumo")
    serializer_class = DetalleOrdenCompraSerializer
    permission_classes = [EscribeCompras]


class DetalleSolicitudMaterialViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "solicitud__sucursal_id"
    tenant_lookup_empresa = "solicitud__sucursal__empresa_id"
    tenant_relation_fields = {"solicitud": ("sucursal_id", "sucursal__empresa_id"), "insumo": (None, "empresa_id")}
    queryset = DetalleSolicitudMaterial.objects.select_related("solicitud", "insumo")
    serializer_class = DetalleSolicitudMaterialSerializer
    permission_classes = [EscribeMRQ]


class RecepcionCompraViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "orden__bodega_entrega__sucursal_id"
    tenant_lookup_empresa = "orden__bodega_entrega__sucursal__empresa_id"
    tenant_relation_fields = {"orden": ("bodega_entrega__sucursal_id", "bodega_entrega__sucursal__empresa_id")}
    queryset = RecepcionCompra.objects.select_related("orden", "receptor")
    serializer_class = RecepcionCompraSerializer
    permission_classes = [EscribeRecepcionCompra]

    def perform_create(self, serializer):
        serializer.save(receptor=self.request.user)

    @action(detail=True, methods=["post"], url_path="recibir")
    def recibir(self, request, pk=None):
        recepcion = self.get_object()
        try:
            detalle = recibir_detalle_compra(
                recepcion=recepcion, detalle_orden_id=request.data.get("detalle_orden"),
                ubicacion=_tenant_get(Ubicacion, request.user, request.data.get("ubicacion"), sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id"),
                codigo_lote=request.data.get("codigo_lote", ""),
                cantidad=request.data.get("cantidad"), usuario=request.user,
                vencimiento=request.data.get("vencimiento") or None,
                elaboracion=request.data.get("elaboracion") or None,
                cantidad_danada=request.data.get("cantidad_danada", 0),
                temperatura=request.data.get("temperatura"),
                embalaje_conforme=request.data.get("embalaje_conforme", True),
                certificado_recibido=request.data.get("certificado_recibido", False),
            )
        except (ValueError, Ubicacion.DoesNotExist, DjangoValidationError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detalle": detalle.pk, "lote": detalle.lote_id}, status=status.HTTP_201_CREATED)


class InspeccionMaterialViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    queryset = InspeccionMaterial.objects.select_related("lote__insumo", "responsable")
    serializer_class = InspeccionMaterialSerializer
    permission_classes = [EscribeCalidad]

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        inspeccion = self.get_object()
        try:
            inspeccion = decidir_inspeccion(
                inspeccion_id=inspeccion.pk, decision=request.data.get("decision"),
                usuario=request.user, resultados=request.data.get("resultados", {}),
                observaciones=request.data.get("observaciones", ""),
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)
        return Response(self.get_serializer(inspeccion).data)


class SolicitudMaterialViewSet(SucursalTenantViewSetMixin, RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    tenant_relation_fields = {"lote_produccion": ("sucursal_id", "sucursal__empresa_id")}
    queryset = SolicitudMaterial.objects.select_related("solicitante", "lote_produccion").prefetch_related("detalles")
    serializer_class = SolicitudMaterialSerializer
    permission_classes = [EscribeMRQ]

    def get_permissions(self):
        clases = [EscribeBodega] if self.action in {"reservar", "entregar"} else self.permission_classes
        return [clase() for clase in clases]

    def perform_create(self, serializer):
        serializer.save(
            solicitante=self.request.user,
            sucursal=sucursal_para_escritura(self.request.user, serializer.validated_data),
        )

    @action(detail=True, methods=["post"], url_path="enviar")
    def enviar(self, request, pk=None):
        solicitud = self.get_object()
        if solicitud.estado != solicitud.Estado.BORRADOR:
            return Response({"error": "Solo puede enviarse una MRQ en borrador."}, status=409)
        if not solicitud.detalles.exists():
            return Response({"error": "La MRQ debe contener al menos un material."}, status=409)
        solicitud.estado = solicitud.Estado.ENVIADA
        solicitud.save(update_fields=["estado"])
        from usuarios.models import PerfilUsuario
        from .servicios import _notificar_area
        _notificar_area(
            PerfilUsuario.Area.BODEGA, tipo="mrq_enviada", titulo="Nueva solicitud de materiales",
            mensaje=f"La MRQ {solicitud.numero} requiere preparación.",
            documento_tipo="inventario.SolicitudMaterial", documento_id=solicitud.pk,
        )
        return Response(self.get_serializer(solicitud).data)

    @action(detail=True, methods=["post"], url_path="reservar")
    def reservar(self, request, pk=None):
        try:
            solicitud = reservar_solicitud_material(solicitud=self.get_object(), usuario=request.user)
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)
        return Response(self.get_serializer(solicitud).data)

    @action(detail=True, methods=["post"], url_path="entregar")
    def entregar(self, request, pk=None):
        from django.contrib.auth.models import User
        solicitud = self.get_object()
        try:
            destino_id = request.data.get("destino")
            destino = (
                _tenant_get(Ubicacion, request.user, destino_id, sucursal="bodega__sucursal_id", empresa="bodega__sucursal__empresa_id")
                if destino_id
                else filtrar_por_scope(Ubicacion.objects.all(), request.user, campo_sucursal="bodega__sucursal_id", campo_empresa="bodega__sucursal__empresa_id").filter(tipo=Ubicacion.Tipo.PRODUCCION, activo=True).order_by("id").first()
            )
            if destino is None:
                raise Ubicacion.DoesNotExist
            recibe_id = request.data.get("recibe_por") or solicitud.solicitante_id
            entrega = entregar_solicitud_material(
                solicitud=solicitud, destino=destino,
                entrega_por=request.user,
                recibe_por=User.objects.get(pk=recibe_id),
                selecciones=request.data.get("selecciones"),
                observaciones=request.data.get("observaciones", ""),
            )
        except (Ubicacion.DoesNotExist, User.DoesNotExist, DjangoValidationError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else "Destino o receptor inválido."
            return Response({"error": mensaje}, status=409)
        return Response({"entrega": entrega.pk, "estado": entrega.solicitud.estado}, status=201)


class NotificacionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        return Notificacion.objects.filter(destinatario=self.request.user)

    @action(detail=True, methods=["post"], url_path="leer")
    def leer(self, request, pk=None):
        from django.utils import timezone
        notificacion = self.get_object()
        notificacion.leida_en = timezone.now()
        notificacion.save(update_fields=["leida_en"])
        return Response(self.get_serializer(notificacion).data)


class EjecucionMRPViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = EjecucionMRP.objects.select_related("ejecutada_por").prefetch_related("resultados__insumo")
    serializer_class = EjecucionMRPSerializer
    permission_classes = [EsAdministrador]

    @action(detail=False, methods=["post"], url_path="ejecutar")
    def ejecutar(self, request):
        """
        Corre el MRP de una semana. **Una a la vez por semana.**

        La explosión multinivel ya no ocurre dentro de la petición: ocupaba un
        worker de Gunicorn de principio a fin, y con dos workers eso deja al
        resto de la planta esperando. Se encola y la pantalla consulta cómo va.

        El candado sigue haciendo falta aunque se encole: dos peticiones
        seguidas —o una persona pulsando dos veces porque no ve respuesta—
        meterían dos tareas idénticas en la cola.
        """
        from planificacion.models import SemanaPlan

        semana_id = request.data.get("semana")

        try:
            with solo_uno(f"mrp:semana:{semana_id}"):
                ejecucion = encolar_mrp_semana(
                    semana=_tenant_get(SemanaPlan, request.user, semana_id, sucursal="sucursal_id", empresa="sucursal__empresa_id"),
                    usuario=request.user,
                )
        except YaEnCurso:
            return Response(
                {"error": "El MRP de esta semana ya se está calculando. "
                          "Espera a que termine antes de volver a pedirlo."},
                status=status.HTTP_409_CONFLICT,
            )
        except (SemanaPlan.DoesNotExist, DjangoValidationError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else "La semana no existe."
            return Response({"error": mensaje}, status=409)

        # 202 y no 201: lo que se devuelve es la ejecución, no el resultado. La
        # pantalla consulta su estado hasta que termina. Sin worker ya viene
        # calculada, pero el contrato es el mismo — un solo camino que mantener.
        return Response(self.get_serializer(ejecucion).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="solicitar-compra")
    def solicitar_compra(self, request, pk=None):
        """
        Pasa lo que este cálculo dice que falta a una solicitud de compra.

        Cierra el circuito. Hasta aquí el MRP calculaba y ahí terminaba:
        alguien leía la pantalla y volvía a teclear las cantidades, que es
        donde se pierde el «para cuándo» y donde aparecen las diferencias
        entre lo calculado y lo pedido.
        """
        from django.db import IntegrityError

        try:
            solicitud = crear_solicitud_desde_mrp(
                ejecucion=self.get_object(), usuario=request.user
            )
        except IntegrityError:
            # `numero` lleva el id de la ejecución y es único, así que un
            # segundo intento sobre el mismo cálculo choca aquí. Es la
            # garantía de no duplicar la compra, no un accidente.
            return Response(
                {"error": "Esta ejecución ya generó su solicitud de compra."},
                status=409,
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)

        return Response(SolicitudCompraSerializer(solicitud).data, status=201)


class PlantillaInspeccionViewSet(EmpresaTenantViewSetMixin, RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_empresa = "empresa_id"
    tenant_relation_fields = {"insumo": (None, "empresa_id")}
    queryset = PlantillaInspeccion.objects.select_related("insumo")
    serializer_class = PlantillaInspeccionSerializer
    permission_classes = [EscribeCalidad]


class NoConformidadViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "inspeccion__lote__sucursal_id"
    tenant_lookup_empresa = "inspeccion__lote__sucursal__empresa_id"
    tenant_relation_fields = {"inspeccion": ("lote__sucursal_id", "lote__sucursal__empresa_id")}
    queryset = NoConformidadMaterial.objects.select_related(
        "inspeccion__lote__insumo", "creada_por", "cerrada_por", "liberacion"
    )
    serializer_class = NoConformidadSerializer
    permission_classes = [EscribeCalidad]

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)

    @action(detail=True, methods=["post"], url_path="cerrar")
    def cerrar(self, request, pk=None):
        """
        Cierra dejando qué se hizo con el material.

        No es un `PATCH cerrada=true`: el cierre exige la acción tomada y, si
        el destino es liberación excepcional, una concesión vigente que lo
        ampare. Por eso esos campos son de solo lectura en el serializer.
        """
        try:
            no_conformidad = cerrar_no_conformidad(
                no_conformidad=self.get_object(),
                usuario=request.user,
                accion_tomada=request.data.get("accion_tomada", ""),
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)

        return Response(self.get_serializer(no_conformidad).data)


class LiberacionExcepcionalViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    tenant_relation_fields = {
        "lote": ("sucursal_id", "sucursal__empresa_id"),
        "solicitante": ("perfil__sucursal_id", "perfil__empresa_id"),
    }
    queryset = LiberacionExcepcionalMaterial.objects.select_related("lote", "solicitante", "aprobada_calidad_por")
    serializer_class = LiberacionExcepcionalSerializer
    permission_classes = [EscribeCalidad]

    def perform_create(self, serializer):
        serializer.save(aprobada_calidad_por=self.request.user)


class AdjuntoViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = Adjunto.objects.select_related("autor")
    serializer_class = AdjuntoSerializer
    permission_classes = [EscribeRecepcionCompra]
    http_method_names = ["get", "post", "head", "options"]

    def perform_create(self, serializer):
        import hashlib
        archivo = self.request.FILES.get("archivo")
        digest = hashlib.sha256()
        if archivo:
            for bloque in archivo.chunks():
                digest.update(bloque)
            archivo.seek(0)
        serializer.save(
            autor=self.request.user,
            hash_sha256=digest.hexdigest(),
            sucursal=sucursal_para_escritura(self.request.user, serializer.validated_data),
        )


class AlertaViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    """
    Las alertas vigentes. Solo de lectura: no se marcan como vistas.

    Una alerta se apaga arreglando lo que la causó —reponiendo el material,
    liberando el lote— y `actualizar_alertas_inventario()` la recalcula en la
    siguiente operación. Poder cerrarlas a mano dejaría el panel limpio con el
    problema intacto, que es la forma más rápida de que nadie vuelva a mirarlo.

    Por omisión salen solo las activas; `?historico=1` trae también las
    resueltas, que es lo que sirve para preguntarse con qué frecuencia se
    repite un quiebre.
    """

    queryset = Alerta.objects.select_related("insumo", "lote")
    serializer_class = AlertaSerializer

    def get_queryset(self):
        consulta = super().get_queryset()

        if self.request.query_params.get("historico"):
            return consulta

        return consulta.filter(activa=True)


@api_view(["POST"])
@permission_classes([EsAdministrador])
def calcular_mrp(request):
    try:
        producto_id = int(request.data["producto"])
        kilos = Decimal(str(request.data["kilos_producir"]))
        if kilos <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return Response({"error": "Producto y kilos a producir son obligatorios."}, status=status.HTTP_400_BAD_REQUEST)

    # A la fecha de hoy: es un cálculo de «qué necesito para producir esto»,
    # así que manda la receta que rige ahora. El descuento de un lote, en
    # cambio, usa la que regía el día del lote.
    from maestros.models import Producto
    try:
        producto = _tenant_get(
            Producto, request.user, producto_id,
            sucursal=None, empresa="mandante__empresa_id",
        )
    except Producto.DoesNotExist:
        return Response({"error": "El producto no existe."}, status=status.HTTP_404_NOT_FOUND)

    explosion, requerido = insumos_requeridos(
        producto_id=producto.pk, cantidad=kilos, fecha=timezone.localdate()
    )

    por_id = {
        i.id: i for i in filtrar_por_scope(
            Insumo.objects.filter(id__in=requerido), request.user,
            campo_empresa="empresa_id",
        )
    }

    resultado = []
    for insumo_id in sorted(requerido):
        insumo = por_id[insumo_id]
        cantidad = requerido[insumo_id]
        existencias = filtrar_por_scope(
            Existencia.objects.select_related("lote").filter(lote__insumo=insumo),
            request.user,
            campo_sucursal="ubicacion__bodega__sucursal_id",
            campo_empresa="ubicacion__bodega__sucursal__empresa_id",
        )
        disponible = sum((e.cantidad_disponible for e in existencias), Decimal("0"))
        comprar = max(Decimal("0"), cantidad - disponible)
        envase = insumo.contenido_envase or Decimal("1")
        resultado.append({
            "insumo": insumo.nombre,
            "unidad": insumo.unidad,
            "requerido": cantidad,
            "stock": disponible,
            "faltante": comprar,
            "envases_a_pedir": ceil(comprar / envase),
            "eoq": insumo.eoq,
        })

    return Response({
        "kilos_producir": kilos,
        "materiales": resultado,
        # Si la cadena se cortó, el listado está incompleto y hay que decirlo:
        # una lista de materiales a medias se parece demasiado a una completa,
        # y con ella se emite una orden de compra corta.
        "receta_completa": explosion.completa,
    })


@api_view(["GET"])
def catalogos(request):
    """
    Opciones de los desplegables del módulo.

    Se sirven desde aquí y no se escriben en el frontend por la misma razón
    que en maestros y planificación: una copia en el cliente ofrece tarde o
    temprano un valor que el backend rechaza. Ya pasó — la pantalla de bodegas
    llevaba la lista de áreas a mano y se quedó sin «despacho» ni
    «mantenimiento» en cuanto el maestro las incorporó.
    """
    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    return Response(
        {
            "area": opciones(PerfilUsuario.Area.choices),
            "tipo_ubicacion": opciones(Ubicacion.Tipo.choices),
            "categoria_insumo": opciones(Insumo.Categoria.choices),
            "unidad_insumo": opciones(Insumo.Unidad.choices),
        }
    )
