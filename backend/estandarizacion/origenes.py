"""Identidad material del vale; nunca asigna un lote histórico por compartir silo."""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Sum

from procesos.models import CorridaDescremacion, EtapaProceso, SalidaProceso
from recepcion.models import AnalisisSilo, MovimientoSilo
from recepcion.servicios import saldo_silo

from .recepciones import recepcion_posterior_a_vaciado


COMPONENTES = ("entera", "descremada", "crema")


def salidas_en_silos(silo_ids):
    return SalidaProceso.objects.filter(
        silo_id__in=silo_ids, unidad__iexact="l",
    ).exclude(naturaleza=SalidaProceso.Naturaleza.MERMA).select_related(
        "ejecucion__etapa", "ejecucion__vale", "ruta_producto", "lote", "silo",
    ).order_by("pk")


def saldo_material(salida):
    """Disponible de una salida, sin sumar dos veces la misma evidencia física."""
    from estandarizacion.balance import cantidad_operativa_salida
    from procesos.servicios import _disponible_salida_crema

    if salida.lote_id:
        # OP-05 ya concilia el retiro físico y la entrada del mismo consumo.
        return _disponible_salida_crema(salida)
    consumido = salida.usos_como_origen.aggregate(total=Sum("cantidad"))["total"] or 0
    comprometido = salida.detalles_despacho_granel.filter(
        despacho__estado__in=["autorizado", "despachado"],
    ).aggregate(total=Sum("cantidad"))["total"] or 0
    return cantidad_operativa_salida(salida) - consumido - comprometido


def exigir_ingreso_identificado(salida):
    """Prueba física acotada: un productor, ingreso único y tanque antes vacío.

    No interpreta capas mezcladas ni rellena la procedencia de históricos.
    Los llamadores de escritura mantienen silo y cadena bloqueados.
    """
    corrida = CorridaDescremacion.objects.filter(ejecucion_id=salida.ejecucion_id).first()
    if corrida is None:
        raise ValidationError("El origen requiere revisión: falta un ingreso productor inequívoco.")
    movimientos = list(MovimientoSilo.objects.filter(silo_id=salida.silo_id).order_by("fecha_hora", "pk"))
    ingresos = [m for m in movimientos if m.tipo == MovimientoSilo.Tipo.INGRESO
                and m.origen_tipo == MovimientoSilo.OrigenTipo.DESCREMACION
                and m.origen_id == corrida.pk]
    if len(ingresos) != 1 or ingresos[0].litros != salida.cantidad or ingresos[0].operacion_id != corrida.operacion_id:
        raise ValidationError("El origen requiere revisión: el ingreso productor no es único o no coincide.")
    ingreso = ingresos[0]
    saldo = Decimal("0")
    posterior = False
    for movimiento in movimientos:
        if movimiento.pk == ingreso.pk:
            if saldo != 0:
                raise ValidationError("El origen está mezclado con saldo previo; requiere identificar la composición.")
            posterior = True
        elif posterior and (movimiento.tipo == MovimientoSilo.Tipo.INGRESO
                            or (movimiento.tipo == MovimientoSilo.Tipo.AJUSTE and movimiento.litros > 0)):
            raise ValidationError("El origen recibió otros ingresos; requiere identificar la composición.")
        saldo += -movimiento.litros if movimiento.tipo == MovimientoSilo.Tipo.SALIDA else movimiento.litros


def preparar_origenes(vale, seleccion=None, *, candidatos_bloqueados=None):
    """La elección no reemplaza saldo, ruta ni firma; se revalida al transferir.

    El llamador bloquea cadenas antes de vale/silos y vuelve a consultar las
    candidatas bajo esos locks. No se define FIFO nuevo para los componentes.
    """
    from calidad.continuidad import comprobar_salida
    from procesos.servicios import siguiente_etapa_para_salida

    seleccion = {} if seleccion is None else seleccion
    if not isinstance(seleccion, dict) or set(seleccion) - set(COMPONENTES):
        raise ValidationError({"salidas_origen": "Indica los orígenes de entera, descremada o crema."})
    resultado = {}
    for componente in COMPONENTES:
        silo = getattr(vale, f"silo_{componente}")
        cantidad = Decimal(str(getattr(vale, f"litros_{componente}") or 0))
        if not silo or cantidad <= 0:
            if seleccion.get(componente):
                raise ValidationError({"salidas_origen": "El origen elegido no corresponde a un componente utilizado."})
            continue
        salidas = list(salidas_en_silos([silo.pk]))
        if candidatos_bloqueados is not None and not {s.pk for s in salidas} <= candidatos_bloqueados:
            raise ValidationError("Cambió un origen material mientras se confirmaba; actualiza el vale.")
        saldos = {s.pk: max(saldo_material(s), Decimal("0")) for s in salidas}
        activas = [s for s in salidas if saldos[s.pk] > 0]
        elegido_id = seleccion.get(componente)
        if elegido_id is not None and (type(elegido_id) is not int or elegido_id <= 0):
            raise ValidationError({"salidas_origen": "El identificador de origen debe ser un entero positivo."})
        nueva = recepcion_posterior_a_vaciado(silo, salidas) if componente == "entera" and salidas else None
        if nueva is not None:
            if elegido_id is not None:
                raise ValidationError({"salidas_origen": "La salida elegida pertenece al ciclo anterior del silo."})
            from calidad.continuidad import activa
            muestras = AnalisisSilo.objects.filter(silo_id=silo.pk)
            if not activa():
                muestras = muestras.filter(estado=AnalisisSilo.Estado.CONFIRMADO)
            analisis = muestras.order_by("-tomado_en", "-pk").first()
            if analisis is None or analisis.tomado_en <= nueva.ingreso.fecha_hora:
                raise ValidationError("La recepción nueva requiere un análisis posterior a su ingreso.")
            if vale.analisis_entera_id is not None and vale.analisis_entera_id != analisis.pk:
                raise ValidationError("El análisis del vale no identifica la recepción nueva.")
            if (vale.entera_grasa, vale.entera_sng) != (analisis.grasa, analisis.sng):
                raise ValidationError("La composición del vale no coincide con el análisis de la recepción nueva.")
            continue  # Recepción demostrada: conserva silo/FIFO, no fabrica un lote histórico.
        if not salidas:
            if elegido_id is not None:
                raise ValidationError({"salidas_origen": "El origen no pertenece al silo seleccionado."})
            continue  # Entrada cruda/de legado: conserva silo, sin inventar lote.
        if len(activas) != 1:
            raise ValidationError({"salidas_origen": f"{silo.codigo}: el origen es ambiguo; requiere identificar la composición antes de transferir."})
        elegido = next((s for s in activas if s.pk == elegido_id), None) if elegido_id else activas[0]
        if elegido is None:
            raise ValidationError({"salidas_origen": f"{silo.codigo}: el origen elegido no está disponible en ese silo."})
        if elegido.ejecucion.sucursal_id != silo.sucursal_id:
            raise ValidationError({"salidas_origen": "El origen no pertenece a la planta del silo."})
        # Un retiro histórico sin FK no se imputa automáticamente a una salida.
        # Tampoco se presenta como conciliada una mezcla con material sin origen.
        if sum(saldos.values(), Decimal("0")) != saldo_silo(silo):
            raise ValidationError({"salidas_origen": f"{silo.codigo}: hay que conciliar el saldo físico y sus orígenes antes de transferir."})
        exigir_ingreso_identificado(elegido)
        if elegido.destino not in {
            SalidaProceso.Destino.ESTANDARIZACION,
            SalidaProceso.Destino.SIGUIENTE_PROCESO,
            SalidaProceso.Destino.PENDIENTE,
        }:
            raise ValidationError({"salidas_origen": "Ese material tiene otro destino operativo."})
        siguiente = siguiente_etapa_para_salida(salida=elegido)
        if siguiente is None or siguiente.tipo != EtapaProceso.Tipo.ESTANDARIZACION:
            raise ValidationError({"salidas_origen": "La ruta del origen no continúa en Estandarización."})
        if cantidad > saldos[elegido.pk]:
            raise ValidationError({"salidas_origen": f"{silo.codigo}: la cantidad supera el saldo del origen seleccionado."})
        comprobar_salida(elegido.pk)
        resultado[componente] = elegido
    return resultado


def origenes_catalogo(silo_ids):
    """Lectura informativa; la confirmación exige firma y saldo bajo bloqueo."""
    resultado = []
    salidas = list(salidas_en_silos(silo_ids))
    recepciones_nuevas = {}
    for salida in salidas:
        if salida.silo_id not in recepciones_nuevas:
            recepciones_nuevas[salida.silo_id] = recepcion_posterior_a_vaciado(
                salida.silo, [s for s in salidas if s.silo_id == salida.silo_id],
            )
        if recepciones_nuevas[salida.silo_id] is not None:
            continue  # Las salidas previas no son material del ciclo actual.
        try:
            disponible = max(saldo_material(salida), Decimal("0"))
        except ValidationError:
            disponible = Decimal("0")
        if disponible <= 0:
            continue
        resultado.append({
            "id": salida.pk, "silo_id": salida.silo_id,
            "codigo": salida.lote.codigo_lote if salida.lote_id else salida.ejecucion.codigo,
            "cantidad_disponible": disponible,
            "bloqueo": motivo_origen_no_identificado(salida),
        })
    return resultado


def motivo_origen_no_identificado(salida):
    """El material ambiguo se muestra para revisión, nunca como consumible."""
    try:
        activas = [s for s in salidas_en_silos([salida.silo_id]) if saldo_material(s) > 0]
        if len(activas) != 1 or activas[0].pk != salida.pk:
            return "Hay varias fuentes en el tanque; falta identificar su composición."
        if saldo_material(salida) != saldo_silo(salida.silo):
            return "Hay que conciliar el material con el saldo físico del tanque."
        exigir_ingreso_identificado(salida)
    except ValidationError as error:
        return " ".join(error.messages)
    return None
