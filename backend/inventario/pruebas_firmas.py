"""Precondición Calidad → Inventario; no sustituye las pruebas de firma por API.

Los escenarios de inventario parten de un acto upstream ya aprobado. Se
materializa su muestra y sello versionado; no existe este atajo en producción.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from calidad.evidencia import bloquear_catalogo
from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from produccion.models import Analisis
from recepcion.models import AnalisisSilo, ControlInhibidores


@transaction.atomic
def firmar_salida_de_prueba(salida, usuario):
    bloquear_catalogo()
    ahora = timezone.now()
    muestra = {}
    if salida.silo_id:
        muestra["analisis_silo"] = AnalisisSilo.objects.create(
            silo_id=salida.silo_id, tomado_en=ahora,
            estado=AnalisisSilo.Estado.CONFIRMADO,
            grasa=Decimal("3.5"), sng=Decimal("9"),
            inhibidores_resultado=ControlInhibidores.Resultado.NEGATIVO,
            metodo=ControlInhibidores.Metodo.TRI_SENSOR, hora_lectura=ahora.time(),
            analista=usuario, visualizado_por=usuario, visualizado_en=ahora,
        )
    elif salida.lote_id:
        muestra["analisis_lote"] = Analisis.objects.create(
            lote_id=salida.lote_id, fecha=salida.lote.fecha,
            muestra=f"Salida de prueba {salida.pk}", valores={},
        )
    else:
        raise ValueError("El fixture firmado debe identificar silo o lote de su muestra.")
    decision = LiberacionProceso.objects.create(
        salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
        decidida_por=usuario, decidida_en=ahora, **muestra,
    )
    registrar_firma_salida(decision)
    return decision
