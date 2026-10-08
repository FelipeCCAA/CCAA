from collections import defaultdict
from decimal import Decimal, InvalidOperation
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import (
    Case, Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, Prefetch, Q, Subquery,
    Sum, Value, When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from auditoria.registro import (
    actualizar_en_lote_con_auditoria,
    actualizar_queryset_con_auditoria,
    crear_en_lote_con_auditoria,
)
from maestros.models import Silo
from .dominio import balance_mantequilla, errores_cierre_mantequilla
from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla, CorridaSecado,
    EjecucionProceso, EntradaProceso, EtapaProceso, EventoProceso, SalidaProceso,
    ReservaSiloProceso, RutaProducto,
)


ESTADOS_QUE_OCUPAN_EQUIPO = frozenset({
    EjecucionProceso.Estado.PREPARACION,
    EjecucionProceso.Estado.EJECUCION,
    EjecucionProceso.Estado.PAUSADA,
    EjecucionProceso.Estado.BLOQUEADA,
})

# Una ejecución en estos estados ya terminó: su corrida, si sigue en
# `borrador`/`en_proceso`, es un huérfano (E2E abortado, dato viejo) y no
# ocupa la máquina ni cuenta como trabajo del día en el puesto de Evaporación.
ESTADOS_EJECUCION_TERMINALES = frozenset({
    EjecucionProceso.Estado.CERRADA,
    EjecucionProceso.Estado.CANCELADA,
})


def ejecucion_cancelable(estado):
    """
    ¿Se puede cancelar una ejecución en este estado? Lo dice
    `EjecucionProceso.TRANSICIONES`: ni las terminales ni `pendiente_control`
    —el material ya salió y lo decide Calidad—. Una sola regla para
    `anular_lote`, que cancela, y para el `PATCH` del lote, que pide el permiso
    de la etapa solo cuando va a cancelar.
    """
    return EjecucionProceso.Estado.CANCELADA in EjecucionProceso.TRANSICIONES.get(estado, set())

# Una ejecución cancelada sin haber iniciado: se reservó la máquina y el
# material, pero nada entró a la máquina. Sus entradas quedan como rastro y no
# consumen saldo (`disponible_de_salida`).
def preparacion_cancelada(prefijo=""):
    """
    `PREPARACION_CANCELADA` vista desde otro modelo: con
    `prefijo="usos_como_origen__"` filtra los usos de una salida dentro de una
    anotación (`Sum(..., filter=~preparacion_cancelada(prefijo))`). Un solo
    `Q` para el saldo, la oferta y el cambio de destino.
    """
    return Q(**{
        f"{prefijo}ejecucion__estado": EjecucionProceso.Estado.CANCELADA,
        f"{prefijo}ejecucion__inicio__isnull": True,
    })


PREPARACION_CANCELADA = preparacion_cancelada()


def salida_de_lote_anulado(prefijo=""):
    """
    Una salida cuyo lote se anuló. Cancelar la preparación le devuelve el
    saldo (`PREPARACION_CANCELADA`), pero ese material ya no es de ningún
    lote vivo: no se ofrece (puesto de Secado, `salidas/disponibles`,
    «materiales listos») ni se prepara (`preparar_continuacion`). Un solo
    `Q` para las cuatro cuentas.
    """
    from produccion.models import Lote

    return Q(**{f"{prefijo}lote__estado": Lote.Estado.ANULADO})


MENSAJE_SALIDA_DE_LOTE_ANULADO = (
    "El lote {codigo} está anulado: su material no se ofrece ni se prepara."
)
MENSAJE_MOTIVO_CANCELACION = "Indica el motivo de la cancelación."
# La mantequilla tiene una sola entrada: su puesto. `preparar_continuacion`
# creaba una ejecución de Mantequilla sin `CorridaMantequilla`, sin cierre ni
# balance que ninguna pantalla supiera hacer.
MENSAJE_MANTEQUILLA_EN_PUESTO = "La mantequilla se prepara en el puesto de Mantequilla."

# Registro de planta que la torre pide antes de operar. Avisa, no bloquea:
# que bloquee lo decide Calidad, y sería sobre `avisos_de_torre`.
CODIGO_INSPECCION_PREOPERATIVA = "CCAA.Sec.FORM.003"
AVISO_INSPECCION_PREOPERATIVA = (
    f"Falta la inspección pre-operativa de hoy ({CODIGO_INSPECCION_PREOPERATIVA})."
)
MENSAJE_INICIO_SECADO_EN_PUESTO = "Las corridas de secado se inician desde el puesto de Secado."
MENSAJE_INICIO_DESCREMADO_EN_PUESTO = (
    "Las corridas de descremado se inician desde el puesto de Descremado."
)
MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO = (
    "Las corridas de mantequilla se inician desde el puesto de Mantequilla."
)
# Etapas cuyo inicio (`preparacion → ejecucion`) es de su puesto: el puesto
# aplica la única función de motivos de esa etapa. La bandeja genérica no lo
# ofrece y `transicionar` lo rechaza con este mensaje. Espejo en el frontend:
# `textoIniciarEnPuesto` (`services/planta-ahora.ts`).
MENSAJES_INICIO_EN_PUESTO = {
    EtapaProceso.Tipo.SECADO: MENSAJE_INICIO_SECADO_EN_PUESTO,
    EtapaProceso.Tipo.DESCREMACION: MENSAJE_INICIO_DESCREMADO_EN_PUESTO,
    EtapaProceso.Tipo.MANTEQUILLA: MENSAJE_INICIO_MANTEQUILLA_EN_PUESTO,
}


class ConflictoVersionEjecucion(Exception):
    """El operador actuó sobre una versión que otro turno ya modificó."""

    def __init__(self, *, version_actual):
        self.version_actual = version_actual
        super().__init__(
            "La ejecución cambió desde que abriste la pantalla. "
            "Actualiza la bandeja antes de volver a intentar."
        )


def diagnosticar_integridad_produccion(*, usuario):
    """Hallazgos operacionales acotados al alcance visible del usuario."""
    from usuarios.tenancy import filtrar_por_scope

    ejecuciones = filtrar_por_scope(
        EjecucionProceso.objects.select_related("equipo", "etapa"),
        usuario,
        campo_sucursal="sucursal_id",
        campo_empresa="sucursal__empresa_id",
    )

    def categoria(*, codigo, titulo, severidad, queryset, detalle):
        cantidad = queryset.count()
        return {
            "codigo": codigo,
            "titulo": titulo,
            "severidad": severidad,
            "cantidad": cantidad,
            "items": [
                {
                    "id": ejecucion.pk,
                    "codigo": ejecucion.codigo,
                    "detalle": detalle(ejecucion),
                }
                for ejecucion in queryset.order_by("-actualizada_en")[:20]
            ],
        }

    estados_iniciados = {
        EjecucionProceso.Estado.EJECUCION,
        EjecucionProceso.Estado.PAUSADA,
        EjecucionProceso.Estado.PENDIENTE_CONTROL,
        EjecucionProceso.Estado.BLOQUEADA,
        EjecucionProceso.Estado.CERRADA,
    }
    sin_entrada = ejecuciones.filter(
        estado__in=estados_iniciados, entradas__isnull=True
    )
    cerradas_sin_salida = ejecuciones.filter(
        estado=EjecucionProceso.Estado.CERRADA, salidas__isnull=True
    )
    fechas_inconsistentes = ejecuciones.filter(
        Q(estado__in=estados_iniciados, inicio__isnull=True)
        | Q(estado=EjecucionProceso.Estado.CERRADA, termino__isnull=True)
        | (~Q(estado=EjecucionProceso.Estado.CERRADA) & Q(termino__isnull=False))
    )
    ocupaciones = list(
        ejecuciones.filter(
            equipo_id__isnull=False, estado__in=ESTADOS_QUE_OCUPAN_EQUIPO
        )
        .values("equipo_id", "equipo__codigo")
        .annotate(cantidad=Count("id"))
        .filter(cantidad__gt=1)
        .order_by("equipo__codigo")[:20]
    )

    categorias = [
        categoria(
            codigo="ejecucion_sin_entrada",
            titulo="Ejecuciones iniciadas sin entrada",
            severidad="critico",
            queryset=sin_entrada,
            detalle=lambda item: f"{item.etapa.nombre} no tiene material de origen.",
        ),
        categoria(
            codigo="cierre_sin_salida",
            titulo="Ejecuciones cerradas sin salida",
            severidad="critico",
            queryset=cerradas_sin_salida,
            detalle=lambda item: f"{item.etapa.nombre} cerró sin producto ni merma.",
        ),
        categoria(
            codigo="estado_temporal_inconsistente",
            titulo="Estados y fechas contradictorios",
            severidad="alto",
            queryset=fechas_inconsistentes,
            detalle=lambda item: (
                f"Estado {item.get_estado_display()} con inicio o término inconsistente."
            ),
        ),
        {
            "codigo": "equipo_ocupado_multiples_veces",
            "titulo": "Equipos con más de una ocupación física",
            "severidad": "critico",
            "cantidad": len(ocupaciones),
            "items": [
                {
                    "id": item["equipo_id"],
                    "codigo": item["equipo__codigo"],
                    "detalle": f'{item["cantidad"]} ejecuciones ocupan el equipo.',
                }
                for item in ocupaciones
            ],
        },
    ]
    hallazgos = [item for item in categorias if item["cantidad"]]
    return {
        "completa": not hallazgos,
        "total_hallazgos": sum(item["cantidad"] for item in hallazgos),
        "categorias": hallazgos,
    }


def reservas_activas_silo(*, silo_id, tipo=None, excluir_ejecucion_id=None):
    """Consulta comun para que todos los procesos respeten el mismo compromiso."""
    reservas = ReservaSiloProceso.objects.filter(
        silo_id=silo_id,
        estado=ReservaSiloProceso.Estado.ACTIVA,
    )
    if tipo is not None:
        reservas = reservas.filter(tipo=tipo)
    if excluir_ejecucion_id is not None:
        reservas = reservas.exclude(ejecucion_id=excluir_ejecucion_id)
    return reservas


def litros_origen_reservados(*, silo_id, excluir_ejecucion_id=None):
    return reservas_activas_silo(
        silo_id=silo_id,
        tipo=ReservaSiloProceso.Tipo.ORIGEN,
        excluir_ejecucion_id=excluir_ejecucion_id,
    ).aggregate(total=Sum("cantidad_planificada"))["total"] or Decimal("0")


def exigir_destino_sin_reserva(*, silo, excluir_ejecucion_id=None):
    reserva = reservas_activas_silo(
        silo_id=silo.pk,
        excluir_ejecucion_id=excluir_ejecucion_id,
    ).select_related("ejecucion").order_by("pk").first()
    if reserva is not None:
        raise ValidationError({
            "silo_destino": (
                f"{silo.codigo} esta reservado por {reserva.ejecucion.codigo}."
            )
        })


def motivos_destino_concentrado(destino, litros, *, excluir_ejecucion_id=None):
    """
    Por qué `destino` no puede recibir `litros` de concentrado: reservado por
    otra ejecución, en un estado que no admite precondensado, o sin capacidad.

    Una sola regla para preparar (`crear_condensacion_guiada`) y para iniciar
    (`motivos_para_iniciar_condensacion`): con dos, el puesto preparaba una
    corrida que «Iniciar» rechazaba después, con el lote ya abierto.
    """
    from maestros.models import Silo
    from recepcion.servicios import saldo_silo

    motivos = []
    try:
        exigir_destino_sin_reserva(silo=destino, excluir_ejecucion_id=excluir_ejecucion_id)
    except ValidationError as error:
        motivos.extend(error.messages)
    if not destino.activo or destino.estado in {
        Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
    }:
        motivos.append(f"{destino.codigo} no admite precondensado.")
    elif saldo_silo(destino) + litros > destino.capacidad_l:
        motivos.append(f"{destino.codigo} no tiene capacidad para reservar {litros} L.")
    return motivos


def disponible_de_salida(salida):
    """
    Lo que queda de una salida para continuar: su cantidad menos lo que otras
    ejecuciones ya tomaron como origen y lo comprometido en despachos a granel
    autorizados o despachados.

    Una cantidad, una consulta: `preparar_continuacion` rechaza con esta misma
    función y el puesto de Secado ofrece con ella. Con dos cuentas, la pantalla
    ofrecía litros que el formulario, ya completo, rechazaba (caso 1 de «La
    pantalla ofrece lo que el backend va a rechazar», CLAUDE.md).

    Una preparación cancelada no cuenta: nunca llegó a la máquina
    (`PREPARACION_CANCELADA`). Una ejecución cancelada después de iniciar sí:
    lo que entró a la torre no vuelve al silo.
    """
    consumido = salida.usos_como_origen.exclude(
        PREPARACION_CANCELADA
    ).aggregate(total=Sum("cantidad"))["total"] or 0
    comprometido = salida.detalles_despacho_granel.filter(
        despacho__estado__in=["autorizado", "despachado"]
    ).aggregate(total=Sum("cantidad"))["total"] or 0
    return salida.cantidad - consumido - comprometido


def silos_con_saldo(queryset):
    """Anota cada silo de `queryset` con su saldo real, en una sola consulta.

    Misma regla que `recepcion.servicios.saldo_silo` —ingreso y ajuste suman,
    salida resta—, pero como anotación agrupada por silo en vez de una
    consulta aparte por cada uno: sobre un listado (opciones de destino del
    puesto, por ejemplo) una consulta por fila crece con la planta.
    """
    from recepcion.models import MovimientoSilo

    return queryset.annotate(
        saldo_l=Coalesce(
            Sum(Case(
                When(
                    movimientos__tipo=MovimientoSilo.Tipo.SALIDA,
                    then=-F("movimientos__litros"),
                ),
                default=F("movimientos__litros"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            )),
            Value(0), output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )


def adquirir_equipo(*, equipo_id, ejecucion_id=None):
    """Serializa la reserva del equipo y rechaza una segunda corrida activa."""
    from maestros.models import Equipo

    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    ocupadas = EjecucionProceso.objects.filter(
        equipo_id=equipo.pk,
        estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
    )
    if ejecucion_id is not None:
        ocupadas = ocupadas.exclude(pk=ejecucion_id)
    ocupada = ocupadas.order_by("pk").first()
    if ocupada is not None:
        raise ValidationError({
            "equipo": f"{equipo.nombre} está ocupado por {ocupada.codigo}."
        })
    return equipo


@transaction.atomic
def crear_ejecucion_proceso(*, datos):
    """Crea un borrador operativo sin permitir escrituras directas al modelo."""
    ejecucion = EjecucionProceso(**datos)
    ejecucion.full_clean()
    ejecucion.save()
    return ejecucion


@transaction.atomic
def crear_corrida_descremacion(*, datos):
    """Registra la corrida sobre una ejecucion bloqueada y aun disponible."""
    datos = dict(datos)
    ejecucion = (
        EjecucionProceso.objects.select_for_update()
        .select_related("etapa", "sucursal")
        .get(pk=datos["ejecucion"].pk)
    )
    datos["ejecucion"] = ejecucion
    corrida = CorridaDescremacion(**datos)
    corrida.full_clean()
    corrida.save()
    return corrida


@transaction.atomic
def crear_entrada_proceso(*, datos):
    """Agrega una entrada conservando saldo, autorizacion y trazabilidad."""
    from produccion.models import Lote

    datos = dict(datos)
    ejecucion = (
        EjecucionProceso.objects.select_for_update()
        .select_related("etapa", "sucursal")
        .get(pk=datos["ejecucion"].pk)
    )
    datos["ejecucion"] = ejecucion

    lote = datos.get("lote")
    if lote is not None:
        datos["lote"] = Lote.objects.select_for_update(of=("self",)).get(pk=lote.pk)

    salida = datos.get("salida_origen")
    if salida is not None:
        datos["salida_origen"] = (
            SalidaProceso.objects.select_for_update(of=("self",))
            .select_related("ejecucion__etapa", "silo")
            .get(pk=salida.pk)
        )

    entrada = EntradaProceso(**datos)
    entrada.full_clean()
    entrada.save()
    return entrada


@transaction.atomic
def crear_salida_proceso(*, datos):
    """Registra una salida serializando el balance de masa de la ejecucion."""
    datos = dict(datos)
    ejecucion = (
        EjecucionProceso.objects.select_for_update()
        .select_related("etapa", "sucursal")
        .get(pk=datos["ejecucion"].pk)
    )
    # El lock de la ejecucion evita que dos requests validen el mismo saldo.
    datos["ejecucion"] = ejecucion
    salida = SalidaProceso(**datos)
    salida.full_clean()
    salida.save()
    return salida


@transaction.atomic
def crear_descremacion_guiada(
    *, etapa_id, equipo_id, silo_entera_id,
    litros_entrada, silo_descremada_id, estanque_crema_id,
    producto_descremada_id, producto_crema_id, usuario,
    ruta_descremada_id=None, ruta_crema_id=None,
    destino_descremada=CorridaDescremacion.DestinoRama.PENDIENTE,
    destino_crema=CorridaDescremacion.DestinoRama.PENDIENTE,
    litros_descremada_plan=None, litros_crema_plan=None,
    analisis_esperado_id=None,
):
    """
    Prepara una descremación: corrida, reservas de silo y descremadora tomada,
    en una sola transacción —todo o nada—. El análisis y el código los pone el
    servidor.

    `analisis_esperado_id` es el análisis con que el formulario pidió la
    sugerencia. Si ya no es el último confirmado, el reparto que el operador
    confirmó se calculó para otra leche: se rechaza sin escribir nada.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Equipo, Producto, Silo
    from recepcion.servicios import ultimo_analisis_confirmado

    try:
        etapa = EtapaProceso.objects.select_related("proceso").get(
            pk=etapa_id, activa=True, tipo=EtapaProceso.Tipo.DESCREMACION
        )
    except EtapaProceso.DoesNotExist as error:
        raise ValidationError({"etapa": "Selecciona una etapa activa de descremacion."}) from error

    # Los tres silos en una sola consulta y en orden de clave, como preparar,
    # iniciar y cerrar: dos transacciones que los tomen en otro orden se
    # bloquean entre sí.
    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(
            pk__in=[silo_entera_id, silo_descremada_id, estanque_crema_id]
        ).order_by("pk")
    }
    origen = silos.get(silo_entera_id)
    if origen is None:
        raise ValidationError({"silo_entera": "El silo de origen no existe."})
    destinos = {
        pk: silos[pk] for pk in (silo_descremada_id, estanque_crema_id)
        if pk in silos and pk != silo_entera_id
    }
    if len(destinos) != 2:
        raise ValidationError("Selecciona los dos estanques de destino.")
    try:
        equipo = Equipo.objects.get(pk=equipo_id, activo=True)
    except Equipo.DoesNotExist as error:
        raise ValidationError({"equipo": "El equipo no esta activo en la planta de origen."}) from error
    if equipo.tipo not in tipos_equipo_para_etapa(etapa.tipo):
        raise ValidationError({"equipo": "El equipo no es compatible con descremacion."})
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})

    # El análisis lo elige el servidor: el último confirmado del silo, el
    # mismo que lee `motivos_silo_no_disponible` al iniciar. Un análisis
    # elegido en el cliente podía ser uno viejo, y el inicio evaluaba otro.
    analisis = ultimo_analisis_confirmado(origen)
    motivos = motivos_para_preparar_desde_silo(origen, analisis)
    if motivos:
        raise ValidationError({"silo_entera": motivos[0]})
    if analisis_esperado_id is not None and analisis.pk != analisis_esperado_id:
        raise ValidationError({
            "analisis_esperado": "El análisis del silo cambió: recalcula la sugerencia."
        })

    productos = {
        producto.pk: producto
        for producto in Producto.objects.select_related("mandante").filter(
            pk__in=[producto_descremada_id, producto_crema_id]
        )
    }
    if len(productos) != 2:
        raise ValidationError("Selecciona los dos productos intermedios.")

    rutas = {
        ruta.pk: ruta
        for ruta in RutaProducto.objects.select_related("proceso").filter(
            pk__in=[valor for valor in (ruta_descremada_id, ruta_crema_id) if valor],
            activa=True,
        )
    }
    if ruta_descremada_id and ruta_descremada_id not in rutas:
        raise ValidationError({"ruta_descremada": "La ruta no está activa."})
    if ruta_crema_id and ruta_crema_id not in rutas:
        raise ValidationError({"ruta_crema": "La ruta no está activa."})
    for campo, destino, ruta_id in (
        ("ruta_descremada", destino_descremada, ruta_descremada_id),
        ("ruta_crema", destino_crema, ruta_crema_id),
    ):
        if destino != CorridaDescremacion.DestinoRama.PENDIENTE and not ruta_id:
            raise ValidationError({campo: "Selecciona la ruta de continuidad de esta salida."})
        if destino == CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO and ruta_id:
            if rutas[ruta_id].destino_final != RutaProducto.DestinoFinal.DESPACHO_DIRECTO:
                raise ValidationError({campo: "La ruta elegida no termina en despacho directo."})

    sugerencia = sugerir_plan_descremacion(
        analisis=analisis, litros_entrada=litros_entrada,
        producto_descremada=productos[producto_descremada_id],
        producto_crema=productos[producto_crema_id],
    )
    ejecucion = crear_ejecucion_proceso(datos={
        # Provisional: el código usa el id de la corrida, que todavía no
        # existe. Todo ocurre en esta transacción: nadie ve este valor.
        "codigo": f"EJ-DES-TMP-{uuid.uuid4().hex}",
        "etapa": etapa,
        "sucursal": origen.sucursal,
        "equipo": equipo,
        "responsable": usuario,
    })
    corrida = crear_corrida_descremacion(datos={
        "ejecucion": ejecucion,
        "silo_entera": origen,
        "analisis_entrada": analisis,
        "litros_entrada": Decimal(str(litros_entrada)),
        "grasa_entrada": analisis.grasa,
        "sng_entrada": analisis.sng,
        "silo_descremada": destinos[silo_descremada_id],
        "estanque_crema": destinos[estanque_crema_id],
        "producto_descremada": productos[producto_descremada_id],
        "producto_crema": productos[producto_crema_id],
        "ruta_descremada": rutas.get(ruta_descremada_id),
        "ruta_crema": rutas.get(ruta_crema_id),
        "destino_descremada": destino_descremada,
        "destino_crema": destino_crema,
        "litros_descremada_plan": Decimal(str(litros_descremada_plan)),
        "litros_crema_plan": Decimal(str(litros_crema_plan)),
        "fuente_plan": sugerencia["fuente_plan"],
        "plan_confirmado_por": usuario,
        "plan_confirmado_en": timezone.now(),
    })
    # Como `EJ-PROD-{lote}` y los lotes `INT-DES-{corrida}-LD/CR`: el código
    # lo pone el servidor, y la tarjeta del puesto se reconoce por él.
    ejecucion.codigo = f"EJ-DES-{corrida.pk}"
    ejecucion.save(update_fields=["codigo"])
    return preparar_descremacion(corrida_id=corrida.pk, usuario=usuario)


def sugerir_plan_descremacion(
    *, analisis, litros_entrada, producto_descremada, producto_crema,
):
    """Sugiere el reparto usando MG de especificaciones vigentes, sin fijarlo."""
    from maestros.models import Especificacion, Producto
    from produccion.dominio import especificacion_vigente
    from .dominio import calcular_balance_descremacion

    if not (
        producto_descremada.tipo == Producto.TipoProducto.DESCREMADA
        and producto_descremada.familia == Producto.Familia.LIQUIDO
        and producto_descremada.naturaleza == Producto.Naturaleza.INTERMEDIO
        and producto_descremada.unidad_base == Producto.Unidad.L
    ):
        raise ValidationError({
            "producto_descremada": (
                "Selecciona leche descremada intermedia, liquida y medida en litros."
            )
        })
    if not (
        producto_crema.familia == Producto.Familia.CREMA
        and producto_crema.naturaleza == Producto.Naturaleza.INTERMEDIO
    ):
        raise ValidationError({"producto_crema": "Selecciona una crema intermedia."})

    hoy = timezone.localdate()
    especificaciones = list(Especificacion.objects.filter(
        producto_id__in=[producto_descremada.pk, producto_crema.pk],
        tipo_analisis=Especificacion.TipoAnalisis.SILO,
        vigente_desde__lte=hoy,
    ))

    def objetivo(producto):
        especificacion = especificacion_vigente(
            especificaciones, producto.pk, hoy, Especificacion.TipoAnalisis.SILO
        )
        if especificacion is None:
            raise ValidationError({
                "especificacion": (
                    f"{producto.nombre} no tiene especificación de silo vigente."
                )
            })
        rango = especificacion.rangos.get("mg", {})
        valor = rango.get("objetivo")
        minimo, maximo = rango.get("min"), rango.get("max")
        if valor is None and minimo is not None and maximo is not None:
            valor = (Decimal(str(minimo)) + Decimal(str(maximo))) / Decimal("2")
        elif valor is None:
            valor = minimo if minimo is not None else maximo
        if valor is None:
            raise ValidationError({
                "especificacion": (
                    f"La especificación v{especificacion.version} de {producto.nombre} "
                    "no define MG objetivo ni rango."
                )
            })
        return Decimal(str(valor)), especificacion

    grasa_descremada, especificacion_descremada = objetivo(producto_descremada)
    grasa_crema, especificacion_crema = objetivo(producto_crema)
    balance = calcular_balance_descremacion(
        litros_entrada, analisis.grasa, analisis.sng,
        grasa_descremada, grasa_crema,
    )
    if balance.descremada_esperada_l is None or balance.crema_esperada_l is None:
        raise ValidationError({"balance": list(balance.avisos)})
    return {
        "litros_descremada_sugeridos": balance.descremada_esperada_l.quantize(Decimal("0.01")),
        "litros_crema_sugeridos": balance.crema_esperada_l.quantize(Decimal("0.01")),
        "grasa_descremada_objetivo": grasa_descremada,
        "grasa_crema_objetivo": grasa_crema,
        "fuente_plan": {
            "metodo": "balance_materia_grasa",
            "especificacion_descremada_id": especificacion_descremada.pk,
            "especificacion_descremada_version": especificacion_descremada.version,
            "especificacion_crema_id": especificacion_crema.pk,
            "especificacion_crema_version": especificacion_crema.version,
            "grasa_descremada_objetivo": str(grasa_descremada),
            "grasa_crema_objetivo": str(grasa_crema),
        },
        "avisos": list(balance.avisos),
        "requiere_confirmacion_operador": True,
    }


def tipos_equipo_para_etapa(tipo_etapa):
    """Tipos físicos válidos para una etapa configurable del proceso."""
    from maestros.models import Equipo

    return {
        EtapaProceso.Tipo.DESCREMACION: {Equipo.Tipo.DESCREMADORA},
        EtapaProceso.Tipo.EVAPORACION: {Equipo.Tipo.EVAPORADOR},
        EtapaProceso.Tipo.CONDENSACION: {Equipo.Tipo.EVAPORADOR},
        EtapaProceso.Tipo.SECADO: {Equipo.Tipo.TORRE},
        EtapaProceso.Tipo.ENVASADO: {Equipo.Tipo.ENVASADORA, Equipo.Tipo.LINEA},
        EtapaProceso.Tipo.MANTEQUILLA: {Equipo.Tipo.MANTEQUERA},
        EtapaProceso.Tipo.TRANSFERENCIA: {Equipo.Tipo.CARGA},
        EtapaProceso.Tipo.OTRO: {Equipo.Tipo.OTRO},
    }.get(tipo_etapa, set())


def etapa_para_producto(*, producto, sucursal, tipo):
    """Obtiene una etapa desde la ruta activa del producto.

    ``sucursal`` se conserva en la firma por compatibilidad con llamadores
    históricos, pero no participa en la navegación productiva.
    """
    return (
        EtapaProceso.objects.filter(
            proceso__rutas_producto__producto=producto,
            proceso__rutas_producto__activa=True,
            proceso__activo=True,
            tipo=tipo,
            activa=True,
        )
        .order_by("proceso__rutas_producto__prioridad", "orden")
        .first()
    )


def ruta_para_etapa(*, producto, sucursal, etapa):
    """Devuelve la ruta del producto que contiene la etapa.

    ``sucursal`` es un argumento legado y no selecciona la ruta funcional.
    """
    return (
        RutaProducto.objects.filter(
            producto=producto,
            proceso=etapa.proceso,
            activa=True,
            proceso__activo=True,
        )
        .order_by("prioridad", "pk")
        .first()
    )


def siguiente_etapa_para_salida(*, salida, etapas_por_proceso=None):
    """Resuelve la continuidad desde la ruta persistida de la salida.

    Una rama puede abandonar el proceso que la produjo (por ejemplo,
    Descremado -> Mantequilla). En ese caso corresponde la primera etapa de
    la ruta elegida, no una etapa posterior del proceso de origen.
    """
    origen = salida.ejecucion.etapa
    ruta = salida.ruta_producto
    if ruta is not None and (
        not ruta.activa
        or (salida.producto_id and ruta.producto_id != salida.producto_id)
    ):
        return None
    proceso_id = ruta.proceso_id if ruta is not None else origen.proceso_id
    if etapas_por_proceso is None:
        etapas = list(
            EtapaProceso.objects.filter(proceso_id=proceso_id, activa=True)
            .order_by("orden", "pk")
        )
    else:
        etapas = etapas_por_proceso.get(proceso_id, [])
    if proceso_id != origen.proceso_id:
        return etapas[0] if etapas else None
    return next((etapa for etapa in etapas if etapa.orden > origen.orden), None)


def notificar_handoff_salida_liberada(salida):
    """Avisa al puesto que realmente puede actuar después de la liberación."""
    from inventario.servicios import _notificar_area
    from usuarios.models import PerfilUsuario

    if salida.destino == SalidaProceso.Destino.ENVASADO:
        area = PerfilUsuario.Area.ENVASE
        accion_url = "/envasado"
        accion = "Envasado ya puede utilizar este material."
    elif salida.destino == SalidaProceso.Destino.DESPACHO_DIRECTO:
        area = PerfilUsuario.Area.DESPACHO
        accion_url = "/despacho"
        accion = "Despacho ya puede preparar la salida a granel."
    else:
        siguiente = siguiente_etapa_para_salida(salida=salida)
        if siguiente is None:
            return
        from .dominio import ruta_de_etapa

        area = (
            PerfilUsuario.Area.SECADO
            if siguiente.tipo == EtapaProceso.Tipo.SECADO
            else PerfilUsuario.Area.CONDENSACION
        )
        accion_url = ruta_de_etapa(siguiente.tipo)
        accion = f"{siguiente.nombre} ya puede preparar la continuación."

    lote = salida.lote.codigo_lote if salida.lote_id else "sin lote asignado"
    _notificar_area(
        area,
        tipo="material_liberado_para_continuar",
        titulo=f"Material liberado para {dict(PerfilUsuario.Area.choices)[area]}",
        mensaje=(
            f"{salida.ejecucion.codigo} · lote {lote} · "
            f"{salida.cantidad} {salida.unidad}. {accion}"
        ),
        documento_tipo="procesos.SalidaProceso",
        documento_id=salida.pk,
        accion_url=accion_url,
    )


def etapas_iniciales_por_producto(*, productos_sucursales, etapa_previa_tipo=None):
    """Resuelve, por ruta y prioridad, dónde puede comenzar una operación.

    Cuando la operación nace desde un hecho previo conocido (por ejemplo, un
    vale ya estandarizado), la etapa inicial es la primera etapa activa
    posterior a ese hecho. Si la ruta no contiene esa etapa previa, comienza
    en su primera etapa activa.
    """
    pares = {(int(producto_id), int(sucursal_id)) for producto_id, sucursal_id in productos_sucursales}
    if not pares:
        return {}

    pares_por_producto = defaultdict(list)
    for par in pares:
        pares_por_producto[par[0]].append(par)

    rutas = (
        RutaProducto.objects.filter(
            producto_id__in={par[0] for par in pares},
            activa=True,
            proceso__activo=True,
        )
        .select_related("proceso")
        .prefetch_related(Prefetch(
            "proceso__etapas",
            queryset=EtapaProceso.objects.order_by("orden", "pk"),
            to_attr="etapas_para_inicio",
        ))
        .order_by("producto_id", "prioridad", "pk")
    )
    resultado = {par: [] for par in pares}
    etapas_vistas = {par: set() for par in pares}
    for ruta in rutas:
        etapas = ruta.proceso.etapas_para_inicio
        orden_previo = None
        if etapa_previa_tipo is not None:
            previa = next(
                (etapa for etapa in etapas if etapa.tipo == etapa_previa_tipo),
                None,
            )
            if previa is not None:
                orden_previo = previa.orden
        inicial = next(
            (
                etapa for etapa in etapas
                if etapa.activa and (orden_previo is None or etapa.orden > orden_previo)
            ),
            None,
        )
        if inicial is not None:
            for par in pares_por_producto[ruta.producto_id]:
                if inicial.pk not in etapas_vistas[par]:
                    resultado[par].append(inicial)
                    etapas_vistas[par].add(inicial.pk)
    return resultado


def etapas_iniciales_para_producto(*, producto, sucursal, etapa_previa_tipo=None):
    """Etapas iniciales válidas de todas las rutas activas del producto."""
    return etapas_iniciales_por_producto(
        productos_sucursales=[(producto.pk, sucursal.pk)],
        etapa_previa_tipo=etapa_previa_tipo,
    ).get((producto.pk, sucursal.pk), [])


def exigir_etapa_inicial_para_producto(
    *, producto, sucursal, tipo, etapa_previa_tipo=None
):
    """Impide comenzar en una etapa posterior de una ruta productiva."""
    iniciales = etapas_iniciales_para_producto(
        producto=producto,
        sucursal=sucursal,
        etapa_previa_tipo=etapa_previa_tipo,
    )
    encontrada = next((etapa for etapa in iniciales if etapa.tipo == tipo), None)
    if encontrada is not None:
        return encontrada

    etiqueta_solicitada = dict(EtapaProceso.Tipo.choices).get(tipo, tipo)
    if iniciales:
        permitidas = ", ".join(dict.fromkeys(etapa.nombre for etapa in iniciales))
        detalle = (
            f"La ruta de {producto.nombre} inicia en {permitidas}; no permite "
            f"comenzar directamente en {etiqueta_solicitada}."
        )
    else:
        detalle = (
            f"{producto.nombre} no tiene una ruta activa con una etapa inicial "
            "disponible. Configura la ruta antes de continuar."
        )
    raise ValidationError({"ruta_producto": detalle})


def exigir_etapa_para_producto(*, producto, sucursal, tipo):
    """Impide iniciar hechos de planta sin una ruta productiva trazable."""
    etapa = etapa_para_producto(producto=producto, sucursal=sucursal, tipo=tipo)
    if etapa is None:
        etiqueta = dict(EtapaProceso.Tipo.choices).get(tipo, tipo)
        raise ValidationError({
            "ruta_producto": (
                f"{producto.nombre} no tiene una ruta activa con la etapa "
                f"{etiqueta} en {sucursal.nombre}. Configura la ruta antes "
                "de continuar."
            )
        })
    return etapa


def destino_salida_de_ruta(*, producto, sucursal, etapa, ruta=None):
    """Decide si el resultado continúa o termina en su destino real."""
    siguiente = EtapaProceso.objects.filter(
        proceso=etapa.proceso, activa=True, orden__gt=etapa.orden,
    ).order_by("orden").first()
    if siguiente is not None:
        if siguiente.tipo == EtapaProceso.Tipo.ENVASADO:
            return SalidaProceso.Destino.ENVASADO
        return SalidaProceso.Destino.SIGUIENTE_PROCESO
    ruta = ruta or ruta_para_etapa(
        producto=producto, sucursal=sucursal, etapa=etapa
    )
    if ruta is not None:
        return ruta.destino_final
    return SalidaProceso.Destino.PENDIENTE


@transaction.atomic
def crear_condensacion_guiada(*, lote_id, silo_destino_id, usuario):
    """Especializa la ejecución de evaporación ya abierta por el lote."""
    from maestros.models import Silo
    from produccion.models import Lote, OrdenProduccion

    lote = Lote.objects.select_for_update(of=("self",)).select_related(
        "orden", "producto", "ejecucion__etapa", "ejecucion__equipo", "sucursal"
    ).get(pk=lote_id)
    if not lote.orden_id:
        raise ValidationError({"lote": "El lote debe pertenecer a una orden estructurada."})
    if lote.orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        raise ValidationError({"lote": "La orden del lote no está programada o en proceso."})
    ejecucion = lote.ejecucion
    if ejecucion is None or ejecucion.etapa.tipo not in {
        EtapaProceso.Tipo.EVAPORACION, EtapaProceso.Tipo.CONDENSACION,
    }:
        raise ValidationError({"lote": "El lote no tiene una ejecución de evaporación."})
    if hasattr(ejecucion, "corrida_condensacion"):
        raise ValidationError({"lote": "La ejecución ya tiene una corrida de evaporación."})
    entrada = ejecucion.entradas.select_related("silo").filter(
        silo__isnull=False, unidad__iexact="L"
    ).order_by("pk").first()
    if entrada is None:
        raise ValidationError({"lote": "La ejecución no tiene una entrada trazable en litros."})
    destino = Silo.objects.select_for_update().get(pk=silo_destino_id)
    if not destino.activo or destino.estado != Silo.Estado.DISPONIBLE:
        raise ValidationError({
            "silo_destino": (
                f"{destino.codigo} no está disponible para recibir el concentrado "
                f"({destino.get_estado_display().lower()})."
            )
        })
    litros_entrada = entrada.cantidad.quantize(Decimal("0.01"))
    motivos = motivos_destino_concentrado(
        destino, litros_entrada, excluir_ejecucion_id=ejecucion.pk,
    )
    if motivos:
        raise ValidationError({"silo_destino": motivos})
    corrida = CorridaCondensacion(
        ejecucion=ejecucion, orden=lote.orden, lote=lote,
        silo_origen=entrada.silo, silo_destino=destino,
        litros_entrada=litros_entrada,
    )
    corrida.full_clean()
    corrida.save()
    EventoProceso.objects.create(
        ejecucion=ejecucion, usuario=usuario, tipo="corrida_configurada",
        estado_anterior=ejecucion.estado, estado_nuevo=ejecucion.estado,
        motivo=f"Evaporación configurada hacia {destino.codigo}",
    )
    return corrida


def filtro_crema_liberada():
    """
    Un lote de crema que Calidad liberó. Si la crema está en un TK, la
    liberación que cuenta es la de **esa** salida (`fuente_tk_de_crema`: la
    primera con silo, por `registrada_en` y `pk`): de ella se lee la densidad
    con que se descuenta el TK, y otra salida liberada del mismo lote no dice
    nada de esa crema. Sin TK, basta que alguna salida esté liberada.

    Una sola condición —con `Exists`, sin multiplicar filas— para la lista
    `cremas` del puesto, «Preparar» y el inicio
    (`motivos_crema_para_mantequilla`): con la condición vieja, «cualquier
    salida liberada», el puesto ofrecía una crema cuyo TK esperaba a Calidad y
    «Preparar» la rechazaba.
    """
    from calidad.models import LiberacionProceso

    liberado = LiberacionProceso.Estado.LIBERADO
    en_tk = Exists(SalidaProceso.objects.filter(lote=OuterRef("pk"), silo__isnull=False))
    primera_en_tk = (
        SalidaProceso.objects.filter(lote=OuterRef(OuterRef("pk")), silo__isnull=False)
        .order_by("registrada_en", "pk").values("pk")[:1]
    )
    tk_liberado = Exists(LiberacionProceso.objects.filter(
        salida_id=Subquery(primera_en_tk), estado=liberado,
    ))
    alguna_liberada = Exists(LiberacionProceso.objects.filter(
        salida__lote=OuterRef("pk"), estado=liberado,
    ))
    return (Q(en_tk) & Q(tk_liberado)) | (~Q(en_tk) & Q(alguna_liberada))


def sueros_libres(consulta=None):
    """
    Los lotes de suero o mazada que una corrida puede tomar: categoría suero,
    en borrador o en proceso, sin kilos y sin una corrida de mantequilla
    **viva** —una `anulada` lo suelta, aunque conserve el rastro—. La usan la
    lista `sueros` del puesto, «Preparar» y `preparar_circuito_mantequilla`.
    """
    from produccion.models import Lote

    consulta = Lote.objects.all() if consulta is None else consulta
    vivas = CorridaMantequilla.objects.filter(lote_suero=OuterRef("pk")).exclude(
        estado=CorridaMantequilla.Estado.ANULADA,
    )
    return consulta.filter(
        producto__categoria="suero",
        estado__in=[Lote.Estado.BORRADOR, Lote.Estado.EN_PROCESO],
        kg_producidos__isnull=True,
    ).exclude(Exists(vivas))


def kg_crema_disponible(lote, *, excluir_corrida_id=None):
    """
    Lo que queda de una crema para una corrida de mantequilla: sus kilos
    producidos menos lo que ya entró a una mantequera (las entradas en kg que
    no son una preparación cancelada) y menos lo que **otras corridas
    preparadas** ya pidieron: corrida `borrador` con su ejecución en
    `preparacion`, que es lo que deja «Preparar». Una corrida heredada o
    huérfana cuya ejecución quedó en `borrador` no tomó la mantequera ni
    compromete crema; una iniciada ya la cuenta por su `EntradaProceso`.

    Una cantidad, una consulta: la usan la lista `cremas` del puesto,
    «Preparar» y el inicio. Sin restar las preparadas, el puesto ofrecía una
    crema que el inicio de la segunda corrida rechazaba (caso 1 de «La
    pantalla ofrece lo que el backend va a rechazar», `CLAUDE.md`).

    La cuenta es una expresión (`expresion_kg_crema_disponible`): el puesto la
    anota sobre todas las cremas en una consulta y aquí se evalúa para una.
    """
    from produccion.models import Lote

    return Lote.objects.filter(pk=lote.pk).annotate(
        disponible=expresion_kg_crema_disponible(excluir_corrida_id=excluir_corrida_id),
    ).values_list("disponible", flat=True).get()


def expresion_kg_crema_disponible(*, excluir_corrida_id=None):
    """
    `kg_crema_disponible` como expresión sobre `Lote`: kilos producidos menos
    las entradas en kg que no son una preparación cancelada, menos el
    `kg_crema` de las otras corridas preparadas.
    """
    decimal = DecimalField(max_digits=20, decimal_places=3)
    cero = Value(Decimal("0"), output_field=decimal)
    utilizado = (
        EntradaProceso.objects.filter(lote=OuterRef("pk"), unidad__iexact="kg")
        .exclude(PREPARACION_CANCELADA)
        .order_by().values("lote").annotate(total=Sum("cantidad")).values("total")
    )
    preparadas = CorridaMantequilla.objects.filter(
        lote_crema=OuterRef("pk"), estado=CorridaMantequilla.Estado.BORRADOR,
        ejecucion__estado=EjecucionProceso.Estado.PREPARACION,
    )
    if excluir_corrida_id is not None:
        preparadas = preparadas.exclude(pk=excluir_corrida_id)
    comprometido = (
        preparadas.order_by().values("lote_crema").annotate(total=Sum("kg_crema")).values("total")
    )
    return ExpressionWrapper(
        Coalesce(F("kg_producidos"), cero)
        - Coalesce(Subquery(utilizado, output_field=decimal), cero)
        - Coalesce(Subquery(comprometido, output_field=decimal), cero),
        output_field=decimal,
    )


def motivos_crema_para_mantequilla(lote, kg, *, excluir_corrida_id=None):
    """
    Por qué `kg` de este lote no pueden entrar a una corrida de mantequilla,
    como pares `(motivo, resolver_en)`. Lista vacía: pueden.

    Lo propio de la crema —familia, estado, liberación, disponible—, que no
    cambia entre preparar e iniciar: «Preparar» rechaza con el primero y el
    inicio los incluye en su lista. Si la crema está en un TK, la liberación
    que cuenta es la de **esa** salida: de ella se lee la densidad con que se
    descuenta el TK, y otra salida liberada del mismo lote no dice nada de esa
    crema. Las condiciones del TK (análisis, firmas, CIP, saldo en litros) no
    están aquí: cambian entre los dos pasos y son solo motivos de inicio.
    """
    from produccion.models import Lote

    if lote.producto.familia != "crema":
        return [(f"El lote {lote.codigo_lote} no es un lote de crema.", None)]
    if lote.estado == Lote.Estado.ANULADO:
        # El material de un lote anulado no se procesa (como en Secado).
        return [(MENSAJE_SALIDA_DE_LOTE_ANULADO.format(codigo=lote.codigo_lote), None)]
    if lote.estado not in {Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO}:
        return [(f"El lote de crema {lote.codigo_lote} todavía no está producido.", None)]
    motivos = []
    # La regla del TK vive en `filtro_crema_liberada`, la misma con que el
    # puesto arma su lista `cremas`.
    if not Lote.objects.filter(pk=lote.pk).filter(filtro_crema_liberada()).exists():
        motivos.append((
            f"El lote de crema {lote.codigo_lote} todavía no está liberado por Calidad.",
            RESOLVER_CALIDAD,
        ))
    pedido = Decimal(str(kg))
    disponible = kg_crema_disponible(lote, excluir_corrida_id=excluir_corrida_id)
    if pedido > disponible:
        motivos.append((
            f"El lote de crema {lote.codigo_lote} tiene {disponible} kg disponibles; "
            f"la corrida pide {pedido} kg.",
            None,
        ))
    return motivos


def fuente_tk_de_crema(lote):
    """
    La salida del lote de crema que está en un TK, si la hay: de ahí sale la
    crema al iniciar (en litros, con la densidad de su liberación). El inicio
    y el puesto (`cremas[].tk`) leen la misma.
    """
    return (
        SalidaProceso.objects.select_related("silo", "liberacion_calidad__analisis_silo")
        .filter(lote=lote, silo__isnull=False)
        .order_by("registrada_en", "pk")
        .first()
    )


def litros_de_crema(kg, densidad):
    """Los litros del TK que corresponden a `kg` de crema con esta densidad (kg/m³)."""
    return (Decimal(str(kg)) * Decimal("1000") / Decimal(str(densidad))).quantize(Decimal("0.01"))


@transaction.atomic
def crear_mantequilla_guiada(
    *, orden_id, lote_crema_id, equipo_id, codigo_lote_mantequilla,
    kg_crema, usuario, lote_suero_id=None,
):
    """
    Prepara una corrida de mantequilla: lote de salida, ejecución y corrida, y
    toma la mantequera (`borrador → preparacion`), en una sola transacción
    —todo o nada: ni lote, ni ejecución, ni corrida, ni máquina ocupada—.

    La crema se valida con las mismas reglas que el inicio
    (`motivos_crema_para_mantequilla`), pero no se mueve: entra a la
    mantequera al iniciar. Las condiciones del TK cambian entre preparar e
    iniciar y son motivos de inicio, con su enlace.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update(of=("self",)).select_related(
        "producto", "sucursal"
    ).get(pk=orden_id)
    crema = (
        Lote.objects.select_for_update(of=("self",)).select_related("producto")
        .get(pk=lote_crema_id)
    )
    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    suero = (
        Lote.objects.select_for_update(of=("self",)).get(pk=lote_suero_id)
        if lote_suero_id else None
    )
    if orden.producto.categoria != "mantequilla":
        raise ValidationError({"orden": "La orden no corresponde a mantequilla."})
    if orden.estado not in {OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO}:
        raise ValidationError({"orden": "La orden no está programada o en proceso."})
    if not equipo.activo:
        raise ValidationError({"equipo": f"{equipo.nombre} no está activa."})
    if equipo.tipo not in tipos_equipo_para_etapa(EtapaProceso.Tipo.MANTEQUILLA):
        raise ValidationError({"equipo": f"{equipo.nombre} no es una mantequera."})
    # Hoy una mantequera en CIP se preparaba y el rechazo llegaba al iniciar.
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})
    motivos = motivos_crema_para_mantequilla(crema, kg_crema)
    if motivos:
        raise ValidationError({"lote_crema": motivos[0][0]})
    if suero is not None and not sueros_libres(Lote.objects.filter(pk=suero.pk)).exists():
        raise ValidationError({
            "lote_suero": (
                f"El lote {suero.codigo_lote} no puede recibir el suero: ya lo tomó otra "
                "corrida, ya tiene kilos o no es un lote de suero."
            )
        })
    etapa = etapa_para_producto(
        producto=orden.producto, sucursal=orden.sucursal,
        tipo=EtapaProceso.Tipo.MANTEQUILLA,
    )
    if etapa is None:
        raise ValidationError({"orden": "El producto no tiene una etapa de mantequilla activa."})
    ruta = ruta_para_etapa(producto=orden.producto, sucursal=orden.sucursal, etapa=etapa)
    codigo = str(codigo_lote_mantequilla).strip()
    if not codigo:
        raise ValidationError({"codigo_lote_mantequilla": "Ingresa el código del lote de salida."})
    lote_salida = Lote(
        sucursal=orden.sucursal, codigo_lote=codigo,
        codigo_lote_propuesto=codigo, op=orden.codigo, orden=orden,
        producto=orden.producto, equipo=equipo, fecha=timezone.localdate(),
        estado=Lote.Estado.EN_PROCESO,
    )
    lote_salida.full_clean()
    lote_salida.save()
    ejecucion = EjecucionProceso(
        codigo=f"EJ-MANT-{lote_salida.pk}", etapa=etapa, ruta_producto=ruta,
        sucursal=orden.sucursal, equipo=equipo, responsable=usuario,
    )
    ejecucion.full_clean()
    ejecucion.save()
    lote_salida.ejecucion = ejecucion
    lote_salida.save(update_fields=["ejecucion"])
    corrida = CorridaMantequilla(
        ejecucion=ejecucion, orden=orden, lote_crema=crema,
        lote_mantequilla=lote_salida, lote_suero=suero,
        kg_crema=Decimal(str(kg_crema)),
    )
    corrida.full_clean()
    corrida.save()
    # Toma la mantequera: `adquirir_equipo` rechaza una ocupada, y la
    # excepción revierte todo lo de arriba.
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario, motivo="Preparación desde el puesto de Mantequilla.",
    )
    return CorridaMantequilla.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto", "lote_suero",
    ).get(pk=corrida.pk)


@transaction.atomic
def preparar_continuacion(*, salida_id, etapa_id, equipo_id, cantidad, usuario):
    """Reserva parte de una salida liberada y prepara su próxima ejecución."""
    from maestros.models import Equipo

    salida = (
        SalidaProceso.objects.select_for_update(of=("self",))
        .select_related(
            "ejecucion__etapa", "ejecucion__sucursal", "silo",
            "ruta_producto__proceso", "liberacion_calidad",
        )
        .get(pk=salida_id)
    )
    try:
        etapa = EtapaProceso.objects.select_related("proceso").get(
            pk=etapa_id, activa=True
        )
    except (EtapaProceso.DoesNotExist, TypeError, ValueError) as error:
        raise ValidationError("La etapa seleccionada no existe o está inactiva.") from error
    if etapa.tipo == EtapaProceso.Tipo.MANTEQUILLA:
        raise ValidationError(MENSAJE_MANTEQUILLA_EN_PUESTO)
    siguiente = siguiente_etapa_para_salida(salida=salida)
    if siguiente is None or etapa.pk != siguiente.pk:
        raise ValidationError(
            "La etapa elegida debe ser la siguiente etapa activa de la ruta; no se pueden saltar procesos."
        )
    if salida.destino not in {
        SalidaProceso.Destino.PENDIENTE,
        SalidaProceso.Destino.SIGUIENTE_PROCESO,
        SalidaProceso.Destino.ESTANDARIZACION,
    }:
        raise ValidationError(
            f"La salida fue destinada a {salida.get_destino_display()} y no puede consumirse como continuación."
        )

    try:
        equipo = Equipo.objects.get(pk=equipo_id, activo=True)
    except (Equipo.DoesNotExist, TypeError, ValueError) as error:
        raise ValidationError("La máquina seleccionada no está activa en esta planta.") from error
    compatibles = tipos_equipo_para_etapa(etapa.tipo)
    if not compatibles:
        raise ValidationError(
            f"La etapa {etapa.nombre} todavía no tiene un tipo de máquina configurado."
        )
    if equipo.tipo not in compatibles:
        raise ValidationError(
            f"{equipo.nombre} no es compatible con la etapa {etapa.nombre}."
        )

    try:
        cantidad = Decimal(str(cantidad))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError("Ingresa una cantidad válida.") from error
    if cantidad <= 0:
        raise ValidationError("La cantidad debe ser mayor que cero.")
    if SalidaProceso.objects.filter(pk=salida.pk).filter(salida_de_lote_anulado()).exists():
        raise ValidationError(
            MENSAJE_SALIDA_DE_LOTE_ANULADO.format(codigo=salida.lote.codigo_lote)
        )
    disponible = disponible_de_salida(salida)
    if cantidad > disponible:
        raise ValidationError(
            f"La salida tiene {disponible} {salida.unidad} disponibles."
        )

    if etapa.tipo == EtapaProceso.Tipo.SECADO:
        # `CorridaSecado.lote` es uno a uno: un lote se seca en una sola
        # corrida. Sin estos dos rechazos, la segunda toma reventaba con un
        # IntegrityError y una salida sin lote dejaba una preparación sin
        # corrida, que el puesto no puede iniciar.
        if not salida.lote_id:
            raise ValidationError(
                "Secado necesita el lote del concentrado: esta salida no tiene lote."
            )
        if CorridaSecado.objects.filter(lote_id=salida.lote_id).exists():
            raise ValidationError(
                f"El lote {salida.lote.codigo_lote} ya tiene una corrida de Secado; "
                "un lote se seca en una sola corrida."
            )
        # Una regla con la alimentación externa (`preparar_secado_desde_
        # inventario`): una torre en CIP no se prepara.
        from inventario.servicios import motivo_equipo_no_habilitado

        impedimento = motivo_equipo_no_habilitado(equipo)
        if impedimento:
            raise ValidationError({"equipo": impedimento})

    ejecucion = EjecucionProceso(
        codigo=f"CONT-{salida.pk}-{uuid.uuid4().hex[:8].upper()}",
        etapa=etapa,
        ruta_producto=salida.ruta_producto,
        sucursal=salida.ejecucion.sucursal,
        equipo=equipo,
        responsable=usuario,
    )
    ejecucion.full_clean()
    ejecucion.save()
    entrada = EntradaProceso(
        ejecucion=ejecucion,
        silo=salida.silo,
        salida_origen=salida,
        cantidad=cantidad,
        unidad=salida.unidad,
    )
    entrada.full_clean()
    entrada.save()
    if salida.lote_id:
        lote = salida.lote
        lote.ejecucion = ejecucion
        lote.equipo = equipo
        lote.save(update_fields=["ejecucion", "equipo"])
        if etapa.tipo == EtapaProceso.Tipo.SECADO:
            CorridaSecado.objects.get_or_create(
                ejecucion=ejecucion,
                defaults={"orden": lote.orden, "lote": lote},
            )
    if salida.destino == SalidaProceso.Destino.PENDIENTE:
        salida.destino = SalidaProceso.Destino.SIGUIENTE_PROCESO
        salida.save(update_fields=["destino"])
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario,
        motivo=f"Continuación de {salida.ejecucion.codigo}",
    )


def bloquear_para_cancelar(ejecucion_id):
    """
    Los candados de una cancelación, en el orden de los puestos.

    Mismo orden que `iniciar_secado`/`cancelar_preparacion_secado`,
    `iniciar_condensacion`/`cancelar_preparacion_evaporacion`,
    `iniciar_descremacion`/`cancelar_preparacion_descremacion` e
    `iniciar_mantequilla`/`cancelar_preparacion_mantequilla`: la corrida
    especializada primero, la ejecución después. Cancelar una preparación la
    borra o la cancela (`_deshacer_preparacion_secado`,
    `_deshacer_preparacion_evaporacion`); si este camino tomara la ejecución
    antes, un inicio y una cancelación simultáneos se esperarían el uno al
    otro en orden cruzado (deadlock). Sin corrida —otras etapas— la consulta
    no bloquea nada; para quien ya la tiene, retomarla en la misma
    transacción no espera. Solo vale dentro de una transacción.
    """
    for modelo in (
        CorridaSecado, CorridaCondensacion, CorridaDescremacion, CorridaMantequilla,
    ):
        list(
            modelo.objects.select_for_update(of=("self",))
            .filter(ejecucion_id=ejecucion_id).values_list("pk", flat=True)
        )
    list(
        EjecucionProceso.objects.select_for_update(of=("self",))
        .filter(pk=ejecucion_id).values_list("pk", flat=True)
    )


@transaction.atomic
def transicionar_ejecucion(
    *, ejecucion_id, estado_nuevo, usuario, motivo="", version_esperada=None
):
    if estado_nuevo == EjecucionProceso.Estado.CANCELADA:
        bloquear_para_cancelar(ejecucion_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update()
        .select_related("etapa")
        .get(pk=ejecucion_id)
    )
    if version_esperada is not None and ejecucion.version != version_esperada:
        raise ConflictoVersionEjecucion(version_actual=ejecucion.version)
    permitidos = EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set())
    if estado_nuevo not in permitidos:
        raise ValidationError(
            f"No se puede pasar de {ejecucion.get_estado_display()} a {estado_nuevo}."
        )

    if estado_nuevo in ESTADOS_QUE_OCUPAN_EQUIPO and ejecucion.equipo_id:
        if not usuario:
            raise ValidationError(
                "Para reservar o iniciar se requiere equipo y usuario responsable."
            )
        ejecucion.equipo = adquirir_equipo(
            equipo_id=ejecucion.equipo_id,
            ejecucion_id=ejecucion.pk,
        )
    elif estado_nuevo in {
        EjecucionProceso.Estado.PREPARACION,
        EjecucionProceso.Estado.EJECUCION,
    }:
        raise ValidationError(
            "Para reservar o iniciar se requiere equipo y usuario responsable."
        )

    if estado_nuevo == EjecucionProceso.Estado.EJECUCION:
        if not ejecucion.entradas.exists():
            raise ValidationError("Para iniciar se requiere al menos una entrada de proceso.")

        # Reglas de planta 3 y 15: no se produce en un equipo que está en CIP
        # ni en uno cuyo último aseo quedó observado. La primera es física
        # antes que informática — hay soda circulando por dentro.
        from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado

        # Ojo con el nombre: `motivo` es el parámetro de esta función —el
        # porqué de la transición, que va al evento—. Llamar igual a esta
        # variable lo pisaba con `None` y el evento quedaba sin motivo.
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)

        if impedimento:
            raise ValidationError(impedimento)

        advertencia_aseo = advertencia_aseo_equipo(ejecucion.equipo)
        if advertencia_aseo and not motivo.strip():
            motivo = f"Advertencia no bloqueante de aseo: {advertencia_aseo}"

        if ejecucion.inicio is None:
            ejecucion.inicio = timezone.now()

    if estado_nuevo == EjecucionProceso.Estado.CERRADA:
        if not ejecucion.salidas.exists():
            raise ValidationError("No se puede cerrar sin registrar una salida o merma.")
        ejecucion.termino = timezone.now()

    if estado_nuevo in {
        EjecucionProceso.Estado.BLOQUEADA,
        EjecucionProceso.Estado.CANCELADA,
    } and not motivo.strip():
        raise ValidationError("Esta transición requiere un motivo.")

    anterior = ejecucion.estado
    ejecucion.estado = estado_nuevo
    ejecucion.version += 1
    ejecucion.save()
    if (
        estado_nuevo == EjecucionProceso.Estado.CANCELADA
        and anterior == EjecucionProceso.Estado.PREPARACION
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.SECADO
    ):
        # Aquí y no en la acción del puesto: cancelar desde la bandeja
        # genérica tiene que soltar el concentrado igual.
        _deshacer_preparacion_secado(ejecucion, motivo, usuario)
    if estado_nuevo == EjecucionProceso.Estado.CANCELADA and ejecucion.etapa.tipo in {
        EtapaProceso.Tipo.EVAPORACION, EtapaProceso.Tipo.CONDENSACION,
    }:
        # Igual que Secado: por el puesto, por la bandeja genérica o al
        # anular el lote, una corrida preparada devuelve su leche.
        _deshacer_preparacion_evaporacion(ejecucion, motivo, usuario)
    if (
        estado_nuevo == EjecucionProceso.Estado.CANCELADA
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.DESCREMACION
    ):
        # Por el puesto o por la bandeja genérica, cancelar deja lo mismo.
        _deshacer_preparacion_descremacion(ejecucion, motivo)
    if (
        estado_nuevo == EjecucionProceso.Estado.CANCELADA
        and ejecucion.etapa.tipo == EtapaProceso.Tipo.MANTEQUILLA
    ):
        # Por el puesto, por la bandeja genérica o al anular el lote,
        # cancelar deja lo mismo.
        _deshacer_preparacion_mantequilla(ejecucion, motivo, usuario)
    if estado_nuevo == EjecucionProceso.Estado.CANCELADA:
        actualizar_queryset_con_auditoria(
            ReservaSiloProceso.objects.filter(
                ejecucion=ejecucion,
                estado=ReservaSiloProceso.Estado.ACTIVA,
            ),
            estado=ReservaSiloProceso.Estado.LIBERADA,
            cerrada_en=timezone.now(),
        )
    EventoProceso.objects.create(
        ejecucion=ejecucion,
        tipo="cambio_estado",
        estado_anterior=anterior,
        estado_nuevo=estado_nuevo,
        motivo=motivo,
        usuario=usuario,
    )
    return ejecucion


@transaction.atomic
def definir_destino_salida(
    *, salida_id, destino, destino_anterior, operacion_id, usuario
):
    """Define un destino con bloqueo, control optimista e idempotencia."""
    try:
        operacion_id = uuid.UUID(str(operacion_id))
    except (TypeError, ValueError, AttributeError) as error:
        raise ValidationError("La clave de operación no es válida.") from error

    salida = (
        SalidaProceso.objects.select_for_update(of=("self",))
        .select_related("ejecucion")
        .get(pk=salida_id)
    )
    evento_existente = EventoProceso.objects.filter(
        operacion_id=operacion_id
    ).first()
    if evento_existente:
        datos = evento_existente.datos
        if datos.get("salida_id") != salida.pk or datos.get("destino") != destino:
            raise ValidationError("La clave de operación ya fue usada para otra decisión.")
        return salida

    if destino_anterior != salida.destino:
        raise ValidationError(
            "El destino cambió desde que abriste la pantalla. Actualiza antes de decidir."
        )
    if destino not in salida.destinos_permitidos():
        raise ValidationError("El destino no es compatible con este producto intermedio.")
    # Una preparación cancelada no tomó nada (`PREPARACION_CANCELADA`): la
    # salida queda libre para cambiar de destino, igual que en su saldo.
    if (
        salida.usos_como_origen.exclude(PREPARACION_CANCELADA).exists()
        and destino != SalidaProceso.Destino.SIGUIENTE_PROCESO
    ):
        raise ValidationError(
            "La salida ya fue consumida por otro proceso y no puede cambiar de destino."
        )
    if salida.detalles_despacho_granel.exclude(
        despacho__estado="cancelado"
    ).exists() and destino != SalidaProceso.Destino.DESPACHO_DIRECTO:
        raise ValidationError(
            "La salida ya forma parte de un despacho y no puede cambiar de destino."
        )

    salida.destino = destino
    salida.save(update_fields=["destino"])
    EventoProceso.objects.create(
        ejecucion=salida.ejecucion,
        tipo="destino_salida_definido",
        datos={
            "salida_id": salida.pk,
            "destino_anterior": destino_anterior,
            "destino": destino,
        },
        usuario=usuario,
        operacion_id=operacion_id,
    )
    return salida


def genealogia_lote(lote_id, direccion, profundidad_maxima=12):
    from produccion.models import Lote
    from .models import EntradaProceso, SalidaProceso

    if direccion not in {"atras", "adelante"}:
        raise ValueError("Dirección inválida.")

    def serializar_nodo(lote):
        return {
            "id": lote.id,
            "codigo": lote.codigo_lote,
            "producto": lote.producto.nombre,
            "fecha": lote.fecha,
            "estado": lote.get_estado_display(),
            "cantidad": lote.kg_producidos,
            "unidad": "kg" if lote.kg_producidos is not None else None,
        }

    # Empresa y Sucursal son campos heredados de persistencia. La genealogía
    # sigue relaciones productivas reales y nunca corta una cadena por ellos.
    lotes = Lote.objects.select_related("producto")
    raiz = lotes.get(pk=int(lote_id))
    visitados = {raiz.id}
    frontera = [raiz]
    nodos = {raiz.id: serializar_nodo(raiz)}
    enlaces = []

    # Una consulta por nivel, no por nodo. En un proceso con varias entradas
    # o coproductos, el recorrido anterior volvía a consultar el lote y sus
    # relaciones para cada rama, de modo que el costo crecía con el ancho del
    # grafo. El JOIN devuelve a la vez el vecino y el extremo de la arista.
    for _profundidad in range(max(0, profundidad_maxima)):
        if not frontera:
            break
        ids_actuales = [lote.id for lote in frontera]
        if direccion == "atras":
            relaciones = EntradaProceso.objects.filter(
                ejecucion__salidas__lote_id__in=ids_actuales,
                lote_id__isnull=False,
            ).annotate(
                actual_relacion_id=F("ejecucion__salidas__lote_id"),
                salida_relacion_id=F("ejecucion__salidas__id"),
                salida_cantidad=F("ejecucion__salidas__cantidad"),
                salida_unidad=F("ejecucion__salidas__unidad"),
                salida_naturaleza=F("ejecucion__salidas__naturaleza"),
                salida_destino=F("ejecucion__salidas__destino"),
            ).select_related("lote__producto", "ejecucion__etapa", "ejecucion__equipo")
            relaciones = relaciones.order_by(
                "ejecucion__salidas__id", "id"
            )
        else:
            relaciones = SalidaProceso.objects.filter(
                ejecucion__entradas__lote_id__in=ids_actuales,
                lote_id__isnull=False,
            ).annotate(
                actual_relacion_id=F("ejecucion__entradas__lote_id"),
                entrada_relacion_id=F("ejecucion__entradas__id"),
                entrada_cantidad=F("ejecucion__entradas__cantidad"),
                entrada_unidad=F("ejecucion__entradas__unidad"),
                entrada_tipo=F("ejecucion__entradas__tipo"),
            ).select_related("lote__producto", "ejecucion__etapa", "ejecucion__equipo")
            relaciones = relaciones.order_by(
                "ejecucion__entradas__id", "id"
            )

        # Se guarda la relación completa, no solo el lote vecino: con dos
        # entradas o salidas para el mismo lote actual, cada enlace necesita
        # su propia cantidad y ejecución, y no la última que haya recorrido
        # este bucle.
        por_actual = {actual_id: [] for actual_id in ids_actuales}
        for relacion in relaciones:
            por_actual[relacion.actual_relacion_id].append(relacion)

        siguiente = {}
        for actual_id in ids_actuales:
            for relacion in por_actual[actual_id]:
                relacionado = relacion.lote
                origen, destino = (
                    (relacionado.id, actual_id)
                    if direccion == "atras"
                    else (actual_id, relacionado.id)
                )
                if direccion == "atras":
                    entrada = {
                        "id": relacion.pk,
                        "cantidad": relacion.cantidad,
                        "unidad": relacion.unidad,
                        "tipo": relacion.get_tipo_display(),
                    }
                    salida = {
                        "id": relacion.salida_relacion_id,
                        "cantidad": relacion.salida_cantidad,
                        "unidad": relacion.salida_unidad,
                        "naturaleza": dict(SalidaProceso.Naturaleza.choices).get(
                            relacion.salida_naturaleza, relacion.salida_naturaleza
                        ),
                        "destino": dict(SalidaProceso.Destino.choices).get(
                            relacion.salida_destino, relacion.salida_destino
                        ),
                    }
                else:
                    entrada = {
                        "id": relacion.entrada_relacion_id,
                        "cantidad": relacion.entrada_cantidad,
                        "unidad": relacion.entrada_unidad,
                        "tipo": dict(EntradaProceso.Tipo.choices).get(
                            relacion.entrada_tipo, relacion.entrada_tipo
                        ),
                    }
                    salida = {
                        "id": relacion.pk,
                        "cantidad": relacion.cantidad,
                        "unidad": relacion.unidad,
                        "naturaleza": relacion.get_naturaleza_display(),
                        "destino": relacion.get_destino_display(),
                    }
                enlaces.append({
                    "origen": origen,
                    "destino": destino,
                    "ejecucion": {
                        "id": relacion.ejecucion_id,
                        "codigo": relacion.ejecucion.codigo,
                        "etapa": relacion.ejecucion.etapa.nombre,
                        "tipo": relacion.ejecucion.etapa.tipo,
                        "equipo": (
                            relacion.ejecucion.equipo.nombre
                            if relacion.ejecucion.equipo_id else None
                        ),
                    },
                    "entrada": entrada,
                    "salida": salida,
                })
                if relacionado.id in visitados:
                    continue
                visitados.add(relacionado.id)
                nodos[relacionado.id] = serializar_nodo(relacionado)
                siguiente[relacionado.id] = relacionado
        frontera = list(siguiente.values())

    return {"nodos": list(nodos.values()), "enlaces": enlaces}


@transaction.atomic
def registrar_estandarizacion(*, vale):
    """
    Deja el vale registrado como una ejecución de la etapa «Estandarización».

    **Un vale es una ejecución de esa etapa**, no algo que la acompaña: son el
    mismo hecho de planta visto desde dos sitios. El vale lleva la receta y el
    RC; la ejecución lleva el lugar en la cadena, que es lo que después responde
    de qué salió un saco.

    Se registra cuando el vale **se transfiere**, que es cuando la mezcla ocurre
    de verdad: antes de eso el vale es un cálculo, y una ejecución de algo que
    no pasó ensucia la trazabilidad con corridas que nunca existieron.

    Las entradas son **silos**, no lotes: esa leche todavía no es de ningún
    lote. La salida es el silo de destino, por lo mismo.

    Idempotente: si el vale ya tiene su ejecución, la devuelve. Transferir es
    una acción única, pero un reintento no debería duplicar la corrida.
    """
    from .models import EntradaProceso, EtapaProceso, SalidaProceso

    existente = EjecucionProceso.objects.filter(vale=vale).first()

    if existente is not None:
        return existente

    etapa = exigir_etapa_para_producto(
        producto=vale.producto,
        sucursal=vale.silo_destino.sucursal,
        tipo=EtapaProceso.Tipo.ESTANDARIZACION,
    )

    ejecucion = EjecucionProceso.objects.create(
        codigo=f"EJ-{vale.codigo}",
        etapa=etapa,
        sucursal=vale.silo_destino.sucursal,
        responsable=vale.responsable,
        vale=vale,
        estado=EjecucionProceso.Estado.EJECUCION,
        inicio=timezone.now(),
    )

    EntradaProceso.objects.create(
        ejecucion=ejecucion,
        silo=vale.silo_entera,
        tipo=EntradaProceso.Tipo.PRINCIPAL,
        cantidad=vale.litros_entera,
        unidad="L",
    )

    if vale.silo_descremada_id and vale.litros_descremada:
        EntradaProceso.objects.create(
            ejecucion=ejecucion,
            silo=vale.silo_descremada,
            tipo=EntradaProceso.Tipo.MEZCLA,
            cantidad=vale.litros_descremada,
            unidad="L",
        )
    if vale.silo_crema_id and vale.litros_crema:
        EntradaProceso.objects.create(
            ejecucion=ejecucion,
            silo=vale.silo_crema,
            tipo=EntradaProceso.Tipo.MEZCLA,
            cantidad=vale.litros_crema,
            unidad="L",
        )

    SalidaProceso.objects.create(
        ejecucion=ejecucion,
        silo=vale.silo_destino,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
        destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
        cantidad=vale.volumen,
        unidad="L",
    )

    return ejecucion


@transaction.atomic
def cerrar_estandarizacion(*, vale):
    """
    Cierra la ejecución del vale cuando su RC quedó conforme.

    El cierre es lo que dice que la etapa terminó bien. Un vale que se va a
    corrección **no cierra**: sigue en ejecución, que es exactamente lo que
    está pasando en el silo.
    """
    ejecucion = EjecucionProceso.objects.filter(vale=vale).first()

    if ejecucion is None or ejecucion.estado == EjecucionProceso.Estado.CERRADA:
        return ejecucion

    ejecucion.estado = EjecucionProceso.Estado.CERRADA
    ejecucion.termino = timezone.now()
    ejecucion.save(update_fields=["estado", "termino"])

    return ejecucion


def motivos_para_iniciar_condensacion(corrida, *, origen=None, destino=None):
    """
    Lo que impide iniciar esta corrida, en el orden en que el inicio lo
    comprueba. Lista vacía: se puede iniciar.

    Es la única implementación de esas reglas: `iniciar_condensacion` lanza el
    primer motivo, y el puesto de Evaporación los muestra junto a un botón
    deshabilitado. Con dos copias, la pantalla habilitaría «Iniciar» sobre una
    corrida que el servidor rechaza.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from produccion.models import OrdenProduccion
    from recepcion.servicios import motivos_silo_no_disponible

    origen = origen or corrida.silo_origen
    destino = destino or corrida.silo_destino
    motivos = []
    if corrida.orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        motivos.append("La orden debe estar programada o en proceso.")
    if not corrida.ejecucion.equipo_id:
        motivos.append("La corrida requiere un evaporador asignado.")
    else:
        impedimento = motivo_equipo_no_habilitado(corrida.ejecucion.equipo)
        if impedimento:
            motivos.append(impedimento)
    motivos_silo = motivos_silo_no_disponible(origen, para="proceso")
    if motivos_silo:
        motivos.append(f"{origen.codigo}: " + " ".join(motivos_silo))
    if reservas_activas_silo(
        silo_id=origen.pk, tipo=ReservaSiloProceso.Tipo.DESTINO,
        excluir_ejecucion_id=corrida.ejecucion_id,
    ).exists():
        motivos.append(f"{origen.codigo} esta reservado como destino de otra ejecucion.")
    motivos.extend(motivos_destino_concentrado(
        destino, corrida.litros_entrada, excluir_ejecucion_id=corrida.ejecucion_id,
    ))
    return motivos


def estado_puesto_evaporacion(usuario):
    """
    Lo que el puesto de Evaporación dibuja: un estado por evaporador, derivado
    de una sola corrida (la en proceso manda sobre la preparada), con los
    motivos que impiden iniciarla calculados por la misma función que decide
    al iniciar; los destinos que el cierre aceptará; y las corridas de hoy.

    `en_calidad` es aparte de `corrida`: una corrida nueva preparada en el
    mismo evaporador no oculta que la anterior sigue esperando a Calidad —la
    máquina física está libre para empezar, pero el destino de esa corrida
    anterior puede seguir bloqueado. Cuando la fila misma está
    `esperando_calidad`, `en_calidad` es esa misma corrida.

    `bloqueo_silo_origen` nombra el silo cuando el motivo de una preparada es
    el silo de origen y no otra cosa (equipo, orden, destino): la pantalla
    ofrece «Analizar silo» solo ahí. Adivinarlo leyendo el texto del motivo
    se habría roto con el primer cambio de redacción; esto lo tipa en vez de
    describirlo en prosa.

    Una corrida `borrador`/`en_proceso` cuya ejecución ya terminó
    (`cerrada`/`cancelada`) es un huérfano —de un E2E abortado o de datos
    viejos— y no cuenta como ocupación: la máquina física ya quedó libre
    aunque la corrida nunca se puso al día. No se reutiliza
    `ESTADOS_QUE_OCUPAN_EQUIPO` tal cual porque esa lista excluye `borrador`
    (y esta función sí trata un borrador como preparación legítima, igual
    que `FlujoCondensacionTests` siembra su ejecución); lo único que de
    verdad libera el equipo aquí es que la ejecución haya llegado a un
    estado terminal (`ESTADOS_EJECUCION_TERMINALES`, el mismo criterio que
    saca a los huérfanos de `corridas_de_hoy`). Anular un lote cancela su
    ejecución (`produccion.servicios.anular_lote`, caso 3 de «La pantalla
    ofrece lo que el backend va a rechazar», `CLAUDE.md`), así que un lote
    anulado ya no deja la máquina ocupada por este camino.
    """
    from maestros.models import Equipo, Silo
    from recepcion.servicios import motivos_silo_no_disponible
    from usuarios.tenancy import filtrar_por_scope

    equipos = filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.EVAPORADOR).order_by("nombre"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    )
    corridas = CorridaCondensacion.objects.select_related(
        "ejecucion__equipo", "orden", "lote", "silo_origen", "silo_destino",
    ).filter(ejecucion__equipo__in=equipos)
    activas = {}
    for corrida in corridas.filter(
        estado__in=[CorridaCondensacion.Estado.EN_PROCESO, CorridaCondensacion.Estado.BORRADOR]
    ).exclude(
        ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES
    ).order_by("pk"):
        actual = activas.get(corrida.ejecucion.equipo_id)
        if actual is None or (
            corrida.estado == CorridaCondensacion.Estado.EN_PROCESO
            and actual.estado != CorridaCondensacion.Estado.EN_PROCESO
        ):
            activas[corrida.ejecucion.equipo_id] = corrida
    esperando = {
        corrida.ejecucion.equipo_id: corrida
        for corrida in corridas.filter(
            ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL
        ).order_by("pk")
    }

    def resumen(corrida):
        return {
            "id": corrida.pk, "codigo": corrida.ejecucion.codigo,
            "lote_codigo": corrida.lote.codigo_lote if corrida.lote_id else None,
            "silo_origen": corrida.silo_origen.codigo,
            "silo_destino": corrida.silo_destino.codigo,
            # Texto, como en los serializers: el tipo del frontend es `string`.
            "litros_entrada": str(corrida.litros_entrada),
            "iniciada_en": corrida.iniciada_en,
        }

    def resumen_en_calidad(corrida):
        return {
            "id": corrida.pk, "codigo": corrida.ejecucion.codigo,
            "lote_codigo": corrida.lote.codigo_lote if corrida.lote_id else None,
        }

    evaporadores = []
    for equipo in equipos:
        corrida = activas.get(equipo.pk)
        corrida_en_calidad = esperando.get(equipo.pk)
        if corrida is not None:
            en_curso = corrida.estado == CorridaCondensacion.Estado.EN_PROCESO
            estado = "en_curso" if en_curso else "preparada"
            motivos = [] if en_curso else motivos_para_iniciar_condensacion(corrida)
            bloqueo_silo_origen = None
            if not en_curso and motivos_silo_no_disponible(corrida.silo_origen, para="proceso"):
                bloqueo_silo_origen = corrida.silo_origen.codigo
        elif corrida_en_calidad is not None:
            corrida, estado, motivos, bloqueo_silo_origen = corrida_en_calidad, "esperando_calidad", [], None
        else:
            estado, motivos, bloqueo_silo_origen = "disponible", [], None
        evaporadores.append({
            "equipo_id": equipo.pk, "codigo": equipo.codigo, "nombre": equipo.nombre,
            "estado": estado,
            "corrida": resumen(corrida) if corrida is not None else None,
            "en_calidad": (
                resumen_en_calidad(corrida_en_calidad)
                if corrida_en_calidad is not None else None
            ),
            "motivos_para_iniciar": motivos,
            "bloqueo_silo_origen": bloqueo_silo_origen,
        })

    # Un silo con una reserva activa no se ofrece: `exigir_destino_sin_reserva`
    # lo rechaza entero, sin importar cuántos litros queden libres, así que
    # restarle lo reservado al `libre_l` seguiría ofreciendo un destino que el
    # backend no acepta. Las corridas solo preparadas no reservan (la reserva
    # nace al iniciar), y la capacidad la vuelve a comprobar
    # `crear_condensacion_guiada` con el saldo bloqueado.
    reservados = ReservaSiloProceso.objects.filter(
        silo=OuterRef("pk"), estado=ReservaSiloProceso.Estado.ACTIVA,
    )
    destinos = [
        {
            "id": silo.pk, "codigo": silo.codigo,
            "libre_l": str(silo.capacidad_l - silo.saldo_l),
        }
        for silo in filtrar_por_scope(
            silos_con_saldo(
                Silo.objects.filter(activo=True, estado=Silo.Estado.DISPONIBLE)
                .exclude(Exists(reservados))
            ).order_by("codigo"),
            usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )
    ]

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.nombre if corrida.ejecucion.equipo_id else None,
            "lote_codigo": corrida.lote.codigo_lote if corrida.lote_id else None,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
        }
        for corrida in corridas.filter(
            Q(iniciada_en__date=hoy) | Q(finalizada_en__date=hoy)
            | Q(
                estado=CorridaCondensacion.Estado.BORRADOR,
                ejecucion__creada_en__date=hoy,
            )
        ).exclude(
            # Mismo criterio que la ocupación de arriba: un huérfano no es
            # trabajo del día, ni preparado ni «En proceso».
            estado__in=[
                CorridaCondensacion.Estado.BORRADOR, CorridaCondensacion.Estado.EN_PROCESO,
            ],
            ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES,
        ).order_by("-pk")
    ]
    return {"evaporadores": evaporadores, "destinos": destinos, "corridas_de_hoy": corridas_de_hoy}


@transaction.atomic
def iniciar_condensacion(*, corrida_id, usuario):
    from maestros.models import Silo
    from produccion.models import OrdenProduccion
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import saldo_silo
    from .models import EntradaProceso

    corrida = CorridaCondensacion.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
        "silo_origen", "silo_destino",
    ).get(pk=corrida_id)
    # La ejecución también se bloquea. Una corrida puede especializar la que
    # abrió el lote; sin este bloqueo podría cerrarse mientras decidimos si la
    # adoptamos o la iniciamos.
    corrida.ejecucion = EjecucionProceso.objects.select_for_update(
        of=("self",)
    ).select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    if corrida.estado != CorridaCondensacion.Estado.BORRADOR:
        raise ValidationError("Solo una corrida en borrador puede iniciarse.")
    corrida.clean()

    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=[
            corrida.silo_origen_id, corrida.silo_destino_id,
        ]).order_by("pk")
    }
    origen = silos[corrida.silo_origen_id]
    destino = silos[corrida.silo_destino_id]
    motivos = motivos_para_iniciar_condensacion(corrida, origen=origen, destino=destino)
    if motivos:
        raise ValidationError(motivos[0])

    # Tras integrar el lote con el motor de procesos aparecieron dos caminos
    # representando el mismo hecho: abrir el lote ya consumía el silo y dejaba
    # su ejecución activa; luego la corrida intentaba consumir y arrancar otra
    # vez. Si esta corrida especializa ESA ejecución, adopta su entrada y su
    # movimiento. No es idempotencia por casualidad: es una sola ejecución
    # física con un registro genérico y otro especializado.
    consumo_del_lote = MovimientoSilo.objects.filter(
        Q(lote_id=corrida.lote_id)
        | Q(
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=corrida.lote_id,
        ),
        silo=origen,
        tipo=MovimientoSilo.Tipo.SALIDA,
    ).first()
    adopta_ejecucion_del_lote = (
        corrida.lote.ejecucion_id == corrida.ejecucion_id
        and corrida.ejecucion.estado == EjecucionProceso.Estado.EJECUCION
    )

    if adopta_ejecucion_del_lote:
        if consumo_del_lote is None:
            raise ValidationError(
                "La ejecución del lote ya está activa, pero no tiene su consumo "
                "de silo. Corrige esa inconsistencia antes de iniciar la condensación."
            )
        if consumo_del_lote.litros != corrida.litros_entrada:
            raise ValidationError({
                "litros_entrada": (
                    f"El lote ya consumió {consumo_del_lote.litros} L; la corrida "
                    f"declara {corrida.litros_entrada} L. Deben coincidir."
                )
            })
        entrada = EntradaProceso.objects.filter(
            ejecucion=corrida.ejecucion,
            silo=origen,
            cantidad=corrida.litros_entrada,
            unidad="L",
        ).first()
        if entrada is None:
            raise ValidationError(
                "La ejecución del lote ya está activa, pero no tiene la entrada "
                "de proceso que corresponde al consumo del silo."
            )
    else:
        disponible = saldo_silo(origen) - litros_origen_reservados(
            silo_id=origen.pk, excluir_ejecucion_id=corrida.ejecucion_id,
        )
        if corrida.litros_entrada > disponible:
            raise ValidationError(
                f"{origen.codigo} tiene {disponible} L; la corrida requiere {corrida.litros_entrada} L."
            )

        consumo_del_lote = MovimientoSilo.objects.create(
            silo=origen, silo_contraparte=corrida.silo_destino,
            tipo=MovimientoSilo.Tipo.SALIDA, litros=corrida.litros_entrada,
            fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=corrida.pk, operacion_id=corrida.operacion_id,
            lote=corrida.lote, producto=corrida.lote.producto,
            equipo=corrida.ejecucion.equipo, usuario=usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=corrida.ejecucion, silo=origen,
            cantidad=corrida.litros_entrada, unidad="L",
        )
        if corrida.ejecucion.estado == EjecucionProceso.Estado.BORRADOR:
            transicionar_ejecucion(
                ejecucion_id=corrida.ejecucion_id,
                estado_nuevo=EjecucionProceso.Estado.PREPARACION,
                usuario=usuario,
            )
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.EJECUCION,
            usuario=usuario,
        )
    ReservaSiloProceso.objects.create(
        ejecucion=corrida.ejecucion,
        silo=destino,
        producto=corrida.lote.producto,
        tipo=ReservaSiloProceso.Tipo.DESTINO,
        cantidad_planificada=corrida.litros_entrada,
    )
    corrida.estado = CorridaCondensacion.Estado.EN_PROCESO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    if corrida.orden.estado == OrdenProduccion.Estado.PROGRAMADA:
        corrida.orden.estado = OrdenProduccion.Estado.EN_PROCESO
        corrida.orden.save(update_fields=["estado"])
    return corrida


@transaction.atomic
def cerrar_condensacion(*, corrida_id, usuario, litros_precondensado, controles):
    from maestros.models import Silo
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import heredar_atribuciones, saldo_silo
    from .models import SalidaProceso

    corrida = CorridaCondensacion.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "lote__producto", "silo_destino"
    ).get(pk=corrida_id)
    if corrida.estado != CorridaCondensacion.Estado.EN_PROCESO:
        raise ValidationError("Solo una condensación en proceso puede cerrarse.")
    cantidad = Decimal(str(litros_precondensado))
    if cantidad <= 0:
        raise ValidationError({"litros_precondensado": "Debe ser mayor que cero."})
    destino = Silo.objects.select_for_update().get(pk=corrida.silo_destino_id)
    if not destino.activo or destino.estado in {
        Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
    }:
        raise ValidationError(f"{destino.codigo} no admite el precondensado.")
    if saldo_silo(destino) + cantidad > destino.capacidad_l:
        raise ValidationError("El precondensado excedería la capacidad del destino.")
    reserva_destino = ReservaSiloProceso.objects.select_for_update().filter(
        ejecucion=corrida.ejecucion,
        silo=destino,
        tipo=ReservaSiloProceso.Tipo.DESTINO,
        estado=ReservaSiloProceso.Estado.ACTIVA,
    ).first()
    if reserva_destino is not None and cantidad > reserva_destino.cantidad_planificada:
        raise ValidationError({
            "litros_precondensado": (
                f"La salida supera los {reserva_destino.cantidad_planificada} L "
                "reservados en el destino."
            )
        })

    for campo, valor in controles.items():
        if campo not in {
            "flujo_promedio", "densidad_salida", "solidos_salida",
            "temperatura_salida", "vacio_promedio", "presion_promedio",
        }:
            raise ValidationError({campo: "Control de condensación no reconocido."})
        setattr(corrida, campo, valor)
    corrida.litros_precondensado = cantidad
    ingreso = MovimientoSilo.objects.create(
        silo=destino, silo_contraparte=corrida.silo_origen,
        tipo=MovimientoSilo.Tipo.INGRESO, litros=cantidad,
        fecha_hora=timezone.now(), origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
        origen_id=corrida.pk, operacion_id=corrida.operacion_id,
        lote=corrida.lote, producto=corrida.lote.producto,
        equipo=corrida.ejecucion.equipo, usuario=usuario,
    )
    if reserva_destino is not None:
        reserva_destino.estado = ReservaSiloProceso.Estado.CONSUMIDA
        reserva_destino.cantidad_real = cantidad
        reserva_destino.cerrada_en = timezone.now()
        reserva_destino.save(update_fields=[
            "estado", "cantidad_real", "cerrada_en",
        ])
    consumo = MovimientoSilo.objects.filter(
        Q(lote_id=corrida.lote_id)
        | Q(
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=corrida.lote_id,
        )
        | Q(
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=corrida.pk,
        ),
        silo_id=corrida.silo_origen_id,
        tipo=MovimientoSilo.Tipo.SALIDA,
    ).order_by("fecha_hora", "id").last()
    if consumo is None:
        raise ValidationError(
            "La condensación no tiene un consumo de silo del cual heredar trazabilidad."
        )
    heredar_atribuciones(ingreso, [consumo])
    destino_operativo = destino_salida_de_ruta(
        producto=corrida.lote.producto,
        sucursal=corrida.ejecucion.sucursal,
        etapa=corrida.ejecucion.etapa,
        ruta=corrida.ejecucion.ruta_producto,
    )
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=corrida.lote, silo=destino,
        producto=corrida.lote.producto,
        ruta_producto=corrida.ejecucion.ruta_producto,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=(
            SalidaProceso.Clasificacion.GRANEL
            if destino_operativo == SalidaProceso.Destino.DESPACHO_DIRECTO
            else SalidaProceso.Clasificacion.INTERMEDIO
        ),
        destino=destino_operativo,
        cantidad=cantidad, unidad="L",
    )
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        usuario=usuario,
    )
    if (
        corrida.ejecucion.etapa.requiere_calidad
        or destino_operativo == SalidaProceso.Destino.DESPACHO_DIRECTO
    ):
        corrida.estado = CorridaCondensacion.Estado.PENDIENTE_CALIDAD
        destino.estado = Silo.Estado.BLOQUEADO_CALIDAD
        destino.save(update_fields=["estado"])
    else:
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.CERRADA,
            usuario=usuario,
        )
        corrida.estado = CorridaCondensacion.Estado.CERRADA
    corrida.finalizada_por = usuario
    corrida.finalizada_en = timezone.now()
    corrida.save()
    if destino_operativo == SalidaProceso.Destino.DESPACHO_DIRECTO:
        from produccion.models import OrdenProduccion
        if corrida.orden.estado == OrdenProduccion.Estado.EN_PROCESO:
            corrida.orden.estado = OrdenProduccion.Estado.PENDIENTE_CALIDAD
            corrida.orden.save(update_fields=["estado"])
    return corrida


# Estados en que un estanque no recibe producto ni se procesa desde él. Una
# sola lista para preparar, iniciar, el puesto y `cerrar_descremacion`.
ESTADOS_SILO_SIN_PRODUCTO = frozenset({
    Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
})


def motivos_para_preparar_desde_silo(silo, analisis):
    """
    Por qué no se puede preparar un descremado desde `silo` con `analisis` (el
    último confirmado, `ultimo_analisis_confirmado`). Lista vacía: se puede.

    Solo lo que el **plan** necesita: el silo en servicio y una composición
    vigente. Firmas, inhibidores y la revalidación de 48 h no frenan la
    preparación: son motivos de inicio y la tarjeta los muestra con su enlace,
    como en Evaporación. El puesto ofrece los silos con esta función y
    `crear_descremacion_guiada` rechaza con ella.
    """
    if not silo.activo or silo.estado in ESTADOS_SILO_SIN_PRODUCTO:
        estado = "fuera de servicio" if not silo.activo else silo.get_estado_display().lower()
        return [f"{silo.codigo} está {estado}."]
    if analisis is None:
        return [f"{silo.codigo} no tiene un análisis confirmado: Calidad debe analizarlo."]
    motivos = []
    if not analisis.vigente:
        motivos.append(
            f"{silo.codigo}: "
            + (analisis.motivo_vigencia or "el análisis perdió vigencia; vuelve a muestrear.")
        )
    if analisis.grasa is None or analisis.sng is None:
        motivos.append(
            f"{silo.codigo}: el análisis no tiene grasa y SNG, y sin composición no hay plan."
        )
    return motivos


def litros_libres_origen(origen, *, saldo=None, excluir_ejecucion_id=None):
    """
    Lo que el silo de origen puede entregar a un descremado: su saldo menos lo
    que otras ejecuciones reservaron como origen. `saldo` evita releerlo
    cuando la consulta ya lo trae anotado (`silos_con_saldo`).
    """
    from recepcion.servicios import saldo_silo

    if saldo is None:
        saldo = saldo_silo(origen)
    return saldo - litros_origen_reservados(
        silo_id=origen.pk, excluir_ejecucion_id=excluir_ejecucion_id,
    )


def motivos_origen_descremacion(origen, litros, *, excluir_ejecucion_id=None):
    """
    Si el silo de origen tiene `litros` libres (`litros_libres_origen`). Una
    sola regla para preparar, para iniciar y para lo que el puesto ofrece:
    con dos, el puesto prepararía una corrida que «Iniciar» rechaza.
    """
    libre = litros_libres_origen(origen, excluir_ejecucion_id=excluir_ejecucion_id)
    if libre < Decimal(str(litros)):
        return [f"{origen.codigo} tiene {libre} L libres; la corrida requiere {litros} L."]
    return []


def motivos_destino_descremacion(destino, *, producto=None, litros=None, excluir_ejecucion_id=None):
    """
    Por qué `destino` no puede recibir una rama del descremado. Sin `producto`
    ni `litros` comprueba solo estado y reservas —lo que el puesto usa para
    ofrecer el TK—; con ellos, también mezcla y capacidad, que dependen del
    plan. Preparar, iniciar y el puesto llaman a esta misma función.
    """
    from recepcion.servicios import saldo_silo

    motivos = []
    if not destino.activo or destino.estado in ESTADOS_SILO_SIN_PRODUCTO:
        motivos.append(f"{destino.codigo} no admite producto.")
    reserva = (
        reservas_activas_silo(silo_id=destino.pk, excluir_ejecucion_id=excluir_ejecucion_id)
        .select_related("ejecucion").order_by("pk").first()
    )
    if reserva is not None:
        motivos.append(f"{destino.codigo} ya está reservado por {reserva.ejecucion.codigo}.")
    if producto is None and litros is None:
        return motivos
    saldo = saldo_silo(destino)
    if producto is not None and saldo > 0 and destino.producto_actual_id not in {None, producto.pk}:
        motivos.append(f"{destino.codigo} contiene otro producto y no admite la mezcla.")
    if litros is not None and saldo + Decimal(str(litros)) > destino.capacidad_l:
        motivos.append(f"{destino.codigo} no tiene capacidad para los {litros} L planificados.")
    return motivos


@transaction.atomic
def preparar_descremacion(*, corrida_id, usuario):
    """
    Reserva el silo de origen y los dos TK y toma la descremadora
    (`borrador → preparacion`). Lo llama `crear_descremacion_guiada` al final
    de su transacción: si algo falla no queda corrida, ni reservas, ni máquina
    ocupada. Las reglas son las mismas que vuelve a aplicar el inicio.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Silo

    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .select_related("producto_descremada", "producto_crema").get(pk=corrida_id)
    )
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("equipo").get(pk=corrida.ejecucion_id)
    )
    if (
        corrida.estado != CorridaDescremacion.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.BORRADOR
    ):
        raise ValidationError(f"{ejecucion.codigo} ya no está en borrador: no se vuelve a preparar.")
    if not ejecucion.equipo_id:
        raise ValidationError({"equipo": "La descremación requiere una descremadora asignada."})
    impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})
    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=[
            corrida.silo_entera_id, corrida.silo_descremada_id, corrida.estanque_crema_id,
        ]).order_by("pk")
    }
    origen = silos[corrida.silo_entera_id]
    destino_descremada = silos[corrida.silo_descremada_id]
    destino_crema = silos[corrida.estanque_crema_id]
    motivos = motivos_origen_descremacion(
        origen, corrida.litros_entrada, excluir_ejecucion_id=ejecucion.pk,
    )
    for destino, producto, litros in (
        (destino_descremada, corrida.producto_descremada, corrida.litros_descremada_plan),
        (destino_crema, corrida.producto_crema, corrida.litros_crema_plan),
    ):
        motivos.extend(motivos_destino_descremacion(
            destino, producto=producto, litros=litros, excluir_ejecucion_id=ejecucion.pk,
        ))
    if motivos:
        raise ValidationError(motivos[0])
    crear_en_lote_con_auditoria([
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=origen, producto=origen.producto_actual,
            tipo=ReservaSiloProceso.Tipo.ORIGEN, cantidad_planificada=corrida.litros_entrada,
        ),
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=destino_descremada, producto=corrida.producto_descremada,
            tipo=ReservaSiloProceso.Tipo.DESTINO,
            cantidad_planificada=corrida.litros_descremada_plan,
        ),
        ReservaSiloProceso(
            ejecucion=ejecucion, silo=destino_crema, producto=corrida.producto_crema,
            tipo=ReservaSiloProceso.Tipo.DESTINO, cantidad_planificada=corrida.litros_crema_plan,
        ),
    ])
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario, motivo="Preparación desde el puesto de Descremado.",
    )
    return CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema", "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)


def motivos_tipados_para_iniciar_descremacion(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta descremación, como pares `(motivo,
    resolver_en)`, en el orden en que el inicio lo comprueba. Lista vacía: se
    puede.

    Es la única implementación de esas reglas: `iniciar_descremacion` lanza el
    primer motivo y el puesto los muestra junto a un botón deshabilitado,
    enlazando a donde se resuelve el primero. Un aseo observado **no** está
    aquí: avisa, no bloquea.
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from recepcion.servicios import motivos_silo_no_disponible, ultimo_analisis_confirmado

    ejecucion = ejecucion or corrida.ejecucion
    if (
        corrida.estado != CorridaDescremacion.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.PREPARACION
    ):
        # Lo demás no aplica a una corrida que no está preparada.
        return [(
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}.",
            None,
        )]
    motivos = []
    if not (
        corrida.litros_descremada_plan and corrida.litros_crema_plan
        and corrida.plan_confirmado_por_id and corrida.plan_confirmado_en
    ):
        motivos.append(("Calcula y confirma el reparto planificado antes de iniciar.", None))
    try:
        corrida.clean()
    except ValidationError as error:
        motivos.extend((mensaje, None) for mensaje in error.messages)
    if not ejecucion.equipo_id:
        motivos.append(("La descremación requiere una descremadora asignada.", None))
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append((impedimento, RESOLVER_CIP))
    origen = corrida.silo_entera
    del_silo = motivos_silo_no_disponible(origen, para="proceso")
    if del_silo:
        motivos.append((f"{origen.codigo}: " + " ".join(del_silo), RESOLVER_SILOS))
    vigente = ultimo_analisis_confirmado(origen)
    if vigente is not None and (
        vigente.pk != corrida.analisis_entrada_id
        or (vigente.grasa, vigente.sng) != (corrida.grasa_entrada, corrida.sng_entrada)
    ):
        # Analizar de nuevo no arregla esto: la corrida congeló la composición
        # vieja. Se arregla cancelando y volviendo a preparar, en el puesto.
        motivos.append((
            f"El análisis con que se preparó {ejecucion.codigo} ya no es el vigente de "
            f"{origen.codigo}: cancela la preparación y vuelve a prepararla con la "
            "composición actual.",
            None,
        ))
    motivos.extend(
        (motivo, None) for motivo in motivos_origen_descremacion(
            origen, corrida.litros_entrada, excluir_ejecucion_id=ejecucion.pk,
        )
    )
    for destino, producto, litros in (
        (corrida.silo_descremada, corrida.producto_descremada, corrida.litros_descremada_plan),
        (corrida.estanque_crema, corrida.producto_crema, corrida.litros_crema_plan),
    ):
        motivos.extend(
            (motivo, None) for motivo in motivos_destino_descremacion(
                destino, producto=producto, litros=litros, excluir_ejecucion_id=ejecucion.pk,
            )
        )
    propias = set(
        ReservaSiloProceso.objects.filter(
            ejecucion=ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
        ).values_list("tipo", "silo_id")
    )
    esperadas = {
        (ReservaSiloProceso.Tipo.ORIGEN, corrida.silo_entera_id),
        (ReservaSiloProceso.Tipo.DESTINO, corrida.silo_descremada_id),
        (ReservaSiloProceso.Tipo.DESTINO, corrida.estanque_crema_id),
    }
    if not esperadas <= propias:
        motivos.append((
            "Las reservas de origen y destino de la preparación no están completas: "
            "cancela la preparación y vuelve a prepararla.",
            None,
        ))
    return motivos


def motivos_para_iniciar_descremacion(corrida, *, ejecucion=None):
    """Los textos de `motivos_tipados_para_iniciar_descremacion`. Lista vacía: se puede."""
    return [
        motivo for motivo, _ in
        motivos_tipados_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
    ]


@transaction.atomic
def iniciar_descremacion(*, corrida_id, usuario):
    """
    Pasa una descremación preparada a ejecución. Recalcula los motivos con la
    corrida, la ejecución y los silos bloqueados —entre que el puesto los
    mostró y el clic pudo perder vigencia el análisis o entrar un CIP— y lanza
    el primero. No crea reservas: nacieron al preparar.
    """
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import Silo
    from .models import EntradaProceso

    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .select_related("analisis_entrada", "producto_descremada", "producto_crema")
        .get(pk=corrida_id)
    )
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    )
    silos = {
        silo.pk: silo
        for silo in Silo.objects.select_for_update().filter(pk__in=[
            corrida.silo_entera_id, corrida.silo_descremada_id, corrida.estanque_crema_id,
        ]).order_by("pk")
    }
    corrida.ejecucion = ejecucion
    corrida.silo_entera = silos[corrida.silo_entera_id]
    corrida.silo_descremada = silos[corrida.silo_descremada_id]
    corrida.estanque_crema = silos[corrida.estanque_crema_id]
    motivos = motivos_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])

    EntradaProceso.objects.create(
        ejecucion=ejecucion, silo=corrida.silo_entera, tipo=EntradaProceso.Tipo.PRINCIPAL,
        cantidad=corrida.litros_entrada, unidad="L",
    )
    aseo = advertencia_aseo_equipo(ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            f"Advertencia no bloqueante de aseo: {aseo}"
            if aseo else "Inicio desde el puesto de Descremado."
        ),
    )
    corrida.estado = CorridaDescremacion.Estado.EN_CURSO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    return CorridaDescremacion.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden", "analisis_entrada",
        "producto_descremada", "producto_crema",
        "silo_entera", "silo_descremada", "estanque_crema", "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)


def condicion_situacion(tabla, situacion):
    """
    El filtro del historial por situación: la misma tabla que nombra cada fila
    (`dominio.SITUACIONES_DESCREMACION`, `dominio.SITUACIONES_MANTEQUILLA`),
    con «gana la primera» traducido a excluir las filas anteriores. Una
    situación desconocida no devuelve nada. Una función para los dos puestos:
    con dos copias, el filtro de un historial y su columna podían dejar de
    coincidir.
    """
    def condicion(estado_corrida, estados_ejecucion):
        resultado = Q(estado=estado_corrida)
        if estados_ejecucion is not None:
            resultado &= Q(ejecucion__estado__in=estados_ejecucion)
        return resultado

    anteriores = Q()
    for valor, _etiqueta, estado_corrida, estados_ejecucion in tabla:
        propia = condicion(estado_corrida, estados_ejecucion)
        if valor == situacion:
            return propia & ~anteriores if anteriores else propia
        anteriores |= propia
    return Q(pk__in=[])


def catalogo_situaciones(tabla):
    """Las opciones del filtro del historial: las mismas situaciones que muestra la columna."""
    return [
        {"valor": valor, "etiqueta": etiqueta}
        for valor, etiqueta, _estado, _ejecucion in tabla
    ]


def estado_puesto_descremado(usuario):
    """
    Lo que el puesto de Descremado dibuja: un estado por descremadora,
    derivado de su ejecución de Descremación que ocupa el equipo (una en curso
    manda sobre una preparada), con los motivos que impiden iniciar
    calculados por la misma función que decide al iniciar; los silos de origen
    con el análisis que usará «Preparar»; los TK que la regla de destino
    acepta; y las corridas de hoy. La pantalla no recalcula nada de esto.

    Una ejecución `cerrada`/`cancelada` no ocupa la máquina aunque su corrida
    haya quedado en `borrador`/`en_curso` (`ESTADOS_QUE_OCUPAN_EQUIPO`).
    `en_calidad` es informativa: esa ejecución ya no ocupa la descremadora,
    pero sus TK siguen bloqueados hasta que Calidad decida.
    """
    from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado
    from maestros.models import Equipo, Silo
    from recepcion.servicios import ultimo_analisis_confirmado
    from usuarios.tenancy import filtrar_por_scope

    from .dominio import SITUACIONES_DESCREMACION, situacion_descremacion

    def texto(valor):
        # Texto, como en los serializers: el tipo del frontend es `string`.
        return None if valor is None else str(valor)

    descremadoras = list(filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.DESCREMADORA)
        .select_related("sucursal").order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ))
    ids = [equipo.pk for equipo in descremadoras]

    activas = {}
    for ejecucion in (
        EjecucionProceso.objects.filter(
            etapa__tipo=EtapaProceso.Tipo.DESCREMACION, equipo_id__in=ids,
            estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
        )
        .select_related(
            "etapa", "equipo", "corrida_descremacion__analisis_entrada",
            "corrida_descremacion__silo_entera", "corrida_descremacion__silo_descremada",
            "corrida_descremacion__estanque_crema", "corrida_descremacion__producto_descremada",
            "corrida_descremacion__producto_crema",
            # `motivos_tipados_para_iniciar_descremacion` llama a `clean()`,
            # que lee las dos rutas: sin esto, dos consultas por tarjeta.
            "corrida_descremacion__ruta_descremada", "corrida_descremacion__ruta_crema",
        )
        .order_by("pk")
    ):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in (
        CorridaDescremacion.objects.filter(
            ejecucion__equipo_id__in=ids,
            ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        ).select_related("ejecucion", "silo_descremada", "estanque_crema").order_by("pk")
    ):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_descremacion", None)
        base = {
            "id": None, "ejecucion_id": ejecucion.pk, "ejecucion_codigo": ejecucion.codigo,
            "ejecucion_estado": ejecucion.estado, "estado": None,
            "silo_entera": None, "litros_entrada": None, "grasa_entrada": None,
            "sng_entrada": None, "silo_descremada": None, "litros_descremada_plan": None,
            "estanque_crema": None, "litros_crema_plan": None, "destino_crema": None,
            "iniciada_en": ejecucion.inicio,
        }
        if corrida is None:
            return base
        return {
            **base,
            "id": corrida.pk, "estado": corrida.estado,
            "silo_entera": corrida.silo_entera.codigo,
            "litros_entrada": texto(corrida.litros_entrada),
            "grasa_entrada": texto(corrida.grasa_entrada),
            "sng_entrada": texto(corrida.sng_entrada),
            "silo_descremada": corrida.silo_descremada.codigo,
            "litros_descremada_plan": texto(corrida.litros_descremada_plan),
            "estanque_crema": corrida.estanque_crema.codigo,
            "litros_crema_plan": texto(corrida.litros_crema_plan),
            "destino_crema": corrida.destino_crema,
            "iniciada_en": corrida.iniciada_en,
        }

    filas = []
    for maquina in descremadoras:
        ejecucion = activas.get(maquina.pk)
        motivos_tomar, motivos_iniciar, resolver_en = [], [], None
        if ejecucion is None:
            estado = "disponible"
            # La misma regla con que «Preparar» rechaza la descremadora.
            impedimento = motivo_equipo_no_habilitado(maquina)
            if impedimento:
                motivos_tomar, resolver_en = [impedimento], RESOLVER_CIP
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_descremacion", None)
            if corrida is None:
                # Dato heredado del alta genérica, ya cerrada: sin corrida no
                # hay `cancelar-preparacion/`.
                motivos_iniciar = [
                    f"{ejecucion.codigo} no tiene corrida de descremado y no puede "
                    "iniciarse: cancela esa ejecución en Procesos y vuelve a preparar."
                ]
            else:
                tipados = motivos_tipados_para_iniciar_descremacion(corrida, ejecucion=ejecucion)
                motivos_iniciar = [motivo for motivo, _ in tipados]
                # El enlace es del primer motivo, que es el que la tarjeta muestra.
                resolver_en = tipados[0][1] if tipados else None
        else:
            estado = "en_curso"
        aseo = None if estado == "en_curso" else advertencia_aseo_equipo(maquina)
        pendiente = en_calidad.get(maquina.pk)
        filas.append({
            "equipo_id": maquina.pk, "codigo": maquina.codigo, "nombre": maquina.nombre,
            "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_tomar": motivos_tomar,
            "motivos_para_iniciar": motivos_iniciar,
            "resolver_en": resolver_en,
            "avisos": [aseo] if aseo else [],
            "en_calidad": (
                {
                    "id": pendiente.pk, "ejecucion_codigo": pendiente.ejecucion.codigo,
                    "tanques": [
                        silo.codigo for silo in (pendiente.silo_descremada, pendiente.estanque_crema)
                        if silo.estado == Silo.Estado.BLOQUEADO_CALIDAD
                    ],
                }
                if pendiente is not None else None
            ),
        })

    origenes = []
    for silo in filtrar_por_scope(
        silos_con_saldo(Silo.objects.filter(activo=True, tipo=Silo.Tipo.SILO))
        .filter(saldo_l__gt=0).order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ):
        analisis = ultimo_analisis_confirmado(silo)
        # La misma regla con que `crear_descremacion_guiada` rechaza el
        # origen. Con motivo, el silo se ofrece deshabilitado con el texto:
        # es la entrada que viene desde «Descremar» del silo.
        motivos = motivos_para_preparar_desde_silo(silo, analisis)
        # El tope del formulario: lo que otras preparaciones no reservaron
        # ya como origen, con la misma cuenta con que «Preparar» rechaza.
        libre = litros_libres_origen(silo, saldo=silo.saldo_l)
        if libre <= 0 and not motivos:
            motivos = [
                f"{silo.codigo} no tiene litros libres: su saldo está reservado "
                "por otras corridas."
            ]
        origenes.append({
            "id": silo.pk, "codigo": silo.codigo, "saldo_l": texto(silo.saldo_l),
            "libre_l": texto(libre),
            "analisis": (
                {
                    "id": analisis.pk, "grasa": texto(analisis.grasa),
                    "sng": texto(analisis.sng), "tomado_en": analisis.tomado_en,
                }
                if analisis is not None and not motivos else None
            ),
            "motivo": motivos[0] if motivos else None,
        })

    def destinos(tipo):
        # Estado y reservas con la regla de destino; capacidad y mezcla
        # dependen del plan y las vuelve a comprobar «Preparar».
        return [
            {"id": silo.pk, "codigo": silo.codigo, "libre_l": texto(silo.capacidad_l - silo.saldo_l)}
            for silo in filtrar_por_scope(
                silos_con_saldo(Silo.objects.filter(tipo=tipo)).order_by("codigo"),
                usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
            )
            if not motivos_destino_descremacion(silo)
        ]

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "silo_entera": corrida.silo_entera.codigo,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
            "estado_ejecucion": corrida.ejecucion.estado,
            **dict(zip(
                ("situacion", "situacion_etiqueta"),
                situacion_descremacion(corrida.estado, corrida.ejecucion.estado),
            )),
        }
        for corrida in CorridaDescremacion.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(
            Q(ejecucion__creada_en__date=hoy) | Q(iniciada_en__date=hoy)
            | Q(finalizada_en__date=hoy)
        )
        # Un huérfano cuya ejecución terminó sin iniciarse no es trabajo del día.
        .exclude(iniciada_en__isnull=True, ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES)
        .select_related("ejecucion__equipo", "silo_entera")
        .order_by("-pk")
    ]
    return {
        "descremadoras": filas,
        "origenes": origenes,
        "destinos_descremada": destinos(Silo.Tipo.TK_LD),
        "destinos_crema": destinos(Silo.Tipo.TK_CREMA),
        "corridas_de_hoy": corridas_de_hoy,
        # Las opciones del filtro del historial: las mismas situaciones que
        # muestra la columna, no los estados crudos de la corrida.
        "estados": catalogo_situaciones(SITUACIONES_DESCREMACION),
    }


def revisar_cierre_descremacion(
    corrida, *, litros_descremada=None, grasa_descremada=None,
    litros_crema=None, grasa_crema=None,
):
    """
    Lo que el cierre avisaría con estos valores, sin escribir nada. El
    formulario lo pide mientras se teclea (el patrón de `calcular/` del vale):
    la misma función de límites que `cerrar_descremacion` guarda y el mismo
    balance. El cliente no calcula nada por su cuenta.
    """
    from .dominio import avisos_limites_descremacion, calcular_balance_descremacion

    limites = avisos_limites_descremacion(
        grasa_descremada=grasa_descremada, grasa_crema=grasa_crema,
        crema_a_despacho=(
            corrida.destino_crema == CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO
        ),
    )
    avisos_balance, merma, desvio = [], None, None
    if grasa_descremada is not None and grasa_crema is not None:
        con_litros = litros_descremada is not None and litros_crema is not None
        balance = calcular_balance_descremacion(
            corrida.litros_entrada, corrida.grasa_entrada, corrida.sng_entrada,
            grasa_descremada, grasa_crema,
            litros_descremada=litros_descremada if con_litros else None,
            litros_crema=litros_crema if con_litros else None,
        )
        avisos_balance = list(balance.avisos)
        merma, desvio = balance.merma_declarada_l, balance.desvio_grasa_kg
    return {
        "avisos_limites": [{"codigo": codigo, "mensaje": mensaje} for codigo, mensaje in limites],
        "avisos_balance": avisos_balance,
        # Texto, como en los serializers: el tipo del frontend es `string`.
        "merma_l": None if merma is None else str(merma.quantize(Decimal("0.01"))),
        "desvio_grasa_kg": None if desvio is None else str(desvio.quantize(Decimal("0.001"))),
    }


@transaction.atomic
def cerrar_descremacion(
    *, corrida_id, usuario, litros_descremada, grasa_descremada,
    litros_crema, grasa_crema, controles=None,
):
    from maestros.models import Silo
    from produccion.models import Lote
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import heredar_atribuciones, motivos_silo_no_disponible, saldo_silo
    from .dominio import avisos_limites_descremacion, calcular_balance_descremacion
    from .models import SalidaProceso

    corrida = CorridaDescremacion.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "silo_entera",
        "silo_descremada", "estanque_crema", "producto_descremada", "producto_crema",
        "ruta_descremada", "ruta_crema",
    ).get(pk=corrida_id)
    if corrida.estado != CorridaDescremacion.Estado.EN_CURSO:
        raise ValidationError("Solo una descremación en curso puede cerrarse.")
    ld, lc = Decimal(str(litros_descremada)), Decimal(str(litros_crema))
    gd, gc = Decimal(str(grasa_descremada)), Decimal(str(grasa_crema))
    if min(ld, lc) <= 0:
        raise ValidationError("Las dos salidas deben ser mayores que cero.")
    if ld + lc > corrida.litros_entrada:
        raise ValidationError("La descremada y la crema superan los litros de entrada.")

    silos = {
        silo.pk: silo for silo in Silo.objects.select_for_update().filter(
            pk__in=[corrida.silo_entera_id, corrida.silo_descremada_id, corrida.estanque_crema_id]
        ).order_by("pk")
    }
    origen, destino_d, destino_c = (
        silos[corrida.silo_entera_id], silos[corrida.silo_descremada_id],
        silos[corrida.estanque_crema_id],
    )
    motivos = motivos_silo_no_disponible(origen, para="proceso")
    if motivos:
        raise ValidationError(f"{origen.codigo}: " + " ".join(motivos))
    if saldo_silo(origen) < corrida.litros_entrada:
        raise ValidationError(f"{origen.codigo} no tiene litros suficientes.")
    for destino, cantidad in ((destino_d, ld), (destino_c, lc)):
        if not destino.activo or destino.estado in ESTADOS_SILO_SIN_PRODUCTO:
            raise ValidationError(f"{destino.codigo} no admite producto.")
        if saldo_silo(destino) + cantidad > destino.capacidad_l:
            raise ValidationError(f"{destino.codigo} excedería su capacidad.")

    ahora = timezone.now()
    consumo = MovimientoSilo.objects.create(
        silo=origen, tipo=MovimientoSilo.Tipo.SALIDA, litros=corrida.litros_entrada,
        fecha_hora=ahora, origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        origen_id=corrida.pk, operacion_id=corrida.operacion_id,
        equipo=corrida.ejecucion.equipo, usuario=usuario,
    )
    ingresos = []
    for destino, cantidad in ((destino_d, ld), (destino_c, lc)):
        ingreso = MovimientoSilo.objects.create(
            silo=destino, silo_contraparte=origen, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=cantidad, fecha_hora=ahora,
            origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
            origen_id=corrida.pk, operacion_id=corrida.operacion_id,
            equipo=corrida.ejecucion.equipo, usuario=usuario,
        )
        heredar_atribuciones(ingreso, [consumo])
        ingresos.append(ingreso)
    reservas = list(ReservaSiloProceso.objects.select_for_update().filter(
        ejecucion=corrida.ejecucion,
        estado=ReservaSiloProceso.Estado.ACTIVA,
    ))
    if corrida.plan_confirmado_en and len(reservas) != 3:
        raise ValidationError(
            "Las reservas de origen y destino no están completas; no se puede cerrar."
        )
    cantidades_reales = {
        (ReservaSiloProceso.Tipo.ORIGEN, corrida.silo_entera_id): corrida.litros_entrada,
        (ReservaSiloProceso.Tipo.DESTINO, corrida.silo_descremada_id): ld,
        (ReservaSiloProceso.Tipo.DESTINO, corrida.estanque_crema_id): lc,
    }
    for reserva in reservas:
        reserva.estado = ReservaSiloProceso.Estado.CONSUMIDA
        reserva.cantidad_real = cantidades_reales[(reserva.tipo, reserva.silo_id)]
        reserva.cerrada_en = ahora
    if reservas:
        actualizar_en_lote_con_auditoria(
            reservas, ["estado", "cantidad_real", "cerrada_en"]
        )
    lotes = {}
    for clave, producto in (
        ("descremada", corrida.producto_descremada),
        ("crema", corrida.producto_crema),
    ):
        if producto is None:
            continue
        codigo = f"INT-DES-{corrida.pk}-{'LD' if clave == 'descremada' else 'CR'}"
        lote = Lote(
            sucursal=corrida.ejecucion.sucursal,
            codigo_lote=codigo,
            codigo_lote_propuesto=codigo,
            producto=producto,
            equipo=corrida.ejecucion.equipo,
            fecha=timezone.localdate(ahora),
            estado=Lote.Estado.EN_PROCESO,
            observacion=(
                f"Intermedio generado por {corrida.ejecucion.codigo}; "
                "los kilos se determinan al liberar con la densidad analizada."
            ),
        )
        lote.full_clean()
        lote.save()
        lotes[clave] = lote
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=lotes.get("descremada"), silo=destino_d,
        producto=corrida.producto_descremada,
        ruta_producto=corrida.ruta_descremada,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
        destino=corrida.destino_descremada,
        cantidad=ld, unidad="L",
    )
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=lotes.get("crema"), silo=destino_c,
        producto=corrida.producto_crema,
        ruta_producto=corrida.ruta_crema,
        naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
        clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
        destino=corrida.destino_crema,
        cantidad=lc, unidad="L",
    )
    merma = corrida.litros_entrada - ld - lc
    if merma > 0:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion,
            naturaleza=SalidaProceso.Naturaleza.MERMA,
            clasificacion=SalidaProceso.Clasificacion.MERMA,
            destino=SalidaProceso.Destino.OTRO,
            cantidad=merma,
            unidad="L",
            motivo="Diferencia medida en el balance de descremación",
        )
    balance = calcular_balance_descremacion(
        corrida.litros_entrada, corrida.grasa_entrada, corrida.sng_entrada, gd, gc,
        litros_descremada=ld, litros_crema=lc,
    )
    limites = avisos_limites_descremacion(
        grasa_descremada=gd, grasa_crema=gc,
        crema_a_despacho=(
            corrida.destino_crema == CorridaDescremacion.DestinoRama.DESPACHO_DIRECTO
        ),
    )
    corrida.litros_descremada, corrida.grasa_descremada = ld, gd
    corrida.litros_crema, corrida.grasa_crema = lc, gc
    corrida.controles = {
        **(controles or {}),
        # Después de lo que manda el cliente: los avisos los escribe el
        # servidor y no se pueden pisar por `controles`.
        "avisos_balance": list(balance.avisos),
        "avisos_limites": [
            {"codigo": codigo, "mensaje": mensaje} for codigo, mensaje in limites
        ],
    }
    corrida.estado = CorridaDescremacion.Estado.CERRADA
    corrida.finalizada_por = usuario
    corrida.finalizada_en = ahora
    corrida.save()
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL, usuario=usuario,
        # Lo que lee la auditoría de la ejecución.
        motivo=" ".join(mensaje for _, mensaje in limites),
    )
    if corrida.ejecucion.etapa.requiere_calidad:
        actualizar_queryset_con_auditoria(
            Silo.objects.filter(pk__in=[destino_d.pk, destino_c.pk]),
            estado=Silo.Estado.BLOQUEADO_CALIDAD
        )
    else:
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.CERRADA, usuario=usuario,
        )
    return corrida


def motivos_tipados_para_iniciar_mantequilla(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta corrida de mantequilla, como pares `(motivo,
    resolver_en)`, en el orden en que el inicio lo comprueba. Lista vacía: se
    puede.

    Es la única implementación de esas reglas: `iniciar_mantequilla` lanza el
    primer motivo y el puesto los muestra junto a un botón deshabilitado,
    enlazando a donde se resuelve el primero. Un aseo observado **no** está
    aquí: avisa, no bloquea. El stock de envases tampoco: se descuenta al
    declarar el lote producido y no bloquea (`cerrar_lote_producido`).
    """
    from inventario.servicios import motivo_equipo_no_habilitado
    from produccion.models import OrdenProduccion
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo

    ejecucion = ejecucion or corrida.ejecucion
    if (
        corrida.estado != CorridaMantequilla.Estado.BORRADOR
        or ejecucion.estado != EjecucionProceso.Estado.PREPARACION
    ):
        # Lo demás no aplica a una corrida que no está preparada.
        return [(
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}.",
            None,
        )]
    motivos = []
    try:
        corrida.clean()
    except ValidationError as error:
        motivos.extend((mensaje, None) for mensaje in error.messages)
    orden = corrida.orden
    if orden.estado not in {OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO}:
        motivos.append((
            f"La orden {orden.codigo} está {orden.get_estado_display().lower()}: "
            "debe estar programada o en proceso.",
            RESOLVER_PLANIFICACION,
        ))
    if not ejecucion.equipo_id:
        motivos.append(("La corrida requiere una mantequera asignada.", None))
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append((impedimento, RESOLVER_CIP))
    motivos.extend(motivos_crema_para_mantequilla(
        corrida.lote_crema, corrida.kg_crema, excluir_corrida_id=corrida.pk,
    ))
    fuente = fuente_tk_de_crema(corrida.lote_crema)
    if fuente is not None:
        tk = fuente.silo
        liberacion = getattr(fuente, "liberacion_calidad", None)
        densidad = (
            liberacion.analisis_silo.densidad
            if liberacion is not None and liberacion.analisis_silo_id else None
        )
        if densidad is None or densidad <= 0:
            motivos.append((
                f"El análisis de la crema en {tk.codigo} no tiene una densidad válida.",
                RESOLVER_CALIDAD,
            ))
        del_tk = motivos_silo_no_disponible(tk, para="proceso")
        if del_tk:
            motivos.append((f"{tk.codigo}: " + " ".join(del_tk), RESOLVER_SILOS))
        if densidad is not None and densidad > 0:
            litros = litros_de_crema(corrida.kg_crema, densidad)
            if saldo_silo(tk) < litros:
                motivos.append((
                    f"{tk.codigo} no tiene los {litros} L equivalentes a la crema solicitada.",
                    None,
                ))
    return motivos


def motivos_para_iniciar_mantequilla(corrida, *, ejecucion=None):
    """Los textos de `motivos_tipados_para_iniciar_mantequilla`. Lista vacía: se puede."""
    return [
        motivo for motivo, _ in
        motivos_tipados_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
    ]


@transaction.atomic
def iniciar_mantequilla(*, corrida_id, usuario):
    """
    Pasa una corrida preparada a ejecución. Recalcula los motivos con la
    corrida, la ejecución, la crema y su TK bloqueados —entre que el puesto los
    mostró y el clic pudo entrar un CIP o perderse la liberación— y lanza el
    primero. Sin motivos, saca la crema del TK, registra la entrada y la
    mantequera pasa a `ejecucion`. Ya no pasa por `borrador → preparacion`:
    eso lo hizo «Preparar».
    """
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import Silo
    from produccion.models import Lote, OrdenProduccion
    from recepcion.models import MovimientoSilo

    # Candados: la corrida, luego su ejecución (el orden de los otros puestos
    # y de `bloquear_para_cancelar`, que también toma `CorridaMantequilla`
    # antes que la ejecución al cancelar una preparación). Después,
    # el mismo orden que «Preparar» (`crear_mantequilla_guiada`): orden, lote
    # de crema, y la mantequera al transicionar. Con la orden tomada al final
    # —este camino la actualiza—, un inicio y una preparación sobre la misma
    # orden y la misma crema se esperarían en orden cruzado (deadlock).
    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).select_related(
        "lote_crema__producto", "lote_mantequilla__producto",
    ).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    )
    corrida.ejecucion = ejecucion
    corrida.orden = OrdenProduccion.objects.select_for_update(of=("self",)).get(
        pk=corrida.orden_id,
    )
    # Dos inicios sobre la misma crema se serializan antes de contar su disponible.
    list(
        Lote.objects.select_for_update(of=("self",))
        .filter(pk=corrida.lote_crema_id).values_list("pk", flat=True)
    )
    fuente = fuente_tk_de_crema(corrida.lote_crema)
    tk = Silo.objects.select_for_update().get(pk=fuente.silo_id) if fuente is not None else None
    motivos = motivos_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])

    if tk is not None:
        MovimientoSilo.objects.create(
            silo=tk,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=litros_de_crema(
                corrida.kg_crema, fuente.liberacion_calidad.analisis_silo.densidad,
            ),
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=corrida.pk,
            operacion_id=corrida.operacion_id,
            lote=corrida.lote_crema,
            producto=corrida.lote_crema.producto,
            equipo=ejecucion.equipo,
            usuario=usuario,
        )
    EntradaProceso.objects.create(
        ejecucion=ejecucion, lote=corrida.lote_crema,
        cantidad=corrida.kg_crema, unidad="kg",
    )
    aseo = advertencia_aseo_equipo(ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            f"Advertencia no bloqueante de aseo: {aseo}"
            if aseo else "Inicio desde el puesto de Mantequilla."
        ),
    )
    corrida.estado = CorridaMantequilla.Estado.EN_PROCESO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    if corrida.orden.estado == OrdenProduccion.Estado.PROGRAMADA:
        corrida.orden.estado = OrdenProduccion.Estado.EN_PROCESO
        corrida.orden.save(update_fields=["estado"])
    return CorridaMantequilla.objects.select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto", "lote_suero",
        "iniciada_por", "finalizada_por",
    ).get(pk=corrida.pk)


def _estado_calidad_de_crema(lote):
    """Por qué una crema no se ofrece: rechazada, pendiente o sin decisión de Calidad."""
    estados = {
        decision.estado
        for decision in (
            getattr(salida, "liberacion_calidad", None) for salida in lote.salidas_proceso.all()
        )
        if decision is not None
    }
    if "rechazado" in estados:
        return "rechazado"
    if "pendiente" in estados:
        return "pendiente"
    return "trazabilidad_incompleta"


def estado_puesto_mantequilla(usuario):
    """
    Lo que el puesto de Mantequilla dibuja: un estado por mantequera
    —derivado de su ejecución de Mantequilla que ocupa el equipo; una en
    curso manda sobre una preparada—, los motivos que impiden iniciar
    calculados por la misma función que decide al iniciar, y las listas que
    «Preparar» vuelve a validar con las mismas reglas: órdenes, cremas con su
    disponible (`kg_crema_disponible`), cremas que esperan a Calidad y sueros
    libres (`sueros_libres`). La pantalla no recalcula nada de esto.

    Se listan las mantequeras activas **y** cualquier equipo que tenga una
    ejecución de Mantequilla que lo ocupe aunque no sea mantequera (un dato de
    antes de `maestros.0040`): sin eso, esa corrida no tendría tarjeta ni cómo
    cerrarse. Una ejecución terminal o en `pendiente_control` no ocupa; la
    segunda se informa en `en_calidad`.
    """
    from inventario.servicios import advertencia_aseo_equipo, motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion
    from usuarios.tenancy import filtrar_por_scope

    from .dominio import SITUACIONES_MANTEQUILLA, situacion_mantequilla

    def texto(valor):
        # Texto, como en los serializers: el tipo del frontend es `string`.
        return None if valor is None else str(valor)

    def acotar(consulta):
        return filtrar_por_scope(
            consulta, usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    ocupantes = EjecucionProceso.objects.filter(
        etapa__tipo=EtapaProceso.Tipo.MANTEQUILLA,
        estado__in=ESTADOS_QUE_OCUPAN_EQUIPO, equipo__isnull=False,
    )
    maquinas = list(acotar(
        Equipo.objects.filter(
            Q(activo=True, tipo=Equipo.Tipo.MANTEQUERA)
            | Q(pk__in=ocupantes.values("equipo_id"))
        ).order_by("codigo")
    ))
    ids = [maquina.pk for maquina in maquinas]

    activas = {}
    for ejecucion in ocupantes.filter(equipo_id__in=ids).select_related(
        "etapa", "equipo", "corrida_mantequilla__orden__producto",
        "corrida_mantequilla__lote_crema__producto",
        "corrida_mantequilla__lote_mantequilla__producto",
        "corrida_mantequilla__lote_suero",
    ).order_by("pk"):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in CorridaMantequilla.objects.filter(
        ejecucion__equipo_id__in=ids,
        ejecucion__estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
    ).select_related("ejecucion", "lote_mantequilla").order_by("pk"):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_mantequilla", None)
        base = {
            "id": None, "estado": None, "ejecucion_id": ejecucion.pk,
            "ejecucion_codigo": ejecucion.codigo, "ejecucion_estado": ejecucion.estado,
            "orden_codigo": None, "producto": None, "lote_mantequilla": None,
            "lote_crema": None, "kg_crema": None, "lote_suero": None,
            "iniciada_en": ejecucion.inicio,
        }
        if corrida is None:
            return base
        return {
            **base,
            "id": corrida.pk, "estado": corrida.estado,
            "orden_codigo": corrida.orden.codigo, "producto": corrida.orden.producto.nombre,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": corrida.lote_crema.codigo_lote,
            "kg_crema": texto(corrida.kg_crema),
            "lote_suero": corrida.lote_suero.codigo_lote if corrida.lote_suero_id else None,
            "iniciada_en": corrida.iniciada_en,
        }

    filas = []
    for maquina in maquinas:
        ejecucion = activas.get(maquina.pk)
        motivos_tomar, motivos_iniciar, resolver_en = [], [], None
        if ejecucion is None:
            estado = "disponible"
            # La misma regla con que «Preparar» rechaza la mantequera.
            impedimento = motivo_equipo_no_habilitado(maquina)
            if impedimento:
                motivos_tomar, resolver_en = [impedimento], RESOLVER_CIP
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_mantequilla", None)
            if corrida is None:
                # Dato heredado de `preparar-continuacion`, ya cerrado para
                # Mantequilla: sin corrida no hay `cancelar-preparacion/`.
                motivos_iniciar = [
                    f"{ejecucion.codigo} no tiene corrida de mantequilla y no puede "
                    "iniciarse: cancela esa ejecución en Procesos y vuelve a preparar."
                ]
            else:
                tipados = motivos_tipados_para_iniciar_mantequilla(corrida, ejecucion=ejecucion)
                motivos_iniciar = [motivo for motivo, _ in tipados]
                # El enlace es del primer motivo, que es el que la tarjeta muestra.
                resolver_en = tipados[0][1] if tipados else None
        else:
            estado = "en_curso"
        aseo = None if estado == "en_curso" else advertencia_aseo_equipo(maquina)
        pendiente = en_calidad.get(maquina.pk)
        filas.append({
            "equipo_id": maquina.pk, "codigo": maquina.codigo, "nombre": maquina.nombre,
            "tipo": maquina.tipo, "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_tomar": motivos_tomar,
            "motivos_para_iniciar": motivos_iniciar,
            "resolver_en": resolver_en,
            "avisos": [aseo] if aseo else [],
            "en_calidad": (
                {
                    "id": pendiente.pk, "ejecucion_codigo": pendiente.ejecucion.codigo,
                    "lote_mantequilla": pendiente.lote_mantequilla.codigo_lote,
                }
                if pendiente is not None else None
            ),
        })

    ordenes = acotar(
        OrdenProduccion.objects.filter(
            producto__categoria="mantequilla",
            estado__in=[OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO],
        ).select_related("producto").order_by("codigo")
    )
    cremas_producidas = acotar(
        Lote.objects.filter(
            producto__familia="crema",
            estado__in=[Lote.Estado.PRODUCIDO, Lote.Estado.CERRADO],
            kg_producidos__isnull=False,
        ).select_related("producto")
    )
    # Lo que «Preparar» acepta, en una consulta: la misma liberación
    # (`filtro_crema_liberada`, la del TK si la crema está en uno) y el mismo
    # disponible (`expresion_kg_crema_disponible`, la cuenta de
    # `kg_crema_disponible`). Con una cuenta por fila, el puesto hacía tres
    # consultas por crema.
    tk_de_la_crema = (
        SalidaProceso.objects.filter(lote=OuterRef("pk"), silo__isnull=False)
        .order_by("registrada_en", "pk").values("silo__codigo")[:1]
    )
    cremas = [
        {
            "id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre,
            "disponible_kg": texto(lote.disponible_kg),
            "tk": lote.tk,
        }
        for lote in cremas_producidas.filter(filtro_crema_liberada())
        .annotate(disponible_kg=expresion_kg_crema_disponible(), tk=Subquery(tk_de_la_crema))
        .filter(disponible_kg__gt=0)
        .order_by("codigo_lote")
    ]
    pendientes = (
        cremas_producidas.filter(Exists(SalidaProceso.objects.filter(lote=OuterRef("pk"))))
        .exclude(filtro_crema_liberada())
        .prefetch_related("salidas_proceso__liberacion_calidad", "salidas_proceso__ejecucion__etapa")
        .order_by("codigo_lote")
    )
    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk, "ejecucion_codigo": corrida.ejecucion.codigo,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "lote_mantequilla": corrida.lote_mantequilla.codigo_lote,
            "lote_crema": corrida.lote_crema.codigo_lote,
            "estado": corrida.estado, "estado_etiqueta": corrida.get_estado_display(),
            "estado_ejecucion": corrida.ejecucion.estado,
            **dict(zip(
                ("situacion", "situacion_etiqueta"),
                situacion_mantequilla(corrida.estado, corrida.ejecucion.estado),
            )),
        }
        for corrida in CorridaMantequilla.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(
            Q(ejecucion__creada_en__date=hoy) | Q(iniciada_en__date=hoy)
            | Q(finalizada_en__date=hoy)
        )
        # Un huérfano cuya ejecución terminó sin iniciarse no es trabajo del día.
        .exclude(iniciada_en__isnull=True, ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES)
        .select_related("ejecucion__equipo", "lote_mantequilla", "lote_crema")
        .order_by("-pk")
    ]
    return {
        "mantequeras": filas,
        "ordenes": [
            {"id": orden.pk, "codigo": orden.codigo, "producto": orden.producto.nombre}
            for orden in ordenes
        ],
        "cremas": cremas,
        "cremas_pendientes_calidad": [
            {
                "id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre,
                "estado_calidad": _estado_calidad_de_crema(lote),
                "etapa_origen": next(
                    (salida.ejecucion.etapa.get_tipo_display() for salida in lote.salidas_proceso.all()),
                    "Sin proceso de origen",
                ),
            }
            for lote in pendientes
        ],
        "sueros": [
            {"id": lote.pk, "codigo": lote.codigo_lote, "producto": lote.producto.nombre}
            for lote in sueros_libres(acotar(Lote.objects.select_related("producto"))).order_by("codigo_lote")
        ],
        "corridas_de_hoy": corridas_de_hoy,
        # Las opciones del filtro del historial: las mismas situaciones que
        # muestra la columna, no los estados crudos de la corrida.
        "estados": catalogo_situaciones(SITUACIONES_MANTEQUILLA),
    }


def revisar_cierre_mantequilla(
    corrida, *, kg_mantequilla=None, kg_suero=None, kg_merma=None,
    kg_reproceso=None, motivo_reproceso="",
):
    """
    Lo que el cierre decidiría con estos valores, sin escribir nada. El
    formulario lo pide mientras se teclea (el patrón de
    `revisar_cierre_descremacion`) y habilita «Cerrar» solo con una revisión
    que cuadra: el cliente no calcula. La misma función que `cerrar_mantequilla`
    y `CorridaMantequilla.clean()`.
    """
    balance = balance_mantequilla(
        kg_crema=corrida.kg_crema, kg_mantequilla=kg_mantequilla,
        kg_suero=kg_suero, kg_merma=kg_merma, kg_reproceso=kg_reproceso,
    )
    return {
        # Texto, como en los serializers: el tipo del frontend es `string`.
        "entrada_kg": str(balance.entrada_kg),
        "clasificado_kg": str(balance.clasificado_kg),
        "diferencia_kg": str(balance.diferencia_kg),
        "cuadra": balance.cuadra,
        "mensaje": balance.mensaje,
        "errores": errores_cierre_mantequilla(
            tiene_lote_suero=bool(corrida.lote_suero_id), kg_mantequilla=kg_mantequilla,
            kg_suero=kg_suero, kg_reproceso=kg_reproceso, motivo_reproceso=motivo_reproceso,
        ),
    }


@transaction.atomic
def cerrar_mantequilla(
    *, corrida_id, usuario, kg_mantequilla, kg_suero=0, kg_merma=0,
    kg_reproceso=0, motivo_reproceso="", controles=None,
):
    from calidad.models import LiberacionProceso
    from produccion.models import Lote
    from .models import AutorizacionReproceso, SalidaProceso

    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "lote_mantequilla__producto", "lote_suero", "orden"
    ).get(pk=corrida_id)
    if corrida.estado != CorridaMantequilla.Estado.EN_PROCESO:
        raise ValidationError("Solo una corrida en proceso puede cerrarse.")
    corrida.kg_mantequilla = Decimal(str(kg_mantequilla))
    corrida.kg_suero = Decimal(str(kg_suero))
    corrida.kg_merma = Decimal(str(kg_merma))
    corrida.kg_reproceso = Decimal(str(kg_reproceso))
    corrida.motivo_reproceso = str(motivo_reproceso).strip()
    corrida.controles = controles or {}
    # El balance y las reglas de lo tecleado se deciden antes de escribir
    # nada —hoy el lote de reproceso se creaba y `clean()` lo revertía—, con
    # las mismas funciones que `revisar-cierre/` y `clean()`.
    errores = errores_cierre_mantequilla(
        tiene_lote_suero=bool(corrida.lote_suero_id), kg_mantequilla=corrida.kg_mantequilla,
        kg_suero=corrida.kg_suero, kg_reproceso=corrida.kg_reproceso,
        motivo_reproceso=corrida.motivo_reproceso,
    )
    if errores:
        raise ValidationError(errores)
    balance = balance_mantequilla(
        kg_crema=corrida.kg_crema, kg_mantequilla=corrida.kg_mantequilla,
        kg_suero=corrida.kg_suero, kg_merma=corrida.kg_merma,
        kg_reproceso=corrida.kg_reproceso,
    )
    if not balance.cuadra:
        raise ValidationError({"balance": balance.mensaje})
    if corrida.kg_reproceso:
        codigo_reproceso = f"RW-MANT-{corrida.operacion_id.hex[:12].upper()}"
        lote_reproceso = Lote(
            sucursal=corrida.lote_mantequilla.sucursal,
            codigo_lote=codigo_reproceso,
            codigo_lote_propuesto=codigo_reproceso,
            op=corrida.orden.codigo,
            orden=corrida.orden,
            producto=corrida.lote_mantequilla.producto,
            equipo=corrida.ejecucion.equipo,
            fecha=timezone.localdate(),
            estado=Lote.Estado.PRODUCIDO,
            kg_producidos=corrida.kg_reproceso,
            observacion=(
                f"Reproceso segregado al cerrar {corrida.ejecucion.codigo}. "
                f"Motivo: {corrida.motivo_reproceso}"
            ),
        )
        lote_reproceso.full_clean()
        lote_reproceso.save()
        corrida.lote_reproceso = lote_reproceso
    corrida.clean()
    salida_mantequilla = SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=corrida.lote_mantequilla,
        producto=corrida.lote_mantequilla.producto,
        ruta_producto=corrida.ejecucion.ruta_producto,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=SalidaProceso.Clasificacion.GRANEL,
        destino=SalidaProceso.Destino.ENVASADO,
        cantidad=corrida.kg_mantequilla, unidad="kg",
    )
    if corrida.ejecucion.etapa.requiere_calidad:
        LiberacionProceso.objects.get_or_create(salida=salida_mantequilla)
    if corrida.kg_suero:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion, lote=corrida.lote_suero,
            producto=corrida.lote_suero.producto,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.SUBPRODUCTO,
            destino=SalidaProceso.Destino.PENDIENTE,
            cantidad=corrida.kg_suero, unidad="kg",
        )
        corrida.lote_suero.kg_producidos = corrida.kg_suero
        corrida.lote_suero.estado = corrida.lote_suero.Estado.PRODUCIDO
        corrida.lote_suero.save(update_fields=["kg_producidos", "estado"])
    if corrida.kg_merma:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion, naturaleza=SalidaProceso.Naturaleza.MERMA,
            clasificacion=SalidaProceso.Clasificacion.MERMA,
            destino=SalidaProceso.Destino.OTRO,
            cantidad=corrida.kg_merma, unidad="kg", motivo="Merma de mantequilla",
        )
    if corrida.kg_reproceso:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion, lote=corrida.lote_reproceso,
            producto=corrida.lote_reproceso.producto,
            ruta_producto=corrida.ejecucion.ruta_producto,
            naturaleza=SalidaProceso.Naturaleza.REPROCESO,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.REPROCESO,
            cantidad=corrida.kg_reproceso, unidad="kg",
            motivo=corrida.motivo_reproceso,
        )
        autorizacion = AutorizacionReproceso(
            lote=corrida.lote_reproceso,
            origen=AutorizacionReproceso.Origen.RECUPERABLE,
            cantidad_kg=corrida.kg_reproceso,
            motivo=corrida.motivo_reproceso,
            solicitado_por=usuario,
        )
        autorizacion.full_clean()
        autorizacion.save()
        from inventario.servicios import _notificar_area
        from usuarios.models import PerfilUsuario

        _notificar_area(
            PerfilUsuario.Area.CALIDAD,
            tipo="reproceso_pendiente_calidad",
            titulo="Reproceso de mantequilla pendiente de Calidad",
            mensaje=(
                f"Lote {corrida.lote_reproceso.codigo_lote}: "
                f"{corrida.kg_reproceso} kg segregados. "
                f"Motivo: {corrida.motivo_reproceso}"
            ),
            documento_tipo="procesos.AutorizacionReproceso",
            documento_id=autorizacion.pk,
            accion_url="/calidad",
        )
        EventoProceso.objects.create(
            ejecucion=corrida.ejecucion, usuario=usuario,
            tipo="reproceso_solicitado",
            estado_anterior=corrida.ejecucion.estado,
            estado_nuevo=corrida.ejecucion.estado,
            motivo=(
                f"{corrida.kg_reproceso} kg segregados en "
                f"{corrida.lote_reproceso.codigo_lote}; pendiente de Calidad."
            ),
        )
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL, usuario=usuario,
    )
    corrida.estado = CorridaMantequilla.Estado.PENDIENTE_CALIDAD
    corrida.finalizada_por = usuario
    corrida.finalizada_en = timezone.now()
    corrida.save()
    corrida.lote_mantequilla.kg_producidos = corrida.kg_mantequilla
    corrida.lote_mantequilla.estado = corrida.lote_mantequilla.Estado.PRODUCIDO
    corrida.lote_mantequilla.save(update_fields=["kg_producidos", "estado"])
    # Adopta la cola común, no `registrar_produccion`: mantequilla crea sus
    # coproductos y su merma a mano y transiciona a `pendiente_control`, no a
    # `cerrada`. Unificar eso sería reescribirlo, no simplificarlo.
    from produccion.servicios import cerrar_lote_producido

    aviso_bodega = cerrar_lote_producido(
        lote=corrida.lote_mantequilla,
        usuario=usuario,
        titulo="Mantequilla pendiente de Calidad",
        mensaje=(
            f"Lote {corrida.lote_mantequilla.codigo_lote} terminado y "
            "pendiente de liberación."
        ),
    )

    if aviso_bodega:
        EventoProceso.objects.create(
            ejecucion=corrida.ejecucion, usuario=usuario,
            tipo="consumo_materiales_pendiente", motivo=aviso_bodega,
        )

    return corrida


def _deshacer_preparacion_secado(ejecucion, motivo, usuario=None):
    """
    Lo que una preparación de Secado dejó escrito, deshecho al cancelarla.

    La `CorridaSecado` se borra: es uno a uno con el lote, así que mientras
    exista el concentrado no se puede volver a tomar —ni ofrecer
    (`lote__corrida_secado__isnull`), ni aceptar en `preparar_continuacion`—,
    y en preparación no guarda nada medido. El rastro queda en la ejecución
    cancelada (su entrada y el evento con el motivo) y en la auditoría, que
    registra el borrado. Las entradas no se borran: dejan de contar por
    `PREPARACION_CANCELADA`.

    El lote vuelve a apuntar a la ejecución que produjo el concentrado. Un
    lote externo nació con la preparación y se anula; el stock que salió de
    bodega al preparar **no** vuelve (Desviación 6 del plan del puesto).
    """
    from produccion.models import Lote

    corrida = CorridaSecado.objects.filter(ejecucion=ejecucion).first()
    if corrida is None:
        return
    lote = Lote.objects.select_for_update(of=("self",)).get(pk=corrida.lote_id)
    corrida.delete()
    if lote.ejecucion_id != ejecucion.pk:
        return
    entrada = ejecucion.entradas.select_related("salida_origen__ejecucion").first()
    origen = entrada.salida_origen.ejecucion if entrada and entrada.salida_origen_id else None
    if origen is not None:
        lote.ejecucion = origen
        lote.equipo = origen.equipo
        lote.save(update_fields=["ejecucion", "equipo"])
        return
    from produccion.servicios import anular_lote

    # La misma anulación que el `PATCH` del lote. Su ejecución ya es esta,
    # cancelada, así que no vuelve a transicionarla; y si el `PATCH` ya lo
    # anuló, no lo marca dos veces.
    anular_lote(
        lote=lote,
        motivo=(
            f"Preparación de Secado cancelada: {_con_punto(motivo)} "
            "La materia prima descontada no vuelve a bodega."
        ),
        usuario=usuario,
    )
    if corrida.orden_id:
        _devolver_orden_a_programada(corrida.orden_id, ejecucion=ejecucion, lote=lote)


def _devolver_orden_a_programada(orden_id, *, ejecucion, lote):
    """
    La alimentación externa pasa la orden a en proceso al preparar
    (`preparar_secado_desde_inventario`). Si esa preparación era lo único que
    la tenía ahí —ningún otro lote vivo de la orden, ninguna otra corrida sin
    terminar—, cancelarla la devuelve a programada; si no, la orden quedaba en
    proceso sin nada en proceso.
    """
    from produccion.models import Lote, OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update(of=("self",)).get(pk=orden_id)
    if orden.estado != OrdenProduccion.Estado.EN_PROCESO:
        return
    # Un lote en proceso o ya producido dice que la orden empezó por otro
    # lado. Un borrador no: es un formulario autoguardado, no producción.
    if Lote.objects.filter(orden=orden).exclude(pk=lote.pk).exclude(
        estado__in=[Lote.Estado.ANULADO, Lote.Estado.BORRADOR]
    ).exists():
        return
    for corridas in (
        orden.corridas_condensacion, orden.corridas_secado,
        orden.corridas_descremacion, orden.corridas_mantequilla,
    ):
        if corridas.exclude(ejecucion=ejecucion).exclude(
            ejecucion__estado__in=ESTADOS_EJECUCION_TERMINALES
        ).exists():
            return
    # `en_proceso → programada` no está en `OrdenProduccion.TRANSICIONES`, a
    # propósito: esa tabla es la que valida el PATCH de la API, y agregarla
    # dejaría a cualquiera devolver a mano una orden en curso. Aquí no es una
    # decisión del usuario sino deshacer lo que la preparación cancelada hizo.
    orden.estado = OrdenProduccion.Estado.PROGRAMADA
    orden.save(update_fields=["estado"])


@transaction.atomic
def cancelar_preparacion_secado(*, corrida_id, usuario, motivo):
    """
    Suelta una torre preparada sin iniciarla. Solo desde `preparacion`: una
    corrida que ya inició se cierra con su balance. La transición genérica
    libera la torre y las reservas, y deshace la preparación.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaSecado.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .get(pk=corrida.ejecucion_id)
    )
    if ejecucion.estado != EjecucionProceso.Estado.PREPARACION:
        raise ValidationError(
            f"Solo se cancela una torre preparada: {ejecucion.codigo} está "
            f"{ejecucion.get_estado_display().lower()}. Una corrida iniciada se "
            "cierra registrando su balance."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario,
        motivo=motivo,
    )


def _con_punto(texto):
    texto = (texto or "").strip()
    return texto if texto.endswith((".", "!", "?")) else f"{texto}."


def _deshacer_preparacion_evaporacion(ejecucion, motivo, usuario):
    """
    Lo que abrir el lote sobre un evaporador dejó escrito, deshecho al
    cancelar su ejecución sin haber iniciado la corrida.

    Abrir el lote sacó la leche del silo del vale (`abrir_lote_desde_vale`);
    como la corrida no empezó, esa leche nunca entró al evaporador y vuelve al
    mismo silo con un ingreso compensatorio (`devolver_leche_del_lote`). La
    salida original no se borra. La corrida queda `cancelada` —no se borra
    como la de Secado: no bloquea nada, y es el rastro de la preparación— y
    el lote se anula con la misma anulación que el `PATCH`.

    Una corrida que ya inició no devuelve nada: lo que entró al evaporador no
    vuelve, y la anulación sigue el camino de siempre. Pero queda `cancelada`
    con su ejecución: una corrida «en proceso» sobre una ejecución cancelada
    no la está haciendo nadie.
    """
    from produccion.models import Lote
    from produccion.servicios import anular_lote, devolver_leche_del_lote

    corrida = (
        CorridaCondensacion.objects.select_for_update(of=("self",))
        .select_related("silo_origen").filter(ejecucion=ejecucion).first()
    )
    if corrida is None:
        return
    if corrida.estado == CorridaCondensacion.Estado.EN_PROCESO:
        corrida.estado = CorridaCondensacion.Estado.CANCELADA
        corrida.save(update_fields=["estado"])
        return
    if corrida.estado != CorridaCondensacion.Estado.BORRADOR:
        return
    lote = Lote.objects.select_for_update(of=("self",)).get(pk=corrida.lote_id)
    devuelta = devolver_leche_del_lote(
        lote=lote, silo=corrida.silo_origen, usuario=usuario,
        motivo=f"preparación de Evaporación {ejecucion.codigo} cancelada.",
    )
    corrida.estado = CorridaCondensacion.Estado.CANCELADA
    corrida.save(update_fields=["estado"])
    if lote.ejecucion_id == ejecucion.pk:
        # Solo se dice que la leche volvió si hubo devolución: un lote sin
        # salida del silo (o ya devuelta) no tiene leche que devolver.
        leche = (
            f"La leche volvió a {corrida.silo_origen.codigo}."
            if devuelta is not None
            else "No había leche descontada que devolver."
        )
        if lote.estado == Lote.Estado.ANULADO:
            # Por el `PATCH` la anulación ya escribió su marca antes de llegar
            # aquí, y `anular_lote` no vuelve a marcar un lote anulado: la
            # devolución se agrega a esa marca, una sola vez.
            if devuelta is not None:
                lote.observacion = f"{_con_punto(lote.observacion.rstrip())} {leche}"
                lote.save(update_fields=["observacion"])
            return
        anular_lote(
            lote=lote,
            motivo=f"Preparación de Evaporación cancelada: {_con_punto(motivo)} {leche}",
            usuario=usuario,
        )


@transaction.atomic
def cancelar_preparacion_evaporacion(*, corrida_id, usuario, motivo):
    """
    Suelta un evaporador preparado sin iniciarlo: anula el lote y devuelve la
    leche al silo del vale. Solo desde una corrida en `borrador`: una que ya
    inició se cierra declarando su precondensado. Simétrico a
    `cancelar_preparacion_secado`; lo que se deshace lo hace la transición
    genérica (`_deshacer_preparacion_evaporacion`).
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaCondensacion.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .get(pk=corrida.ejecucion_id)
    )
    if (
        corrida.estado != CorridaCondensacion.Estado.BORRADOR
        or ejecucion.estado in ESTADOS_EJECUCION_TERMINALES
    ):
        raise ValidationError(
            f"Solo se cancela un evaporador preparado: {ejecucion.codigo} está "
            f"{corrida.get_estado_display().lower()}. Una corrida iniciada se "
            "cierra declarando su precondensado."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario,
        motivo=motivo,
    )


def _deshacer_preparacion_descremacion(ejecucion, motivo):
    """
    Lo propio de Descremación al cancelar su ejecución: la corrida queda
    `anulada` con el motivo. Las reservas las suelta la transición genérica, y
    la descremadora queda libre al salir de `ESTADOS_QUE_OCUPAN_EQUIPO`. No
    hay lote que anular ni leche que devolver: hasta el cierre no se mueve un
    litro.

    También una corrida ya iniciada, cancelada desde la bandeja: una corrida
    «en curso» sobre una ejecución cancelada no la hace nadie (como
    `_deshacer_preparacion_evaporacion` con la que está en proceso).
    """
    corrida = (
        CorridaDescremacion.objects.select_for_update(of=("self",))
        .filter(ejecucion=ejecucion).first()
    )
    if corrida is None or corrida.estado not in {
        CorridaDescremacion.Estado.BORRADOR, CorridaDescremacion.Estado.EN_CURSO,
    }:
        return
    corrida.estado = CorridaDescremacion.Estado.ANULADA
    corrida.motivo_anulacion = _con_punto(motivo)
    corrida.save(update_fields=["estado", "motivo_anulacion"])


@transaction.atomic
def cancelar_preparacion_descremacion(*, corrida_id, usuario, motivo):
    """
    Suelta una descremadora preparada sin iniciarla. Acepta la ejecución en
    `preparacion` y también en `borrador` (corridas heredadas del modal
    anterior, que nunca llegaron a reservar). Una corrida iniciada se cierra
    registrando sus salidas. Simétrica a `cancelar_preparacion_secado`; lo que
    se deshace lo hace la transición genérica.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaDescremacion.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",)).get(pk=corrida.ejecucion_id)
    )
    if corrida.estado != CorridaDescremacion.Estado.BORRADOR or ejecucion.estado not in {
        EjecucionProceso.Estado.BORRADOR, EjecucionProceso.Estado.PREPARACION,
    }:
        raise ValidationError(
            f"Solo se cancela una descremadora preparada: {ejecucion.codigo} está "
            f"{ejecucion.get_estado_display().lower()}. Una corrida iniciada se cierra "
            "registrando sus salidas."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario, motivo=motivo,
    )


def _deshacer_preparacion_mantequilla(ejecucion, motivo, usuario):
    """
    Lo propio de Mantequilla al cancelar su ejecución: la corrida queda
    `anulada` con el motivo y el lote de salida se anula con `anular_lote`, la
    misma anulación que el `PATCH`. La mantequera queda libre al salir de
    `ESTADOS_QUE_OCUPAN_EQUIPO`.

    No hay crema que devolver desde una preparación: no se movió, entra al
    iniciar. Desde una corrida en curso, lo que entró a la mantequera no
    vuelve, como en Evaporación; y su lote también se anula, porque un lote
    `en_proceso` sobre una ejecución cancelada no lo cierra nadie. El suero no
    se desvincula —la corrida anulada conserva el rastro—, pero
    `sueros_libres` ignora las anuladas.

    Si se llegó aquí desde el `PATCH`, el lote ya viene anulado y
    `anular_lote` lo deja como está; la ejecución ya está cancelada, así que
    tampoco la vuelve a cancelar (`ejecucion_cancelable`).
    """
    from produccion.models import Lote
    from produccion.servicios import anular_lote

    corrida = (
        CorridaMantequilla.objects.select_for_update(of=("self",))
        .filter(ejecucion=ejecucion).first()
    )
    if corrida is None or corrida.estado not in {
        CorridaMantequilla.Estado.BORRADOR, CorridaMantequilla.Estado.EN_PROCESO,
    }:
        return
    origen = (
        "Preparación de Mantequilla cancelada"
        if corrida.estado == CorridaMantequilla.Estado.BORRADOR
        else "Corrida de Mantequilla cancelada"
    )
    corrida.estado = CorridaMantequilla.Estado.ANULADA
    corrida.motivo_anulacion = _con_punto(motivo)[:250]
    corrida.save(update_fields=["estado", "motivo_anulacion"])
    anular_lote(
        lote=Lote.objects.get(pk=corrida.lote_mantequilla_id),
        motivo=f"{origen}: {_con_punto(motivo)}",
        usuario=usuario,
    )


@transaction.atomic
def cancelar_preparacion_mantequilla(*, corrida_id, usuario, motivo):
    """
    Suelta una mantequera preparada sin iniciarla: la corrida y su lote de
    salida quedan anulados. Acepta la ejecución en `preparacion` y también en
    `borrador` (corridas heredadas del modal anterior, que nunca tomaron la
    máquina). Una corrida iniciada se cierra registrando su balance. Simétrica
    a `cancelar_preparacion_descremacion`; lo que se deshace lo hace la
    transición genérica.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise ValidationError(MENSAJE_MOTIVO_CANCELACION)
    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",)).get(pk=corrida.ejecucion_id)
    )
    if corrida.estado != CorridaMantequilla.Estado.BORRADOR or ejecucion.estado not in {
        EjecucionProceso.Estado.BORRADOR, EjecucionProceso.Estado.PREPARACION,
    }:
        raise ValidationError(
            f"Solo se cancela una mantequera preparada: {ejecucion.codigo} está "
            f"{ejecucion.get_estado_display().lower()}. Una corrida iniciada se cierra "
            "registrando su balance."
        )
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
        usuario=usuario, motivo=motivo,
    )


def inicio_reservado_al_puesto(ejecucion, estado_nuevo):
    """
    ¿Es este paso el inicio de una corrida que solo inicia su puesto?
    (`MENSAJES_INICIO_EN_PUESTO`: Secado, Descremación y Mantequilla). Reanudar
    (`pausada`/`bloqueada` → `ejecucion`) no es iniciar: sigue por la
    transición genérica, o una máquina pausada no tendría cómo volver.
    """
    return (
        estado_nuevo == EjecucionProceso.Estado.EJECUCION
        and ejecucion.estado == EjecucionProceso.Estado.PREPARACION
        and ejecucion.etapa.tipo in MENSAJES_INICIO_EN_PUESTO
    )


# Dónde se resuelve cada motivo, como dato: la pantalla enlaza ahí sin leer
# el texto. Un motivo sin destino (sin saldo, sin torre) no tiene pantalla
# que lo arregle y viaja con `None`.
RESOLVER_CIP = "/calidad/inocuidad"
RESOLVER_CALIDAD = "/calidad"

# Motivos del silo de origen (análisis, firmas, inhibidores, 48 h, estado):
# se resuelven donde Recepción y Calidad analizan los silos.
RESOLVER_SILOS = "/silos"

# Motivos de la orden (cancelada, cerrada): se resuelven donde se programan.
RESOLVER_PLANIFICACION = "/planificacion"


def motivos_tipados_para_iniciar_secado(corrida, *, ejecucion=None):
    """
    Lo que impide iniciar esta corrida de Secado, como pares
    `(motivo, resolver_en)`. Lista vacía: se puede.

    Es la única implementación de esas reglas: `iniciar_secado` lanza el primer
    motivo (vía `motivos_para_iniciar_secado`) y el puesto los muestra junto a
    un botón deshabilitado, enlazando a donde se resuelve el primero. Un aseo
    observado o una inspección pre-operativa que falta **no** están aquí: son
    avisos (`avisos_de_torre`), no bloquean.
    """
    from calidad.models import LiberacionProceso
    from inventario.servicios import motivo_equipo_no_habilitado

    ejecucion = ejecucion or corrida.ejecucion
    motivos = []
    if ejecucion.estado != EjecucionProceso.Estado.PREPARACION:
        motivos.append((
            f"{ejecucion.codigo} no está preparada: está "
            f"{ejecucion.get_estado_display().lower()}.",
            None,
        ))
    entradas = list(ejecucion.entradas.select_related(
        "salida_origen__silo", "lote_inventario",
    ))
    if not entradas:
        motivos.append(("Para iniciar se requiere al menos una entrada de proceso.", None))
    if not ejecucion.equipo_id:
        motivos.append(("La corrida requiere una torre asignada.", None))
    else:
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)
        if impedimento:
            motivos.append((impedimento, RESOLVER_CIP))
    for entrada in entradas:
        salida = entrada.salida_origen
        if salida is not None:
            nombre = salida.silo.codigo if salida.silo_id else f"la salida {salida.pk}"
            decision = getattr(salida, "liberacion_calidad", None)
            estado = decision.estado if decision is not None else None
            if estado == LiberacionProceso.Estado.RECHAZADO:
                motivos.append((f"Calidad rechazó el concentrado de {nombre}.", RESOLVER_CALIDAD))
            elif estado != LiberacionProceso.Estado.LIBERADO:
                motivos.append((
                    f"El concentrado de {nombre} no está liberado por Calidad.",
                    RESOLVER_CALIDAD,
                ))
            if disponible_de_salida(salida) < 0:
                motivos.append((
                    f"El concentrado de {nombre} ya no tiene saldo: otra ejecución lo consumió.",
                    None,
                ))
        elif entrada.lote_inventario_id and not entrada.lote_inventario.utilizable:
            # El stock ya salió de bodega al preparar; lo que puede cambiar
            # después es la decisión de Calidad sobre el lote del proveedor.
            motivos.append((
                f"El lote externo {entrada.lote_inventario.codigo} ya no está liberado por Calidad.",
                RESOLVER_CALIDAD,
            ))
    return motivos


def motivos_para_iniciar_secado(corrida, *, ejecucion=None):
    """Los textos de `motivos_tipados_para_iniciar_secado`. Lista vacía: se puede."""
    return [
        motivo for motivo, _ in motivos_tipados_para_iniciar_secado(corrida, ejecucion=ejecucion)
    ]


def avisos_de_torre(torre, *, hoy=None):
    """
    Lo que conviene saber antes de operar la torre y **no bloquea**: el último
    aseo con advertencia y la falta de una inspección pre-operativa completa
    de hoy. «Hay inspección» se decide como en el expediente del lote
    (`cubre_al_lote` + `registro_completo`), pero acotado a **esta** torre.
    """
    from types import SimpleNamespace

    from calidad.dominio import cubre_al_lote, registro_completo
    from calidad.models import RegistroEquipo
    from inventario.servicios import advertencia_aseo_equipo
    from maestros.models import DocumentoLiberacion

    avisos = []
    aseo = advertencia_aseo_equipo(torre)
    if aseo:
        avisos.append(aseo)
    empresa_id = torre.sucursal.empresa_id if torre.sucursal_id else None
    documento = DocumentoLiberacion.objects.filter(
        empresa_id=empresa_id, codigo=CODIGO_INSPECCION_PREOPERATIVA, activo=True,
    ).first()
    if documento is None:
        # Sin el documento configurado no hay dónde registrar la inspección:
        # avisar de algo imposible de cumplir solo enseña a ignorar el aviso.
        return avisos
    jornada = SimpleNamespace(fecha=hoy or timezone.localdate(), turno="")
    # Basta mirar el último mes: la frecuencia más larga que se deduce sola es
    # la semanal (`cubre_al_lote`); `segun_programa` declara su vigencia.
    registros = RegistroEquipo.objects.filter(
        documento=documento, equipo=torre, fecha__lte=jornada.fecha,
    ).order_by("-fecha")[:31]
    if not any(
        cubre_al_lote(registro, documento, jornada) and registro_completo(registro, documento)
        for registro in registros
    ):
        avisos.append(AVISO_INSPECCION_PREOPERATIVA)
    return avisos


def _marcar_aseo_en_el_lote(corrida, torre):
    """
    Deja en la observación del lote la misma marca que `abrir_lote_desde_vale`
    pone al abrir sobre una máquina con aseo observado: la ficha del lote
    (`DetalleLote`, paso «Aseo») la lee de ahí.
    """
    from inventario.servicios import advertencia_aseo_equipo
    from produccion.models import Lote

    advertencia = advertencia_aseo_equipo(torre)
    if not advertencia:
        return
    lote = Lote.objects.select_for_update(of=("self",)).get(pk=corrida.lote_id)
    marca = f"[ADVERTENCIA ASEO AL INICIO] {advertencia}"
    lote.observacion = "\n".join(parte for parte in (lote.observacion.strip(), marca) if parte)
    lote.save(update_fields=["observacion"])


@transaction.atomic
def iniciar_secado(*, corrida_id, usuario):
    """
    Pasa una corrida de Secado preparada a ejecución. Recalcula los motivos
    con la ejecución bloqueada —entre que el puesto los mostró y el clic pudo
    entrar un CIP o un rechazo de Calidad— y deja los avisos en el evento.
    """
    corrida = CorridaSecado.objects.select_for_update(of=("self",)).get(pk=corrida_id)
    ejecucion = (
        EjecucionProceso.objects.select_for_update(of=("self",))
        .select_related("etapa", "equipo__sucursal")
        .get(pk=corrida.ejecucion_id)
    )
    motivos = motivos_para_iniciar_secado(corrida, ejecucion=ejecucion)
    if motivos:
        raise ValidationError(motivos[0])
    avisos = avisos_de_torre(ejecucion.equipo)
    _marcar_aseo_en_el_lote(corrida, ejecucion.equipo)
    transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.EJECUCION,
        usuario=usuario,
        motivo=(
            "Advertencia no bloqueante: " + " ".join(avisos)
            if avisos else "Inicio desde el puesto de Secado."
        ),
    )
    return (
        CorridaSecado.objects.select_related(
            "ejecucion__etapa", "ejecucion__equipo", "orden", "lote__producto",
            "finalizada_por",
        ).prefetch_related("ejecucion__salidas__liberacion_calidad").get(pk=corrida.pk)
    )


def estado_calidad_secado(corrida):
    """La decisión de Calidad sobre el polvo de una corrida, o `no_requerida`."""
    if not corrida.ejecucion.etapa.requiere_calidad:
        return "no_requerida"
    salida = next(
        (
            salida for salida in corrida.ejecucion.salidas.all()
            if salida.lote_id == corrida.lote_id
            and salida.naturaleza == SalidaProceso.Naturaleza.PRINCIPAL
        ),
        None,
    )
    decision = getattr(salida, "liberacion_calidad", None) if salida else None
    return decision.estado if decision else "pendiente"


def estado_puesto_secado(usuario):
    """
    Lo que el puesto de Secado dibuja: un estado por torre derivado de su
    ejecución de Secado activa (la que ocupa el equipo; una en curso manda
    sobre una preparada), con los motivos que impiden iniciar calculados por
    la misma función que decide al iniciar; los concentrados que se pueden
    tomar, con el saldo que `preparar_continuacion` va a aceptar; y las
    corridas de hoy. La pantalla no recalcula nada de esto.

    Las ejecuciones `cerrada`/`cancelada` no ocupan la torre: un huérfano de
    un E2E abortado no deja la máquina tomada (`ESTADOS_QUE_OCUPAN_EQUIPO`).
    """
    from calidad.models import LiberacionProceso
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Equipo
    from usuarios.tenancy import filtrar_por_scope

    torres = list(filtrar_por_scope(
        Equipo.objects.filter(activo=True, tipo=Equipo.Tipo.TORRE)
        .select_related("sucursal").order_by("codigo"),
        usuario, campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
    ))
    ids = [torre.pk for torre in torres]

    activas = {}
    for ejecucion in (
        EjecucionProceso.objects.filter(
            etapa__tipo=EtapaProceso.Tipo.SECADO, equipo_id__in=ids,
            estado__in=ESTADOS_QUE_OCUPAN_EQUIPO,
        )
        .select_related("etapa", "equipo", "corrida_secado__lote")
        .prefetch_related("entradas__silo", "entradas__lote_inventario")
        .order_by("pk")
    ):
        actual = activas.get(ejecucion.equipo_id)
        if actual is None or (
            actual.estado == EjecucionProceso.Estado.PREPARACION
            and ejecucion.estado != EjecucionProceso.Estado.PREPARACION
        ):
            activas[ejecucion.equipo_id] = ejecucion

    en_calidad = {}
    for corrida in (
        CorridaSecado.objects.filter(
            ejecucion__equipo_id__in=ids,
            ejecucion__salidas__naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            ejecucion__salidas__liberacion_calidad__estado=LiberacionProceso.Estado.PENDIENTE,
        ).select_related("ejecucion", "lote").order_by("pk")
    ):
        en_calidad[corrida.ejecucion.equipo_id] = corrida

    def resumen(ejecucion):
        corrida = getattr(ejecucion, "corrida_secado", None)
        entrada = next(iter(ejecucion.entradas.all()), None)
        origen = None
        if entrada is not None and entrada.silo_id:
            origen = entrada.silo.codigo
        elif entrada is not None and entrada.lote_inventario_id:
            origen = entrada.lote_inventario.codigo
        return {
            "id": corrida.pk if corrida else None,
            "ejecucion_id": ejecucion.pk,
            "ejecucion_codigo": ejecucion.codigo,
            "ejecucion_estado": ejecucion.estado,
            "lote_codigo": corrida.lote.codigo_lote if corrida else None,
            "origen": origen,
            # Texto, como en los serializers: el tipo del frontend es `string`.
            "cantidad": str(entrada.cantidad) if entrada else None,
            "unidad": entrada.unidad if entrada else None,
            "iniciada_en": ejecucion.inicio,
        }

    filas = []
    for torre in torres:
        ejecucion = activas.get(torre.pk)
        motivos, motivos_para_tomar, resolver_en = [], [], None
        if ejecucion is None:
            estado = "disponible"
            # La misma regla con que `preparar_continuacion` y
            # `preparar_secado_desde_inventario` rechazan la torre.
            impedimento = motivo_equipo_no_habilitado(torre)
            if impedimento:
                motivos_para_tomar, resolver_en = [impedimento], RESOLVER_CIP
        elif ejecucion.estado == EjecucionProceso.Estado.PREPARACION:
            estado = "preparada"
            corrida = getattr(ejecucion, "corrida_secado", None)
            if corrida is None:
                # Sin corrida no hay `secados/{id}/cancelar-preparacion/`: la
                # ejecución se cancela desde la bandeja de Procesos.
                motivos = [
                    f"{ejecucion.codigo} no tiene lote de Secado y no puede iniciarse: "
                    "cancela esa ejecución en Procesos y vuelve a tomar el concentrado."
                ]
            else:
                tipados = motivos_tipados_para_iniciar_secado(corrida, ejecucion=ejecucion)
                motivos = [motivo for motivo, _ in tipados]
                # El enlace es del primer motivo, que es el que la tarjeta muestra.
                resolver_en = tipados[0][1] if tipados else None
        else:
            estado = "en_curso"
        avisos = [] if estado == "en_curso" else avisos_de_torre(torre)
        pendiente = en_calidad.get(torre.pk)
        filas.append({
            "equipo_id": torre.pk, "codigo": torre.codigo, "nombre": torre.nombre,
            "estado": estado,
            "corrida": resumen(ejecucion) if ejecucion is not None else None,
            "motivos_para_iniciar": motivos,
            "motivos_para_tomar": motivos_para_tomar,
            "resolver_en": resolver_en,
            "avisos": avisos,
            "falta_inspeccion": AVISO_INSPECCION_PREOPERATIVA in avisos,
            "en_calidad": (
                {"id": pendiente.pk, "lote_codigo": pendiente.lote.codigo_lote}
                if pendiente is not None else None
            ),
        })

    concentrados = []
    # Descarta en la consulta lo que no puede seguir a Secado: el proceso de
    # la ruta (o el de origen, sin ruta) no tiene un Secado activo después de
    # la etapa que produjo la salida. Es un filtro grueso, no la regla: la
    # decide `siguiente_etapa_para_salida`, abajo, sobre lo que queda.
    secado_por_delante = EtapaProceso.objects.filter(
        tipo=EtapaProceso.Tipo.SECADO, activa=True, proceso_id=OuterRef("proceso_de_ruta"),
    ).filter(
        ~Q(proceso_id=OuterRef("ejecucion__etapa__proceso_id"))
        | Q(orden__gt=OuterRef("ejecucion__etapa__orden"))
    )
    salidas = filtrar_por_scope(
        SalidaProceso.objects.annotate(
            proceso_de_ruta=Coalesce("ruta_producto__proceso_id", "ejecucion__etapa__proceso_id"),
        ).filter(
            Exists(secado_por_delante),
            liberacion_calidad__estado=LiberacionProceso.Estado.LIBERADO,
            silo__isnull=False, lote__isnull=False, lote__corrida_secado__isnull=True,
            destino__in=[
                SalidaProceso.Destino.PENDIENTE,
                SalidaProceso.Destino.SIGUIENTE_PROCESO,
                SalidaProceso.Destino.ESTANDARIZACION,
            ],
        ).exclude(naturaleza=SalidaProceso.Naturaleza.MERMA)
        .exclude(salida_de_lote_anulado())
        .select_related("ejecucion__etapa", "silo", "lote__producto", "ruta_producto")
        .order_by("lote__codigo_lote", "pk"),
        usuario, campo_sucursal="ejecucion__sucursal_id",
        campo_empresa="ejecucion__sucursal__empresa_id",
    )
    for salida in salidas:
        siguiente = siguiente_etapa_para_salida(salida=salida)
        if siguiente is None or siguiente.tipo != EtapaProceso.Tipo.SECADO:
            continue
        disponible = disponible_de_salida(salida)
        if disponible <= 0:
            continue
        concentrados.append({
            "salida_id": salida.pk, "etapa_id": siguiente.pk,
            "lote_codigo": salida.lote.codigo_lote,
            "producto": salida.lote.producto.nombre if salida.lote.producto_id else "",
            "silo": salida.silo.codigo,
            "disponible": str(disponible), "unidad": salida.unidad,
        })

    hoy = timezone.localdate()
    corridas_de_hoy = [
        {
            "id": corrida.pk,
            "equipo": corrida.ejecucion.equipo.codigo if corrida.ejecucion.equipo_id else None,
            "lote_codigo": corrida.lote.codigo_lote,
            "estado": corrida.ejecucion.estado,
            "estado_calidad": estado_calidad_secado(corrida),
        }
        # Iniciadas o cerradas hoy: una preparación que nunca empezó no es
        # trabajo del día, y un huérfano cancelado sin iniciar tampoco.
        for corrida in CorridaSecado.objects.filter(ejecucion__equipo_id__in=ids)
        .filter(Q(ejecucion__inicio__date=hoy) | Q(finalizada_en__date=hoy))
        .select_related("ejecucion__etapa", "ejecucion__equipo", "lote")
        .prefetch_related("ejecucion__salidas__liberacion_calidad")
        .order_by("-pk")
    ]
    return {
        "torres": filas,
        "concentrados": concentrados,
        "corridas_de_hoy": corridas_de_hoy,
        "estados": [
            {"valor": valor, "etiqueta": etiqueta}
            for valor, etiqueta in EjecucionProceso.Estado.choices
        ],
    }


@transaction.atomic
def preparar_secado_desde_inventario(
    *, orden, existencia, equipo, codigo_lote, cantidad, usuario,
):
    """Prepara una torre con materia prima externa liberada; el inicio es `iniciar_secado`."""
    from inventario.models import Existencia, Insumo, Ubicacion
    from inventario.servicios import motivo_equipo_no_habilitado, registrar_salida
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update(of=("self",)).select_related(
        "producto", "sucursal"
    ).get(pk=orden.pk)
    existencia = Existencia.objects.select_for_update(of=("self",)).select_related(
        "lote__insumo", "lote__sucursal", "ubicacion"
    ).get(pk=existencia.pk)
    equipo = adquirir_equipo(equipo_id=equipo.pk)
    cantidad = Decimal(str(cantidad))

    if orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        raise ValidationError({"orden": "La orden no esta programada o en proceso."})
    if existencia.lote.insumo.categoria != Insumo.Categoria.MATERIA_PRIMA:
        raise ValidationError({"existencia": "Selecciona un lote clasificado como materia prima."})
    if existencia.lote.insumo.unidad != Insumo.Unidad.KG:
        raise ValidationError({
            "existencia": (
                "El balance actual de Secado trabaja en kg. Configura esta materia prima "
                "en kg antes de alimentarla; no se aplican conversiones ocultas."
            )
        })
    if not existencia.lote.utilizable or existencia.ubicacion.tipo != Ubicacion.Tipo.DISPONIBLE:
        raise ValidationError({
            "existencia": "La materia prima debe estar vigente y aprobada por Calidad."
        })
    if cantidad > existencia.cantidad_disponible:
        raise ValidationError({
            "cantidad": f"El lote externo tiene {existencia.cantidad_disponible} kg disponibles."
        })
    if equipo.tipo != Equipo.Tipo.TORRE or not equipo.activo:
        raise ValidationError({"equipo": "Selecciona una torre activa de esta planta."})
    impedimento = motivo_equipo_no_habilitado(equipo)
    if impedimento:
        raise ValidationError({"equipo": impedimento})

    rutas = RutaProducto.objects.filter(
        sucursal=orden.sucursal, producto=orden.producto,
        insumo_origen=existencia.lote.insumo, activa=True,
    ).select_related("proceso").prefetch_related(Prefetch(
        "proceso__etapas",
        queryset=EtapaProceso.objects.filter(activa=True).order_by("orden", "pk"),
        to_attr="etapas_para_inicio",
    )).order_by(
        "prioridad", "pk"
    )
    ruta = next((
        candidata for candidata in rutas
        if candidata.proceso.etapas_para_inicio
        and candidata.proceso.etapas_para_inicio[0].tipo == EtapaProceso.Tipo.SECADO
    ), None)
    if ruta is None:
        raise ValidationError({
            "ruta_producto": (
                f"{orden.producto.nombre} no tiene una ruta de Secado que acepte "
                f"{existencia.lote.insumo.nombre} como materia prima externa."
            )
        })
    etapa = ruta.proceso.etapas_para_inicio[0]
    codigo = str(codigo_lote).strip()
    if not codigo:
        raise ValidationError({"codigo_lote": "Ingresa el codigo del lote de salida."})
    lote = Lote(
        sucursal=orden.sucursal, codigo_lote=codigo,
        codigo_lote_propuesto=codigo, op=orden.codigo, orden=orden,
        producto=orden.producto, equipo=equipo, fecha=timezone.localdate(),
        estado=Lote.Estado.EN_PROCESO,
    )
    lote.full_clean()
    lote.save()
    ejecucion = EjecucionProceso(
        codigo=f"EJ-SEC-EXT-{lote.pk}", etapa=etapa, ruta_producto=ruta,
        sucursal=orden.sucursal, equipo=equipo, responsable=usuario,
        estado=EjecucionProceso.Estado.PREPARACION,
    )
    ejecucion.full_clean()
    ejecucion.save()
    lote.ejecucion = ejecucion
    lote.save(update_fields=["ejecucion"])
    entrada = EntradaProceso(
        ejecucion=ejecucion, lote_inventario=existencia.lote,
        tipo=EntradaProceso.Tipo.PRINCIPAL, cantidad=cantidad, unidad="kg",
    )
    entrada.full_clean()
    entrada.save()
    registrar_salida(
        existencia_id=existencia.pk, cantidad=cantidad, usuario=usuario,
        documento_tipo="procesos.EjecucionProceso", documento_id=ejecucion.pk,
        motivo=f"Alimentacion externa de Secado {ejecucion.codigo}", consumo=True,
    )
    corrida = CorridaSecado.objects.create(
        ejecucion=ejecucion, orden=orden, lote=lote, kg_alimentacion=cantidad,
    )
    if orden.estado == OrdenProduccion.Estado.PROGRAMADA:
        orden.estado = OrdenProduccion.Estado.EN_PROCESO
        orden.save(update_fields=["estado"])
    EventoProceso.objects.create(
        ejecucion=ejecucion, usuario=usuario, tipo="preparacion_secado_externo",
        estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        motivo=(
            f"Lote externo {existencia.lote.codigo}; {cantidad} kg de "
            f"{existencia.lote.insumo.nombre}."
        ),
    )
    return corrida


@transaction.atomic
def cerrar_secado(
    *, corrida_id, usuario, kg_alimentacion, solidos_entrada_pct,
    kg_polvo, kg_finos=0, kg_merma=0, controles=None,
):
    """Cierra torre, balance y lote como un solo hecho transaccional."""
    from calidad.models import LiberacionProceso
    from produccion.models import Lote, OrdenProduccion
    from produccion.servicios import cerrar_lote_producido, registrar_produccion
    from .models import CorridaSecado

    corrida = (
        CorridaSecado.objects.select_for_update(of=("self",))
        .select_related("ejecucion__etapa", "ejecucion__equipo", "lote", "orden")
        .get(pk=corrida_id)
    )
    corrida.ejecucion = EjecucionProceso.objects.select_for_update(
        of=("self",)
    ).select_related("etapa", "equipo").get(pk=corrida.ejecucion_id)
    if corrida.ejecucion.estado not in {
        EjecucionProceso.Estado.EJECUCION,
        EjecucionProceso.Estado.PAUSADA,
    }:
        raise ValidationError("Solo una corrida de Secado activa puede cerrarse.")

    alimentacion = Decimal(str(kg_alimentacion))
    if corrida.kg_alimentacion is not None and alimentacion != corrida.kg_alimentacion:
        raise ValidationError({
            "kg_alimentacion": (
                f"La corrida consumio {corrida.kg_alimentacion} kg del lote externo; "
                "el cierre debe conservar esa cantidad auditable."
            )
        })
    corrida.kg_alimentacion = alimentacion
    corrida.solidos_entrada_pct = Decimal(str(solidos_entrada_pct))
    corrida.kg_polvo = Decimal(str(kg_polvo))
    corrida.kg_finos = Decimal(str(kg_finos))
    corrida.kg_merma = Decimal(str(kg_merma))
    corrida.controles = controles or {}
    corrida.finalizada_por = usuario
    corrida.finalizada_en = timezone.now()
    corrida.full_clean()

    lote = Lote.objects.select_for_update(of=("self",)).get(pk=corrida.lote_id)
    if lote.estado != Lote.Estado.EN_PROCESO:
        raise ValidationError("El lote de Secado ya no está en proceso.")
    lote.kg_producidos = corrida.kg_polvo
    lote.estado = Lote.Estado.PRODUCIDO
    lote.save(update_fields=["kg_producidos", "estado"])
    corrida.lote = lote
    corrida.save()
    estado_anterior = corrida.ejecucion.estado
    requiere_calidad = corrida.ejecucion.etapa.requiere_calidad
    registrar_produccion(
        lote=lote,
        destino_salida=(
            SalidaProceso.Destino.PENDIENTE
            if requiere_calidad
            else SalidaProceso.Destino.ENVASADO
        ),
    )
    corrida.ejecucion.refresh_from_db()
    salida = SalidaProceso.objects.get(
        ejecucion=corrida.ejecucion,
        lote=lote,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
    )
    if requiere_calidad:
        LiberacionProceso.objects.get_or_create(salida=salida)

    # La misma cola que el `PATCH` del lote y que Mantequilla: orden a
    # pendiente de Calidad, descuento de bodega y aviso al área. Cerrar la
    # corrida aquí dejaba las dos últimas sin hacer, así que el polvo salía de
    # la torre sin descontar sus sacos y sin llegar a la bandeja de Calidad —
    # y como el descuento no falla sino que no ocurre, nada lo delataba.
    aviso_bodega = cerrar_lote_producido(lote=lote, usuario=usuario)

    if aviso_bodega:
        EventoProceso.objects.create(
            ejecucion=corrida.ejecucion, usuario=usuario,
            tipo="consumo_materiales_pendiente", motivo=aviso_bodega,
        )

    EventoProceso.objects.create(
        ejecucion=corrida.ejecucion,
        tipo="cierre_secado",
        estado_anterior=estado_anterior,
        estado_nuevo=EjecucionProceso.Estado.CERRADA,
        motivo=(
            f"Polvo {corrida.kg_polvo} kg; finos {corrida.kg_finos} kg; "
            f"merma {corrida.kg_merma} kg."
        ),
        usuario=usuario,
    )
    return corrida
