"""
Pruebas del ciclo del vale de estandarización.

Lo que se fija aquí no es que el vale guarde campos, sino las tres reglas que
la planta pone sobre él:

1. **No se muestrea antes de los 30 minutos de agitación.**
2. **Liberar no se pide: se calcula** desde el RC medido.
3. **Corregir reinicia el reloj**, porque agregar leche deshace la mezcla.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from maestros.models import Mandante, Producto, Silo

from . import servicios
from .models import MINUTOS_DE_AGITACION, ValeEstandarizacion


class BaseVale(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="operador", password="x"
        )
        cls.mandante, _ = Mandante.objects.update_or_create(
            nombre="Mandante de prueba"
        )
        cls.producto = Producto.objects.create(
            codigo="TEST-RC", nombre="Precondensado RC 0,201",
            familia=Producto.Familia.LIQUIDO,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
            unidad_base=Producto.Unidad.L,
            mandante=cls.mandante,
        )
        # `update_or_create`: las migraciones de datos siembran también la base
        # de pruebas, y un `create` chocaría con la unicidad del código.
        cls.silo_entera, _ = Silo.objects.update_or_create(
            codigo="SILO-E-TEST",
            defaults={"tipo": Silo.Tipo.SILO, "capacidad_l": 50000},
        )
        cls.silo_descremada, _ = Silo.objects.update_or_create(
            codigo="TK-LD-TEST",
            defaults={"tipo": Silo.Tipo.TK_LD, "capacidad_l": 50000},
        )
        cls.silo_destino, _ = Silo.objects.update_or_create(
            codigo="SILO-D-TEST",
            defaults={"tipo": Silo.Tipo.SILO, "capacidad_l": 50000},
        )

    def crear_vale(self, **extra):
        datos = {
            "codigo": "VE-0001",
            "fecha": timezone.localdate(),
            "producto": self.producto,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera,
            "silo_descremada": self.silo_descremada,
            "silo_destino": self.silo_destino,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
        }
        datos.update(extra)

        return ValeEstandarizacion.objects.create(**datos)

    def llevar_a_agitando(self, vale, minutos=MINUTOS_DE_AGITACION):
        """Deja el vale agitando desde hace `minutos`."""
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        servicios.iniciar_agitacion(vale_id=vale.pk)

        vale.refresh_from_db()
        vale.agitacion_desde = timezone.now() - timedelta(minutes=minutos)
        vale.save(update_fields=["agitacion_desde"])

        return vale


class AgitacionTests(BaseVale):

    def test_no_se_muestrea_antes_de_los_treinta_minutos(self):
        """
        La regla de planta (§10.3). Una muestra tomada antes mide una mezcla
        que todavía no es homogénea: el RC que devuelve no es el del silo, y
        liberar con él sería liberar contra un número que no describe lo que
        hay.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=20)

        with self.assertRaises(ValidationError) as fallo:
            servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

        self.assertIn("20 minutos", fallo.exception.messages[0])

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.AGITANDO)
        self.assertIsNone(vale.grasa_real)

    def test_cumplidos_los_treinta_se_muestrea(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.MUESTREADO)
        self.assertAlmostEqual(vale.rc_real, 0.2011, places=3)

    def test_sin_agitar_no_se_muestrea(self):
        vale = self.crear_vale()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        with self.assertRaises(ValidationError):
            servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

    def test_el_reloj_lo_pone_el_servidor(self):
        """
        La hora de inicio no se recibe: es lo que decide si una muestra vale, y
        aceptarla de fuera permitiría declarar treinta minutos que no
        ocurrieron.
        """
        vale = self.crear_vale()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        antes = timezone.now()
        servicios.iniciar_agitacion(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertGreaterEqual(vale.agitacion_desde, antes)


class DecisionTests(BaseVale):

    def _muestrear(self, grasa, sng):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=grasa, sng=sng)

        return vale

    def test_si_el_rc_cumple_se_libera(self):
        vale = self._muestrear(grasa=1.79, sng=8.9)

        actualizado, evaluacion = servicios.decidir(
            vale_id=vale.pk, usuario=self.usuario
        )

        self.assertTrue(evaluacion.cumple)
        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)

    def test_si_el_rc_no_cumple_va_a_correccion_con_el_motivo(self):
        """
        El motivo queda escrito en el vale: es lo que le dice al operador qué
        agregar. Un vale «no conforme» sin decir qué falta obliga a rehacer el
        cálculo a mano.
        """
        vale = self._muestrear(grasa=2.20, sng=8.9)

        actualizado, evaluacion = servicios.decidir(
            vale_id=vale.pk, usuario=self.usuario
        )

        self.assertFalse(evaluacion.cumple)
        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.CORRIGIENDO)
        self.assertEqual(evaluacion.agregar, "descremada")
        self.assertIn("sobra", actualizado.observaciones)

    def test_la_decision_no_se_recibe_se_calcula(self):
        """
        No hay forma de pedir «liberado»: `decidir` no acepta el destino. Si
        alguien se lo agregara, esta prueba no lo vería —por eso el estado se
        comprueba contra el análisis, que es lo que manda.
        """
        vale = self._muestrear(grasa=2.20, sng=8.9)

        actualizado, _ = servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertNotEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)

    def test_no_se_decide_sin_muestra(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        with self.assertRaises(ValidationError) as fallo:
            servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertIn("muestreado", fallo.exception.messages[0])


class CorreccionTests(BaseVale):

    def test_reagitar_reinicia_el_reloj_y_borra_el_analisis(self):
        """
        Agregar leche deshace la homogeneidad: los treinta minutos se cuentan
        otra vez desde cero, y el análisis anterior ya no describe lo que hay
        en el silo. Conservar cualquiera de los dos dejaría liberar contra una
        medición que no corresponde.
        """
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.AGITANDO)
        self.assertIsNone(vale.grasa_real)
        self.assertLess(vale.minutos_agitando, 1)

        # Y no se puede muestrear de inmediato: el reloj arrancó de nuevo.
        with self.assertRaises(ValidationError):
            servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

    def test_el_ciclo_completo_termina_liberando(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()
        vale.agitacion_desde = timezone.now() - timedelta(
            minutes=MINUTOS_DE_AGITACION
        )
        vale.save(update_fields=["agitacion_desde"])

        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        actualizado, _ = servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)


class TransicionesTests(BaseVale):

    def test_un_vale_liberado_no_vuelve_atras(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        for accion in (servicios.reagitar, servicios.iniciar_agitacion):
            with self.subTest(accion=accion.__name__):
                with self.assertRaises(ValidationError):
                    accion(vale_id=vale.pk)

    def test_no_se_agita_lo_que_no_se_transfirio(self):
        vale = self.crear_vale()

        with self.assertRaises(ValidationError):
            servicios.iniciar_agitacion(vale_id=vale.pk)

    def test_anular_exige_motivo(self):
        """
        Un vale anulado en blanco no distingue el error de captura del silo que
        se contaminó, y es lo primero que se pregunta al auditarlo.
        """
        vale = self.crear_vale()

        with self.assertRaises(ValidationError):
            servicios.anular(vale_id=vale.pk, motivo="   ")

        actualizado = servicios.anular(vale_id=vale.pk, motivo="Silo contaminado")

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.ANULADO)
        self.assertIn("Silo contaminado", actualizado.observaciones)

    def test_un_vale_liberado_no_se_anula(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        with self.assertRaises(ValidationError):
            servicios.anular(vale_id=vale.pk, motivo="me arrepentí")


class ReglasDelDocumentoTests(BaseVale):

    def test_el_destino_no_puede_ser_el_origen(self):
        vale = ValeEstandarizacion(
            codigo="VE-X", fecha=timezone.localdate(), producto=self.producto,
            rc_objetivo="0.2010", volumen="1000.00",
            silo_entera=self.silo_entera,
            silo_descremada=self.silo_descremada,
            silo_destino=self.silo_entera,
            entera_grasa="3.90", entera_sng="8.60",
            descremada_grasa="0.05", descremada_sng="8.90",
            litros_entera="400.00", litros_descremada="600.00",
        )

        with self.assertRaises(ValidationError):
            vale.clean()

    def test_la_composicion_queda_congelada_en_el_vale(self):
        """
        La composición se guarda **en el vale** y no se lee del silo al
        mirarlo: el silo cambia con cada ingreso, y un vale de mayo tiene que
        poder auditarse contra la leche que había en mayo.
        """
        vale = self.crear_vale()

        self.assertEqual(float(vale.entera_grasa), 3.90)
        self.assertEqual(float(vale.descremada_sng), 8.90)
