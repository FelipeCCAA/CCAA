"""
Pruebas de la capa de inocuidad.

Lo que se vigila aquí es lo que después va a decidir si un lote se libera: un
PPRO con lecturas No-OK y sin acción correctiva es un incidente abierto, y un
incidente abierto no debería dejar salir producto.

La regla de bloqueo en sí todavía no está escrita —va en `calidad/dominio.py`
con sus propias pruebas—; esto asegura que el dato sobre el que se apoyará
sea fiable.
"""

from datetime import date, time

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from maestros.models import Mandante, Producto
from produccion.models import Lote

from .models import MonitoreoPPRO, PproLectura


class BaseInocuidad(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="CCAA6197",
            producto=self.producto,
            fecha=date(2026, 7, 16),
            kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )

    def _monitoreo(self, **cambios):
        datos = {
            "lote": self.lote,
            "tipo": MonitoreoPPRO.Tipo.DETECTOR_METALES,
            "equipo": "Rovema 3",
            "turno": "A",
            "fecha": date(2026, 7, 16),
        }
        datos.update(cambios)
        return MonitoreoPPRO.objects.create(**datos)

    def _lectura(self, monitoreo, hora, resultado, **extra):
        return PproLectura.objects.create(
            monitoreo=monitoreo,
            hora=hora,
            resultado=resultado,
            **extra,
        )


class MonitoreoPPROTests(BaseInocuidad):
    def test_sin_lecturas_no_hay_nada_que_resolver(self):
        monitoreo = self._monitoreo()

        self.assertFalse(monitoreo.tiene_no_ok)
        self.assertTrue(monitoreo.resuelto)

    def test_todo_ok_queda_resuelto(self):
        monitoreo = self._monitoreo()
        self._lectura(monitoreo, time(8, 0), PproLectura.Resultado.OK)
        self._lectura(monitoreo, time(9, 0), PproLectura.Resultado.OK)

        self.assertFalse(monitoreo.tiene_no_ok)
        self.assertTrue(monitoreo.resuelto)

    def test_un_no_ok_sin_accion_correctiva_queda_abierto(self):
        """Es lo que debe impedir liberar el lote."""
        monitoreo = self._monitoreo()
        self._lectura(monitoreo, time(8, 0), PproLectura.Resultado.OK)
        self._lectura(monitoreo, time(9, 0), PproLectura.Resultado.NO_OK)

        self.assertTrue(monitoreo.tiene_no_ok)
        self.assertFalse(monitoreo.resuelto)

    def test_un_no_ok_con_accion_correctiva_queda_resuelto(self):
        monitoreo = self._monitoreo(
            accion_correctiva="Se detuvo la línea y se reprocesó el producto retenido."
        )
        self._lectura(monitoreo, time(9, 0), PproLectura.Resultado.NO_OK)

        self.assertTrue(monitoreo.tiene_no_ok)
        self.assertTrue(monitoreo.resuelto)

    def test_una_accion_correctiva_en_blanco_no_cuenta(self):
        """Espacios no son una explicación."""
        monitoreo = self._monitoreo(accion_correctiva="   ")
        self._lectura(monitoreo, time(9, 0), PproLectura.Resultado.NO_OK)

        self.assertFalse(monitoreo.resuelto)

    def test_no_se_duplica_el_monitoreo_del_mismo_turno(self):
        """
        Dos cabeceras del mismo chequeo partirían las lecturas en dos, y la
        regla de bloqueo miraría solo la mitad.
        """
        self._monitoreo()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._monitoreo()

    def test_el_mismo_chequeo_si_se_repite_en_otro_turno(self):
        self._monitoreo(turno="A")
        self._monitoreo(turno="B")

        self.assertEqual(MonitoreoPPRO.objects.count(), 2)

    def test_el_mismo_turno_admite_chequeos_distintos(self):
        self._monitoreo(tipo=MonitoreoPPRO.Tipo.DETECTOR_METALES)
        self._monitoreo(tipo=MonitoreoPPRO.Tipo.CUERPOS_EXTRANOS)

        self.assertEqual(MonitoreoPPRO.objects.count(), 2)


class PproLecturaTests(BaseInocuidad):
    def test_no_se_repite_la_hora_dentro_de_un_monitoreo(self):
        monitoreo = self._monitoreo()
        self._lectura(monitoreo, time(8, 0), PproLectura.Resultado.OK)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._lectura(monitoreo, time(8, 0), PproLectura.Resultado.NO_OK)

    def test_el_detalle_del_detector_admite_rechazos_y_alarmas(self):
        monitoreo = self._monitoreo()
        lectura = self._lectura(
            monitoreo,
            time(10, 0),
            PproLectura.Resultado.NO_OK,
            detalle={"rechazos": 2, "alarmas": 1},
        )
        lectura.full_clean()

        self.assertEqual(lectura.detalle["rechazos"], 2)

    def test_el_detalle_rechaza_lo_que_no_sea_numerico(self):
        monitoreo = self._monitoreo()
        lectura = PproLectura(
            monitoreo=monitoreo,
            hora=time(11, 0),
            resultado=PproLectura.Resultado.OK,
            detalle={"rechazos": "muchos"},
        )

        with self.assertRaises(ValidationError) as error:
            lectura.full_clean()

        self.assertIn("detalle", error.exception.message_dict)

    def test_el_detalle_puede_ir_vacio(self):
        """La mayoría de los PPRO son solo OK / No-OK, sin números."""
        monitoreo = self._monitoreo(tipo=MonitoreoPPRO.Tipo.ROCE_VALVULAS)
        lectura = self._lectura(monitoreo, time(12, 0), PproLectura.Resultado.OK)
        lectura.full_clean()

        self.assertEqual(lectura.detalle, {})


class BorradoEnCascadaTests(BaseInocuidad):
    def test_borrar_el_monitoreo_se_lleva_sus_lecturas(self):
        monitoreo = self._monitoreo()
        self._lectura(monitoreo, time(8, 0), PproLectura.Resultado.OK)

        monitoreo.delete()

        self.assertEqual(PproLectura.objects.count(), 0)

    def test_el_operador_no_se_puede_borrar_si_firmo(self):
        """Su nombre es el dato de auditoría del registro."""
        usuario = User.objects.create_user("operador1", password="x")
        self._monitoreo(operador=usuario)

        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            usuario.delete()
