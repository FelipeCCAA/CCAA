from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone

from usuarios.models import PerfilUsuario, Rol

from .models import Despacho
from .pruebas_base import EscenarioProductoTerminado
from .servicios import autorizar_despacho, ejecutar_despacho, ingresar_pallet


class HojaDeCargaTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        self.dar_permiso("despacho_crear")
        self.dar_permiso("despacho_autorizar")
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)

    def crear(self, pallets=None):
        return self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": pallets or [self.pallet.pk],
        }, format="json")

    def cancelar(self, despacho_id, motivo="Cliente reprogramó"):
        return self.api.post(
            f"/api/inventario/despachos/{despacho_id}/cancelar/", {"motivo": motivo}, format="json",
        )

    # ---- un pallet, una hoja activa

    def test_un_pallet_en_otra_hoja_en_borrador_se_rechaza_nombrandola(self):
        primera = self.crear()
        self.assertEqual(primera.status_code, 201, primera.data)
        segunda = self.crear()
        self.assertEqual(segunda.status_code, 400)
        self.assertIn("PAL-PT", str(segunda.data))
        self.assertIn(primera.data["numero"], str(segunda.data))

    def test_un_pallet_en_una_hoja_autorizada_tambien_se_rechaza(self):
        primera = self.crear()
        autorizar_despacho(Despacho.objects.get(pk=primera.data["id"]), self.usuario)
        self.assertEqual(self.crear().status_code, 400)

    def test_tras_cancelar_el_pallet_vuelve_a_poder_cargarse(self):
        primera = self.crear()
        self.assertEqual(self.cancelar(primera.data["id"]).status_code, 200)
        self.assertEqual(self.crear().status_code, 201)

    # ---- cancelar

    def test_cancelar_deja_motivo_quien_y_cuando(self):
        creado = self.crear().data
        respuesta = self.cancelar(creado["id"], "  Camión no llegó  ")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        despacho = Despacho.objects.get(pk=creado["id"])
        self.assertEqual(despacho.estado, Despacho.Estado.CANCELADO)
        self.assertEqual(despacho.motivo_cancelacion, "Camión no llegó")
        self.assertEqual(despacho.cancelado_por, self.usuario)
        self.assertIsNotNone(despacho.cancelado_en)

    def test_cancelar_sin_motivo_se_rechaza(self):
        creado = self.crear().data
        respuesta = self.cancelar(creado["id"], "   ")
        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Despacho.objects.get(pk=creado["id"]).estado, Despacho.Estado.BORRADOR)

    def test_un_despacho_despachado_no_se_cancela(self):
        despacho = Despacho.objects.get(pk=self.crear().data["id"])
        autorizar_despacho(despacho, self.usuario)
        ejecutar_despacho(despacho, self.usuario)
        respuesta = self.cancelar(despacho.pk)
        self.assertEqual(respuesta.status_code, 400)
        despacho.refresh_from_db()
        self.assertEqual(despacho.estado, Despacho.Estado.DESPACHADO)

    def test_cancelar_exige_el_permiso_de_autorizar(self):
        creado = self.crear().data
        solo_crea = User.objects.create_user("despacho-solo-crea")
        PerfilUsuario.objects.create(
            usuario=solo_crea, empresa=self.empresa, sucursal=self.planta,
            rol=Rol.OPERARIO, area=PerfilUsuario.Area.DESPACHO,
        )
        self.dar_permiso("despacho_crear", solo_crea)
        self.api.force_authenticate(solo_crea)
        self.assertEqual(self.cancelar(creado["id"]).status_code, 403)

    # ---- hojas vigentes y detalle legible

    def test_vigentes_trae_borradores_autorizados_y_despachados_hoy(self):
        borrador = self.crear().data
        otro = self.crear_pallet("PAL-PT-2")
        ingresar_pallet(otro, self.ubicacion, self.usuario)
        despachado = Despacho.objects.get(pk=self.crear([otro.pk]).data["id"])
        autorizar_despacho(despachado, self.usuario)
        ejecutar_despacho(despachado, self.usuario)
        ayer = Despacho.objects.create(
            sucursal=self.planta, numero="VIEJO-1", cliente=self.cliente,
            creado_por=self.usuario, estado=Despacho.Estado.DESPACHADO,
            despachado_en=timezone.now() - timedelta(days=2),
        )
        respuesta = self.api.get("/api/inventario/despachos/?vigentes=1")
        filas = respuesta.data["results"] if isinstance(respuesta.data, dict) else respuesta.data
        ids = {fila["id"] for fila in filas}
        self.assertIn(borrador["id"], ids)
        self.assertIn(despachado.pk, ids)
        self.assertNotIn(ayer.pk, ids)

    def test_el_detalle_dice_lote_y_ubicacion_del_pallet(self):
        detalle = self.crear().data["detalles"][0]
        self.assertEqual(detalle["lote_codigo"], "L-PT")
        self.assertEqual(detalle["ubicacion_codigo"], "A-01")
