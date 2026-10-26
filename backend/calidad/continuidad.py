"""Continuidad productiva pendiente: nunca emite una firma ni libera despacho."""
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class AprobacionPendiente(ValidationError):
    """Ausencia/vencimiento de firma; no equivale a material rechazado."""


def activa():
    return bool(getattr(settings, "CCAA_CALIDAD_INTERMEDIA_AVISO", False))


def muestras_del_material(silo_id, *, desde=None, bloquear=False):
    """Todas las muestras del ciclo físico; otro llenado no dispone el anterior.

    Para una salida histórica, el primer vaciado posterior cierra su ventana.
    Para materia prima actual, el último vaciado separa los llenados.
    Los servicios de consumo mantienen el silo bloqueado durante esta lectura.
    """
    from decimal import Decimal
    from django.utils import timezone
    from recepcion.models import AnalisisSilo, MovimientoSilo

    hasta, saldo, inicio = timezone.now(), Decimal("0"), None
    movimientos = MovimientoSilo.objects.filter(silo_id=silo_id).order_by("fecha_hora", "pk")
    for fecha, tipo, litros in movimientos.values_list("fecha_hora", "tipo", "litros"):
        if fecha > hasta:
            break
        saldo += -litros if tipo == "salida" else litros
        if desde is not None:
            if fecha >= desde and saldo == 0 and tipo == "salida":
                hasta = fecha
                break
        elif saldo == 0 and tipo == "salida":
            inicio = None
        elif inicio is None:
            inicio = fecha
    muestras = AnalisisSilo.objects.filter(silo_id=silo_id, tomado_en__lte=hasta)
    if desde is not None or inicio is not None:
        muestras = muestras.filter(tomado_en__gte=desde if desde is not None else inicio)
    else:
        muestras = muestras.none()
    if bloquear:
        muestras = muestras.select_for_update()
    return muestras.order_by("tomado_en", "pk")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def politica(request):
    return Response({
        "avisos_intermedios": activa(),
        "mensaje": "Producción con Calidad pendiente; la inocuidad y liberación final siguen siendo obligatorias.",
    })


def vale_conforme_pendiente(vale):
    from estandarizacion.balance import balance_vale
    from procesos.models import EjecucionProceso

    evaluacion = vale.evaluacion()
    return bool(
        activa() and vale.estado == vale.Estado.MUESTREADO and vale.ejecutado_en
        and evaluacion is not None and evaluacion.cumple
        and not balance_vale(vale)["pendiente"]
        and EjecucionProceso.objects.filter(vale=vale, estado="cerrada").exists()
    )


def exigir_inocuidad_salida(salida, *, directa=True, bloquear=False):
    """Evalúa los controles reales existentes; no inventa límites ni resultados."""
    from inocuidad.models import MonitoreoPPRO
    from produccion.models import ControlProceso, ControlProcesoLectura
    from .dominio import bloqueos_de_inocuidad
    from .models import Liberacion, LiberacionProceso

    decision = LiberacionProceso.objects.filter(salida_id=salida.pk).first()
    if decision and decision.estado == "rechazado":
        raise ValidationError("El material fue rechazado por Calidad; no admite continuidad pendiente.")
    muestras = []
    if decision and decision.analisis_silo_id:
        muestras.append(decision.analisis_silo)
    if salida.silo_id:
        muestras.extend(muestras_del_material(
            salida.silo_id, desde=salida.registrada_en, bloquear=bloquear,
        ))
    if any(m.inhibidores_resultado == "positivo" for m in muestras):
        raise ValidationError("Inhibidores positivos: el material continúa bloqueado por inocuidad.")
    if not salida.ejecucion.vale_id:
        from maestros.models import Especificacion
        from produccion.dominio import evaluar_analisis, especificacion_vigente
        from produccion.models import Analisis
        from django.utils import timezone
        from .consultas import valores_calidad_de_silo

        producto_id = salida.producto_id or (salida.lote.producto_id if salida.lote_id else None)
        if salida.silo_id and producto_id:
            especificacion = especificacion_vigente(
                Especificacion.objects.filter(producto_id=producto_id), producto_id,
                timezone.localdate(salida.registrada_en), Especificacion.TipoAnalisis.SILO,
            )
            if any(evaluar_analisis(valores_calidad_de_silo(m), especificacion).resultado == "no_conforme" for m in muestras):
                raise ValidationError("El análisis del material es no conforme; Calidad debe resolver el resultado adverso.")
        if salida.lote_id:
            analisis_lote = Analisis.objects.filter(lote_id=salida.lote_id)
            if bloquear:
                analisis_lote = analisis_lote.select_for_update()
            for analisis in analisis_lote:
                especificacion = analisis.especificacion or especificacion_vigente(
                    Especificacion.objects.filter(producto_id=producto_id), producto_id, analisis.fecha,
                )
                if evaluar_analisis(analisis.valores, especificacion).resultado == "no_conforme":
                    raise ValidationError("El análisis del lote es no conforme; no es una firma meramente pendiente.")
    if salida.lote_id:
        if bloquear:
            from produccion.models import Lote
            Lote.objects.select_for_update().get(pk=salida.lote_id)
        if salida.lote.estado == "rechazado" or Liberacion.objects.filter(
            lote_id=salida.lote_id, estado="rechazado",
        ).exists():
            raise ValidationError("El lote fue rechazado; requiere la disposición de Calidad.")
        controles_qs = ControlProceso.objects.filter(lote_id=salida.lote_id)
        monitoreos_qs = MonitoreoPPRO.objects.filter(lote_id=salida.lote_id)
        if bloquear:
            controles_qs = controles_qs.select_for_update()
            monitoreos_qs = monitoreos_qs.select_for_update()
        controles = list(controles_qs)
        lecturas_qs = ControlProcesoLectura.objects.filter(control_id__in=[c.pk for c in controles])
        if bloquear:
            lecturas_qs = lecturas_qs.select_for_update()
        lecturas = list(lecturas_qs)
        monitoreos = list(monitoreos_qs)
        motivos = bloqueos_de_inocuidad(controles, lecturas, monitoreos)
        if motivos:
            raise ValidationError(motivos)


def comprobar_salida(salida_id, *, bloquear=True):
    """Devuelve firma real o None, más pendientes; errores estructurales bloquean."""
    from procesos.models import SalidaProceso
    from .etapas import cadena_salidas
    from .models import LiberacionProceso
    from .vigencia import _exigir, evidencia_salida, exigir_liberacion_salida_vigente

    if not activa():
        return exigir_liberacion_salida_vigente(salida_id, bloquear=bloquear), []
    cadena = cadena_salidas(salida_id, bloquear=bloquear)
    avisos, firma = [], None
    for pk in cadena:
        fuente = SalidaProceso.objects.select_related("ejecucion__vale", "ejecucion__etapa", "lote").get(pk=pk)
        evidencia_salida(pk, bloquear=bloquear)
        exigir_inocuidad_salida(fuente, directa=pk == salida_id, bloquear=bloquear)
        try:
            exigir_pendientes_entrada_resueltos(fuente.ejecucion_id, bloquear=bloquear)
        except AprobacionPendiente as error:
            avisos.extend(error.messages)
        if fuente.ejecucion.estado not in {"pendiente_control", "cerrada"}:
            raise ValidationError("La operación de origen todavía no está terminada.")
        if fuente.ejecucion.vale_id:
            from estandarizacion.balance import balance_vale

            vale = fuente.ejecucion.vale
            if balance_vale(vale)["pendiente"]:
                raise ValidationError("El vale de origen mantiene una discrepancia física de litros.")
            if vale.estado != "liberado":
                if not vale_conforme_pendiente(vale):
                    raise ValidationError("La operación del vale debe estar terminada y su RC medido conforme.")
                avisos.append(f"{vale.codigo}: operación conforme, pendiente de decisión de Calidad.")
            continue
        if not fuente.ejecucion.etapa.requiere_calidad:
            continue
        try:
            identificador = _exigir(LiberacionProceso, "salida_id", pk, evidencia_salida, bloquear=bloquear)
            if pk == salida_id:
                firma = identificador
        except AprobacionPendiente:
            avisos.append(f"{fuente.ejecucion.codigo}: análisis o firma de Calidad pendientes; sin liberación final.")
    return firma, list(dict.fromkeys(avisos))


def avisos_salida(salida_id):
    if not activa():
        return []
    return comprobar_salida(salida_id, bloquear=False)[1]


def avisos_ejecucion(ejecucion, *, bloquear=False):
    if not activa() or ejecucion is None:
        return []
    ids = ejecucion.entradas.exclude(salida_origen_id=None).values_list("salida_origen_id", flat=True)
    return list(dict.fromkeys(aviso for pk in ids for aviso in comprobar_salida(pk, bloquear=bloquear)[1]))


def registrar_desde_entradas(ejecucion, usuario, accion):
    if not activa() or ejecucion is None:
        return
    registrar(ejecucion, usuario, accion, avisos_ejecucion(ejecucion, bloquear=True))
    from maestros.models import Silo
    from recepcion.servicios import saldo_silo
    for silo in Silo.objects.filter(pk__in=ejecucion.entradas.values_list("silo_id", flat=True)):
        if silo.estado == Silo.Estado.PENDIENTE_CALIDAD and saldo_silo(silo) == 0:
            silo.estado = Silo.Estado.DISPONIBLE
            silo.save(update_fields=["estado"])


def registrar(ejecucion, usuario, accion, avisos):
    """Mismo commit del acto físico, una evidencia inmutable por acción."""
    if not activa():
        return
    from procesos.models import EventoProceso
    from recepcion.models import AnalisisSilo

    pendientes, controles_crudos = [], []
    avisos = list(avisos)
    for entrada in ejecucion.entradas.filter(salida_origen__isnull=True).exclude(silo_id=None):
        silo_id = entrada.silo_id
        control = deuda_sin_muestra(entrada)
        controles_crudos.append(control)
        # El acto puede cerrarse después de reutilizar el silo. La muestra
        # debe describir el retiro original, nunca el contenido actual.
        analisis = AnalisisSilo.objects.filter(
            silo_id=silo_id, tomado_en__gte=control["desde"], tomado_en__lte=control["hasta"],
        ).order_by("-tomado_en", "-pk").first()
        if analisis is None:
            pendientes.append(control)
            avisos.append(f"Silo {silo_id}: falta registrar la muestra representativa del material consumido.")
        else:
            pendientes.append(foto_analisis(analisis))
            if not analisis_completo(analisis):
                avisos.append(f"Análisis de silo {analisis.pk}: firma/revisión pendiente.")
    if not avisos and not controles_crudos:
        return

    if usuario is None:
        raise ValidationError("Continuar con Calidad pendiente requiere identificar al operador.")
    EventoProceso.objects.get_or_create(
        operacion_id=uuid5(NAMESPACE_URL, f"ccaa:calidad-pendiente:{ejecucion.pk}:{accion}"),
        defaults={"ejecucion": ejecucion, "usuario": usuario,
                  "tipo": "continuidad_calidad_pendiente", "motivo": accion,
                  "datos": {"politica": "intermedios_aviso_v1", "avisos": list(dict.fromkeys(avisos)),
                            "analisis_silo_pendientes": pendientes,
                            "controles_material_crudo": controles_crudos, "liberacion_final": False}},
    )


def analisis_completo(analisis):
    return bool(analisis.estado == "confirmado" and analisis.analista_id and analisis.visualizado_por_id
                and analisis.analista_id != analisis.visualizado_por_id and analisis.visualizado_en
                and analisis.inhibidores_resultado == "negativo")


def foto_analisis(analisis):
    campos = ("id", "silo_id", "tomado_en", "grasa", "sng", "densidad", "inhibidores_resultado")
    return {campo: str(getattr(analisis, campo)) for campo in campos}


def deuda_sin_muestra(entrada):
    from decimal import Decimal
    from django.db.models import Q, Sum
    from recepcion.models import MovimientoSilo

    ejecucion = entrada.ejecucion
    filtro = Q(pk__in=[])
    if ejecucion.vale_id:
        filtro |= Q(origen_tipo="estandarizacion", origen_id=ejecucion.vale_id,
                    operacion_id=uuid5(NAMESPACE_URL, f"ccaa:estandarizacion:{ejecucion.vale_id}"))
    for relacion, tipo in (("corrida_descremacion", "descremacion"),
                           ("corrida_condensacion", "produccion"), ("corrida_secado", "produccion")):
        corrida = getattr(ejecucion, relacion, None)
        if corrida:
            filtro |= Q(origen_tipo=tipo, origen_id=corrida.pk, operacion_id=corrida.operacion_id)
    lote = getattr(ejecucion, "lote_produccion", None)
    if lote:
        filtro |= Q(origen_tipo="lote", origen_id=lote.pk, lote_id=lote.pk)
    retiros = list(MovimientoSilo.objects.filter(filtro, silo_id=entrada.silo_id, tipo="salida"))
    cantidad = ejecucion.entradas.filter(silo_id=entrada.silo_id).aggregate(total=Sum("cantidad"))["total"] or Decimal("0")
    if len(retiros) != 1 or retiros[0].litros != cantidad:
        raise ValidationError("No se puede registrar la deuda de muestra sin un retiro físico único y correlacionado.")
    retiro = retiros[0]
    ingreso = MovimientoSilo.objects.filter(
        Q(fecha_hora__lt=retiro.fecha_hora) | Q(fecha_hora=retiro.fecha_hora, pk__lt=retiro.pk),
        silo_id=entrada.silo_id, tipo="ingreso",
    ).order_by("-fecha_hora", "-pk").first()
    if ingreso is None:
        raise ValidationError("La muestra pendiente requiere identificar el ingreso del material consumido.")
    # Una nueva adición cambia la muestra representativa, pero no elimina
    # un adverso del contenido anterior cuando nunca se vació físicamente.
    saldo, inicio_control = Decimal("0"), None
    historia = MovimientoSilo.objects.filter(silo_id=entrada.silo_id).filter(
        Q(fecha_hora__lt=retiro.fecha_hora) | Q(fecha_hora=retiro.fecha_hora, pk__lt=retiro.pk),
    ).order_by("fecha_hora", "pk")
    for fecha, tipo, litros in historia.values_list("fecha_hora", "tipo", "litros"):
        saldo += -litros if tipo == "salida" else litros
        if saldo == 0 and tipo == "salida":
            inicio_control = None
        elif inicio_control is None and tipo == "ingreso":
            inicio_control = fecha
    return {"tipo": "sin_muestra", "entrada_id": entrada.pk, "silo_id": entrada.silo_id,
            "movimiento_retiro_id": retiro.pk, "movimiento_ingreso_id": ingreso.pk,
            "desde_control": (inicio_control or ingreso.fecha_hora).isoformat(),
            "desde": ingreso.fecha_hora.isoformat(), "hasta": retiro.fecha_hora.isoformat()}


def exigir_pendientes_entrada_resueltos(ejecucion_id, *, bloquear=False):
    """La firma final también exige resolver las mediciones crudas utilizadas."""
    from procesos.models import EventoProceso
    from recepcion.models import AnalisisSilo

    for datos in EventoProceso.objects.filter(
        ejecucion_id=ejecucion_id, tipo="continuidad_calidad_pendiente",
    ).values_list("datos", flat=True):
        for control in datos.get("controles_material_crudo", []):
            muestras = AnalisisSilo.objects.filter(
                silo_id=control["silo_id"], tomado_en__gte=control.get("desde_control", control["desde"]), tomado_en__lte=control["hasta"],
            )
            if bloquear:
                muestras = muestras.select_for_update()
            if any(m.inhibidores_resultado == "positivo" for m in muestras):
                raise ValidationError("Inhibidores positivos en el material consumido: sus descendientes siguen bloqueados.")
        for foto in datos.get("analisis_silo_pendientes", []):
            if foto.get("tipo") == "sin_muestra":
                muestras = AnalisisSilo.objects.filter(
                    silo_id=foto["silo_id"], tomado_en__gte=foto["desde"], tomado_en__lte=foto["hasta"],
                ).order_by("-tomado_en", "-pk")
                if bloquear:
                    muestras = muestras.select_for_update()
                muestras = list(muestras)
                if any(m.inhibidores_resultado == "positivo" for m in muestras):
                    raise ValidationError("Inhibidores positivos en el material consumido; un remuestreo no lo libera.")
                if not any(analisis_completo(muestra) for muestra in muestras):
                    raise AprobacionPendiente("Falta una muestra representativa del material antes de consumirlo; una muestra de otro llenado no libera el lote.")
                continue
            muestras = AnalisisSilo.objects.filter(pk=foto["id"])
            if bloquear:
                muestras = muestras.select_for_update()
            analisis = muestras.first()
            if analisis and analisis.inhibidores_resultado == "positivo":
                raise ValidationError("Inhibidores positivos en la muestra utilizada: no es una firma pendiente.")
            actual = foto_analisis(analisis) if analisis else {}
            coincide = all(actual.get(campo) == valor for campo, valor in foto.items() if valor not in {"None", ""})
            if analisis is None or not coincide or not analisis_completo(analisis):
                raise AprobacionPendiente("La medición de origen utilizada sigue pendiente de Calidad o cambió; requiere resolver el antecedente.")


def informacion_salida(salida):
    """Metadatos informativos; jamás convierte una firma ausente en liberado."""
    decision = getattr(salida, "liberacion_calidad", None)
    if not activa():
        return {"avisos_calidad": [], "estado_calidad": decision.estado if decision else "pendiente"}
    firma, avisos = comprobar_salida(salida.pk, bloquear=False)
    vale_liberado = bool(salida.ejecucion.vale_id and salida.ejecucion.vale.estado == "liberado")
    return {"avisos_calidad": avisos, "estado_calidad": "liberado" if (firma or vale_liberado) and not avisos else "pendiente"}
