"""
Pruebas de los maestros.

Cubren las garantías que el modelo promete: unicidad de la clave natural del
producto y validación de los rangos de una especificación. Son el equivalente
en Django de las que el prototipo corre en `prototipo/pruebas.html`.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import DocumentoLiberacion, Especificacion, Mandante, Producto


class ProductoTests(TestCase):
    def setUp(self):
        self.nestle = Mandante.objects.create(nombre="Nestlé")
        self.ccaa = Mandante.objects.create(nombre="CCAA")

    def test_no_se_repite_el_nombre_dentro_del_mismo_mandante(self):
        Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.nestle,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Producto.objects.create(
                    nombre="Leche entera en polvo",
                    familia=Producto.Familia.POLVO,
                    mandante=self.nestle,
                )

    def test_el_mismo_nombre_si_puede_existir_en_otro_mandante(self):
        """El mandante es parte de la identidad: no se deduce del nombre."""
        Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.nestle,
        )
        Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.ccaa,
        )

        self.assertEqual(Producto.objects.count(), 2)

    def test_no_se_borra_un_mandante_con_productos(self):
        Producto.objects.create(
            nombre="Crema",
            familia=Producto.Familia.CREMA,
            mandante=self.nestle,
        )

        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.nestle.delete()


class EspecificacionTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )

    def _especificacion(self, **extra):
        datos = {
            "producto": self.producto,
            "version": 1,
            "vigente_desde": date(2026, 1, 1),
            "rangos": {"humedad": {"min": 2.5, "max": 4.0, "obligatorio": True}},
        }
        datos.update(extra)
        return Especificacion(**datos)

    def test_una_especificacion_valida_pasa(self):
        self._especificacion().full_clean()

    def test_rechaza_parametros_desconocidos(self):
        spec = self._especificacion(rangos={"inventado": {"min": 1, "max": 2}})

        with self.assertRaises(ValidationError) as caso:
            spec.full_clean()

        self.assertIn("rangos", caso.exception.message_dict)

    def test_rechaza_minimo_mayor_que_maximo(self):
        spec = self._especificacion(rangos={"humedad": {"min": 5.0, "max": 3.0}})

        with self.assertRaises(ValidationError) as caso:
            spec.full_clean()

        self.assertIn("rangos", caso.exception.message_dict)

    def test_rechaza_valores_no_numericos(self):
        spec = self._especificacion(rangos={"humedad": {"min": "bajo", "max": 4.0}})

        with self.assertRaises(ValidationError):
            spec.full_clean()

    def test_rechaza_vigencia_invertida(self):
        spec = self._especificacion(
            vigente_desde=date(2026, 6, 1), vigente_hasta=date(2026, 1, 1)
        )

        with self.assertRaises(ValidationError) as caso:
            spec.full_clean()

        self.assertIn("vigente_hasta", caso.exception.message_dict)

    def test_no_se_repite_la_version_dentro_del_mismo_producto(self):
        self._especificacion().save()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._especificacion().save()

    def test_el_mismo_producto_admite_varias_versiones(self):
        """Un lote se audita contra la versión vigente en su fecha, no la actual."""
        self._especificacion(version=1, vigente_hasta=date(2026, 5, 31)).save()
        self._especificacion(version=2, vigente_desde=date(2026, 6, 1)).save()

        self.assertEqual(self.producto.especificaciones.count(), 2)


class DossierSembradoTests(TestCase):
    """
    El catálogo del Dossier lo siembra una migración de datos, no un fixture:
    es configuración del sistema, y sin él Liberación no tiene checklist que
    exigir.

    Estas pruebas lo vigilan. Una migración de datos que se rompe no avisa —
    se aplicó una vez, quedó registrada, y el error solo aparece cuando
    alguien instala de cero meses después.
    """

    # Los 19 del Dossier CCAA.Calidad.FORM.023, repartidos por etapa del flujo.
    POR_AREA = {
        "recepcion": 1,
        "condensacion": 3,
        "secado": 8,
        "envase": 7,
    }

    def test_estan_los_diecinueve(self):
        self.assertEqual(DocumentoLiberacion.objects.count(), 19)

    def test_cada_area_tiene_los_suyos(self):
        for area, esperados in self.POR_AREA.items():
            with self.subTest(area=area):
                self.assertEqual(
                    DocumentoLiberacion.objects.filter(area=area).count(), esperados
                )

    def test_todos_declaran_su_area(self):
        """Sin área no se sabe qué equipo tiene el registro pendiente."""
        self.assertFalse(DocumentoLiberacion.objects.filter(area="").exists())

    def test_el_orden_reproduce_el_flujo_del_dossier(self):
        """Recepción primero, envase al final: es el orden en que se completa."""
        areas = list(
            DocumentoLiberacion.objects.order_by("orden").values_list("area", flat=True)
        )

        self.assertEqual(areas[0], "recepcion")
        self.assertEqual(areas[-1], "envase")
        self.assertEqual(sorted(set(areas)), ["condensacion", "envase", "recepcion", "secado"])

    def test_el_disco_de_uperizacion_va_sin_codigo(self):
        """Es un registro físico y no tiene código de formato: no se inventa."""
        disco = DocumentoLiberacion.objects.get(nombre="Disco de Uperización")

        self.assertEqual(disco.codigo, "")
        self.assertEqual(disco.area, "condensacion")

    def test_los_demas_llevan_su_codigo_de_formato(self):
        sin_codigo = DocumentoLiberacion.objects.filter(codigo="").count()

        self.assertEqual(sin_codigo, 1, "solo el disco de uperización")

    def test_entran_como_atestacion(self):
        """
        La plantilla de cada formulario se define después, contra su formato
        real. Inventarla ahora sería peor que dejarla vacía: un formulario que
        pide campos equivocados se completa igual y da el documento por
        cumplido.
        """
        for documento in DocumentoLiberacion.objects.all():
            with self.subTest(documento=documento.codigo or documento.nombre):
                self.assertEqual(documento.plantilla, [])

    def test_todos_aplican_al_polvo(self):
        """
        Pendiente de confirmar con Calidad si alguno aplica también a crema
        (MODELO_DATOS.md §8.3). Se responde editando el catálogo, no migrando.
        """
        for documento in DocumentoLiberacion.objects.all():
            with self.subTest(documento=documento.codigo or documento.nombre):
                self.assertEqual(documento.aplica_a, ["polvo"])

    def test_la_plantilla_sembrada_es_valida(self):
        """Lo que siembra la migración tiene que pasar el clean() del modelo."""
        for documento in DocumentoLiberacion.objects.all():
            with self.subTest(documento=documento.codigo or documento.nombre):
                documento.full_clean()
