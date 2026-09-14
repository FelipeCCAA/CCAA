from django.contrib.auth.models import User
from django.test import TestCase

from usuarios.models import AreaDePerfil, Empresa, PerfilUsuario, Rol, Sucursal

from .models import Notificacion
from .servicios import _notificar_area


class NotificacionesPorAreaTests(TestCase):
    def setUp(self):
        # Estas relaciones solo satisfacen campos históricos obligatorios. La
        # selección operacional de destinatarios no las consulta.
        self.empresa_legacy = Empresa.objects.create(
            rut="NOTIF-LEGACY-1", nombre="Compatibilidad histórica"
        )
        self.sucursal_legacy = Sucursal.objects.create(
            empresa=self.empresa_legacy,
            codigo="LEGACY-1",
            nombre="Registro histórico",
        )

    def _perfil(self, username, *, area, activo=True, empresa=None, sucursal=None):
        usuario = User.objects.create_user(username, is_active=activo)
        perfil = PerfilUsuario.objects.create(
            usuario=usuario,
            empresa=empresa or self.empresa_legacy,
            sucursal=sucursal or self.sucursal_legacy,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            area=area,
            rol=Rol.CALIDAD if area == PerfilUsuario.Area.CALIDAD else Rol.LECTURA,
        )
        return usuario, perfil

    def test_entrega_segun_responsabilidad_de_area_y_trabajo_real(self):
        principal, _ = self._perfil(
            "calidad-principal", area=PerfilUsuario.Area.CALIDAD
        )
        adicional, perfil_adicional = self._perfil(
            "calidad-adicional", area=PerfilUsuario.Area.BODEGA
        )
        AreaDePerfil.objects.create(
            perfil=perfil_adicional, area=PerfilUsuario.Area.CALIDAD
        )
        otra_area, _ = self._perfil(
            "operador-bodega", area=PerfilUsuario.Area.BODEGA
        )
        inactivo, _ = self._perfil(
            "calidad-inactiva", area=PerfilUsuario.Area.CALIDAD, activo=False
        )

        # Incluso si los campos históricos difieren, el área autorizada sigue
        # siendo la única dimensión funcional de entrega.
        otra_empresa_legacy = Empresa.objects.create(
            rut="NOTIF-LEGACY-2", nombre="Otro dato histórico"
        )
        otra_sucursal_legacy = Sucursal.objects.create(
            empresa=otra_empresa_legacy,
            codigo="LEGACY-2",
            nombre="Otro registro histórico",
        )
        misma_area, _ = self._perfil(
            "calidad-misma-responsabilidad",
            area=PerfilUsuario.Area.CALIDAD,
            empresa=otra_empresa_legacy,
            sucursal=otra_sucursal_legacy,
        )

        _notificar_area(
            PerfilUsuario.Area.CALIDAD,
            tipo="prueba_handoff",
            titulo="Trabajo nuevo",
            mensaje="Revisar lote",
            documento_tipo="procesos.SalidaProceso",
            documento_id=10,
            accion_url="/calidad",
        )

        destinatarios = set(
            Notificacion.objects.values_list("destinatario_id", flat=True)
        )
        self.assertEqual(destinatarios, {principal.pk, adicional.pk, misma_area.pk})
        self.assertNotIn(otra_area.pk, destinatarios)
        self.assertNotIn(inactivo.pk, destinatarios)
        aviso = Notificacion.objects.get(destinatario=principal)
        self.assertEqual(aviso.documento_tipo, "procesos.SalidaProceso")
        self.assertEqual(aviso.documento_id, 10)
        self.assertEqual(aviso.accion_url, "/calidad")
