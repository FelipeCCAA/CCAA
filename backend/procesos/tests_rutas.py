from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import EtapaProceso, Proceso, RutaProducto


class RutasProductoTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="RUTA-1", nombre="Empresa rutas")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="RP", nombre="Planta rutas"
        )
        self.usuario = User.objects.create_user("administrador-rutas")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.ADMIN, area=PerfilUsuario.Area.ADMINISTRACION,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante rutas", codigo_cliente="mr"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Producto ruteable"
        )
        self.proceso = Proceso.objects.create(codigo="polvo", nombre="Leche en polvo")
        EtapaProceso.objects.create(
            proceso=self.proceso, codigo="condensar", nombre="Condensación",
            tipo=EtapaProceso.Tipo.CONDENSACION, orden=1,
        )
        EtapaProceso.objects.create(
            proceso=self.proceso, codigo="secar", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )

    def test_crea_ruta_configurable_y_expone_sus_etapas(self):
        respuesta = self.cliente.post(
            "/api/procesos/rutas-producto/",
            {"producto": self.producto.pk, "proceso": self.proceso.pk, "prioridad": 1},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["producto_nombre"], "Producto ruteable")
        self.assertEqual(len(respuesta.json()["etapas"]), 2)
        self.assertEqual(RutaProducto.objects.get().sucursal, self.planta)

    def test_catalogo_de_procesos_expone_la_secuencia_para_el_formulario(self):
        respuesta = self.cliente.get("/api/procesos/procesos/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        proceso = next(
            item for item in respuesta.data["results"]
            if item["id"] == self.proceso.pk
        )
        self.assertEqual(
            [(item["tipo"], item["orden"]) for item in proceso["etapas"]],
            [(EtapaProceso.Tipo.CONDENSACION, 1), (EtapaProceso.Tipo.SECADO, 2)],
        )

    def test_no_acepta_producto_de_otra_empresa(self):
        otra = Empresa.objects.create(rut="RUTA-2", nombre="Otra")
        mandante = Mandante.objects.create(
            empresa=otra, nombre="Mandante ajeno", codigo_cliente="ma"
        )
        ajeno = Producto.objects.create(mandante=mandante, nombre="Producto ajeno")

        respuesta = self.cliente.post(
            "/api/procesos/rutas-producto/",
            {"producto": ajeno.pk, "proceso": self.proceso.pk, "prioridad": 1},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_produccion_consulta_pero_no_configura_rutas(self):
        operador = User.objects.create_user("operador-rutas")
        PerfilUsuario.objects.create(
            usuario=operador, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.CONDENSACION,
        )
        cliente = APIClient()
        cliente.force_authenticate(operador)

        self.assertEqual(cliente.get("/api/procesos/rutas-producto/").status_code, 200)
        respuesta = cliente.post(
            "/api/procesos/rutas-producto/",
            {"producto": self.producto.pk, "proceso": self.proceso.pk, "prioridad": 1},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("Administracion", respuesta.json()["detail"])
