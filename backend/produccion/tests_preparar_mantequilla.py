from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import User
from django.core.management import CommandError, call_command
from django.test import TestCase

from maestros.models import Equipo, FormatoEnvasado, Mandante, Producto
from procesos.models import Proceso, RutaProducto
from produccion.models import OrdenProduccion
from usuarios.models import Empresa, Sucursal
from usuarios.tenancy import unica_sucursal_activa


class PrepararCircuitoMantequillaTests(TestCase):
    """
    La mantequilla se bate en la mantequera y se envasa en una envasadora: el
    comando busca la primera por su tipo y autoriza la segunda en los formatos
    de la mantequilla. Antes buscaba «una línea que diga mantequilla» y el
    E2E envasaba en esa misma máquina.
    """

    def setUp(self):
        # Compatibilidad de esquema: el comando resuelve este registro técnico
        # sin recibir Empresa/Sucursal como selector funcional.
        self.sucursal = unica_sucursal_activa(None)
        if self.sucursal is None:
            empresa = Empresa.objects.create(rut="PCM-REF", nombre="Configuración técnica")
            self.sucursal = Sucursal.objects.create(
                empresa=empresa, codigo="PCM", nombre="Configuración técnica"
            )
        User.objects.create_superuser("admin-pcm", "admin-pcm@example.com", "clave-pcm")
        mandante, _ = Mandante.objects.get_or_create(
            empresa=self.sucursal.empresa, codigo_cliente=Mandante.Cliente.NO_DEFINIDO,
            defaults={"nombre": "CCAA PCM"},
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Mantequilla sin sal 20 kg PCM",
            categoria=Producto.Categoria.MANTEQUILLA, formato=Producto.Formato.CAJA_20KG,
            naturaleza=Producto.Naturaleza.TERMINADO, unidad_base=Producto.Unidad.KG,
        )
        proceso, _ = Proceso.objects.update_or_create(
            codigo="ruta-mantequilla", version=1,
            defaults={"nombre": "Ruta mantequilla", "activo": True},
        )
        RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.producto, proceso=proceso,
            destino_final=RutaProducto.DestinoFinal.ENVASADO,
        )
        self.formato = FormatoEnvasado.objects.create(
            producto=self.producto, codigo="caja-20-pcm", nombre="Caja 20 kg",
            kg_neto=Decimal("20"), unidades_maximas_pallet=25,
        )

    def preparar(self):
        salida = StringIO()
        call_command("preparar_circuito_mantequilla", aplicar=True, stdout=salida)
        return salida.getvalue()

    def test_usa_la_mantequera_y_autoriza_una_envasadora_sin_duplicarla(self):
        self.preparar()
        self.preparar()

        envasadoras = Equipo.objects.filter(codigo="envasadora_mantequilla")
        self.assertEqual(envasadoras.count(), 1)
        envasadora = envasadoras.get()
        self.assertEqual(envasadora.tipo, Equipo.Tipo.ENVASADORA)
        self.assertEqual(envasadora.nombre, "Envasadora de mantequilla")
        self.assertIn(envasadora, self.formato.equipos.all())
        self.assertFalse(self.formato.equipos.filter(tipo=Equipo.Tipo.MANTEQUERA).exists())
        orden = OrdenProduccion.objects.get(producto=self.producto)
        self.assertEqual(orden.equipo.tipo, Equipo.Tipo.MANTEQUERA)

    def test_sin_mantequera_activa_lo_dice(self):
        Equipo.objects.filter(tipo=Equipo.Tipo.MANTEQUERA).update(activo=False)

        with self.assertRaisesMessage(CommandError, "Falta una mantequera activa"):
            self.preparar()

    def test_una_mantequilla_sin_formato_activo_se_avisa(self):
        self.formato.activo = False
        self.formato.save(update_fields=["activo"])

        salida = self.preparar()

        self.assertIn("no tiene un formato de envasado activo", salida)
        self.assertNotIn(
            "envasadora_mantequilla",
            self.formato.equipos.values_list("codigo", flat=True),
        )
