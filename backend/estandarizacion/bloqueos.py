"""Retenciones de estandarización por discrepancias de balance.

Estas guardas consultan la evidencia vigente sin bloquear vales. Las acciones
que registran el acto físico mantienen la jerarquía propia de silo y vale.
"""

from django.core.exceptions import ValidationError
from django.db import connection


def _motivo_vale(vale):
    from .balance import balance_vale
    from .models import ValeEstandarizacion

    balance = balance_vale(vale)
    actos_fisicos = vale.actos.filter(tipo__in=("adicion", "retiro")).exists()
    ciclo_fisico_pendiente = (
        actos_fisicos and vale.estado != ValeEstandarizacion.Estado.LIBERADO
    )
    if not balance["pendiente"] and not ciclo_fisico_pendiente:
        return None
    if ciclo_fisico_pendiente:
        return (
            f"El vale {vale.codigo} tiene una corrección física sin nuevo ciclo "
            "de muestreo, análisis y liberación por Calidad."
        )
    diferencia = balance["diferencia"]
    if diferencia is not None:
        return (
            f"El vale {vale.codigo} tiene una discrepancia de balance de "
            f"{diferencia} L pendiente de investigación y corrección."
        )
    return (
        f"El vale {vale.codigo} tiene componentes que no concuerdan con el "
        "volumen ejecutado; requiere investigación y corrección."
    )


def motivo_retencion_silo(silo_id):
    """Motivo de retención si el silo recibió estandarización discrepante."""
    from maestros.models import Silo
    from .models import ValeEstandarizacion

    # Comparte el candado físico con transferencias y actos de corrección.
    if connection.in_atomic_block:
        Silo.objects.select_for_update().get(pk=silo_id)
    vales = ValeEstandarizacion.objects.filter(
        silo_destino_id=silo_id,
        ejecutado_en__isnull=False,
    ).order_by("pk")
    for vale in vales:
        motivo = _motivo_vale(vale)
        if motivo:
            return motivo
    return None


def exigir_sin_retencion_lote(lote_id):
    """Impide liberar o mover a inventario un lote ligado a un vale retenido."""
    from produccion.models import Lote

    vale_id = Lote.objects.filter(pk=lote_id).values_list("vale_id", flat=True).first()
    if not vale_id:
        return
    from .models import ValeEstandarizacion

    vale = ValeEstandarizacion.objects.get(pk=vale_id)
    motivo = _motivo_vale(vale)
    if motivo:
        raise ValidationError(motivo)


def exigir_sin_retencion_salida(salida_id):
    """Impide liberar o despachar una salida ligada al vale retenido."""
    from procesos.models import SalidaProceso

    salida = (
        SalidaProceso.objects.select_related("ejecucion").filter(pk=salida_id).first()
    )
    if salida is None:
        return
    vale_id = salida.ejecucion.vale_id
    if not vale_id and salida.lote_id:
        from produccion.models import Lote

        vale_id = (
            Lote.objects.filter(pk=salida.lote_id)
            .values_list("vale_id", flat=True)
            .first()
        )
    if vale_id:
        from .models import ValeEstandarizacion

        vale = ValeEstandarizacion.objects.get(pk=vale_id)
        motivo = _motivo_vale(vale)
        if motivo:
            raise ValidationError(motivo)
    if salida.silo_id:
        motivo = motivo_retencion_silo(salida.silo_id)
        if motivo:
            raise ValidationError(motivo)
