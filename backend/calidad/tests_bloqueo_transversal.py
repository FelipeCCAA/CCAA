from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto, Silo
from produccion.models import Lote, PalletProducto, RegistroEnvase
from recepcion.models import MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Liberacion


class BloqueoTransversalTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="CAL-BLOQ", nombre="Empresa Calidad")
        planta = Sucursal.objects.create(empresa=empresa, codigo="CB", nombre="Planta")
        usuario = User.objects.create_user("calidad-bloqueo")
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=empresa, sucursal=planta,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante CB", codigo_cliente="cb"
        )
        producto = Producto.objects.create(mandante=mandante, nombre="Producto CB")
        self.lote = Lote.objects.create(
            sucursal=planta, codigo_lote="L-CB", producto=producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=100,
        )
        equipo = Equipo.objects.create(
            sucursal=planta, codigo="env-cb", nombre="Envasadora CB",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        envase = RegistroEnvase.objects.create(
            lote=self.lote, equipo=equipo, formato_kg=25, unidades=4,
            kg_envasados=100, operador=usuario,
            inicio=timezone.now() - timedelta(hours=1), termino=timezone.now(),
        )
        self.pallet = PalletProducto.objects.create(
            envase=envase, codigo="PAL-CB", unidades=4, kg_neto=100
        )
        self.silo = Silo.objects.create(
            sucursal=planta, codigo="S-CB", tipo=Silo.Tipo.SILO, capacidad_l=1000
        )
        MovimientoSilo.objects.create(
            silo=self.silo, lote=self.lote, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=100, fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
        )

    def test_bloqueo_alcanza_lote_pallet_y_silo(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/bloquear/",
            {"motivo": "Desviación microbiológica confirmada"}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Liberacion.objects.get(lote=self.lote).estado, Liberacion.Estado.RECHAZADO)
        self.pallet.refresh_from_db()
        self.silo.refresh_from_db()
        self.assertEqual(self.pallet.estado, PalletProducto.Estado.BLOQUEADO)
        self.assertEqual(self.silo.estado, Silo.Estado.BLOQUEADO_CALIDAD)

    def test_motivo_es_obligatorio(self):
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/bloquear/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Liberacion.objects.exists())
