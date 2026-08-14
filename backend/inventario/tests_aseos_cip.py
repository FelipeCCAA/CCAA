from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from .models import CicloCIP


class AseosCIPApiTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.111.222-3", nombre="Planta pruebas")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="P1", nombre="Planta 1"
        )
        self.secado = self._usuario("operador-secado", PerfilUsuario.Area.SECADO)
        self.bodega = self._usuario("operador-bodega", PerfilUsuario.Area.BODEGA)
        self.aseo = self._usuario("equipo-aseo", PerfilUsuario.Area.ASEO)
        self.equipo = Equipo.objects.create(
            sucursal=self.sucursal, codigo="egron-1", nombre="Torre Egron 1", tipo=Equipo.Tipo.TORRE
        )
        self.silo = Silo.objects.create(
            sucursal=self.sucursal, codigo="TK-LD-01", tipo=Silo.Tipo.TK_LD, capacidad_l=50000
        )

    def _usuario(self, nombre, area):
        usuario = User.objects.create_user(nombre, password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, area=area, rol="operario",
            empresa=self.empresa, sucursal=self.sucursal,
        )
        return usuario

    def _cliente(self, usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def _crear_directo(self, *, area, equipo=None, silo=None, seccion=""):
        tipo = "equipo" if equipo else "silo" if silo else "seccion"
        return CicloCIP.objects.create(
            sucursal=self.sucursal,
            area=area,
            tipo_objetivo=tipo,
            equipo=equipo,
            silo=silo,
            seccion=seccion,
            inicio=timezone.now(),
            responsable=self.aseo,
        )

    def test_cada_area_ve_solo_sus_aseos_y_aseo_ve_la_planilla_completa(self):
        propio = self._crear_directo(area=PerfilUsuario.Area.SECADO, equipo=self.equipo)
        ajeno = self._crear_directo(area=PerfilUsuario.Area.BODEGA, seccion="Bodega seca")

        respuesta = self._cliente(self.secado).get("/api/inventario/cip/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual([fila["id"] for fila in respuesta.json()["results"]], [propio.id])

        respuesta = self._cliente(self.aseo).get("/api/inventario/cip/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual({fila["id"] for fila in respuesta.json()["results"]}, {propio.id, ajeno.id})

    def test_persona_del_area_no_programa_aseo_para_otra_area(self):
        respuesta = self._cliente(self.secado).post(
            "/api/inventario/cip/",
            {
                "area": PerfilUsuario.Area.BODEGA,
                "tipo_aseo": "general",
                "tipo_objetivo": "seccion",
                "seccion": "Andén",
                "inicio": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_plan_sobre_tanque_guarda_etapas_y_no_pide_equipo(self):
        respuesta = self._cliente(self.aseo).post(
            "/api/inventario/cip/",
            {
                "area": PerfilUsuario.Area.RECEPCION,
                "tipo_aseo": "cip",
                "tipo_objetivo": "silo",
                "silo": self.silo.id,
                "inicio": timezone.now().isoformat(),
                "documento_codigo": "CCAA.Rec.FORM.015.01",
                "etapas": [
                    {
                        "orden": 1,
                        "tipo": "soda",
                        "duracion_min": 20,
                        "temperatura_c": "75.00",
                        "concentracion_pct": "1.500",
                        "cumple": True,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertEqual(respuesta.json()["objetivo_nombre"], "TK-LD-01")
        self.assertEqual(len(respuesta.json()["etapas"]), 1)

    def test_iniciar_y_cerrar_deja_horas_reales_y_verificacion(self):
        ciclo = self._crear_directo(area=PerfilUsuario.Area.SECADO, equipo=self.equipo)
        cliente = self._cliente(self.secado)

        respuesta = cliente.patch(
            f"/api/inventario/cip/{ciclo.id}/", {"estado": "en_curso"}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(respuesta.json()["inicio_real"])
        self.assertEqual(respuesta.json()["ejecutado_por"], self.secado.id)

        respuesta = cliente.patch(
            f"/api/inventario/cip/{ciclo.id}/",
            {"estado": "completado", "verificacion": "conforme", "ph_final": "7.20"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(respuesta.json()["fin"])
        self.assertEqual(respuesta.json()["verificacion"], "conforme")
        self.assertEqual(respuesta.json()["verificado_por"], self.secado.id)

    def test_objetivo_exige_el_atributo_correcto(self):
        respuesta = self._cliente(self.aseo).post(
            "/api/inventario/cip/",
            {
                "area": PerfilUsuario.Area.SECADO,
                "tipo_objetivo": "seccion",
                "inicio": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("seccion", respuesta.json())
