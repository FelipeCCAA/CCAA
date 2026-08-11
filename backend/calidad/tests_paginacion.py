"""
Pruebas del techo del listado de expedientes.

Era el endpoint más caro del sistema: sin paginación ni límite, cada llamada
armaba el expediente de **todo** el histórico —evaluando checklist y veredicto
de cada lote en memoria— y el coste crecía con la planta. El filtro por estado,
además, se aplicaba después de armarlo todo, así que filtrar no ahorraba nada.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import DocumentoLiberacion, Mandante, Producto
from produccion.models import Lote
from usuarios.models import PerfilUsuario, Rol

from .models import Liberacion


class BaseExpedientes(TestCase):

    def setUp(self):
        # El catálogo del Dossier se siembra por migración de datos y también
        # aparece en la base de pruebas: sin limpiarlo, el avance se mediría
        # contra documentos que esta prueba no creó.
        DocumentoLiberacion.objects.all().delete()

        usuario = User.objects.create_user(username="calidad", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.CALIDAD)

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        mandante = Mandante.objects.create(nombre="Mandante")
        self.producto = Producto.objects.create(
            nombre="Leche en polvo", familia=Producto.Familia.POLVO, mandante=mandante
        )

    def _lotes(self, cuantos, estado=Lote.Estado.PRODUCIDO):
        return [
            Lote.objects.create(
                codigo_lote=f"L-{n:04d}",
                producto=self.producto,
                fecha=date(2026, 8, 1),
                estado=estado,
                kg_producidos=100,
            )
            for n in range(cuantos)
        ]

    def _pedir(self, **params):
        return self.cliente.get("/api/calidad/expedientes/", params)


class TechoTests(BaseExpedientes):

    def test_la_pagina_tiene_techo(self):
        """
        Sin esto se armaban los 954 lotes del histórico —y subiendo— en cada
        carga de la pantalla de Calidad.
        """
        self._lotes(60)

        datos = self._pedir().json()

        self.assertEqual(len(datos["resultados"]), 50)
        self.assertEqual(datos["total"], 60)
        self.assertTrue(datos["hay_mas"])

    def test_el_total_es_el_de_la_consulta_y_no_el_de_la_pagina(self):
        """
        Es lo que permite decir «50 de 60». Con el total de la página, la
        pantalla afirmaría que no hay nada más.
        """
        self._lotes(60)

        self.assertEqual(self._pedir().json()["total"], 60)

    def test_se_puede_pedir_la_siguiente(self):
        self._lotes(60)

        datos = self._pedir(pagina=2).json()

        self.assertEqual(len(datos["resultados"]), 10)
        self.assertFalse(datos["hay_mas"])

    def test_nadie_sube_el_techo_desde_la_url(self):
        """
        `limite=100000` en la barra de direcciones sería una forma trivial de
        tumbar el backend: cada fila evalúa el checklist de su lote.
        """
        self._lotes(60)

        datos = self._pedir(limite=100000).json()

        self.assertLessEqual(len(datos["resultados"]), 200)
        self.assertEqual(datos["limite"], 200)

    def test_una_paginacion_con_basura_no_revienta(self):
        self._lotes(3)

        for valores in ({"pagina": "abc"}, {"limite": "-5"}, {"pagina": "0"}):
            with self.subTest(valores=valores):
                respuesta = self._pedir(**valores)

                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.json()["total"], 3)


class FiltroPorEstadoTests(BaseExpedientes):

    def test_el_estado_filtra_en_la_consulta(self):
        """
        Antes se armaban todas las filas y luego se descartaban: el filtro no
        ahorraba trabajo, solo escondía el resultado. Ahora recorta el total,
        que es la prueba de que ocurrió en la base.
        """
        lotes = self._lotes(5)
        Liberacion.objects.create(
            lote=lotes[0], estado=Liberacion.Estado.LIBERADO
        )

        datos = self._pedir(estado=Liberacion.Estado.LIBERADO).json()

        self.assertEqual(datos["total"], 1)
        self.assertEqual(len(datos["resultados"]), 1)

    def test_pendiente_incluye_al_lote_sin_expediente(self):
        """
        «Pendiente» son dos cosas a la vez: el lote que nadie abrió y el que
        tiene el expediente en ese estado. Para Calidad son lo mismo —algo que
        todavía nadie decidió— y separarlas escondería la mitad del trabajo.
        """
        lotes = self._lotes(3)
        Liberacion.objects.create(
            lote=lotes[0], estado=Liberacion.Estado.PENDIENTE
        )

        datos = self._pedir(estado=Liberacion.Estado.PENDIENTE).json()

        self.assertEqual(datos["total"], 3)
