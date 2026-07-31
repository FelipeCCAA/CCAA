"""
Pruebas del control de proceso (PCC 1 de uperización).

Cubren la cabecera y su libro de lecturas. La evaluación de cumplimiento del
PCC —que una lectura por debajo de la temperatura mínima o por encima del
caudal máximo bloquee la liberación— se escribe después en
`calidad/dominio.py`, con sus propias pruebas.

Lo que se asegura aquí es que el dato sobre el que esa regla se apoyará no
pueda quedar partido ni duplicado.
"""

from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from maestros.models import Mandante, Producto

from .models import ControlProceso, ControlProcesoLectura, Equipo, Lote


class BaseControlProceso(TestCase):
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
        )

    def _control(self, **cambios):
        datos = {
            "lote": self.lote,
            "equipo": Equipo.VEB,
            "turno": "A",
            "fecha": date(2026, 7, 16),
            "pcc1_temp_min": 80.0,
            "pcc1_caudal_max": 14175.0,
        }
        datos.update(cambios)
        return ControlProceso.objects.create(**datos)


class ControlProcesoTests(BaseControlProceso):
    def test_los_limites_del_pcc_se_guardan_por_registro(self):
        """
        Cambian por equipo y producto: el VEB trabaja a 80,0 °C y el
        Scheffers 2 a 81,2 °C. Guardarlos aquí permite auditar cada lectura
        contra lo que regía ese día, no contra lo que rige hoy.
        """
        veb = self._control(equipo=Equipo.VEB, pcc1_temp_min=80.0)
        sch = self._control(
            equipo=Equipo.SCH2, pcc1_temp_min=81.2, pcc1_caudal_max=17100.0
        )

        self.assertEqual(float(veb.pcc1_temp_min), 80.0)
        self.assertEqual(float(sch.pcc1_temp_min), 81.2)

    def test_un_equipo_lleva_un_control_por_lote_fecha_y_turno(self):
        """
        Dos cabeceras del mismo turno partirían las lecturas en dos y el
        cumplimiento del PCC se evaluaría sobre la mitad de los datos.
        """
        self._control()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._control()

    def test_el_mismo_equipo_si_registra_en_otro_turno(self):
        self._control(turno="A")
        self._control(turno="B")

        self.assertEqual(ControlProceso.objects.count(), 2)

    def test_dos_equipos_registran_el_mismo_turno(self):
        self._control(equipo=Equipo.VEB)
        self._control(equipo=Equipo.SCH2)

        self.assertEqual(ControlProceso.objects.count(), 2)

    def test_la_hora_de_termino_no_puede_ser_la_de_inicio(self):
        control = ControlProceso(
            lote=self.lote,
            equipo=Equipo.E1,
            fecha=date(2026, 7, 16),
            hora_inicio_produccion=time(8, 0),
            hora_termino_produccion=time(8, 0),
        )

        with self.assertRaises(ValidationError) as error:
            control.full_clean()

        self.assertIn("hora_termino_produccion", error.exception.message_dict)

    def test_los_limites_pueden_ir_vacios(self):
        """No todos los formatos de control llevan el PCC 1."""
        control = self._control(
            equipo=Equipo.E1, pcc1_temp_min=None, pcc1_caudal_max=None
        )
        control.full_clean()

        self.assertIsNone(control.pcc1_temp_min)


class ControlProcesoLecturaTests(BaseControlProceso):
    def test_los_parametros_medidos_van_como_json(self):
        """
        Cambian por equipo: el VEB no mide lo mismo que la torre Egron. Una
        columna por parámetro obligaría a migrar la base cada vez que un
        formato agrega una medición.
        """
        control = self._control()
        lectura = ControlProcesoLectura.objects.create(
            control=control,
            hora=time(9, 0),
            valores={"flujo_entrada": 13500, "densidad": 1020, "t_dsi": 82.1},
        )
        lectura.full_clean()

        self.assertEqual(lectura.valores["t_dsi"], 82.1)

    def test_no_se_repite_la_hora_dentro_de_un_control(self):
        control = self._control()
        ControlProcesoLectura.objects.create(
            control=control, hora=time(9, 0), valores={"t_dsi": 82.1}
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ControlProcesoLectura.objects.create(
                    control=control, hora=time(9, 0), valores={"t_dsi": 79.0}
                )

    def test_los_valores_deben_ser_numericos(self):
        control = self._control()
        lectura = ControlProcesoLectura(
            control=control, hora=time(10, 0), valores={"t_dsi": "ochenta"}
        )

        with self.assertRaises(ValidationError) as error:
            lectura.full_clean()

        self.assertIn("valores", error.exception.message_dict)

    def test_las_lecturas_salen_ordenadas_por_hora(self):
        """El formato de planta se lee de arriba abajo, hora a hora."""
        control = self._control()
        for hora in [time(11, 0), time(9, 0), time(10, 0)]:
            ControlProcesoLectura.objects.create(
                control=control, hora=hora, valores={}
            )

        horas = list(control.lecturas.values_list("hora", flat=True))

        self.assertEqual(horas, [time(9, 0), time(10, 0), time(11, 0)])

    def test_borrar_el_control_se_lleva_sus_lecturas(self):
        control = self._control()
        ControlProcesoLectura.objects.create(control=control, hora=time(9, 0), valores={})

        control.delete()

        self.assertEqual(ControlProcesoLectura.objects.count(), 0)

    def test_el_control_se_borra_con_su_lote(self):
        control = self._control()
        ControlProcesoLectura.objects.create(control=control, hora=time(9, 0), valores={})

        self.lote.delete()

        self.assertEqual(ControlProceso.objects.count(), 0)
        self.assertEqual(ControlProcesoLectura.objects.count(), 0)
