"""Contrato estable para errores de dominio que alcanzan la frontera REST."""

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


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


def respuesta_error_integridad(error):
    """
    Traduce un `IntegrityError` de PostgreSQL que ningún serializer anticipó.

    Pasa cuando una regla vive solo en un `CheckConstraint` o una
    `UniqueConstraint` y el dato que la rompe no quedó cubierto por la
    validación de arriba — un campo nuevo, una combinación que nadie
    reprodujo. El texto que manda PostgreSQL nombra la restricción, a veces la
    tabla y la sesión: no es apto para el operador, así que se queda en el
    log y la respuesta lleva un mensaje genérico en español.

    Una violación de unicidad es un conflicto con lo que ya existe (409);
    cualquier otra restricción —un CHECK, una FK— es un dato que el cliente
    nunca debió mandar (400). Esto corre **después** de que la transacción en
    curso ya hizo rollback: el `atomic()` de la vista revierte al desenrollar
    la pila, antes de que la excepción llegue hasta aquí, así que no hay
    escritura a medias que esta respuesta pudiera confirmar.
    """
    logger.exception("IntegrityError no anticipado por ningún serializer")
    texto = str(error).casefold()
    es_unicidad = "unique" in texto or "duplicate key" in texto
    if es_unicidad:
        codigo = "REGISTRO_DUPLICADO"
        estado = status.HTTP_409_CONFLICT
        mensaje = "Ya existe un registro con esos datos."
    else:
        codigo = "ERROR_INTEGRIDAD"
        estado = status.HTTP_400_BAD_REQUEST
        mensaje = "Los datos no cumplen una regla de la base: revisa los valores ingresados."
    return Response(
        {"code": codigo, "message": mensaje, "details": {}},
        status=estado,
    )


def api_exception_handler(exc, context):
    """Deja actuar a DRF y normaliza solo lo que DRF no sabe traducir."""
    response = drf_exception_handler(exc, context)
    if response is not None:
        return response
    if isinstance(exc, DjangoValidationError):
        return respuesta_error_dominio(exc)
    if isinstance(exc, IntegrityError):
        return respuesta_error_integridad(exc)
    return None
