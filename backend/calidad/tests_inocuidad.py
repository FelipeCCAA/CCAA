"""
Pruebas de las dos reglas de inocuidad que bloquean la liberación.

Son de HACCP, no de calidad de producto, y esa diferencia es el punto:

- El **PCC 1** de uperización es la barrera que hace inocua la leche. Una
  lectura por debajo de la temperatura mínima —o por encima del caudal
  máximo— significa que el producto pasó sin ese tratamiento.
- Un **PPRO** con lecturas No-OK y sin acción correctiva es un incidente
  abierto. Lo que bloquea no es el No-OK, que ocurre y se corrige, sino que
  nadie haya dejado constancia de qué se hizo.

Ninguna de las dos admite concesión: una concesión asume un riesgo *medido*
sobre la calidad del producto, y aquí lo que falló es la barrera que lo hace
seguro.

Las funciones son puras, así que la mayoría de estas pruebas no tocan la base.
"""

from datetime import date, time

from django.test import SimpleTestCase, TestCase

from produccion import dominio as produccion_dominio

from . import dominio


class _Control:
    """Un control de proceso con sus límites, sin ORM."""

    def __init__(self, id=1, equipo="VEB", temp_min=80.0, caudal_max=14175.0):
        self.id = id
        self.equipo = equipo
        self.pcc1_temp_min = temp_min
        self.pcc1_caudal_max = caudal_max


class _Lectura:
    def __init__(self, control_id=1, hora=time(10, 0), **valores):
        self.control_id = control_id
        self.hora = hora
        self.valores = valores


class _Monitoreo:
    def __init__(self, resuelto=True, tipo="Detector de metales"):
        self.resuelto = resuelto
        self._tipo = tipo

    def get_tipo_display(self):
        return self._tipo


class EvaluarPcc1Tests(SimpleTestCase):

    def test_una_lectura_dentro_del_limite_cumple(self):
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(), [_Lectura(t_dsi=82.1, flujo_entrada=13500)]
        )

        self.assertTrue(evaluacion.cumple)
        self.assertFalse(evaluacion.incumplimientos)

    def test_temperatura_bajo_el_minimo_incumple(self):
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(temp_min=80.0), [_Lectura(t_dsi=78.4)]
        )

        self.assertFalse(evaluacion.cumple)
        self.assertEqual(evaluacion.incumplimientos[0].sentido, "bajo")
        self.assertEqual(evaluacion.incumplimientos[0].valor, 78.4)

    def test_caudal_sobre_el_maximo_incumple(self):
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(caudal_max=14175.0), [_Lectura(flujo_entrada=15000)]
        )

        self.assertFalse(evaluacion.cumple)
        self.assertEqual(evaluacion.incumplimientos[0].sentido, "alto")

    def test_justo_en_el_limite_cumple(self):
        """
        El límite es «mínimo» y «máximo», no «mayor que» y «menor que». Un
        control que trabaja exactamente en su límite está dentro.
        """
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(temp_min=80.0, caudal_max=14175.0),
            [_Lectura(t_dsi=80.0, flujo_entrada=14175.0)],
        )

        self.assertTrue(evaluacion.cumple)

    def test_los_limites_salen_del_control_y_no_de_un_maestro(self):
        """
        Cambian por equipo: el VEB trabaja a 80,0 °C y el Scheffers 2 a 81,2.
        La misma lectura cumple en uno e incumple en el otro.
        """
        lectura = [_Lectura(t_dsi=80.5)]

        self.assertTrue(
            produccion_dominio.evaluar_pcc1(_Control(temp_min=80.0), lectura).cumple
        )
        self.assertFalse(
            produccion_dominio.evaluar_pcc1(_Control(temp_min=81.2), lectura).cumple
        )

    def test_una_lectura_sin_el_parametro_no_es_un_incumplimiento(self):
        """No se midió no es lo mismo que se salió."""
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(), [_Lectura(densidad=1020)]
        )

        self.assertTrue(evaluacion.cumple)
        self.assertFalse(evaluacion.incumplimientos)

    def test_un_control_sin_lecturas_se_informa(self):
        """Un PCC sin lecturas no vigiló nada, aunque no tenga incumplimientos."""
        evaluacion = produccion_dominio.evaluar_pcc1(_Control(), [])

        self.assertTrue(evaluacion.sin_lecturas)

    def test_un_control_sin_limites_se_informa(self):
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(temp_min=None, caudal_max=None), [_Lectura(t_dsi=10)]
        )

        self.assertTrue(evaluacion.sin_limites)

    def test_solo_mira_las_lecturas_de_ese_control(self):
        """
        Las lecturas llegan todas juntas en una consulta; filtrarlas mal
        cruzaría los límites de un equipo con las lecturas de otro.
        """
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(id=1),
            [_Lectura(control_id=2, t_dsi=10.0)],
        )

        self.assertTrue(evaluacion.cumple)

    def test_el_motivo_dice_que_paso_y_cuando(self):
        evaluacion = produccion_dominio.evaluar_pcc1(
            _Control(temp_min=80.0), [_Lectura(hora=time(14, 30), t_dsi=77.0)]
        )

        descripcion = evaluacion.incumplimientos[0].descripcion

        self.assertIn("77.0", descripcion)
        self.assertIn("80.0", descripcion)
        self.assertIn("14:30", descripcion)


class BloqueosDeInocuidadTests(SimpleTestCase):

    def test_un_pcc1_incumplido_bloquea(self):
        bloqueos = dominio.bloqueos_de_inocuidad(
            controles=[_Control(temp_min=80.0)],
            lecturas_control=[_Lectura(t_dsi=75.0)],
        )

        self.assertEqual(len(bloqueos), 1)
        self.assertIn("PCC 1", bloqueos[0])

    def test_un_pcc1_cumplido_no_bloquea(self):
        self.assertEqual(
            dominio.bloqueos_de_inocuidad(
                controles=[_Control()], lecturas_control=[_Lectura(t_dsi=82.0)]
            ),
            [],
        )

    def test_un_ppro_sin_resolver_bloquea(self):
        bloqueos = dominio.bloqueos_de_inocuidad(monitoreos=[_Monitoreo(resuelto=False)])

        self.assertEqual(len(bloqueos), 1)
        self.assertIn("acción correctiva", bloqueos[0])

    def test_un_ppro_resuelto_no_bloquea(self):
        self.assertEqual(
            dominio.bloqueos_de_inocuidad(monitoreos=[_Monitoreo(resuelto=True)]), []
        )

    def test_sin_datos_no_bloquea_nada(self):
        """
        Un lote sin controles cargados no se bloquea *por esta regla*. Lo que
        exige tener el registro es el checklist del Dossier, y ese es otro
        mecanismo: aquí solo se juzga lo que sí se registró.
        """
        self.assertEqual(dominio.bloqueos_de_inocuidad(), [])

    def test_se_acumulan_varios_motivos(self):
        bloqueos = dominio.bloqueos_de_inocuidad(
            controles=[_Control(id=1), _Control(id=2, equipo="SCH2")],
            lecturas_control=[
                _Lectura(control_id=1, t_dsi=70.0),
                _Lectura(control_id=2, flujo_entrada=99999),
            ],
            monitoreos=[_Monitoreo(resuelto=False)],
        )

        self.assertEqual(len(bloqueos), 3)

    def test_el_motivo_no_lista_mas_de_tres_lecturas(self):
        """Un turno completo fuera de rango son 24 lecturas: se resume."""
        lecturas = [_Lectura(hora=time(h, 0), t_dsi=70.0) for h in range(8)]

        bloqueos = dominio.bloqueos_de_inocuidad(
            controles=[_Control(temp_min=80.0)], lecturas_control=lecturas
        )

        self.assertIn("y 5 más", bloqueos[0])


class LiberacionConInocuidadTests(TestCase):
    """
    La regla completa: qué pasa con la liberación cuando la inocuidad falla.

    Toca la base porque `puede_liberar` necesita el checklist y la
    especificación para llegar hasta el final.
    """

    def setUp(self):
        from maestros.models import (
            DocumentoLiberacion,
            Especificacion,
            Mandante,
            Producto,
        )
        from produccion.models import Analisis, Lote

        # El catálogo se siembra por migración de datos y también aparece en
        # la base de pruebas (CLAUDE.md, «Trampas conocidas»).
        DocumentoLiberacion.objects.all().delete()

        mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="L-1",
            producto=self.producto,
            fecha=date(2026, 7, 16),
            kg_producidos=1000,
            estado=Lote.Estado.PRODUCIDO,
        )

        self.spec = Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={"humedad": {"min": 2.0, "max": 4.0}},
        )
        Analisis.objects.create(
            lote=self.lote, fecha=date(2026, 7, 16), valores={"humedad": 3.0}
        )

    def _decidir(self, **extra):
        from produccion.models import Analisis

        return dominio.puede_liberar(
            self.lote,
            self.producto,
            documentos=[],
            registros=[],
            analisis=list(Analisis.objects.all()),
            especificaciones=[self.spec],
            **extra,
        )

    def _con_checklist_completo(self, no_conforme=False, **extra):
        """
        Un lote sin más peros que los que le ponga la prueba: checklist
        completo, rol autorizador, y la calidad que se le pida.
        """
        from maestros.models import DocumentoLiberacion
        from produccion.models import Analisis

        from .models import RegistroCalidad

        documento = DocumentoLiberacion.objects.create(
            codigo="DOC-1",
            nombre="Formulario único",
            aplica_a=["polvo"],
            orden=1,
        )
        RegistroCalidad.objects.create(
            lote=self.lote,
            documento=documento,
            estado=RegistroCalidad.Estado.COMPLETADO,
        )

        if no_conforme:
            Analisis.objects.all().delete()
            Analisis.objects.create(
                lote=self.lote,
                fecha=date(2026, 7, 16),
                valores={"humedad": 9.9},  # fuera del rango 2,0–4,0
            )

        return dominio.puede_liberar(
            self.lote,
            self.producto,
            documentos=[documento],
            registros=list(RegistroCalidad.objects.all()),
            analisis=list(Analisis.objects.all()),
            especificaciones=[self.spec],
            **extra,
        )

    def test_sin_documentos_ya_hay_otros_bloqueos(self):
        """Punto de partida: el checklist vacío bloquea por su cuenta."""
        decision = self._decidir()

        self.assertFalse(decision.permitido)

    def test_un_pcc1_incumplido_agrega_su_motivo(self):
        decision = self._decidir(
            controles=[_Control(temp_min=80.0)],
            lecturas_control=[_Lectura(t_dsi=75.0)],
        )

        self.assertTrue(any("PCC 1" in b for b in decision.bloqueos))

    def test_la_inocuidad_no_se_salva_por_concesion(self):
        """
        Una concesión asume un riesgo conocido y medido sobre la calidad. Un
        PCC 1 incumplido no es eso: es que la barrera que hace inocuo al
        producto no actuó, y no hay medición que acote ese riesgo.

        El escenario **aísla** el fallo: checklist completo y el lote no
        conforme, que es justo la situación en que la concesión se ofrecería.
        Con otros bloqueos encima la prueba pasaría por el motivo equivocado
        y no probaría nada — es como estaba antes.
        """
        decision = self._con_checklist_completo(
            no_conforme=True,
            controles=[_Control(temp_min=80.0)],
            lecturas_control=[_Lectura(t_dsi=75.0)],
        )

        self.assertFalse(decision.permitido)
        self.assertFalse(decision.via_concesion)

    def test_sin_el_fallo_de_inocuidad_ese_mismo_lote_si_se_concede(self):
        """
        El control de la prueba anterior: demuestra que lo único que cierra la
        concesión es la inocuidad, y no algo más del escenario.
        """
        decision = self._con_checklist_completo(no_conforme=True)

        self.assertTrue(decision.via_concesion)

    def test_un_ppro_abierto_tampoco_se_concede(self):
        decision = self._decidir(monitoreos=[_Monitoreo(resuelto=False)])

        self.assertFalse(decision.via_concesion)
        self.assertTrue(any("correctiva" in b for b in decision.bloqueos))

    def test_sin_pasar_controles_la_inocuidad_no_se_evalua(self):
        """
        Igual que con el rol: consultar el estado de un lote sin traer los
        controles no debe inventar un bloqueo que no se comprobó.
        """
        decision = self._decidir()

        self.assertFalse(any("PCC 1" in b for b in decision.bloqueos))
