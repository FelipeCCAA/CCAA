from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import OrdenTrabajo


@transaction.atomic
def transicionar_orden(*, orden_id, estado_nuevo, usuario, motivo=""):
    orden = OrdenTrabajo.objects.select_for_update().select_related("plan").get(pk=orden_id)
    if estado_nuevo not in OrdenTrabajo.TRANSICIONES.get(orden.estado, set()):
        raise ValidationError(
            f"No se puede pasar de {orden.get_estado_display()} a {estado_nuevo}."
        )
    if estado_nuevo == OrdenTrabajo.Estado.ASIGNADA and not orden.responsable_id:
        raise ValidationError("Asigne un responsable antes de continuar.")
    if estado_nuevo == OrdenTrabajo.Estado.EJECUCION and orden.inicio is None:
        orden.inicio = timezone.now()
    if estado_nuevo == OrdenTrabajo.Estado.CANCELADA and not motivo.strip():
        raise ValidationError("La cancelación requiere un motivo.")
    if estado_nuevo == OrdenTrabajo.Estado.CERRADA:
        if orden.prueba_conforme is not True:
            raise ValidationError("La orden solo se cierra con prueba conforme.")
        if not orden.motivo_cierre.strip():
            raise ValidationError("Registre el trabajo realizado antes de cerrar.")
        orden.termino = timezone.now()
        if orden.plan_id:
            plan = orden.plan
            plan.ultima_ejecucion = timezone.localdate()
            plan.proxima_ejecucion = plan.ultima_ejecucion + timedelta(days=plan.frecuencia_dias)
            plan.save(update_fields=["ultima_ejecucion", "proxima_ejecucion"])
    orden.estado = estado_nuevo
    orden.save()
    return orden
