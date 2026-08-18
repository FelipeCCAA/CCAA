from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from maestros.models import Silo

from .models import MovimientoSilo


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
    if producto and destino.producto_actual_id is None:
        destino.producto_actual = producto
        destino.save(update_fields=["producto_actual"])
    return [salida, ingreso]


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
