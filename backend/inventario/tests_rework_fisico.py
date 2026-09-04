from datetime import date
from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from procesos.models import EjecucionProceso, EtapaProceso, Proceso
from produccion.models import Lote
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Bodega, MovimientoRework, Ubicacion, UnidadRework


class FlujoFisicoReworkTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.040.904-2", nombre="Planta rework")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="RW", nombre="Planta Rework"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, codigo_cliente="RW", nombre="Mandante Rework"
        )
        producto = Producto.objects.create(
            mandante=mandante, nombre="Leche en polvo recuperable",
            familia=Producto.Familia.POLVO,
        )
        self.lote = Lote.objects.create(
            sucursal=self.sucursal, codigo_lote="LOT-RW-FISICO",
            producto=producto, fecha=date(2026, 9, 4),
            kg_producidos=Decimal("100"), estado=Lote.Estado.PRODUCIDO,
        )
        proceso = Proceso.objects.create(codigo="rw-fis", nombre="Secado rework")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec-rw", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            sucursal=self.sucursal, codigo="EJ-RW-FISICO", etapa=etapa,
        )
        self.calidad = self._usuario("calidad-rw", PerfilUsuario.Area.CALIDAD, Rol.CALIDAD)
        self.bodega = self._usuario("bodega-rw", PerfilUsuario.Area.BODEGA, Rol.OPERARIO)
        self.secado = self._usuario("secado-rw", PerfilUsuario.Area.SECADO, Rol.PRODUCCION)
        bodega = Bodega.objects.create(
            sucursal=self.sucursal, codigo="B-DISP", nombre="Bodega disponible"
        )
        self.destino = Ubicacion.objects.create(
            bodega=bodega, codigo="RW-01", tipo=Ubicacion.Tipo.DISPONIBLE
        )

    def _usuario(self, username, area, rol):
        usuario = User.objects.create_user(username)
        PerfilUsuario.objects.create(
            usuario=usuario, empresa=self.empresa, sucursal=self.sucursal,
            area=area, rol=rol,
        )
        return usuario

    @staticmethod
    def _cliente(usuario):
        cliente = APIClient()
        cliente.force_authenticate(usuario)
        return cliente

    def _aprobar(self):
        return self._cliente(self.calidad).post(
            f"/api/calidad/expedientes/{self.lote.pk}/rework/",
            {
                "estado": "aprobado", "origen": "saco_danado",
                "cantidad_kg": "60", "motivo": "Sacos segregados e identificados",
            },
            format="json",
        )

    def test_calidad_aprueba_pero_bodega_habilita_la_existencia(self):
        respuesta = self._aprobar()
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        unidad = UnidadRework.objects.get()
        self.assertEqual(unidad.estado, UnidadRework.Estado.PENDIENTE_UBICACION)
        self.assertEqual(unidad.ubicacion.tipo, Ubicacion.Tipo.CUARENTENA)

        antes = self._cliente(self.secado).get("/api/procesos/entradas/opciones-rework/")
        self.assertEqual(antes.status_code, 200, antes.data)
        self.assertEqual(antes.data, [])

        denegada = self._cliente(self.calidad).post(
            f"/api/inventario/rework/{unidad.pk}/habilitar/",
            {"destino": self.destino.pk, "operacion_id": str(uuid4())}, format="json",
        )
        self.assertEqual(denegada.status_code, 403)

        operacion = str(uuid4())
        habilitada = self._cliente(self.bodega).post(
            f"/api/inventario/rework/{unidad.pk}/habilitar/",
            {"destino": self.destino.pk, "operacion_id": operacion}, format="json",
        )
        self.assertEqual(habilitada.status_code, 200, habilitada.data)
        self.assertEqual(habilitada.data["estado"], "disponible")
        repetida = self._cliente(self.bodega).post(
            f"/api/inventario/rework/{unidad.pk}/habilitar/",
            {"destino": self.destino.pk, "operacion_id": operacion}, format="json",
        )
        self.assertEqual(repetida.status_code, 200, repetida.data)
        self.assertEqual(
            MovimientoRework.objects.filter(tipo=MovimientoRework.Tipo.HABILITACION).count(), 1
        )

        despues = self._cliente(self.secado).get("/api/procesos/entradas/opciones-rework/")
        self.assertEqual(despues.status_code, 200, despues.data)
        self.assertEqual(despues.data[0]["unidad_rework_id"], unidad.pk)
        self.assertTrue(despues.data[0]["trazabilidad_fisica"])

    def test_consumo_es_atomico_e_idempotente(self):
        self.assertEqual(self._aprobar().status_code, 200)
        unidad = UnidadRework.objects.get()
        self.assertEqual(
            self._cliente(self.bodega).post(
                f"/api/inventario/rework/{unidad.pk}/habilitar/",
                {"destino": self.destino.pk, "operacion_id": str(uuid4())}, format="json",
            ).status_code,
            200,
        )
        operacion = str(uuid4())
        payload = {
            "lote": self.lote.pk, "unidad_rework": unidad.pk,
            "cantidad": "25", "motivo": "Mezcla controlada en secado",
            "operacion_id": operacion,
        }
        cliente = self._cliente(self.secado)
        primera = cliente.post(
            f"/api/procesos/ejecuciones/{self.ejecucion.pk}/incorporar-rework/",
            payload, format="json",
        )
        repetida = cliente.post(
            f"/api/procesos/ejecuciones/{self.ejecucion.pk}/incorporar-rework/",
            payload, format="json",
        )
        self.assertEqual(primera.status_code, 201, primera.data)
        self.assertEqual(repetida.status_code, 201, repetida.data)
        unidad.refresh_from_db()
        self.assertEqual(unidad.cantidad_disponible_kg, Decimal("35"))
        self.assertEqual(
            MovimientoRework.objects.filter(tipo=MovimientoRework.Tipo.CONSUMO).count(), 1
        )

        exceso = cliente.post(
            f"/api/procesos/ejecuciones/{self.ejecucion.pk}/incorporar-rework/",
            {**payload, "cantidad": "36", "operacion_id": str(uuid4())}, format="json",
        )
        self.assertEqual(exceso.status_code, 400)
        unidad.refresh_from_db()
        self.assertEqual(unidad.cantidad_disponible_kg, Decimal("35"))
