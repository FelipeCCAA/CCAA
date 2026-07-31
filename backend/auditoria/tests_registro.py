"""
Pruebas del registro de auditoría.

Lo que protegen: que el rastro exista y sea *usable* en una auditoría. Que
diga quién, qué campo, y de qué valor a qué valor — no solo que «alguien tocó
esto». Y que cubra lo que pasa por la API, que es por donde trabaja la planta,
y no solo el admin como hacía el `LogEntry` de Django.
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


class BaseAuditoria(TestCase):
    def setUp(self):
        RegistroAuditoria.objects.all().delete()

        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )

        RegistroAuditoria.objects.all().delete()

    def _cliente(self, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente, usuario

    def _registros(self, modelo=None):
        consulta = RegistroAuditoria.objects.all()

        if modelo:
            consulta = consulta.filter(modelo=modelo)

        return list(consulta.order_by("id"))


class CapturaDeCambiosTests(BaseAuditoria):

    def test_una_creacion_queda_registrada(self):
        Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )

        registro = self._registros("produccion.Lote")[0]

        self.assertEqual(registro.accion, "creacion")
        self.assertEqual(registro.objeto_desc[:3], "L-1")

    def test_todos_los_cambios_tienen_la_misma_forma(self):
        """
        Siempre `[antes, despues]`, también en un alta —con `None` delante—.

        Es la prueba que faltaba. Las altas se guardaban como un diccionario
        plano de valores y las modificaciones como pares; la pantalla de
        auditoría desestructuraba pares sobre todo, intentó iterar un número y
        dejó la página en blanco. Dos formas en el mismo campo obligan a cada
        consumidor a distinguirlas, y el que no lo haga revienta.
        """
        lote = Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )
        lote.observacion = "algo"
        lote.save()
        lote.delete()

        for registro in self._registros("produccion.Lote"):
            with self.subTest(accion=registro.accion):
                for campo, valor in registro.cambios.items():
                    self.assertIsInstance(valor, list, campo)
                    self.assertEqual(len(valor), 2, campo)

    def test_un_alta_no_declara_un_valor_anterior(self):
        Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )

        cambios = self._registros("produccion.Lote")[0].cambios

        self.assertEqual(cambios["codigo_lote"], [None, "L-1"])
        self.assertTrue(all(par[0] is None for par in cambios.values()))

    def test_la_clave_primaria_no_es_un_cambio(self):
        """Ya viaja en `objeto_id`: repetirla en el diff solo es ruido."""
        Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )

        self.assertNotIn("id", self._registros("produccion.Lote")[0].cambios)

    def test_una_modificacion_guarda_el_antes_y_el_despues(self):
        """
        Es la pregunta que hace un auditor: no «quién lo tocó» sino «qué decía
        antes». Guardar solo el valor final no la responde.
        """
        lote = Lote.objects.create(
            codigo_lote="L-1",
            producto=self.producto,
            fecha=date(2026, 7, 16),
            kg_producidos=1000,
        )
        RegistroAuditoria.objects.all().delete()

        lote.kg_producidos = 1200
        lote.save()

        registro = self._registros("produccion.Lote")[0]

        self.assertEqual(registro.accion, "modificacion")
        self.assertEqual(registro.cambios["kg_producidos"], ["1000.00", "1200.00"])

    def test_solo_registra_los_campos_que_cambiaron(self):
        lote = Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )
        RegistroAuditoria.objects.all().delete()

        lote.observacion = "Se detuvo la torre"
        lote.save()

        self.assertEqual(
            self._registros("produccion.Lote")[0].campos_cambiados, ["observacion"]
        )

    def test_un_guardado_que_no_cambia_nada_no_deja_rastro(self):
        """Ruido: un `save()` sin cambios no es un hecho que auditar."""
        lote = Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )
        RegistroAuditoria.objects.all().delete()

        lote.save()

        self.assertEqual(self._registros("produccion.Lote"), [])

    def test_un_borrado_conserva_lo_que_habia(self):
        """
        Después de borrar, el registro es lo único que queda para reconstruir
        qué se perdió.
        """
        lote = Lote.objects.create(
            codigo_lote="L-1",
            producto=self.producto,
            fecha=date(2026, 7, 16),
            kg_producidos=900,
        )
        RegistroAuditoria.objects.all().delete()

        lote.delete()

        registro = self._registros("produccion.Lote")[0]

        self.assertEqual(registro.accion, "borrado")
        self.assertEqual(registro.cambios["kg_producidos"], ["900.00", None])
        self.assertIn("L-1", registro.objeto_desc)

    def test_las_claves_foraneas_se_guardan_por_id(self):
        """
        Sin esto, cada campo de relación dispararía una consulta para
        describir el objeto apuntado. Se audita qué cambió, no el grafo.
        """
        otro = Producto.objects.create(
            nombre="Crema", familia=Producto.Familia.CREMA, mandante=self.mandante
        )
        lote = Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )
        RegistroAuditoria.objects.all().delete()

        lote.producto = otro
        lote.save()

        self.assertEqual(
            self._registros("produccion.Lote")[0].cambios["producto"],
            [self.producto.id, otro.id],
        )


class AtribucionTests(BaseAuditoria):
    """A quién se le atribuye el cambio."""

    def test_un_cambio_por_la_api_lleva_su_usuario(self):
        """
        Es lo que el `LogEntry` de Django no cubría: registra solo el admin, y
        la planta trabaja por la pantalla.
        """
        cliente, usuario = self._cliente()

        cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "L-API",
                "producto": self.producto.id,
                "fecha": "2026-07-16",
            },
            format="json",
        )

        registro = self._registros("produccion.Lote")[0]

        self.assertEqual(registro.usuario, usuario)
        self.assertEqual(registro.usuario_nombre, usuario.username)
        self.assertEqual(registro.origen, "api")

    def test_el_nombre_sobrevive_al_borrado_del_usuario(self):
        """
        Borrar un usuario no puede borrar la historia de lo que hizo: es
        justamente lo que la auditoría existe para conservar.
        """
        cliente, usuario = self._cliente()
        cliente.post(
            "/api/produccion/lotes/",
            {"codigo_lote": "L-API", "producto": self.producto.id, "fecha": "2026-07-16"},
            format="json",
        )

        usuario.delete()

        registro = RegistroAuditoria.objects.filter(modelo="produccion.Lote").first()

        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.usuario_nombre, "u-produccion")

    def test_un_cambio_fuera_de_una_peticion_queda_como_sistema(self):
        """Migraciones, scripts y shell también se registran, sin usuario."""
        Lote.objects.create(
            codigo_lote="L-1", producto=self.producto, fecha=date(2026, 7, 16)
        )

        registro = self._registros("produccion.Lote")[0]

        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.origen, "sistema")


class AlcanceTests(BaseAuditoria):

    def test_cubre_los_maestros(self):
        Mandante.objects.create(nombre="Colun")

        self.assertTrue(self._registros("maestros.Mandante"))

    def test_cubre_las_asignaciones_de_leche(self):
        """
        Un movimiento de silo mueve el saldo del estanque: quién lo escribió
        importa tanto como el número.
        """
        from maestros.models import Silo
        from recepcion.models import MovimientoSilo

        silo = Silo.objects.create(
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=100000
        )
        MovimientoSilo.objects.create(
            silo=silo, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora="2026-07-16T10:00:00Z",
        )

        self.assertTrue(self._registros("recepcion.MovimientoSilo"))

    def test_no_audita_la_infraestructura_de_django(self):
        """
        Sesiones, permisos y tokens son ruido: no son decisiones de nadie y
        enterrarían los cambios que sí importan.
        """
        User.objects.create_user("alguien", password="x")

        self.assertEqual(self._registros("auth.User"), [])
        self.assertEqual(self._registros("sessions.Session"), [])

    def test_no_se_audita_a_si_misma(self):
        """Auditar la tabla de auditoría sería una recursión infinita."""
        Mandante.objects.create(nombre="Colun")

        self.assertEqual(self._registros("auditoria.RegistroAuditoria"), [])

    def test_la_contrasena_nunca_se_registra(self):
        """
        Aunque `auth` no se audite hoy, el campo está excluido por nombre: si
        alguien agrega `auth` a la lista, la contraseña no se filtra igual.
        """
        from .registro import CAMPOS_EXCLUIDOS

        self.assertIn("password", CAMPOS_EXCLUIDOS)
