"""
`limpiar_transaccional`: borra la operación de la planta y conserva los
maestros. Antes llevaba su propia lista en orden de borrado, que envejeció y
chocaba con `LiberacionProceso.analisis_lote` (PROTECT) en cuanto había una
liberación por lote.
"""

from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from calidad.models import LiberacionProceso
from estandarizacion.models import ValeEstandarizacion
from maestros.models import Equipo, Mandante, Producto, Silo
from procesos.models import (
    CorridaSecado, EjecucionProceso, EtapaProceso, Proceso, SalidaProceso,
)
from produccion.models import Analisis, Lote, OrdenProduccion
from recepcion.models import MovimientoSilo

from .management.commands.limpiar_transaccional import (
    MODELOS_CONSERVADOS, modelos_a_borrar,
)
from .management.commands.reset_datos_operacionales import MODELOS_OPERACIONALES


def _modelos_de_negocio():
    """
    Los modelos de las apps del proyecto: las que viven bajo `BASE_DIR` y no
    en un entorno virtual (el `.venv` del backend también está bajo
    `BASE_DIR`, y con él entrarían `auth`, `admin` y compañía).
    """
    raiz = Path(settings.BASE_DIR).resolve()
    return {
        modelo._meta.label
        for config in apps.get_app_configs()
        if raiz in Path(config.path).resolve().parents
        and "site-packages" not in Path(config.path).parts
        for modelo in config.get_models()
    }


class ClasificacionTests(TestCase):
    def test_todo_modelo_de_negocio_es_transaccional_o_conservado(self):
        """
        Un modelo nuevo obliga a decidir: o va a `MODELOS_OPERACIONALES` y se
        borra, o va a `MODELOS_CONSERVADOS`. Sin decidir, la limpieza lo
        ignoraba y, si apuntaba a algo borrado, reventaba.
        """
        sin_clasificar = _modelos_de_negocio() - set(MODELOS_OPERACIONALES) - MODELOS_CONSERVADOS

        self.assertEqual(sin_clasificar, set())

    def test_lo_conservado_no_se_borra(self):
        borrados = {modelo._meta.label for modelo in modelos_a_borrar()}

        self.assertEqual(borrados & MODELOS_CONSERVADOS, set())


class LimpiarTransaccionalTests(TestCase):
    def setUp(self):
        mandante = Mandante.objects.create(nombre="Mandante limpieza", codigo_cliente="lmp")
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Polvo limpieza", familia=Producto.Familia.POLVO,
        )
        self.silo = Silo.objects.create(codigo="S-LMP", tipo=Silo.Tipo.SILO, capacidad_l=10000)
        self.torre = Equipo.objects.create(
            codigo="tor-lmp", nombre="Torre limpieza", tipo=Equipo.Tipo.TORRE,
        )
        proceso = Proceso.objects.create(codigo="lmp", nombre="Proceso limpieza")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec-lmp", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        vale = ValeEstandarizacion.objects.create(
            codigo="V-LMP", fecha=date(2026, 10, 1), producto=self.producto,
            silo_destino=self.silo, rc_objetivo=Decimal("0.40"), volumen=1000,
            estado=ValeEstandarizacion.Estado.LIBERADO,
        )
        orden = OrdenProduccion.objects.create(
            codigo="OP-LMP", producto=self.producto,
            cantidad_planificada=Decimal("100"), unidad="kg",
            estado=OrdenProduccion.Estado.EN_PROCESO,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-LMP", etapa=etapa, equipo=self.torre,
            estado=EjecucionProceso.Estado.CERRADA,
        )
        lote = Lote.objects.create(
            codigo_lote="CCAA-LMP-01", producto=self.producto, orden=orden, vale=vale,
            ejecucion=ejecucion, fecha=timezone.localdate(), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("100"),
        )
        CorridaSecado.objects.create(ejecucion=ejecucion, orden=orden, lote=lote)
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=self.producto,
            destino=SalidaProceso.Destino.PENDIENTE, cantidad=Decimal("100"), unidad="kg",
        )
        analisis = Analisis.objects.create(
            lote=lote, fecha=timezone.localdate(), valores={"humedad": 3},
        )
        # La liberación por lote apunta al análisis con PROTECT: es la clave
        # con la que la lista anterior chocaba.
        LiberacionProceso.objects.create(
            salida=salida, analisis_lote=analisis,
            estado=LiberacionProceso.Estado.LIBERADO,
        )
        MovimientoSilo.objects.create(
            silo=self.silo, tipo=MovimientoSilo.Tipo.INGRESO, litros=Decimal("1000"),
            fecha_hora=timezone.now(),
        )
        self.transaccionales = (
            ValeEstandarizacion, OrdenProduccion, EjecucionProceso, Lote, CorridaSecado,
            SalidaProceso, Analisis, LiberacionProceso, MovimientoSilo,
        )

    def test_aplicar_borra_lo_transaccional_y_conserva_los_maestros(self):
        maestros = (Producto, Mandante, Silo, Equipo, Proceso, EtapaProceso)
        antes = {modelo: modelo.objects.count() for modelo in maestros}

        call_command("limpiar_transaccional", aplicar=True, stdout=StringIO())

        for modelo in self.transaccionales:
            self.assertFalse(modelo.objects.exists(), modelo._meta.label)
        for modelo, cuantos in antes.items():
            self.assertEqual(modelo.objects.count(), cuantos, modelo._meta.label)

    def test_sin_aplicar_solo_cuenta(self):
        salida = StringIO()

        call_command("limpiar_transaccional", stdout=salida)

        for modelo in self.transaccionales:
            self.assertTrue(modelo.objects.exists(), modelo._meta.label)
        self.assertIn("Nada se escribió", salida.getvalue())
        self.assertIn("procesos.CorridaSecado", salida.getvalue())

    def test_no_corre_en_un_entorno_endurecido(self):
        for entorno in ("staging", "production"):
            with self.subTest(entorno=entorno), override_settings(DJANGO_ENV=entorno):
                with self.assertRaises(CommandError):
                    call_command("limpiar_transaccional", aplicar=True, stdout=StringIO())
        self.assertTrue(Lote.objects.exists())
