"""
Pruebas de la recolección en predios.

Lo que se fija aquí es la regla que decide si la leche sube al camión —la
prueba de alcohol— y la trazabilidad mínima: qué predio, de qué proveedor, en
qué módulo.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Vehiculo
from usuarios.models import PerfilUsuario, Rol

from .models import (
    CargaPredio, Conductor, Modulo, Predio, ProveedorLeche, Recoleccion,
)


class RecoleccionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("recepcionista-rec", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.RECEPCION,
            rol=Rol.RECEPCION,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        self.proveedor = ProveedorLeche.objects.create(
            rut="12.345.678-9", nombre="Agrícola Los Robles"
        )
        self.predio = Predio.objects.create(
            proveedor=self.proveedor, codigo="P-01", nombre="Fundo El Alto"
        )
        self.conductor = Conductor.objects.create(
            rut="9.876.543-2", nombre="Pedro Soto"
        )
        self.camion = Vehiculo.objects.create(placa="ABCD-11", tipo="Camión")
        self.carro = Vehiculo.objects.create(placa="EFGH-22", tipo="Carro")
        self.modulo = Modulo.objects.create(vehiculo=self.camion, numero="1")

        self.recoleccion = Recoleccion.objects.create(
            codigo="REC-2026-001", fecha=date(2026, 8, 5),
            conductor=self.conductor, camion=self.camion, carro=self.carro,
        )

    def _carga(self, **extra):
        datos = {
            "recoleccion": self.recoleccion.id,
            "predio": self.predio.id,
            "modulo": self.modulo.id,
            "litros": "3200.00",
            "temperatura": "4.20",
            "alcohol": CargaPredio.Alcohol.NEGATIVA,
            "visual": CargaPredio.Visual.CONFORME,
            "muestra_tomada": True,
            "cargada": True,
        }
        datos.update(extra)

        return self.cliente.post("/api/recoleccion/cargas/", datos, format="json")

    # -------------------------------------------- la prueba de alcohol

    def test_con_alcohol_negativa_la_leche_se_carga(self):
        respuesta = self._carga()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_con_alcohol_positiva_la_leche_no_sube_al_camion(self):
        """La regla dura del proceso: es la que decide en el predio."""
        respuesta = self._carga(alcohol=CargaPredio.Alcohol.POSITIVA)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no sube al camión", str(respuesta.data))

    def test_una_positiva_si_se_registra_como_no_cargada(self):
        """
        El problema hay que poder reconstruirlo después aunque la leche se haya
        quedado en el predio.
        """
        respuesta = self._carga(
            alcohol=CargaPredio.Alcohol.POSITIVA,
            cargada=False,
            modulo=None,
            observaciones="Alcohol positivo, se deja en el predio.",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_una_evaluacion_visual_no_conforme_tampoco_carga(self):
        respuesta = self._carga(visual=CargaPredio.Visual.NO_CONFORME)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no conforme", str(respuesta.data))

    # ------------------------------------------------------ desviación

    def test_no_cargar_exige_decir_por_que(self):
        """Es la desviación que después se le informa al proveedor."""
        respuesta = self._carga(cargada=False, modulo=None, observaciones="   ")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("por qué", str(respuesta.data))

    # ---------------------------------------------------- trazabilidad

    def test_lo_cargado_indica_en_que_modulo(self):
        """
        Leche que subió al camión y no sabe a qué estanque rompe la
        trazabilidad justo donde empieza.
        """
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CargaPredio.objects.create(
                    recoleccion=self.recoleccion, predio=self.predio,
                    modulo=None, litros=100, temperatura=4,
                    alcohol=CargaPredio.Alcohol.NEGATIVA, cargada=True,
                )

    def test_los_litros_cargados_se_suman_del_detalle(self):
        """Un total guardado se desincroniza al corregir una carga."""
        self._carga(litros="3200.00")
        self._carga(
            litros="1800.00", cargada=False, modulo=None,
            observaciones="Estanque con sedimento.",
        )

        self.recoleccion.refresh_from_db()
        self.assertEqual(self.recoleccion.litros_cargados, Decimal("3200.00"))
        self.assertEqual(self.recoleccion.predios_rechazados, ["Fundo El Alto"])

    # -------------------------------------------- proveedor bloqueado

    def test_a_un_proveedor_bloqueado_no_se_le_recolecta(self):
        self.proveedor.bloqueado = True
        self.proveedor.motivo_bloqueo = "Antibióticos confirmados."
        self.proveedor.save()

        respuesta = self._carga()

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("bloqueado", str(respuesta.data))

    def test_un_bloqueo_sin_motivo_no_se_guarda(self):
        """Sin motivo nadie sabe qué tendría que corregirse para
        desbloquearlo."""
        with self.assertRaisesMessage(ValidationError, "motivo"):
            ProveedorLeche(
                rut="1-9", nombre="Sin motivo", bloqueado=True
            ).full_clean()

    # ------------------------------------------------------- vehículos

    def test_el_carro_no_puede_ser_el_mismo_camion(self):
        with self.assertRaisesMessage(ValidationError, "mismo vehículo"):
            Recoleccion(
                codigo="REC-X", fecha=date(2026, 8, 5),
                conductor=self.conductor, camion=self.camion,
                carro=self.camion,
            ).clean()
