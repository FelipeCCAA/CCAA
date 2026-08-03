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
    #
    # Son 21 documentos y no 19 porque el checklist de cuerpos extraños se
    # separó en uno por evaporador: en planta son tres formatos con piezas
    # distintas —Scheffers 2 tiene pulmones y coil, el VEB tiene cuatro
    # efectos— y una plantilla única pediría el estado de piezas que ese
    # evaporador no tiene.
    POR_AREA = {
        "recepcion": 1,
        "condensacion": 5,
        "secado": 8,
        "envase": 7,
    }

    def test_estan_los_del_dossier(self):
        self.assertEqual(DocumentoLiberacion.objects.count(), 21)

    def test_el_checklist_de_cuerpos_extranos_va_por_evaporador(self):
        """
        Uno solo obligaría a elegir un evaporador y dejar los otros dos sin
        sus piezas, o a mezclar las tres listas. Las dos cosas convierten el
        checklist en un trámite: se marca igual y no dice qué se revisó.
        """
        codigos = {"CCAA.Cond.FORM.005", "CCAA.Cond.FORM.014", "CCAA.Cond.FORM.016"}

        checklists = DocumentoLiberacion.objects.filter(codigo__in=codigos)

        self.assertEqual(checklists.count(), 3)

        # Cada uno con sus piezas: si dos coincidieran, sobraría uno.
        piezas = [
            tuple(c["clave"] for c in d.plantilla) for d in checklists
        ]
        self.assertEqual(len(set(piezas)), 3)

    def test_solo_el_veb_tiene_cuarto_efecto(self):
        """La diferencia que hace que no puedan compartir plantilla."""
        veb = DocumentoLiberacion.objects.get(codigo="CCAA.Cond.FORM.016")
        sch3 = DocumentoLiberacion.objects.get(codigo="CCAA.Cond.FORM.014")

        claves_veb = {c["clave"] for c in veb.plantilla}
        claves_sch3 = {c["clave"] for c in sch3.plantilla}

        self.assertIn("tapa_sup_4_estado", claves_veb)
        self.assertNotIn("tapa_sup_4_estado", claves_sch3)

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

    #: Los únicos documentos con plantilla cargada, y de dónde salió cada una.
    #: La lista es explícita para que agregar una plantilla exija declarar su
    #: formato de origen aquí — que es la forma de que nadie invente una.
    PLANTILLAS_DE_UN_FORMATO_REAL = {
        "CCAA.Sec.FORM.007": "Check list cuerpos extraños Rovema 3 y 4",
        "CCAA.Cond.FORM.005": "Check list CE Scheffers 2",
        "CCAA.Cond.FORM.014": "Checklist CE Scheffer 3",
        "CCAA.Cond.FORM.016": "Checklist CE VEB",
        "CCAA.Sec.FORM.003": "Inspeccion preoperativa egron 1",
    }

    #: Documentos cuyo formato **sí** se revisó y que aun así no llevan
    #: plantilla, con el motivo. No es lo mismo que «todavía no lo hemos
    #: mirado»: son grillas de lecturas horarias, y aplanarlas a un campo por
    #: ítem daría un formulario que se completa entero habiendo registrado una
    #: de las veinticuatro lecturas que el formato pide.
    REVISADOS_Y_SIN_PLANTILLA = {
        "CCAA.Sec.FORM.022": (
            "Lecturas horarias OK/No-OK de tres tipos en tres turnos: es lo "
            "que MonitoreoPPRO y PproLectura ya modelan."
        ),
        "CCAA.Sec.FORM.021": (
            "Lecturas horarias de kilos y consumo: es ControlProcesoLectura."
        ),
        "CCAA.Sec.FORM.024": (
            "Grilla de 24 horas. La mitad «al inicio de la operación» sí sería "
            "un checklist, pero la mitad «cada 1 hora» son lecturas; partir un "
            "formato de planta en dos registros lo decide Calidad."
        ),
    }

    def test_los_formatos_revisados_sin_plantilla_siguen_sin_ella(self):
        """
        Que un formato exista no significa que su plantilla deba cargarse.
        Estos tres se revisaron y se dejaron fuera a propósito; sin esta
        prueba, el próximo que los encuentre en `Documentos Planta/` los
        cargaría creyendo que faltaban.
        """
        for codigo, motivo in self.REVISADOS_Y_SIN_PLANTILLA.items():
            with self.subTest(codigo=codigo, motivo=motivo):
                documento = DocumentoLiberacion.objects.get(codigo=codigo)
                self.assertEqual(documento.plantilla, [], motivo)

    def test_solo_tienen_plantilla_los_que_salen_de_un_formato_real(self):
        """
        Una plantilla inventada es peor que ninguna: un formulario que pide
        campos equivocados se completa igual y da el documento por cumplido.
        Los demás siguen como atestación hasta tener su formato a la vista.
        """
        con_plantilla = {
            d.codigo
            for d in DocumentoLiberacion.objects.all()
            if d.plantilla
        }

        self.assertEqual(con_plantilla, set(self.PLANTILLAS_DE_UN_FORMATO_REAL))

    def test_los_campos_de_una_plantilla_declaran_su_tipo(self):
        """
        Un campo sin tipo lo dibuja el frontend como texto libre, y un estado
        OK/A que se teclea a mano deja de ser un estado.
        """
        tipos = {
            "texto", "entero", "decimal", "fecha", "fechaHora", "hora",
            "booleano", "enum", "objeto",
        }

        for documento in DocumentoLiberacion.objects.exclude(plantilla=[]):
            for campo in documento.plantilla:
                with self.subTest(documento=documento.codigo, campo=campo.get("clave")):
                    self.assertIn(campo.get("tipo"), tipos)
                    self.assertTrue(campo.get("clave"))
                    self.assertTrue(campo.get("etiqueta"))

    def test_un_enum_declara_sus_valores(self):
        for documento in DocumentoLiberacion.objects.exclude(plantilla=[]):
            for campo in documento.plantilla:
                if campo.get("tipo") != "enum":
                    continue

                with self.subTest(documento=documento.codigo, campo=campo["clave"]):
                    self.assertTrue(campo.get("valores"))

    def test_ninguna_plantilla_usa_un_tipo_que_la_pantalla_no_dibuja(self):
        """
        `lista` está en el contrato pero el formulario dinámico no lo dibuja:
        cae al campo de texto por defecto, sin avisar. Una lectura horaria
        declarada así se convertiría en un cuadro de texto libre.
        """
        for documento in DocumentoLiberacion.objects.exclude(plantilla=[]):
            for campo in documento.plantilla:
                with self.subTest(documento=documento.codigo, campo=campo.get("clave")):
                    self.assertNotEqual(campo.get("tipo"), "lista")

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
