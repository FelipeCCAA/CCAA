"""
Pruebas de permisos por rol.

El criterio: todos leen todo, cada uno escribe en lo suyo.

Lo que se vigila aquí es que un rol NO pueda escribir donde no le
corresponde. Que el camino permitido funcione importa; que el prohibido
falle, importa más.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from produccion.models import Lote

from .models import PerfilUsuario, Rol, SesionUsuario
from .sesiones import nueva_credencial


def autenticar(cliente, usuario):
    token, digest = nueva_credencial()
    SesionUsuario.objects.create(usuario=usuario, token_hash=digest)
    cliente.credentials(HTTP_AUTHORIZATION=f"Token {token}")


class BasePermisos(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")
        self.producto = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=self.producto,
            fecha=date(2026, 7, 20),
            kg_producidos=10000,
        )

    def cliente_con_rol(self, rol):
        usuario = User.objects.create_user(username=f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)

        cliente = APIClient()
        autenticar(cliente, usuario)
        return cliente

    def _lote_nuevo(self, codigo):
        return {
            "codigo_lote": codigo,
            "producto": self.producto.id,
            "fecha": "2026-07-25",
            "kg_producidos": "1000.00",
        }


class TodosLeenTodoTests(BasePermisos):
    """
    Que Recepción consulte los lotes de Producción no es una concesión: es
    necesario para trabajar. Ocultar información entre áreas de la misma
    planta genera más errores de los que evita.
    """

    RUTAS = [
        "/api/produccion/lotes/",
        "/api/produccion/resumen/",
        "/api/maestros/productos/",
        "/api/maestros/especificaciones/",
    ]

    def test_todos_los_roles_pueden_leer(self):
        for rol in Rol.values:
            cliente = self.cliente_con_rol(rol)

            for ruta in self.RUTAS:
                with self.subTest(rol=rol, ruta=ruta):
                    self.assertEqual(cliente.get(ruta).status_code, 200)


class EscrituraDeProduccionTests(BasePermisos):
    def test_produccion_registra_lotes(self):
        cliente = self.cliente_con_rol(Rol.PRODUCCION)

        respuesta = cliente.post(
            "/api/produccion/lotes/", self._lote_nuevo("NUEVO-1"), format="json"
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_administracion_tambien(self):
        cliente = self.cliente_con_rol(Rol.ADMIN)

        respuesta = cliente.post(
            "/api/produccion/lotes/", self._lote_nuevo("NUEVO-2"), format="json"
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_recepcion_calidad_y_lectura_no_registran_lotes(self):
        for rol in [Rol.RECEPCION, Rol.CALIDAD, Rol.LECTURA]:
            with self.subTest(rol=rol):
                cliente = self.cliente_con_rol(rol)

                respuesta = cliente.post(
                    "/api/produccion/lotes/",
                    self._lote_nuevo(f"X-{rol}"),
                    format="json",
                )

                self.assertEqual(respuesta.status_code, 403)

    def test_calidad_no_borra_lotes(self):
        cliente = self.cliente_con_rol(Rol.CALIDAD)

        respuesta = cliente.delete(f"/api/produccion/lotes/{self.lote.id}/")

        self.assertEqual(respuesta.status_code, 403)
        self.assertEqual(Lote.objects.count(), 1)

    def test_el_rechazo_explica_el_motivo(self):
        """Un 403 sin explicación deja al usuario sin saber qué hacer."""
        cliente = self.cliente_con_rol(Rol.LECTURA)

        respuesta = cliente.post(
            "/api/produccion/lotes/", self._lote_nuevo("X"), format="json"
        )

        self.assertIn("Producción", respuesta.json()["detail"])


class EscrituraDeMaestrosTests(BasePermisos):
    """
    Los maestros solo los toca Administración: una especificación decide qué
    producto sale como conforme y su cambio reevalúa el histórico completo.
    """

    def test_administracion_crea_productos(self):
        cliente = self.cliente_con_rol(Rol.ADMIN)

        respuesta = cliente.post(
            "/api/maestros/productos/",
            {"nombre": "Crema", "familia": "crema", "mandante": self.mandante.id},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201)

    def test_ningun_otro_rol_toca_los_maestros(self):
        for rol in [Rol.PRODUCCION, Rol.RECEPCION, Rol.CALIDAD, Rol.LECTURA]:
            with self.subTest(rol=rol):
                cliente = self.cliente_con_rol(rol)

                respuesta = cliente.post(
                    "/api/maestros/productos/",
                    {"nombre": f"X-{rol}", "familia": "otro", "mandante": self.mandante.id},
                    format="json",
                )

                self.assertEqual(respuesta.status_code, 403)

    def test_produccion_no_cambia_una_especificacion(self):
        """
        Si Producción pudiera editar la spec, podría hacer conforme un lote
        que no lo es. Es exactamente lo que el sistema viene a impedir.
        """
        cliente = self.cliente_con_rol(Rol.PRODUCCION)

        respuesta = cliente.post(
            "/api/maestros/especificaciones/",
            {
                "producto": self.producto.id,
                "version": 9,
                "vigente_desde": "2026-01-01",
                "rangos": {"humedad": {"min": 0, "max": 100}},
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)


class RolEfectivoTests(BasePermisos):
    def test_un_superusuario_es_administrador_sin_perfil(self):
        """
        Quien instaló el sistema con `createsuperuser` no tiene perfil.
        Dejarlo sin permisos lo encerraría fuera de su propia instalación.
        """
        usuario = User.objects.create_superuser(username="root", password="x")
        cliente = APIClient()
        autenticar(cliente, usuario)

        self.assertEqual(cliente.get("/api/usuarios/yo/").json()["rol"], "admin")
        self.assertEqual(
            cliente.post(
                "/api/produccion/lotes/", self._lote_nuevo("ROOT-1"), format="json"
            ).status_code,
            201,
        )

    def test_un_usuario_normal_sin_perfil_no_escribe(self):
        usuario = User.objects.create_user(username="huerfano", password="x")
        cliente = APIClient()
        autenticar(cliente, usuario)

        self.assertIsNone(cliente.get("/api/usuarios/yo/").json()["rol"])
        self.assertEqual(
            cliente.post(
                "/api/produccion/lotes/", self._lote_nuevo("X"), format="json"
            ).status_code,
            403,
        )

    def test_el_rol_efectivo_viaja_en_el_login(self):
        """La interfaz decide con este campo qué acciones mostrar."""
        User.objects.create_user(username="cal", password="clave-de-prueba")
        PerfilUsuario.objects.create(
            usuario=User.objects.get(username="cal"), rol=Rol.CALIDAD
        )

        datos = APIClient().post(
            "/api/usuarios/login/",
            {"username": "cal", "password": "clave-de-prueba"},
            format="json",
        ).json()

        self.assertEqual(datos["usuario"]["rol"], "calidad")
        self.assertEqual(datos["usuario"]["perfil"]["rol_etiqueta"], "Calidad")
