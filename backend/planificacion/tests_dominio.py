"""
Pruebas del planificador.

Portadas de `prototipo/js/modelo/pruebas.js` (bloque del planificador). Lo que
protegen es el acoplamiento entre el programa horario y el balance: si se
rompe, el plan sigue mostrando números y dejan de ser ciertos, que es la peor
forma de fallar para una herramienta de planificación.
"""

from datetime import date

from django.test import TestCase

from maestros.models import Equipo, Mandante, Producto

from . import dominio
from .models import (
    BalanceDia,
    BloquePlan,
    CategoriaConsumo,
    CodigoProduccion,
    SemanaPlan,
)


class BasePlanificador(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )

        # Los rendimientos de la hoja BD del Excel.
        self.rc_nestle = self._codigo("RCSH2N", CategoriaConsumo.PREC_NESTLE, 15900)
        self.ln_nestle = self._codigo("LNSH2", CategoriaConsumo.SECADO_NESTLE, 11000)
        self.lc_ccaa = self._codigo("LCVEB", CategoriaConsumo.SECADO_CCAA, 12400)

        self.semana = SemanaPlan.objects.create(
            codigo="W7", anio=2026, fecha_inicio=date(2026, 2, 9)  # lunes
        )

        # Los equipos son maestro: quién consume leche lo dice el propio
        # equipo, no una lista en el código.
        self.scheffers2 = self._equipo("scheffers2", "Evaporador Scheffers 2", True)
        self.scheffers3 = self._equipo("scheffers3", "Evaporador Scheffers 3", True)
        self.veb = self._equipo("veb", "Evaporador VEB", True)
        self.linea1 = self._equipo("linea1", "Línea 1", False)

    @staticmethod
    def _equipo(codigo, nombre, consume):
        """
        `update_or_create` y no `create`: los equipos se siembran por
        migración de datos, así que ya existen en la base de pruebas
        (CLAUDE.md, «Trampas conocidas»). Se fuerzan sus valores para que la
        prueba no dependa de cómo quedó la siembra.
        """
        equipo, _ = Equipo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "tipo": Equipo.Tipo.EVAPORADOR if consume else Equipo.Tipo.LINEA,
                "consume_leche": consume,
            },
        )
        return equipo

    def _codigo(self, codigo, categoria, rendimiento):
        return CodigoProduccion.objects.create(
            codigo=codigo,
            categoria=categoria,
            rendimiento_lh=rendimiento,
            producto=self.producto,
            mandante=self.mandante,
        )

    def _bloque(self, **cambios):
        datos = {
            "semana": self.semana,
            "equipo": self.scheffers2,
            "dia": 0,
            "hora_inicio": 8,
            "hora_fin": 12,
            "tipo": BloquePlan.Tipo.PRODUCCION,
            "codigo": self.rc_nestle,
        }
        datos.update(cambios)
        return BloquePlan.objects.create(**datos)

    def _balance(self, dia=0, **cambios):
        datos = {"semana": self.semana, "dia": dia}
        datos.update(cambios)
        return BalanceDia.objects.create(**datos)

    def _ctx(self):
        return (
            list(BloquePlan.objects.all()),
            list(CodigoProduccion.objects.all()),
            list(BalanceDia.objects.all()),
        )


class ConsumoDelProgramaTests(BasePlanificador):
    """El núcleo: el consumo sale de las horas del bloque por el rendimiento."""

    def test_el_consumo_sale_de_las_horas_por_el_rendimiento(self):
        self._bloque(hora_inicio=8, hora_fin=12)  # 4 h × 15.900
        bloques, codigos, _ = self._ctx()

        consumo = dominio.consumo_dia(bloques, codigos, 0)

        self.assertEqual(consumo.por_categoria["prec_nestle"], 63600)
        self.assertEqual(consumo.total, 63600)

    def test_cada_codigo_suma_a_su_propia_categoria(self):
        self._bloque(hora_inicio=8, hora_fin=12, codigo=self.rc_nestle)
        self._bloque(
            equipo=self.scheffers3, hora_inicio=8, hora_fin=10, codigo=self.ln_nestle
        )
        bloques, codigos, _ = self._ctx()

        consumo = dominio.consumo_dia(bloques, codigos, 0)

        self.assertEqual(consumo.por_categoria["prec_nestle"], 63600)
        self.assertEqual(consumo.por_categoria["secado_nestle"], 22000)

    def test_las_lineas_de_secado_no_vuelven_a_consumir(self):
        """
        Sin esto se contaría la leche dos veces: el mismo código aparece en el
        evaporador y en la línea que lo recibe.
        """
        self._bloque(equipo=self.scheffers2, hora_inicio=8, hora_fin=12)
        self._bloque(equipo=self.linea1, hora_inicio=8, hora_fin=12)
        bloques, codigos, _ = self._ctx()

        consumo = dominio.consumo_dia(bloques, codigos, 0)

        self.assertEqual(consumo.total, 63600, "solo el evaporador consume")

    def test_un_bloque_de_estado_no_consume(self):
        self._bloque(
            tipo=BloquePlan.Tipo.ESTADO, codigo=None, estado_equipo="A",
            hora_inicio=6, hora_fin=8,
        )
        bloques, codigos, _ = self._ctx()

        self.assertEqual(dominio.consumo_dia(bloques, codigos, 0).total, 0)

    def test_los_bloques_de_otro_dia_no_cuentan(self):
        self._bloque(dia=0, hora_inicio=8, hora_fin=12)
        self._bloque(dia=1, hora_inicio=8, hora_fin=12)
        bloques, codigos, _ = self._ctx()

        self.assertEqual(dominio.consumo_dia(bloques, codigos, 0).total, 63600)

    def test_el_trasvasije_se_toma_del_balance_no_de_los_bloques(self):
        bloques, codigos, _ = self._ctx()

        consumo = dominio.consumo_dia(bloques, codigos, 0, trasvasije=5000)

        self.assertEqual(consumo.derivado, 0)
        self.assertEqual(consumo.total, 5000)

    def test_las_medias_horas_cuentan(self):
        """En planta se programa a media hora: 8.5 es las 08:30."""
        self._bloque(hora_inicio=8, hora_fin=8.5)
        bloques, codigos, _ = self._ctx()

        self.assertEqual(dominio.consumo_dia(bloques, codigos, 0).total, 7950)


class ArrastreDeStockTests(BasePlanificador):
    def test_el_stock_se_arrastra_de_un_dia_al_siguiente(self):
        self._balance(0, stock_inicial=100000, recepcion_nestle=50000)
        self._balance(1, recepcion_nestle=40000)
        self._bloque(dia=0, hora_inicio=8, hora_fin=12)  # 63.600
        bloques, codigos, balances = self._ctx()

        filas = dominio.balance_semana(bloques, codigos, balances)

        self.assertEqual(filas[0].total_disponible, 150000)
        self.assertEqual(filas[0].stock_final, 86400)
        self.assertEqual(filas[1].stock_inicial, 86400, "el final de ayer")

    def test_las_recepciones_suman_al_disponible(self):
        self._balance(
            0, stock_inicial=10000, recepcion_ccaa=1000,
            recepcion_nestle=2000, recepcion_punion=3000,
        )
        bloques, codigos, balances = self._ctx()

        fila = dominio.balance_semana(bloques, codigos, balances)[0]

        self.assertEqual(fila.total_recepciones, 6000)
        self.assertEqual(fila.total_disponible, 16000)

    def test_un_stock_declarado_manda_sobre_el_arrastrado(self):
        """Sirve para corregir a mitad de semana sin rehacer el plan."""
        self._balance(0, stock_inicial=100000)
        self._balance(1, stock_inicial=7)
        bloques, codigos, balances = self._ctx()

        filas = dominio.balance_semana(bloques, codigos, balances)

        self.assertEqual(filas[1].stock_inicial, 7)

    def test_el_saldo_por_origen_descuenta_solo_lo_de_ese_origen(self):
        self._balance(0, recepcion_nestle=100000, recepcion_ccaa=50000)
        self._bloque(dia=0, hora_inicio=8, hora_fin=12, codigo=self.rc_nestle)
        bloques, codigos, balances = self._ctx()

        fila = dominio.balance_semana(bloques, codigos, balances)[0]

        self.assertEqual(fila.stock_por_origen["nestle"], 36400)
        self.assertEqual(fila.stock_por_origen["ccaa"], 50000, "CCAA no se tocó")

    def test_un_saldo_negativo_por_origen_se_marca_como_alarma(self):
        """
        Significa que se programó más leche de la que va a llegar. Se informa,
        no se recorta a cero.
        """
        self._balance(0, recepcion_nestle=1000)
        self._bloque(dia=0, hora_inicio=0, hora_fin=10)
        bloques, codigos, balances = self._ctx()

        fila = dominio.balance_semana(bloques, codigos, balances)[0]

        self.assertLess(fila.stock_por_origen["nestle"], 0)
        self.assertEqual(fila.origenes_negativos, ["nestle"])

    def test_los_ajustes_por_origen_entran_en_el_saldo(self):
        self._balance(0, recepcion_nestle=10000, ajustes={"nestle": -5800})
        bloques, codigos, balances = self._ctx()

        fila = dominio.balance_semana(bloques, codigos, balances)[0]

        self.assertEqual(fila.stock_por_origen["nestle"], 4200)

    def test_un_dia_sin_balance_no_rompe_el_arrastre(self):
        self._balance(0, stock_inicial=50000)
        bloques, codigos, balances = self._ctx()

        filas = dominio.balance_semana(bloques, codigos, balances)

        self.assertEqual(len(filas), 7)
        self.assertEqual(filas[3].stock_inicial, 50000)


class SolapamientoTests(BasePlanificador):
    def test_detecta_dos_bloques_pisandose_en_el_mismo_equipo_y_dia(self):
        a = self._bloque(hora_inicio=8, hora_fin=12)
        b = BloquePlan(
            semana=self.semana, equipo=self.scheffers2, dia=0,
            hora_inicio=10, hora_fin=14, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )

        self.assertTrue(dominio.se_solapan(a, b))
        self.assertFalse(dominio.validar_bloque(b, [a]).permitido)

    def test_dos_bloques_contiguos_no_se_solapan(self):
        """Un turno tras otro es la programación normal."""
        a = self._bloque(hora_inicio=8, hora_fin=14)
        b = BloquePlan(
            semana=self.semana, equipo=self.scheffers2, dia=0,
            hora_inicio=14, hora_fin=20, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )

        self.assertFalse(dominio.se_solapan(a, b))
        self.assertTrue(dominio.validar_bloque(b, [a]).permitido)

    def test_el_mismo_tramo_en_otro_equipo_o_dia_es_valido(self):
        a = self._bloque(hora_inicio=8, hora_fin=12)

        otro_equipo = BloquePlan(
            semana=self.semana, equipo=self.veb, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )
        otro_dia = BloquePlan(
            semana=self.semana, equipo=self.scheffers2, dia=1,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )

        self.assertFalse(dominio.se_solapan(a, otro_equipo))
        self.assertFalse(dominio.se_solapan(a, otro_dia))


class ValidarBloqueTests(BasePlanificador):
    def test_la_hora_de_termino_debe_ser_posterior(self):
        bloque = BloquePlan(
            semana=self.semana, equipo=self.veb, dia=0,
            hora_inicio=12, hora_fin=8, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )

        v = dominio.validar_bloque(bloque)

        self.assertFalse(v.permitido)
        self.assertIn("posterior", " ".join(v.bloqueos))

    def test_un_bloque_de_produccion_sin_codigo_no_vale(self):
        bloque = BloquePlan(
            semana=self.semana, equipo=self.veb, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
        )

        self.assertFalse(dominio.validar_bloque(bloque).permitido)

    def test_un_bloque_de_estado_sin_estado_tampoco(self):
        bloque = BloquePlan(
            semana=self.semana, equipo=self.veb, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.ESTADO,
        )

        self.assertFalse(dominio.validar_bloque(bloque).permitido)

    def test_un_bloque_valido_pasa(self):
        bloque = BloquePlan(
            semana=self.semana, equipo=self.veb, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.rc_nestle,
        )

        self.assertTrue(dominio.validar_bloque(bloque).permitido)


class PublicarTests(BasePlanificador):
    def _semana_cuadrada(self):
        for dia in range(6):
            self._balance(dia, stock_inicial=500000 if dia == 0 else None,
                          recepcion_nestle=200000)
        self._bloque(dia=0, hora_inicio=8, hora_fin=12)

    def test_una_semana_cuadrada_se_puede_publicar(self):
        self._semana_cuadrada()
        bloques, codigos, balances = self._ctx()

        v = dominio.puede_publicar(self.semana, bloques, codigos, balances)

        self.assertTrue(v.permitido, " ".join(v.bloqueos))

    def test_no_se_publica_una_semana_con_dias_sin_balance(self):
        self._bloque(dia=0, hora_inicio=8, hora_fin=12)
        bloques, codigos, balances = self._ctx()

        v = dominio.puede_publicar(self.semana, bloques, codigos, balances)

        self.assertFalse(v.permitido)
        self.assertIn("sin balance", " ".join(v.bloqueos))

    def test_no_se_publica_una_semana_con_saldos_negativos(self):
        """Sería mandar a planta un programa que no se puede cumplir."""
        for dia in range(6):
            self._balance(dia, recepcion_nestle=1000)
        self._bloque(dia=0, hora_inicio=0, hora_fin=10)
        bloques, codigos, balances = self._ctx()

        v = dominio.puede_publicar(self.semana, bloques, codigos, balances)

        self.assertFalse(v.permitido)
        self.assertIn("negativo", " ".join(v.bloqueos))

    def test_no_se_publica_una_semana_vacia(self):
        for dia in range(6):
            self._balance(dia, recepcion_nestle=1000)
        bloques, codigos, balances = self._ctx()

        v = dominio.puede_publicar(self.semana, bloques, codigos, balances)

        self.assertFalse(v.permitido)
        self.assertIn("ningún bloque", " ".join(v.bloqueos))

    def test_una_semana_ya_cerrada_no_se_republica(self):
        self._semana_cuadrada()
        self.semana.estado = SemanaPlan.Estado.CERRADA
        bloques, codigos, balances = self._ctx()

        v = dominio.puede_publicar(self.semana, bloques, codigos, balances)

        self.assertFalse(v.permitido)


class CalculadoraTests(TestCase):
    """La hoja `Base` del Excel: apoyo para sugerir la hora de término."""

    def test_las_horas_salen_de_los_kilos_sobre_el_flujo(self):
        self.assertEqual(dominio.horas_corrida(12000, 3000), 4)

    def test_sin_flujo_no_se_inventa_un_tiempo(self):
        self.assertIsNone(dominio.horas_corrida(12000, 0))

    def test_el_factor_de_concentracion(self):
        self.assertAlmostEqual(dominio.factor_concentracion(3.5, 8.8), 0.123)


class ConsumoPorEquipoTests(BasePlanificador):
    """
    Quién resta leche del balance lo dice el maestro de equipos.

    Antes era una tupla repetida en el dominio y en el modelo, con una prueba
    que vigilaba la duplicación. Ahora el dato viaja con el equipo, así que la
    duplicación no existe — pero la regla sí, y es la que evita contar dos
    veces la misma leche.
    """

    def test_un_evaporador_resta_del_balance(self):
        self._bloque(equipo=self.veb, hora_inicio=8, hora_fin=12)

        self.assertGreater(
            dominio.consumo_dia(
                list(BloquePlan.objects.all()),
                list(CodigoProduccion.objects.all()),
                0,
            ).total,
            0,
        )

    def test_una_linea_no_resta(self):
        """
        La línea recibe lo que el evaporador ya produjo: si también restara,
        el balance contaría la misma leche dos veces.
        """
        self._bloque(equipo=self.linea1, hora_inicio=8, hora_fin=12)

        self.assertEqual(
            dominio.consumo_dia(
                list(BloquePlan.objects.all()),
                list(CodigoProduccion.objects.all()),
                0,
            ).total,
            0,
        )

    def test_marcar_una_linea_como_consumidora_la_hace_restar(self):
        """
        Es la consecuencia de que sea configurable: el administrador puede
        cambiar el balance desde el maestro. Por eso el campo lleva su aviso.
        """
        self.linea1.consume_leche = True
        self.linea1.save()
        self._bloque(equipo=self.linea1, hora_inicio=8, hora_fin=12)

        self.assertGreater(
            dominio.consumo_dia(
                list(BloquePlan.objects.select_related("equipo")),
                list(CodigoProduccion.objects.all()),
                0,
            ).total,
            0,
        )


class CategoriasCoincidenTests(TestCase):

    def test_las_categorias_del_dominio_coinciden_con_las_del_modelo(self):
        self.assertEqual(set(dominio.CATEGORIAS), set(CategoriaConsumo.values))
