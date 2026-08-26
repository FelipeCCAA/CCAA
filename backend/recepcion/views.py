import csv
import uuid
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Case, Count, DecimalField, F, Max, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
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
from .models import (
    CONTROLES_DECLARADOS, AlertaCalidadSilo, AnalisisSilo, BusquedaProveedor,
    AtribucionRecepcion, CorreccionRecepcion, ModuloRecepcion, MovimientoSilo, Recepcion,
    DespachoLeche,
)
from .serializers import (
    AjusteSiloSerializer, AnalisisSiloSerializer, CorreccionCrioscopiasSerializer,
    CrearDespachoLecheSerializer, DespachoLecheSerializer, ReversaDespachoLecheSerializer,
    MovimientoSiloSerializer, RecepcionSerializer, TransferenciaSiloSerializer,
)
from .servicios import (
    ajustar_silo, despachar_leche, momento_leche_mas_antigua, motivos_silo_no_disponible,
    reversar_despacho_leche,
    saldo_silo, transferir_silo,
)


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
    ).prefetch_related(
        "modulos",
        # `crioscopia_pool`, `diferencia_recoleccion_litros` y `get_evaluacion`
        # recorren `modulos` por fila; sin este prefetch, exponerlas en el
        # serializer dispara una consulta por recepción (N+1) al listar.
        "controles_inhibidores__busquedas",
        "alertas_calidad_silo",
    )
    serializer_class = RecepcionSerializer
    permission_classes = [EscribeRecepcion]

    def get_permissions(self):
        if self.action == "decidir_calidad":
            return [DecideCalidadRecepcion()]
        return super().get_permissions()

    @action(detail=True, methods=["get"])
    def destino(self, request, pk=None):
        """Movimientos posteriores en que aparece leche de esta recepción."""
        recepcion = self.get_object()
        atribuciones = (
            AtribucionRecepcion.objects.filter(
                recepcion=recepcion,
                movimiento__tipo=MovimientoSilo.Tipo.SALIDA,
            )
            .select_related("movimiento__silo", "movimiento__lote")
            .order_by("movimiento__fecha_hora", "orden")
        )
        destinos = []
        for item in atribuciones:
            movimiento = item.movimiento
            destinos.append({
                "movimiento_id": movimiento.id,
                "fecha_hora": movimiento.fecha_hora,
                "litros": item.litros,
                "silo": movimiento.silo.codigo,
                "origen_tipo": movimiento.origen_tipo,
                "lote": (
                    {"id": movimiento.lote_id, "codigo": movimiento.lote.codigo_lote}
                    if movimiento.lote_id else None
                ),
                "porcentaje_movimiento": (
                    item.litros * 100 / movimiento.litros
                ).quantize(Decimal("0.01")),
            })
        return Response({
            "recepcion_id": recepcion.id,
            "litros_atribuidos": sum(
                (item.litros for item in atribuciones), Decimal("0")
            ),
            "destinos": destinos,
        })

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
            if Recepcion.Estado.BORRADOR in estados:
                consulta = consulta.filter(abierto_por=self.request.user)
        else:
            consulta = consulta.exclude(
                estado__in=[Recepcion.Estado.BORRADOR, Recepcion.Estado.ANULADA]
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
            Recepcion.objects.exclude(
                estado__in=[Recepcion.Estado.BORRADOR, Recepcion.Estado.ANULADA]
            ), request.user,
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

    def update(self, request, *args, **kwargs):
        recepcion = self.get_object()
        if recepcion.estado in {Recepcion.Estado.CERRADA, Recepcion.Estado.ANULADA}:
            return Response(
                {"detail": "El documento está cerrado y ya no admite edición."},
                status=status.HTTP_409_CONFLICT,
            )
        if "litros" in request.data and MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
            origen_id=recepcion.id,
        ).exists():
            return Response(
                {
                    "litros": (
                        "Los litros ya movieron el saldo del silo. Corrígelos "
                        "mediante un ajuste con motivo, no editando la recepción."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().update(request, *args, **kwargs)

    def _borrador_del_usuario(self, request, pk=None):
        consulta = filtrar_por_scope(
            Recepcion.objects.select_related("vehiculo", "silo").prefetch_related(
                "modulos", "controles_inhibidores__busquedas"
            ),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        ).filter(estado=Recepcion.Estado.BORRADOR, abierto_por=request.user)
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
                    "detail": "Ya tienes un borrador de recepción abierto.",
                    "borrador": self.get_serializer(existente).data,
                },
                status=status.HTTP_409_CONFLICT,
            )

        datos = {
            clave: valor for clave, valor in request.data.items()
            if clave != "modulos" and valor not in (None, "")
        }
        serializer = self.get_serializer(data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            recepcion = serializer.save(
                sucursal=sucursal_para_escritura(request.user, {}),
                operador=request.user,
                abierto_por=request.user,
                abierto_en=timezone.now(),
                estado=Recepcion.Estado.BORRADOR,
                fecha=serializer.validated_data.get("fecha", timezone.localdate()),
                tipo_leche=serializer.validated_data.get(
                    "tipo_leche", Recepcion.TipoLeche.ENTERA
                ),
                litros=serializer.validated_data.get("litros", Decimal("0")),
            )
            self._guardar_modulos_borrador(
                recepcion, request.data.get("modulos", [])
            )
        return Response(self.get_serializer(recepcion).data, status=status.HTTP_201_CREATED)

    def _guardar_modulos_borrador(self, recepcion, modulos):
        if not isinstance(modulos, list):
            raise DRFValidationError({"modulos": "Debe ser una lista."})
        numeros = [item.get("numero") for item in modulos if isinstance(item, dict)]
        if len(numeros) != len(modulos) or any(
            not isinstance(numero, int) or numero < 1 or numero > 4
            for numero in numeros
        ) or len(set(numeros)) != len(numeros):
            raise DRFValidationError(
                {"modulos": "Usa números únicos de módulo entre 1 y 4."}
            )
        recepcion.modulos.all().delete()
        ModuloRecepcion.objects.bulk_create([
            ModuloRecepcion(
                recepcion=recepcion,
                numero=item["numero"],
                crioscopia=item.get("crioscopia") or None,
                carga_recoleccion_id=item.get("carga_recoleccion") or None,
            )
            for item in modulos
        ])

    @action(detail=True, methods=["patch"], url_path="guardar-borrador")
    def guardar_borrador(self, request, pk=None):
        recepcion = self._borrador_del_usuario(request, pk)
        if recepcion is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        datos = {clave: valor for clave, valor in request.data.items() if clave != "modulos"}
        serializer = self.get_serializer(recepcion, data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            recepcion = serializer.save()
            if "modulos" in request.data:
                self._guardar_modulos_borrador(recepcion, request.data["modulos"])
        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"], url_path="confirmar-borrador")
    def confirmar_borrador(self, request, pk=None):
        recepcion = self._borrador_del_usuario(request, pk)
        if recepcion is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        motivos = recepcion.confirmar(request.user)
        if motivos:
            return Response({"motivos": motivos}, status=status.HTTP_400_BAD_REQUEST)
        _notificar_recepcion(
            recepcion,
            tipo="leche_recepcionada",
            titulo="Camión de leche recepcionado",
            mensaje=(
                f"Se recibieron {recepcion.litros} L del camión "
                f"{recepcion.vehiculo.placa if recepcion.vehiculo else 'sin patente'}."
            ),
            areas=[PerfilUsuario.Area.RECEPCION],
        )
        return Response(self.get_serializer(recepcion).data)

    @action(detail=True, methods=["post"], url_path="descartar-borrador")
    def descartar_borrador(self, request, pk=None):
        recepcion = self._borrador_del_usuario(request, pk)
        if recepcion is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        recepcion.estado = Recepcion.Estado.ANULADA
        recepcion.save(update_fields=["estado", "actualizado_en"])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="registrar-llegada")
    def registrar_llegada(self, request):
        """
        Registra un camión: **un** registro, con sus módulos.

        Los litros, el silo y el destino son del camión. Lo único que baja al
        módulo es la crioscopía, que es lo único que el formato mide por
        compartimiento.
        """
        modulos = request.data.get("modulos")

        if not isinstance(modulos, list) or not modulos:
            return Response(
                {"modulos": "Declara al menos un compartimiento del camión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        numeros = [item.get("numero") for item in modulos if isinstance(item, dict)]

        if len(numeros) != len(modulos) or any(
            not isinstance(numero, int) or numero < 1 or numero > 4
            for numero in numeros
        ):
            return Response(
                {"modulos": "Cada módulo necesita su número (1 a 4)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(set(numeros)) != len(numeros):
            return Response(
                {"modulos": "No repitas el mismo número de módulo en el camión."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sucursal = sucursal_para_escritura(request.user, {})

        datos = {
            clave: valor
            for clave, valor in request.data.items()
            if clave != "modulos" and valor not in (None, "")
        }

        serializer = self.get_serializer(data=datos)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            recepcion = serializer.save(
                sucursal=sucursal,
                operador=request.user,
                estado=Recepcion.Estado.REGISTRADA,
            )

            for item in modulos:
                ModuloRecepcion.objects.create(
                    recepcion=recepcion,
                    numero=item["numero"],
                    crioscopia=item.get("crioscopia") or None,
                    carga_recoleccion_id=item.get("carga_recoleccion") or None,
                )

            _notificar_recepcion(
                recepcion,
                tipo="leche_recepcionada",
                titulo="Camion de leche recepcionado",
                mensaje=(
                    f"Se recibieron {recepcion.litros} L del camión "
                    f"{recepcion.vehiculo.placa if recepcion.vehiculo else 'sin patente'} "
                    f"en {len(modulos)} compartimiento(s)."
                ),
                areas=[PerfilUsuario.Area.RECEPCION],
            )

        return Response(
            self.get_serializer(recepcion).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["patch"], url_path="corregir-crioscopias")
    def corregir_crioscopias(self, request, pk=None):
        """Corrige un paso recorrido sin tocar litros ni movimientos de silo."""
        entrada = CorreccionCrioscopiasSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        with transaction.atomic():
            recepcion = Recepcion.objects.select_for_update().get(
                pk=self.get_object().pk
            )
            if recepcion.estado in {
                Recepcion.Estado.BORRADOR,
                Recepcion.Estado.CERRADA,
                Recepcion.Estado.ANULADA,
            }:
                return Response(
                    {
                        "detail": (
                            "Una recepción cerrada, anulada o todavía en borrador "
                            "no admite correcciones de pasos recorridos."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            modulos = {
                modulo.id: modulo
                for modulo in recepcion.modulos.select_for_update()
            }
            solicitados = entrada.validated_data["modulos"]
            ajenos = [item["id"] for item in solicitados if item["id"] not in modulos]
            if ajenos:
                return Response(
                    {"modulos": f"Los módulos {ajenos} no pertenecen a esta recepción."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            evaluacion_antes = recepcion.evaluar()
            cambios = {}
            for item in solicitados:
                modulo = modulos[item["id"]]
                anterior = modulo.crioscopia
                nuevo = item["crioscopia"]
                if anterior == nuevo:
                    continue
                modulo.crioscopia = nuevo
                modulo.save(update_fields=["crioscopia"])
                cambios[f"M{modulo.numero}.crioscopia"] = [
                    str(anterior) if anterior is not None else None,
                    str(nuevo) if nuevo is not None else None,
                ]

            if not cambios:
                return Response(
                    {"modulos": "No hay cambios de crioscopía que guardar."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            evaluacion_despues = recepcion.evaluar()
            estado_anterior = recepcion.estado
            se_volvio_no_conforme = (
                evaluacion_antes.conforme and not evaluacion_despues.conforme
            )
            if se_volvio_no_conforme and estado_anterior in {
                Recepcion.Estado.LIBERADA,
                Recepcion.Estado.DESCARGADA,
            }:
                recepcion.estado = Recepcion.Estado.RETENIDA
                recepcion.motivo = " · ".join(evaluacion_despues.motivos)
                recepcion.calidad_por = request.user
                recepcion.calidad_en = timezone.now()
                recepcion.save(update_fields=[
                    "estado", "motivo", "calidad_por", "calidad_en",
                ])

            CorreccionRecepcion.objects.create(
                recepcion=recepcion,
                usuario=request.user,
                paso="llegada",
                motivo=entrada.validated_data["motivo"],
                cambios=cambios,
            )

            if (
                se_volvio_no_conforme
                and estado_anterior == Recepcion.Estado.DESCARGADA
                and recepcion.silo_id is not None
            ):
                detalle = (
                    f"La recepción {recepcion.id} cambió a no conforme tras "
                    f"corregir crioscopía: {' · '.join(evaluacion_despues.motivos)}"
                )
                AlertaCalidadSilo.objects.create(
                    recepcion=recepcion,
                    silo=recepcion.silo,
                    motivo=detalle,
                )
                _notificar_recepcion(
                    recepcion,
                    tipo="silo_afectado_por_correccion",
                    titulo=f"Revisar calidad de {recepcion.silo.codigo}",
                    mensaje=detalle,
                    areas=[PerfilUsuario.Area.CALIDAD, PerfilUsuario.Area.RECEPCION],
                )

        recepcion = self.queryset.get(pk=recepcion.pk)
        return Response(self.get_serializer(recepcion).data)

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

            ph_enviado = request.data.get("ph_camion", recepcion.ph_camion)
            ph_enviado = None if ph_enviado in (None, "") else Decimal(str(ph_enviado))
            if ph_enviado != recepcion.ph_camion:
                motivo_correccion = str(
                    request.data.get("motivo_correccion", "")
                ).strip()
                if len(motivo_correccion) < 5:
                    return Response(
                        {
                            "motivo_correccion": (
                                "Indica por qué corriges el pH del camión "
                                "(mínimo 5 caracteres)."
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                ph_enviado = RecepcionSerializer().fields[
                    "ph_camion"
                ].run_validation(ph_enviado)
                anterior = recepcion.ph_camion
                recepcion.ph_camion = ph_enviado
                recepcion.save(update_fields=["ph_camion"])
                CorreccionRecepcion.objects.create(
                    recepcion=recepcion,
                    usuario=request.user,
                    paso="calidad",
                    motivo=motivo_correccion,
                    cambios={
                        "ph_camion": [
                            str(anterior) if anterior is not None else None,
                            str(ph_enviado) if ph_enviado is not None else None,
                        ]
                    },
                )

            # `Recepcion.evaluar()` arma también la crioscopía de los módulos
            # y el pH del camión — llamar a `dominio.evaluar_recepcion`
            # directo aquí, sin esos dos argumentos, es la regresión que
            # dejó salir leche aguada o con el pH del camión fuera de rango:
            # la ficha mostraba el motivo (el serializer sí los pasa) pero el
            # estado que se guardaba no lo consideraba.
            evaluacion = recepcion.evaluar(controles)
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
            if silo.sucursal_id != recepcion.sucursal_id:
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
            bloqueos_silo = motivos_silo_no_disponible(silo, para="descarga")
            if bloqueos_silo:
                return Response(
                    {"motivos": bloqueos_silo}, status=status.HTTP_409_CONFLICT
                )
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

        def opciones(choices):
            return [{"valor": valor, "etiqueta": etiqueta} for valor, etiqueta in choices]

        return Response({
            "responsables_recepcion": [
                {
                    "id": usuario.id,
                    "nombre": usuario.get_full_name().strip() or usuario.username,
                    "turno": usuario.perfil.turno,
                }
                for usuario in usuarios.select_related("perfil")
            ],
            # Los catálogos se sirven desde aquí y no se escriben en el
            # frontend: una copia ofrece tarde o temprano un valor que el
            # backend rechaza.
            "usos": opciones(Recepcion.Uso.choices),
            "usos_numerados": list(Recepcion.USOS_NUMERADOS),
            "procedencias": opciones(Recepcion.Procedencia.choices),
            "recambios_dilucion": opciones(Recepcion.RecambioDilucion.choices),
            "controles": sorted(CONTROLES_DECLARADOS),
        })

    @action(detail=False, methods=["get"], url_path="resumen-diario")
    def resumen_diario(self, request):
        """
        Los totales que la planilla pone al pie: litros y kilos del día,
        reparto por silo y por procedencia, promedios de grasa y SNG, y las
        horas de sobreestadía.

        Las horas se suman en Python y no en SQL porque `permanencia` devuelve
        `None` cuando falta una marca horaria, y esa distinción —no medido
        contra cero— es justamente la que la planilla perdía.
        """
        fecha_texto = request.query_params.get("fecha")
        desde_texto = request.query_params.get("desde")
        hasta_texto = request.query_params.get("hasta")

        if fecha_texto and (desde_texto or hasta_texto):
            return Response(
                {"fecha": "Usa fecha o el rango desde/hasta, no ambos."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not fecha_texto and not (desde_texto and hasta_texto):
            return Response(
                {"fecha": "Indica fecha o un rango completo desde/hasta (AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def fecha_valida(texto):
            try:
                return parse_date(texto)
            except (TypeError, ValueError):
                return None

        desde = fecha_valida(fecha_texto or desde_texto)
        hasta = fecha_valida(fecha_texto or hasta_texto)
        if desde is None or hasta is None:
            valor = fecha_texto or f"{desde_texto} / {hasta_texto}"
            return Response(
                {"fecha": f"Fecha no reconocida: {valor!r} (usa AAAA-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if desde > hasta:
            return Response(
                {"fecha": "El inicio del rango no puede ser posterior al término."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        formato = request.query_params.get("formato", "json").lower()
        if formato not in {"json", "csv", "xlsx"}:
            return Response(
                {"formato": "Formato no reconocido. Usa json, csv o xlsx."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        base = filtrar_por_scope(
            Recepcion.objects.filter(
                fecha__range=(desde, hasta)
            ).exclude(
                estado__in=[Recepcion.Estado.BORRADOR, Recepcion.Estado.ANULADA]
            )
            .select_related("silo", "vehiculo")
            .prefetch_related("modulos"),
            request.user,
            campo_sucursal="sucursal_id",
            campo_empresa="sucursal__empresa_id",
        ).order_by("fecha", "hora", "id")

        recepciones = list(base)

        litros = sum((r.litros or Decimal("0") for r in recepciones), Decimal("0"))
        kg_guia = sum(
            (r.kg_guia or Decimal("0") for r in recepciones), Decimal("0")
        )

        # `kg_romana` es nulable: un camión sin pesar no aporta 0 kg de
        # romana, aporta NADA de romana. Sumarlo con `or Decimal("0")` — como
        # hacía esto antes — mezclaba ese cero con los kilos completos de su
        # guía en `diferencia_kg` y producía una diferencia que nadie midió
        # (el mismo defecto que las 254 horas fantasma, trasladado a la hoja
        # `Diferencia`). El total y la diferencia se calculan solo sobre los
        # camiones que sí tienen romana, y `camiones_sin_romana` informa
        # aparte cuántos quedaron fuera.
        con_romana = [r for r in recepciones if r.kg_romana is not None]
        kg_romana = sum((r.kg_romana for r in con_romana), Decimal("0"))
        diferencia_kg = (
            kg_romana - sum((r.kg_guia for r in con_romana), Decimal("0"))
            if con_romana
            else None
        )
        camiones_sin_romana = len(recepciones) - len(con_romana)

        por_silo = {}
        por_procedencia = {}
        for recepcion in recepciones:
            if recepcion.silo_id:
                clave = recepcion.silo.codigo
                por_silo[clave] = por_silo.get(clave, Decimal("0")) + recepcion.litros
            if recepcion.procedencia:
                por_procedencia[recepcion.procedencia] = (
                    por_procedencia.get(recepcion.procedencia, Decimal("0"))
                    + recepcion.litros
                )

        grasas = [
            r.controles.get("grasa") for r in recepciones
            if (r.controles or {}).get("grasa") is not None
        ]
        sngs = [
            r.controles.get("sng") for r in recepciones
            if (r.controles or {}).get("sng") is not None
        ]

        horas = [r.horas_a_pagar for r in recepciones]
        medidas = [h for h in horas if h is not None]

        detalle = [
            {
                "id": r.id,
                "fecha": r.fecha.isoformat(),
                "hora_arribo": (
                    (r.hora_arribo_porteria or r.hora).strftime("%H:%M")
                    if (r.hora_arribo_porteria or r.hora)
                    else None
                ),
                "guia": r.guia,
                "patente": r.vehiculo.placa if r.vehiculo_id else "",
                "procedencia": r.procedencia,
                "tipo_leche": r.tipo_leche,
                "litros": str(r.litros),
                "kg_guia": str(r.kg_guia),
                "kg_romana": str(r.kg_romana) if r.kg_romana is not None else None,
                "diferencia_kg": (
                    str(r.diferencia_kg) if r.diferencia_kg is not None else None
                ),
                "silo": r.silo.codigo if r.silo_id else "",
                "estado": r.estado,
                "estado_etiqueta": r.get_estado_display(),
                "crioscopias": [
                    {
                        "modulo": modulo.numero,
                        "valor": str(modulo.crioscopia)
                        if modulo.crioscopia is not None else None,
                    }
                    for modulo in r.modulos.all()
                ],
                "permanencia_horas": r.permanencia_horas,
                "permanencia_motivo": r.permanencia_motivo,
                "horas_a_pagar": r.horas_a_pagar,
            }
            for r in recepciones
        ]

        resumen = {
            "fecha": desde.isoformat() if desde == hasta else None,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
            "camiones": len(recepciones),
            "litros": str(litros),
            "kg_guia": str(kg_guia),
            "kg_romana": str(kg_romana),
            "diferencia_kg": str(diferencia_kg) if diferencia_kg is not None else None,
            "por_silo": {clave: str(valor) for clave, valor in por_silo.items()},
            "por_procedencia": {
                clave: str(valor) for clave, valor in por_procedencia.items()
            },
            "grasa_promedio": round(sum(grasas) / len(grasas), 2) if grasas else None,
            "sng_promedio": round(sum(sngs) / len(sngs), 2) if sngs else None,
            "horas_a_pagar": sum(medidas),
            # Cuántos camiones no se pudieron calcular. Sin esto el total
            # parecería completo aunque le falte la mitad de las marcas.
            "camiones_sin_marcas_horarias": len(horas) - len(medidas),
            # Mismo criterio que `camiones_sin_marcas_horarias`, para la
            # romana: sin este contador, un `kg_romana`/`diferencia_kg` bajo
            # parecería completo aunque la mitad de los camiones no se
            # pesaron.
            "camiones_sin_romana": camiones_sin_romana,
        }

        if formato == "json":
            if request.query_params.get("detalle") == "1":
                resumen["detalle"] = detalle
            return Response(resumen)

        nombre = (
            f"recepciones-{desde.isoformat()}"
            if desde == hasta
            else f"recepciones-{desde.isoformat()}-{hasta.isoformat()}"
        )
        columnas = [
            ("Fecha", "fecha"),
            ("Hora arribo", "hora_arribo"),
            ("Guía", "guia"),
            ("Patente", "patente"),
            ("Procedencia", "procedencia"),
            ("Tipo de leche", "tipo_leche"),
            ("Litros", "litros"),
            ("Kg guía", "kg_guia"),
            ("Kg romana", "kg_romana"),
            ("Diferencia kg", "diferencia_kg"),
            ("Silo", "silo"),
            ("Estado", "estado_etiqueta"),
            ("Crioscopías", "crioscopias_texto"),
            ("Permanencia horas", "permanencia_horas"),
            ("Horas a pagar", "horas_a_pagar"),
            ("Dato horario faltante", "permanencia_motivo"),
        ]
        filas = []
        for item in detalle:
            fila = dict(item)
            fila["crioscopias_texto"] = " · ".join(
                f"M{m['modulo']}: {m['valor'] if m['valor'] is not None else 'sin dato'}"
                for m in item["crioscopias"]
            )
            filas.append(fila)

        if formato == "csv":
            salida = StringIO()
            escritor = csv.writer(salida, delimiter=";")
            escritor.writerow([titulo for titulo, _ in columnas])
            escritor.writerows(
                [
                    [
                        fila.get(clave) if fila.get(clave) is not None else ""
                        for _, clave in columnas
                    ]
                    for fila in filas
                ]
            )
            respuesta = HttpResponse(
                "\ufeff" + salida.getvalue(), content_type="text/csv; charset=utf-8"
            )
            respuesta["Content-Disposition"] = f'attachment; filename="{nombre}.csv"'
            return respuesta

        from openpyxl import Workbook

        libro = Workbook()
        hoja = libro.active
        hoja.title = "Recepciones"
        hoja.append([titulo for titulo, _ in columnas])
        for fila in filas:
            hoja.append([
                fila.get(clave) if fila.get(clave) is not None else ""
                for _, clave in columnas
            ])
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = hoja.dimensions
        for columna in hoja.columns:
            largo = min(max(len(str(celda.value or "")) for celda in columna) + 2, 40)
            hoja.column_dimensions[columna[0].column_letter].width = largo

        totales = libro.create_sheet("Totales")
        for etiqueta, valor in [
            ("Desde", resumen["desde"]),
            ("Hasta", resumen["hasta"]),
            ("Camiones", resumen["camiones"]),
            ("Litros", resumen["litros"]),
            ("Kg guía", resumen["kg_guia"]),
            ("Kg romana", resumen["kg_romana"]),
            ("Diferencia kg", resumen["diferencia_kg"]),
            ("Horas a pagar", resumen["horas_a_pagar"]),
            ("Camiones sin romana", resumen["camiones_sin_romana"]),
            ("Camiones sin marcas horarias", resumen["camiones_sin_marcas_horarias"]),
        ]:
            totales.append([etiqueta, valor if valor is not None else ""])
        contenido = BytesIO()
        libro.save(contenido)
        respuesta = HttpResponse(
            contenido.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
        return respuesta


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
    from recepcion.servicios import momento_leche_mas_antigua, motivos_silo_no_disponible

    ocupaciones = []
    for silo in silos:
        analisis = AnalisisSilo.objects.filter(
            silo=silo, estado=AnalisisSilo.Estado.CONFIRMADO
        ).order_by("-tomado_en", "-id").first()
        vigencia = analisis.vigencia if analisis else None
        leche_mas_antigua_en = momento_leche_mas_antigua(silo)
        motivos = motivos_silo_no_disponible(silo, para="proceso")
        porcentaje = (
            silo.litros_ocupados / silo.capacidad_l * 100
            if silo.capacidad_l
            else 0
        )
        ocupaciones.append({
            "silo_id": silo.id,
            "codigo": silo.codigo,
            "tipo": silo.tipo,
            "tipo_etiqueta": silo.get_tipo_display(),
            "litros": silo.litros_ocupados,
            "capacidad": silo.capacidad_l,
            "estado": silo.estado,
            "estado_etiqueta": silo.get_estado_display(),
            "producto_actual": silo.producto_actual.nombre if silo.producto_actual else None,
            "temperatura_actual": silo.temperatura_actual,
            "ultima_limpieza": silo.ultima_limpieza,
            "ultimo_movimiento": silo.ultimo_movimiento,
            "leche_mas_antigua_en": leche_mas_antigua_en,
            "antiguedad_horas": (
                round((timezone.now() - leche_mas_antigua_en).total_seconds() / 3600, 1)
                if leche_mas_antigua_en else None
            ),
            "analisis": analisis.pk if analisis else None,
            "analisis_tomado_en": analisis.tomado_en if analisis else None,
            "grasa": analisis.grasa if analisis else None,
            "sng": analisis.sng if analisis else None,
            "analisis_vigente": vigencia.vigente if vigencia else False,
            "motivo_vigencia": vigencia.motivo if vigencia else "Sin análisis confirmado.",
            "motivos_no_disponible": motivos,
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


class DespachoLecheViewSet(
    RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet
):
    tenant_lookup_sucursal = "silo__sucursal_id"
    tenant_lookup_empresa = "silo__sucursal__empresa_id"
    tenant_relation_fields = {"silo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = DespachoLeche.objects.select_related(
        "silo", "liberacion_analisis", "responsable", "movimiento"
    )
    serializer_class = DespachoLecheSerializer
    permission_classes = [EscribeRecepcion]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        entrada = CrearDespachoLecheSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        silos = filtrar_por_scope(
            Silo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
        if not silos.filter(pk=datos["silo"]).exists():
            raise DRFValidationError({"silo": "Silo inexistente o fuera de tu planta."})
        try:
            despacho = despachar_leche(
                silo_id=datos.pop("silo"), usuario=request.user, **datos
            )
        except Exception as error:
            if hasattr(error, "message_dict"):
                raise DRFValidationError(error.message_dict) from error
            if hasattr(error, "messages"):
                raise DRFValidationError(error.messages) from error
            raise
        return Response(self.get_serializer(despacho).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def reversar(self, request, pk=None):
        entrada = ReversaDespachoLecheSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            despacho = reversar_despacho_leche(
                despacho_id=self.get_object().pk, usuario=request.user,
                **entrada.validated_data,
            )
        except Exception as error:
            if hasattr(error, "message_dict"):
                raise DRFValidationError(error.message_dict) from error
            if hasattr(error, "messages"):
                raise DRFValidationError(error.messages) from error
            raise
        return Response(self.get_serializer(despacho).data)


class AnalisisSiloViewSet(RelacionesTenantMixin, QuerysetTenantMixin, viewsets.ModelViewSet):
    """
    El análisis del silo — `CCAA.REC.FORM.005.01`.

    `?vigentes=1` filtra en Python y no en la base: la vigencia se decide
    contra el libro de movimientos, y expresarla como consulta duplicaría en
    SQL una regla que ya está en el dominio. Con ocho silos el costo es nulo
    y la regla sigue teniendo una sola implementación.
    """

    tenant_lookup_sucursal = "silo__sucursal_id"
    tenant_lookup_empresa = "silo__sucursal__empresa_id"
    tenant_relation_fields = {"silo": ("sucursal_id", "sucursal__empresa_id")}
    queryset = AnalisisSilo.objects.select_related(
        "silo", "analista", "visualizado_por"
    )


    serializer_class = AnalisisSiloSerializer
    permission_classes = [EscribeRecepcion]

    def get_queryset(self):
        consulta = super().get_queryset().exclude(
            estado__in=[AnalisisSilo.Estado.BORRADOR, AnalisisSilo.Estado.ANULADO]
        )

        silo = self.request.query_params.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)

        if self.request.query_params.get("vigentes") in {"1", "true"}:
            vigentes = [fila.id for fila in consulta if fila.vigente]
            consulta = consulta.filter(id__in=vigentes)

        return consulta

    def perform_create(self, serializer):
        serializer.save(
            analista=self.request.user,
            estado=AnalisisSilo.Estado.CONFIRMADO,
        )

    @action(detail=True, methods=["post"])
    def visualizar(self, request, pk=None):
        analisis = self.get_object()
        if analisis.estado != AnalisisSilo.Estado.CONFIRMADO:
            return Response(
                {"detail": "Solo se firma un análisis confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        if analisis.analista_id == request.user.id:
            return Response(
                {
                    "detail": (
                        "La visualización debe firmarla una persona distinta "
                        "de quien realizó el análisis."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        analisis.visualizado_por = request.user
        analisis.visualizado_en = timezone.now()
        analisis.save(update_fields=["visualizado_por", "visualizado_en"])
        return Response(self.get_serializer(analisis).data)

    def _borrador_del_usuario(self, request, pk=None):
        consulta = filtrar_por_scope(
            AnalisisSilo.objects.select_related("silo", "analista"),
            request.user,
            campo_sucursal="silo__sucursal_id",
            campo_empresa="silo__sucursal__empresa_id",
        ).filter(estado=AnalisisSilo.Estado.BORRADOR, abierto_por=request.user)
        silo = request.query_params.get("silo") or request.data.get("silo")
        if silo:
            consulta = consulta.filter(silo_id=silo)
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
            # Idempotente ante la carrera GET inicial / primer autoguardado:
            # el cliente adopta este id y continúa con PATCH, sin repetir POST.
            return Response(self.get_serializer(existente).data)
        datos = request.data.copy()
        datos.setdefault("tomado_en", timezone.now())
        serializer = self.get_serializer(data=datos, partial=True)
        serializer.is_valid(raise_exception=True)
        analisis = serializer.save(
            analista=request.user,
            abierto_por=request.user,
            abierto_en=timezone.now(),
            estado=AnalisisSilo.Estado.BORRADOR,
            tomado_en=serializer.validated_data["tomado_en"],
        )
        return Response(self.get_serializer(analisis).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch"], url_path="guardar-borrador")
    def guardar_borrador(self, request, pk=None):
        analisis = self._borrador_del_usuario(request, pk)
        if analisis is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(analisis, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="confirmar-borrador")
    def confirmar_borrador(self, request, pk=None):
        analisis = self._borrador_del_usuario(request, pk)
        if analisis is None:
            return Response(
                {"detail": "El borrador no existe o ya fue confirmado."},
                status=status.HTTP_409_CONFLICT,
            )
        analisis.tomado_en = timezone.now()
        motivos = analisis.confirmar(request.user)
        if motivos:
            return Response({"motivos": motivos}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(analisis).data)

    @action(detail=True, methods=["post"], url_path="descartar-borrador")
    def descartar_borrador(self, request, pk=None):
        analisis = self._borrador_del_usuario(request, pk)
        if analisis is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        analisis.estado = AnalisisSilo.Estado.ANULADO
        analisis.save(update_fields=["estado", "actualizado_en"])
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
def sugerencia_silos(request):
    """Silos ordenados por la leche utilizable más antigua."""
    try:
        volumen = Decimal(str(request.query_params.get("volumen", "0")))
    except Exception:
        return Response({"volumen": "Indica un volumen numérico."}, status=400)
    tipo = request.query_params.get("tipo", Silo.Tipo.SILO)
    silos = filtrar_por_scope(
        Silo.objects.filter(activo=True, tipo=tipo), request.user,
        campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ).order_by("codigo")
    ahora = timezone.now()
    entradas = []
    metadatos = {}
    for silo in silos:
        antigua = momento_leche_mas_antigua(silo)
        motivos = motivos_silo_no_disponible(silo, para="proceso", ahora=ahora)
        analisis = silo.analisis.filter(
            estado=AnalisisSilo.Estado.CONFIRMADO
        ).order_by("-tomado_en", "-id").first()
        antiguedad = (
            Decimal(str(round((ahora - antigua).total_seconds() / 3600, 1)))
            if antigua else None
        )
        entradas.append({
            "silo_id": silo.id,
            "litros_disponibles": saldo_silo(silo),
            "leche_mas_antigua_en": antigua,
            "antiguedad_horas": antiguedad,
            "motivos_no_disponible": motivos,
        })
        metadatos[silo.id] = (silo, analisis)
    sugerencias = dominio.sugerir_origenes(entradas, volumen)
    return Response({
        "volumen": volumen,
        "sugerencias": [
            {
                "silo": item.silo_id,
                "codigo": metadatos[item.silo_id][0].codigo,
                "litros_disponibles": item.litros_disponibles,
                "litros_sugeridos": item.litros_sugeridos,
                "leche_mas_antigua_en": item.leche_mas_antigua_en,
                "antiguedad_horas": item.antiguedad_horas,
                "grasa": metadatos[item.silo_id][1].grasa if metadatos[item.silo_id][1] else None,
                "sng": metadatos[item.silo_id][1].sng if metadatos[item.silo_id][1] else None,
                "motivos_no_disponible": item.motivos_no_disponible,
                "sugerido": item.sugerido,
            }
            for item in sugerencias
        ],
    })
