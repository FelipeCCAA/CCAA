from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import SimpleTestCase

from .api_exceptions import api_exception_handler


class ApiExceptionHandlerTests(SimpleTestCase):
    def test_validation_de_dominio_no_termina_en_500(self):
        respuesta = api_exception_handler(
            ValidationError({"estado": "La transición no está permitida."}), {}
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.data["code"], "VALIDACION_DOMINIO")
        self.assertEqual(
            respuesta.data["details"],
            {"estado": ["La transición no está permitida."]},
        )

    def test_equipo_ocupado_es_conflicto_409(self):
        respuesta = api_exception_handler(
            ValidationError({"equipo": "La torre está ocupada por EJ-002."}), {}
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "EQUIPO_OCUPADO")
        self.assertIn("ocupada", respuesta.data["message"])

    def test_transicion_invalida_tiene_codigo_operacional(self):
        respuesta = api_exception_handler(
            ValidationError("No se puede pasar de Pendiente de control a ejecución."),
            {},
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.data["code"], "TRANSICION_NO_PERMITIDA")

    def test_integrity_error_no_termina_en_500(self):
        respuesta = api_exception_handler(
            IntegrityError(
                'new row for relation "lote" violates check constraint '
                '"lote_kg_no_negativos"'
            ),
            {},
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(respuesta.data["code"], "ERROR_INTEGRIDAD")
        # El texto crudo de PostgreSQL —nombres de tabla y de restricción— no
        # sale en la respuesta: se queda en el log.
        self.assertNotIn("lote_kg_no_negativos", respuesta.data["message"])

    def test_integrity_error_de_unicidad_es_conflicto_409(self):
        respuesta = api_exception_handler(
            IntegrityError(
                "duplicate key value violates unique constraint "
                '"lote_codigo_unico_sucursal"'
            ),
            {},
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(respuesta.data["code"], "REGISTRO_DUPLICADO")
