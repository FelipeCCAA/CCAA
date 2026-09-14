"""Contrato estable para errores de dominio que alcanzan la frontera REST."""

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def _detalle_validacion(error):
    if hasattr(error, "message_dict"):
        return error.message_dict
    return {"non_field_errors": list(error.messages)}


def _primer_mensaje(detalle):
    for valor in detalle.values():
        if isinstance(valor, (list, tuple)) and valor:
            return str(valor[0])
        if valor:
            return str(valor)
    return "La operación no cumple las reglas del proceso."


def respuesta_error_dominio(error):
    """Convierte una validación esperable en 400/409, sin ocultar sus campos."""
    detalle = _detalle_validacion(error)
    mensaje = _primer_mensaje(detalle)
    texto = mensaje.casefold()
    transicion_no_permitida = texto.startswith("no se puede pasar de ")
    conflicto_equipo = "equipo" in detalle and any(
        termino in texto for termino in ("ocupad", "reservad", "en uso")
    )
    if transicion_no_permitida:
        codigo = "TRANSICION_NO_PERMITIDA"
        estado = status.HTTP_400_BAD_REQUEST
    elif conflicto_equipo:
        codigo = "EQUIPO_OCUPADO"
        estado = status.HTTP_409_CONFLICT
    else:
        codigo = "VALIDACION_DOMINIO"
        estado = status.HTTP_400_BAD_REQUEST
    return Response(
        {"code": codigo, "message": mensaje, "details": detalle},
        status=estado,
    )


def api_exception_handler(exc, context):
    """Deja actuar a DRF y normaliza solo ValidationError de Django no capturados."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, DjangoValidationError):
        return respuesta_error_dominio(exc)
    return None
