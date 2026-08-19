from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from planificacion.models import SemanaPlan
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import Lote, OrdenProduccion


class OrdenProduccionTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="OP", nombre="Órdenes")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta 1"
        )
        mandante = Mandante.objects.create(empresa=self.empresa, nombre="CCAA")
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo", familia=Producto.Familia.POLVO
        )
        self.semana = SemanaPlan.objects.create(
            sucursal=self.sucursal, codigo="W35", anio=2026,
            fecha_inicio=date(2026, 8, 24),
        )
        usuario = User.objects.create_user("produccion", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, area=PerfilUsuario.Area.SECADO,
            empresa=self.empresa, sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)

    def _crear(self):
        return self.cliente.post(
            "/api/produccion/ordenes/",
            {
                "semana": self.semana.id, "codigo": "OP-2026-0001",
                "producto": self.producto.id, "cantidad_planificada": "48000",
                "unidad": "l", "linea": "Condensación 2", "destino": "PC-04",
            },
            format="json",
        )

    def test_crea_orden_vinculada_a_semana_y_planta(self):
        respuesta = self._crear()
        orden = OrdenProduccion.objects.get()

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(orden.sucursal, self.sucursal)
        self.assertEqual(orden.creada_por.username, "produccion")

    def test_lote_con_orden_conserva_codigo_legacy_y_relacion(self):
        self._crear()
        orden = OrdenProduccion.objects.get()
        respuesta = self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "L-0001", "orden": orden.id,
                "producto": self.producto.id, "fecha": "2026-08-25",
            },
            format="json",
        )
        lote = Lote.objects.get()

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(lote.orden, orden)
        self.assertEqual(lote.op, orden.codigo)

    def test_orden_no_se_borra_y_transiciones_invalidas_se_rechazan(self):
        self._crear()
        orden = OrdenProduccion.objects.get()

        self.assertEqual(
            self.cliente.delete(f"/api/produccion/ordenes/{orden.id}/").status_code,
            405,
        )
        respuesta = self.cliente.patch(
            f"/api/produccion/ordenes/{orden.id}/",
            {"estado": "cerrada"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
