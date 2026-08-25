"""
El ciclo del vale de estandarización.

Cada paso es una acción con su regla, no un `PATCH estado=...`. La diferencia
importa en el paso que decide: **liberar exige que el RC medido cumpla**, y con
un campo escribible eso se salta con una petición.
"""

import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import ValeEstandarizacion
from maestros.models import Silo
from procesos.servicios import cerrar_estandarizacion, registrar_estandarizacion
from recepcion.models import MovimientoSilo
from recepcion.servicios import ESTADOS_SIN_CONSUMO, motivos_silo_no_disponible


def _saldo(silo):
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

    ids_silos = [vale.silo_entera_id, vale.silo_destino_id]
    if vale.silo_descremada_id:
        ids_silos.append(vale.silo_descremada_id)
    bloqueados = {
        silo.id: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=ids_silos)
    }
    entera = bloqueados[vale.silo_entera_id]
    destino = bloqueados[vale.silo_destino_id]
    descremada = bloqueados.get(vale.silo_descremada_id)

    for silo in filter(None, [entera, descremada]):
        motivos = motivos_silo_no_disponible(silo, para="proceso")
        if motivos:
            raise ValidationError(f"{silo.codigo}: " + " ".join(motivos))
    if not destino.activo or destino.estado in {
        Silo.Estado.BLOQUEADO_CALIDAD,
        Silo.Estado.EN_CIP,
        Silo.Estado.FUERA_SERVICIO,
    }:
        raise ValidationError(
            f"{destino.codigo} no admite ingresos ({destino.get_estado_display()})."
        )

    if _saldo(entera) < vale.litros_entera:
        raise ValidationError(
            f"{entera.codigo} no tiene {vale.litros_entera} L de leche entera disponibles."
        )
    if vale.litros_descremada and (
        descremada is None or _saldo(descremada) < vale.litros_descremada
    ):
        codigo = descremada.codigo if descremada else "el TK seleccionado"
        raise ValidationError(
            f"{codigo} no tiene {vale.litros_descremada} L de leche descremada disponibles."
        )
    if _saldo(destino) + vale.volumen > destino.capacidad_l:
        disponible = destino.capacidad_l - _saldo(destino)
        raise ValidationError(
            f"{destino.codigo} solo tiene {disponible} L de capacidad disponible."
        )

    ahora = timezone.now()
    operacion_id = uuid.uuid5(uuid.NAMESPACE_URL, f"ccaa:estandarizacion:{vale.pk}")
    movimientos = [
        MovimientoSilo(
            silo=entera, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=vale.litros_entera, fecha_hora=ahora,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.id,
            operacion_id=operacion_id, usuario=usuario,
        ),
        MovimientoSilo(
            silo=destino, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=vale.volumen, fecha_hora=ahora,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.id,
            operacion_id=operacion_id, usuario=usuario,
        ),
    ]
    if descremada and vale.litros_descremada:
        movimientos.append(MovimientoSilo(
            silo=descremada, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=vale.litros_descremada, fecha_hora=ahora,
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.id,
            operacion_id=operacion_id, usuario=usuario,
        ))
    creados = MovimientoSilo.objects.bulk_create(movimientos)
    from recepcion.servicios import atribuir_salida, heredar_atribuciones

    salidas = [
        movimiento for movimiento in creados
        if movimiento.tipo == MovimientoSilo.Tipo.SALIDA
    ]
    ingreso = next(
        movimiento for movimiento in creados
        if movimiento.tipo == MovimientoSilo.Tipo.INGRESO
    )
    for salida in salidas:
        atribuir_salida(salida)
    heredar_atribuciones(ingreso, salidas)

    vale.estado = ValeEstandarizacion.Estado.TRANSFERIDO
    vale.responsable = vale.responsable or usuario
    vale.save(update_fields=["estado", "responsable"])

    # El vale queda registrado como ejecucion de la etapa
    # «Estandarizacion»: es el mismo hecho de planta, y este es el
    # momento en que la mezcla ocurre de verdad.
    registrar_estandarizacion(vale=vale)

    return vale


@transaction.atomic
def iniciar_agitacion(*, vale_id):
    """
    Arranca el reloj de la agitación.

    La hora se toma del servidor y no se recibe del cliente: es lo que después
    decide si la muestra dispara el aviso de agitación corta, y aceptarla de
    fuera permitiría declarar treinta minutos que no ocurrieron.
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

    **Los treinta minutos avisan, no bloquean** (decisión de planta,
    2026-08-17). Una muestra tomada antes mide una mezcla que todavía no es
    homogénea, así que el RC que devuelve puede no ser el del silo; el vale
    queda con el aviso y con `muestreado_en`, que es lo que después permite
    auditar cuánto agitó de verdad. Lo que sigue impidiendo muestrear sin haber
    agitado nada es la transición de estado, no esta función.

    Devuelve `(vale, avisos)`, como `decidir` devuelve `(vale, evaluacion)`: la
    vista necesita el resultado del cálculo y no solo el objeto guardado.
    """
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    _exigir_transicion(vale, ValeEstandarizacion.Estado.MUESTREADO)

    if sng is None or float(sng) <= 0:
        raise ValidationError(
            "Sin sólidos no grasos no hay RC que calcular: revisa el análisis."
        )

    vale.grasa_real = grasa
    vale.sng_real = sng
    vale.muestreado_en = timezone.now()
    vale.estado = ValeEstandarizacion.Estado.MUESTREADO
    vale.save(update_fields=[
        "grasa_real", "sng_real", "muestreado_en", "estado",
    ])

    # Después de sellar, no antes: así el aviso que devuelve la acción es el
    # mismo que la ficha del vale mostrará más tarde. Calculado antes contaría
    # contra el reloj actual y los dos podrían no coincidir.
    return vale, vale.avisos_de_muestreo


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

    # Cierra la etapa solo si quedo conforme. Un vale que va a
    # correccion sigue en ejecucion, que es lo que pasa en el silo.
    if vale.estado == ValeEstandarizacion.Estado.LIBERADO:
        cerrar_estandarizacion(vale=vale)

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
    # Y el sello del muestreo anterior tampoco: conservarlo lo dejaría *antes*
    # del nuevo `agitacion_desde`, y `minutos_agitando` saldría negativo.
    vale.muestreado_en = None
    vale.save(update_fields=[
        "estado", "agitacion_desde", "grasa_real", "sng_real", "muestreado_en",
    ])

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
