from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from maestros.models import Silo

from . import dominio
from .models import AnalisisSilo, AtribucionRecepcion, DespachoLeche, MovimientoSilo


ESTADOS_SIN_CONSUMO = {
    Silo.Estado.BLOQUEADO_CALIDAD,
    Silo.Estado.PENDIENTE_CIP,
    Silo.Estado.EN_CIP,
    Silo.Estado.FUERA_SERVICIO,
}


def saldo_silo(silo):
    return MovimientoSilo.objects.filter(silo=silo).aggregate(
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


def capas_fifo_silo(silo, antes_de=None):
    """Reconstruye el saldo del silo por origen justo antes de un movimiento."""
    movimientos = MovimientoSilo.objects.filter(silo=silo)
    if antes_de is not None:
        movimientos = movimientos.filter(
            Q(fecha_hora__lt=antes_de.fecha_hora)
            | Q(fecha_hora=antes_de.fecha_hora, id__lt=antes_de.id)
        )
    movimientos = list(movimientos.order_by("fecha_hora", "id"))
    ids = [movimiento.id for movimiento in movimientos]
    atribuciones = AtribucionRecepcion.objects.filter(
        movimiento_id__in=ids
    ).order_by("movimiento_id", "orden")
    return dominio.saldo_por_recepcion(movimientos, atribuciones)


def motivos_silo_no_disponible(silo, *, para, ahora=None):
    """Adapta la compuerta pura al libro, análisis y CIP persistidos."""
    from inventario.models import CicloCIP
    from .models import AnalisisSilo

    ahora = ahora or timezone.now()
    analisis = (
        AnalisisSilo.objects.filter(
            silo=silo, estado=AnalisisSilo.Estado.CONFIRMADO
        )
        .select_related("analista", "visualizado_por")
        .order_by("-tomado_en", "-id")
        .first()
    )
    ciclo_cip = (
        CicloCIP.objects.filter(
            silo=silo,
            tipo_objetivo=CicloCIP.TipoObjetivo.SILO,
            estado=CicloCIP.Estado.EN_CURSO,
        )
        .order_by("-inicio", "-id")
        .first()
    )

    leche_mas_antigua_en = momento_leche_mas_antigua(silo)
    datos_silo = {
        "activo": silo.activo,
        "estado": silo.estado,
        "leche_mas_antigua_en": leche_mas_antigua_en,
    }
    datos_analisis = None
    if analisis is not None:
        vigencia = analisis.vigencia
        datos_analisis = {
            "vigente": vigencia.vigente,
            "motivo_vigencia": vigencia.motivo,
            "grasa": analisis.grasa,
            "sng": analisis.sng,
            "inhibidores_resultado": analisis.inhibidores_resultado,
            "apto_inocuidad": analisis.apto_inocuidad,
            "analista_id": analisis.analista_id,
            "visualizado_por_id": analisis.visualizado_por_id,
            "alcohol_75_conforme": analisis.alcohol_75_conforme,
            "hervor_conforme": analisis.hervor_conforme,
            "organoleptico_conforme": analisis.organoleptico_conforme,
        }
    return dominio.motivos_silo_no_disponible(
        datos_silo, datos_analisis, ciclo_cip, ahora, para=para
    )


def momento_leche_mas_antigua(silo):
    capas = capas_fifo_silo(silo)
    leche_mas_antigua_en = None
    if capas:
        primera = capas[0]
        ingresos = MovimientoSilo.objects.filter(
            silo=silo, tipo=MovimientoSilo.Tipo.INGRESO
        )
        if primera.recepcion_id is not None:
            ingresos = ingresos.filter(
                origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
                origen_id=primera.recepcion_id,
            )
        leche_mas_antigua_en = ingresos.order_by("fecha_hora", "id").values_list(
            "fecha_hora", flat=True
        ).first()

    return leche_mas_antigua_en


@transaction.atomic
def atribuir_salida(movimiento):
    """Congela la composición FIFO de una salida; repetirlo es idempotente."""
    existentes = list(movimiento.atribuciones_recepcion.all())
    if existentes:
        return existentes
    es_salida = movimiento.tipo == MovimientoSilo.Tipo.SALIDA
    es_ajuste_negativo = (
        movimiento.tipo == MovimientoSilo.Tipo.AJUSTE
        and Decimal(str(movimiento.litros)) < 0
    )
    if not (es_salida or es_ajuste_negativo):
        raise ValidationError("Solo se atribuyen salidas o ajustes negativos.")

    Silo.objects.select_for_update().get(pk=movimiento.silo_id)
    resultado = dominio.atribuir_fifo(
        capas_fifo_silo(movimiento.silo, antes_de=movimiento),
        abs(Decimal(str(movimiento.litros))),
    )
    filas = [
        AtribucionRecepcion(
            movimiento=movimiento,
            recepcion_id=parte.recepcion_id,
            litros=parte.litros,
            orden=parte.orden,
            origen_no_atribuible=parte.origen_no_atribuible,
        )
        for parte in resultado.partes
    ]
    if resultado.remanente_no_atribuible > 0:
        filas.append(AtribucionRecepcion(
            movimiento=movimiento,
            recepcion=None,
            litros=resultado.remanente_no_atribuible,
            orden=len(filas) + 1,
            origen_no_atribuible="saldo histórico sin recepción atribuible",
        ))
    return AtribucionRecepcion.objects.bulk_create(filas)


@transaction.atomic
def heredar_atribuciones(ingreso, salidas):
    """Propaga al ingreso las recepciones consumidas por sus salidas fuente."""
    existentes = list(ingreso.atribuciones_recepcion.all())
    if existentes:
        return existentes
    fuentes = []
    for salida in salidas:
        fuentes.extend(atribuir_salida(salida))
    total_fuente = sum((fila.litros for fila in fuentes), Decimal("0"))
    if total_fuente <= 0:
        return []

    objetivo = abs(ingreso.litros)
    filas = []
    acumulado = Decimal("0")
    for indice, fuente in enumerate(fuentes, start=1):
        if indice == len(fuentes):
            litros = objetivo - acumulado
        else:
            litros = (objetivo * fuente.litros / total_fuente).quantize(Decimal("0.01"))
            acumulado += litros
        if litros <= 0:
            continue
        filas.append(AtribucionRecepcion(
            movimiento=ingreso,
            recepcion_id=fuente.recepcion_id,
            litros=litros,
            orden=len(filas) + 1,
            origen_no_atribuible=fuente.origen_no_atribuible,
        ))
    return AtribucionRecepcion.objects.bulk_create(filas)


@transaction.atomic
def transferir_silo(
    *, silo_origen_id, silo_destino_id, litros, operacion_id, usuario,
    motivo="", lote=None, producto=None, equipo=None,
):
    """Transfiere con dos asientos atómicos y una clave idempotente."""
    existente = list(
        MovimientoSilo.objects.filter(operacion_id=operacion_id)
        .select_related("silo", "silo_contraparte")
        .order_by("tipo")
    )
    if existente:
        return existente

    if silo_origen_id == silo_destino_id:
        raise ValidationError("El silo de origen y destino deben ser distintos.")
    cantidad = Decimal(str(litros))
    if cantidad <= 0:
        raise ValidationError({"litros": "La cantidad debe ser mayor que cero."})

    bloqueados = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(
            pk__in=sorted([silo_origen_id, silo_destino_id])
        )
    }
    if len(bloqueados) != 2:
        raise ValidationError("Uno de los silos no existe.")
    origen = bloqueados[silo_origen_id]
    destino = bloqueados[silo_destino_id]
    if origen.sucursal_id != destino.sucursal_id:
        raise ValidationError("No se puede transferir entre plantas distintas.")
    if not origen.activo or origen.estado in ESTADOS_SIN_CONSUMO:
        raise ValidationError(f"El silo {origen.codigo} no está habilitado para consumo.")
    if not destino.activo or destino.estado in {
        Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP,
        Silo.Estado.FUERA_SERVICIO,
    }:
        raise ValidationError(f"El silo {destino.codigo} no admite ingresos.")
    if producto and origen.producto_actual_id and origen.producto_actual_id != producto.pk:
        raise ValidationError("El producto no coincide con el contenido declarado del origen.")

    disponible = saldo_silo(origen)
    if cantidad > disponible:
        raise ValidationError({
            "litros": f"Saldo insuficiente: {origen.codigo} tiene {disponible} L."
        })
    ocupacion_destino = saldo_silo(destino)
    if ocupacion_destino + cantidad > destino.capacidad_l:
        raise ValidationError({
            "litros": (
                f"Capacidad insuficiente: {destino.codigo} admite "
                f"{destino.capacidad_l - ocupacion_destino} L."
            )
        })

    comunes = {
        "litros": cantidad,
        "fecha_hora": timezone.now(),
        "origen_tipo": MovimientoSilo.OrigenTipo.TRANSFERENCIA,
        "motivo": motivo,
        "operacion_id": operacion_id,
        "lote": lote,
        "producto": producto,
        "equipo": equipo,
        "usuario": usuario,
    }
    salida = MovimientoSilo.objects.create(
        silo=origen, silo_contraparte=destino,
        tipo=MovimientoSilo.Tipo.SALIDA, **comunes,
    )
    ingreso = MovimientoSilo.objects.create(
        silo=destino, silo_contraparte=origen,
        tipo=MovimientoSilo.Tipo.INGRESO, **comunes,
    )
    atribuir_salida(salida)
    heredar_atribuciones(ingreso, [salida])
    if producto and destino.producto_actual_id is None:
        destino.producto_actual = producto
        destino.save(update_fields=["producto_actual"])
    return [salida, ingreso]


@transaction.atomic
def despachar_leche(
    *, silo_id, litros, destino, guia_despacho, patente, fecha_hora,
    operacion_id, usuario,
):
    """Registra una salida a granel, con liberación vigente y FIFO."""
    existente = DespachoLeche.objects.filter(operacion_id=operacion_id).first()
    if existente:
        return existente

    silo = Silo.objects.select_for_update().get(pk=silo_id)
    cantidad = Decimal(str(litros))
    if cantidad <= 0:
        raise ValidationError({"litros": "La cantidad debe ser mayor que cero."})
    motivos = motivos_silo_no_disponible(silo, para="proceso", ahora=fecha_hora)
    if motivos:
        raise ValidationError({"silo": motivos})
    disponible = saldo_silo(silo)
    if cantidad > disponible:
        raise ValidationError({
            "litros": f"Saldo insuficiente: {silo.codigo} tiene {disponible} L."
        })
    analisis = AnalisisSilo.objects.filter(
        silo=silo, estado=AnalisisSilo.Estado.CONFIRMADO
    ).order_by("-tomado_en", "-id").first()
    if analisis.tomado_en > fecha_hora:
        raise ValidationError({
            "fecha_hora": "La liberación de Calidad debe ser anterior al despacho."
        })

    despacho = DespachoLeche.objects.create(
        silo=silo, litros=cantidad, destino=destino.strip(),
        guia_despacho=guia_despacho.strip(), patente=patente.strip().upper(),
        fecha_hora=fecha_hora, liberacion_analisis=analisis,
        responsable=usuario, operacion_id=operacion_id,
    )
    movimiento = MovimientoSilo.objects.create(
        silo=silo, tipo=MovimientoSilo.Tipo.SALIDA, litros=cantidad,
        fecha_hora=fecha_hora, origen_tipo=MovimientoSilo.OrigenTipo.DESPACHO,
        origen_id=despacho.pk, operacion_id=operacion_id,
        motivo=f"Guía {despacho.guia_despacho} · {despacho.destino}", usuario=usuario,
    )
    despacho.movimiento = movimiento
    despacho.save(update_fields=["movimiento"])
    return despacho


@transaction.atomic
def ajustar_silo(*, silo_id, litros, operacion_id, usuario, motivo):
    existente = MovimientoSilo.objects.filter(operacion_id=operacion_id).first()
    if existente:
        return existente
    silo = Silo.objects.select_for_update().get(pk=silo_id)
    cantidad = Decimal(str(litros))
    if cantidad == 0:
        raise ValidationError({"litros": "El ajuste no puede ser cero."})
    if not motivo.strip():
        raise ValidationError({"motivo": "El ajuste requiere un motivo."})
    nuevo_saldo = saldo_silo(silo) + cantidad
    if nuevo_saldo < 0:
        raise ValidationError({"litros": "El ajuste dejaría el silo con saldo negativo."})
    if nuevo_saldo > silo.capacidad_l:
        raise ValidationError({"litros": "El ajuste excedería la capacidad del silo."})
    return MovimientoSilo.objects.create(
        silo=silo, tipo=MovimientoSilo.Tipo.AJUSTE, litros=cantidad,
        fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        motivo=motivo, operacion_id=operacion_id, usuario=usuario,
    )
