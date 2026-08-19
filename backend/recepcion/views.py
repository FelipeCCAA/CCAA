import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Max, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from maestros.models import Silo
from usuarios.areas import perfiles_del_area, usuarios_del_area
from usuarios.permisos import DecideCalidadRecepcion, EscribeRecepcion
from usuarios.models import PerfilUsuario, Rol
from usuarios.tenancy import (
    QuerysetTenantMixin, RelacionesTenantMixin,
    filtrar_por_scope, scope_de, sucursal_para_escritura,
)

from . import dominio
from .models import BusquedaProveedor, MovimientoSilo, Recepcion
from .serializers import (
    AjusteSiloSerializer, MovimientoSiloSerializer, RecepcionSerializer,
    TransferenciaSiloSerializer,
)
from .servicios import ajustar_silo, transferir_silo


def _usuarios_recepcion(usuario):
    """Quién puede figurar como responsable de una muestra."""
    return usuarios_del_area(
        PerfilUsuario.Area.RECEPCION,
        empresa_id=scope_de(usuario, requerido=True).empresa_id,
    ).order_by("first_name", "last_name", "username")


def _notificar_recepcion(recepcion, *, tipo, titulo, mensaje, areas):
    """
    Crea avisos operativos solo para la misma empresa.

    Pregunta **lo mismo** que `_usuarios_recepcion`. Cuando cada una lo
    preguntaba a su manera —una miraba `area` o `rol`, esta solo `area`— una
    persona podía aparecer en el desplegable de responsables y no recibir nunca
    un aviso; en la base de desarrollo, donde ningún perfil tiene área cargada,
    la lista de destinatarios salía **vacía siempre** y las notificaciones no
    llegaban a nadie sin que nada fallara.
    """
    from inventario.models import Notificacion

    destinatarios = set()

    for area in areas:
        destinatarios.update(
            perfiles_del_area(
                area,
                empresa_id=recepcion.sucursal.empresa_id,
            ).values_list("usuario_id", flat=True)
        )
    Notificacion.objects.bulk_create([
        Notificacion(
            destinatario_id=usuario_id,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje,
            documento_tipo="recepcion_leche",
            documento_id=recepcion.id,
        )
        for usuario_id in destinatarios
    ])


class RecepcionViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "sucursal_id"
    tenant_lookup_empresa = "sucursal__empresa_id"
    tenant_relation_fields = {
        "vehiculo": ("sucursal_id", "sucursal__empresa_id"),
        "silo": ("sucursal_id", "sucursal__empresa_id"),
    }
    queryset = Recepcion.objects.select_related(
        "vehiculo",
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
        sucursal = sucursal_para_escritura(self.request.user, serializer.validated_data)

        if serializer.validated_data.get("operador") is None:
            extra["operador"] = self.request.user

        recepcion = serializer.save(
            sucursal=sucursal, estado=Recepcion.Estado.REGISTRADA, **extra
        )
        _notificar_recepcion(
            recepcion,
            tipo="leche_recepcionada",
            titulo="Leche recepcionada",
            mensaje=(
                f"Se recibieron {recepcion.litros} L del camion "
                f"{recepcion.vehiculo.placa if recepcion.vehiculo else 'sin patente'}."
            ),
            areas=[PerfilUsuario.Area.RECEPCION],
        )

    def perform_update(self, serializer):
        serializer.save()

    @action(detail=False, methods=["post"], url_path="registrar-llegada")
    def registrar_llegada(self, request):
        """
        Registra los camiones de una llegada.

        Versión mínima: cada elemento de `modulos` crea su propia `Recepcion`,
        sin identificador compartido — ya no existe `llegada_id`. La Task 7
        rediseña este contrato para que un camión sea un único registro con
        sus `ModuloRecepcion` (crioscopía por compartimiento).
        """
        modulos = request.data.get("modulos")
        if not isinstance(modulos, list) or not modulos:
            return Response(
                {"modulos": "Agrega al menos un modulo o compartimiento."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # La misma resolución que el resto de las escrituras. Resolverla aquí a
        # mano volvía a exigirle la planta a quien administra —el formulario no
        # tiene ese campo— y respondía el mismo 400 que se corrigió en 92513e8.
        sucursal = sucursal_para_escritura(request.user, {})

        generales = {
            clave: request.data.get(clave)
            for clave in (
                "fecha", "hora", "guia", "vehiculo", "procedencia",
                "tipo_leche", "turno", "observacion",
            )
            if request.data.get(clave) not in (None, "")
        }
        serializers = []
        for item in modulos:
            datos = {**generales, "sucursal": sucursal.id, "litros": item.get("litros")}
            serializer = self.get_serializer(data=datos)
            serializer.is_valid(raise_exception=True)
            serializers.append(serializer)

        with transaction.atomic():
            recepciones = [
                serializer.save(
                    sucursal=sucursal,
                    operador=request.user,
                    estado=Recepcion.Estado.REGISTRADA,
                )
                for serializer in serializers
            ]
            total = sum((recepcion.litros for recepcion in recepciones), 0)
            primera = recepciones[0]
            _notificar_recepcion(
                primera,
                tipo="leche_recepcionada",
                titulo="Camion de leche recepcionado",
                mensaje=(
                    f"Se recibieron {total} L en {len(recepciones)} registro(s) del "
                    f"camion {primera.vehiculo.placa if primera.vehiculo else 'sin patente'}."
                ),
                areas=[PerfilUsuario.Area.RECEPCION],
            )

        return Response(
            self.get_serializer(recepciones, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="tomar-muestra")
    def tomar_muestra(self, request, pk=None):
        """Identifica la muestra del módulo y lo entrega a la cola de Calidad."""
        codigo = str(request.data.get("codigo_muestra", "")).strip()
        if not codigo:
            return Response(
                {"codigo_muestra": "Debes identificar la muestra."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        responsable_id = request.data.get("responsable") or request.user.id

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

            try:
                responsable = _usuarios_recepcion(request.user).get(pk=responsable_id)
            except (User.DoesNotExist, TypeError, ValueError):
                return Response(
                    {"responsable": "Selecciona un usuario activo del area Recepcion."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            recepcion.codigo_muestra = codigo
            recepcion.muestreado_por = responsable
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

        decision_manual = request.data.get("decision")
        motivo_manual = str(request.data.get("motivo", "")).strip()

        if decision_manual == "retener" and not motivo_manual:
            return Response(
                {"motivo": "Una retención manual debe indicar el motivo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            recepcion = Recepcion.objects.select_for_update().get(pk=self.get_object().pk)
            if recepcion.estado not in (Recepcion.Estado.MUESTREADA, Recepcion.Estado.RETENIDA):
                return Response(
                    {"detail": "La recepción debe estar muestreada para decidir su calidad."},
                    status=status.HTTP_409_CONFLICT,
                )

            evaluacion = dominio.evaluar_recepcion(controles)
            if decision_manual != "retener" and not evaluacion.analizada:
                return Response(
                    {"controles": f"Falta completar: {', '.join(evaluacion.faltantes)}."},
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

            _notificar_recepcion(
                recepcion,
                tipo="leche_disponible_estandarizacion",
                titulo=f"Leche disponible en {silo.codigo}",
                mensaje=(
                    f"Recepcion confirmada: {recepcion.litros} L quedaron en "
                    f"{silo.codigo} y ya pueden seleccionarse en Estandarizacion."
                ),
                areas=[PerfilUsuario.Area.RECEPCION, PerfilUsuario.Area.CONDENSACION],
            )

        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        """
        Cierra la recepción.

        Un positivo de inhibidores no basta con retener: antes de cerrar tiene
        que estar registrada la búsqueda al proveedor. Es el primer eslabón de
        la cadena de `REGLAS_DE_PLANTA.md` §1.2, que hasta ahora no existía.
        """
        with transaction.atomic():
            # Se relee con bloqueo de fila (mismo `of=("self",)` que
            # `descargar`, más abajo): la decisión de cerrar se toma sobre
            # los controles y el estado que se leen aquí, y sin el bloqueo
            # `decidir-calidad` podría cambiarlos en el medio — el cierre
            # quedaría resuelto contra un estado que ya no es el vigente.
            recepcion = Recepcion.objects.select_for_update(of=("self",)).get(
                pk=self.get_object().pk
            )

            busquedas = BusquedaProveedor.objects.filter(
                control__recepcion=recepcion
            ).count()

            bloqueos = dominio.bloqueos_de_cierre(
                recepcion.controles, busquedas_a_proveedor=busquedas
            )

            if bloqueos:
                return Response(
                    {"bloqueos": bloqueos}, status=status.HTTP_400_BAD_REQUEST
                )

            if not recepcion.puede_pasar_a(Recepcion.Estado.CERRADA):
                return Response(
                    {
                        "estado": (
                            f"Una recepción {recepcion.get_estado_display()} no puede "
                            "cerrarse."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            recepcion.estado = Recepcion.Estado.CERRADA
            recepcion.save(update_fields=["estado"])

        return Response(self.get_serializer(recepcion).data)

    @action(detail=False, methods=["get"], url_path="catalogos-flujo")
    def catalogos_flujo(self, request):
        usuarios = _usuarios_recepcion(request.user)
        return Response({
            "responsables_recepcion": [
                {
                    "id": usuario.id,
                    "nombre": usuario.get_full_name().strip() or usuario.username,
                    "turno": usuario.perfil.turno,
                }
                for usuario in usuarios.select_related("perfil")
            ],
        })


class MovimientoSiloViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    tenant_lookup_sucursal = "silo__sucursal_id"
    tenant_lookup_empresa = "silo__sucursal__empresa_id"
    tenant_relation_fields = {"silo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = MovimientoSilo.objects.select_related(
        "silo", "silo_contraparte", "lote", "producto", "equipo", "usuario"
    )
    serializer_class = MovimientoSiloSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset()

        silo = self.request.query_params.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)

        return consulta

    def update(self, request, *args, **kwargs):
        return Response(
            {"detail": "El libro mayor es inmutable; registra un ajuste o reversa."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {"detail": "Los movimientos de silo no se eliminan."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def create(self, request, *args, **kwargs):
        """Compatibilidad: POST directo solo registra ajustes auditables."""
        if request.data.get("tipo") != MovimientoSilo.Tipo.AJUSTE:
            return Response(
                {"tipo": ["Ingresos y salidas solo se generan desde operaciones de dominio."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        datos = request.data.copy()
        datos.setdefault("operacion_id", str(uuid.uuid4()))
        entrada = AjusteSiloSerializer(data=datos)
        entrada.is_valid(raise_exception=True)
        return self._ejecutar_ajuste(entrada.validated_data)

    @action(detail=False, methods=["post"])
    def ajustar(self, request):
        entrada = AjusteSiloSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return self._ejecutar_ajuste(entrada.validated_data)

    def _ejecutar_ajuste(self, datos):
        silos = filtrar_por_scope(
            Silo.objects.all(), self.request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        if not silos.filter(pk=datos["silo"]).exists():
            raise DRFValidationError({"silo": "Silo inexistente o fuera de tu planta."})
        try:
            movimiento = ajustar_silo(
                silo_id=datos["silo"], litros=datos["litros"],
                operacion_id=datos["operacion_id"], usuario=self.request.user,
                motivo=datos["motivo"],
            )
        except Exception as error:
            if hasattr(error, "message_dict"):
                raise DRFValidationError(error.message_dict) from error
            if hasattr(error, "messages"):
                raise DRFValidationError(error.messages) from error
            raise
        return Response(MovimientoSiloSerializer(movimiento).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def transferir(self, request):
        entrada = TransferenciaSiloSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        silos = filtrar_por_scope(
            Silo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        if silos.filter(pk__in=[datos["silo_origen"], datos["silo_destino"]]).count() != 2:
            raise DRFValidationError("Los silos deben pertenecer a tu planta.")

        from maestros.models import Equipo, Producto
        from produccion.models import Lote

        scope = scope_de(request.user, requerido=True)
        filtro_sucursal = {"sucursal_id": scope.sucursal_id} if scope.es_sucursal else {
            "sucursal__empresa_id": scope.empresa_id
        }
        lote = Lote.objects.filter(pk=datos.get("lote"), **filtro_sucursal).first() if datos.get("lote") else None
        producto = Producto.objects.filter(
            pk=datos.get("producto"), mandante__empresa_id=scope.empresa_id
        ).first() if datos.get("producto") else None
        equipo = Equipo.objects.filter(pk=datos.get("equipo"), **filtro_sucursal).first() if datos.get("equipo") else None
        if datos.get("lote") and lote is None:
            raise DRFValidationError({"lote": "Lote inexistente o fuera de tu planta."})
        if datos.get("producto") and producto is None:
            raise DRFValidationError({"producto": "Producto inexistente o fuera de tu empresa."})
        if datos.get("equipo") and equipo is None:
            raise DRFValidationError({"equipo": "Equipo inexistente o fuera de tu planta."})
        try:
            movimientos = transferir_silo(
                silo_origen_id=datos["silo_origen"],
                silo_destino_id=datos["silo_destino"], litros=datos["litros"],
                operacion_id=datos["operacion_id"], usuario=request.user,
                motivo=datos["motivo"], lote=lote, producto=producto, equipo=equipo,
            )
        except Exception as error:
            if hasattr(error, "message_dict"):
                raise DRFValidationError(error.message_dict) from error
            if hasattr(error, "messages"):
                raise DRFValidationError(error.messages) from error
            raise
        return Response(
            MovimientoSiloSerializer(movimientos, many=True).data,
            status=status.HTTP_201_CREATED,
        )


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
        Silo.objects.filter(activo=True).select_related("producto_actual"), request.user,
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
        ),
        ultimo_movimiento=Max("movimientos__fecha_hora"),
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
            "estado": silo.estado,
            "estado_etiqueta": silo.get_estado_display(),
            "producto_actual": silo.producto_actual.nombre if silo.producto_actual else None,
            "temperatura_actual": silo.temperatura_actual,
            "ultima_limpieza": silo.ultima_limpieza,
            "ultimo_movimiento": silo.ultimo_movimiento,
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
