from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto
from produccion.models import Lote
from usuarios.models import PerfilUsuario, Rol
from .models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, SalidaProceso
from .servicios import transicionar_ejecucion


class ProcesosIndustrialesTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("produccion", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario, area=PerfilUsuario.Area.SECADO, rol=Rol.PRODUCCION
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)
        mandante = Mandante.objects.create(nombre="CCAA")
        self.leche = Producto.objects.create(nombre="Leche", familia="otro", mandante=mandante)
        self.crema = Producto.objects.create(nombre="Crema", familia="crema", mandante=mandante)
        self.descremada = Producto.objects.create(nombre="Descremada", familia="otro", mandante=mandante)
        self.lote_origen = self._lote("ORIGEN", self.leche)
        self.lote_crema = self._lote("CREMA", self.crema)
        self.lote_descremada = self._lote("DESCREMADA", self.descremada)
        self.equipo = Equipo.objects.create(
            codigo="descremadora", nombre="Descremadora", tipo=Equipo.Tipo.OTRO
        )
        self.proceso = Proceso.objects.create(codigo="descremacion", nombre="Descremación")
        self.etapa = EtapaProceso.objects.create(
            proceso=self.proceso, codigo="separar", nombre="Separar crema",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-001", etapa=self.etapa, equipo=self.equipo,
            responsable=self.usuario,
        )

    @staticmethod
    def _lote(codigo, producto):
        return Lote.objects.create(
            codigo_lote=codigo, producto=producto, fecha=date(2026, 8, 4),
            estado=Lote.Estado.EN_PROCESO,
        )

    def test_una_ejecucion_admite_una_entrada_y_dos_coproductos(self):
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_origen, cantidad=Decimal("1000")
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO, cantidad=Decimal("100"),
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_descremada,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL, cantidad=Decimal("890"),
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion, naturaleza=SalidaProceso.Naturaleza.MERMA,
            cantidad=Decimal("10"), motivo="Pérdida operacional medida",
        )

        self.assertEqual(self.ejecucion.salidas.count(), 3)
        self.assertEqual(sum(s.cantidad for s in self.ejecucion.salidas.all()), Decimal("1000"))

    def test_transicion_exige_entrada_equipo_y_registra_evento(self):
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_origen, cantidad=1000
        )
        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.id,
            estado_nuevo=EjecucionProceso.Estado.PREPARACION,
            usuario=self.usuario,
        )
        resultado = transicionar_ejecucion(
            ejecucion_id=self.ejecucion.id,
            estado_nuevo=EjecucionProceso.Estado.EJECUCION,
            usuario=self.usuario,
        )

        self.assertEqual(resultado.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertIsNotNone(resultado.inicio)
        self.assertEqual(resultado.eventos.count(), 2)

    def test_trazabilidad_hacia_atras_encuentra_lote_origen(self):
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_origen, cantidad=1000
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.lote_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO, cantidad=100,
        )

        respuesta = self.cliente.get(
            f"/api/procesos/trazabilidad/lotes/{self.lote_crema.id}/?direccion=atras"
        )

        self.assertEqual(respuesta.status_code, 200)
        ids = {nodo["id"] for nodo in respuesta.json()["nodos"]}
        self.assertIn(self.lote_origen.id, ids)

    def test_api_no_permite_borrado_fisico_de_ejecucion(self):
        respuesta = self.cliente.delete(f"/api/procesos/ejecuciones/{self.ejecucion.id}/")
        self.assertEqual(respuesta.status_code, 405)
