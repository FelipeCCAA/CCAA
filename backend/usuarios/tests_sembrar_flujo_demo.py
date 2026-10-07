from django.core.management.base import CommandError
from django.test import TestCase

from maestros.models import Equipo, Mandante, Producto
from procesos.models import EtapaProceso, Proceso, RutaProducto
from usuarios.management.commands.sembrar_flujo_demo import Command
from usuarios.models import Empresa, Sucursal


class EquipoDeAperturaTests(TestCase):
    """
    `sembrar_flujo_demo` abre el lote en la máquina de la primera etapa
    después del vale. Si no la encuentra, tiene que decir qué falta: antes
    devolvía `None` y el comando fallaba más adelante con un mensaje que no
    nombraba ni el tipo de máquina ni la ruta.
    """

    def setUp(self):
        empresa = Empresa.objects.create(rut="SEM-DEMO", nombre="Empresa sembrado")
        self.planta = Sucursal.objects.create(empresa=empresa, codigo="SEMD", nombre="Planta")
        mandante = Mandante.objects.create(empresa=empresa, nombre="Mandante demo")
        self.producto = Producto.objects.create(mandante=mandante, nombre="Polvo demo")
        proceso = Proceso.objects.create(codigo="demo-polvo", nombre="Demo polvo")
        EtapaProceso.objects.create(
            proceso=proceso, codigo="est", nombre="Estandarización",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION, orden=1,
        )
        EtapaProceso.objects.create(
            proceso=proceso, codigo="eva", nombre="Evaporación",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=2,
        )
        RutaProducto.objects.create(sucursal=self.planta, producto=self.producto, proceso=proceso)
        # Las migraciones siembran máquinas también en la base de pruebas.
        Equipo.objects.update(activo=False)

    def test_sin_maquina_con_sigla_dice_que_falta(self):
        Equipo.objects.create(
            sucursal=self.planta, codigo="ev-sin-sigla", nombre="Evaporador sin sigla",
            tipo=Equipo.Tipo.EVAPORADOR,
        )

        with self.assertRaises(CommandError) as error:
            Command()._equipo_de_apertura(self.producto, self.planta)

        texto = str(error.exception)
        self.assertIn("Evaporador", texto)
        self.assertIn("sigla", texto)
        self.assertIn(self.producto.nombre, texto)

    def test_con_un_evaporador_con_sigla_lo_usa(self):
        evaporador = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-demo", nombre="Evaporador demo",
            tipo=Equipo.Tipo.EVAPORADOR, sigla="VD",
        )

        self.assertEqual(Command()._equipo_de_apertura(self.producto, self.planta), evaporador)
