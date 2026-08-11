from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import DocumentoLiberacion, Equipo, Especificacion, Mandante, Producto
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Lote


class TenancyOperacionalTests(TestCase):
    def setUp(self):
        self.empresa_a = Empresa.objects.create(rut="OP-A", nombre="Empresa A")
        self.a1 = Sucursal.objects.create(empresa=self.empresa_a, codigo="A1", nombre="A1")
        self.a2 = Sucursal.objects.create(empresa=self.empresa_a, codigo="A2", nombre="A2")
        self.empresa_b = Empresa.objects.create(rut="OP-B", nombre="Empresa B")
        self.b1 = Sucursal.objects.create(empresa=self.empresa_b, codigo="B1", nombre="B1")

        self.mandante_a = Mandante.objects.create(empresa=self.empresa_a, nombre="Cliente A")
        self.mandante_b = Mandante.objects.create(empresa=self.empresa_b, nombre="Cliente B")
        self.producto_a = Producto.objects.create(
            nombre="Producto A", familia=Producto.Familia.POLVO, mandante=self.mandante_a
        )
        self.producto_b = Producto.objects.create(
            nombre="Producto B", familia=Producto.Familia.POLVO, mandante=self.mandante_b
        )
        self.lote_a1 = Lote.objects.create(
            sucursal=self.a1, codigo_lote="A1-1", producto=self.producto_a, fecha=date(2026, 8, 1)
        )
        self.lote_a2 = Lote.objects.create(
            sucursal=self.a2, codigo_lote="A2-1", producto=self.producto_a, fecha=date(2026, 8, 1)
        )
        self.lote_b1 = Lote.objects.create(
            sucursal=self.b1, codigo_lote="B1-1", producto=self.producto_b, fecha=date(2026, 8, 1)
        )
        self.equipo_a1 = Equipo.objects.create(
            sucursal=self.a1, codigo="EQ", nombre="Equipo A1", tipo=Equipo.Tipo.OTRO
        )
        self.equipo_a2 = Equipo.objects.create(
            sucursal=self.a2, codigo="EQ", nombre="Equipo A2", tipo=Equipo.Tipo.OTRO
        )
        self.documento_a = DocumentoLiberacion.objects.create(
            empresa=self.empresa_a, nombre="Documento A"
        )
        self.documento_b = DocumentoLiberacion.objects.create(
            empresa=self.empresa_b, nombre="Documento B"
        )
        self.spec_b = Especificacion.objects.create(
            producto=self.producto_b, version="1", vigente_desde=date(2026, 1, 1), rangos={}
        )

    def cliente(self, nombre, rol, empresa, sucursal):
        usuario = User.objects.create_user(nombre, password="x")
        PerfilUsuario.objects.create(
            usuario=usuario,
            rol=rol,
            area=(PerfilUsuario.Area.CALIDAD if rol == Rol.CALIDAD else PerfilUsuario.Area.SECADO),
            empresa=empresa,
            sucursal=sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def test_lote_ajeno_es_404_en_get_y_patch(self):
        cliente = self.cliente("prod-a1", Rol.PRODUCCION, self.empresa_a, self.a1)
        ruta = f"/api/produccion/lotes/{self.lote_a2.id}/"
        self.assertEqual(cliente.get(ruta).status_code, 404)
        self.assertEqual(cliente.patch(ruta, {"observacion": "intrusión"}, format="json").status_code, 404)

    def test_no_crea_lote_con_producto_de_otra_empresa(self):
        cliente = self.cliente("prod-a2", Rol.PRODUCCION, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/produccion/lotes/",
            {"codigo_lote": "X", "producto": self.producto_b.id, "fecha": "2026-08-02"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(Lote.objects.filter(codigo_lote="X").exists())

    def test_no_crea_control_con_equipo_de_otra_sucursal(self):
        cliente = self.cliente("prod-a3", Rol.PRODUCCION, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/produccion/controles/",
            {"lote": self.lote_a1.id, "equipo": self.equipo_a2.id, "fecha": "2026-08-01"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_no_crea_analisis_con_especificacion_ajena(self):
        cliente = self.cliente("prod-a4", Rol.PRODUCCION, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/produccion/analisis/",
            {
                "lote": self.lote_a1.id,
                "fecha": "2026-08-01",
                "valores": {},
                "especificacion": self.spec_b.id,
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_inocuidad_no_admite_equipo_de_otra_sucursal(self):
        cliente = self.cliente("prod-a5", Rol.PRODUCCION, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/inocuidad/monitoreos/",
            {
                "lote": self.lote_a1.id,
                "tipo": "aire_transporte",
                "equipo": self.equipo_a2.id,
                "fecha": "2026-08-01",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_expediente_ajeno_es_404(self):
        cliente = self.cliente("cal-a1", Rol.CALIDAD, self.empresa_a, self.a1)
        self.assertEqual(
            cliente.get(f"/api/calidad/expedientes/{self.lote_a2.id}/").status_code,
            404,
        )

    def test_registro_calidad_no_admite_documento_de_otra_empresa(self):
        cliente = self.cliente("cal-a2", Rol.CALIDAD, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/calidad/registros/",
            {"lote": self.lote_a1.id, "documento": self.documento_b.id},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_registro_periodico_no_admite_equipo_de_otra_sucursal(self):
        cliente = self.cliente("cal-a3", Rol.CALIDAD, self.empresa_a, self.a1)
        respuesta = cliente.post(
            "/api/calidad/registros-equipo/",
            {
                "documento": self.documento_a.id,
                "equipo": self.equipo_a2.id,
                "fecha": "2026-08-01",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
