"""
Pruebas de los modelos de liberación.

Cubren lo que la base de datos no puede garantizar por sí sola: la forma del
JSON de una plantilla y las condiciones que hacen de una liberación una firma
y no un campo más.
"""

from datetime import date

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from maestros.models import DocumentoLiberacion, Mandante, Producto
from produccion.models import Lote

from .models import Liberacion, RegistroCalidad


class DocumentoLiberacionTests(TestCase):
    """
    La plantilla se valida al guardarla porque una mal escrita no falla: se
    dibuja a medias. Un campo con el tipo mal tecleado simplemente no aparece,
    y quien completa el registro en planta no tiene forma de notar que falta.
    """

    def setUp(self):
        # Hay pruebas que cuentan documentos, y el catálogo del Dossier se
        # siembra por migración también en la base de pruebas.
        DocumentoLiberacion.objects.all().delete()

    def _documento(self, **cambios):
        datos = {
            "nombre": "Ficha técnica",
            "aplica_a": ["polvo"],
            "plantilla": [],
        }
        datos.update(cambios)
        return DocumentoLiberacion(**datos)

    def test_una_plantilla_vacia_es_valida(self):
        """Un documento sin campos es una atestación: se firma, no se llena."""
        self._documento().full_clean()

    def test_exige_al_menos_una_familia(self):
        with self.assertRaises(ValidationError) as error:
            self._documento(aplica_a=[]).full_clean()

        self.assertIn("aplica_a", error.exception.message_dict)

    def test_rechaza_una_familia_que_no_existe(self):
        with self.assertRaises(ValidationError) as error:
            self._documento(aplica_a=["polvillo"]).full_clean()

        self.assertIn("polvillo", str(error.exception))

    def test_rechaza_un_campo_con_tipo_no_reconocido(self):
        with self.assertRaises(ValidationError) as error:
            self._documento(
                plantilla=[{"clave": "x", "etiqueta": "X", "tipo": "textito"}]
            ).full_clean()

        self.assertIn("textito", str(error.exception))

    def test_rechaza_un_campo_sin_etiqueta_que_mostrar(self):
        with self.assertRaises(ValidationError):
            self._documento(plantilla=[{"clave": "x", "tipo": "texto"}]).full_clean()

    def test_rechaza_claves_repetidas(self):
        """Los valores se guardan por clave: una repetida se pisa en silencio."""
        with self.assertRaises(ValidationError) as error:
            self._documento(
                plantilla=[
                    {"clave": "mg", "etiqueta": "Materia grasa", "tipo": "decimal"},
                    {"clave": "mg", "etiqueta": "MG (repetida)", "tipo": "decimal"},
                ]
            ).full_clean()

        self.assertIn("repetidas", str(error.exception).lower())

    def test_rechaza_un_campo_objeto_sin_subcampos_declarados(self):
        """MODELO_DATOS.md §2.6: sin `campos` solo queda JSON crudo en pantalla."""
        with self.assertRaises(ValidationError) as error:
            self._documento(
                plantilla=[{"clave": "controles", "etiqueta": "Controles", "tipo": "objeto"}]
            ).full_clean()

        self.assertIn("JSON crudo", str(error.exception))

    def test_acepta_un_campo_objeto_con_sus_subcampos(self):
        self._documento(
            plantilla=[
                {
                    "clave": "controles",
                    "etiqueta": "Controles",
                    "tipo": "objeto",
                    "campos": [{"clave": "ph", "etiqueta": "pH", "tipo": "decimal"}],
                }
            ]
        ).full_clean()

    def test_rechaza_un_enum_que_no_declara_sus_valores(self):
        with self.assertRaises(ValidationError):
            self._documento(
                plantilla=[{"clave": "turno", "etiqueta": "Turno", "tipo": "enum"}]
            ).full_clean()

    def test_rechaza_un_parametro_que_no_esta_en_el_catalogo(self):
        """Un campo atado a un fisicoquímico inexistente nunca se cotejaría."""
        with self.assertRaises(ValidationError) as error:
            self._documento(
                plantilla=[
                    {
                        "clave": "x",
                        "etiqueta": "X",
                        "tipo": "decimal",
                        "parametro": "inventado",
                    }
                ]
            ).full_clean()

        self.assertIn("inventado", str(error.exception))

    def test_no_se_repite_el_codigo_entre_documentos(self):
        DocumentoLiberacion.objects.create(
            nombre="Ficha técnica", aplica_a=["polvo"], codigo="CCAA.FORM.016.02"
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DocumentoLiberacion.objects.create(
                    nombre="Otra ficha", aplica_a=["crema"], codigo="CCAA.FORM.016.02"
                )

    def test_varios_documentos_pueden_no_tener_codigo(self):
        """La unicidad no debe impedir cargar documentos sin código todavía."""
        DocumentoLiberacion.objects.create(nombre="Uno", aplica_a=["polvo"])
        DocumentoLiberacion.objects.create(nombre="Dos", aplica_a=["polvo"])

        self.assertEqual(DocumentoLiberacion.objects.filter(codigo="").count(), 2)


class BaseExpediente(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=self.producto,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )
        self.documento = DocumentoLiberacion.objects.create(
            nombre="Ficha técnica", aplica_a=["polvo"]
        )
        self.usuario = User.objects.create_user("jandrade", password="x")


class RegistroCalidadTests(BaseExpediente):
    def test_un_documento_se_completa_una_sola_vez_por_lote(self):
        """
        Dos registros del mismo documento se pisarían al calcular el avance, y
        el checklist podría darse por cumplido con el borrador equivocado.
        """
        RegistroCalidad.objects.create(lote=self.lote, documento=self.documento)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                RegistroCalidad.objects.create(lote=self.lote, documento=self.documento)

    def test_el_mismo_documento_si_se_completa_en_otro_lote(self):
        otro = Lote.objects.create(
            codigo_lote="CCAA6141N",
            producto=self.producto,
            fecha=date(2026, 7, 21),
            kg_producidos=9000,
        )
        RegistroCalidad.objects.create(lote=self.lote, documento=self.documento)
        RegistroCalidad.objects.create(lote=otro, documento=self.documento)

        self.assertEqual(RegistroCalidad.objects.count(), 2)

    def test_un_formulario_observado_debe_decir_que_se_observo(self):
        """Sin la observación, quien lo lea después no sabe qué resolver."""
        registro = RegistroCalidad(
            lote=self.lote,
            documento=self.documento,
            estado=RegistroCalidad.Estado.OBSERVADO,
        )

        with self.assertRaises(ValidationError) as error:
            registro.full_clean()

        self.assertIn("observacion", error.exception.message_dict)


class LiberacionTests(BaseExpediente):
    def test_hay_una_sola_liberacion_por_lote(self):
        Liberacion.objects.create(lote=self.lote)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Liberacion.objects.create(lote=self.lote)

    def test_una_concesion_sin_motivo_no_se_guarda(self):
        liberacion = Liberacion(
            lote=self.lote,
            estado=Liberacion.Estado.CONCESION,
            concesion=True,
            autorizada_por=self.usuario,
        )

        with self.assertRaises(ValidationError) as error:
            liberacion.full_clean()

        self.assertIn("motivo_concesion", error.exception.message_dict)

    def test_el_estado_concesion_exige_la_marca_permanente(self):
        liberacion = Liberacion(
            lote=self.lote,
            estado=Liberacion.Estado.CONCESION,
            concesion=False,
            motivo_concesion="Aceptado por el mandante según correo del 21-05.",
            autorizada_por=self.usuario,
        )

        with self.assertRaises(ValidationError) as error:
            liberacion.full_clean()

        self.assertIn("concesion", error.exception.message_dict)

    def test_una_liberacion_sin_autorizador_no_es_una_firma(self):
        liberacion = Liberacion(lote=self.lote, estado=Liberacion.Estado.LIBERADO)

        with self.assertRaises(ValidationError) as error:
            liberacion.full_clean()

        self.assertIn("autorizada_por", error.exception.message_dict)

    def test_un_lote_liberado_puede_volver_a_revision(self):
        """Al desmarcar un documento, la autorización ya no se sostiene."""
        liberacion = Liberacion.objects.create(
            lote=self.lote,
            estado=Liberacion.Estado.LIBERADO,
            autorizada_por=self.usuario,
        )

        self.assertTrue(liberacion.puede_pasar_a(Liberacion.Estado.EN_REVISION))
        self.assertFalse(liberacion.puede_pasar_a(Liberacion.Estado.PENDIENTE))

    def test_liberado_y_bajo_concesion_son_los_dos_estados_que_dejan_despachar(self):
        """Es lo único que Despachos necesita preguntar."""
        liberacion = Liberacion.objects.create(
            lote=self.lote,
            estado=Liberacion.Estado.CONCESION,
            concesion=True,
            motivo_concesion="Aceptado por el mandante según correo del 21-05.",
            autorizada_por=self.usuario,
        )
        self.assertTrue(liberacion.liberado)

        liberacion.estado = Liberacion.Estado.RECHAZADO
        self.assertFalse(liberacion.liberado)

    def test_el_expediente_nace_pendiente(self):
        """Que no tenga liberación no significa que no la necesite."""
        self.assertEqual(
            Liberacion.objects.create(lote=self.lote).estado,
            Liberacion.Estado.PENDIENTE,
        )
