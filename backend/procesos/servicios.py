from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import EjecucionProceso, EventoProceso


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

        # Reglas de planta 3 y 15: no se produce en un equipo que está en CIP
        # ni en uno cuyo último aseo quedó observado. La primera es física
        # antes que informática — hay soda circulando por dentro.
        from inventario.servicios import motivo_equipo_no_habilitado

        # Ojo con el nombre: `motivo` es el parámetro de esta función —el
        # porqué de la transición, que va al evento—. Llamar igual a esta
        # variable lo pisaba con `None` y el evento quedaba sin motivo.
        impedimento = motivo_equipo_no_habilitado(ejecucion.equipo)

        if impedimento:
            raise ValidationError(impedimento)

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

    if direccion not in {"atras", "adelante"}:
        raise ValueError("Dirección inválida.")

    visitados = {int(lote_id)}
    frontera = [(int(lote_id), 0)]
    nodos = {}
    enlaces = []

    while frontera:
        actual_id, profundidad = frontera.pop(0)
        lotes = Lote.objects.select_related("producto")
        if sucursal_id is not None:
            lotes = lotes.filter(sucursal_id=sucursal_id)
        elif empresa_id is not None:
            lotes = lotes.filter(sucursal__empresa_id=empresa_id)
        lote = lotes.get(pk=actual_id)
        nodos[actual_id] = {
            "id": lote.id,
            "codigo": lote.codigo_lote,
            "producto": lote.producto.nombre,
            "fecha": lote.fecha,
        }
        if profundidad >= profundidad_maxima:
            continue

        if direccion == "atras":
            ejecuciones = lote.salidas_proceso.select_related("ejecucion").all()
            relacionados = [
                entrada.lote
                for salida in ejecuciones
                for entrada in salida.ejecucion.entradas.select_related("lote__producto")
                if (sucursal_id is None or entrada.lote.sucursal_id == sucursal_id)
                and (empresa_id is None or entrada.lote.sucursal.empresa_id == empresa_id)
            ]
            pares = [(rel.id, actual_id) for rel in relacionados]
        else:
            ejecuciones = lote.entradas_proceso.select_related("ejecucion").all()
            relacionados = [
                salida.lote
                for entrada in ejecuciones
                for salida in entrada.ejecucion.salidas.select_related("lote__producto")
                if salida.lote_id
                and (sucursal_id is None or salida.lote.sucursal_id == sucursal_id)
                and (empresa_id is None or salida.lote.sucursal.empresa_id == empresa_id)
            ]
            pares = [(actual_id, rel.id) for rel in relacionados]

        for relacionado, (origen, destino) in zip(relacionados, pares):
            enlaces.append({"origen": origen, "destino": destino})
            if relacionado.id not in visitados:
                visitados.add(relacionado.id)
                frontera.append((relacionado.id, profundidad + 1))

    return {"nodos": list(nodos.values()), "enlaces": enlaces}
