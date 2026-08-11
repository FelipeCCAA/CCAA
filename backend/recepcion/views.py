from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from maestros.models import Silo
from usuarios.permisos import DecideCalidadRecepcion, EscribeRecepcion
from usuarios.models import Sucursal
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin, exigir_sucursal_permitida,
    filtrar_por_scope, scope_de,
)

from . import dominio
from .models import MovimientoSilo, Recepcion
from .serializers import MovimientoSiloSerializer, RecepcionSerializer


class RecepcionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    tenant_relation_fields = {
        "sucursal": ("pk", "empresa_id"),
        "vehiculo": ("sucursal_id", "sucursal__empresa_id"),
        "silo": ("sucursal_id", "sucursal__empresa_id"),
        "carga_recoleccion": (
            "recoleccion__parada__ruta__vehiculo__sucursal_id",
            "recoleccion__parada__ruta__vehiculo__sucursal__empresa_id",
        ),
    }
    queryset = Recepcion.objects.select_related(
        "vehiculo",
        "carga_recoleccion__recoleccion__parada__ruta__vehiculo",
        "silo",
        "operador",
        "muestreado_por",
        "calidad_por",
        "silo_asignado_por",
    )
    serializer_class = RecepcionSerializer
    permission_classes = [EscribeRecepcion]

    def get_permissions(self):
        if self.action == "decidir_calidad":
            return [DecideCalidadRecepcion()]
        return super().get_permissions()

    def get_queryset(self):
        consulta = super().get_queryset()
        parametros = self.request.query_params

        # `estado` admite varios separados por coma: las pestañas del módulo
        # agrupan estados —«Calidad» son las muestreadas *y* las retenidas— y
        # sin esto cada una tendría que traerse todo y filtrar en el cliente,
        # que es como los contadores terminaban midiendo la página en vez del
        # total.
        estado = parametros.get("estado")
        if estado:
            estados = [e for e in estado.split(",") if e]
            consulta = (
                consulta.filter(estado__in=estados)
                if len(estados) > 1
                else consulta.filter(estado=estados[0])
            )

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

        # La búsqueda la resuelve la base, no el cliente. Filtrar en el
        # navegador solo alcanza a las filas ya descargadas: buscar una guía de
        # la semana pasada respondía «no encontramos recepciones», que es una
        # afirmación falsa sobre algo que sí existe.
        termino = (parametros.get("q") or "").strip()
        if termino:
            consulta = consulta.filter(
                Q(guia__icontains=termino)
                | Q(modulo__icontains=termino)
                | Q(codigo_muestra__icontains=termino)
                | Q(procedencia__icontains=termino)
                | Q(vehiculo__placa__icontains=termino)
                | Q(silo__codigo__icontains=termino)
            )

        return consulta

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        """
        Cuántas recepciones hay en cada estado, **sobre el total**.

        El tablero las contaba sobre la página que tenía cargada: con más de
        cincuenta recepciones dejaba de decir la verdad, y al filtrar por un
        estado mostraba ceros en todos los demás —como si la planta se hubiera
        vaciado—. Un contador que solo acierta cuando hay pocos datos es peor
        que no tenerlo, porque nadie sabe cuándo dejó de acertar.

        Se cuenta sobre el queryset **sin filtros de pantalla**: el resumen
        describe la planta, no la vista.
        """
        base = filtrar_por_scope(
            Recepcion.objects.all(), request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        )

        por_estado = {
            fila["estado"]: fila["n"]
            for fila in base.values("estado").annotate(n=Count("id"))
        }

        return Response({
            "por_estado": {
                estado: por_estado.get(estado, 0)
                for estado, _ in Recepcion.Estado.choices
            },
            "total": base.count(),
            # Sin silo asignado y ya aprobadas: es el trabajo pendiente que no
            # se deduce del estado solo.
            "liberadas_sin_silo": base.filter(
                estado=Recepcion.Estado.LIBERADA, silo__isnull=True
            ).count(),
            "liberadas_con_silo": base.filter(
                estado=Recepcion.Estado.LIBERADA, silo__isnull=False
            ).count(),
        })

    def perform_create(self, serializer):
        # Quien registra queda como operador si no se indicó otro: el dato es
        # para auditoría y teclearlo a mano solo lo hace menos fiable.
        extra = {}
        scope = scope_de(self.request.user, requerido=True)
        sucursal = serializer.validated_data.get("sucursal")
        if scope.es_sucursal:
            sucursal = Sucursal.objects.get(pk=scope.sucursal_id)
        elif sucursal is None:
            raise DRFValidationError({"sucursal": "Debes indicar una sucursal permitida."})
        exigir_sucursal_permitida(self.request.user, sucursal)

        carga = serializer.validated_data.get("carga_recoleccion")
        if carga:
            extra["vehiculo"] = carga.recoleccion.parada.ruta.vehiculo
            extra["modulo"] = carga.modulo

        if serializer.validated_data.get("operador") is None:
            extra["operador"] = self.request.user

        serializer.save(sucursal=sucursal, estado=Recepcion.Estado.REGISTRADA, **extra)

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"], url_path="tomar-muestra")
    def tomar_muestra(self, request, pk=None):
        """Identifica la muestra del módulo y lo entrega a la cola de Calidad."""
        codigo = str(request.data.get("codigo_muestra", "")).strip()
        if not codigo:
            return Response(
                {"codigo_muestra": "Debes identificar la muestra."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            recepcion = Recepcion.objects.select_for_update().get(pk=self.get_object().pk)
            if recepcion.estado != Recepcion.Estado.REGISTRADA:
                return Response(
                    {"detail": "Solo una recepción en espera puede ser muestreada."},
                    status=status.HTTP_409_CONFLICT,
                )
            if Recepcion.objects.exclude(pk=recepcion.pk).filter(codigo_muestra=codigo).exists():
                return Response(
                    {"codigo_muestra": "Este código de muestra ya está en uso."},
                    status=status.HTTP_409_CONFLICT,
                )

            recepcion.codigo_muestra = codigo
            recepcion.muestreado_por = request.user
            recepcion.muestreado_en = timezone.now()
            recepcion.estado = Recepcion.Estado.MUESTREADA
            recepcion.save(
                update_fields=["codigo_muestra", "muestreado_por", "muestreado_en", "estado"]
            )

        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"], url_path="decidir-calidad")
    def decidir_calidad(self, request, pk=None):
        """Registra los resultados y deja el módulo aprobado o retenido."""
        controles = request.data.get("controles")
        if not isinstance(controles, dict):
            return Response(
                {"controles": "Debes informar los controles de la muestra."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            controles = RecepcionSerializer().validate_controles(controles)
        except DRFValidationError as error:
            return Response({"controles": error.detail}, status=status.HTTP_400_BAD_REQUEST)

        evaluacion = dominio.evaluar_recepcion(controles)
        decision_manual = request.data.get("decision")
        motivo_manual = str(request.data.get("motivo", "")).strip()

        if decision_manual == "retener" and not motivo_manual:
            return Response(
                {"motivo": "Una retención manual debe indicar el motivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if decision_manual != "retener" and not evaluacion.analizada:
            return Response(
                {"controles": f"Falta completar: {', '.join(evaluacion.faltantes)}."},
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            recepcion = Recepcion.objects.select_for_update().get(pk=self.get_object().pk)
            if recepcion.estado not in (Recepcion.Estado.MUESTREADA, Recepcion.Estado.RETENIDA):
                return Response(
                    {"detail": "La recepción debe estar muestreada para decidir su calidad."},
                    status=status.HTTP_409_CONFLICT,
                )

            retenida = decision_manual == "retener" or not evaluacion.liberable
            recepcion.controles = controles
            recepcion.estado = (
                Recepcion.Estado.RETENIDA if retenida else Recepcion.Estado.LIBERADA
            )
            recepcion.motivo = motivo_manual or (
                " · ".join(evaluacion.motivos) if retenida else ""
            )
            recepcion.calidad_por = request.user
            recepcion.calidad_en = timezone.now()
            recepcion.save(
                update_fields=[
                    "controles",
                    "estado",
                    "motivo",
                    "calidad_por",
                    "calidad_en",
                ]
            )

        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"], url_path="asignar-silo")
    def asignar_silo(self, request, pk=None):
        """Asigna el destino solo después de la aprobación de Calidad."""
        try:
            silo = filtrar_por_scope(
                Silo.objects.filter(activo=True), request.user,
                campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            ).get(pk=request.data.get("silo"))
        except (Silo.DoesNotExist, TypeError, ValueError):
            return Response(
                {"silo": "Selecciona un silo activo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            recepcion = Recepcion.objects.select_for_update().get(pk=self.get_object().pk)
            if recepcion.estado != Recepcion.Estado.LIBERADA:
                return Response(
                    {"detail": "El silo se asigna solo después de la aprobación de Calidad."},
                    status=status.HTTP_409_CONFLICT,
                )
            if silo.sucursal_id != recepcion.vehiculo.sucursal_id:
                return Response(
                    {"silo": "El silo debe pertenecer a la sucursal de la recepción."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            tipo_esperado = (
                Silo.Tipo.TK_LD
                if recepcion.tipo_leche == Recepcion.TipoLeche.DESCREMADA
                else Silo.Tipo.SILO
            )
            if silo.tipo != tipo_esperado:
                etiqueta = (
                    "TK de leche descremada"
                    if tipo_esperado == Silo.Tipo.TK_LD
                    else "silo de leche entera"
                )
                return Response(
                    {"silo": f"Esta carga requiere un {etiqueta}."},
                    status=status.HTTP_409_CONFLICT,
                )

            recepcion.silo = silo
            recepcion.silo_asignado_por = request.user
            recepcion.silo_asignado_en = timezone.now()
            recepcion.save(
                update_fields=["silo", "silo_asignado_por", "silo_asignado_en"]
            )

        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"])
    def descargar(self, request, pk=None):
        """
        Descarga la recepción al silo.

        Es lo que convierte una recepción en litros dentro de un silo: crea el
        asiento de ingreso en el libro mayor. Se hace en una transacción junto
        al cambio de estado, porque una descarga sin su movimiento dejaría el
        saldo del silo mintiendo.
        """
        with transaction.atomic():
            # `of=("self",)` acota el bloqueo a la fila de la recepción. Sin
            # eso PostgreSQL rechaza la consulta entera —«FOR UPDATE no puede
            # ser aplicado al lado nulable de un outer join»—: `silo` es
            # nulable, así que `select_related` genera un LEFT JOIN y no hay
            # fila que bloquear cuando la recepción todavía no tiene silo.
            #
            # Y aunque se pudiera, no se querría: el silo se bloquea aparte,
            # unas líneas más abajo, que es donde de verdad hace falta.
            recepcion = (
                Recepcion.objects.select_for_update(of=("self",))
                .select_related("silo")
                .get(pk=self.get_object().pk)
            )
            movimiento_existente = MovimientoSilo.objects.filter(
                origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
                origen_id=recepcion.id,
            ).first()
            if movimiento_existente:
                if recepcion.estado != Recepcion.Estado.DESCARGADA:
                    recepcion.estado = Recepcion.Estado.DESCARGADA
                    recepcion.save(update_fields=["estado"])
                return Response(self.get_serializer(recepcion).data)

            if recepcion.silo_id is None:
                return Response(
                    {"detail": "La recepción no tiene silo de destino asignado."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not recepcion.puede_pasar_a(Recepcion.Estado.DESCARGADA):
                return Response(
                    {"detail": f"Una recepción {recepcion.get_estado_display().lower()} no puede descargarse. Debe estar liberada."},
                    status=status.HTTP_409_CONFLICT,
                )

            silo = Silo.objects.select_for_update().get(pk=recepcion.silo_id)
            ocupacion_actual = MovimientoSilo.objects.filter(silo=silo).aggregate(
                total=Coalesce(
                    Sum(Case(
                        When(tipo=MovimientoSilo.Tipo.SALIDA, then=-F("litros")),
                        default=F("litros"),
                        output_field=DecimalField(max_digits=14, decimal_places=2),
                    )),
                    Value(0),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )["total"]
            if ocupacion_actual + recepcion.litros > silo.capacidad_l:
                disponible = silo.capacidad_l - ocupacion_actual
                return Response(
                    {"detail": f"El silo {silo.codigo} no tiene capacidad suficiente. Disponible: {disponible} L."},
                    status=status.HTTP_409_CONFLICT,
                )

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


class MovimientoSiloViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "silo__sucursal_id"
    tenant_lookup_empresa = "silo__sucursal__empresa_id"
    tenant_relation_fields = {"silo": ("sucursal_id", "sucursal__empresa_id")}
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
    silos = filtrar_por_scope(
        Silo.objects.filter(activo=True), request.user,
        campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ).annotate(
        litros_ocupados=Coalesce(
            Sum(Case(
                When(movimientos__tipo=MovimientoSilo.Tipo.SALIDA, then=-F("movimientos__litros")),
                default=F("movimientos__litros"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )),
            Value(0),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )
    ocupaciones = []
    for silo in silos:
        porcentaje = (
            silo.litros_ocupados / silo.capacidad_l * 100
            if silo.capacidad_l
            else 0
        )
        ocupaciones.append({
            "silo_id": silo.id,
            "codigo": silo.codigo,
            "litros": silo.litros_ocupados,
            "capacidad": silo.capacidad_l,
            "pct": round(porcentaje, 1),
            "excedido": silo.litros_ocupados > silo.capacidad_l,
            "negativo": silo.litros_ocupados < 0,
        })

    return Response(
        {
            "silos": ocupaciones,
            "litros_totales": sum(o["litros"] for o in ocupaciones),
            "alertas": {
                "excedidos": [o["codigo"] for o in ocupaciones if o["excedido"]],
                "negativos": [o["codigo"] for o in ocupaciones if o["negativo"]],
            },
        }
    )
