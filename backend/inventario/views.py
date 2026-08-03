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
from .servicios import (
    consumir_receta_produccion, crear_ajuste, decidir_inspeccion, decidir_solicitud_compra,
    decidir_y_aplicar_ajuste, entregar_solicitud_material,
    ejecutar_mrp_semana, insumos_requeridos, recibir_detalle_compra, registrar_devolucion,
    ingresar_material_manual, registrar_entrada, registrar_salida, reservar_solicitud_material, trasladar_existencia,
)


class FiltroAreaAdminMixin:
    permission_classes = [EsAdministrador]

    def get_queryset(self):
        qs = super().get_queryset()
        perfil = getattr(self.request.user, "perfil", None)
        if self.request.user.is_superuser or (perfil and perfil.area == PerfilUsuario.Area.ADMINISTRACION):
            return qs
        return qs.filter(area=perfil.area) if perfil else qs.none()


class InsumoViewSet(FiltroAreaAdminMixin, viewsets.ModelViewSet):
    queryset = Insumo.objects.prefetch_related("lotes__existencias", "proveedores__proveedor")
    serializer_class = InsumoSerializer
    permission_classes = [EscribeBodega]


class CicloCIPViewSet(FiltroAreaAdminMixin, viewsets.ModelViewSet):
    queryset = CicloCIP.objects.select_related("responsable", "equipo")
    serializer_class = CicloCIPSerializer


class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    permission_classes = [EscribeCompras]


class InsumoProveedorViewSet(viewsets.ModelViewSet):
    queryset = InsumoProveedor.objects.select_related("insumo", "proveedor")
    serializer_class = InsumoProveedorSerializer
    permission_classes = [EscribeCompras]


class BodegaViewSet(viewsets.ModelViewSet):
    queryset = Bodega.objects.all()
    serializer_class = BodegaSerializer
    permission_classes = [EscribeBodega]


class UbicacionViewSet(viewsets.ModelViewSet):
    queryset = Ubicacion.objects.select_related("bodega")
    serializer_class = UbicacionSerializer
    permission_classes = [EscribeBodega]


class LoteInventarioViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = LoteInventario.objects.select_related("insumo", "proveedor")
    serializer_class = LoteInventarioSerializer
    permission_classes = [EscribeBodega]


class ExistenciaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Existencia.objects.select_related("lote__insumo", "ubicacion__bodega")
    serializer_class = ExistenciaSerializer
    permission_classes = [EscribeBodega]


class MovimientoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = MovimientoInventario.objects.select_related("lote__insumo", "origen", "destino", "usuario")
    serializer_class = MovimientoSerializer
    permission_classes = [EscribeBodega]

    @action(detail=False, methods=["post"], url_path="entrada")
    def entrada(self, request):
        try:
            movimiento = registrar_entrada(
                lote=LoteInventario.objects.get(pk=request.data.get("lote")),
                ubicacion=Ubicacion.objects.get(pk=request.data.get("ubicacion")),
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
                insumo=Insumo.objects.get(pk=request.data.get("insumo")),
                codigo_lote=request.data.get("codigo_lote", ""),
                ubicacion=Ubicacion.objects.get(pk=request.data.get("ubicacion")),
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
            movimiento = registrar_salida(
                existencia_id=request.data.get("existencia"), cantidad=request.data.get("cantidad"),
                usuario=request.user,
                documento_tipo=request.data.get("documento_tipo", "inventario.SalidaManual"),
                documento_id=request.data.get("documento_id") or 0,
                motivo=request.data.get("motivo", ""),
                consumo=request.data.get("tipo") == "consumo",
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
                lote_produccion=Lote.objects.get(pk=request.data.get("lote_produccion")),
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
            movimiento = trasladar_existencia(
                existencia_id=request.data.get("existencia"),
                destino=Ubicacion.objects.get(pk=request.data.get("destino")),
                cantidad=request.data.get("cantidad"), usuario=request.user,
                documento_tipo=request.data.get("documento_tipo", "inventario.TrasladoManual"),
                documento_id=request.data.get("documento_id") or 0,
                motivo=request.data.get("motivo", ""),
            )
        except (Existencia.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=409)
        return Response(self.get_serializer(movimiento).data, status=201)


class AjusteInventarioViewSet(viewsets.ModelViewSet):
    queryset = AjusteInventario.objects.select_related("existencia__lote__insumo", "solicitante", "aprobador")
    serializer_class = AjusteInventarioSerializer
    permission_classes = [EscribeBodega]

    def create(self, request, *args, **kwargs):
        try:
            ajuste = crear_ajuste(
                existencia=Existencia.objects.get(pk=request.data.get("existencia")),
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


class DevolucionProduccionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DevolucionProduccion.objects.select_related("detalle_entrega__lote__insumo", "registrada_por")
    serializer_class = DevolucionProduccionSerializer
    permission_classes = [EscribeBodega]

    def create(self, request, *args, **kwargs):
        try:
            estado = request.data.get("estado_material")
            destino = None
            if estado != DevolucionProduccion.EstadoMaterial.MERMA:
                destino = Ubicacion.objects.get(pk=request.data.get("ubicacion_destino"))
                tipo_esperado = (
                    Ubicacion.Tipo.DISPONIBLE if estado == DevolucionProduccion.EstadoMaterial.UTILIZABLE
                    else Ubicacion.Tipo.RECHAZADO
                )
                if destino.tipo != tipo_esperado:
                    raise DjangoValidationError(
                        "El material utilizable debe volver a Disponible y el dañado a Rechazados."
                    )
            devolucion = registrar_devolucion(
                detalle_entrega=DetalleEntregaProduccion.objects.get(pk=request.data.get("detalle_entrega")),
                cantidad=request.data.get("cantidad"), estado_material=estado,
                motivo=request.data.get("motivo", ""), usuario=request.user,
                ubicacion_destino=destino,
            )
        except (DetalleEntregaProduccion.DoesNotExist, Ubicacion.DoesNotExist, DjangoValidationError, ValueError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else str(error)
            return Response({"error": mensaje}, status=400)
        return Response(self.get_serializer(devolucion).data, status=201)


class SolicitudCompraViewSet(viewsets.ModelViewSet):
    queryset = SolicitudCompra.objects.select_related("solicitante")
    serializer_class = SolicitudCompraSerializer
    permission_classes = [EscribeCompras]

    def perform_create(self, serializer):
        serializer.save(solicitante=self.request.user)

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


class OrdenCompraViewSet(viewsets.ModelViewSet):
    queryset = OrdenCompra.objects.select_related("proveedor", "bodega_entrega").prefetch_related("detalles")
    serializer_class = OrdenCompraSerializer
    permission_classes = [EscribeCompras]


class DetalleSolicitudCompraViewSet(viewsets.ModelViewSet):
    queryset = DetalleSolicitudCompra.objects.select_related("solicitud", "insumo")
    serializer_class = DetalleSolicitudCompraSerializer
    permission_classes = [EscribeCompras]


class DetalleOrdenCompraViewSet(viewsets.ModelViewSet):
    queryset = DetalleOrdenCompra.objects.select_related("orden", "insumo")
    serializer_class = DetalleOrdenCompraSerializer
    permission_classes = [EscribeCompras]


class DetalleSolicitudMaterialViewSet(viewsets.ModelViewSet):
    queryset = DetalleSolicitudMaterial.objects.select_related("solicitud", "insumo")
    serializer_class = DetalleSolicitudMaterialSerializer
    permission_classes = [EscribeMRQ]


class RecepcionCompraViewSet(viewsets.ModelViewSet):
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
                ubicacion=Ubicacion.objects.get(pk=request.data.get("ubicacion")),
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


class InspeccionMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InspeccionMaterial.objects.select_related("lote__insumo", "responsable")
    serializer_class = InspeccionMaterialSerializer
    permission_classes = [EscribeCalidad]

    @action(detail=True, methods=["post"], url_path="decidir")
    def decidir(self, request, pk=None):
        try:
            inspeccion = decidir_inspeccion(
                inspeccion_id=pk, decision=request.data.get("decision"),
                usuario=request.user, resultados=request.data.get("resultados", {}),
                observaciones=request.data.get("observaciones", ""),
            )
        except DjangoValidationError as error:
            return Response({"error": error.messages[0]}, status=409)
        return Response(self.get_serializer(inspeccion).data)


class SolicitudMaterialViewSet(viewsets.ModelViewSet):
    queryset = SolicitudMaterial.objects.select_related("solicitante", "lote_produccion").prefetch_related("detalles")
    serializer_class = SolicitudMaterialSerializer
    permission_classes = [EscribeMRQ]

    def get_permissions(self):
        clases = [EscribeBodega] if self.action in {"reservar", "entregar"} else self.permission_classes
        return [clase() for clase in clases]

    def perform_create(self, serializer):
        serializer.save(solicitante=self.request.user)

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
                Ubicacion.objects.get(pk=destino_id)
                if destino_id
                else Ubicacion.objects.filter(tipo=Ubicacion.Tipo.PRODUCCION, activo=True).order_by("id").first()
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


class EjecucionMRPViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EjecucionMRP.objects.select_related("ejecutada_por").prefetch_related("resultados__insumo")
    serializer_class = EjecucionMRPSerializer
    permission_classes = [EsAdministrador]

    @action(detail=False, methods=["post"], url_path="ejecutar")
    def ejecutar(self, request):
        from planificacion.models import SemanaPlan
        try:
            ejecucion = ejecutar_mrp_semana(
                semana=SemanaPlan.objects.get(pk=request.data.get("semana")),
                usuario=request.user,
            )
        except (SemanaPlan.DoesNotExist, DjangoValidationError) as error:
            mensaje = error.messages[0] if isinstance(error, DjangoValidationError) else "La semana no existe."
            return Response({"error": mensaje}, status=409)
        return Response(self.get_serializer(ejecucion).data, status=201)


class PlantillaInspeccionViewSet(viewsets.ModelViewSet):
    queryset = PlantillaInspeccion.objects.select_related("insumo")
    serializer_class = PlantillaInspeccionSerializer
    permission_classes = [EscribeCalidad]


class NoConformidadViewSet(viewsets.ModelViewSet):
    queryset = NoConformidadMaterial.objects.select_related("inspeccion__lote", "creada_por")
    serializer_class = NoConformidadSerializer
    permission_classes = [EscribeCalidad]

    def perform_create(self, serializer):
        serializer.save(creada_por=self.request.user)


class LiberacionExcepcionalViewSet(viewsets.ModelViewSet):
    queryset = LiberacionExcepcionalMaterial.objects.select_related("lote", "solicitante", "aprobada_calidad_por")
    serializer_class = LiberacionExcepcionalSerializer
    permission_classes = [EscribeCalidad]

    def perform_create(self, serializer):
        serializer.save(aprobada_calidad_por=self.request.user)


class AdjuntoViewSet(viewsets.ModelViewSet):
    queryset = Adjunto.objects.select_related("autor")
    serializer_class = AdjuntoSerializer
    permission_classes = [EscribeRecepcionCompra]

    def perform_create(self, serializer):
        import hashlib
        archivo = self.request.FILES.get("archivo")
        digest = hashlib.sha256()
        if archivo:
            for bloque in archivo.chunks():
                digest.update(bloque)
            archivo.seek(0)
        serializer.save(autor=self.request.user, hash_sha256=digest.hexdigest())


class AlertaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Alerta.objects.select_related("insumo", "lote")
    serializer_class = AlertaSerializer


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
    explosion, requerido = insumos_requeridos(
        producto_id=producto_id, cantidad=kilos, fecha=timezone.localdate()
    )

    por_id = {i.id: i for i in Insumo.objects.filter(id__in=requerido)}

    resultado = []
    for insumo_id in sorted(requerido):
        insumo = por_id[insumo_id]
        cantidad = requerido[insumo_id]
        existencias = Existencia.objects.select_related("lote").filter(lote__insumo=insumo)
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
