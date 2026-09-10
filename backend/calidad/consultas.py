"""Consultas optimizadas para la bandeja de resultados de procesos de Calidad.

Este módulo construye el modelo de lectura completo y aplica el alcance tenant.
Las vistas HTTP sólo validan parámetros y convierten el resultado en una respuesta.
"""

from collections import defaultdict
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from maestros.models import Especificacion
from produccion.models import Analisis
from recepcion.models import MovimientoSilo
from usuarios.tenancy import filtrar_por_scope

from .models import LiberacionProceso


RESULTADOS_PROCESO_POR_PAGINA = 20
RESULTADOS_PROCESO_MAXIMO = 50


def filtro_resultados_de_proceso():
    """Resultados que Calidad debe decidir antes de que el flujo continúe."""
    from procesos.models import EtapaProceso, SalidaProceso

    intermedio_en_silo = Q(silo__isnull=False) & (
        Q(ejecucion__etapa__requiere_calidad=True)
        | Q(destino=SalidaProceso.Destino.DESPACHO_DIRECTO)
    )
    mantequilla_a_granel = Q(
        silo__isnull=True,
        lote__isnull=False,
        ejecucion__etapa__tipo=EtapaProceso.Tipo.MANTEQUILLA,
        ejecucion__etapa__requiere_calidad=True,
        destino=SalidaProceso.Destino.ENVASADO,
    )
    secado_a_granel = Q(
        silo__isnull=True,
        lote__isnull=False,
        ejecucion__etapa__tipo=EtapaProceso.Tipo.SECADO,
        ejecucion__etapa__requiere_calidad=True,
        destino=SalidaProceso.Destino.PENDIENTE,
    )
    return intermedio_en_silo | mantequilla_a_granel | secado_a_granel


def valores_calidad_de_silo(analisis):
    """Traduce el análisis físico del silo al catálogo común de Calidad."""
    grasa = analisis.grasa
    sng = analisis.sng
    return {
        "mg": grasa,
        "sng": sng,
        "st": grasa + sng if grasa is not None and sng is not None else None,
        "acidez": analisis.acidez,
        "ph": analisis.ph,
        "temperatura": analisis.temperatura,
        "proteina": analisis.proteina,
        # AnalisisSilo conserva kg/m³; el catálogo común expresa g/mL.
        "pesoEsp": analisis.densidad / 1000 if analisis.densidad is not None else None,
    }


def consultar_resultados_intermedios(
    usuario,
    *,
    solo_pendientes=False,
    pagina=None,
    limite=50,
    tipo="",
    preparacion="",
    buscar="",
):
    """Salidas trazables que requieren una decisión propia de Calidad."""
    from produccion import dominio as dominio_produccion
    from procesos.models import EjecucionProceso, SalidaProceso
    from recepcion.models import AnalisisSilo

    salidas = filtrar_por_scope(
        SalidaProceso.objects.filter(filtro_resultados_de_proceso())
        .filter(
            Q(
                ejecucion__estado__in=[
                    EjecucionProceso.Estado.PENDIENTE_CONTROL,
                    EjecucionProceso.Estado.BLOQUEADA,
                ]
            )
            | Q(liberacion_calidad__isnull=False)
        )
        .select_related(
            "ejecucion__etapa",
            "ejecucion__equipo",
            "silo",
            "lote__producto",
            "liberacion_calidad",
            "liberacion_calidad__analisis_lote",
            "ejecucion__corrida_condensacion__lote__producto",
            "ejecucion__corrida_descremacion",
        )
        .order_by("-registrada_en"),
        usuario,
        campo_sucursal="ejecucion__sucursal_id",
        campo_empresa="ejecucion__sucursal__empresa_id",
    )
    if solo_pendientes:
        salidas = salidas.filter(
            Q(liberacion_calidad__isnull=True)
            | Q(liberacion_calidad__estado=LiberacionProceso.Estado.PENDIENTE)
        ).order_by("registrada_en", "id")
    if tipo:
        salidas = salidas.filter(ejecucion__etapa__tipo=tipo)
    if buscar:
        salidas = salidas.filter(
            Q(ejecucion__codigo__icontains=buscar)
            | Q(lote__codigo_lote__icontains=buscar)
            | Q(lote__producto__nombre__icontains=buscar)
            | Q(silo__codigo__icontains=buscar)
        )
    if preparacion:
        con_analisis_silo = AnalisisSilo.objects.filter(
            silo_id=OuterRef("silo_id"),
            tomado_en__gte=OuterRef("registrada_en"),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista_id__isnull=False,
            visualizado_por_id__isnull=False,
        )
        con_analisis_lote = Analisis.objects.filter(
            lote_id=OuterRef("lote_id"),
            fecha__gte=OuterRef("registrada_fecha"),
        )
        salidas = salidas.annotate(
            registrada_fecha=TruncDate("registrada_en"),
            tiene_analisis_silo=Exists(con_analisis_silo),
            tiene_analisis_lote=Exists(con_analisis_lote),
        )
        tiene_antecedentes = Q(silo_id__isnull=False, tiene_analisis_silo=True) | Q(
            silo_id__isnull=True, tiene_analisis_lote=True
        )
        salidas = (
            salidas.filter(tiene_antecedentes)
            if preparacion == "con_analisis"
            else salidas.filter(~tiene_antecedentes)
        )
    total = salidas.count() if pagina is not None else None
    if pagina is None:
        salidas = list(salidas[:limite])
    else:
        inicio = (pagina - 1) * limite
        salidas = list(salidas[inicio : inicio + limite])
    analisis_por_silo = defaultdict(list)
    ingresos_posteriores = (
        MovimientoSilo.objects.filter(
            silo_id=OuterRef("silo_id"),
            tipo=MovimientoSilo.Tipo.INGRESO,
            fecha_hora__gt=OuterRef("tomado_en"),
        )
        .order_by()
        .values("silo_id")
        .annotate(total=Sum("litros"), cantidad=Count("id"))
    )
    analisis = (
        AnalisisSilo.objects.filter(
            silo_id__in=[salida.silo_id for salida in salidas],
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista_id__isnull=False,
            visualizado_por_id__isnull=False,
        )
        .annotate(
            ingresos_posteriores_litros=Coalesce(
                Subquery(ingresos_posteriores.values("total")[:1]),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=16, decimal_places=2),
            ),
            ingresos_posteriores_cantidad=Coalesce(
                Subquery(ingresos_posteriores.values("cantidad")[:1]),
                Value(0),
                output_field=IntegerField(),
            ),
        )
        .order_by("-tomado_en")
    )
    for item in analisis:
        analisis_por_silo[item.silo_id].append(item)
    analisis_por_lote = defaultdict(list)
    for item in (
        Analisis.objects.filter(
            lote_id__in=[salida.lote_id for salida in salidas if salida.lote_id]
        )
        .select_related("especificacion")
        .order_by("-fecha", "-id")
    ):
        analisis_por_lote[item.lote_id].append(item)
    especificaciones = list(
        Especificacion.objects.filter(
            producto_id__in={
                salida.lote.producto_id
                for salida in salidas
                if salida.lote_id and salida.lote.producto_id
            }
        )
    )

    resultado = []
    for salida in salidas:
        decision = getattr(salida, "liberacion_calidad", None)
        descremacion = getattr(salida.ejecucion, "corrida_descremacion", None)
        if salida.lote_id:
            producto = salida.lote.producto.nombre
            lote_codigo = salida.lote.codigo_lote
        elif descremacion is not None:
            producto = (
                "Leche descremada"
                if salida.naturaleza == SalidaProceso.Naturaleza.PRINCIPAL
                else "Crema"
            )
            lote_codigo = f"{salida.ejecucion.codigo}-{salida.pk}"
        else:
            producto = salida.ejecucion.etapa.nombre
            lote_codigo = salida.ejecucion.codigo
        disponibles_silo = (
            [
                item
                for item in analisis_por_silo[salida.silo_id]
                if item.tomado_en >= salida.registrada_en
            ]
            if salida.silo_id
            else []
        )
        disponibles_lote = (
            [
                item
                for item in analisis_por_lote[salida.lote_id]
                if item.fecha >= timezone.localdate(salida.registrada_en)
            ]
            if salida.lote_id and not salida.silo_id
            else []
        )
        especificacion = None
        if salida.lote_id and salida.lote.producto_id:
            especificacion = dominio_produccion.especificacion_vigente(
                especificaciones,
                salida.lote.producto_id,
                timezone.localdate(salida.registrada_en),
                (
                    Especificacion.TipoAnalisis.SILO
                    if salida.silo_id
                    else Especificacion.TipoAnalisis.LOTE
                ),
            )
        requiere_densidad = bool(
            salida.silo_id
            and salida.lote_id
            and (
                salida.ejecucion.etapa.tipo == "descremacion"
                or salida.lote.producto.familia == "crema"
            )
        )

        def serializar_analisis_silo(item):
            evaluacion = (
                dominio_produccion.evaluar_analisis(
                    valores_calidad_de_silo(item), especificacion
                )
                if salida.lote_id
                else None
            )
            return {
                "id": item.id,
                "tomado_en": item.tomado_en,
                "ph": item.ph,
                "acidez": item.acidez,
                "grasa": item.grasa,
                "sng": item.sng,
                "proteina": item.proteina,
                "densidad": item.densidad,
                "resultado": evaluacion.resultado if evaluacion else None,
                "habilita_liberacion": bool(
                    (evaluacion is None or evaluacion.resultado == "conforme")
                    and item.inhibidores_resultado == "negativo"
                    and item.vigente
                    and (not requiere_densidad or item.densidad is not None)
                ),
                "faltantes": evaluacion.faltantes if evaluacion else [],
                "desviaciones": [
                    {
                        "parametro": detalle.parametro,
                        "valor": detalle.valor,
                        "min": detalle.minimo,
                        "max": detalle.maximo,
                    }
                    for detalle in (evaluacion.desviaciones if evaluacion else [])
                ],
            }

        def serializar_analisis_lote(item):
            evaluacion = dominio_produccion.evaluar_analisis(
                item.valores, item.especificacion or especificacion
            )
            return {
                "id": item.id,
                "fecha": item.fecha,
                "muestra": item.muestra,
                "valores": item.valores,
                "resultado": evaluacion.resultado,
                "habilita_liberacion": evaluacion.resultado == "conforme",
                "faltantes": evaluacion.faltantes,
                "desviaciones": [
                    {
                        "parametro": detalle.parametro,
                        "valor": detalle.valor,
                        "min": detalle.minimo,
                        "max": detalle.maximo,
                    }
                    for detalle in evaluacion.desviaciones
                ],
            }

        analisis_serializados = (
            [serializar_analisis_silo(item) for item in disponibles_silo]
            if salida.silo_id
            else [serializar_analisis_lote(item) for item in disponibles_lote]
        )
        if salida.silo_id:
            puede_liberarse = any(
                item["habilita_liberacion"] for item in analisis_serializados
            )
        else:
            puede_liberarse = any(
                item["habilita_liberacion"] for item in analisis_serializados
            )
        if puede_liberarse:
            preparacion = "listo_liberar"
            motivo_preparacion = "Existe un análisis vigente y conforme para liberar."
        elif analisis_serializados:
            preparacion = "requiere_decision"
            motivo_preparacion = (
                "Hay análisis firmados, pero ninguno cumple todas las condiciones "
                "de liberación. Revisa desviaciones o rechaza con motivo."
            )
        else:
            preparacion = "esperando_analisis"
            motivo_preparacion = (
                "Falta un análisis confirmado, firmado y posterior al resultado."
            )

        resultado.append(
            {
                "id": salida.id,
                "tipo": salida.ejecucion.etapa.get_tipo_display(),
                "etapa_tipo": salida.ejecucion.etapa.tipo,
                "corrida_codigo": salida.ejecucion.codigo,
                "lote_codigo": lote_codigo,
                "producto_nombre": producto,
                "equipo_nombre": (
                    salida.ejecucion.equipo.nombre
                    if salida.ejecucion.equipo_id
                    else None
                ),
                "silo_destino_codigo": salida.silo.codigo if salida.silo_id else None,
                "cantidad": salida.cantidad,
                "unidad": salida.unidad,
                "registrada_en": salida.registrada_en,
                "preparacion": preparacion,
                "motivo_preparacion": motivo_preparacion,
                "clasificacion": salida.get_clasificacion_display(),
                "destino": salida.get_destino_display(),
                "estado": decision.estado
                if decision
                else LiberacionProceso.Estado.PENDIENTE,
                "observacion": decision.observacion if decision else "",
                "decidida_en": decision.decidida_en if decision else None,
                "analisis_tipo": "silo" if salida.silo_id else "lote",
                "analisis_seleccionado": (
                    decision.analisis_silo_id
                    if salida.silo_id
                    else decision.analisis_lote_id
                )
                if decision
                else None,
                "especificacion": {
                    "version": especificacion.version,
                    "rangos": especificacion.rangos,
                }
                if especificacion
                else None,
                "analisis_disponibles": analisis_serializados,
            }
        )
    return (resultado, total) if pagina is not None else resultado
