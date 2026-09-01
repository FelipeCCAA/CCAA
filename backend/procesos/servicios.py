from decimal import Decimal, InvalidOperation
import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from .models import (
    CorridaCondensacion, CorridaDescremacion, CorridaMantequilla,
    EjecucionProceso, EntradaProceso, EtapaProceso, EventoProceso, SalidaProceso,
    RutaProducto,
)


def tipos_equipo_para_etapa(tipo_etapa):
    """Tipos físicos válidos para una etapa configurable del proceso."""
    from maestros.models import Equipo

    return {
        EtapaProceso.Tipo.DESCREMACION: {Equipo.Tipo.OTRO},
        EtapaProceso.Tipo.EVAPORACION: {Equipo.Tipo.EVAPORADOR},
        EtapaProceso.Tipo.CONDENSACION: {Equipo.Tipo.EVAPORADOR},
        EtapaProceso.Tipo.SECADO: {Equipo.Tipo.TORRE},
        EtapaProceso.Tipo.ENVASADO: {Equipo.Tipo.ENVASADORA, Equipo.Tipo.LINEA},
        EtapaProceso.Tipo.MANTEQUILLA: {Equipo.Tipo.LINEA, Equipo.Tipo.OTRO},
        EtapaProceso.Tipo.TRANSFERENCIA: {Equipo.Tipo.CARGA},
        EtapaProceso.Tipo.OTRO: {Equipo.Tipo.OTRO},
    }.get(tipo_etapa, set())


def etapa_para_producto(*, producto, sucursal, tipo):
    """Obtiene la etapa desde la ruta del producto; conserva fallback histórico."""
    etapa = (
        EtapaProceso.objects.filter(
            proceso__rutas_producto__producto=producto,
            proceso__rutas_producto__sucursal=sucursal,
            proceso__rutas_producto__activa=True,
            tipo=tipo,
            activa=True,
        )
        .order_by("proceso__rutas_producto__prioridad", "orden")
        .first()
    )
    if etapa is not None:
        return etapa
    return (
        EtapaProceso.objects.filter(tipo=tipo, activa=True)
        .order_by("proceso__version", "orden")
        .last()
    )


def destino_salida_de_ruta(*, producto, sucursal, etapa):
    """Decide si el resultado continúa o termina en su destino real."""
    siguiente = EtapaProceso.objects.filter(
        proceso=etapa.proceso, activa=True, orden__gt=etapa.orden,
    ).order_by("orden").first()
    if siguiente is not None:
        if siguiente.tipo == EtapaProceso.Tipo.ENVASADO:
            return SalidaProceso.Destino.ENVASADO
        return SalidaProceso.Destino.SIGUIENTE_PROCESO
    ruta = RutaProducto.objects.filter(
        producto=producto, sucursal=sucursal, proceso=etapa.proceso, activa=True,
    ).order_by("prioridad").first()
    destino = (ruta.destino if ruta else "").strip().lower()
    if "despacho" in destino:
        return SalidaProceso.Destino.DESPACHO_DIRECTO
    if "inventario" in destino:
        return SalidaProceso.Destino.INVENTARIO
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
    if destino.sucursal_id != lote.sucursal_id:
        raise ValidationError({"silo_destino": "El destino pertenece a otra planta."})
    corrida = CorridaCondensacion(
        ejecucion=ejecucion, orden=lote.orden, lote=lote,
        silo_origen=entrada.silo, silo_destino=destino,
        litros_entrada=entrada.cantidad.quantize(Decimal("0.01")),
    )
    corrida.full_clean()
    corrida.save()
    EventoProceso.objects.create(
        ejecucion=ejecucion, usuario=usuario, tipo="corrida_configurada",
        estado_anterior=ejecucion.estado, estado_nuevo=ejecucion.estado,
        motivo=f"Evaporación configurada hacia {destino.codigo}",
    )
    return corrida


@transaction.atomic
def crear_mantequilla_guiada(
    *, orden_id, lote_crema_id, equipo_id, codigo_lote_mantequilla,
    kg_crema, usuario, lote_suero_id=None,
):
    """Crea ejecución, lote de salida y corrida sin pasos parciales huérfanos."""
    from maestros.models import Equipo
    from produccion.models import Lote, OrdenProduccion

    orden = OrdenProduccion.objects.select_for_update(of=("self",)).select_related(
        "producto", "sucursal"
    ).get(pk=orden_id)
    crema = Lote.objects.select_for_update(of=("self",)).select_related("producto").get(pk=lote_crema_id)
    equipo = Equipo.objects.select_for_update().get(pk=equipo_id)
    suero = Lote.objects.select_for_update().get(pk=lote_suero_id) if lote_suero_id else None
    if orden.producto.categoria != "mantequilla":
        raise ValidationError({"orden": "La orden no corresponde a mantequilla."})
    if orden.estado not in {OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO}:
        raise ValidationError({"orden": "La orden no está programada o en proceso."})
    if crema.sucursal_id != orden.sucursal_id or crema.producto.familia != "crema":
        raise ValidationError({"lote_crema": "Selecciona un lote de crema de esta planta."})
    if equipo.sucursal_id != orden.sucursal_id or not equipo.activo:
        raise ValidationError({"equipo": "La línea no está activa en esta planta."})
    if equipo.tipo not in {Equipo.Tipo.LINEA, Equipo.Tipo.OTRO}:
        raise ValidationError({"equipo": "El equipo no corresponde a la línea de mantequilla."})
    if suero and suero.sucursal_id != orden.sucursal_id:
        raise ValidationError({"lote_suero": "El lote de suero pertenece a otra planta."})
    etapa = etapa_para_producto(
        producto=orden.producto, sucursal=orden.sucursal,
        tipo=EtapaProceso.Tipo.MANTEQUILLA,
    )
    if etapa is None:
        raise ValidationError({"orden": "El producto no tiene una etapa de mantequilla activa."})
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
        codigo=f"EJ-MANT-{lote_salida.pk}", etapa=etapa,
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
    return corrida


@transaction.atomic
def preparar_continuacion(*, salida_id, etapa_id, equipo_id, cantidad, usuario):
    """Reserva parte de una salida liberada y prepara su próxima ejecución."""
    from maestros.models import Equipo

    salida = (
        SalidaProceso.objects.select_for_update(of=("self",))
        .select_related("ejecucion__etapa", "ejecucion__sucursal", "silo")
        .get(pk=salida_id)
    )
    try:
        etapa = EtapaProceso.objects.select_related("proceso").get(
            pk=etapa_id, activa=True
        )
    except (EtapaProceso.DoesNotExist, TypeError, ValueError) as error:
        raise ValidationError("La etapa seleccionada no existe o está inactiva.") from error
    origen = salida.ejecucion.etapa
    siguiente_orden = (
        EtapaProceso.objects.filter(
            proceso_id=origen.proceso_id,
            activa=True,
            orden__gt=origen.orden,
        )
        .order_by("orden")
        .values_list("orden", flat=True)
        .first()
    )
    if etapa.proceso_id != origen.proceso_id or etapa.orden != siguiente_orden:
        raise ValidationError(
            "La etapa elegida debe ser la siguiente etapa activa de la ruta; no se pueden saltar procesos."
        )
    if salida.destino not in {
        SalidaProceso.Destino.PENDIENTE,
        SalidaProceso.Destino.SIGUIENTE_PROCESO,
    }:
        raise ValidationError(
            f"La salida fue destinada a {salida.get_destino_display()} y no puede consumirse como continuación."
        )

    try:
        equipo = Equipo.objects.get(
            pk=equipo_id, sucursal_id=salida.ejecucion.sucursal_id, activo=True
        )
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
    consumido = salida.usos_como_origen.aggregate(total=Sum("cantidad"))["total"] or 0
    disponible = salida.cantidad - consumido
    if cantidad > disponible:
        raise ValidationError(
            f"La salida tiene {disponible} {salida.unidad} disponibles."
        )

    ejecucion = EjecucionProceso(
        codigo=f"CONT-{salida.pk}-{uuid.uuid4().hex[:8].upper()}",
        etapa=etapa,
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
    if salida.destino == SalidaProceso.Destino.PENDIENTE:
        salida.destino = SalidaProceso.Destino.SIGUIENTE_PROCESO
        salida.save(update_fields=["destino"])
    return transicionar_ejecucion(
        ejecucion_id=ejecucion.pk,
        estado_nuevo=EjecucionProceso.Estado.PREPARACION,
        usuario=usuario,
        motivo=f"Continuación de {salida.ejecucion.codigo}",
    )


@transaction.atomic
def transicionar_ejecucion(*, ejecucion_id, estado_nuevo, usuario, motivo=""):
    ejecucion = (
        EjecucionProceso.objects.select_for_update()
        .select_related("etapa")
        .get(pk=ejecucion_id)
    )
    permitidos = EjecucionProceso.TRANSICIONES.get(ejecucion.estado, set())
    if estado_nuevo not in permitidos:
        raise ValidationError(
            f"No se puede pasar de {ejecucion.get_estado_display()} a {estado_nuevo}."
        )

    if estado_nuevo == EjecucionProceso.Estado.EJECUCION:
        if not ejecucion.equipo_id or not usuario:
            raise ValidationError("Para iniciar se requiere equipo y usuario responsable.")
        if not ejecucion.entradas.exists():
            raise ValidationError("Para iniciar se requiere al menos una entrada de proceso.")
        ocupada = EjecucionProceso.objects.select_for_update().filter(
            equipo_id=ejecucion.equipo_id,
            estado=EjecucionProceso.Estado.EJECUCION,
        ).exclude(pk=ejecucion.pk).first()
        if ocupada:
            raise ValidationError(
                f"{ejecucion.equipo.nombre} está ocupado por {ocupada.codigo}."
            )

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
    EventoProceso.objects.create(
        ejecucion=ejecucion,
        tipo="cambio_estado",
        estado_anterior=anterior,
        estado_nuevo=estado_nuevo,
        motivo=motivo,
        usuario=usuario,
    )
    return ejecucion


def genealogia_lote(
    lote_id, direccion, profundidad_maxima=12, sucursal_id=None, empresa_id=None
):
    from produccion.models import Lote
    from .models import EntradaProceso, SalidaProceso

    if direccion not in {"atras", "adelante"}:
        raise ValueError("Dirección inválida.")

    def acotar_por_tenant(consulta, prefijo=""):
        if sucursal_id is not None:
            return consulta.filter(**{f"{prefijo}sucursal_id": sucursal_id})
        if empresa_id is not None:
            return consulta.filter(
                **{f"{prefijo}sucursal__empresa_id": empresa_id}
            )
        return consulta

    def serializar_nodo(lote):
        return {
            "id": lote.id,
            "codigo": lote.codigo_lote,
            "producto": lote.producto.nombre,
            "fecha": lote.fecha,
        }

    lotes = acotar_por_tenant(Lote.objects.select_related("producto"))
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
                actual_relacion_id=F("ejecucion__salidas__lote_id")
            ).select_related("lote__producto")
            relaciones = acotar_por_tenant(relaciones, "lote__").order_by(
                "ejecucion__salidas__id", "id"
            )
        else:
            relaciones = SalidaProceso.objects.filter(
                ejecucion__entradas__lote_id__in=ids_actuales,
                lote_id__isnull=False,
            ).annotate(
                actual_relacion_id=F("ejecucion__entradas__lote_id")
            ).select_related("lote__producto")
            relaciones = acotar_por_tenant(relaciones, "lote__").order_by(
                "ejecucion__entradas__id", "id"
            )

        por_actual = {actual_id: [] for actual_id in ids_actuales}
        for relacion in relaciones:
            por_actual[relacion.actual_relacion_id].append(relacion.lote)

        siguiente = {}
        for actual_id in ids_actuales:
            for relacionado in por_actual[actual_id]:
                origen, destino = (
                    (relacionado.id, actual_id)
                    if direccion == "atras"
                    else (actual_id, relacionado.id)
                )
                enlaces.append({"origen": origen, "destino": destino})
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

    etapa = etapa_para_producto(
        producto=vale.producto,
        sucursal=vale.silo_destino.sucursal,
        tipo=EtapaProceso.Tipo.ESTANDARIZACION,
    )

    if etapa is None:
        # No es un error del vale: es que nadie declaró el proceso. Se avisa y
        # no se rompe la transferencia, que es una operación de planta y no
        # puede depender de que el maestro esté completo.
        return None

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


@transaction.atomic
def iniciar_condensacion(*, corrida_id, usuario):
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Silo
    from produccion.models import OrdenProduccion
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo
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
    if corrida.orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        raise ValidationError("La orden debe estar programada o en proceso.")
    if not corrida.ejecucion.equipo_id:
        raise ValidationError("La corrida requiere un evaporador asignado.")
    impedimento = motivo_equipo_no_habilitado(corrida.ejecucion.equipo)
    if impedimento:
        raise ValidationError(impedimento)

    origen = Silo.objects.select_for_update().get(pk=corrida.silo_origen_id)
    motivos_silo = motivos_silo_no_disponible(origen, para="proceso")
    if motivos_silo:
        raise ValidationError(f"{origen.codigo}: " + " ".join(motivos_silo))

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
        disponible = saldo_silo(origen)
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
    )
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=corrida.lote, silo=destino,
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


@transaction.atomic
def iniciar_descremacion(*, corrida_id, usuario):
    from inventario.servicios import motivo_equipo_no_habilitado
    from maestros.models import Silo
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo
    from .models import EntradaProceso

    corrida = CorridaDescremacion.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "analisis_entrada",
        "silo_entera", "silo_descremada", "estanque_crema",
    ).get(pk=corrida_id)
    if corrida.estado != CorridaDescremacion.Estado.BORRADOR:
        raise ValidationError("Solo una descremación en borrador puede iniciarse.")
    corrida.clean()
    if not corrida.ejecucion.equipo_id:
        raise ValidationError("La descremación requiere un equipo asignado.")
    impedimento = motivo_equipo_no_habilitado(corrida.ejecucion.equipo)
    if impedimento:
        raise ValidationError(impedimento)
    origen = Silo.objects.select_for_update().get(pk=corrida.silo_entera_id)
    motivos = motivos_silo_no_disponible(origen, para="proceso")
    if motivos:
        raise ValidationError(f"{origen.codigo}: " + " ".join(motivos))
    if corrida.analisis_entrada.estado != corrida.analisis_entrada.Estado.CONFIRMADO:
        raise ValidationError({"analisis_entrada": "El análisis de entrada debe estar confirmado."})
    if corrida.analisis_entrada.grasa != corrida.grasa_entrada or corrida.analisis_entrada.sng != corrida.sng_entrada:
        raise ValidationError({
            "analisis_entrada": "Grasa y SNG deben coincidir con el análisis seleccionado."
        })
    if saldo_silo(origen) < corrida.litros_entrada:
        raise ValidationError(f"{origen.codigo} no tiene litros suficientes.")

    EntradaProceso.objects.create(
        ejecucion=corrida.ejecucion, silo=origen,
        tipo=EntradaProceso.Tipo.PRINCIPAL, cantidad=corrida.litros_entrada, unidad="L",
    )
    if corrida.ejecucion.estado == EjecucionProceso.Estado.BORRADOR:
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.PREPARACION, usuario=usuario,
        )
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.EJECUCION, usuario=usuario,
    )
    corrida.estado = CorridaDescremacion.Estado.EN_CURSO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    return corrida


@transaction.atomic
def cerrar_descremacion(
    *, corrida_id, usuario, litros_descremada, grasa_descremada,
    litros_crema, grasa_crema, controles=None,
):
    from maestros.models import Silo
    from produccion.models import Lote
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import heredar_atribuciones, motivos_silo_no_disponible, saldo_silo
    from .dominio import calcular_balance_descremacion
    from .models import SalidaProceso

    corrida = CorridaDescremacion.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "silo_entera",
        "silo_descremada", "estanque_crema", "producto_descremada", "producto_crema",
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
        if not destino.activo or destino.estado in {
            Silo.Estado.BLOQUEADO_CALIDAD, Silo.Estado.EN_CIP, Silo.Estado.FUERA_SERVICIO,
        }:
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
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
        destino=SalidaProceso.Destino.PENDIENTE,
        cantidad=ld, unidad="L",
    )
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=lotes.get("crema"), silo=destino_c,
        naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
        clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
        destino=SalidaProceso.Destino.PENDIENTE,
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
    corrida.litros_descremada, corrida.grasa_descremada = ld, gd
    corrida.litros_crema, corrida.grasa_crema = lc, gc
    corrida.controles = {**(controles or {}), "avisos_balance": list(balance.avisos)}
    corrida.estado = CorridaDescremacion.Estado.CERRADA
    corrida.finalizada_por = usuario
    corrida.finalizada_en = ahora
    corrida.save()
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.PENDIENTE_CONTROL, usuario=usuario,
    )
    if corrida.ejecucion.etapa.requiere_calidad:
        Silo.objects.filter(pk__in=[destino_d.pk, destino_c.pk]).update(
            estado=Silo.Estado.BLOQUEADO_CALIDAD
        )
    else:
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.CERRADA, usuario=usuario,
        )
    return corrida


@transaction.atomic
def iniciar_mantequilla(*, corrida_id, usuario):
    from inventario.servicios import motivo_equipo_no_habilitado
    from calidad.models import LiberacionProceso
    from maestros.models import Silo
    from produccion.models import OrdenProduccion
    from recepcion.models import MovimientoSilo
    from recepcion.servicios import motivos_silo_no_disponible, saldo_silo
    from .models import EntradaProceso, SalidaProceso

    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "ejecucion__equipo", "orden",
        "lote_crema__producto", "lote_mantequilla__producto",
    ).get(pk=corrida_id)
    if corrida.estado != CorridaMantequilla.Estado.BORRADOR:
        raise ValidationError("Solo una corrida en borrador puede iniciarse.")
    corrida.clean()
    if corrida.orden.estado not in {
        OrdenProduccion.Estado.PROGRAMADA, OrdenProduccion.Estado.EN_PROCESO,
    }:
        raise ValidationError("La orden debe estar programada o en proceso.")
    impedimento = motivo_equipo_no_habilitado(corrida.ejecucion.equipo)
    if impedimento:
        raise ValidationError(impedimento)
    utilizado = EntradaProceso.objects.filter(
        lote=corrida.lote_crema, unidad__iexact="kg"
    ).aggregate(total=Sum("cantidad"))["total"] or Decimal("0")
    disponible = Decimal(str(corrida.lote_crema.kg_producidos or 0)) - utilizado
    if corrida.kg_crema > disponible:
        raise ValidationError(f"El lote de crema solo tiene {disponible} kg disponibles.")
    fuente_tk = (
        SalidaProceso.objects.select_for_update(of=("self",))
        .select_related("silo", "liberacion_calidad__analisis_silo")
        .filter(lote=corrida.lote_crema, silo__isnull=False)
        .order_by("registrada_en")
        .first()
    )
    if fuente_tk is not None:
        liberacion = getattr(fuente_tk, "liberacion_calidad", None)
        if not liberacion or liberacion.estado != LiberacionProceso.Estado.LIBERADO:
            raise ValidationError("El lote de crema todavía no está liberado por Calidad.")
        densidad = liberacion.analisis_silo.densidad if liberacion.analisis_silo_id else None
        if densidad is None or densidad <= 0:
            raise ValidationError("El análisis de la crema no tiene una densidad válida.")
        litros_consumidos = (
            Decimal(str(corrida.kg_crema)) * Decimal("1000") / Decimal(str(densidad))
        ).quantize(Decimal("0.01"))
        tk_crema = Silo.objects.select_for_update().get(pk=fuente_tk.silo_id)
        motivos_tk = motivos_silo_no_disponible(tk_crema, para="proceso")
        if motivos_tk:
            raise ValidationError(f"{tk_crema.codigo}: " + " ".join(motivos_tk))
        if saldo_silo(tk_crema) < litros_consumidos:
            raise ValidationError(
                f"{tk_crema.codigo} no tiene los {litros_consumidos} L equivalentes "
                "a la crema solicitada."
            )
        MovimientoSilo.objects.create(
            silo=tk_crema,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=litros_consumidos,
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            origen_id=corrida.pk,
            operacion_id=corrida.operacion_id,
            lote=corrida.lote_crema,
            producto=corrida.lote_crema.producto,
            equipo=corrida.ejecucion.equipo,
            usuario=usuario,
        )
    EntradaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=corrida.lote_crema,
        cantidad=corrida.kg_crema, unidad="kg",
    )
    if corrida.ejecucion.estado == EjecucionProceso.Estado.BORRADOR:
        transicionar_ejecucion(
            ejecucion_id=corrida.ejecucion_id,
            estado_nuevo=EjecucionProceso.Estado.PREPARACION, usuario=usuario,
        )
    transicionar_ejecucion(
        ejecucion_id=corrida.ejecucion_id,
        estado_nuevo=EjecucionProceso.Estado.EJECUCION, usuario=usuario,
    )
    corrida.estado = CorridaMantequilla.Estado.EN_PROCESO
    corrida.iniciada_por = usuario
    corrida.iniciada_en = timezone.now()
    corrida.save(update_fields=["estado", "iniciada_por", "iniciada_en"])
    if corrida.orden.estado == OrdenProduccion.Estado.PROGRAMADA:
        corrida.orden.estado = OrdenProduccion.Estado.EN_PROCESO
        corrida.orden.save(update_fields=["estado"])
    return corrida


@transaction.atomic
def cerrar_mantequilla(
    *, corrida_id, usuario, kg_mantequilla, kg_suero=0, kg_merma=0, controles=None
):
    from .models import SalidaProceso

    corrida = CorridaMantequilla.objects.select_for_update(of=("self",)).select_related(
        "ejecucion__etapa", "lote_mantequilla__producto", "lote_suero", "orden"
    ).get(pk=corrida_id)
    if corrida.estado != CorridaMantequilla.Estado.EN_PROCESO:
        raise ValidationError("Solo una corrida en proceso puede cerrarse.")
    corrida.kg_mantequilla = Decimal(str(kg_mantequilla))
    corrida.kg_suero = Decimal(str(kg_suero))
    corrida.kg_merma = Decimal(str(kg_merma))
    corrida.controles = controles or {}
    corrida.clean()
    SalidaProceso.objects.create(
        ejecucion=corrida.ejecucion, lote=corrida.lote_mantequilla,
        naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
        clasificacion=SalidaProceso.Clasificacion.GRANEL,
        destino=SalidaProceso.Destino.ENVASADO,
        cantidad=corrida.kg_mantequilla, unidad="kg",
    )
    if corrida.kg_suero:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion, lote=corrida.lote_suero,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.SUBPRODUCTO,
            destino=SalidaProceso.Destino.PENDIENTE,
            cantidad=corrida.kg_suero, unidad="kg",
        )
    if corrida.kg_merma:
        SalidaProceso.objects.create(
            ejecucion=corrida.ejecucion, naturaleza=SalidaProceso.Naturaleza.MERMA,
            clasificacion=SalidaProceso.Clasificacion.MERMA,
            destino=SalidaProceso.Destino.OTRO,
            cantidad=corrida.kg_merma, unidad="kg", motivo="Merma de mantequilla",
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
    from produccion.models import OrdenProduccion
    if corrida.orden.estado == OrdenProduccion.Estado.EN_PROCESO:
        corrida.orden.estado = OrdenProduccion.Estado.PENDIENTE_CALIDAD
        corrida.orden.save(update_fields=["estado"])
    try:
        from inventario.servicios import consumir_receta_produccion
        consumir_receta_produccion(
            lote_produccion=corrida.lote_mantequilla, usuario=usuario
        )
    except ValidationError as error:
        EventoProceso.objects.create(
            ejecucion=corrida.ejecucion, usuario=usuario,
            tipo="consumo_materiales_pendiente",
            motivo=" ".join(error.messages),
        )
    from inventario.servicios import _notificar_area
    _notificar_area(
        "calidad", tipo="producto_pendiente_calidad",
        titulo="Mantequilla pendiente de Calidad",
        mensaje=(
            f"Lote {corrida.lote_mantequilla.codigo_lote} terminado y "
            "pendiente de liberación."
        ),
        documento_tipo="lote_produccion",
        documento_id=corrida.lote_mantequilla_id,
    )
    return corrida
