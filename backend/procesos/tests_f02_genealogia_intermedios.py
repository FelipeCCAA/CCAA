"""F02: la genealogía cruza un vale sin convertirlo en lote ni prorratearlo."""

from datetime import date
from decimal import Decimal

from django.test import TestCase

from estandarizacion.models import ValeEstandarizacion
from maestros.models import Mandante, Producto, Silo
from produccion.models import Lote
from usuarios.models import Empresa, Sucursal

from .models import EntradaProceso, EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from .servicios import genealogia_lote


class GenealogiaIntermediosF02Tests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="76.515.516-2", nombre="F02")
        planta = Sucursal.objects.create(empresa=empresa, codigo="F02", nombre="Planta F02")
        mandante = Mandante.objects.create(empresa=empresa, nombre="Mandante F02")
        producto = Producto.objects.create(mandante=mandante, nombre="Polvo F02")
        tk = Silo.objects.create(
            sucursal=planta, codigo="TK-F02", tipo=Silo.Tipo.TK_LD,
            capacidad_l=Decimal("20000"),
        )
        silo_vale = Silo.objects.create(
            sucursal=planta, codigo="SILO-F02", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("20000"),
        )
        proceso = Proceso.objects.create(codigo="f02-genealogia", nombre="F02")
        etapa_descremado = EtapaProceso.objects.create(
            proceso=proceso, codigo="f02-des", nombre="Descremado",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        etapa_vale = EtapaProceso.objects.create(
            proceso=proceso, codigo="f02-est", nombre="Estandarización",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION, orden=2,
        )
        etapa_producto = EtapaProceso.objects.create(
            proceso=proceso, codigo="f02-sec", nombre="Producción",
            tipo=EtapaProceso.Tipo.SECADO, orden=3,
        )
        self.lote_descremada = Lote.objects.create(
            codigo_lote="DES-F02", producto=producto, fecha=date(2026, 10, 26),
        )
        self.lote_polvo = Lote.objects.create(
            codigo_lote="POL-F02", producto=producto, fecha=date(2026, 10, 26),
            kg_producidos=Decimal("500"),
        )
        ejecucion_descremado = EjecucionProceso.objects.create(
            codigo="EJ-DES-F02", etapa=etapa_descremado, sucursal=planta,
        )
        vale = ValeEstandarizacion.objects.create(
            codigo="VE-F02", fecha=date(2026, 10, 26), producto=producto,
            silo_descremada=tk, silo_destino=silo_vale,
        )
        ejecucion_vale = EjecucionProceso.objects.create(
            codigo="EJ-VE-F02", etapa=etapa_vale, sucursal=planta, vale=vale,
        )
        ejecucion_producto = EjecucionProceso.objects.create(
            codigo="EJ-POL-F02", etapa=etapa_producto, sucursal=planta,
        )
        self.salida_descremada = SalidaProceso.objects.create(
            ejecucion=ejecucion_descremado, lote=self.lote_descremada, silo=tk,
            cantidad=Decimal("9150.08"), unidad="L",
        )
        self.salida_vale = SalidaProceso.objects.create(
            ejecucion=ejecucion_vale, silo=silo_vale,
            cantidad=Decimal("15000"), unidad="L",
        )
        self.salida_polvo = SalidaProceso.objects.create(
            ejecucion=ejecucion_producto, lote=self.lote_polvo,
            cantidad=Decimal("500"), unidad="kg",
        )
        self.entrada_descremada = EntradaProceso.objects.create(
            ejecucion=ejecucion_vale, silo=tk,
            salida_origen=self.salida_descremada, tipo=EntradaProceso.Tipo.MEZCLA,
            cantidad=Decimal("4300.53"), unidad="L",
        )
        self.entrada_producto = EntradaProceso.objects.create(
            ejecucion=ejecucion_producto, silo=silo_vale,
            salida_origen=self.salida_vale,
            cantidad=Decimal("6000"), unidad="L",
        )

    def _consultar(self, lote, direccion, profundidad=12):
        return genealogia_lote(
            lote.pk, direccion, profundidad_maxima=profundidad,
        )

    def test_atras_conserva_cantidades_por_tramo_sin_asignacion_proporcional(self):
        resultado = self._consultar(self.lote_polvo, "atras")

        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {self.lote_polvo.pk, self.lote_descremada.pk},
        )
        self.assertEqual(resultado["enlaces"], [])
        self.assertEqual(len(resultado["tramos"]), 2)
        fuente, consumo = sorted(
            resultado["tramos"], key=lambda tramo: tramo["entrada"]["id"]
        )
        self.assertEqual(fuente["origen"]["id"], self.salida_descremada.pk)
        self.assertEqual(fuente["entrada"]["cantidad"], Decimal("4300.53"))
        self.assertEqual(fuente["destino"]["cantidad"], Decimal("15000"))
        self.assertIsNone(fuente["destino"]["lote_id"])
        self.assertEqual(fuente["destino"]["ejecucion"]["vale_codigo"], "VE-F02")
        self.assertEqual(consumo["origen"]["id"], self.salida_vale.pk)
        self.assertEqual(consumo["entrada"]["cantidad"], Decimal("6000"))
        self.assertEqual(consumo["destino"]["cantidad"], Decimal("500"))
        self.assertEqual(consumo["destino"]["unidad"], "kg")

    def test_adelante_recupera_lote_posterior_a_traves_del_vale(self):
        resultado = self._consultar(self.lote_descremada, "adelante")

        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {self.lote_descremada.pk, self.lote_polvo.pk},
        )
        self.assertEqual(
            {(tramo["origen"]["id"], tramo["destino"]["id"])
             for tramo in resultado["tramos"]},
            {(self.salida_descremada.pk, self.salida_vale.pk),
             (self.salida_vale.pk, self.salida_polvo.pk)},
        )

    def test_varias_fuentes_son_tramos_independientes(self):
        otra_fuente = Lote.objects.create(
            codigo_lote="OTRA-F02", producto=self.lote_polvo.producto,
            fecha=date(2026, 10, 26),
        )
        otra_salida = SalidaProceso.objects.create(
            ejecucion=self.salida_descremada.ejecucion, lote=otra_fuente,
            silo=self.salida_descremada.silo, cantidad=Decimal("2000"), unidad="L",
        )
        EntradaProceso.objects.create(
            ejecucion=self.salida_vale.ejecucion,
            silo=self.salida_descremada.silo, salida_origen=otra_salida,
            tipo=EntradaProceso.Tipo.MEZCLA, cantidad=Decimal("700"), unidad="L",
        )

        resultado = self._consultar(self.lote_polvo, "atras")
        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {self.lote_polvo.pk, self.lote_descremada.pk, otra_fuente.pk},
        )
        self.assertEqual(
            {tramo["entrada"]["cantidad"] for tramo in resultado["tramos"]},
            {Decimal("4300.53"), Decimal("700"), Decimal("6000")},
        )

    def test_entrada_legada_solo_silo_no_atribuye_lote_fuente(self):
        self.entrada_descremada.salida_origen = None
        self.entrada_descremada.save(update_fields=["salida_origen"])

        resultado = self._consultar(self.lote_polvo, "atras")
        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {self.lote_polvo.pk},
        )
        self.assertEqual(len(resultado["tramos"]), 1)
        self.assertEqual(resultado["tramos"][0]["origen"]["id"], self.salida_vale.pk)

    def _agregar_antecedente_directo(self):
        previo = Lote.objects.create(
            codigo_lote="PREV-F02", producto=self.lote_polvo.producto,
            fecha=date(2026, 10, 26),
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-PREV-F02", etapa=self.salida_descremada.ejecucion.etapa,
            sucursal=self.salida_descremada.ejecucion.sucursal,
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=previo,
            cantidad=Decimal("100"), unidad="kg",
        )
        EntradaProceso.objects.create(
            ejecucion=self.salida_descremada.ejecucion, lote=previo,
            cantidad=Decimal("100"), unidad="kg",
        )
        return previo

    def test_ruta_mixta_adelante_sigue_lote_directo_y_luego_vale(self):
        previo = self._agregar_antecedente_directo()

        resultado = self._consultar(previo, "adelante")
        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {previo.pk, self.lote_descremada.pk, self.lote_polvo.pk},
        )
        self.assertTrue(any(
            enlace["origen"] == previo.pk
            and enlace["destino"] == self.lote_descremada.pk
            for enlace in resultado["enlaces"]
        ))
        self.assertEqual(len(resultado["tramos"]), 2)

    def test_ruta_mixta_atras_sigue_vale_y_luego_antecedente_directo(self):
        previo = self._agregar_antecedente_directo()

        resultado = self._consultar(self.lote_polvo, "atras")
        self.assertEqual(
            {nodo["id"] for nodo in resultado["nodos"]},
            {self.lote_polvo.pk, self.lote_descremada.pk, previo.pk},
        )
        self.assertTrue(any(
            enlace["origen"] == previo.pk
            and enlace["destino"] == self.lote_descremada.pk
            for enlace in resultado["enlaces"]
        ))
        self.assertEqual(len(resultado["tramos"]), 2)

    def test_ruta_mixta_comparte_un_solo_presupuesto_de_profundidad(self):
        previo = self._agregar_antecedente_directo()

        atras = self._consultar(self.lote_polvo, "atras", profundidad=2)
        adelante = self._consultar(previo, "adelante", profundidad=2)

        self.assertEqual(
            {nodo["id"] for nodo in atras["nodos"]},
            {self.lote_polvo.pk, self.lote_descremada.pk},
        )
        self.assertNotIn(previo.pk, {nodo["id"] for nodo in atras["nodos"]})
        self.assertEqual(
            {nodo["id"] for nodo in adelante["nodos"]},
            {previo.pk, self.lote_descremada.pk},
        )
        self.assertEqual(len(adelante["tramos"]), 1)

    def test_profundidad_y_ciclo_acotan_recorrido_sin_duplicar_tramos(self):
        corto = self._consultar(self.lote_polvo, "atras", profundidad=1)
        self.assertEqual(len(corto["tramos"]), 1)
        self.assertNotIn(
            self.lote_descremada.pk, {nodo["id"] for nodo in corto["nodos"]}
        )
        # La escritura ordinaria de H09 rechaza este ciclo. Se inserta sólo
        # como dato histórico corrupto para verificar que la lectura termina.
        EntradaProceso.objects.bulk_create([EntradaProceso(
            ejecucion=self.salida_descremada.ejecucion,
            salida_origen=self.salida_polvo, silo=self.salida_vale.silo,
            cantidad=Decimal("1"), unidad="kg",
        )])
        resultado = self._consultar(self.lote_polvo, "atras", profundidad=12)
        claves = [
            (tramo["entrada"]["id"], tramo["destino"]["id"])
            for tramo in resultado["tramos"]
        ]
        self.assertEqual(len(claves), len(set(claves)))
        self.assertEqual(len(claves), 3)
