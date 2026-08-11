from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Bodega, Ubicacion


class TenancyInventarioTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="INV-A", nombre="Empresa A")
        self.a1 = Sucursal.objects.create(empresa=self.empresa, codigo="A1", nombre="A1")
        self.a2 = Sucursal.objects.create(empresa=self.empresa, codigo="A2", nombre="A2")
        self.bodega_a1 = Bodega.objects.create(sucursal=self.a1, codigo="B1", nombre="Bodega A1")
        self.bodega_a2 = Bodega.objects.create(sucursal=self.a2, codigo="B2", nombre="Bodega A2")
        usuario = User.objects.create_user("bodega-a1", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, rol=Rol.LECTURA, area=PerfilUsuario.Area.BODEGA,
            empresa=self.empresa, sucursal=self.a1,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)

    def test_lista_y_detalle_no_exponen_otra_sucursal(self):
        respuesta = self.cliente.get("/api/inventario/bodegas/")
        ids = {fila["id"] for fila in respuesta.data["results"]}
        self.assertEqual(ids, {self.bodega_a1.id})
        self.assertEqual(
            self.cliente.get(f"/api/inventario/bodegas/{self.bodega_a2.id}/").status_code,
            404,
        )

    def test_patch_ajeno_es_404(self):
        respuesta = self.cliente.patch(
            f"/api/inventario/bodegas/{self.bodega_a2.id}/",
            {"nombre": "Intrusion"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 404)

    def test_create_ignora_sucursal_ajena_y_usa_scope(self):
        respuesta = self.cliente.post(
            "/api/inventario/bodegas/",
            {"codigo": "N", "nombre": "Nueva", "sucursal": self.a2.id},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Bodega.objects.get(codigo="N").sucursal_id, self.a1.id)

    def test_no_crea_ubicacion_en_bodega_ajena(self):
        respuesta = self.cliente.post(
            "/api/inventario/ubicaciones/",
            {"bodega": self.bodega_a2.id, "codigo": "X"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Ubicacion.objects.filter(codigo="X").exists())
