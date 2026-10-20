"""Rectificaciones y movimientos nuevos; nunca reescriben la transferencia."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from auditoria.registro import crear_en_lote_con_auditoria
from calidad.evidencia import bloquear_catalogo
from maestros.models import Silo
from procesos.models import EntradaProceso
from procesos.servicios import exigir_destino_sin_reserva, litros_origen_reservados
from recepcion.models import MovimientoSilo
from recepcion.servicios import (
    atribuir_salida,
    heredar_atribuciones,
    motivos_silo_no_disponible,
)
from usuarios.models import Rol, rol_de

from .balance import balance_vale, litros_exactos
from .models import ActoValeEstandarizacion, ValeEstandarizacion
from .servicios import _saldo


def _rectificacion(vale, datos):
    permitidos = {*ValeEstandarizacion.CAMPOS_RECETA, "observaciones"}
    if not datos or set(datos) - permitidos:
        raise ValidationError(
            "Indica campos de receta u observaciones para rectificar documentalmente."
        )
    cambios = {}
    for campo, nuevo in datos.items():
        campo_modelo = vale._meta.get_field(campo)
        anterior = getattr(vale, campo_modelo.attname)
        if isinstance(anterior, Decimal):
            anterior = str(anterior)
        if campo in ValeEstandarizacion.CAMPOS_QUE_MUEVEN_LIBRO and campo.startswith(
            ("litros", "volumen")
        ):
            nuevo = str(litros_exactos(nuevo, campo=campo))
        if not isinstance(nuevo, (str, int, float, type(None))):
            raise ValidationError("El valor documental debe ser simple.")
        if str(anterior) != str(nuevo):
            cambios[campo] = [anterior, nuevo]
    if not cambios:
        raise ValidationError("No hay valores distintos para rectificar.")
    return cambios


def _exigir_sin_uso_posterior(vale):
    propios = list(vale.actos.values_list("clave", flat=True))
    if (
        MovimientoSilo.objects.filter(
            silo_id=vale.silo_destino_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
            fecha_hora__gte=vale.ejecutado_en,
        )
        .exclude(operacion_id__in=propios)
        .exists()
        or vale.lotes.exclude(estado="borrador").exists()
    ):
        raise ValidationError(
            "Hay consumo posterior o un lote asociado. Producción, Calidad y Bodega "
            "deben revisar el material afectado; no se permite una reversión automática."
        )
    if (
        EntradaProceso.objects.filter(
            silo_id=vale.silo_destino_id,
            ejecucion__inicio__gte=vale.ejecutado_en,
        )
        .exclude(ejecucion__vale=vale)
        .exists()
    ):
        raise ValidationError(
            "El silo alimenta otro proceso; requiere revisión de las áreas afectadas."
        )


@transaction.atomic
def registrar_acto(*, vale_id, usuario, datos):
    # Comparte la frontera con firmas/despacho; se toma antes del vale y silos.
    bloquear_catalogo(escritura=True)
    vale = ValeEstandarizacion.objects.select_for_update().get(pk=vale_id)
    tipo = datos["tipo"]
    if tipo in {"adicion", "retiro", "documental"} and rol_de(usuario) not in {
        Rol.PRODUCCION,
        Rol.ADMIN,
    }:
        raise PermissionDenied(
            "Solo Producción autoriza rectificaciones y correcciones físicas."
        )
    existente = ActoValeEstandarizacion.objects.filter(clave=datos["clave"]).first()
    firma = {
        "tipo": tipo,
        "motivo": datos["motivo"],
        "litros": str(datos["litros"]) if datos.get("litros") is not None else None,
        "silo_contraparte": datos["silo_contraparte"].pk
        if datos.get("silo_contraparte")
        else None,
        "volumen_medido": str(datos["volumen_medido"])
        if datos.get("volumen_medido") is not None
        else None,
        "rectificacion": datos.get("rectificacion", {}),
    }
    if existente:
        if existente.vale_id != vale.pk or existente.solicitud != firma:
            raise ValidationError(
                "La clave ya identifica otro acto; vuelve a cargar el vale."
            )
        return vale
    if MovimientoSilo.objects.filter(operacion_id=datos["clave"]).exists():
        raise ValidationError("La clave ya identifica otro movimiento físico.")
    if not vale.ejecutado_en:
        raise ValidationError("Primero debe registrarse la transferencia del vale.")
    if vale.estado == vale.Estado.ANULADO:
        raise ValidationError(
            "El vale está anulado; requiere revisión antes de registrar nuevos actos."
        )

    ids = {vale.silo_destino_id}
    contraparte = datos.get("silo_contraparte")
    if contraparte:
        ids.add(contraparte.pk)
    silos = {
        s.pk: s
        for s in Silo.objects.select_for_update().filter(pk__in=ids).order_by("pk")
    }
    actual = Decimal(balance_vale(vale)["volumen_ejecutado"])
    cambios = {}
    if tipo == "medicion":
        medido = litros_exactos(datos["volumen_medido"], campo="volumen_medido")
        cambios = {"volumen_contable": str(actual), "diferencia": str(medido - actual)}
    elif tipo == "documental":
        cambios = _rectificacion(vale, datos["rectificacion"])
    else:
        _exigir_sin_uso_posterior(vale)
        if contraparte.pk == vale.silo_destino_id:
            raise ValidationError(
                "Selecciona una contraparte distinta al silo del vale."
            )
        litros = litros_exactos(datos["litros"], permitir_cero=False)
        origen = silos[contraparte.pk if tipo == "adicion" else vale.silo_destino_id]
        destino = silos[vale.silo_destino_id if tipo == "adicion" else contraparte.pk]
        # Un retiro puede resolver material retenido; no evade CIP ni reservas.
        if tipo == "adicion":
            motivos = motivos_silo_no_disponible(origen, para="proceso")
            if motivos:
                raise ValidationError(" ".join(motivos))
        for silo in (origen, destino):
            if not silo.activo or silo.estado in {
                Silo.Estado.EN_CIP,
                Silo.Estado.FUERA_SERVICIO,
                Silo.Estado.BLOQUEADO_CALIDAD,
            }:
                raise ValidationError(
                    f"{silo.codigo} no permite esta corrección física."
                )
            exigir_destino_sin_reserva(silo=silo)
            from inventario.models import CicloCIP

            if CicloCIP.objects.filter(
                silo=silo, estado=CicloCIP.Estado.EN_CURSO
            ).exists():
                raise ValidationError(f"{silo.codigo} tiene una limpieza en curso.")
        if _saldo(origen) - litros_origen_reservados(silo_id=origen.pk) < litros:
            raise ValidationError(
                "La corrección supera los litros disponibles en el origen."
            )
        if tipo == "retiro" and litros >= actual:
            raise ValidationError(
                "El retiro debe dejar volumen en el vale; vaciarlo requiere revisión."
            )
        if _saldo(destino) + litros > destino.capacidad_l:
            raise ValidationError("El destino no tiene capacidad para esta corrección.")
        ahora = timezone.now()
        movimientos = crear_en_lote_con_auditoria(
            [
                MovimientoSilo(
                    silo=silo,
                    tipo=clase,
                    litros=litros,
                    fecha_hora=ahora,
                    origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
                    origen_id=vale.pk,
                    operacion_id=datos["clave"],
                    silo_contraparte=otro,
                    motivo=datos["motivo"],
                    usuario=usuario,
                )
                for silo, clase, otro in (
                    (origen, MovimientoSilo.Tipo.SALIDA, destino),
                    (destino, MovimientoSilo.Tipo.INGRESO, origen),
                )
            ]
        )
        atribuir_salida(movimientos[0])
        heredar_atribuciones(movimientos[1], [movimientos[0]])
        cambios = {
            "volumen_ejecutado": [
                str(actual),
                str(actual + (litros if tipo == "adicion" else -litros)),
            ]
        }
        vale.estado = vale.Estado.CORRIGIENDO
        vale.grasa_real = vale.sng_real = None
        vale.agitacion_desde = vale.muestreado_en = None
        vale.save(
            update_fields=[
                "estado",
                "grasa_real",
                "sng_real",
                "agitacion_desde",
                "muestreado_en",
            ]
        )
        # El acto abre otro ciclo del vale; la ejecución inicial ya cerrada
        # conserva su estado y término como hechos históricos.
        from calidad.models import LiberacionProceso

        destinos_afectados = [vale.silo_destino_id]
        if tipo == "retiro":
            destinos_afectados.append(contraparte.pk)
        for decision in (
            LiberacionProceso.objects.select_for_update()
            .filter(
                salida__silo_id__in=destinos_afectados,
                estado=LiberacionProceso.Estado.LIBERADO,
            )
            .order_by("pk")
        ):
            decision.estado = LiberacionProceso.Estado.PENDIENTE
            decision.version_evidencia += 1
            decision.save(update_fields=["estado", "version_evidencia"])
    ActoValeEstandarizacion.objects.create(
        vale=vale,
        usuario=usuario,
        clave=datos["clave"],
        tipo=tipo,
        motivo=datos["motivo"],
        litros=datos.get("litros"),
        silo_contraparte=contraparte,
        volumen_medido=datos.get("volumen_medido"),
        rectificacion=cambios,
        solicitud=firma,
    )
    return vale
