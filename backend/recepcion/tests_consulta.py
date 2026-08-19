"""
Pruebas de la consulta de recepciones: filtro por estados, búsqueda y resumen.

Las tres existen por el mismo defecto: la pantalla traía una página y sacaba
conclusiones sobre ella. Contaba los estados de esa página, buscaba dentro de
esa página, y respondía «no encontramos recepciones» sobre datos que sí
estaban. Lo que se fija aquí es que las tres preguntas las conteste la base.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo
from usuarios.models import PerfilUsuario, Rol

from .models import Recepcion


class BaseConsulta(TestCase):

    def setUp(self):
        usuario = User.objects.create_user(username="op-consulta", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        self.silo, _ = Silo.objects.update_or_create(
            codigo="SILO-CONSULTA",
            defaults={"tipo": Silo.Tipo.SILO, "capacidad_l": 100000},
        )

    def _recepcion(self, **extra):
        datos = {
            "fecha": date(2026, 8, 1),
            "hora": "08:00",
            "litros": "20000.00",
            "estado": Recepcion.Estado.REGISTRADA,
        }
        datos.update(extra)
        return Recepcion.objects.create(**datos)


class FiltroEstadosTests(BaseConsulta):

    def test_un_solo_estado(self):
        self._recepcion(estado=Recepcion.Estado.REGISTRADA)
        self._recepcion(estado=Recepcion.Estado.MUESTREADA)

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/", {"estado": "registrada"}
        )

        self.assertEqual(respuesta.data["count"], 1)

    def test_varios_estados_separados_por_coma(self):
        """
        La pestaña «Calidad» son las muestreadas *y* las retenidas. Sin esto
        tendría que traerse todo y filtrar en el cliente, que es de donde
        venían los contadores que medían la página.
        """
        self._recepcion(estado=Recepcion.Estado.MUESTREADA)
        self._recepcion(estado=Recepcion.Estado.RETENIDA)
        self._recepcion(estado=Recepcion.Estado.REGISTRADA)

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/", {"estado": "muestreada,retenida"}
        )

        self.assertEqual(respuesta.data["count"], 2)
        self.assertEqual(
            {r["estado"] for r in respuesta.data["results"]},
            {"muestreada", "retenida"},
        )


class BusquedaTests(BaseConsulta):

    def test_busca_en_la_base_y_no_en_la_pagina(self):
        """
        La de la página 2 tiene que aparecer. Con el filtro en el cliente
        —sobre las cincuenta filas descargadas— esta búsqueda no la encontraba
        y la pantalla afirmaba que no existía.
        """
        for n in range(60):
            self._recepcion(guia=f"G-{n:03d}")

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/", {"q": "G-059"}
        )

        self.assertEqual(respuesta.data["count"], 1)
        self.assertEqual(respuesta.data["results"][0]["guia"], "G-059")

    def test_busca_por_varios_campos(self):
        self._recepcion(guia="G-1", procedencia="Nestlé")
        self._recepcion(guia="G-2", codigo_muestra="M-2026-88")
        self._recepcion(guia="G-3", silo=self.silo)

        for termino, esperado in (
            ("Nestlé", "G-1"),
            ("2026-88", "G-2"),
            ("SILO-CONSULTA", "G-3"),
        ):
            with self.subTest(termino=termino):
                respuesta = self.cliente.get(
                    "/api/recepcion/recepciones/", {"q": termino}
                )
                self.assertEqual(respuesta.data["count"], 1)
                self.assertEqual(respuesta.data["results"][0]["guia"], esperado)

    def test_una_busqueda_sin_resultados_no_es_un_error(self):
        self._recepcion(guia="G-1")

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/", {"q": "no-existe"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["count"], 0)


class ResumenTests(BaseConsulta):

    def test_cuenta_sobre_el_total_y_no_sobre_una_pagina(self):
        """
        Sesenta recepciones no caben en una página de cincuenta. El tablero las
        contaba desde ahí, así que a partir de la fila cincuenta y uno dejaba
        de decir la verdad sin avisar.
        """
        for _ in range(60):
            self._recepcion(estado=Recepcion.Estado.REGISTRADA)

        respuesta = self.cliente.get("/api/recepcion/recepciones/resumen/")

        self.assertEqual(respuesta.data["total"], 60)
        self.assertEqual(respuesta.data["por_estado"]["registrada"], 60)

    def test_el_resumen_describe_la_planta_no_la_vista(self):
        """
        Filtrar la tabla por un estado no puede vaciar el resumen: hacía
        parecer que la planta se había quedado sin nada más.
        """
        self._recepcion(estado=Recepcion.Estado.REGISTRADA)
        self._recepcion(estado=Recepcion.Estado.MUESTREADA)

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/resumen/", {"estado": "registrada"}
        )

        self.assertEqual(respuesta.data["por_estado"]["muestreada"], 1)

    def test_distingue_las_aprobadas_con_y_sin_silo(self):
        """
        Asignar silo y descargar son dos trabajos distintos y el estado es el
        mismo en los dos. Sin esta partición, «liberada» no dice cuál toca.
        """
        self._recepcion(estado=Recepcion.Estado.LIBERADA)
        self._recepcion(estado=Recepcion.Estado.LIBERADA, silo=self.silo)

        respuesta = self.cliente.get("/api/recepcion/recepciones/resumen/")

        self.assertEqual(respuesta.data["liberadas_sin_silo"], 1)
        self.assertEqual(respuesta.data["liberadas_con_silo"], 1)

    def test_todos_los_estados_aparecen_aunque_esten_en_cero(self):
        """
        Una clave ausente y un cero se leen distinto en la pantalla: la primera
        obliga a cada consumidor a defenderse de `undefined`.
        """
        respuesta = self.cliente.get("/api/recepcion/recepciones/resumen/")

        self.assertEqual(
            set(respuesta.data["por_estado"]),
            {valor for valor, _ in Recepcion.Estado.choices},
        )
