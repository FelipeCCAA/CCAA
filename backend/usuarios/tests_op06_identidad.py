"""OP-06 baseline: identity changes must not leave usable old sessions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.core.cache import cache
from django.db import connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from .models import Empresa, PerfilUsuario, SesionUsuario, Sucursal


class IdentidadOp06APITests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="OP06-IDENTIDAD", nombre="Identidad OP-06")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="OP06", nombre="Planta OP-06",
        )
        self.admin = User.objects.create_user("jefe-op06", password="Clave-admin-2026!")
        PerfilUsuario.objects.create(
            usuario=self.admin, empresa=self.empresa, sucursal=self.sucursal,
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.trabajador = User.objects.create_user(
            "operador-op06", password="Clave-trabajador-2026!",
        )
        PerfilUsuario.objects.create(
            usuario=self.trabajador, empresa=self.empresa, sucursal=self.sucursal,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.admin_cliente = APIClient()
        self.admin_cliente.force_authenticate(self.admin)

    def test_alta_con_password_admin_obliga_cambio_antes_de_operar(self):
        superusuario = User.objects.create_superuser("root-op06", password="Clave-root-2026!")
        cliente = APIClient()
        cliente.force_authenticate(superusuario)

        respuesta = cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "nuevo-op06", "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.SECADO,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertTrue(User.objects.get(username="nuevo-op06").perfil.debe_cambiar_password)

    def test_sin_change_roles_no_crea_administrador(self):
        respuesta = self.admin_cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "admin-sin-delegacion-op06",
                "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.CALIDAD,
                "nivel": PerfilUsuario.Nivel.ADMIN,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertFalse(User.objects.filter(username="admin-sin-delegacion-op06").exists())

    def test_sin_change_roles_no_crea_admin_implicito_por_area(self):
        respuesta = self.admin_cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "admin-implicito-op06",
                "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.ADMINISTRACION,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertFalse(User.objects.filter(username="admin-implicito-op06").exists())

    def test_con_change_roles_crea_admin_implicito_por_area(self):
        self.admin.user_permissions.add(Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        ))
        respuesta = self.admin_cliente.post(
            "/api/usuarios/trabajadores/",
            {
                "username": "admin-implicito-delegado-op06",
                "password": "Clave-inicial-2026!",
                "area": PerfilUsuario.Area.ADMINISTRACION,
                "nivel": PerfilUsuario.Nivel.TRABAJADOR,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        creada = User.objects.get(username="admin-implicito-delegado-op06")
        self.assertEqual(creada.perfil.area, PerfilUsuario.Area.ADMINISTRACION)
        self.assertTrue(creada.perfil.debe_cambiar_password)

    def test_sin_change_roles_no_cambia_area_ni_promueve(self):
        for datos in (
            {"area": PerfilUsuario.Area.CALIDAD},
            {"nivel": PerfilUsuario.Nivel.ADMIN},
        ):
            with self.subTest(datos=datos):
                respuesta = self.admin_cliente.patch(
                    f"/api/usuarios/trabajadores/{self.trabajador.pk}/",
                    datos, format="json",
                )
                self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.trabajador.perfil.refresh_from_db()
        self.assertEqual(self.trabajador.perfil.area, PerfilUsuario.Area.SECADO)
        self.assertEqual(self.trabajador.perfil.nivel, PerfilUsuario.Nivel.TRABAJADOR)

    def test_con_change_roles_crea_admin_sin_superusuario(self):
        self.admin.user_permissions.add(Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        ))
        respuesta = self.admin_cliente.post(
            "/api/usuarios/trabajadores/",
            {"username": "jefa-calidad-op06", "password": "Clave-inicial-2026!",
             "area": PerfilUsuario.Area.CALIDAD, "nivel": PerfilUsuario.Nivel.ADMIN},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        creada = User.objects.get(username="jefa-calidad-op06")
        self.assertTrue(creada.is_staff)
        self.assertFalse(creada.is_superuser)
        self.assertTrue(creada.perfil.debe_cambiar_password)

    def test_yo_expone_change_roles_concedido_por_grupo(self):
        grupo = Group.objects.create(name="roles-delegados-op06")
        grupo.permissions.add(Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        ))
        self.admin.groups.add(grupo)
        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.admin.username, "password": "Clave-admin-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {acceso.data['token']}")
        respuesta = cliente.get("/api/usuarios/yo/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertIn("change_roles", respuesta.data["capacidades"])
        self.assertNotIn("change_roles", self.admin.user_permissions.values_list(
            "codename", flat=True,
        ))

    def test_cambio_efectivo_de_permisos_revoca_token_previo(self):
        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.trabajador.username, "password": "Clave-trabajador-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)
        token = acceso.data["token"]

        respuesta = self.admin_cliente.patch(
            f"/api/usuarios/trabajadores/{self.trabajador.pk}/",
            {"permisos": ["produccion_orden_crear"]},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        anterior = APIClient()
        anterior.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(anterior.get("/api/usuarios/yo/").status_code, 401)
        self.assertFalse(SesionUsuario.objects.filter(
            usuario=self.trabajador, fecha_cierre__isnull=True,
        ).exists())

    def test_repetir_mismos_permisos_no_revoca_sesion(self):
        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.trabajador.username, "password": "Clave-trabajador-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)
        token = acceso.data["token"]

        respuesta = self.admin_cliente.patch(
            f"/api/usuarios/trabajadores/{self.trabajador.pk}/",
            {"permisos": []}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        anterior = APIClient()
        anterior.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(anterior.get("/api/usuarios/yo/").status_code, 200)
        self.assertEqual(SesionUsuario.objects.filter(
            usuario=self.trabajador, fecha_cierre__isnull=True,
        ).count(), 1)

    def test_fallo_revocacion_revierte_permisos_y_preserva_sesion(self):
        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.trabajador.username, "password": "Clave-trabajador-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)
        token = acceso.data["token"]

        with patch("usuarios.views.revocar_sesiones", side_effect=RuntimeError("fallo inyectado")):
            with self.assertRaises(RuntimeError):
                self.admin_cliente.patch(
                    f"/api/usuarios/trabajadores/{self.trabajador.pk}/",
                    {"permisos": ["produccion_orden_crear"]}, format="json",
                )

        self.trabajador.refresh_from_db()
        self.assertEqual(list(self.trabajador.user_permissions.values_list("codename", flat=True)), [])
        anterior = APIClient()
        anterior.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(anterior.get("/api/usuarios/yo/").status_code, 200)

    def test_permiso_change_roles_habilita_promocion_y_revoca_token(self):
        self.admin.user_permissions.add(Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        ))
        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.trabajador.username, "password": "Clave-trabajador-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)

        respuesta = self.admin_cliente.patch(
            f"/api/usuarios/trabajadores/{self.trabajador.pk}/",
            {"area": PerfilUsuario.Area.CALIDAD, "nivel": PerfilUsuario.Nivel.ADMIN},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.trabajador.perfil.refresh_from_db()
        self.assertEqual(self.trabajador.perfil.area, PerfilUsuario.Area.CALIDAD)
        self.assertEqual(self.trabajador.perfil.nivel, PerfilUsuario.Nivel.ADMIN)
        anterior = APIClient()
        anterior.credentials(HTTP_AUTHORIZATION=f"Token {acceso.data['token']}")
        self.assertEqual(anterior.get("/api/usuarios/yo/").status_code, 401)

    def test_alta_propia_area_y_cambio_forzado_de_password(self):
        jefe_secado = User.objects.create_user("jefe-secado-op06", password="Clave-jefe-2026!")
        PerfilUsuario.objects.create(
            usuario=jefe_secado, empresa=self.empresa, sucursal=self.sucursal,
            area=PerfilUsuario.Area.SECADO, nivel=PerfilUsuario.Nivel.ADMIN,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        cliente_jefe = APIClient()
        cliente_jefe.force_authenticate(jefe_secado)
        alta = cliente_jefe.post(
            "/api/usuarios/trabajadores/",
            {"username": "nuevo-turno-op06", "password": "Clave-inicial-2026!",
             "area": PerfilUsuario.Area.CALIDAD, "nivel": PerfilUsuario.Nivel.ADMIN},
            format="json",
        )
        self.assertEqual(alta.status_code, 201, alta.data)
        creado = User.objects.get(username="nuevo-turno-op06")
        self.assertEqual(creado.perfil.area, PerfilUsuario.Area.SECADO)
        self.assertEqual(creado.perfil.nivel, PerfilUsuario.Nivel.TRABAJADOR)
        self.assertTrue(creado.perfil.debe_cambiar_password)

        acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": creado.username, "password": "Clave-inicial-2026!"},
            format="json",
        )
        self.assertEqual(acceso.status_code, 200, acceso.data)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {acceso.data['token']}")
        bloqueada = cliente.get("/api/maestros/productos/")
        self.assertEqual(bloqueada.status_code, 403)
        self.assertEqual(bloqueada.data["code"], "PASSWORD_CHANGE_REQUIRED")
        igual = cliente.post(
            "/api/usuarios/cambiar-password/",
            {"password_actual": "Clave-inicial-2026!",
             "nueva_contrasena": "Clave-inicial-2026!",
             "confirmar_contrasena": "Clave-inicial-2026!"},
            format="json",
        )
        self.assertEqual(igual.status_code, 400, igual.data)
        creado.perfil.refresh_from_db()
        self.assertTrue(creado.perfil.debe_cambiar_password)
        self.assertEqual(cliente.get("/api/maestros/productos/").status_code, 403)
        cambiada = cliente.post(
            "/api/usuarios/cambiar-password/",
            {"password_actual": "Clave-inicial-2026!",
             "nueva_contrasena": "Clave-propia-2026!",
             "confirmar_contrasena": "Clave-propia-2026!"},
            format="json",
        )
        self.assertEqual(cambiada.status_code, 200, cambiada.data)
        self.assertEqual(cliente.get("/api/usuarios/yo/").status_code, 401)
        creado.perfil.refresh_from_db()
        self.assertFalse(creado.perfil.debe_cambiar_password)
        nuevo_acceso = APIClient().post(
            "/api/usuarios/login/",
            {"username": creado.username, "password": "Clave-propia-2026!"},
            format="json",
        )
        self.assertEqual(nuevo_acceso.status_code, 200, nuevo_acceso.data)
        nueva_sesion = APIClient()
        nueva_sesion.credentials(HTTP_AUTHORIZATION=f"Token {nuevo_acceso.data['token']}")
        self.assertEqual(nueva_sesion.get("/api/maestros/productos/").status_code, 200)


class IdentidadOp06ConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.usuario = User.objects.create_user(
            "carrera-clave-op06", password="Clave-antigua-2026!",
        )

    def test_login_que_autentico_antes_del_reset_revalida_bajo_lock(self):
        import usuarios.views as vistas

        autenticado = Event()
        continuar = Event()
        original = vistas.authenticate

        def autenticar_y_pausar(*args, **kwargs):
            usuario = original(*args, **kwargs)
            autenticado.set()
            if not continuar.wait(timeout=10):
                raise AssertionError("El reset no liberó el login.")
            return usuario

        def iniciar_login():
            try:
                return APIClient().post(
                    "/api/usuarios/login/",
                    {"username": "carrera-clave-op06", "password": "Clave-antigua-2026!"},
                    format="json",
                ).status_code
            finally:
                connections.close_all()

        with patch.object(vistas, "authenticate", side_effect=autenticar_y_pausar):
            with ThreadPoolExecutor(max_workers=1) as ejecutor:
                futuro = ejecutor.submit(iniciar_login)
                try:
                    self.assertTrue(autenticado.wait(timeout=8))
                    with transaction.atomic():
                        usuario = User.objects.select_for_update().get(pk=self.usuario.pk)
                        usuario.set_password("Clave-nueva-2026!")
                        usuario.save(update_fields=["password"])
                finally:
                    continuar.set()
                resultado = futuro.result(timeout=10)

        self.assertEqual(resultado, 401)
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.usuario).count(), 0)

    def test_desactivacion_entre_authenticate_y_lock_no_abre_sesion(self):
        import usuarios.views as vistas

        autenticado = Event()
        continuar = Event()
        original = vistas.authenticate

        def autenticar_y_pausar(*args, **kwargs):
            usuario = original(*args, **kwargs)
            autenticado.set()
            if not continuar.wait(timeout=10):
                raise AssertionError("La desactivación no liberó el login.")
            return usuario

        def iniciar_login():
            try:
                return APIClient().post(
                    "/api/usuarios/login/",
                    {"username": "carrera-clave-op06", "password": "Clave-antigua-2026!"},
                    format="json",
                ).status_code
            finally:
                connections.close_all()

        with patch.object(vistas, "authenticate", side_effect=autenticar_y_pausar):
            with ThreadPoolExecutor(max_workers=1) as ejecutor:
                futuro = ejecutor.submit(iniciar_login)
                try:
                    self.assertTrue(autenticado.wait(timeout=8))
                    with transaction.atomic():
                        usuario = User.objects.select_for_update().get(pk=self.usuario.pk)
                        usuario.is_active = False
                        usuario.save(update_fields=["is_active"])
                finally:
                    continuar.set()
                resultado = futuro.result(timeout=10)

        self.assertEqual(resultado, 403)
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.usuario).count(), 0)

    def test_login_espera_lock_real_de_reset_y_rechaza_clave_vieja(self):
        if connection.vendor != "postgresql":
            self.skipTest("pg_blocking_pids requiere PostgreSQL")
        import usuarios.views as vistas

        reset_tiene_lock = Event()
        liberar_reset = Event()
        autenticado = Event()
        pids = {}
        original = vistas.authenticate

        def autenticar_observable(*args, **kwargs):
            usuario = original(*args, **kwargs)
            autenticado.set()
            return usuario

        def resetear():
            try:
                with transaction.atomic():
                    usuario = User.objects.select_for_update().get(pk=self.usuario.pk)
                    usuario.set_password("Clave-nueva-2026!")
                    usuario.save(update_fields=["password"])
                    reset_tiene_lock.set()
                    if not liberar_reset.wait(timeout=10):
                        raise AssertionError("El test no liberó el reset.")
            finally:
                connections.close_all()

        def iniciar_login():
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_backend_pid()")
                    pids["login"] = cursor.fetchone()[0]
                return APIClient().post(
                    "/api/usuarios/login/",
                    {"username": "carrera-clave-op06", "password": "Clave-antigua-2026!"},
                    format="json",
                ).status_code
            finally:
                connections.close_all()

        with patch.object(vistas, "authenticate", side_effect=autenticar_observable):
            with ThreadPoolExecutor(max_workers=2) as ejecutor:
                reset = ejecutor.submit(resetear)
                try:
                    self.assertTrue(reset_tiene_lock.wait(timeout=8))
                    login = ejecutor.submit(iniciar_login)
                    self.assertTrue(autenticado.wait(timeout=8))
                    limite = monotonic() + 8
                    bloqueadores = []
                    while monotonic() < limite:
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_blocking_pids(%s)", [pids["login"]])
                            bloqueadores = cursor.fetchone()[0]
                        if bloqueadores:
                            break
                        sleep(0.05)
                    self.assertTrue(bloqueadores, "El login no esperó el lock de User.")
                finally:
                    liberar_reset.set()
                reset.result(timeout=10)
                resultado = login.result(timeout=10)

        self.assertEqual(resultado, 401)
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.usuario).count(), 0)
