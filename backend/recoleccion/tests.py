from datetime import date

from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from maestros.models import Vehiculo
from recepcion.models import ModuloRecepcion, Recepcion
from usuarios.models import PerfilUsuario, Rol

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion


class FlujoRecoleccionTests(APITestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("recolector", password="secreto")
        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.RECEPCION)
        token = Token.objects.create(user=self.usuario)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.vehiculo = Vehiculo.objects.create(placa="ABCD12", numero="12")

        respuesta = self.client.post(
            "/api/recoleccion/rutas/",
            {
                "codigo": "R-2026-001",
                "fecha": date.today().isoformat(),
                "vehiculo": self.vehiculo.pk,
            },
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.ruta_id = respuesta.data["id"]
        respuesta = self.client.post(
            "/api/recoleccion/paradas/",
            {
                "ruta": self.ruta_id,
                "orden": 1,
                "proveedor": "Proveedor Sur",
                "predio": "Predio Uno",
                "sala": "Sala 1",
            },
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.parada_id = respuesta.data["id"]

    def registrar(self, alcohol="conforme", muestra="M-001"):
        return self.client.post(
            "/api/recoleccion/recolecciones/",
            {
                "parada": self.parada_id,
                "fecha_hora": timezone.now().isoformat(),
                "litros_medidos": "1000.00",
                "temperatura": "4.20",
                "alcohol": alcohol,
                "codigo_muestra": muestra,
            },
        )

    def test_flujo_conforme_carga_modulo_y_cierra_ruta(self):
        registro = self.registrar()
        self.assertEqual(registro.status_code, 201, registro.data)
        self.assertEqual(
            RutaRecoleccion.objects.get(pk=self.ruta_id).estado,
            RutaRecoleccion.Estado.EN_CURSO,
        )

        carga = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/",
            {
                "codigo": "CARGA-001",
                "modulo": "M1",
                "estanque_origen": "E1",
                "litros": "1000.00",
            },
        )
        self.assertEqual(carga.status_code, 201, carga.data)
        self.assertEqual(
            ParadaRuta.objects.get(pk=self.parada_id).estado,
            ParadaRuta.Estado.COMPLETADA,
        )

        cierre = self.client.post(f"/api/recoleccion/rutas/{self.ruta_id}/cerrar/")
        self.assertEqual(cierre.status_code, 200, cierre.data)
        self.assertEqual(cierre.data["estado"], RutaRecoleccion.Estado.CERRADA)

    def test_reintento_de_carga_es_idempotente(self):
        registro = self.registrar()
        datos = {"codigo": "CARGA-IDEM", "modulo": "M1", "litros": "500.00"}
        primera = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/", datos
        )
        segunda = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/", datos
        )
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(CargaModulo.objects.count(), 1)

    def test_alcohol_no_conforme_impide_cargar(self):
        registro = self.registrar(alcohol="no_conforme", muestra="")
        self.assertEqual(registro.status_code, 201, registro.data)
        self.assertEqual(registro.data["estado"], Recoleccion.Estado.RECHAZADA)

        carga = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/",
            {"codigo": "NO-CARGAR", "modulo": "M1", "litros": "500.00"},
        )
        self.assertEqual(carga.status_code, 409, carga.data)

    def test_no_permite_superar_litros_medidos(self):
        registro = self.registrar()
        carga = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/",
            {"codigo": "EXCESO", "modulo": "M1", "litros": "1000.01"},
        )
        self.assertEqual(carga.status_code, 409, carga.data)

    def test_el_modulo_se_vincula_con_la_carga_de_recoleccion(self):
        """
        La Task 3 movió `carga_recoleccion` de `Recepcion` a `ModuloRecepcion`:
        los litros y el vehículo son del camión, pero la carga esperada es por
        compartimiento. El POST de la recepción ya no acepta `carga_recoleccion`
        —lo arma el módulo—, y la validación de que una carga no se vincule dos
        veces la restaura la Task 7, junto con el contrato nuevo de
        `registrar-llegada`.
        """
        registro = self.registrar()
        carga = self.client.post(
            f"/api/recoleccion/recolecciones/{registro.data['id']}/cargas/",
            {"codigo": "VINCULO", "modulo": "M1", "litros": "900.00"},
        )
        datos = {
            "fecha": date.today().isoformat(),
            "tipo_leche": "Entera",
            "litros": "890.00",
            "vehiculo": self.vehiculo.pk,
        }
        respuesta = self.client.post("/api/recepcion/recepciones/", datos)
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        recepcion = Recepcion.objects.get(pk=respuesta.data["id"])
        ModuloRecepcion.objects.create(
            recepcion=recepcion, numero=1, carga_recoleccion_id=carga.data["id"]
        )

        self.assertEqual(recepcion.vehiculo, self.vehiculo)
        self.assertEqual(recepcion.diferencia_recoleccion_litros, -10)

