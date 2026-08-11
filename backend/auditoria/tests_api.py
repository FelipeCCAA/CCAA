"""
Pruebas de la consulta del registro de auditoría.

La garantía que más importa aquí: **no hay forma de modificarlo por la API**.
Un registro de auditoría que se puede editar o borrar no prueba nada.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from produccion.models import Lote
from usuarios.models import PerfilUsuario, Rol

from .models import RegistroAuditoria


class BaseApiAuditoria(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )
        self.cliente, self.usuario = self._cliente(Rol.ADMIN)

    def _cliente(self, rol):
        # Sufijo por cantidad: una prueba puede pedir varios clientes del
        # mismo rol y el username es único.
        usuario = User.objects.create_user(
            f"u-{rol}-{User.objects.count()}", password="x"
        )
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente, usuario


class SoloLecturaTests(BaseApiAuditoria):

    def test_no_se_puede_crear_un_registro(self):
        respuesta = self.cliente.post(
            "/api/auditoria/registros/", {"accion": "creacion"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 405)

    def test_no_se_puede_modificar_un_registro(self):
        registro = RegistroAuditoria.objects.first()

        respuesta = self.cliente.patch(
            f"/api/auditoria/registros/{registro.id}/",
            {"usuario_nombre": "otro"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 405)

    def test_no_se_puede_borrar_un_registro(self):
        registro = RegistroAuditoria.objects.first()

        respuesta = self.cliente.delete(f"/api/auditoria/registros/{registro.id}/")

        self.assertEqual(respuesta.status_code, 405)

    def test_sin_sesion_no_se_consulta(self):
        self.assertEqual(
            APIClient().get("/api/auditoria/registros/").status_code, 401
        )

    def test_solo_calidad_y_administracion_pueden_consultar(self):
        """
        La auditoría se mira, no se toca. Restringirla a Administración
        escondería el rastro justo de quien tiene más poder para cambiar cosas.
        """
        for rol in (Rol.CALIDAD, Rol.ADMIN):
            with self.subTest(rol=rol):
                cliente, _ = self._cliente(rol)
                self.assertEqual(
                    cliente.get("/api/auditoria/registros/").status_code, 200
                )
        for rol in (Rol.PRODUCCION, Rol.RECEPCION):
            with self.subTest(rol=rol):
                cliente, _ = self._cliente(rol)
                self.assertEqual(
                    cliente.get("/api/auditoria/registros/").status_code, 403
                )


class ConsultaTests(BaseApiAuditoria):

    def _resultados(self, **params):
        return self.cliente.get("/api/auditoria/registros/", params).json()["results"]

    def test_lista_los_cambios_con_su_diff(self):
        self.lote.kg_producidos = 1200
        self.lote.save()

        fila = self._resultados(modelo="produccion.Lote", accion="modificacion")[0]

        self.assertEqual(fila["cambios"]["kg_producidos"], [None, "1200.00"])
        self.assertEqual(fila["accion_etiqueta"], "Modificación")

    def test_se_filtra_por_modelo(self):
        filas = self._resultados(modelo="maestros.Mandante")

        self.assertTrue(filas)
        self.assertTrue(all(f["modelo"] == "maestros.Mandante" for f in filas))

    def test_se_filtra_por_objeto_para_ver_su_historia(self):
        """
        Es la consulta que hace un auditor: qué le pasó a ESTE lote, en orden.
        """
        self.lote.observacion = "primera"
        self.lote.save()
        self.lote.observacion = "segunda"
        self.lote.save()

        filas = self._resultados(modelo="produccion.Lote", objeto=str(self.lote.id))

        self.assertEqual(len(filas), 3)  # alta + dos modificaciones

    def test_se_filtra_por_usuario(self):
        self.cliente.post(
            "/api/produccion/lotes/",
            {"codigo_lote": "L-API", "producto": self.producto.id, "fecha": "2026-07-16"},
            format="json",
        )

        filas = self._resultados(usuario=self.usuario.username)

        self.assertTrue(filas)
        self.assertTrue(all(f["usuario_nombre"] == self.usuario.username for f in filas))

    def test_el_mas_reciente_va_primero(self):
        self.lote.observacion = "última"
        self.lote.save()

        self.assertEqual(self._resultados()[0]["accion"], "modificacion")


class FiltrosTests(BaseApiAuditoria):

    def test_ofrece_solo_los_modelos_que_tienen_registros(self):
        """
        Una lista fija ofrecería filtros que no devuelven nada y escondería
        los que sí.
        """
        datos = self.cliente.get("/api/auditoria/filtros/").json()

        valores = {m["valor"] for m in datos["modelos"]}

        self.assertIn("produccion.Lote", valores)
        self.assertNotIn("calidad.Liberacion", valores)

    def test_los_modelos_traen_su_nombre_legible(self):
        datos = self.cliente.get("/api/auditoria/filtros/").json()
        lote = next(m for m in datos["modelos"] if m["valor"] == "produccion.Lote")

        self.assertEqual(lote["etiqueta"], "Lote de producción")
