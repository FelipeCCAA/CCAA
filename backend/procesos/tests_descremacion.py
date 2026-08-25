from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from maestros.models import Equipo, Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, Sucursal

from .dominio import calcular_balance_descremacion
from .models import (
    CorridaDescremacion, EjecucionProceso, EtapaProceso, Proceso,
)
from .servicios import cerrar_descremacion, iniciar_descremacion


class BalanceDescremacionTests(TestCase):
    def test_calcula_las_dos_salidas_sin_inventar_una_tolerancia(self):
        balance = calcular_balance_descremacion(1000, 4, 8.7, 0.1, 40)

        self.assertAlmostEqual(balance.crema_esperada_l, Decimal("97.74436"), places=4)
        self.assertAlmostEqual(balance.descremada_esperada_l, Decimal("902.25564"), places=4)
        self.assertEqual(balance.avisos, ())


class CierreDescremacionTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="76.999.111-2", nombre="Descremación")
        sucursal = Sucursal.objects.create(empresa=empresa, codigo="DES", nombre="Planta")
        self.usuario = User.objects.create_user("operador-descremacion")
        self.origen = Silo.objects.create(
            sucursal=sucursal, codigo="ENTERA-D", tipo=Silo.Tipo.SILO, capacidad_l=5000
        )
        self.descremada = Silo.objects.create(
            sucursal=sucursal, codigo="DESCREMADA-D", tipo=Silo.Tipo.TK_LD,
            capacidad_l=5000,
        )
        self.crema = Silo.objects.create(
            sucursal=sucursal, codigo="CREMA-D", tipo=Silo.Tipo.TK_CREMA,
            capacidad_l=1000,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora=timezone.now() - timedelta(hours=2),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        analisis = AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now() - timedelta(hours=1),
            grasa=Decimal("4.000"), sng=Decimal("8.700"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(), estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        equipo = Equipo.objects.create(
            sucursal=sucursal, codigo="DES-1", nombre="Descremadora 1",
            tipo=Equipo.Tipo.OTRO,
        )
        proceso = Proceso.objects.create(codigo="descremar", nombre="Descremación")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="des", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-1", etapa=etapa, sucursal=sucursal,
            equipo=equipo, responsable=self.usuario,
        )
        self.corrida = CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.origen, analisis_entrada=analisis,
            litros_entrada=1000, grasa_entrada=Decimal("4.000"),
            sng_entrada=Decimal("8.700"), silo_descremada=self.descremada,
            estanque_crema=self.crema,
        )

    def test_cierre_genera_dos_saldos_y_hereda_fifo_en_una_operacion(self):
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        resultado = cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada=Decimal("0.1"),
            litros_crema=90, grasa_crema=Decimal("40"),
            controles={"ph_salida": "6.7"},
        )

        movimientos = MovimientoSilo.objects.filter(operacion_id=self.corrida.operacion_id)
        self.assertEqual(movimientos.count(), 3)
        self.assertEqual(resultado.estado, CorridaDescremacion.Estado.CERRADA)
        self.assertEqual(resultado.ejecucion.salidas.count(), 2)
        self.assertEqual(
            sum(m.atribuciones_recepcion.count() for m in movimientos.filter(tipo="ingreso")),
            2,
        )
        self.assertTrue(resultado.controles["avisos_balance"])
