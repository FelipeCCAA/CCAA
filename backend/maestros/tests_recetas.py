"""
Pruebas de la explosión de recetas.

Portadas de `prototipo/js/modelo/pruebas.js` (bloque de recetas). La cadena
que se comprueba es la real de la planta:

    mantequilla 1 kg ──► crema 2 kg ──► leche fresca 8 L
    crema       1 kg ──► leche fresca 4 L
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from . import recetas
from .models import Mandante, Producto, Receta, RecetaComponente


class BaseRecetas(TestCase):
    """La cadena leche → crema → mantequilla, como en la semilla del prototipo."""

    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="CCAA")

        self.leche = self._producto("Leche fresca", "materia_prima", "L")
        self.crema = self._producto("Crema", "intermedio", "kg")
        self.mantequilla = self._producto("Mantequilla", "terminado", "kg")

        # 1 kg de crema ← 4 L de leche
        self.receta_crema = self._receta(self.crema, [(self.leche, 4, "L", 0)])
        # 1 kg de mantequilla ← 2 kg de crema
        self.receta_mantequilla = self._receta(
            self.mantequilla, [(self.crema, 2, "kg", 0)]
        )

        self.fecha = date(2026, 7, 20)

    def _producto(self, nombre, naturaleza, unidad):
        return Producto.objects.create(
            nombre=nombre,
            familia=Producto.Familia.OTRO,
            naturaleza=naturaleza,
            unidad_base=unidad,
            mandante=self.mandante,
        )

    def _receta(self, producto, componentes, cantidad_base=1, desde=date(2026, 1, 1),
                version=1):
        receta = Receta.objects.create(
            producto=producto,
            cantidad_base=cantidad_base,
            vigente_desde=desde,
            version=version,
        )
        for prod, cantidad, unidad, merma in componentes:
            RecetaComponente.objects.create(
                receta=receta,
                producto=prod,
                cantidad=cantidad,
                unidad=unidad,
                merma=merma,
            )
        return receta

    def _ctx(self):
        return list(Producto.objects.all()), list(Receta.objects.all())


class ExplosionTests(BaseRecetas):
    def test_un_kilo_de_crema_son_cuatro_litros_de_leche(self):
        productos, rs = self._ctx()

        e = recetas.insumo_por_unidad(productos, rs, self.crema.id, self.fecha)

        self.assertEqual(e.total_materia_prima, 4)
        self.assertTrue(e.completa)

    def test_la_explosion_es_multinivel_hasta_la_leche(self):
        """La mantequilla no se hace con leche: se hace con crema."""
        productos, rs = self._ctx()

        e = recetas.explosionar(productos, rs, self.mantequilla.id, 1, self.fecha)

        self.assertEqual(e.materia_prima[self.leche.id], 8)
        self.assertTrue(e.completa)

    def test_los_intermedios_tambien_quedan_a_la_vista(self):
        productos, rs = self._ctx()

        e = recetas.explosionar(productos, rs, self.mantequilla.id, 1, self.fecha)

        self.assertEqual(e.requerimientos[self.crema.id], 2)
        self.assertEqual(e.requerimientos[self.leche.id], 8)

    def test_la_merma_aumenta_lo_que_hay_que_meter(self):
        productos, _ = self._ctx()
        self.receta_crema.componentes.update(merma=10)
        rs = list(Receta.objects.all())

        e = recetas.insumo_por_unidad(productos, rs, self.crema.id, self.fecha)

        self.assertAlmostEqual(e.total_materia_prima, 4.4)

    def test_escala_con_la_cantidad_pedida(self):
        productos, rs = self._ctx()

        e = recetas.explosionar(productos, rs, self.crema.id, 250, self.fecha)

        self.assertEqual(e.total_materia_prima, 1000)

    def test_la_cantidad_base_divide(self):
        """Si la receta rinde 10 kg, un kilo cuesta la décima parte."""
        productos, _ = self._ctx()
        self.receta_crema.cantidad_base = 10
        self.receta_crema.save()
        rs = list(Receta.objects.all())

        e = recetas.insumo_por_unidad(productos, rs, self.crema.id, self.fecha)

        self.assertAlmostEqual(e.total_materia_prima, 0.4)

    def test_una_materia_prima_se_explota_a_si_misma(self):
        """Es la hoja del árbol: no falta receta, es que ahí se detiene."""
        productos, rs = self._ctx()

        e = recetas.insumo_por_unidad(productos, rs, self.leche.id, self.fecha)

        self.assertTrue(e.completa)
        self.assertEqual(e.sin_receta, [])


class CadenaIncompletaTests(BaseRecetas):
    def test_un_producto_sin_receta_que_no_es_materia_prima_se_informa(self):
        """
        Devolver un requerimiento a medias sería peor: se parece demasiado a
        uno completo.
        """
        huerfano = self._producto("Suero en polvo", "terminado", "kg")
        productos, rs = self._ctx()

        e = recetas.explosionar(productos, rs, huerfano.id, 1, self.fecha)

        self.assertFalse(e.completa)
        self.assertIn(huerfano.id, e.sin_receta)

    def test_no_se_inventa_un_rendimiento_sobre_una_cadena_rota(self):
        huerfano = self._producto("Suero en polvo", "terminado", "kg")
        productos, rs = self._ctx()

        salida = recetas.rendimiento_desde_materia_prima(
            productos, rs, huerfano.id, 1000, self.fecha
        )

        self.assertIsNone(salida)


class CicloTests(BaseRecetas):
    def test_se_detecta_un_ciclo_indirecto(self):
        """Crema lleva leche y leche llevaría crema: el cálculo colgaría."""
        self._receta(self.leche, [(self.crema, 1, "kg", 0)])
        productos, rs = self._ctx()

        e = recetas.explosionar(productos, rs, self.mantequilla.id, 1, self.fecha)

        self.assertTrue(e.ciclo)
        self.assertFalse(e.completa)

    def test_validar_receta_delata_el_ciclo(self):
        rota = self._receta(self.leche, [(self.crema, 1, "kg", 0)])
        productos, rs = self._ctx()

        v = recetas.validar_receta(rota, productos, rs, self.fecha)

        self.assertFalse(v.permitido)
        self.assertIn("Ciclo", " ".join(v.bloqueos))


class VigenciaTests(BaseRecetas):
    def _dos_versiones(self):
        self.receta_crema.vigente_hasta = date(2026, 5, 31)
        self.receta_crema.save()
        return self._receta(
            self.crema,
            [(self.leche, 5, "L", 0)],
            desde=date(2026, 6, 1),
            version=2,
        )

    def test_la_receta_vigente_depende_de_la_fecha_del_lote(self):
        nueva = self._dos_versiones()
        rs = list(Receta.objects.all())

        de_mayo = recetas.receta_vigente(rs, self.crema.id, date(2026, 5, 15))
        de_julio = recetas.receta_vigente(rs, self.crema.id, date(2026, 7, 20))

        self.assertEqual(de_mayo, self.receta_crema)
        self.assertEqual(de_julio, nueva)

    def test_un_lote_de_mayo_se_explota_con_la_receta_de_mayo(self):
        self._dos_versiones()
        productos, rs = self._ctx()

        mayo = recetas.insumo_por_unidad(
            productos, rs, self.crema.id, date(2026, 5, 15)
        )
        julio = recetas.insumo_por_unidad(
            productos, rs, self.crema.id, date(2026, 7, 20)
        )

        self.assertEqual(mayo.total_materia_prima, 4)
        self.assertEqual(julio.total_materia_prima, 5)


class RendimientoInversoTests(BaseRecetas):
    def test_dice_cuanto_sale_de_una_cantidad_de_leche(self):
        productos, rs = self._ctx()

        kilos = recetas.rendimiento_desde_materia_prima(
            productos, rs, self.crema.id, 1000, self.fecha
        )

        self.assertEqual(kilos, 250)


class LitrosDeLecheTests(BaseRecetas):
    """Lo que conecta el lote con el libro mayor del silo."""

    def test_calcula_los_litros_que_consume_un_lote(self):
        productos, rs = self._ctx()

        litros = recetas.litros_de_leche(
            productos, rs, self.mantequilla.id, 500, self.fecha
        )

        self.assertEqual(litros, 4000)

    def test_devuelve_None_si_la_cadena_esta_rota(self):
        """
        Descontar una cantidad inventada de un silo es peor que no descontar
        nada: el saldo mentiría sin que nadie lo note.
        """
        huerfano = self._producto("Suero en polvo", "terminado", "kg")
        productos, rs = self._ctx()

        litros = recetas.litros_de_leche(
            productos, rs, huerfano.id, 500, self.fecha
        )

        self.assertIsNone(litros)

    def test_se_puede_acotar_a_una_materia_prima(self):
        productos, rs = self._ctx()

        litros = recetas.litros_de_leche(
            productos,
            rs,
            self.crema.id,
            100,
            self.fecha,
            materia_prima_id=self.leche.id,
        )

        self.assertEqual(litros, 400)


class ModeloRecetaTests(BaseRecetas):
    def test_una_materia_prima_no_lleva_receta(self):
        receta = Receta(producto=self.leche, vigente_desde=date(2026, 1, 1))

        with self.assertRaises(ValidationError) as error:
            receta.full_clean()

        self.assertIn("producto", error.exception.message_dict)

    def test_un_componente_no_puede_ser_el_propio_producto(self):
        componente = RecetaComponente(
            receta=self.receta_crema, producto=self.crema, cantidad=1, unidad="kg"
        )

        with self.assertRaises(ValidationError) as error:
            componente.full_clean()

        self.assertIn("producto", error.exception.message_dict)

    def test_la_unidad_del_componente_debe_ser_la_suya(self):
        """Mezclar litros y kilos da un número que parece bueno y no lo es."""
        componente = RecetaComponente(
            receta=self.receta_mantequilla,
            producto=self.leche,
            cantidad=1,
            unidad="kg",
        )

        with self.assertRaises(ValidationError) as error:
            componente.full_clean()

        self.assertIn("unidad", error.exception.message_dict)
