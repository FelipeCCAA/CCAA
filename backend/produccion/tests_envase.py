import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from maestros.models import Equipo, Mandante, Producto
from inventario.models import ExistenciaProductoTerminado, MovimientoProductoTerminado, Ubicacion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Lote, PalletProducto, RegistroEnvase
from .servicios import registrar_envasado


class EnvasePalletTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="ENV-1", nombre="Empresa envase")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="ENV", nombre="Planta envase"
        )
        self.usuario = User.objects.create_user("operador-envase")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.ENVASE,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante envase", codigo_cliente="env"
        )
        producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo", unidad_base="kg"
        )
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-ENV-1", producto=producto,
            fecha=date(2026, 8, 17), estado=Lote.Estado.PRODUCIDO,
            kg_producidos=Decimal("1000"),
        )
        self.envasadora = Equipo.objects.create(
            sucursal=self.planta, codigo="rovema-test", nombre="Rovema test",
            tipo=Equipo.Tipo.ENVASADORA,
        )

    def registrar(self, *, clave=None, pallets=None):
        inicio = timezone.now() - timedelta(hours=1)
        return registrar_envasado(
            lote_id=self.lote.pk, equipo=self.envasadora, formato_kg="25",
            inicio=inicio, termino=timezone.now(), usuario=self.usuario,
            operacion_id=clave,
            pallets=pallets or [
                {"codigo": "PAL-001", "unidades": 20, "kg_neto": "500"},
                {"codigo": "PAL-002", "unidades": 20, "kg_neto": "500"},
            ],
        )

    def test_registra_envase_y_pallets_sobre_el_mismo_lote(self):
        registro = self.registrar()

        self.assertEqual(registro.lote, self.lote)
        self.assertEqual(registro.unidades, 40)
        self.assertEqual(registro.kg_envasados, Decimal("1000"))
        self.assertEqual(registro.pallets.count(), 2)
        self.assertTrue(all(
            pallet.estado == PalletProducto.Estado.PENDIENTE_CALIDAD
            for pallet in registro.pallets.all()
        ))
        existencias = ExistenciaProductoTerminado.objects.filter(
            pallet__envase=registro, activo=True,
        )
        self.assertEqual(existencias.count(), 2)
        self.assertTrue(all(
            existencia.ubicacion.tipo == Ubicacion.Tipo.CUARENTENA
            for existencia in existencias.select_related("ubicacion")
        ))
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 2)

    def test_clave_idempotente_no_duplica_pallets(self):
        clave = uuid.uuid4()
        primero = self.registrar(clave=clave)
        segundo = self.registrar(clave=clave)

        self.assertEqual(primero.pk, segundo.pk)
        self.assertEqual(RegistroEnvase.objects.count(), 1)
        self.assertEqual(PalletProducto.objects.count(), 2)
        self.assertEqual(ExistenciaProductoTerminado.objects.count(), 2)
        self.assertEqual(MovimientoProductoTerminado.objects.count(), 2)

    def test_no_permite_envasar_mas_de_lo_producido(self):
        with self.assertRaises(ValidationError):
            self.registrar(pallets=[
                {"codigo": "PAL-EXCESO", "unidades": 41, "kg_neto": "1025"}
            ])

        self.assertEqual(RegistroEnvase.objects.count(), 0)
        self.assertEqual(PalletProducto.objects.count(), 0)
