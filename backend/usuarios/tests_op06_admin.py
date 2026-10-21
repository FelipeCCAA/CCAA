"""Regresiones del panel Django: sus ediciones también cambian identidad operativa."""

from unittest.mock import patch

from django.contrib.auth.models import Group, Permission, User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Empresa, PerfilUsuario, SesionUsuario


class IdentidadOp06AdminTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="OP06-ADMIN", nombre="Admin OP-06")
        self.actor = User.objects.create_superuser(
            "root-admin-op06", password="Clave-root-2026!",
        )
        self.client.force_login(self.actor)
        self.usuario = User.objects.create_user(
            "operador-admin-op06", password="Clave-operador-2026!",
        )
        self.perfil = PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.empresa,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.TRABAJADOR,
        )

    def _token_operador(self):
        respuesta = APIClient().post(
            "/api/usuarios/login/",
            {"username": self.usuario.username, "password": "Clave-operador-2026!"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        return respuesta.data["token"]

    def _actor_area(self, nombre, area=PerfilUsuario.Area.ADMINISTRACION):
        actor = User.objects.create_user(nombre, password="Clave-staff-2026!")
        PerfilUsuario.objects.create(
            usuario=actor, empresa=self.empresa, area=area,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        return actor

    def _sesion_sigue_vigente(self, token):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION=f"Token {token}")
        return cliente.get("/api/usuarios/yo/").status_code == 200

    def _datos_perfil(self, *, area=PerfilUsuario.Area.SECADO,
                      nivel=PerfilUsuario.Nivel.TRABAJADOR):
        return {
            "usuario": self.usuario.pk,
            "empresa": self.empresa.pk,
            "area": area,
            "nivel": nivel,
            "cargo": "",
            "turno": "",
            "areas_adicionales-TOTAL_FORMS": "0",
            "areas_adicionales-INITIAL_FORMS": "0",
            "areas_adicionales-MIN_NUM_FORMS": "0",
            "areas_adicionales-MAX_NUM_FORMS": "1000",
        }

    def _datos_usuario(self, *, permisos=(), activo=True):
        return {
            "username": self.usuario.username,
            "first_name": self.usuario.first_name,
            "last_name": self.usuario.last_name,
            "email": self.usuario.email,
            "is_active": "on" if activo else "",
            "is_staff": "",
            "is_superuser": "",
            "groups": [],
            "user_permissions": list(permisos),
            "date_joined_0": self.usuario.date_joined.strftime("%Y-%m-%d"),
            "date_joined_1": self.usuario.date_joined.strftime("%H:%M:%S"),
            "perfil-TOTAL_FORMS": "1",
            "perfil-INITIAL_FORMS": "1",
            "perfil-MIN_NUM_FORMS": "0",
            "perfil-MAX_NUM_FORMS": "1",
            "perfil-0-id": self.perfil.pk,
            "perfil-0-usuario": self.usuario.pk,
            "perfil-0-empresa": self.empresa.pk,
            "perfil-0-area": self.perfil.area,
            "perfil-0-nivel": self.perfil.nivel,
            "perfil-0-cargo": self.perfil.cargo,
            "perfil-0-turno": self.perfil.turno,
        }

    def test_cambio_area_en_perfil_admin_revoca_token(self):
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
            self._datos_perfil(area=PerfilUsuario.Area.CALIDAD),
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.area, PerfilUsuario.Area.CALIDAD)
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_repetir_perfil_sin_cambios_mantiene_token(self):
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
            self._datos_perfil(),
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertTrue(self._sesion_sigue_vigente(token))

    def test_saveasnew_forjado_no_copia_perfil_a_cuenta_sin_perfil(self):
        historico = User.objects.create_user(
            "historico-sin-perfil-op06", password="Clave-historica-2026!",
        )
        datos = self._datos_perfil(area=PerfilUsuario.Area.CALIDAD)
        datos["usuario"] = historico.pk
        datos["_saveasnew"] = "1"
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
            datos,
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.assertFalse(PerfilUsuario.objects.filter(usuario=historico).exists())
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.area, PerfilUsuario.Area.SECADO)

    def test_fallo_al_revocar_revierte_cambio_admin(self):
        token = self._token_operador()
        with patch("usuarios.admin.revocar_sesiones", side_effect=RuntimeError("fallo inyectado")):
            with self.assertRaises(RuntimeError):
                self.client.post(
                    reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
                    self._datos_perfil(area=PerfilUsuario.Area.CALIDAD),
                )
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.area, PerfilUsuario.Area.SECADO)
        self.assertTrue(self._sesion_sigue_vigente(token))

    def test_cambio_permisos_en_user_admin_revoca_token(self):
        token = self._token_operador()
        permiso = Permission.objects.get(
            codename="produccion_orden_crear", content_type__app_label="usuarios",
        )
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]),
            self._datos_usuario(permisos=[permiso.pk]),
        )
        errores = None
        if respuesta.status_code != 302 and respuesta.context:
            errores = {
                "usuario": respuesta.context["adminform"].form.errors,
                "inlines": [
                    inline.formset.errors
                    for inline in respuesta.context["inline_admin_formsets"]
                ],
                "inlines_generales": [
                    inline.formset.non_form_errors()
                    for inline in respuesta.context["inline_admin_formsets"]
                ],
            }
        self.assertEqual(respuesta.status_code, 302, errores)
        self.assertTrue(self.usuario.user_permissions.filter(pk=permiso.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_password_en_user_admin_revoca_token(self):
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.usuario.pk]),
            {"usable_password": "true", "password1": "Clave-nueva-2026!",
             "password2": "Clave-nueva-2026!"},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-nueva-2026!"))
        self.assertTrue(self.usuario.perfil.debe_cambiar_password)
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_superusuario_cambia_su_propia_clave_sin_flag_temporal(self):
        PerfilUsuario.objects.create(
            usuario=self.actor, empresa=self.empresa,
            area=PerfilUsuario.Area.ADMINISTRACION,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        respuesta = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.actor.pk]),
            {"usable_password": "true", "password1": "Clave-propia-root-2026!",
             "password2": "Clave-propia-root-2026!"},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.actor.refresh_from_db()
        self.assertTrue(self.actor.check_password("Clave-propia-root-2026!"))
        self.assertFalse(self.actor.perfil.debe_cambiar_password)

    def test_desactivacion_en_user_admin_revoca_token(self):
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]),
            self._datos_usuario(activo=False),
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_active)
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_nombre_en_user_admin_no_revoca_token(self):
        token = self._token_operador()
        datos = self._datos_usuario()
        datos["first_name"] = "Nombre actualizado"
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]), datos,
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertTrue(self._sesion_sigue_vigente(token))

    def test_alta_password_admin_y_perfil_obliga_cambio(self):
        datos = {
            "username": "nuevo-admin-ui-op06",
            "usable_password": "true",
            "password1": "Clave-temporal-2026!",
            "password2": "Clave-temporal-2026!",
            "perfil-TOTAL_FORMS": "0",
            "perfil-INITIAL_FORMS": "0",
            "perfil-MIN_NUM_FORMS": "1",
            "perfil-MAX_NUM_FORMS": "1",
        }
        sin_perfil = self.client.post(
            reverse("admin:auth_user_add"),
            datos,
        )
        self.assertEqual(sin_perfil.status_code, 200, sin_perfil.status_code)
        self.assertFalse(User.objects.filter(username="nuevo-admin-ui-op06").exists())

        datos.update({
            "perfil-TOTAL_FORMS": "1",
            "perfil-0-empresa": self.empresa.pk,
            "perfil-0-area": PerfilUsuario.Area.SECADO,
            "perfil-0-nivel": PerfilUsuario.Nivel.TRABAJADOR,
            "perfil-0-cargo": "",
            "perfil-0-turno": "",
        })
        alta = self.client.post(reverse("admin:auth_user_add"), datos)
        self.assertEqual(alta.status_code, 302, alta.status_code)
        creado = User.objects.get(username="nuevo-admin-ui-op06")
        self.assertTrue(creado.check_password("Clave-temporal-2026!"))
        self.assertTrue(creado.perfil.debe_cambiar_password)

    def test_staff_sin_permiso_alta_perfil_no_crea_usuario_huerfano(self):
        actor = self._actor_area("staff-sin-alta-perfil-op06")
        actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="auth",
            codename__in=["add_user", "change_user"],
        ))
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:auth_user_add"),
            {"username": "sin-perfil-op06", "usable_password": "true",
             "password1": "Clave-temporal-2026!",
             "password2": "Clave-temporal-2026!"},
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.assertFalse(User.objects.filter(username="sin-perfil-op06").exists())

    def test_staff_sin_change_roles_no_cambia_area_por_perfil_admin(self):
        actor = self._actor_area("staff-op06")
        actor.user_permissions.add(Permission.objects.get(
            codename="change_perfilusuario", content_type__app_label="usuarios",
        ))
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
            self._datos_perfil(area=PerfilUsuario.Area.CALIDAD),
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.area, PerfilUsuario.Area.SECADO)
        self.assertEqual(SesionUsuario.objects.filter(usuario=self.usuario).count(), 0)

    def test_staff_con_change_roles_cambia_area_por_perfil_admin(self):
        token = self._token_operador()
        actor = self._actor_area("staff-delegado-op06")
        actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="usuarios",
            codename__in=["change_perfilusuario", "change_roles"],
        ))
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:usuarios_perfilusuario_change", args=[self.perfil.pk]),
            self._datos_perfil(area=PerfilUsuario.Area.CALIDAD),
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.perfil.refresh_from_db()
        self.assertEqual(self.perfil.area, PerfilUsuario.Area.CALIDAD)
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_staff_no_superusuario_no_concede_superusuario_por_user_admin(self):
        actor = self._actor_area("staff-usuarios-op06")
        actor.user_permissions.add(*Permission.objects.filter(
            content_type__app_label__in=["auth", "usuarios"],
            codename__in=["change_user", "change_roles"],
        ))
        self.client.force_login(actor)
        datos = self._datos_usuario()
        datos["is_staff"] = "on"
        datos["is_superuser"] = "on"
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]), datos,
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_superuser)
        self.assertFalse(self.usuario.is_staff)

    def test_staff_no_puede_autoasignar_change_roles(self):
        actor = self._actor_area("staff-sin-roles-op06")
        actor.user_permissions.add(Permission.objects.get(
            codename="change_user", content_type__app_label="auth",
        ))
        self.client.force_login(actor)
        permiso = Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        )
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]),
            self._datos_usuario(permisos=[permiso.pk]),
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.assertFalse(self.usuario.user_permissions.filter(pk=permiso.pk).exists())

    def test_staff_no_asigna_grupo_con_change_roles(self):
        actor = self._actor_area("staff-sin-grupos-op06")
        actor.user_permissions.add(Permission.objects.get(
            codename="change_user", content_type__app_label="auth",
        ))
        grupo = Group.objects.create(name="jefaturas-op06")
        grupo.permissions.add(Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        ))
        self.client.force_login(actor)
        datos = self._datos_usuario()
        datos["groups"] = [grupo.pk]
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]), datos,
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.assertFalse(self.usuario.groups.filter(pk=grupo.pk).exists())

    def test_staff_delega_permiso_industrial_de_su_area(self):
        actor = self._actor_area("jefe-secado-admin-op06", PerfilUsuario.Area.SECADO)
        actor.user_permissions.add(Permission.objects.get(
            codename="change_user", content_type__app_label="auth",
        ))
        permiso = Permission.objects.get(
            codename="secado_proceso_iniciar", content_type__app_label="usuarios",
        )
        token = self._token_operador()
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:auth_user_change", args=[self.usuario.pk]),
            self._datos_usuario(permisos=[permiso.pk]),
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertTrue(self.usuario.user_permissions.filter(pk=permiso.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_staff_no_restablece_password_superusuario(self):
        actor = self._actor_area("staff-reset-root-op06")
        actor.user_permissions.add(*Permission.objects.filter(
            codename__in=["change_user", "reset_password"],
            content_type__app_label__in=["auth", "usuarios"],
        ))
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.actor.pk]),
            {"usable_password": "true", "password1": "Clave-otra-root-2026!",
             "password2": "Clave-otra-root-2026!"},
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.actor.refresh_from_db()
        self.assertTrue(self.actor.check_password("Clave-root-2026!"))

    def test_staff_sin_reset_password_no_cambia_clave_en_admin(self):
        actor = self._actor_area("staff-sin-reset-op06")
        actor.user_permissions.add(Permission.objects.get(
            codename="change_user", content_type__app_label="auth",
        ))
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.usuario.pk]),
            {"usable_password": "true", "password1": "Clave-nueva-2026!",
             "password2": "Clave-nueva-2026!"},
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-operador-2026!"))

    def test_staff_con_reset_password_restablece_propia_area(self):
        actor = self._actor_area("staff-con-reset-op06", PerfilUsuario.Area.SECADO)
        actor.user_permissions.add(*Permission.objects.filter(
            codename__in=["change_user", "reset_password"],
            content_type__app_label__in=["auth", "usuarios"],
        ))
        token = self._token_operador()
        self.client.force_login(actor)
        respuesta = self.client.post(
            reverse("admin:auth_user_password_change", args=[self.usuario.pk]),
            {"usable_password": "true", "password1": "Clave-nueva-2026!",
             "password2": "Clave-nueva-2026!"},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password("Clave-nueva-2026!"))
        self.assertTrue(self.usuario.perfil.debe_cambiar_password)
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_cambio_permisos_grupo_admin_revoca_miembro(self):
        grupo = Group.objects.create(name="grupo-operador-op06")
        self.usuario.groups.add(grupo)
        token = self._token_operador()
        permiso = Permission.objects.get(
            codename="secado_proceso_iniciar", content_type__app_label="usuarios",
        )
        respuesta = self.client.post(
            reverse("admin:auth_group_change", args=[grupo.pk]),
            {"name": grupo.name, "permissions": [permiso.pk]},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertTrue(grupo.permissions.filter(pk=permiso.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_repetir_permisos_grupo_admin_no_revoca_miembro(self):
        grupo = Group.objects.create(name="grupo-sin-cambio-op06")
        self.usuario.groups.add(grupo)
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_group_change", args=[grupo.pk]),
            {"name": grupo.name, "permissions": []},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertTrue(self._sesion_sigue_vigente(token))

    def test_quitar_permiso_grupo_admin_revoca_miembro(self):
        grupo = Group.objects.create(name="grupo-quitar-permiso-op06")
        permiso = Permission.objects.get(
            codename="secado_proceso_iniciar", content_type__app_label="usuarios",
        )
        grupo.permissions.add(permiso)
        self.usuario.groups.add(grupo)
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_group_change", args=[grupo.pk]),
            {"name": grupo.name, "permissions": []},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertFalse(grupo.permissions.filter(pk=permiso.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_staff_no_edita_permisos_del_grupo(self):
        actor = self._actor_area("staff-grupos-op06")
        actor.user_permissions.add(Permission.objects.get(
            codename="change_group", content_type__app_label="auth",
        ))
        grupo = Group.objects.create(name="grupo-protegido-op06")
        self.client.force_login(actor)
        permiso = Permission.objects.get(
            codename="change_roles", content_type__app_label="usuarios",
        )
        respuesta = self.client.post(
            reverse("admin:auth_group_change", args=[grupo.pk]),
            {"name": grupo.name, "permissions": [permiso.pk]},
        )
        self.assertEqual(respuesta.status_code, 403, respuesta.status_code)
        self.assertFalse(grupo.permissions.filter(pk=permiso.pk).exists())

    def test_borrar_grupo_admin_revoca_miembro(self):
        grupo = Group.objects.create(name="grupo-eliminar-op06")
        self.usuario.groups.add(grupo)
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_group_delete", args=[grupo.pk]),
            {"post": "yes"},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertFalse(Group.objects.filter(pk=grupo.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))

    def test_borrar_grupo_masivo_admin_revoca_miembro(self):
        grupo = Group.objects.create(name="grupo-eliminar-masivo-op06")
        self.usuario.groups.add(grupo)
        token = self._token_operador()
        respuesta = self.client.post(
            reverse("admin:auth_group_changelist"),
            {"action": "delete_selected", "_selected_action": [grupo.pk],
             "select_across": "0", "post": "yes"},
        )
        self.assertEqual(respuesta.status_code, 302, respuesta.status_code)
        self.assertFalse(Group.objects.filter(pk=grupo.pk).exists())
        self.assertFalse(self._sesion_sigue_vigente(token))
