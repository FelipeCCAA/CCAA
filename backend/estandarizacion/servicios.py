"""
El ciclo del vale de estandarización.

Cada paso es una acción con su regla, no un `PATCH estado=...`. La diferencia
importa en el paso que decide: **liberar exige que el RC medido cumpla**, y con
un campo escribible eso se salta con una petición.
"""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import MINUTOS_DE_AGITACION, ValeEstandarizacion


def _exigir_transicion(vale, nuevo):
    permitidos = ValeEstandarizacion.TRANSICIONES.get(vale.estado, set())

    if nuevo not in permitidos:
        raise ValidationError(
            f"Un vale «{vale.get_estado_display()}» no puede pasar a «{nuevo}»."
        )


@transaction.atomic
def transferir(*, vale_id, usuario):
    """Las dos leches ya están en el silo de destino."""
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.TRANSFERIDO)

    vale.estado = ValeEstandarizacion.Estado.TRANSFERIDO
    vale.responsable = vale.responsable or usuario
    vale.save(update_fields=["estado", "responsable"])

    return vale


@transaction.atomic
def iniciar_agitacion(*, vale_id):
    """
    Arranca el reloj de la agitación.

    La hora se toma del servidor y no se recibe del cliente: es lo que después
    decide si una muestra es válida, y aceptarla de fuera permitiría declarar
    treinta minutos que no ocurrieron.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.AGITANDO)

    vale.estado = ValeEstandarizacion.Estado.AGITANDO
    vale.agitacion_desde = timezone.now()
    vale.save(update_fields=["estado", "agitacion_desde"])

    return vale


@transaction.atomic
def registrar_muestra(*, vale_id, grasa, sng):
    """
    Guarda el análisis de la muestra y deja el vale listo para decidir.

    **Exige los 30 minutos de agitación.** Una muestra tomada antes mide una
    mezcla que todavía no es homogénea: el RC que devuelve no es el del silo, y
    liberar con él sería liberar contra un número que no describe lo que hay.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.MUESTREADO)

    if not vale.puede_muestrear:
        minutos = vale.minutos_agitando or 0
        raise ValidationError(
            f"Lleva {minutos:.0f} minutos agitando y hacen falta "
            f"{MINUTOS_DE_AGITACION}. Antes de eso la mezcla no es homogénea y "
            "la muestra no mide el silo."
        )

    if sng is None or float(sng) <= 0:
        raise ValidationError(
            "Sin sólidos no grasos no hay RC que calcular: revisa el análisis."
        )

    vale.grasa_real = grasa
    vale.sng_real = sng
    vale.estado = ValeEstandarizacion.Estado.MUESTREADO
    vale.save(update_fields=["grasa_real", "sng_real", "estado"])

    return vale


@transaction.atomic
def decidir(*, vale_id, usuario):
    """
    Libera el silo si el RC cumple, o lo manda a corrección si no.

    **No recibe la decisión**: la calcula desde el análisis. Dejar que el
    cliente diga «liberado» convertiría la regla en una sugerencia.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)

    if vale.estado != ValeEstandarizacion.Estado.MUESTREADO:
        raise ValidationError(
            "Solo se decide sobre un vale muestreado: falta el análisis."
        )

    evaluacion = vale.evaluacion()

    if evaluacion is None:
        raise ValidationError("El vale no tiene análisis registrado.")

    vale.estado = (
        ValeEstandarizacion.Estado.LIBERADO
        if evaluacion.cumple
        else ValeEstandarizacion.Estado.CORRIGIENDO
    )
    vale.responsable = vale.responsable or usuario

    if not evaluacion.cumple:
        # El motivo queda escrito: es lo que le dice al operador qué agregar.
        nota = f"[{timezone.now():%Y-%m-%d %H:%M}] {evaluacion.motivo}"
        vale.observaciones = f"{vale.observaciones}\n{nota}".strip()

    vale.save(update_fields=["estado", "responsable", "observaciones"])

    return vale, evaluacion


@transaction.atomic
def reagitar(*, vale_id):
    """
    Vuelve a agitar después de corregir, y **reinicia el reloj**.

    Agregar leche deshace la homogeneidad: los treinta minutos se cuentan otra
    vez desde cero. Conservar el reloj anterior dejaría muestrear de inmediato
    una mezcla recién alterada.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.AGITANDO)

    vale.estado = ValeEstandarizacion.Estado.AGITANDO
    vale.agitacion_desde = timezone.now()
    # El análisis anterior ya no describe lo que hay en el silo.
    vale.grasa_real = None
    vale.sng_real = None
    vale.save(
        update_fields=["estado", "agitacion_desde", "grasa_real", "sng_real"]
    )

    return vale


@transaction.atomic
def anular(*, vale_id, motivo=""):
    """
    Cierra el vale sin liberar.

    **Exige motivo**: un vale anulado en blanco no distingue el error de
    captura del silo que se contaminó, y es lo primero que se pregunta al
    auditarlo. Un vale ya liberado no se anula — lo que se anula ahí es el lote
    que lo consumió, y eso no vive aquí.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.ANULADO)

    if not (motivo or "").strip():
        raise ValidationError("Anular un vale exige decir por qué.")

    nota = f"[{timezone.now():%Y-%m-%d %H:%M}] Anulado: {motivo.strip()}"
    vale.estado = ValeEstandarizacion.Estado.ANULADO
    vale.observaciones = f"{vale.observaciones}\n{nota}".strip()
    vale.save(update_fields=["estado", "observaciones"])

    return vale
