"""
Pruebas de la API de producción.

Verifican lo que el frontend va a consumir: que el resultado de calidad llega
calculado, que el resumen informa su cobertura y que un listado no dispara una
consulta por lote.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Especificacion, Mandante, Producto

from .models import Analisis, Lote


class BaseAPI(TestCase):
    def setUp(self):
        # La API exige identificarse. Las pruebas de que SIN token no se puede
        # hacer nada están en usuarios/tests.py; aquí se prueba el camino
        # autenticado.
        usuario = User.objects.create_user(username="pruebas", password="x")
        token = Token.objects.create(user=usuario)

        self.cliente = APIClient()
        self.cliente.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        self.nestle = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.nestle,
        )
        Especificacion.objects.create(
            producto=self.producto,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={
                "humedad": {"min": 2.0, "max": 4.0, "obligatorio": True},
                "mg": {"min": 26.0, "max": 28.0, "obligatorio": True},
            },
        )

    def _lote(self, codigo="CCAA6140N", **extra):
        datos = {
            "codigo_lote": codigo,
            "producto": self.producto,
            "fecha": date(2026, 7, 20),
            "kg_producidos": 10000,
        }
        datos.update(extra)
        return Lote.objects.create(**datos)


class LotesAPITests(BaseAPI):
    def test_el_listado_trae_el_resultado_de_calidad_calculado(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )

        respuesta = self.cliente.get("/api/produccion/lotes/")

        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.json()["results"][0]
        self.assertEqual(datos["calidad"]["resultado"], "conforme")
        self.assertEqual(datos["calidad"]["etiqueta"], "Conforme")
        self.assertEqual(datos["calidad"]["evaluados"], 1)

    def test_un_lote_fuera_de_rango_informa_la_desviacion(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote,
            fecha=date(2026, 7, 20),
            muestra="M-01",
            valores={"humedad": 9.0, "mg": 27.0},
        )

        datos = self.cliente.get("/api/produccion/lotes/").json()["results"][0]

        self.assertEqual(datos["calidad"]["resultado"], "no_conforme")
        desviacion = datos["calidad"]["desviaciones"][0]
        self.assertEqual(desviacion["parametro"], "humedad")
        self.assertEqual(desviacion["desvio"], "alto")
        self.assertEqual(desviacion["muestra"], "M-01")

    def test_la_ficha_de_un_lote_incluye_sus_analisis(self):
        lote = self._lote()
        Analisis.objects.create(
            lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )

        datos = self.cliente.get(f"/api/produccion/lotes/{lote.id}/").json()

        self.assertEqual(len(datos["analisis"]), 1)

    def test_se_puede_crear_un_lote(self):
        respuesta = self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "CCAA6142N",
                "producto": self.producto.id,
                "fecha": "2026-07-22",
                "kg_producidos": "8000.00",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(Lote.objects.count(), 1)

    def test_rechaza_un_analisis_con_parametros_inventados(self):
        lote = self._lote()

        respuesta = self.cliente.post(
            "/api/produccion/analisis/",
            {"lote": lote.id, "fecha": "2026-07-20", "valores": {"inventado": 1}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("valores", respuesta.json())

    def test_filtra_por_producto(self):
        otro = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        self._lote()
        self._lote(codigo="CR-01", producto=otro)

        datos = self.cliente.get(
            f"/api/produccion/lotes/?producto={otro.id}"
        ).json()

        self.assertEqual(datos["count"], 1)
        self.assertEqual(datos["results"][0]["codigo_lote"], "CR-01")

    def test_filtra_por_resultado_de_calidad(self):
        """
        El veredicto no está en la base: se calcula. El filtro tiene que
        funcionar igual, y seguir paginando.
        """
        bueno = self._lote(codigo="L-OK")
        Analisis.objects.create(
            lote=bueno, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        malo = self._lote(codigo="L-MAL")
        Analisis.objects.create(
            lote=malo, fecha=date(2026, 7, 20), valores={"humedad": 9.0, "mg": 27.0}
        )
        self._lote(codigo="L-SIN")

        for resultado, esperado in [
            ("conforme", ["L-OK"]),
            ("no_conforme", ["L-MAL"]),
            ("sin_analisis", ["L-SIN"]),
        ]:
            datos = self.cliente.get(
                f"/api/produccion/lotes/?calidad={resultado}"
            ).json()

            self.assertEqual(
                [l["codigo_lote"] for l in datos["results"]], esperado, resultado
            )

    def test_el_filtro_de_calidad_se_combina_con_los_demas(self):
        crema = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        bueno = self._lote(codigo="L-OK")
        Analisis.objects.create(
            lote=bueno, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        self._lote(codigo="CR-01", producto=crema)

        datos = self.cliente.get(
            f"/api/produccion/lotes/?calidad=conforme&producto={crema.id}"
        ).json()

        self.assertEqual(datos["count"], 0)

    def test_busca_por_codigo_de_lote(self):
        self._lote(codigo="CCAA6140N")
        self._lote(codigo="CCAA6141N")

        datos = self.cliente.get("/api/produccion/lotes/?buscar=6141").json()

        self.assertEqual(datos["count"], 1)

    def test_se_puede_borrar_un_lote(self):
        lote = self._lote()

        respuesta = self.cliente.delete(f"/api/produccion/lotes/{lote.id}/")

        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(Lote.objects.count(), 0)

    def test_el_listado_no_dispara_una_consulta_por_lote(self):
        """
        Con prefetch, agregar lotes no debe agregar consultas. Sin él, esto
        crecería con cada lote y el panel se volvería lento con datos reales.
        """
        for i in range(5):
            lote = self._lote(codigo=f"L-{i}")
            Analisis.objects.create(
                lote=lote, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
            )

        # 1 valida el token, 1 cuenta para paginar, 1 trae los lotes, 1 trae
        # todos sus análisis de una vez y 1 las especificaciones. Ninguna
        # depende del número de lotes.
        with self.assertNumQueries(5):
            self.cliente.get("/api/produccion/lotes/")


class ResumenAPITests(BaseAPI):
    def test_el_resumen_informa_su_cobertura(self):
        """
        Un 100 % de cumplimiento sobre 1 lote de 3 no es una buena noticia:
        el panel tiene que poder decirlo.
        """
        conforme = self._lote(codigo="L-1")
        Analisis.objects.create(
            lote=conforme, fecha=date(2026, 7, 20), valores={"humedad": 3.0, "mg": 27.0}
        )
        self._lote(codigo="L-2")
        self._lote(codigo="L-3")

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 3)
        self.assertEqual(datos["kg_producidos"], 30000.0)
        self.assertEqual(datos["calidad"]["conforme"], 1)
        self.assertEqual(datos["calidad"]["sin_analisis"], 2)
        self.assertEqual(datos["calidad"]["evaluados"], 1)
        self.assertEqual(datos["calidad"]["cumplimiento"], 100.0)
        self.assertAlmostEqual(datos["calidad"]["cobertura"], 33.3)

    def test_el_resumen_agrupa_kilos_por_producto_y_mandante(self):
        crema = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.nestle
        )
        self._lote(codigo="L-1", kg_producidos=10000)
        self._lote(codigo="L-2", producto=crema, kg_producidos=4000)

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["kg_por_producto"][0]["kg"], 10000.0)
        self.assertEqual(len(datos["kg_por_producto"]), 2)
        self.assertEqual(datos["kg_por_mandante"][0]["nombre"], "Nestlé")
        self.assertEqual(datos["kg_por_mandante"][0]["kg"], 14000.0)

    def test_los_lotes_anulados_no_entran_al_resumen(self):
        self._lote(codigo="L-1")
        self._lote(codigo="L-2", estado=Lote.Estado.ANULADO)

        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 1)
        self.assertEqual(datos["kg_producidos"], 10000.0)

    def test_sin_lotes_no_inventa_porcentajes(self):
        datos = self.cliente.get("/api/produccion/resumen/").json()

        self.assertEqual(datos["lotes"], 0)
        self.assertIsNone(datos["calidad"]["cobertura"])
        self.assertIsNone(datos["calidad"]["cumplimiento"])

    def test_acota_por_periodo(self):
        self._lote(codigo="L-1", fecha=date(2026, 7, 1))
        self._lote(codigo="L-2", fecha=date(2026, 8, 1))

        datos = self.cliente.get(
            "/api/produccion/resumen/?desde=2026-07-15"
        ).json()

        self.assertEqual(datos["lotes"], 1)
