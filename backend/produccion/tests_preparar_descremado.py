from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from maestros.models import Equipo, Especificacion, Producto
from planificacion.models import CapacidadProceso
from procesos.models import Proceso, RutaProducto
from usuarios.models import Empresa, Sucursal


class PrepararCircuitoDescremadoTests(TestCase):
    def test_crea_referencias_operables_sin_duplicarlas(self):
        empresa = Empresa.objects.create(rut="DES-REF", nombre="Planta referencia")
        sucursal = Sucursal.objects.create(
            empresa=empresa, codigo="DES", nombre="Planta Descremado"
        )
        Proceso.objects.create(codigo="ruta-polvo", nombre="Ruta polvo", activo=True)
        proceso_mantequilla = Proceso.objects.create(
            codigo="ruta-mantequilla", nombre="Ruta mantequilla", activo=True,
        )

        call_command(
            "preparar_circuito_descremado",
            sucursal=sucursal.pk,
            aplicar=True,
            stdout=StringIO(),
        )
        descremada = Producto.objects.get(
            mandante__empresa=empresa,
            nombre="Leche descremada líquida intermedia CCAA",
        )
        crema = Producto.objects.create(
            mandante=descremada.mandante,
            nombre="Crema 42% intermedia CCAA",
            familia=Producto.Familia.CREMA,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
            unidad_base=Producto.Unidad.KG,
        )
        call_command(
            "preparar_circuito_descremado",
            sucursal=sucursal.pk,
            aplicar=True,
            stdout=StringIO(),
        )

        equipo = Equipo.objects.get(sucursal=sucursal, codigo="des-01")
        producto = Producto.objects.get(
            mandante__empresa=empresa,
            nombre="Leche descremada líquida intermedia CCAA",
        )
        self.assertEqual(equipo.tipo, Equipo.Tipo.DESCREMADORA)
        self.assertEqual(
            CapacidadProceso.objects.get(equipo=equipo).capacidad_hora,
            15000,
        )
        self.assertEqual((producto.naturaleza, producto.unidad_base), ("intermedio", "L"))
        self.assertEqual(RutaProducto.objects.filter(producto=producto).count(), 1)
        self.assertTrue(RutaProducto.objects.filter(
            producto=crema,
            proceso=proceso_mantequilla,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        ).exists())
        especificacion = Especificacion.objects.get(
            producto=producto, tipo_analisis=Especificacion.TipoAnalisis.SILO,
        )
        self.assertEqual(especificacion.rangos["mg"], {
            "min": 0.04, "max": 0.07, "obligatorio": True,
        })
