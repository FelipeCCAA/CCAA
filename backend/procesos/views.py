from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import DecimalField, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from usuarios.permisos import EscribeProduccion
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope, scope_de,
    sucursal_para_escritura,
)
from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla,
    EjecucionProceso, EntradaProceso,
    EtapaProceso, Proceso, RutaProducto,
    SalidaProceso,
)
from .serializers import (
    CierreCondensacionSerializer, CierreDescremacionSerializer,
    CierreMantequillaSerializer, CrearCondensacionGuiadaSerializer,
    CrearMantequillaGuiadaSerializer, CorridaCondensacionSerializer,
    CorridaDescremacionSerializer, CorridaMantequillaSerializer,
    EjecucionProcesoSerializer, EntradaProcesoSerializer, EtapaProcesoSerializer,
    ProcesoSerializer, SalidaProcesoSerializer,
    RutaProductoSerializer,
)
from .servicios import (
    cerrar_condensacion, cerrar_descremacion, cerrar_mantequilla, genealogia_lote,
    crear_condensacion_guiada, crear_mantequilla_guiada,
    iniciar_condensacion, iniciar_descremacion, iniciar_mantequilla,
    preparar_continuacion, tipos_equipo_para_etapa, transicionar_ejecucion,
)


class ProcesoViewSet(viewsets.ModelViewSet):
    queryset = Proceso.objects.prefetch_related("etapas")
    serializer_class = ProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]


class EtapaProcesoViewSet(viewsets.ModelViewSet):
    queryset = EtapaProceso.objects.select_related("proceso")
    serializer_class = EtapaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]


class RutaProductoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    tenant_relation_fields = {
        "producto": (None, "mandante__empresa_id"),
    }
    queryset = RutaProducto.objects.select_related(
        "sucursal", "producto", "proceso"
    ).prefetch_related("proceso__etapas")
    serializer_class = RutaProductoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(sucursal=sucursal_para_escritura(
            self.request.user, serializer.validated_data
        ))


class CorridaCondensacionViewSet(
    RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet
):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "orden": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
        "silo_origen": ("sucursal_id", "sucursal__empresa_id"),
        "silo_destino": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = CorridaCondensacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
        "silo_origen", "silo_destino", "iniciada_por", "finalizada_por",
    )
    serializer_class = CorridaCondensacionSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]

    @staticmethod
    def _respuesta_error(error):
        detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
        return Response(detalle, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="opciones-alta")
    def opciones_alta(self, request):
        from maestros.models import Silo
        from produccion.models import Lote, OrdenProduccion

        lotes = filtrar_por_scope(
            Lote.objects.filter(
                estado=Lote.Estado.EN_PROCESO,
                orden__estado__in=[
                    OrdenProduccion.Estado.PROGRAMADA,
                    OrdenProduccion.Estado.EN_PROCESO,
                ],
                ejecucion__etapa__tipo__in=[
                    EtapaProceso.Tipo.EVAPORACION, EtapaProceso.Tipo.CONDENSACION,
                ],
                ejecucion__corrida_condensacion__isnull=True,
            ).select_related(
                "orden", "producto", "ejecucion__equipo"
            ).prefetch_related("ejecucion__entradas__silo"),
            request.user, campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        silos = filtrar_por_scope(
            Silo.objects.filter(activo=True).annotate(
                ingresos=Coalesce(
                    Sum("movimientos__litros", filter=Q(movimientos__tipo="ingreso")),
                    Value(0), output_field=DecimalField(),
                ),
                salidas=Coalesce(
                    Sum("movimientos__litros", filter=Q(movimientos__tipo="salida")),
                    Value(0), output_field=DecimalField(),
                ),
                ajustes=Coalesce(
                    Sum("movimientos__litros", filter=Q(movimientos__tipo="ajuste")),
                    Value(0), output_field=DecimalField(),
                ),
            ),
            request.user, campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        return Response({
            "lotes": [
                {
                    "id": lote.pk, "codigo": lote.codigo_lote,
                    "producto": lote.producto.nombre, "orden": lote.orden.codigo,
                    "ejecucion": lote.ejecucion.codigo,
                    "equipo": lote.ejecucion.equipo.nombre if lote.ejecucion.equipo else None,
                    "origen": entrada.silo.codigo if entrada and entrada.silo else None,
                    "litros": entrada.cantidad if entrada else None,
                }
                for lote in lotes
                for entrada in [next(iter(lote.ejecucion.entradas.all()), None)]
                if entrada and entrada.silo_id and entrada.unidad.lower() == "l"
            ],
            "silos": [
                {
                    "id": silo.pk, "codigo": silo.codigo,
                    "estado": silo.get_estado_display(), "capacidad_l": silo.capacidad_l,
                    "saldo_l": silo.ingresos - silo.salidas + silo.ajustes,
                }
                for silo in silos
            ],
        })

    @action(detail=False, methods=["post"], url_path="crear-guiada")
    def crear_guiada(self, request):
        from maestros.models import Silo
        from produccion.models import Lote

        entrada = CrearCondensacionGuiadaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        lotes = filtrar_por_scope(
            Lote.objects.all(), request.user, campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        silos = filtrar_por_scope(
            Silo.objects.all(), request.user, campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        if not lotes.filter(pk=datos["lote"]).exists() or not silos.filter(pk=datos["silo_destino"]).exists():
            return Response({"error": "El lote o silo no pertenece a tu alcance."}, status=403)
        try:
            corrida = crear_condensacion_guiada(
                lote_id=datos["lote"], silo_destino_id=datos["silo_destino"],
                usuario=request.user,
            )
        except DjangoValidationError as error:
            return self._respuesta_error(error)
        return Response(self.get_serializer(corrida).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        try:
            corrida = iniciar_condensacion(
                corrida_id=self.get_object().pk, usuario=request.user
            )
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
            return Response(detalle, status=status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(corrida).data)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        entrada = CierreCondensacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data.copy()
        litros = datos.pop("litros_precondensado")
        try:
            corrida = cerrar_condensacion(
                corrida_id=self.get_object().pk, usuario=request.user,
                litros_precondensado=litros, controles=datos,
            )
        except DjangoValidationError as error:
            return self._respuesta_error(error)
        return Response(self.get_serializer(corrida).data)


class CorridaDescremacionViewSet(
    RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet
):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "orden": ("sucursal_id", "sucursal__empresa_id"),
        "silo_entera": ("sucursal_id", "sucursal__empresa_id"),
        "silo_descremada": ("sucursal_id", "sucursal__empresa_id"),
        "estanque_crema": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "silo_entera", "silo_descremada", "estanque_crema",
    )
    serializer_class = CorridaDescremacionSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]

    @staticmethod
    def _error(error, codigo=status.HTTP_400_BAD_REQUEST):
        detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
        return Response(detalle, status=codigo)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        try:
            corrida = iniciar_descremacion(
                corrida_id=self.get_object().pk, usuario=request.user
            )
        except DjangoValidationError as error:
            return self._error(error, status.HTTP_409_CONFLICT)
        return Response(self.get_serializer(corrida).data)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        entrada = CierreDescremacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            corrida = cerrar_descremacion(
                corrida_id=self.get_object().pk, usuario=request.user,
                **entrada.validated_data,
            )
        except DjangoValidationError as error:
            return self._error(error)
        return Response(self.get_serializer(corrida).data)


class CorridaMantequillaViewSet(
    RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet
):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "orden": ("sucursal_id", "sucursal__empresa_id"),
        "lote_crema": ("sucursal_id", "sucursal__empresa_id"),
        "lote_mantequilla": ("sucursal_id", "sucursal__empresa_id"),
        "lote_suero": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = CorridaMantequilla.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto", "lote_suero",
    )
    serializer_class = CorridaMantequillaSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"], url_path="opciones-alta")
    def opciones_alta(self, request):
        from maestros.models import Equipo
        from produccion.models import Lote, OrdenProduccion

        ordenes = filtrar_por_scope(
            OrdenProduccion.objects.filter(
                producto__categoria="mantequilla",
                estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
            ).select_related("producto"), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        lotes = filtrar_por_scope(
            Lote.objects.filter(
                estado__in=[Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
                kg_producidos__isnull=False,
            ).select_related("producto").annotate(
                kg_usados=Coalesce(
                    Sum("entradas_proceso__cantidad", filter=Q(entradas_proceso__unidad__iexact="kg")),
                    Value(0), output_field=DecimalField(),
                )
            ), request.user, campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        equipos = filtrar_por_scope(
            Equipo.objects.filter(activo=True, tipo__in=[Equipo.Tipo.LINEA, Equipo.Tipo.OTRO]),
            request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        return Response({
            "ordenes": [{"id": item.pk, "codigo": item.codigo, "producto": item.producto.nombre} for item in ordenes],
            "cremas": [
                {"id": item.pk, "codigo": item.codigo_lote, "producto": item.producto.nombre,
                 "disponible_kg": item.kg_producidos - item.kg_usados}
                for item in lotes if item.producto.familia == "crema" and item.kg_producidos > item.kg_usados
            ],
            "sueros": [
                {"id": item.pk, "codigo": item.codigo_lote, "producto": item.producto.nombre}
                for item in lotes if "suero" in item.producto.nombre.lower()
            ],
            "equipos": [{"id": item.pk, "nombre": item.nombre, "tipo": item.tipo} for item in equipos],
        })

    @action(detail=False, methods=["post"], url_path="crear-guiada")
    def crear_guiada(self, request):
        from maestros.models import Equipo
        from produccion.models import Lote, OrdenProduccion

        entrada = CrearMantequillaGuiadaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        alcance = {
            "orden": filtrar_por_scope(OrdenProduccion.objects.all(), request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id"),
            "lote": filtrar_por_scope(Lote.objects.all(), request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id"),
            "equipo": filtrar_por_scope(Equipo.objects.all(), request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id"),
        }
        ids_validos = (
            alcance["orden"].filter(pk=datos["orden"]).exists()
            and alcance["lote"].filter(pk=datos["lote_crema"]).exists()
            and alcance["equipo"].filter(pk=datos["equipo"]).exists()
            and (not datos.get("lote_suero") or alcance["lote"].filter(pk=datos["lote_suero"]).exists())
        )
        if not ids_validos:
            return Response({"error": "Alguna selección no pertenece a tu alcance."}, status=403)
        try:
            corrida = crear_mantequilla_guiada(
                orden_id=datos["orden"], lote_crema_id=datos["lote_crema"],
                equipo_id=datos["equipo"],
                codigo_lote_mantequilla=datos["codigo_lote_mantequilla"],
                lote_suero_id=datos.get("lote_suero"), kg_crema=datos["kg_crema"],
                usuario=request.user,
            )
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(corrida).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def iniciar(self, request, pk=None):
        try:
            corrida = iniciar_mantequilla(corrida_id=self.get_object().pk, usuario=request.user)
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(corrida).data)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        entrada = CierreMantequillaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            corrida = cerrar_mantequilla(
                corrida_id=self.get_object().pk, usuario=request.user,
                **entrada.validated_data,
            )
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(corrida).data)

class EjecucionProcesoViewSet(RelacionesTenantMixin, viewsets.ModelViewSet):
    tenant_relation_fields = {
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
    }
    serializer_class = EjecucionProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = EjecucionProceso.objects.select_related(
            "etapa__proceso", "equipo", "responsable", "sucursal", "vale",
            "lote_produccion", "lote_produccion__producto",
        ).prefetch_related(
            "entradas__lote__producto", "entradas__silo",
            "salidas__lote__producto", "salidas__silo", "eventos__usuario"
        )
        estado = self.request.query_params.get("estado")
        etapa = self.request.query_params.get("etapa")
        if estado:
            queryset = queryset.filter(estado=estado)
        if etapa:
            queryset = queryset.filter(etapa_id=etapa)
        return filtrar_por_scope(
            queryset, self.request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    def perform_create(self, serializer):
        serializer.save(
            responsable=self.request.user,
            sucursal=sucursal_para_escritura(
                self.request.user, serializer.validated_data
            ),
        )

    def perform_update(self, serializer):
        if not serializer.instance.editable:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Una ejecución cerrada o cancelada es inmutable.")
        serializer.save()

    @action(detail=False, methods=["get"], url_path="operativas")
    def operativas(self, request):
        """Bandeja liviana: solo ejecuciones que todavía requieren operación."""
        queryset = filtrar_por_scope(
            EjecucionProceso.objects.exclude(
                estado__in={EjecucionProceso.Estado.CERRADA, EjecucionProceso.Estado.CANCELADA}
            ).select_related("etapa", "equipo").prefetch_related(
                "entradas__silo", "entradas__lote", "salidas__silo", "salidas__lote"
            ),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        return Response([
            {
                "id": ejecucion.id,
                "codigo": ejecucion.codigo,
                "estado": ejecucion.estado,
                "estado_etiqueta": ejecucion.get_estado_display(),
                "etapa_nombre": ejecucion.etapa.nombre,
                "etapa_tipo": ejecucion.etapa.tipo,
                "equipo_nombre": ejecucion.equipo.nombre if ejecucion.equipo else None,
                "acciones_permitidas": sorted(
                    EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set())
                ),
                "entradas": [
                    entrada.lote.codigo_lote if entrada.lote else entrada.silo.codigo
                    for entrada in ejecucion.entradas.all()
                ],
                "salidas": [
                    salida.lote.codigo_lote if salida.lote else salida.silo.codigo
                    for salida in ejecucion.salidas.all()
                    if salida.lote_id or salida.silo_id
                ],
            }
            for ejecucion in queryset
        ])

    @action(detail=True, methods=["post"])
    def transicionar(self, request, pk=None):
        try:
            ejecucion = transicionar_ejecucion(
                ejecucion_id=self.get_object().pk,
                estado_nuevo=request.data.get("estado", ""),
                motivo=request.data.get("motivo", ""),
                usuario=request.user,
            )
        except DjangoValidationError as error:
            # `.messages[0]` y no `.message`: el segundo solo existe cuando el
            # error se levantó con un string suelto. Con un dict o una lista
            # —como los que levanta `SalidaProceso.clean()` en este mismo
            # módulo— no existe, y el 400 se convertiría en un 500.
            return Response(
                {"error": error.messages[0]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(self.get_serializer(ejecucion).data)


class EntradaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
        "salida_origen": (
            "ejecucion__sucursal_id", "ejecucion__sucursal__empresa_id"
        ),
    }
    queryset = EntradaProceso.objects.select_related(
        "ejecucion", "lote__producto", "silo", "salida_origen__ejecucion"
    )
    serializer_class = EntradaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]


class SalidaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = SalidaProceso.objects.select_related("ejecucion", "lote__producto")
    serializer_class = SalidaProcesoSerializer
    permission_classes = [EscribeProduccion]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"], url_path="disponibles")
    def disponibles(self, request):
        """Resultados liberados, con saldo y próximas etapas configuradas."""
        from calidad.models import LiberacionProceso

        salidas = filtrar_por_scope(
            SalidaProceso.objects.filter(
                liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
                silo__isnull=False,
                destino__in=[
                    SalidaProceso.Destino.PENDIENTE,
                    SalidaProceso.Destino.SIGUIENTE_PROCESO,
                ],
            ).exclude(
                naturaleza=SalidaProceso.Naturaleza.MERMA
            ).select_related(
                "ejecucion__etapa__proceso", "ejecucion__equipo", "silo",
                "liberacion_calidad",
            ).annotate(consumido=Sum("usos_como_origen__cantidad")),
            request.user,
            campo_sucursal="ejecucion__sucursal_id",
            campo_empresa="ejecucion__sucursal__empresa_id",
        )
        salidas = [
            salida for salida in salidas
            if salida.cantidad - (salida.consumido or 0) > 0
        ]
        procesos_ids = {salida.ejecucion.etapa.proceso_id for salida in salidas}
        sucursales_ids = {salida.ejecucion.sucursal_id for salida in salidas}
        etapas_por_proceso = {}
        for etapa in EtapaProceso.objects.filter(
            proceso_id__in=procesos_ids, activa=True
        ).order_by("proceso_id", "orden"):
            etapas_por_proceso.setdefault(etapa.proceso_id, []).append(etapa)

        from maestros.models import Equipo
        equipos = Equipo.objects.filter(
            sucursal_id__in=sucursales_ids, activo=True
        ).order_by("orden", "nombre")
        ocupaciones = {
            ejecucion.equipo_id: ejecucion.codigo
            for ejecucion in EjecucionProceso.objects.filter(
                sucursal_id__in=sucursales_ids,
                estado=EjecucionProceso.Estado.EJECUCION,
                equipo_id__isnull=False,
            ).only("equipo_id", "codigo")
        }

        return Response([
            {
                "id": salida.id,
                "corrida_codigo": salida.ejecucion.codigo,
                "resultado": (
                    "Crema"
                    if salida.naturaleza == SalidaProceso.Naturaleza.COPRODUCTO
                    else salida.ejecucion.etapa.nombre
                ),
                "silo_id": salida.silo_id,
                "silo_codigo": salida.silo.codigo,
                "cantidad_total": salida.cantidad,
                "cantidad_consumida": salida.consumido or 0,
                "cantidad_disponible": salida.cantidad - (salida.consumido or 0),
                "unidad": salida.unidad,
                "clasificacion": salida.clasificacion,
                "clasificacion_etiqueta": salida.get_clasificacion_display(),
                "destino": salida.destino,
                "destino_etiqueta": salida.get_destino_display(),
                "destinos_permitidos": [
                    {"valor": valor, "etiqueta": dict(SalidaProceso.Destino.choices)[valor]}
                    for valor in sorted(salida.destinos_permitidos())
                ],
                "etapas_siguientes": [
                    {
                        "id": etapa.id,
                        "nombre": etapa.nombre,
                        "tipo": etapa.tipo,
                        "orden": etapa.orden,
                        "equipos": [
                            {
                                "id": equipo.id,
                                "nombre": equipo.nombre,
                                "tipo": equipo.tipo,
                                "ocupado_por": ocupaciones.get(equipo.id),
                            }
                            for equipo in equipos
                            if (
                                equipo.sucursal_id == salida.ejecucion.sucursal_id
                                and equipo.tipo in tipos_equipo_para_etapa(etapa.tipo)
                            )
                        ],
                    }
                    for etapa in etapas_por_proceso.get(
                        salida.ejecucion.etapa.proceso_id, []
                    )
                    if etapa.orden == min(
                        (
                            candidata.orden
                            for candidata in etapas_por_proceso.get(
                                salida.ejecucion.etapa.proceso_id, []
                            )
                            if candidata.orden > salida.ejecucion.etapa.orden
                        ),
                        default=-1,
                    )
                ],
            }
            for salida in salidas
        ])

    @action(detail=True, methods=["post"], url_path="preparar-continuacion")
    def preparar_continuacion(self, request, pk=None):
        salida = self.get_object()
        try:
            ejecucion = preparar_continuacion(
                salida_id=salida.pk,
                etapa_id=request.data.get("etapa"),
                equipo_id=request.data.get("equipo"),
                cantidad=request.data.get("cantidad"),
                usuario=request.user,
            )
        except (DjangoValidationError, ValueError, TypeError) as error:
            mensajes = getattr(error, "messages", None)
            return Response(
                {"error": mensajes[0] if mensajes else "Datos de continuación inválidos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            EjecucionProcesoSerializer(ejecucion).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="definir-destino")
    def definir_destino(self, request, pk=None):
        salida = self.get_object()
        destino = request.data.get("destino", "")
        if destino not in salida.destinos_permitidos():
            return Response(
                {"error": "El destino no es compatible con este producto intermedio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if salida.usos_como_origen.exists() and destino != SalidaProceso.Destino.SIGUIENTE_PROCESO:
            return Response(
                {"error": "La salida ya fue consumida por otro proceso y no puede cambiar de destino."},
                status=status.HTTP_409_CONFLICT,
            )
        if salida.detalles_despacho_granel.exclude(
            despacho__estado="cancelado"
        ).exists() and destino != SalidaProceso.Destino.DESPACHO_DIRECTO:
            return Response(
                {"error": "La salida ya forma parte de un despacho y no puede cambiar de destino."},
                status=status.HTTP_409_CONFLICT,
            )
        salida.destino = destino
        salida.save(update_fields=["destino"])
        return Response(self.get_serializer(salida).data)


@api_view(["GET"])
def trazabilidad(request, lote):
    """
    Genealogía de un lote, hacia atrás o hacia adelante.

    Acepta el **código de lote** además del id. El id es de la base de datos y
    nadie en planta lo conoce: quien pregunta de dónde salió un saco tiene en
    la mano un `CCAA6212010102010201-01`, no un 47. Pedirle el id volvía la
    pantalla inservible para quien la necesita.
    """
    from produccion.models import Lote, PalletProducto

    direccion = request.query_params.get("direccion", "atras")

    lotes = filtrar_por_scope(
        Lote.objects.select_related(
            "producto", "equipo", "ejecucion",
            "vale__silo_destino", "vale__ejecucion",
            "liberacion__autorizada_por",
        ), request.user,
        campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    )
    if str(lote).isdigit():
        encontrado = lotes.filter(pk=int(lote)).first()
    else:
        encontrado = lotes.filter(codigo_lote=lote).first()
        if encontrado is None:
            pallet = filtrar_por_scope(
                PalletProducto.objects.select_related("envase__lote"), request.user,
                campo_sucursal="envase__lote__sucursal_id",
                campo_empresa="envase__lote__sucursal__empresa_id",
            ).filter(codigo=lote).first()
            # Recuperarlo desde el queryset enriquecido evita que el camino
            # por pallet pierda los ``select_related`` que usa el flujo.
            encontrado = (
                lotes.filter(pk=pallet.envase.lote_id).first() if pallet else None
            )

    if encontrado is None:
        return Response(
            {"error": f"No existe un lote «{lote}»."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        scope = scope_de(request.user, requerido=True)
        datos = genealogia_lote(
            encontrado.pk, direccion,
            sucursal_id=scope.sucursal_id if scope.es_sucursal else None,
            empresa_id=scope.empresa_id if scope.es_empresa else None,
        )
    except ValueError as error:
        return Response({"error": str(error)}, status=400)

    return Response({
        **datos,
        "raiz": encontrado.pk,
        "flujo": _flujo_completo(encontrado),
    })


def _flujo_completo(lote):
    """Recepción → estandarización → producción para una corrida concreta."""
    from inventario.models import DetalleDespacho
    from produccion.models import PalletProducto
    from recepcion.models import MovimientoSilo, Recepcion

    vale = lote.vale
    if vale is None:
        return None

    consumos_estandarizacion = list(
        MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.pk,
        ).select_related("silo")
    )

    # Todos los ingresos candidatos se consultan juntos. Antes cada consumo
    # de estandarización hacía una consulta por ids y otra por recepciones.
    # Se conserva el corte temporal propio de cada consumo al agruparlos en
    # memoria.
    filtro_ingresos = Q(pk__in=[])
    for consumo in consumos_estandarizacion:
        filtro_ingresos |= Q(
            silo_id=consumo.silo_id, fecha_hora__lte=consumo.fecha_hora
        )
    ingresos = list(
        MovimientoSilo.objects.filter(
            filtro_ingresos,
            tipo=MovimientoSilo.Tipo.INGRESO,
            origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
        ).only("silo_id", "origen_id", "fecha_hora")
    ) if consumos_estandarizacion else []
    recepciones_por_orden = list(
        Recepcion.objects.filter(
            pk__in={ingreso.origen_id for ingreso in ingresos}
        ).select_related("vehiculo")
    )

    recepciones = []
    vistos = set()
    for consumo in consumos_estandarizacion:
        ids = {
            ingreso.origen_id
            for ingreso in ingresos
            if ingreso.silo_id == consumo.silo_id
            and ingreso.fecha_hora <= consumo.fecha_hora
        }
        for recepcion in recepciones_por_orden:
            if recepcion.pk not in ids:
                continue
            clave = (recepcion.pk, consumo.silo_id)
            if clave in vistos:
                continue
            vistos.add(clave)
            recepciones.append({
                "id": recepcion.pk,
                "fecha": recepcion.fecha,
                "guia": recepcion.guia,
                "litros": recepcion.litros,
                "vehiculo": recepcion.vehiculo.placa if recepcion.vehiculo else None,
                "silo_codigo": consumo.silo.codigo,
            })

    ejecucion_est = getattr(vale, "ejecucion", None)
    ejecucion_prod = lote.ejecucion
    pallets_serializables = PalletProducto.objects.select_related(
        "existencia_producto__ubicacion"
    ).prefetch_related(
        Prefetch(
            "detalles_despacho",
            queryset=DetalleDespacho.objects.filter(
                despacho__estado="despachado"
            ).select_related("despacho__cliente").order_by("pk"),
            to_attr="detalles_despachados",
        )
    )
    pallets = []
    for envase in lote.registros_envase.prefetch_related(
        Prefetch("pallets", queryset=pallets_serializables)
    ):
        for pallet in envase.pallets.all():
            existencia = getattr(pallet, "existencia_producto", None)
            detalle = (
                pallet.detalles_despachados[0]
                if pallet.detalles_despachados else None
            )
            pallets.append({
                "id": pallet.pk,
                "codigo": pallet.codigo,
                "unidades": pallet.unidades,
                "kg_neto": pallet.kg_neto,
                "estado": pallet.get_estado_display(),
                "ubicacion": existencia.ubicacion.codigo if existencia and existencia.activo else None,
                "despacho": detalle.despacho.numero if detalle else None,
                "cliente": detalle.despacho.cliente.nombre if detalle else None,
            })
    liberacion = getattr(lote, "liberacion", None)

    visitadas = set()
    cadena = []

    def agregar_ejecucion(ejecucion):
        if ejecucion is None or ejecucion.pk in visitadas:
            return
        visitadas.add(ejecucion.pk)
        entradas = list(
            ejecucion.entradas.select_related(
                "salida_origen__ejecucion__etapa", "lote", "silo"
            )
        )
        for entrada in entradas:
            if entrada.salida_origen_id:
                agregar_ejecucion(entrada.salida_origen.ejecucion)
        cadena.append({
            "id": ejecucion.pk,
            "codigo": ejecucion.codigo,
            "etapa": ejecucion.etapa.nombre,
            "tipo": ejecucion.etapa.tipo,
            "estado": ejecucion.get_estado_display(),
            "equipo": ejecucion.equipo.nombre if ejecucion.equipo_id else None,
            "entradas": [
                {
                    "origen": (
                        entrada.salida_origen.ejecucion.codigo
                        if entrada.salida_origen_id
                        else entrada.lote.codigo_lote
                        if entrada.lote_id
                        else entrada.silo.codigo
                    ),
                    "cantidad": entrada.cantidad,
                    "unidad": entrada.unidad,
                    "tipo": entrada.get_tipo_display(),
                }
                for entrada in entradas
            ],
            "salidas": [
                {
                    "id": salida.pk,
                    "clase": salida.get_clasificacion_display(),
                    "destino": salida.get_destino_display(),
                    "cantidad": salida.cantidad,
                    "unidad": salida.unidad,
                }
                for salida in ejecucion.salidas.all()
            ],
        })

    agregar_ejecucion(ejecucion_prod)
    agregar_ejecucion(ejecucion_est)
    return {
        "recepciones": recepciones,
        "nota_recepciones": (
            "Son recepciones candidatas: dentro del silo la leche se mezcla "
            "y no existe una relación uno a uno."
        ),
        "estandarizacion": {
            "vale_id": vale.pk,
            "vale_codigo": vale.codigo,
            "ejecucion_id": ejecucion_est.pk if ejecucion_est else None,
            "ejecucion_codigo": ejecucion_est.codigo if ejecucion_est else None,
            "silos_origen": [
                {
                    "codigo": movimiento.silo.codigo,
                    "litros": movimiento.litros,
                }
                for movimiento in consumos_estandarizacion
            ],
            "silo_destino": vale.silo_destino.codigo,
            "rc_objetivo": vale.rc_objetivo,
            "rc_real": vale.rc_real,
        },
        "produccion": {
            "lote_id": lote.pk,
            "lote_codigo": lote.codigo_lote,
            "producto": lote.producto.nombre,
            "linea": lote.linea,
            "equipo": lote.equipo.nombre if lote.equipo else None,
            "ejecucion_id": ejecucion_prod.pk if ejecucion_prod else None,
            "ejecucion_codigo": ejecucion_prod.codigo if ejecucion_prod else None,
            "estado": lote.get_estado_display(),
        },
        "calidad": {
            "estado": liberacion.get_estado_display() if liberacion else "Pendiente",
            "autorizada_por": (
                liberacion.autorizada_por.get_full_name() or liberacion.autorizada_por.username
                if liberacion and liberacion.autorizada_por else None
            ),
            "autorizada_en": liberacion.autorizada_en if liberacion else None,
        },
        "pallets": pallets,
        "cadena_procesos": cadena,
    }
