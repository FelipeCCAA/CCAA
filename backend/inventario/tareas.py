"""
Tareas de inventario que no caben en una petición HTTP.

Por ahora una sola: el MRP semanal. La explosión multinivel de una semana
ocupaba un worker de Gunicorn de principio a fin, y con workers `sync` tres
cálculos dejan al resto de la planta esperando — de ahí los `WORKER TIMEOUT`
que aparecieron en la prueba de carga.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(autoretry_for=(), acks_late=True)
def refrescar_alertas_operacionales():
    """Recalcula vencimientos, cuarentenas y mínimos sin esperar una escritura."""
    from .servicios import actualizar_alertas_inventario

    actualizar_alertas_inventario()


@shared_task(
    # No se reintenta sola. El MRP escribe resultados y órdenes sugeridas: un
    # reintento automático sobre un fallo que dejó datos a medias los duplica,
    # y nadie mira dos veces una ejecución que figura terminada. Quien la pidió
    # ve el motivo y decide si repetirla.
    autoretry_for=(),
    acks_late=True,
)
def calcular_mrp_semana(ejecucion_id):
    """
    Rellena una ejecución encolada.

    **Toda la comunicación es a través de `EjecucionMRP`**, no del resultado de
    Celery: el estado y los datos viven donde la pantalla los consulta. Un
    segundo lugar donde mirar el mismo hecho es un sitio donde discrepar.
    """
    from planificacion.models import SemanaPlan

    from .models import EjecucionMRP
    from .servicios import ejecutar_mrp_semana

    ejecucion = EjecucionMRP.objects.filter(pk=ejecucion_id).first()

    if ejecucion is None:
        # La ejecución desapareció entre encolar y correr. No es un error del
        # cálculo y reintentar no la va a resucitar.
        logger.warning("MRP: la ejecución %s ya no existe", ejecucion_id)
        return

    ejecucion.estado = EjecucionMRP.Estado.EN_CURSO
    ejecucion.save(update_fields=["estado"])

    try:
        semana = SemanaPlan.objects.get(pk=ejecucion.parametros.get("semana"))

        ejecutar_mrp_semana(
            semana=semana,
            usuario=ejecucion.ejecutada_por,
            ejecucion=ejecucion,
        )
    except Exception as error:  # noqa: BLE001 — el motivo se guarda, no se traga
        logger.exception("MRP: falló la ejecución %s", ejecucion_id)

        # El motivo queda en la ejecución. Una fallida sin decir por qué obliga
        # a repetirla para averiguarlo, y repetirla es justo lo caro.
        ejecucion.estado = EjecucionMRP.Estado.FALLIDA
        ejecucion.error = str(error)[:2000]
        ejecucion.terminada_en = timezone.now()
        ejecucion.save(update_fields=["estado", "error", "terminada_en"])
        return

    ejecucion.estado = EjecucionMRP.Estado.TERMINADA
    ejecucion.terminada_en = timezone.now()
    ejecucion.save(update_fields=["estado", "terminada_en"])
