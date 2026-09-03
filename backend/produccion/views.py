import os
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, DecimalField, Exists, OuterRef, Subquery, Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from maestros import recetas
from maestros.models import Equipo, Especificacion, Producto, Receta, Silo
from recepcion.models import MovimientoSilo
from usuarios.permisos import EscribeAnalisisCalidad, EscribeEnvasado, EscribeInocuidad, EscribeProduccion
from usuarios.tenancy import (
    QuerysetTenantMixin,
    RelacionesTenantMixin,
    SucursalTenantViewSetMixin,
    filtrar_por_scope,
    scope_de,
    sucursal_para_escritura,
)

from . import dominio
from . import servicios as servicios_produccion
from .models import (
    Analisis,
    ControlProceso,
    ControlProcesoLectura,
    Lote,
    OrdenProduccion,
    PalletProducto,
    RegistroEnvase,
)
from .serializers import (
    AnalisisSerializer,
    ControlProcesoLecturaSerializer,
    ControlProcesoSerializer,
    LoteDetalleSerializer,
    LoteSerializer,
    OrdenProduccionSerializer,
    PalletProductoSerializer,
    RegistroEnvaseSerializer,
)


class RegistroEnvaseViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    queryset = RegistroEnvase.objects.select_related(
        "lote__producto", "equipo", "operador"
    ).prefetch_related("pallets")
    serializer_class = RegistroEnvaseSerializer
    permission_classes = [EscribeEnvasado]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["get"], url_path="materiales-habilitados")
    def materiales_habilitados(self, request):
        """Contrato acotado: solo material liberado y realmente envasable."""
        from procesos.models import SalidaProceso

        salidas = filtrar_por_scope(
            SalidaProceso.objects.filter(
                destino=SalidaProceso.Destino.ENVASADO,
                naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
                unidad__iexact="kg",
                liberacion_calidad__estado="liberado",
                lote__estado__in=[Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
                lote__producto__formato__in=[
                    Producto.Formato.SACO_25KG,
                    Producto.Formato.CAJA_20KG,
                ],
            ).select_related(
                "lote__producto", "ejecucion__etapa", "liberacion_calidad"
            ).order_by("registrada_en", "pk"),
            request.user,
            campo_sucursal="ejecucion__sucursal_id",
            campo_empresa="ejecucion__sucursal__empresa_id",
        )
        pesos = {
            Producto.Formato.SACO_25KG: Decimal("25"),
            Producto.Formato.CAJA_20KG: Decimal("20"),
        }
        respuesta = []
        for salida in salidas:
            envasado = salida.lote.registros_envase.aggregate(
                total=Sum("kg_envasados")
            )["total"] or Decimal("0")
            disponible = salida.cantidad - envasado
            if disponible <= 0:
                continue
            formato = salida.lote.producto.formato
            respuesta.append({
                "salida_id": salida.pk,
                "lote_id": salida.lote_id,
                "lote_codigo": salida.lote.codigo_lote,
                "producto_id": salida.lote.producto_id,
                "producto_nombre": salida.lote.producto.nombre,
                "cantidad_disponible": disponible,
                "unidad": salida.unidad,
                "formato": formato,
                "formato_nombre": salida.lote.producto.get_formato_display(),
                "formato_kg": pesos[formato],
                "maximo_pallet_kg": Decimal("500"),
                "origen": salida.ejecucion.codigo,
                "calidad": salida.liberacion_calidad.estado,
                "motivo_bloqueo": "",
            })
        return Response(respuesta)


class PalletProductoViewSet(QuerysetTenantMixin, viewsets.ReadOnlyModelViewSet):
    tenant_lookup_sucursal = "envase__lote__sucursal_id"
    tenant_lookup_empresa = "envase__lote__sucursal__empresa_id"
    queryset = PalletProducto.objects.select_related(
        "envase__lote__producto", "envase__equipo"
    )
    serializer_class = PalletProductoSerializer
    permission_classes = [EscribeEnvasado]


class OrdenProduccionViewSet(
    RelacionesTenantMixin, SucursalTenantViewSetMixin, viewsets.ModelViewSet
):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    queryset = OrdenProduccion.objects.select_related(
        "sucursal", "semana", "producto", "equipo", "responsable", "creada_por"
    )
    serializer_class = OrdenProduccionSerializer
    permission_classes = [EscribeProduccion]
    tenant_relation_fields = {
        "semana": ("sucursal_id", "sucursal__empresa_id"),
        "producto": (None, "mandante__empresa_id"),
        "equipo": ("sucursal_id", "sucursal__empresa_id"),
        "responsable": ("perfil__sucursal_id", "perfil__empresa_id"),
    }

    def perform_create(self, serializer):
        sucursal = sucursal_para_escritura(
            self.request.user, serializer.validated_data, "sucursal"
        )
        serializer.save(sucursal=sucursal, creada_por=self.request.user)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Una orden se cancela con motivo; no se elimina."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["post"])
    def partir(self, request, pk=None):
        lote = self.get_object()
        motivo = (request.data.get("motivo") or "").strip()
        if not motivo:
            return Response({"motivo": "Indica por qué se parte la corrida."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            correlativo = self.get_queryset().filter(equipo=lote.equipo, fecha=lote.fecha).count() + 1
            codigo = dominio.generar_codigo_lote(
                lote.fecha, lote.equipo.sigla if lote.equipo_id else "", correlativo
            )
            nuevo = Lote.objects.create(
                sucursal=lote.sucursal, codigo_lote=codigo or "", producto=lote.producto,
                equipo=lote.equipo, fecha=lote.fecha, turno=lote.turno,
                estado=Lote.Estado.EN_PROCESO, lote_anterior=lote, motivo_corte=motivo,
            )
        return Response(self.get_serializer(nuevo).data, status=status.HTTP_201_CREATED)


class LoteViewSet(SucursalTenantViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    # `prefetch_related` trae los análisis de todos los lotes en una sola
    # consulta. Sin esto, calcular la calidad de un listado dispararía una
    # consulta por lote.
    salida_del_lote = MovimientoSilo.objects.filter(
        tipo=MovimientoSilo.Tipo.SALIDA,
        origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        origen_id=OuterRef("pk"),
        silo_id=OuterRef("vale__silo_destino_id"),
    ).order_by("-fecha_hora")
    queryset = (
        Lote.objects.select_related(
            "sucursal", "producto", "producto__mandante", "vale",
            "vale__silo_destino", "equipo", "ejecucion", "orden",
        )
        .prefetch_related(
            "analisis",
            "salidas_proceso__ejecucion__etapa",
            "salidas_proceso__liberacion_calidad",
        )
        .annotate(
            litros_procesados_anotados=Subquery(
                salida_del_lote.values("litros")[:1],
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
    )
    serializer_class = LoteSerializer
    permission_classes = [EscribeProduccion]

    def destroy(self, request, *args, **kwargs):
        """Los lotes industriales se anulan; nunca se eliminan físicamente."""
        return Response(
            {
                "detail": (
                    "Un lote no se elimina porque forma parte de la trazabilidad. "
                    "Cámbialo a estado anulado e indica el motivo."
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_serializer_class(self):
        # Todo lo que opera sobre UN lote devuelve el lote entero, con sus
        # análisis. Devolver menos en la respuesta de un PATCH obliga a quien
        # llama a pedir el lote otra vez, y si no lo hace se queda con una
        # ficha a medias: fue exactamente lo que rompió el panel de Producción
        # al cerrar un lote.
        if self.action in ("retrieve", "update", "partial_update"):
            return LoteDetalleSerializer

        return super().get_serializer_class()

    def get_serializer_context(self):
        contexto = super().get_serializer_context()
        # Las especificaciones se cargan una vez y las comparten todos los
        # lotes del listado.
        contexto["especificaciones"] = list(
            filtrar_por_scope(
                Especificacion.objects.all(), self.request.user,
                campo_empresa="producto__mandante__empresa_id",
            )
        )
        return contexto

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        producto = parametros.get("producto")
        if producto:
            consulta = consulta.filter(producto_id=producto)

        mandante = parametros.get("mandante")
        if mandante:
            consulta = consulta.filter(producto__mandante_id=mandante)

        naturaleza = parametros.get("naturaleza")
        if naturaleza:
            consulta = consulta.filter(producto__naturaleza=naturaleza)

        estado = parametros.get("estado")
        if estado:
            consulta = consulta.filter(estado=estado)
            if estado == Lote.Estado.BORRADOR:
                consulta = consulta.filter(abierto_por=self.request.user)
        else:
            consulta = consulta.exclude(estado=Lote.Estado.BORRADOR)

        desde = parametros.get("desde")
        if desde:
            consulta = consulta.filter(fecha__gte=desde)

        hasta = parametros.get("hasta")
        if hasta:
            consulta = consulta.filter(fecha__lte=hasta)

        buscar = parametros.get("buscar")
        if buscar:
            consulta = consulta.filter(codigo_lote__icontains=buscar)

        calidad = parametros.get("calidad")
        if calidad:
            consulta = consulta.filter(id__in=self._ids_con_calidad(consulta, calidad))

        return consulta

    def perform_update(self, serializer):
        super().perform_update(serializer)
        # La instancia se obtuvo desde el queryset anotado antes del PATCH.
        # Si cambió el vale, esa anotación describe el silo anterior. La
        # respuesta inmediata debe usar el cálculo fresco de respaldo.
        serializer.instance.__dict__.pop("litros_procesados_anotados", None)

    # --------------------------------------------------------- borradores

    def _borrador_del_usuario(self, request, pk=None, *, bloquear=False):
        """
        El borrador abierto de esta persona, o `None`.

        `bloquear` toma el candado de fila y solo vale dentro de una
        transacción; lo piden las acciones que escriben. El porqué está en
        `recepcion.views.RecepcionViewSet._borrador_del_usuario`: sin él, un
        autoguardado en vuelo pisa la confirmación y la deja en borrador.
        """
        consulta = self.queryset.filter(
            estado=Lote.Estado.BORRADOR, abierto_por=request.user
        )
        if pk is not None:
            consulta = consulta.filter(pk=pk)
        if bloquear:
            consulta = consulta.select_for_update(of=("self",))
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
                    "detail": "Ya tienes un borrador de lote abierto.",
                    "borrador": self.get_serializer(existente).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        datos = request.data.copy()
        datos.pop("codigo_lote", None)
        datos.pop("estado", None)
        serializer = self.get_serializer(data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        validados = dict(serializer.validated_data)
        validados.pop("litros_estandarizados", None)
        validados.pop("motivo_anulacion", None)
        fecha = validados.pop("fecha", timezone.localdate())
        lote = Lote.objects.create(
            **validados,
            codigo_lote=Lote.nuevo_codigo_borrador(),
            fecha=fecha,
            estado=Lote.Estado.BORRADOR,
            abierto_por=request.user,
            abierto_en=timezone.now(),
        )
        return Response(self.get_serializer(lote).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="guardar-borrador")
    @transaction.atomic
    def guardar_borrador(self, request, pk=None):
        lote = self._borrador_del_usuario(request, pk, bloquear=True)
        if lote is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        datos = request.data.copy()
        datos.pop("codigo_lote", None)
        datos.pop("estado", None)
        serializer = self.get_serializer(lote, data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="confirmar-borrador")
    @transaction.atomic
    def confirmar_borrador(self, request, pk=None):
        lote = self._borrador_del_usuario(request, pk, bloquear=True)
        if lote is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        motivos = lote.motivos_para_confirmar()
        if motivos:
            return Response({"motivos": motivos}, status=status.HTTP_400_BAD_REQUEST)
        try:
            confirmado = servicios_produccion.abrir_lote_desde_vale(
                vale=lote.vale,
                codigo_lote=lote.codigo_lote_propuesto.strip(),
                fecha=lote.fecha,
                litros=lote.litros_estandarizados_borrador,
                usuario=request.user,
                lote_borrador=lote,
                op=lote.op,
                orden=lote.orden,
                equipo=lote.equipo,
                linea=lote.linea,
                turno=lote.turno,
                observacion=lote.observacion,
            )
        except DjangoValidationError as error:
            detalle = error.message_dict if hasattr(error, "message_dict") else {
                "motivos": error.messages
            }
            return Response(detalle, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(confirmado).data)

    @action(detail=True, methods=["post"], url_path="descartar-borrador")
    @transaction.atomic
    def descartar_borrador(self, request, pk=None):
        lote = self._borrador_del_usuario(request, pk, bloquear=True)
        if lote is not None:
            lote.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def create(self, request, *args, **kwargs):
        """
        Abre una corrida desde un vale liberado de Estandarización.

        Producción no elige silos. El vale ya fija de dónde vino la leche y en
        qué silo quedó; aquí solo se declara cuánto entra a esta corrida, el
        producto, la línea y la máquina.
        """
        if "asignaciones" in request.data:
            return Response(
                {"detail": (
                    "Producción no selecciona silos. Selecciona un vale "
                    "liberado de Estandarización e indica sus litros."
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="vales-disponibles")
    def vales_disponibles(self, request):
        """Vales liberados con saldo, listos para que Producción los tome."""
        return Response(self._vales_operativos(request))

    @staticmethod
    def _vales_operativos(request):
        from estandarizacion.models import ValeEstandarizacion
        from procesos.models import EtapaProceso
        from procesos.servicios import (
            etapas_iniciales_por_producto,
            tipos_equipo_para_etapa,
        )

        vales = filtrar_por_scope(
            ValeEstandarizacion.objects.filter(
                estado=ValeEstandarizacion.Estado.LIBERADO
            ).select_related(
                "producto", "producto__mandante", "silo_entera",
                "silo_descremada", "silo_destino",
            ),
            request.user,
            campo_sucursal="silo_destino__sucursal_id",
            campo_empresa="silo_destino__sucursal__empresa_id",
        )

        producto = request.query_params.get("producto")
        if producto:
            vales = vales.filter(producto_id=producto)

        vales = list(vales)
        etapas_por_producto = etapas_iniciales_por_producto(
            productos_sucursales={
                (vale.producto_id, vale.silo_destino.sucursal_id)
                for vale in vales
            },
            etapa_previa_tipo=EtapaProceso.Tipo.ESTANDARIZACION,
        )

        # El saldo lo calcula `litros_ya_tomados`, la **misma** función que usa
        # `abrir_lote_desde_vale` para decidir si el lote cabe.
        #
        # Antes esta pantalla lo contaba aparte, uniendo por `movimiento.lote`
        # mientras la regla une por `origen_id` y además acota al silo de
        # destino. Las dos cuentas discrepan en cuanto existe un movimiento con
        # `origen_id` puesto y `lote` nulo —los hay en la base—: el desplegable
        # ofrecía un vale con veinte mil litros libres y el formulario, ya
        # completo, respondía «quedan 0,00 L y se piden 20.000». El operador no
        # tenía forma de saber cuál de los dos números era el bueno.
        resultado = []
        for vale in vales:
            usados = servicios_produccion.litros_ya_tomados(vale)
            disponibles = vale.volumen - usados
            if disponibles <= 0:
                continue
            etapas_iniciales = etapas_por_producto.get(
                (vale.producto_id, vale.silo_destino.sucursal_id), []
            )
            resultado.append({
                "id": vale.id,
                "codigo": vale.codigo,
                "fecha": vale.fecha,
                "producto": vale.producto_id,
                "producto_nombre": vale.producto.nombre,
                "producto_familia": vale.producto.familia,
                "mandante_nombre": vale.producto.mandante.nombre,
                "rc_objetivo": vale.rc_objetivo,
                "rc_real": vale.rc_real,
                "litros_preparados": vale.volumen,
                "litros_usados": usados,
                "litros_disponibles": disponibles,
                "silo_entera_codigo": vale.silo_entera.codigo,
                "silo_descremada_codigo": (
                    vale.silo_descremada.codigo if vale.silo_descremada else None
                ),
                "silo_destino_codigo": vale.silo_destino.codigo,
                "etapas_iniciales": [
                    {
                        "id": etapa.pk,
                        "nombre": etapa.nombre,
                        "tipo": etapa.tipo,
                        "orden": etapa.orden,
                        "proceso": etapa.proceso_id,
                        "tipos_equipo": sorted(tipos_equipo_para_etapa(etapa.tipo)),
                    }
                    for etapa in etapas_iniciales
                ],
            })
        return resultado

    @action(detail=False, methods=["get"], url_path="opciones-inicio")
    def opciones_inicio(self, request):
        """Una sola carga liviana para abrir el asistente de Producción."""
        from inventario.models import CicloCIP
        from procesos.models import EjecucionProceso
        from procesos.servicios import ESTADOS_QUE_OCUPAN_EQUIPO

        entradas = self._vales_operativos(request)
        tipos_iniciales = {
            tipo
            for entrada in entradas
            for etapa in entrada["etapas_iniciales"]
            for tipo in etapa["tipos_equipo"]
        }

        cip_en_curso = CicloCIP.objects.filter(
            equipo_id=OuterRef("pk"), estado=CicloCIP.Estado.EN_CURSO,
        )
        ultimo_aseo = (
            CicloCIP.objects.filter(equipo_id=OuterRef("pk"))
            .exclude(estado=CicloCIP.Estado.PROGRAMADO)
            .order_by("-inicio")
        )
        ocupada = EjecucionProceso.objects.filter(
            equipo_id=OuterRef("pk"),
            estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
        )
        equipos = filtrar_por_scope(
            Equipo.objects.filter(activo=True, tipo__in=tipos_iniciales).annotate(
                ocupada=Exists(ocupada),
                cip_en_curso=Exists(cip_en_curso),
                aseo_verificacion=Subquery(ultimo_aseo.values("verificacion")[:1]),
                aseo_estado=Subquery(ultimo_aseo.values("estado")[:1]),
            ),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        ordenes = filtrar_por_scope(
            OrdenProduccion.objects.filter(
                estado__in=[
                    OrdenProduccion.Estado.PROGRAMADA,
                    OrdenProduccion.Estado.EN_PROCESO,
                ]
            ).select_related("producto"),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )
        opciones_equipos = []
        for equipo in equipos:
            motivo = ""
            advertencia_aseo = ""
            if equipo.ocupada:
                motivo = "Máquina ocupada por otra corrida."
            elif equipo.cip_en_curso:
                motivo = "Máquina actualmente en CIP."
            elif equipo.aseo_estado is None:
                advertencia_aseo = f"{equipo.nombre} no tiene un aseo/CIP registrado. Verifica antes de operar."
            elif equipo.aseo_estado == CicloCIP.Estado.OBSERVADO or equipo.aseo_verificacion == CicloCIP.Verificacion.OBSERVADO:
                advertencia_aseo = f"El último aseo de {equipo.nombre} quedó observado. Producción puede continuar con advertencia."
            elif equipo.aseo_verificacion != CicloCIP.Verificacion.CONFORME:
                advertencia_aseo = f"El aseo de {equipo.nombre} aún no tiene verificación conforme de Calidad."
            opciones_equipos.append({
                "id": equipo.id,
                "codigo": equipo.codigo,
                "nombre": equipo.nombre,
                "tipo": equipo.tipo,
                "tipo_etiqueta": equipo.get_tipo_display(),
                "consume_leche": equipo.consume_leche,
                "orden": equipo.orden,
                "activo": equipo.activo,
                "habilitado": not motivo,
                "motivo_no_habilitado": motivo,
                "aseo_verificacion": equipo.aseo_verificacion,
                "advertencia_aseo": advertencia_aseo,
            })
        for entrada in entradas:
            tipos_compatibles = {
                tipo
                for etapa in entrada["etapas_iniciales"]
                for tipo in etapa["tipos_equipo"]
            }
            entrada["equipos_compatibles"] = [
                equipo["id"]
                for equipo in opciones_equipos
                if equipo["tipo"] in tipos_compatibles
            ]
        return Response({
            "entradas": entradas,
            "equipos": opciones_equipos,
            "ordenes": [
                {
                    "id": orden.pk,
                    "codigo": orden.codigo,
                    "producto": orden.producto_id,
                    "producto_nombre": orden.producto.nombre,
                    "cantidad_planificada": orden.cantidad_planificada,
                    "unidad": orden.unidad,
                    "estado": orden.get_estado_display(),
                }
                for orden in ordenes
            ],
        })

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Además de guardar, descuenta de bodega si el lote pasó a producido.

        Es el momento en que se conocen los kilos, y sin kilos no hay nada que
        descontar. Antes esto no ocurría en ninguna parte: `inventario` tenía
        el servicio y nadie lo llamaba, así que la trazabilidad se cortaba
        justo donde el material se consume.
        """
        antes = self.get_object().estado

        respuesta = super().update(request, *args, **kwargs)

        if antes == Lote.Estado.PRODUCIDO:
            return respuesta

        lote = self.get_object()

        if lote.estado != Lote.Estado.PRODUCIDO:
            return respuesta

        # El mismo cambio de estado completa la salida de la ejecución. Así
        # Procesos ve la corrida cerrada con su lote, sin una carga manual.
        try:
            servicios_produccion.registrar_produccion(lote=lote)
        except DjangoValidationError as error:
            detalle = (
                error.message_dict
                if hasattr(error, "message_dict")
                else {"detail": error.messages}
            )
            raise serializers.ValidationError(detalle) from error

        # La orden, el descuento de bodega y el aviso a Calidad son la misma
        # cola para los tres caminos que declaran un lote producido. Vive en
        # `produccion.servicios` para que Secado y Mantequilla no tengan que
        # reimplementarla — Secado se quedó sin sus dos últimas partes cuando
        # la tenía copiada.
        aviso = servicios_produccion.cerrar_lote_producido(
            lote=lote, usuario=request.user
        )

        # Se vuelve a serializar después de descontar y no antes: la ficha
        # lleva el estado del consumo, y la que armó `super().update()` se
        # construyó cuando todavía no había ocurrido. Devolverla diría que el
        # consumo quedó pendiente justo después de haberlo hecho.
        datos = self.get_serializer(lote).data

        if aviso:
            datos["avisos"] = [*(respuesta.data.get("avisos") or []), aviso]

        respuesta.data = datos

        return respuesta

    @action(detail=False, methods=["get"], url_path="codigo-sugerido")
    def codigo_sugerido(self, request):
        """
        El código que le tocaría a un lote nuevo, según el POE.009.02.

        Se **sugiere**, no se impone: la respuesta trae el código y el
        operador puede cambiarlo. El histórico de planta trae códigos que no
        siguen el patrón y hay que poder registrarlos, así que el generador
        avisa y no restringe — la misma razón por la que `codigo_lote_valido`
        no cuelga del `clean()` del modelo.

        `segunda_produccion` no se pregunta: se deduce de si ya existe un lote
        de ese producto y esa fecha. Preguntarlo sería pedirle al operador un
        dato que el sistema ya tiene, y equivocarse ahí repite un código.
        """
        equipo_id = request.query_params.get("equipo")
        fecha_texto = request.query_params.get("fecha")

        if not equipo_id or not fecha_texto:
            return Response(
                {"detail": "Indica la máquina y la fecha."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fecha = parse_date(fecha_texto)

        if fecha is None:
            return Response(
                {"detail": f"Fecha no reconocida: {fecha_texto!r} (usa AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        equipo = get_object_or_404(
            filtrar_por_scope(
                Equipo.objects.all(), request.user,
                campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            ),
            pk=equipo_id,
        )

        # El correlativo distingue dos lotes del mismo producto el mismo día.
        # Se cuenta lo que ya existe en vez de preguntarlo: pedirle al
        # operador un dato que el sistema tiene es como se repite un código.
        anteriores = self.get_queryset().filter(equipo=equipo, fecha=fecha).count()
        correlativo = anteriores + 1

        codigo = dominio.generar_codigo_lote(fecha, equipo.sigla, correlativo)

        if codigo is None:
            # 200 con `codigo: null`: el formulario sigue abierto y el
            # operador escribe el código a mano. Un 400 se leería como si el
            # lote no se pudiera crear, y sí se puede.
            return Response(
                {
                    "codigo": None,
                    "correlativo": correlativo,
                    "motivo": (
                        f"«{equipo.nombre}» no tiene sigla cargada en Maestros, y la "
                        "sigla es parte del código de lote. Escríbelo a mano o "
                        "completa el maestro de equipos."
                    ),
                }
            )

        return Response(
            {
                "codigo": codigo,
                "correlativo": correlativo,
                "motivo": (
                    f"Es el lote n.º {correlativo} de este producto en la fecha."
                    if anteriores
                    else None
                ),
            }
        )

    @action(detail=True, methods=["get", "post"])
    def asignacion(self, request, pk=None):
        """
        La leche que este lote tomó de los silos.

        Aquí empieza la trazabilidad. La leche se mezcla dentro del silo, así
        que lo único que se puede afirmar de un lote es de qué estanques salió
        y cuánto de cada uno; el vínculo con las recepciones concretas es un
        conjunto de candidatas, no una cadena (MODELO_DATOS.md §2.5).

        Los litros **los declara Producción**, no los deriva el sistema. El
        libro mayor registra lo que realmente se tomó del estanque; lo que la
        receta dice que debería haberse tomado es otra cosa, y guardar la
        estimación en lugar del hecho haría que el saldo del silo dejara de
        ser un saldo.

        Se admiten varias líneas porque un producto puede mezclar leche de más
        de un silo, que es lo normal cuando ninguno alcanza solo.
        """
        lote = self.get_object()

        if request.method == "GET":
            return Response(self._estado_asignacion(lote))

        lineas = request.data.get("asignaciones")

        if not isinstance(lineas, list) or not lineas:
            return Response(
                {
                    "detail": (
                        "Hay que indicar de qué silos se tomó la leche: "
                        '[{"silo": 3, "litros": 60000}, ...]'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        bloqueo = self._por_que_no_se_puede_asignar(lote)
        if bloqueo:
            return Response({"detail": bloqueo}, status=status.HTTP_409_CONFLICT)

        creados = self._crear_asignaciones(lote, lineas)

        if isinstance(creados, Response):
            return creados

        return Response(self._estado_asignacion(lote))

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"asignacion/(?P<movimiento_id>\d+)",
    )
    def quitar_asignacion(self, request, pk=None, movimiento_id=None):
        """
        Quita una línea de asignación.

        Solo mientras el lote sigue **en proceso**: hasta ahí la asignación se
        está armando y borrar una línea es corregir un borrador. Después es
        histórico, y un asiento del libro mayor no se borra — se corrige con
        un ajuste que deja rastro.
        """
        from recepcion.models import MovimientoSilo

        lote = self.get_object()

        if lote.estado != Lote.Estado.EN_PROCESO:
            return Response(
                {
                    "detail": (
                        f"Un lote {lote.get_estado_display().lower()} ya no cambia "
                        "su asignación. Corrija con un ajuste de silo, que deja "
                        "rastro."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        movimiento = get_object_or_404(
            MovimientoSilo,
            pk=movimiento_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
        )
        movimiento.delete()

        return Response(self._estado_asignacion(lote))

    @action(detail=True, methods=["get"])
    def trazabilidad(self, request, pk=None):
        """
        De qué recepciones pudo salir este lote.

        Devuelve un **conjunto** de recepciones candidatas por silo, no una
        cadena: son las que habían ingresado a ese estanque antes de que el
        lote consumiera. Prometer un vínculo exacto sería falso, porque dentro
        del silo la leche ya está mezclada.
        """
        from recepcion.dominio import trazabilidad_lote
        from recepcion.models import MovimientoSilo, Recepcion

        lote = self.get_object()

        tramos = trazabilidad_lote(lote.id, MovimientoSilo.objects.all())

        ids = {r for tramo in tramos for r in tramo["recepciones"]}
        recepciones = {
            r.id: {
                "id": r.id,
                "fecha": r.fecha,
                "guia": r.guia,
                "litros": r.litros,
                "procedencia": r.procedencia,
                "vehiculo": r.vehiculo.placa if r.vehiculo else None,
            }
            for r in Recepcion.objects.filter(id__in=ids).select_related("vehiculo")
        }

        silos = {
            s.id: s.codigo
            for s in Silo.objects.filter(id__in=[t["silo_id"] for t in tramos])
        }

        return Response(
            {
                "lote": lote.codigo_lote,
                "tramos": [
                    {
                        "silo": tramo["silo_id"],
                        "silo_codigo": silos.get(tramo["silo_id"]),
                        "litros": tramo["litros"],
                        "fecha_hora": tramo["fecha_hora"],
                        "recepciones": [
                            recepciones[r] for r in tramo["recepciones"] if r in recepciones
                        ],
                    }
                    for tramo in tramos
                ],
                # Se dice explícitamente para que nadie lea la lista como una
                # cadena de origen única.
                "nota": (
                    "Las recepciones son candidatas: la leche se mezcla dentro "
                    "del silo y no hay vínculo uno a uno."
                ),
            }
        )

    # ------------------------------------------------------------- ayudantes

    def _crear_asignaciones(self, lote, lineas):
        """
        Crea las líneas de asignación, todas o ninguna.

        Se valida **antes** de escribir nada. Devolver un `Response` desde
        dentro de `transaction.atomic()` NO revierte —salir por return es una
        salida normal, no un error—, así que media asignación quedaría
        guardada: el silo descontado y el lote sin la leche que decía tener.
        """
        from recepcion.models import MovimientoSilo

        preparadas = []

        for linea in lineas:
            silo_id = linea.get("silo")
            crudo = linea.get("litros")

            if not silo_id or crudo in (None, ""):
                return Response(
                    {"detail": "Cada línea necesita un silo y sus litros."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                litros = Decimal(str(crudo))
            except (InvalidOperation, TypeError):
                return Response(
                    {"detail": f"Litros no numéricos: {crudo!r}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if litros <= 0:
                return Response(
                    {"detail": "Los litros asignados deben ser mayores que cero."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            preparadas.append((silo_id, litros, linea.get("fecha_hora")))

        with transaction.atomic():
            return [
                MovimientoSilo.objects.create(
                    silo_id=silo_id,
                    tipo=MovimientoSilo.Tipo.SALIDA,
                    litros=litros,
                    # La hora acota la trazabilidad: solo cuentan las
                    # recepciones que ya estaban en el silo. Se puede declarar
                    # para cargar una asignación con retraso sin arrastrar
                    # leche que llegó después.
                    fecha_hora=fecha_hora or timezone.now(),
                    origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
                    origen_id=lote.id,
                    motivo=f"Asignación de leche al lote {lote.codigo_lote}",
                )
                for silo_id, litros, fecha_hora in preparadas
            ]

    def _por_que_no_se_puede_asignar(self, lote) -> str | None:
        """
        Un lote liberado o histórico no cambia de qué leche salió.

        Cambiarlo después de que Calidad firmó dejaría esa firma respaldando
        un producto hecho con otra materia prima, que es exactamente lo que la
        trazabilidad existe para impedir.
        """
        from calidad.models import Liberacion

        if lote.vale_id:
            return (
                f"El origen lo fija el vale {lote.vale.codigo}: Producción no "
                "puede cambiar su silo de estandarización."
            )

        if not Lote.TRANSICIONES.get(lote.estado, []):
            return (
                f"Un lote {lote.get_estado_display().lower()} es histórico: su "
                "asignación de leche ya no cambia."
            )

        liberacion = Liberacion.objects.filter(lote=lote).first()

        if liberacion is not None and liberacion.liberado:
            return (
                "El lote está liberado: cambiar de qué leche salió dejaría la "
                "firma de Calidad respaldando otra materia prima. Retire antes "
                f"la liberación en expedientes/{lote.id}/revisar/."
            )

        return None

    def _estado_asignacion(self, lote):
        """
        Lo asignado, lo que la receta esperaba, y cómo se comparan.

        Los dos números se llevan aparte a propósito: **lo asignado es el
        hecho** —lo que salió del estanque— y **lo teórico es la expectativa**.
        Se informa, no se bloquea: una merma mayor de la prevista es algo que
        explicar, no algo que impedir.

        Sobre los dos indicadores, porque el nombre importa:

        - `consumo_pct` es asignado / teórico. Por debajo de 100 se usó menos
          leche de la prevista; por encima, más. En ese orden y no al revés:
          la razón inversa sube cuando se consume menos, y un número que crece
          al gastar menos se lee como un logro cuando muchas veces solo
          significa que falta cargar una línea.
        - `litros_por_kg` es el rendimiento como lo mide la planta: cuánta
          leche costó cada kilo. Al lado va el de la receta, que es contra lo
          que se compara.
        """
        from recepcion.models import MovimientoSilo

        lineas = MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
        ).select_related("silo")

        asignado = float(sum(l.litros for l in lineas))
        teorico = self._litros_de_receta(lote)
        kg = float(lote.kg_producidos or 0)

        return {
            "lote": lote.codigo_lote,
            "estado": lote.estado,
            "editable": self._por_que_no_se_puede_asignar(lote) is None,
            "motivo_bloqueo": self._por_que_no_se_puede_asignar(lote),
            "lineas": [
                {
                    "id": l.id,
                    "silo": l.silo_id,
                    "silo_codigo": l.silo.codigo,
                    "litros": float(l.litros),
                    "fecha_hora": l.fecha_hora,
                }
                for l in lineas
            ],
            "asignado": asignado,
            # None cuando el producto no tiene receta vigente: no se inventa.
            "teorico": teorico,
            "diferencia": (asignado - teorico) if teorico is not None else None,
            "consumo_pct": (
                round(asignado / teorico * 100, 1)
                if teorico else None
            ),
            # Rendimiento real: sin kilos declarados todavía no hay tal cosa.
            "litros_por_kg": round(asignado / kg, 2) if kg and asignado else None,
            "litros_por_kg_receta": (
                round(teorico / kg, 2) if kg and teorico else None
            ),
        }

    @staticmethod
    def _litros_de_receta(lote) -> float | None:
        """
        Litros que la receta vigente dice que cuesta este lote.

        Sin kilos declarados no hay expectativa que calcular: la receta dice
        cuánta leche cuesta *cada kilo*, y mientras el lote está en proceso
        todavía no se sabe cuántos serán.
        """
        if lote.kg_producidos is None:
            return None

        return recetas.litros_de_leche(
            list(Producto.objects.all()),
            list(Receta.objects.prefetch_related("componentes")),
            lote.producto_id,
            lote.kg_producidos,
            lote.fecha,
        )

    @staticmethod
    def _ids_con_calidad(consulta, resultado):
        """
        IDs de los lotes cuyo veredicto de calidad es el pedido.

        El resultado se calcula, no se guarda (MODELO_DATOS.md §2.2), así que
        no se puede filtrar con SQL: hay que evaluar en Python y devolver los
        IDs para que el filtrado y la paginación sigan ocurriendo en la base.

        Coste: recorre los lotes que pasaron los demás filtros. Con el
        histórico previsto (~954 lotes) es asumible. Si algún día pesa, la
        salida no es persistir el veredicto —eso rompería la reevaluación del
        histórico— sino cachear por lote e invalidar al cambiar la spec.
        """
        especificaciones = list(Especificacion.objects.all())

        return [
            lote.id
            for lote in consulta.prefetch_related("analisis")
            if dominio.resultado_calidad_lote(
                lote, list(lote.analisis.all()), especificaciones
            ).resultado
            == resultado
        ]


class AnalisisViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    queryset = Analisis.objects.select_related("lote")
    serializer_class = AnalisisSerializer
    permission_classes = [EscribeAnalisisCalidad]

    def get_queryset(self):
        consulta = super().get_queryset()

        lote = self.request.query_params.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        return consulta


#: Ventana por defecto del panel, en días. Es un indicador de gestión —«cómo
#: vamos»—, no el histórico: para eso están los listados, que paginan.
RESUMEN_DIAS = int(os.environ.get("RESUMEN_DIAS", "90"))


@api_view(["GET"])
@permission_classes([EscribeProduccion])
def resumen(request):
    """
    Indicadores del panel general.

    Acepta `desde` y `hasta` (YYYY-MM-DD) para acotar el periodo.

    El cumplimiento de calidad viaja SIEMPRE con su cobertura: un 90 % sobre 3
    lotes de 40 no es una buena noticia, y el panel tiene que poder decirlo.
    """
    lotes = filtrar_por_scope(
        Lote.objects.select_related("producto", "producto__mandante")
        .prefetch_related("analisis")
        .exclude(estado__in=[Lote.Estado.BORRADOR, Lote.Estado.ANULADO]),
        request.user,
        campo_sucursal="sucursal_id",
        campo_empresa="sucursal__empresa_id",
    )

    desde = request.query_params.get("desde")
    hasta = request.query_params.get("hasta")

    # **Ventana por defecto.** Sin ella, el panel evaluaba la calidad de todo
    # el histórico en memoria en cada carga: el coste crecía con la planta y
    # nadie lo notaba hasta que el panel dejaba de responder. Noventa días es
    # lo que un panel de gestión responde —«cómo vamos»—; para el histórico
    # completo están el listado de lotes y el de expedientes, que sí paginan.
    if not desde and not hasta:
        desde = (timezone.localdate() - timedelta(days=RESUMEN_DIAS)).isoformat()

    if desde:
        lotes = lotes.filter(fecha__gte=desde)

    if hasta:
        lotes = lotes.filter(fecha__lte=hasta)

    lotes = list(lotes)
    especificaciones = list(
        filtrar_por_scope(
            Especificacion.objects.all(), request.user,
            campo_empresa="producto__mandante__empresa_id",
        )
    )

    por_resultado = Counter()
    primera_pasada = Counter()
    kg_por_producto = defaultdict(float)
    kg_por_mandante = defaultdict(float)

    for lote in lotes:
        analisis_lote = list(lote.analisis.all())
        resultado = dominio.resultado_calidad_lote(
            lote, analisis_lote, especificaciones
        )
        por_resultado[resultado.resultado] += 1
        resultado_inicial = dominio.resultado_calidad_lote(
            lote, analisis_lote[:1], especificaciones
        )
        primera_pasada[resultado_inicial.resultado] += 1

        # Un lote en proceso todavía no declaró kilos. Suma cero: no es que
        # haya producido nada, es que aún no se sabe.
        kilos = float(lote.kg_producidos or 0)
        kg_por_producto[lote.producto.nombre] += kilos
        kg_por_mandante[lote.producto.mandante.nombre] += kilos

    evaluados = por_resultado[dominio.CONFORME] + por_resultado[dominio.NO_CONFORME]
    evaluados_primera = (
        primera_pasada[dominio.CONFORME] + primera_pasada[dominio.NO_CONFORME]
    )
    ids_lotes = [lote.id for lote in lotes]
    from calidad.models import Liberacion
    from procesos.models import AutorizacionReproceso

    rework = AutorizacionReproceso.objects.filter(lote_id__in=ids_lotes).aggregate(
        kg=Sum("cantidad_kg"), total=Count("id")
    )

    return Response(
        {
            # El periodo viaja en la respuesta: un indicador sin decir sobre
            # qué ventana está calculado invita a leerlo como si fuera el
            # total histórico.
            "periodo": {"desde": desde, "hasta": hasta},
            "lotes": len(lotes),
            "kg_producidos": float(
                Lote.objects.filter(id__in=ids_lotes).aggregate(
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
                "primera_pasada": (
                    round(
                        primera_pasada[dominio.CONFORME]
                        / evaluados_primera * 100, 1
                    )
                    if evaluados_primera else None
                ),
                "bloqueados": Liberacion.objects.filter(
                    lote_id__in=ids_lotes, estado=Liberacion.Estado.RECHAZADO,
                ).count(),
            },
            "rework": {
                "lotes": rework["total"],
                "kg": float(rework["kg"] or 0),
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


class ControlProcesoViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "lote__sucursal_id"
    tenant_lookup_empresa = "lote__sucursal__empresa_id"
    """
    Control de proceso de un equipo para un lote, con el PCC 1 de uperización.

    Es un registro de inocuidad además de uno de producción: sus lecturas
    deciden si el lote se puede liberar (`calidad.dominio.bloqueos_de_inocuidad`).
    """

    queryset = ControlProceso.objects.select_related("lote", "equipo").prefetch_related(
        "lecturas"
    )
    serializer_class = ControlProcesoSerializer
    permission_classes = [EscribeProduccion]

    def perform_create(self, serializer):
        serializer.save(operador=self.request.user)

    def perform_update(self, serializer):
        serializer.save()

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        lote = parametros.get("lote")
        if lote:
            consulta = consulta.filter(lote_id=lote)

        equipo = parametros.get("equipo")
        if equipo:
            consulta = consulta.filter(equipo=equipo)

        fecha = parametros.get("fecha")
        if fecha:
            consulta = consulta.filter(fecha=fecha)

        return consulta


class ControlProcesoLecturaViewSet(QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "control__lote__sucursal_id"
    tenant_lookup_empresa = "control__lote__sucursal__empresa_id"
    queryset = ControlProcesoLectura.objects.select_related("control")
    serializer_class = ControlProcesoLecturaSerializer
    permission_classes = [EscribeProduccion]

    def get_queryset(self):
        consulta = super().get_queryset()

        control = self.request.query_params.get("control")
        if control:
            consulta = consulta.filter(control_id=control)

        return consulta


@api_view(["GET"])
@permission_classes([EscribeInocuidad])
def catalogos_inocuidad(request):
    """
    Opciones de los formularios de control de proceso y monitoreo PPRO.

    Igual que en maestros: el modelo es la fuente de verdad y la pantalla no
    lleva su propia copia. Incluye los **parámetros del PCC 1** para que la
    captura los rotule igual que el dominio los evalúa — si la pantalla los
    renombrara, el control dejaría de encontrarlos y el PCC pasaría a no
    vigilar nada en silencio.
    """
    from inocuidad.models import MonitoreoPPRO, PproLectura
    from maestros.models import Equipo

    def opciones(choices):
        return [{"valor": v, "etiqueta": e} for v, e in choices]

    def equipos(*tipos):
        """
        Equipos del maestro como opciones. El `valor` es el **id**, que es lo
        que la referencia guarda.

        Qué máquinas admite cada formulario se decide aquí y no en la
        pantalla: un control de proceso se lleva en un evaporador o en una
        torre —no en una envasadora—, y si el filtro viviera en el cliente
        sería una segunda copia de esa regla, libre de discrepar.
        """
        consulta = filtrar_por_scope(
            Equipo.objects.filter(activo=True), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

        if tipos:
            consulta = consulta.filter(tipo__in=tipos)

        return [
            {"valor": e.id, "etiqueta": e.nombre, "codigo": e.codigo}
            for e in consulta.order_by("orden", "nombre")
        ]

    return Response(
        {
            "equipo_control": equipos(Equipo.Tipo.EVAPORADOR, Equipo.Tipo.TORRE),
            # El PPRO se monitorea en cualquier máquina: presión de aire en las
            # torres, cuerpos extraños en las envasadoras, y el detector de
            # metales no cuelga de ninguna.
            "equipo_ppro": equipos(),
            "turno": opciones(Lote.Turno.choices),
            "tipo_ppro": opciones(MonitoreoPPRO.Tipo.choices),
            "resultado_ppro": opciones(PproLectura.Resultado.choices),
            "pcc1": {
                "temperatura": dominio.PCC1_TEMPERATURA,
                "caudal": dominio.PCC1_CAUDAL,
            },
        }
    )
