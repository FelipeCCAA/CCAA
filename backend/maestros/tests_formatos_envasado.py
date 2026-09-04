from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Equipo, FormatoEnvasado, Mandante, Producto


class FormatosEnvasadoApiTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="FMT-1", nombre="Formatos")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="FMT", nombre="Planta formatos"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Mandante formatos"
        )
        self.producto = Producto.objects.create(
            mandante=mandante,
            nombre="Leche entera en polvo",
            naturaleza=Producto.Naturaleza.TERMINADO,
            unidad_base="kg",
        )
        self.envasadora = Equipo.objects.create(
            sucursal=self.planta,
            codigo="ENV-FMT",
            nombre="Envasadora formatos",
            tipo=Equipo.Tipo.ENVASADORA,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta,
            codigo="TOR-FMT",
            nombre="Torre secado",
            tipo=Equipo.Tipo.TORRE,
        )

    def cliente(self, *, administracion):
        usuario = User.objects.create_user(
            f"usuario-{'admin' if administracion else 'envase'}"
        )
        PerfilUsuario.objects.create(
            usuario=usuario,
            empresa=self.empresa,
            sucursal=self.planta,
            rol=Rol.ADMIN if administracion else Rol.PRODUCCION,
            area=(
                PerfilUsuario.Area.ADMINISTRACION
                if administracion
                else PerfilUsuario.Area.ENVASE
            ),
            nivel=(
                PerfilUsuario.Nivel.ADMIN
                if administracion
                else PerfilUsuario.Nivel.TRABAJADOR
            ),
        )
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def datos(self, **cambios):
        datos = {
            "producto": self.producto.pk,
            "codigo": "saco-25kg",
            "nombre": "Saco 25 kg",
            "kg_neto": "25.000",
            "unidades_maximas_pallet": 20,
            "equipos": [self.envasadora.pk],
            "activo": True,
        }
        datos.update(cambios)
        return datos

    def test_administracion_configura_formato_y_lista_equipo(self):
        cliente = self.cliente(administracion=True)
        respuesta = cliente.post(
            "/api/maestros/formatos-envasado/", self.datos(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["maximo_pallet_kg"], "500.000")
        self.assertEqual(respuesta.data["equipos_detalle"][0]["id"], self.envasadora.pk)
        self.assertEqual(FormatoEnvasado.objects.count(), 1)

    def test_rechaza_torre_y_configuracion_sobre_500_kg(self):
        cliente = self.cliente(administracion=True)

        torre = cliente.post(
            "/api/maestros/formatos-envasado/",
            self.datos(equipos=[self.torre.pk]),
            format="json",
        )
        sobrepeso = cliente.post(
            "/api/maestros/formatos-envasado/",
            self.datos(unidades_maximas_pallet=21),
            format="json",
        )

        self.assertEqual(torre.status_code, 400)
        self.assertIn("equipos", torre.data)
        self.assertEqual(sobrepeso.status_code, 400)
        self.assertIn("unidades_maximas_pallet", sobrepeso.data)

    def test_operador_envase_no_puede_modificar_maestro(self):
        respuesta = self.cliente(administracion=False).post(
            "/api/maestros/formatos-envasado/", self.datos(), format="json"
        )

        self.assertEqual(respuesta.status_code, 403)
