"""
Escenario compartido de las pruebas de producto terminado y despacho.

Vive aparte para que las pruebas de despacho no copien el mismo `setUp` de
treinta líneas: dos copias divergen, y lo primero que divergen son los estados
del pallet —que es justo lo que esas pruebas miden—.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import Liberacion
from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote, PalletProducto, RegistroEnvase
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Bodega, ClienteDespacho, Ubicacion


class EscenarioProductoTerminado(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PT-1", nombre="Empresa PT")
        self.planta = Sucursal.objects.create(empresa=self.empresa, codigo="PT", nombre="Planta PT")
        self.usuario = User.objects.create_user("bodega-pt")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.OPERARIO, area=PerfilUsuario.Area.BODEGA,
        )
        mandante = Mandante.objects.create(empresa=self.empresa, nombre="Mandante PT", codigo_cliente="pt")
        producto = Producto.objects.create(mandante=mandante, nombre="Polvo PT", unidad_base="kg")
        self.producto = producto
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-PT", producto=producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("500"),
        )
        equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="ENV-PT", nombre="Envasadora PT", tipo=Equipo.Tipo.ENVASADORA,
        )
        self.envase = RegistroEnvase.objects.create(
            lote=self.lote, equipo=equipo, formato_kg=25, unidades=20, kg_envasados=500,
            operador=self.usuario, inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        self.pallet = PalletProducto.objects.create(
            envase=self.envase, codigo="PAL-PT", unidades=20, kg_neto=500,
        )
        bodega = Bodega.objects.create(sucursal=self.planta, codigo="BPT", nombre="Bodega PT")
        self.ubicacion = Ubicacion.objects.create(bodega=bodega, codigo="A-01")
        self.cliente = ClienteDespacho.objects.create(empresa=self.empresa, codigo="CLI", nombre="Cliente PT")
        self.api = APIClient()
        self.api.force_authenticate(self.usuario)

    def liberar(self):
        Liberacion.objects.create(lote=self.lote, estado=Liberacion.Estado.LIBERADO)
        self.pallet.estado = PalletProducto.Estado.LIBERADO
        self.pallet.save(update_fields=["estado"])

    def dar_permiso(self, codename, usuario=None):
        (usuario or self.usuario).user_permissions.add(
            Permission.objects.get(codename=codename)
        )

    def crear_pallet(self, codigo, *, estado=PalletProducto.Estado.LIBERADO):
        """Otro pallet del mismo lote, ya liberado salvo que se pida otro estado."""
        return PalletProducto.objects.create(
            envase=self.envase, codigo=codigo, unidades=20, kg_neto=500, estado=estado,
        )
