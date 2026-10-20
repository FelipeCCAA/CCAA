"""Balance contable en litros; no equivale a tolerancia física ni de RC."""

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


def litros_exactos(valor, *, campo="litros", permitir_cero=True):
    try:
        cantidad = Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError({campo: "Indica una cantidad válida en litros."})
    if not cantidad.is_finite() or cantidad.as_tuple().exponent < -2:
        raise ValidationError(
            {campo: "Usa como máximo dos decimales (0,01 L), sin redondear."}
        )
    if cantidad < 0 or (not permitir_cero and cantidad == 0):
        raise ValidationError({campo: "La cantidad debe ser positiva."})
    if cantidad > Decimal("9999999999.99"):
        raise ValidationError({campo: "La cantidad excede la capacidad del registro."})
    return cantidad


def componentes_vale(vale):
    return sum(
        (
            litros_exactos(getattr(vale, nombre) or 0, campo=nombre)
            for nombre in ("litros_entera", "litros_descremada", "litros_crema")
        ),
        Decimal("0"),
    )


def exigir_balance(vale):
    volumen = litros_exactos(vale.volumen, campo="volumen", permitir_cero=False)
    total = componentes_vale(vale)
    if total != volumen:
        raise ValidationError(
            {
                "volumen": (
                    f"El ingreso ({volumen:.2f} L) debe igualar los componentes ({total:.2f} L)."
                )
            }
        )
    if not vale.litros_entera or not vale.silo_entera_id or not vale.silo_destino_id:
        raise ValidationError(
            "Faltan origen, destino o litros de entera para transferir."
        )
    vale.clean()
    return total


def balance_vale(vale):
    # La lectura de históricos incongruentes debe mostrar la retención, no
    # impedir que el operador abra el expediente para investigarlo.
    partes = [Decimal(str(getattr(vale, nombre) or 0)) for nombre in
              ("litros_entera", "litros_descremada", "litros_crema")]
    total = sum(partes, Decimal("0"))
    volumen = Decimal(str(vale.volumen or 0))
    actual = volumen if vale.ejecutado_en else Decimal("0")
    medicion = None
    diferencia = None
    for acto in vale.actos.order_by("creado_en", "pk"):
        if acto.tipo == "adicion":
            actual += acto.litros
        elif acto.tipo == "retiro":
            actual -= acto.litros
        elif acto.tipo == "medicion":
            medicion = acto.volumen_medido
            diferencia = Decimal(acto.rectificacion["diferencia"])
    return {
        "componentes": f"{total:.2f}",
        "volumen_ejecutado": f"{actual:.2f}",
        "volumen_medido": None if medicion is None else f"{medicion:.2f}",
        "diferencia": None if diferencia is None else f"{diferencia:.2f}",
        "pendiente": (bool(vale.ejecutado_en) and (total != volumen or volumen <= 0 or any(p < 0 for p in partes)))
        or (diferencia is not None and diferencia != 0),
    }


def cantidad_operativa_salida(salida):
    """La foto original se conserva; el disponible incluye actos vinculados."""
    if salida.ejecucion.vale_id and salida.unidad.lower() == "l":
        vale = salida.ejecucion.vale
        if salida.silo_id == vale.silo_destino_id:
            return vale.volumen_operativo
    return salida.cantidad
