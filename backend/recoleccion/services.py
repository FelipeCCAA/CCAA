from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion


@transaction.atomic
def agregar_carga(*, recoleccion_id, codigo, modulo, litros, estanque_origen=""):
    recoleccion = Recoleccion.objects.select_for_update().select_related("parada").get(
        pk=recoleccion_id
    )
    existente = CargaModulo.objects.filter(codigo=codigo).first()
    if existente:
        if (
            existente.recoleccion_id != recoleccion.id
            or existente.modulo != modulo.strip()
            or existente.estanque_origen != estanque_origen.strip()
            or existente.litros != Decimal(str(litros))
        ):
            raise ValidationError(
                "El código de carga ya existe con datos diferentes. No se puede reutilizar."
            )
        return existente, False
    if recoleccion.alcohol != Recoleccion.Alcohol.CONFORME:
        raise ValidationError("No se puede cargar leche con prueba de alcohol no conforme.")

    if not codigo.strip() or not modulo.strip():
        raise ValidationError("La carga debe identificar código y módulo.")
    litros = Decimal(str(litros))
    if litros <= 0:
        raise ValidationError("Los litros de la carga deben ser mayores que cero.")
    cargado = recoleccion.cargas.aggregate(total=Sum("litros"))["total"] or Decimal("0")
    if cargado + litros > recoleccion.litros_medidos:
        raise ValidationError(
            "Las cargas por módulo no pueden superar los litros medidos en el predio."
        )

    carga = CargaModulo.objects.create(
        codigo=codigo.strip(),
        recoleccion=recoleccion,
        modulo=modulo.strip(),
        estanque_origen=estanque_origen.strip(),
        litros=litros,
    )
    recoleccion.estado = Recoleccion.Estado.CARGADA
    recoleccion.parada.estado = ParadaRuta.Estado.COMPLETADA
    recoleccion.parada.salida = timezone.now()
    recoleccion.save(update_fields=["estado"])
    recoleccion.parada.save(update_fields=["estado", "salida"])
    return carga, True


@transaction.atomic
def cerrar_ruta(ruta_id):
    ruta = RutaRecoleccion.objects.select_for_update().get(pk=ruta_id)
    if ruta.estado in {RutaRecoleccion.Estado.CERRADA, RutaRecoleccion.Estado.CANCELADA}:
        return ruta
    if not ruta.paradas.exists():
        raise ValidationError("No se puede cerrar una ruta sin predios.")
    if ruta.paradas.filter(estado=ParadaRuta.Estado.PENDIENTE).exists():
        raise ValidationError("No se puede cerrar una ruta con predios pendientes.")
    ruta.estado = RutaRecoleccion.Estado.CERRADA
    ruta.save(update_fields=["estado", "actualizada_en"])
    return ruta
