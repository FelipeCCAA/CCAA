from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, F, Prefetch, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response

from usuarios.permisos import ConfiguraProcesos
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, filtrar_por_scope, scope_de,
    sucursal_para_escritura,
)
from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla, CorridaSecado,
    EjecucionProceso, EntradaProceso,
    EtapaProceso, Proceso, RutaProducto,
    SalidaProceso,
)
from .serializers import (
    CierreCondensacionSerializer, CierreDescremacionSerializer,
    CierreSecadoSerializer,
    CierreMantequillaSerializer, CrearCondensacionGuiadaSerializer,
    CrearDescremacionGuiadaSerializer, CrearMantequillaGuiadaSerializer,
    CorridaCondensacionSerializer,
    CorridaDescremacionSerializer, CorridaMantequillaSerializer,
    CorridaSecadoSerializer,
    EjecucionProcesoSerializer, EntradaProcesoSerializer, EtapaProcesoSerializer,
    IncorporarReworkSerializer, ProcesoSerializer, SalidaProcesoSerializer,
    RutaProductoSerializer, SugerirDescremacionSerializer,
)
from .permisos import OperaProcesoPorEtapa
from .servicios import (
    ESTADOS_QUE_OCUPAN_EQUIPO,
    ConflictoVersionEjecucion,
    cerrar_condensacion, cerrar_descremacion, cerrar_mantequilla, cerrar_secado,
    genealogia_lote,
    crear_condensacion_guiada, crear_descremacion_guiada,
    crear_entrada_proceso, crear_mantequilla_guiada,
    diagnosticar_integridad_produccion,
    iniciar_condensacion, iniciar_descremacion, iniciar_mantequilla,
    preparar_continuacion, siguiente_etapa_para_salida,
    sugerir_plan_descremacion,
    tipos_equipo_para_etapa, transicionar_ejecucion,
)


class ProcesoViewSet(viewsets.ModelViewSet):
    queryset = Proceso.objects.prefetch_related("etapas")
    serializer_class = ProcesoSerializer
    permission_classes = [ConfiguraProcesos]
    http_method_names = ["get", "post", "patch", "head", "options"]


class EtapaProcesoViewSet(viewsets.ModelViewSet):
    queryset = EtapaProceso.objects.select_related("proceso")
    serializer_class = EtapaProcesoSerializer
    permission_classes = [ConfiguraProcesos]
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
    permission_classes = [ConfiguraProcesos]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def perform_create(self, serializer):
        serializer.save(sucursal=sucursal_para_escritura(
            self.request.user, serializer.validated_data
        ))

    @action(detail=False, methods=["get"], url_path="diagnostico")
    def diagnostico(self, request):
        """Expone faltantes de configuración sin confundir insumos con productos."""
        from maestros.models import Producto
        from usuarios.models import Sucursal

        categorias_productivas = {
            Producto.Categoria.LECHE_POLVO,
            Producto.Categoria.LP_INSTANTANEA,
            Producto.Categoria.LP_CON_LECITINA,
            Producto.Categoria.PRECONDENSADO,
            Producto.Categoria.MANTEQUILLA,
        }
        productos = Producto.objects.filter(activo=True).filter(
            Q(familia=Producto.Familia.POLVO)
            | Q(categoria__in=categorias_productivas)
        ).select_related("mandante__empresa")
        sucursales = Sucursal.objects.filter(activa=True).select_related("empresa")
        scope = scope_de(request.user, requerido=True)
        if not scope.es_global:
            productos = productos.filter(mandante__empresa_id=scope.empresa_id)
            sucursales = sucursales.filter(empresa_id=scope.empresa_id)
        if scope.es_sucursal:
            sucursales = sucursales.filter(pk=scope.sucursal_id)

        rutas = self.get_queryset().filter(activa=True, proceso__activo=True)
        rutas_por_par = {}
        for ruta in rutas:
            rutas_por_par.setdefault((ruta.producto_id, ruta.sucursal_id), []).append(ruta)

        resultado = []
        for producto in productos:
            plantas_producto = [
                planta for planta in sucursales
                if planta.empresa_id == producto.mandante.empresa_id
            ]
            for planta in plantas_producto:
                configuradas = rutas_por_par.get((producto.pk, planta.pk), [])
                resultado.append({
                    "producto": producto.pk,
                    "producto_nombre": producto.nombre,
                    "sucursal": planta.pk,
                    "sucursal_nombre": planta.nombre,
                    "configurada": bool(configuradas),
                    "rutas": [
                        {
                            "id": ruta.pk,
                            "proceso": ruta.proceso_id,
                            "proceso_nombre": ruta.proceso.nombre,
                            "prioridad": ruta.prioridad,
                        }
                        for ruta in configuradas
                    ],
                })

        faltantes = sum(not item["configurada"] for item in resultado)
        return Response({
            "completo": faltantes == 0,
            "faltantes": faltantes,
            "productos": resultado,
            "integridad": diagnosticar_integridad_produccion(usuario=request.user),
        })


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
    permission_classes = [OperaProcesoPorEtapa]
    tipo_etapa_operacional = EtapaProceso.Tipo.CONDENSACION
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "POST", detail="Usa crear-guiada para registrar una condensacion."
        )

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
        "producto_descremada": (None, "mandante__empresa_id"),
        "producto_crema": (None, "mandante__empresa_id"),
        "silo_entera": ("sucursal_id", "sucursal__empresa_id"),
        "analisis_entrada": ("silo__sucursal_id", "silo__sucursal__empresa_id"),
        "silo_descremada": ("sucursal_id", "sucursal__empresa_id"),
        "estanque_crema": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema",
        "iniciada_por", "finalizada_por",
    )
    serializer_class = CorridaDescremacionSerializer
    permission_classes = [OperaProcesoPorEtapa]
    tipo_etapa_operacional = EtapaProceso.Tipo.DESCREMACION
    http_method_names = ["get", "post", "head", "options"]

    @staticmethod
    def _error(error, codigo=status.HTTP_400_BAD_REQUEST):
        detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
        return Response(detalle, status=codigo)

    @action(detail=False, methods=["get"], url_path="opciones-alta")
    def opciones_alta(self, request):
        """Catálogos operacionales mínimos y faltantes para iniciar descremación."""
        from maestros.models import Equipo, Especificacion, Producto, Silo

        etapas = EtapaProceso.objects.filter(
            tipo=EtapaProceso.Tipo.DESCREMACION,
            activa=True,
            proceso__activo=True,
        ).select_related("proceso")
        equipos = filtrar_por_scope(
            Equipo.objects.filter(
                activo=True,
                tipo__in=tipos_equipo_para_etapa(EtapaProceso.Tipo.DESCREMACION),
            ),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        silos = filtrar_por_scope(
            Silo.objects.filter(activo=True),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        productos = filtrar_por_scope(
            Producto.objects.filter(activo=True).select_related("mandante"),
            request.user,
            campo_sucursal=None,
            campo_empresa="mandante__empresa_id",
        )
        productos_descremada = productos.filter(
            tipo=Producto.TipoProducto.DESCREMADA,
            familia=Producto.Familia.LIQUIDO,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
            unidad_base=Producto.Unidad.L,
        )
        productos_crema = productos.filter(
            familia=Producto.Familia.CREMA,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
        )
        ids_productos = [
            *productos_descremada.values_list("pk", flat=True),
            *productos_crema.values_list("pk", flat=True),
        ]
        hoy = timezone.localdate()
        productos_con_especificacion_silo = set(
            Especificacion.objects.filter(
                producto_id__in=ids_productos,
                tipo_analisis=Especificacion.TipoAnalisis.SILO,
                vigente_desde__lte=hoy,
            ).filter(
                Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=hoy),
            ).values_list("producto_id", flat=True)
        )
        rutas = filtrar_por_scope(
            RutaProducto.objects.filter(
                activa=True,
                proceso__activo=True,
                producto_id__in=ids_productos,
            ).select_related("producto", "proceso").prefetch_related("proceso__etapas"),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        ocupaciones = {
            ejecucion.equipo_id: ejecucion.codigo
            for ejecucion in EjecucionProceso.objects.filter(
                sucursal_id__in={equipo.sucursal_id for equipo in equipos},
                estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
                equipo_id__isnull=False,
            ).only("equipo_id", "codigo")
        }
        silos_descremada = silos.filter(tipo=Silo.Tipo.TK_LD)
        estanques_crema = silos.filter(tipo=Silo.Tipo.TK_CREMA)

        bloqueos = []
        condiciones = (
            ("etapa", etapas.exists(), "Falta una etapa activa de Descremación."),
            ("equipo", equipos.exists(), "Falta configurar una descremadora activa para la planta."),
            (
                "producto_descremada",
                productos_descremada.exists(),
                "Falta leche descremada líquida como producto intermedio medido en litros.",
            ),
            ("producto_crema", productos_crema.exists(), "Falta configurar una crema intermedia."),
            ("silo_descremada", silos_descremada.exists(), "Falta un TK de leche descremada activo."),
            ("estanque_crema", estanques_crema.exists(), "Falta un TK de crema activo."),
        )
        bloqueos.extend(
            {"codigo": codigo, "mensaje": mensaje}
            for codigo, disponible, mensaje in condiciones
            if not disponible
        )

        return Response({
            "etapas": [
                {"id": item.pk, "nombre": item.nombre, "tipo": item.tipo, "activa": item.activa}
                for item in etapas
            ],
            "equipos": [
                {
                    "id": item.pk,
                    "nombre": item.nombre,
                    "tipo": item.tipo,
                    "ocupado_por": ocupaciones.get(item.pk),
                }
                for item in equipos
            ],
            "silos_descremada": [
                {"id": item.pk, "codigo": item.codigo, "tipo": item.tipo, "activo": item.activo}
                for item in silos_descremada
            ],
            "estanques_crema": [
                {"id": item.pk, "codigo": item.codigo, "tipo": item.tipo, "activo": item.activo}
                for item in estanques_crema
            ],
            "productos_descremada": [
                {
                    "id": item.pk,
                    "nombre": item.nombre,
                    "tiene_especificacion_silo_vigente": (
                        item.pk in productos_con_especificacion_silo
                    ),
                }
                for item in productos_descremada
            ],
            "productos_crema": [
                {
                    "id": item.pk,
                    "nombre": item.nombre,
                    "tiene_especificacion_silo_vigente": (
                        item.pk in productos_con_especificacion_silo
                    ),
                }
                for item in productos_crema
            ],
            "rutas": [RutaProductoSerializer(item).data for item in rutas],
            "bloqueos": bloqueos,
        })

    @action(detail=False, methods=["post"], url_path="sugerir-balance")
    def sugerir_balance(self, request):
        from maestros.models import Producto
        from recepcion.models import AnalisisSilo

        entrada = SugerirDescremacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        analisis_qs = filtrar_por_scope(
            AnalisisSilo.objects.select_related("silo"), request.user,
            campo_sucursal="silo__sucursal_id",
            campo_empresa="silo__sucursal__empresa_id",
        )
        productos_qs = filtrar_por_scope(
            Producto.objects.select_related("mandante"), request.user,
            campo_sucursal=None, campo_empresa="mandante__empresa_id",
        )
        try:
            analisis = analisis_qs.get(pk=datos["analisis_entrada"])
            producto_descremada = productos_qs.get(pk=datos["producto_descremada"])
            producto_crema = productos_qs.get(pk=datos["producto_crema"])
        except (AnalisisSilo.DoesNotExist, Producto.DoesNotExist):
            return Response(
                {"error": "El análisis o producto no pertenece a tu alcance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if (
            analisis.estado != AnalisisSilo.Estado.CONFIRMADO
            or not analisis.vigente
            or analisis.grasa is None
            or analisis.sng is None
        ):
            return Response(
                {"analisis_entrada": "Selecciona un análisis confirmado y vigente con MG y SNG."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            sugerencia = sugerir_plan_descremacion(
                analisis=analisis, litros_entrada=datos["litros_entrada"],
                producto_descremada=producto_descremada,
                producto_crema=producto_crema,
            )
        except DjangoValidationError as error:
            return self._error(error, status.HTTP_409_CONFLICT)
        return Response(sugerencia)

    @action(detail=False, methods=["post"], url_path="crear-guiada")
    def crear_guiada(self, request):
        from maestros.models import Equipo, Producto, Silo
        from recepcion.models import AnalisisSilo

        entrada = CrearDescremacionGuiadaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        silos = filtrar_por_scope(
            Silo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        equipos = filtrar_por_scope(
            Equipo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        productos = filtrar_por_scope(
            Producto.objects.all(), request.user,
            campo_sucursal=None, campo_empresa="mandante__empresa_id",
        )
        rutas = filtrar_por_scope(
            RutaProducto.objects.filter(activa=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        analisis = filtrar_por_scope(
            AnalisisSilo.objects.all(), request.user,
            campo_sucursal="silo__sucursal_id",
            campo_empresa="silo__sucursal__empresa_id",
        )
        ids_validos = (
            silos.filter(pk=datos["silo_entera"]).exists()
            and silos.filter(pk=datos["silo_descremada"]).exists()
            and silos.filter(pk=datos["estanque_crema"]).exists()
            and equipos.filter(pk=datos["equipo"]).exists()
            and productos.filter(pk=datos["producto_descremada"]).exists()
            and productos.filter(pk=datos["producto_crema"]).exists()
            and analisis.filter(pk=datos["analisis_entrada"]).exists()
            and (
                not datos.get("ruta_descremada")
                or rutas.filter(pk=datos["ruta_descremada"]).exists()
            )
            and (
                not datos.get("ruta_crema")
                or rutas.filter(pk=datos["ruta_crema"]).exists()
            )
        )
        if not ids_validos:
            return Response(
                {"error": "Alguna seleccion no pertenece a tu alcance."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            corrida = crear_descremacion_guiada(
                codigo=datos["codigo"], etapa_id=datos["etapa"],
                equipo_id=datos["equipo"], silo_entera_id=datos["silo_entera"],
                analisis_entrada_id=datos["analisis_entrada"],
                litros_entrada=datos["litros_entrada"],
                silo_descremada_id=datos["silo_descremada"],
                estanque_crema_id=datos["estanque_crema"],
                producto_descremada_id=datos["producto_descremada"],
                producto_crema_id=datos["producto_crema"],
                ruta_descremada_id=datos.get("ruta_descremada"),
                ruta_crema_id=datos.get("ruta_crema"),
                destino_descremada=datos["destino_descremada"],
                destino_crema=datos["destino_crema"],
                litros_descremada_plan=datos["litros_descremada_plan"],
                litros_crema_plan=datos["litros_crema_plan"],
                usuario=request.user,
            )
        except DjangoValidationError as error:
            return self._error(error)
        return Response(self.get_serializer(corrida).data, status=status.HTTP_201_CREATED)

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
        "iniciada_por", "finalizada_por",
    )
    serializer_class = CorridaMantequillaSerializer
    permission_classes = [OperaProcesoPorEtapa]
    tipo_etapa_operacional = EtapaProceso.Tipo.MANTEQUILLA
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "POST", detail="Usa crear-guiada para registrar una corrida de mantequilla."
        )

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
        lotes_crema = filtrar_por_scope(
            Lote.objects.filter(
                estado__in=[Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
                kg_producidos__isnull=False,
                producto__familia="crema",
            ).select_related("producto"), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        lotes = lotes_crema.filter(
            salidas_proceso__liberacion_calidad__estado="liberado",
        ).annotate(
                kg_usados=Coalesce(
                    Sum("entradas_proceso__cantidad", filter=Q(entradas_proceso__unidad__iexact="kg")),
                    Value(0), output_field=DecimalField(),
                )
            ).distinct()
        pendientes_calidad = lotes_crema.filter(
            salidas_proceso__isnull=False,
        ).exclude(
            pk__in=lotes.values("pk"),
        ).prefetch_related(
            "salidas_proceso__liberacion_calidad",
            "salidas_proceso__ejecucion__etapa",
        ).distinct()
        lotes_suero = filtrar_por_scope(
            Lote.objects.filter(
                producto__categoria="suero",
                estado__in=[Lote.Estado.BORRADOR, Lote.Estado.EN_PROCESO],
                kg_producidos__isnull=True,
                corridas_como_suero_mantequilla__isnull=True,
            ).select_related("producto"), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        equipos = filtrar_por_scope(
            Equipo.objects.filter(activo=True, tipo__in=[Equipo.Tipo.LINEA, Equipo.Tipo.OTRO]),
            request.user, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        ocupaciones = {
            ejecucion.equipo_id: ejecucion.codigo
            for ejecucion in EjecucionProceso.objects.filter(
                sucursal_id__in={equipo.sucursal_id for equipo in equipos},
                estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
                equipo_id__isnull=False,
            ).only("equipo_id", "codigo")
        }

        def estado_calidad_crema(lote):
            decisiones = [
                getattr(salida, "liberacion_calidad", None)
                for salida in lote.salidas_proceso.all()
            ]
            estados = {decision.estado for decision in decisiones if decision}
            if "rechazado" in estados:
                return "rechazado"
            if "pendiente" in estados:
                return "pendiente"
            return "trazabilidad_incompleta"

        return Response({
            "ordenes": [{"id": item.pk, "codigo": item.codigo, "producto": item.producto.nombre} for item in ordenes],
            "cremas": [
                {"id": item.pk, "codigo": item.codigo_lote, "producto": item.producto.nombre,
                 "disponible_kg": item.kg_producidos - item.kg_usados}
                for item in lotes if item.kg_producidos > item.kg_usados
            ],
            "cremas_pendientes_calidad": [
                {
                    "id": item.pk,
                    "codigo": item.codigo_lote,
                    "producto": item.producto.nombre,
                    "estado_calidad": estado_calidad_crema(item),
                    "etapa_origen": next(
                        (
                            salida.ejecucion.etapa.get_tipo_display()
                            for salida in item.salidas_proceso.all()
                        ),
                        "Sin proceso de origen",
                    ),
                }
                for item in pendientes_calidad
            ],
            "sueros": [
                {"id": item.pk, "codigo": item.codigo_lote, "producto": item.producto.nombre}
                for item in lotes_suero
            ],
            "equipos": [
                {
                    "id": item.pk,
                    "nombre": item.nombre,
                    "tipo": item.tipo,
                    "ocupado_por": ocupaciones.get(item.pk),
                }
                for item in equipos
            ],
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


class CorridaSecadoViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    queryset = CorridaSecado.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
        "finalizada_por",
    ).prefetch_related("ejecucion__salidas__liberacion_calidad")
    serializer_class = CorridaSecadoSerializer
    permission_classes = [OperaProcesoPorEtapa]
    tipo_etapa_operacional = EtapaProceso.Tipo.SECADO
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "POST",
            detail="La corrida de Secado nace al abrir el lote desde su vale.",
        )

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        entrada = CierreSecadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            corrida = cerrar_secado(
                corrida_id=self.get_object().pk,
                usuario=request.user,
                **entrada.validated_data,
            )
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else error.messages
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(corrida).data)


class EjecucionProcesoViewSet(RelacionesTenantMixin, viewsets.ModelViewSet):
    modelo_operacional = EjecucionProceso
    tenant_relation_fields = {
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
    }
    serializer_class = EjecucionProcesoSerializer
    permission_classes = [OperaProcesoPorEtapa]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def create(self, request, *args, **kwargs):
        tipo = EtapaProceso.objects.filter(
            pk=request.data.get("etapa")
        ).values_list("tipo", flat=True).first()
        if tipo != EtapaProceso.Tipo.DESCREMACION:
            raise MethodNotAllowed(
                "POST",
                detail=(
                    "La ejecucion debe crearse desde la accion especializada "
                    "del proceso. El alta generica solo conserva compatibilidad "
                    "temporal con Descremacion."
                ),
            )
        return super().create(request, *args, **kwargs)

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

    def partial_update(self, request, *args, **kwargs):
        """PATCH protegido contra la pérdida silenciosa de cambios de otro turno."""
        actual = self.get_object()
        version = request.data.get("version")
        if isinstance(version, bool):
            version = None
        try:
            version = int(version)
        except (TypeError, ValueError):
            return Response(
                {"version": ["Envía la versión visible de la ejecución."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            bloqueada = filtrar_por_scope(
                EjecucionProceso.objects.select_for_update().select_related("etapa"),
                request.user,
                campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            ).get(pk=actual.pk)
            self.check_object_permissions(request, bloqueada)
            if bloqueada.version != version:
                return Response(
                    {
                        "code": "version_conflict",
                        "detail": (
                            "La ejecución cambió desde que abriste la pantalla. "
                            "Actualiza antes de guardar nuevamente."
                        ),
                        "version_actual": bloqueada.version,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            if not bloqueada.editable:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("Una ejecución cerrada o cancelada es inmutable.")
            serializer = self.get_serializer(
                bloqueada, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(version=bloqueada.version + 1)
        return Response(serializer.data)

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
                "version": ejecucion.version,
                "estado": ejecucion.estado,
                "estado_etiqueta": ejecucion.get_estado_display(),
                "etapa_nombre": ejecucion.etapa.nombre,
                "etapa_tipo": ejecucion.etapa.tipo,
                "equipo_id": ejecucion.equipo_id,
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

    @action(detail=False, methods=["get"], url_path="resumen-operacional")
    def resumen_operacional(self, request):
        """Cinco indicadores de puesto sin serializar las bandejas completas."""
        from calidad.models import LiberacionProceso
        from inventario.models import Despacho

        ejecuciones = filtrar_por_scope(
            EjecucionProceso.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        indicadores = ejecuciones.aggregate(
            procesos_activos=Count(
                "id", filter=Q(estado__in=[
                    EjecucionProceso.Estado.PREPARACION,
                    EjecucionProceso.Estado.EJECUCION,
                    EjecucionProceso.Estado.PAUSADA,
                ])
            ),
            esperando_calidad=Count(
                "id", filter=Q(estado=EjecucionProceso.Estado.PENDIENTE_CONTROL)
            ),
            equipos_ocupados=Count(
                "equipo_id", distinct=True,
                filter=Q(
                    equipo_id__isnull=False,
                    estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
                ),
            ),
            bloqueos=Count(
                "id", filter=Q(estado=EjecucionProceso.Estado.BLOQUEADA)
            ),
        )
        salidas = filtrar_por_scope(
            SalidaProceso.objects.filter(
                liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
            ).exclude(naturaleza=SalidaProceso.Naturaleza.MERMA),
            request.user,
            campo_sucursal="ejecucion__sucursal_id",
            campo_empresa="ejecucion__sucursal__empresa_id",
        )
        cero = Value(Decimal("0"))
        decimal = DecimalField(max_digits=14, decimal_places=3)
        continuables = salidas.filter(destino__in=[
            SalidaProceso.Destino.PENDIENTE,
            SalidaProceso.Destino.SIGUIENTE_PROCESO,
            SalidaProceso.Destino.ESTANDARIZACION,
        ]).annotate(
            comprometido=Coalesce(Sum("usos_como_origen__cantidad"), cero, output_field=decimal)
        ).filter(cantidad__gt=F("comprometido")).count()
        despachables = salidas.filter(
            destino=SalidaProceso.Destino.DESPACHO_DIRECTO,
        ).annotate(
            comprometido=Coalesce(
                Sum(
                    "detalles_despacho_granel__cantidad",
                    filter=Q(detalles_despacho_granel__despacho__estado__in=[
                        Despacho.Estado.AUTORIZADO, Despacho.Estado.DESPACHADO,
                    ]),
                ),
                cero,
                output_field=decimal,
            )
        ).filter(cantidad__gt=F("comprometido")).count()
        envasables = salidas.filter(
            destino=SalidaProceso.Destino.ENVASADO,
            lote__isnull=False,
        ).annotate(
            comprometido=Coalesce(
                Sum("lote__registros_envase__kg_envasados"), cero,
                output_field=decimal,
            )
        ).filter(cantidad__gt=F("comprometido")).count()
        indicadores["materiales_listos"] = continuables + despachables + envasables
        return Response(indicadores)

    @action(detail=True, methods=["post"])
    def transicionar(self, request, pk=None):
        version = request.data.get("version")
        if isinstance(version, bool):
            version = None
        try:
            version = int(version)
        except (TypeError, ValueError):
            return Response(
                {"version": ["Envía la versión visible de la ejecución."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ejecucion = transicionar_ejecucion(
                ejecucion_id=self.get_object().pk,
                estado_nuevo=request.data.get("estado", ""),
                motivo=request.data.get("motivo", ""),
                usuario=request.user,
                version_esperada=version,
            )
        except ConflictoVersionEjecucion as error:
            return Response(
                {
                    "code": "version_conflict",
                    "detail": str(error),
                    "version_actual": error.version_actual,
                },
                status=status.HTTP_409_CONFLICT,
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

    @action(detail=True, methods=["post"], url_path="incorporar-rework")
    def incorporar_rework(self, request, pk=None):
        ejecucion = self.get_object()
        entrada = IncorporarReworkSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        from produccion.models import Lote
        from inventario.models import UnidadRework
        from inventario.servicios import consumir_unidad_rework

        lotes = filtrar_por_scope(
            Lote.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        try:
            lote = lotes.get(pk=datos["lote"])
            if datos.get("unidad_rework"):
                unidades = filtrar_por_scope(
                    UnidadRework.objects.all(), request.user,
                    campo_sucursal="autorizacion__lote__sucursal_id",
                    campo_empresa="autorizacion__lote__sucursal__empresa_id",
                )
                unidad = unidades.get(pk=datos["unidad_rework"])
                if unidad.autorizacion.lote_id != lote.pk:
                    return Response(
                        {"unidad_rework": "La unidad no corresponde al lote indicado."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                creada = consumir_unidad_rework(
                    unidad=unidad, ejecucion=ejecucion,
                    cantidad=datos["cantidad"], motivo=datos["motivo"],
                    usuario=request.user,
                    operacion=datos.get("operacion_id") or uuid4(),
                )
            else:
                creada = crear_entrada_proceso(datos={
                    "ejecucion": ejecucion,
                    "lote": lote,
                    "tipo": EntradaProceso.Tipo.REPROCESO,
                    "cantidad": datos["cantidad"],
                    "unidad": "kg",
                    "motivo": datos["motivo"],
                })
        except Lote.DoesNotExist:
            return Response(
                {"lote": "El lote indicado no existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except UnidadRework.DoesNotExist:
            return Response(
                {"unidad_rework": "La unidad física indicada no existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as error:
            detalle = (
                error.message_dict
                if hasattr(error, "message_dict")
                else {"error": error.messages[0]}
            )
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EntradaProcesoSerializer(creada).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="registrar-salida")
    def registrar_salida(self, request, pk=None):
        ejecucion = self.get_object()
        entrada = SalidaProcesoSerializer(data={
            **request.data, "ejecucion": ejecucion.pk,
        })
        for nombre, campo_sucursal, campo_empresa in (
            ("ejecucion", "sucursal_id", "sucursal__empresa_id"),
            ("lote", "sucursal_id", "sucursal__empresa_id"),
            ("silo", "sucursal_id", "sucursal__empresa_id"),
        ):
            campo = entrada.fields.get(nombre)
            if campo is not None and getattr(campo, "queryset", None) is not None:
                campo.queryset = filtrar_por_scope(
                    campo.queryset, request.user,
                    campo_sucursal=campo_sucursal, campo_empresa=campo_empresa,
                )
        entrada.is_valid(raise_exception=True)
        entrada.save()
        return Response(entrada.data, status=status.HTTP_201_CREATED)


class EntradaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
        "silo": ("sucursal_id", "sucursal__empresa_id"),
        "salida_origen": (
            "ejecucion__sucursal_id", "ejecucion__sucursal__empresa_id"
        ),
    }
    queryset = EntradaProceso.objects.select_related(
        "ejecucion", "lote__producto", "silo", "salida_origen__ejecucion"
    )
    serializer_class = EntradaProcesoSerializer
    permission_classes = [OperaProcesoPorEtapa]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"], url_path="opciones-rework")
    def opciones_rework(self, request):
        """Rework aprobado con saldo; consulta acotada para el formulario operativo."""
        from .models import AutorizacionReproceso
        from inventario.models import UnidadRework

        decimal = DecimalField(max_digits=14, decimal_places=3)
        autorizaciones = filtrar_por_scope(
            AutorizacionReproceso.objects.filter(
                estado=AutorizacionReproceso.Estado.APROBADO,
                unidades_fisicas__isnull=True,
            ).select_related("lote__producto").annotate(
                consumido=Coalesce(
                    Sum(
                        "lote__entradas_proceso__cantidad",
                        filter=Q(lote__entradas_proceso__tipo=EntradaProceso.Tipo.REPROCESO),
                    ),
                    Value(0), output_field=decimal,
                )
            ),
            request.user,
            campo_sucursal="lote__sucursal_id",
            campo_empresa="lote__sucursal__empresa_id",
        )
        resultado = []
        unidades = filtrar_por_scope(
            UnidadRework.objects.filter(
                estado=UnidadRework.Estado.DISPONIBLE,
                cantidad_disponible_kg__gt=0,
                ubicacion__tipo="disponible",
                autorizacion__estado=AutorizacionReproceso.Estado.APROBADO,
            ).select_related("autorizacion__lote__producto", "ubicacion"),
            request.user,
            campo_sucursal="autorizacion__lote__sucursal_id",
            campo_empresa="autorizacion__lote__sucursal__empresa_id",
        )
        for unidad in unidades:
            autorizacion = unidad.autorizacion
            resultado.append({
                "id": autorizacion.id,
                "unidad_rework_id": unidad.id,
                "codigo_unidad": unidad.codigo,
                "ubicacion_codigo": unidad.ubicacion.codigo,
                "lote_id": autorizacion.lote_id,
                "lote_codigo": autorizacion.lote.codigo_lote,
                "producto_nombre": autorizacion.lote.producto.nombre,
                "origen": autorizacion.origen,
                "motivo": autorizacion.motivo,
                "cantidad_autorizada_kg": unidad.cantidad_inicial_kg,
                "cantidad_consumida_kg": (
                    unidad.cantidad_inicial_kg - unidad.cantidad_disponible_kg
                ),
                "cantidad_disponible_kg": unidad.cantidad_disponible_kg,
                "trazabilidad_fisica": True,
            })
        for autorizacion in autorizaciones:
            disponible = autorizacion.cantidad_kg - autorizacion.consumido
            if disponible <= 0:
                continue
            resultado.append({
                "id": autorizacion.id,
                "lote_id": autorizacion.lote_id,
                "lote_codigo": autorizacion.lote.codigo_lote,
                "producto_nombre": autorizacion.lote.producto.nombre,
                "origen": autorizacion.origen,
                "motivo": autorizacion.motivo,
                "cantidad_autorizada_kg": autorizacion.cantidad_kg,
                "cantidad_consumida_kg": autorizacion.consumido,
                "cantidad_disponible_kg": disponible,
                "unidad_rework_id": None,
                "codigo_unidad": None,
                "ubicacion_codigo": None,
                "trazabilidad_fisica": False,
            })
        return Response(resultado)


class SalidaProcesoViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "ejecucion__sucursal_id"
    tenant_lookup_empresa = "ejecucion__sucursal__empresa_id"
    tenant_relation_fields = {
        "ejecucion": ("sucursal_id", "sucursal__empresa_id"),
        "lote": ("sucursal_id", "sucursal__empresa_id"),
        "silo": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = SalidaProceso.objects.select_related("ejecucion", "lote__producto")
    serializer_class = SalidaProcesoSerializer
    permission_classes = [OperaProcesoPorEtapa]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"], url_path="disponibles")
    def disponibles(self, request):
        """Resultados liberados, con saldo y próximas etapas configuradas."""
        from calidad.models import LiberacionProceso
        from recepcion.models import MovimientoSilo

        salidas = filtrar_por_scope(
            SalidaProceso.objects.filter(
                liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
                silo__isnull=False,
                destino__in=[
                    SalidaProceso.Destino.PENDIENTE,
                    SalidaProceso.Destino.SIGUIENTE_PROCESO,
                    SalidaProceso.Destino.ESTANDARIZACION,
                    SalidaProceso.Destino.DESPACHO_DIRECTO,
                ],
            ).exclude(
                naturaleza=SalidaProceso.Naturaleza.MERMA
            ).select_related(
                "ejecucion__etapa__proceso", "ejecucion__equipo", "silo",
                "lote__producto", "liberacion_calidad__analisis_silo",
                "ruta_producto__proceso",
            ).annotate(consumido=Sum("usos_como_origen__cantidad")),
            request.user,
            campo_sucursal="ejecucion__sucursal_id",
            campo_empresa="ejecucion__sucursal__empresa_id",
        )
        silo_id = request.query_params.get("silo")
        if silo_id:
            try:
                silo_id = int(silo_id)
            except (TypeError, ValueError):
                return Response(
                    {"silo": "El identificador del silo no es valido."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            salidas = salidas.filter(silo_id=silo_id)
        salidas = list(salidas)
        claves_material = {
            (salida.lote_id, salida.silo_id)
            for salida in salidas if salida.lote_id
        }
        consumos_fisicos = {
            (fila["lote_id"], fila["silo_id"]): fila["total"]
            for fila in MovimientoSilo.objects.filter(
                lote_id__in={clave[0] for clave in claves_material},
                silo_id__in={clave[1] for clave in claves_material},
                tipo=MovimientoSilo.Tipo.SALIDA,
            ).values("lote_id", "silo_id").annotate(total=Sum("litros"))
        }
        consumos_kg = {
            fila["lote_id"]: fila["total"]
            for fila in EntradaProceso.objects.filter(
                lote_id__in={clave[0] for clave in claves_material},
                unidad__iexact="kg",
            ).values("lote_id").annotate(total=Sum("cantidad"))
        }
        for salida in salidas:
            salida.consumido_trazable = (
                (salida.consumido or 0)
                + consumos_fisicos.get((salida.lote_id, salida.silo_id), 0)
            )
            salida.consumido_kg_trazable = consumos_kg.get(salida.lote_id, 0)
            analisis = getattr(salida.liberacion_calidad, "analisis_silo", None)
            if (
                salida.lote_id and salida.unidad.lower() == "l"
                and salida.consumido and analisis and analisis.densidad
            ):
                salida.consumido_kg_trazable += (
                    Decimal(str(salida.consumido))
                    * Decimal(str(analisis.densidad)) / Decimal("1000")
                )
        salidas = [
            salida for salida in salidas
            if salida.cantidad - salida.consumido_trazable > 0
        ]
        procesos_ids = {
            salida.ruta_producto.proceso_id
            if salida.ruta_producto_id else salida.ejecucion.etapa.proceso_id
            for salida in salidas
        }
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
                estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
                equipo_id__isnull=False,
            ).only("equipo_id", "codigo")
        }

        def etapas_siguientes(salida):
            siguiente = siguiente_etapa_para_salida(
                salida=salida, etapas_por_proceso=etapas_por_proceso
            )
            return [siguiente] if siguiente is not None else []

        def acciones_permitidas(salida):
            if salida.destino == SalidaProceso.Destino.DESPACHO_DIRECTO:
                return [{"codigo": "preparar_despacho", "etiqueta": "Preparar despacho"}]
            siguiente = siguiente_etapa_para_salida(
                salida=salida, etapas_por_proceso=etapas_por_proceso
            )
            if siguiente is None:
                return []
            codigos = {
                EtapaProceso.Tipo.ESTANDARIZACION: "enviar_estandarizacion",
                EtapaProceso.Tipo.MANTEQUILLA: "iniciar_mantequilla",
                EtapaProceso.Tipo.SECADO: "continuar_secado",
            }
            etiquetas = {
                EtapaProceso.Tipo.ESTANDARIZACION: "Enviar a Estandarizacion",
                EtapaProceso.Tipo.MANTEQUILLA: "Iniciar Mantequilla",
                EtapaProceso.Tipo.SECADO: "Continuar a Secado",
            }
            return [{
                "codigo": codigos.get(siguiente.tipo, "continuar_proceso"),
                "etiqueta": etiquetas.get(
                    siguiente.tipo, f"Continuar a {siguiente.nombre}"
                ),
            }]

        return Response([
            {
                "id": salida.id,
                "corrida_codigo": salida.ejecucion.codigo,
                "resultado": (
                    salida.lote.producto.nombre
                    if salida.lote_id and salida.lote.producto_id
                    else salida.ejecucion.etapa.nombre
                ),
                "lote_id": salida.lote_id,
                "lote_codigo": salida.lote.codigo_lote if salida.lote_id else None,
                "producto_id": salida.lote.producto_id if salida.lote_id else None,
                "producto_nombre": (
                    salida.lote.producto.nombre if salida.lote_id else None
                ),
                "estado_material": "liberado",
                "estado_material_etiqueta": "Liberado por Calidad",
                "densidad_kg_m3": (
                    salida.liberacion_calidad.analisis_silo.densidad
                    if salida.liberacion_calidad.analisis_silo_id else None
                ),
                "cantidad_trazable_kg": (
                    salida.lote.kg_producidos if salida.lote_id else None
                ),
                "cantidad_consumida_kg": (
                    salida.consumido_kg_trazable if salida.lote_id else None
                ),
                "cantidad_disponible_kg": (
                    max(
                        (salida.lote.kg_producidos or 0)
                        - salida.consumido_kg_trazable,
                        0,
                    )
                    if salida.lote_id and salida.lote.kg_producidos is not None
                    else None
                ),
                "silo_id": salida.silo_id,
                "silo_codigo": salida.silo.codigo,
                "cantidad_total": salida.cantidad,
                "cantidad_consumida": salida.consumido_trazable,
                "cantidad_disponible": salida.cantidad - salida.consumido_trazable,
                "unidad": salida.unidad,
                "clasificacion": salida.clasificacion,
                "clasificacion_etiqueta": salida.get_clasificacion_display(),
                "destino": salida.destino,
                "destino_etiqueta": salida.get_destino_display(),
                "destinos_permitidos": [
                    {"valor": valor, "etiqueta": dict(SalidaProceso.Destino.choices)[valor]}
                    for valor in sorted(salida.destinos_permitidos())
                ],
                "acciones_permitidas": acciones_permitidas(salida),
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
                    for etapa in etapas_siguientes(salida)
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
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import trazabilidad_fifo_movimientos

    vale = lote.vale
    if vale is None:
        return None

    consumos_estandarizacion = list(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.pk,
        ).select_related("silo").order_by("fecha_hora", "pk"))
    trazabilidad_recepciones = trazabilidad_fifo_movimientos(
        consumos_estandarizacion
    )
    recepciones_agrupadas = {}
    for tramo in trazabilidad_recepciones["tramos"]:
        for recepcion in tramo["recepciones"]:
            clave = (
                recepcion["id"], recepcion["silo_codigo"],
                recepcion["trazabilidad"],
            )
            if clave not in recepciones_agrupadas:
                recepciones_agrupadas[clave] = dict(recepcion)
            elif recepcion["litros_atribuidos"] is not None:
                recepciones_agrupadas[clave]["litros_atribuidos"] += (
                    recepcion["litros_atribuidos"]
                )
    recepciones = list(recepciones_agrupadas.values())

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
        "nota_recepciones": trazabilidad_recepciones["nota"],
        "litros_no_atribuibles": trazabilidad_recepciones[
            "litros_no_atribuibles"
        ],
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
