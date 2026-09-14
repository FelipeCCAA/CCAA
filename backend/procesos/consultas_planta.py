"""Modelo de lectura agregado para el panel transversal ``Planta Ahora``."""

from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import EjecucionProceso, EtapaProceso, SalidaProceso
from .servicios import ESTADOS_QUE_OCUPAN_EQUIPO


ESTADOS_ACTIVOS = (
    EjecucionProceso.Estado.PREPARACION,
    EjecucionProceso.Estado.EJECUCION,
    EjecucionProceso.Estado.PAUSADA,
)
ESTADOS_VISIBLES = (
    *ESTADOS_ACTIVOS,
    EjecucionProceso.Estado.PENDIENTE_CONTROL,
    EjecucionProceso.Estado.BLOQUEADA,
)


def _ejecuciones_operacionales():
    return EjecucionProceso.objects.all()


def contar_materiales_listos() -> int:
    """Salidas liberadas con saldo físico para su siguiente destino."""
    from calidad.models import LiberacionProceso
    from inventario.models import Despacho

    salidas = SalidaProceso.objects.filter(
        liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
    ).exclude(naturaleza=SalidaProceso.Naturaleza.MERMA)
    cero = Value(Decimal("0"))
    decimal = DecimalField(max_digits=14, decimal_places=3)
    continuables = (
        salidas.filter(
            destino__in=[
                SalidaProceso.Destino.PENDIENTE,
                SalidaProceso.Destino.SIGUIENTE_PROCESO,
                SalidaProceso.Destino.ESTANDARIZACION,
            ]
        )
        .annotate(
            comprometido=Coalesce(
                Sum("usos_como_origen__cantidad"), cero, output_field=decimal
            )
        )
        .filter(cantidad__gt=F("comprometido"))
        .count()
    )
    despachables = (
        salidas.filter(destino=SalidaProceso.Destino.DESPACHO_DIRECTO)
        .annotate(
            comprometido=Coalesce(
                Sum(
                    "detalles_despacho_granel__cantidad",
                    filter=Q(
                        detalles_despacho_granel__despacho__estado__in=[
                            Despacho.Estado.AUTORIZADO,
                            Despacho.Estado.DESPACHADO,
                        ]
                    ),
                ),
                cero,
                output_field=decimal,
            )
        )
        .filter(cantidad__gt=F("comprometido"))
        .count()
    )
    envasables = (
        salidas.filter(
            destino=SalidaProceso.Destino.ENVASADO,
            lote__isnull=False,
        )
        .annotate(
            comprometido=Coalesce(
                Sum("lote__registros_envase__kg_envasados"),
                cero,
                output_field=decimal,
            )
        )
        .filter(cantidad__gt=F("comprometido"))
        .count()
    )
    return continuables + despachables + envasables


def resumen_operacional_produccion(*, tipos_etapa=None):
    ejecuciones = _ejecuciones_operacionales()
    if tipos_etapa is not None:
        ejecuciones = ejecuciones.filter(etapa__tipo__in=tipos_etapa)
    indicadores = ejecuciones.aggregate(
        procesos_activos=Count("id", filter=Q(estado__in=ESTADOS_ACTIVOS)),
        esperando_calidad=Count(
            "id", filter=Q(estado=EjecucionProceso.Estado.PENDIENTE_CONTROL)
        ),
        equipos_ocupados=Count(
            "equipo_id",
            distinct=True,
            filter=Q(
                equipo_id__isnull=False,
                estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
            ),
        ),
        bloqueos=Count(
            "id", filter=Q(estado=EjecucionProceso.Estado.BLOQUEADA)
        ),
    )
    indicadores["materiales_listos"] = contar_materiales_listos()
    return indicadores


def consultar_planta_ahora():
    """Devuelve cifras exactas de la operación para una mirada de turno."""
    from maestros.models import Silo
    from produccion.models import PalletProducto
    from recepcion.models import MovimientoSilo, Recepcion

    ejecuciones = _ejecuciones_operacionales()
    produccion = resumen_operacional_produccion()

    por_etapa = list(
        ejecuciones.filter(estado__in=ESTADOS_VISIBLES)
        .values("etapa__tipo")
        .annotate(
            total=Count("id"),
            activos=Count("id", filter=Q(estado__in=ESTADOS_ACTIVOS)),
            esperando_calidad=Count(
                "id", filter=Q(estado=EjecucionProceso.Estado.PENDIENTE_CONTROL)
            ),
            bloqueados=Count(
                "id", filter=Q(estado=EjecucionProceso.Estado.BLOQUEADA)
            ),
        )
        .order_by("etapa__tipo")
    )
    etiquetas_etapa = dict(EtapaProceso.Tipo.choices)
    procesos = [
        {
            "tipo": fila["etapa__tipo"],
            "etiqueta": etiquetas_etapa.get(
                fila["etapa__tipo"], fila["etapa__tipo"]
            ),
            "total": fila["total"],
            "activos": fila["activos"],
            "esperando_calidad": fila["esperando_calidad"],
            "bloqueados": fila["bloqueados"],
        }
        for fila in por_etapa
    ]

    recepciones = Recepcion.objects.exclude(
        estado__in=[Recepcion.Estado.BORRADOR, Recepcion.Estado.ANULADA]
    )
    conteos_recepcion = {
        fila["estado"]: fila["total"]
        for fila in recepciones.values("estado").annotate(total=Count("id"))
    }
    pendientes_recepcion = sum(
        conteos_recepcion.get(estado, 0)
        for estado in (
            Recepcion.Estado.REGISTRADA,
            Recepcion.Estado.MUESTREADA,
            Recepcion.Estado.ANALIZADA,
            Recepcion.Estado.LIBERADA,
        )
    )

    silos = Silo.objects.filter(activo=True).annotate(
        litros=Coalesce(
            Sum(
                Case(
                    When(
                        movimientos__tipo=MovimientoSilo.Tipo.SALIDA,
                        then=-F("movimientos__litros"),
                    ),
                    default=F("movimientos__litros"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            ),
            Value(Decimal("0")),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )
    silos_resumen = list(silos.values("id", "codigo", "capacidad_l", "litros"))
    silos_alerta = [
        {
            "id": silo["id"],
            "codigo": silo["codigo"],
            "litros": silo["litros"],
            "capacidad": silo["capacidad_l"],
            "motivo": (
                "saldo_negativo" if silo["litros"] < 0 else "capacidad_excedida"
            ),
        }
        for silo in silos_resumen
        if silo["litros"] < 0 or silo["litros"] > silo["capacidad_l"]
    ]

    pallets = PalletProducto.objects.all()
    producto_pendiente_calidad = pallets.filter(
        estado__in=[
            PalletProducto.Estado.PENDIENTE_CALIDAD,
            PalletProducto.Estado.BLOQUEADO,
        ]
    ).count()

    recientes = list(
        ejecuciones.filter(estado__in=ESTADOS_VISIBLES)
        .select_related("etapa", "equipo")
        .order_by("-actualizada_en", "-id")[:6]
    )
    actividad = [
        {
            "id": ejecucion.id,
            "codigo": ejecucion.codigo,
            "etapa_tipo": ejecucion.etapa.tipo,
            "etapa": ejecucion.etapa.get_tipo_display(),
            "estado": ejecucion.estado,
            "estado_etiqueta": ejecucion.get_estado_display(),
            "equipo": ejecucion.equipo.nombre if ejecucion.equipo_id else None,
            "actualizada_en": ejecucion.actualizada_en,
        }
        for ejecucion in recientes
    ]

    indicadores = {
        **produccion,
        "recepciones_pendientes": pendientes_recepcion,
        "recepciones_retenidas": conteos_recepcion.get(
            Recepcion.Estado.RETENIDA, 0
        ),
        "silos_en_alerta": len(silos_alerta),
        "producto_pendiente_calidad": producto_pendiente_calidad,
    }
    alertas = []
    definiciones_alerta = (
        (
            "procesos_bloqueados",
            "critica",
            "Procesos bloqueados",
            "Requieren resolver una desviación antes de continuar.",
            produccion["bloqueos"],
            "/produccion",
        ),
        (
            "recepciones_retenidas",
            "atencion",
            "Recepciones retenidas",
            "Calidad debe revisar o cerrar estas recepciones.",
            indicadores["recepciones_retenidas"],
            "/leche",
        ),
        (
            "silos_en_alerta",
            "critica",
            "Silos fuera de rango",
            "El saldo físico está negativo o supera la capacidad declarada.",
            indicadores["silos_en_alerta"],
            "/silos",
        ),
        (
            "calidad_pendiente",
            "atencion",
            "Trabajo esperando Calidad",
            "Incluye procesos y producto envasado que no pueden continuar.",
            produccion["esperando_calidad"] + producto_pendiente_calidad,
            "/calidad",
        ),
    )
    for codigo, nivel, titulo, detalle, cantidad, ruta in definiciones_alerta:
        if cantidad:
            alertas.append(
                {
                    "codigo": codigo,
                    "nivel": nivel,
                    "titulo": titulo,
                    "detalle": detalle,
                    "cantidad": cantidad,
                    "ruta": ruta,
                }
            )

    return {
        "generado_en": timezone.now(),
        "indicadores": indicadores,
        "procesos_por_etapa": procesos,
        "silos": {
            "total": len(silos_resumen),
            "litros": sum(
                (silo["litros"] for silo in silos_resumen), Decimal("0")
            ),
            "alertas": silos_alerta,
        },
        "actividad_reciente": actividad,
        "alertas": alertas,
    }
