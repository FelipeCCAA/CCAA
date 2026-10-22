"""Dependencias explícitas de materiales; nunca deduce parentesco por silo/lote."""
from django.core.exceptions import ValidationError


def cadena_salidas(salida_id, *, bloquear=False):
    """Ancestros antes que consumidor; ciclos o cambio de origen se rechazan."""
    from procesos.models import EntradaProceso, SalidaProceso

    orden, visitados, camino = [], set(), set()

    def visitar(identificador):
        if identificador in camino:
            raise ValidationError("La trazabilidad contiene un ciclo; revisa los orígenes antes de operar.")
        if identificador in visitados:
            return
        camino.add(identificador)
        ejecucion_id = SalidaProceso.objects.values_list("ejecucion_id", flat=True).get(pk=identificador)
        origenes = EntradaProceso.objects.filter(
            ejecucion_id=ejecucion_id, salida_origen_id__isnull=False,
        ).order_by("salida_origen_id").values_list("salida_origen_id", flat=True)
        for origen_id in origenes:
            visitar(origen_id)
        camino.remove(identificador)
        visitados.add(identificador)
        orden.append(identificador)

    visitar(salida_id)
    if bloquear:
        bloquear_cadenas([salida_id])
    return orden


def bloquear_cadenas(salida_ids):
    """Unión ordenada antes de bloquear una salida individual seleccionada."""
    from procesos.models import EjecucionProceso, EntradaProceso, SalidaProceso

    iniciales = {pk: cadena_salidas(pk) for pk in sorted(set(salida_ids))}
    todos = {pk for cadena in iniciales.values() for pk in cadena}
    relaciones = list(SalidaProceso.objects.filter(pk__in=todos).values_list("pk", "lote_id", "ejecucion_id"))
    # No tomar raíces de lotes ancestros después de la raíz del consumidor.
    # Sus correcciones estables retiran las decisiones dependientes en el
    # mismo commit; _exigir relee la foto bajo ese lock de decisión.
    list(SalidaProceso.objects.select_for_update().filter(pk__in=todos).order_by("pk"))
    ejecuciones = {r[2] for r in relaciones}
    list(EjecucionProceso.objects.select_for_update().filter(pk__in=ejecuciones).order_by("pk"))
    list(EntradaProceso.objects.select_for_update().filter(ejecucion_id__in=ejecuciones).order_by("pk"))
    posteriores = list(SalidaProceso.objects.filter(pk__in=todos).values_list("pk", "lote_id", "ejecucion_id"))
    if sorted(relaciones) != sorted(posteriores) or any(cadena_salidas(pk) != cadena for pk, cadena in iniciales.items()):
        raise ValidationError("Cambió un origen mientras se confirmaba. Vuelve a cargar el material.")


def decision_material(salida_id):
    from .models import LiberacionProceso

    decision = LiberacionProceso.objects.filter(salida_id=salida_id).first()
    if decision is None:
        return None
    return {
        "estado": decision.estado, "firma_id": str(decision.firma_id) if decision.firma_id else None,
        "version_evidencia": decision.version_evidencia, "version_firmada": decision.version_firmada,
    }
