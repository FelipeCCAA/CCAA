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


class TrazabilidadPorCodigoTests(TestCase):
    """
    La genealogía se consulta por el **código de lote**.

    El id es de la base de datos y nadie en planta lo conoce: quien pregunta de
    dónde salió un saco tiene en la mano un `CCAA…-01`, no un 47. Pedirle el id
    volvía la pantalla inservible para quien la necesita.
    """

    def setUp(self):
        from maestros.models import Mandante, Producto
        from produccion.models import Lote

        from .models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, SalidaProceso

        self.usuario = User.objects.create_user("operador-tz", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        mandante = Mandante.objects.create(nombre="CCAA trazabilidad")
        producto = Producto.objects.create(
            nombre="Leche en polvo tz", familia="polvo", mandante=mandante
        )

        def lote(codigo):
            return Lote.objects.create(
                codigo_lote=codigo, producto=producto, fecha=date(2026, 8, 1)
            )

        # Dos lotes de leche entran al secado y sale uno de polvo.
        self.leche_a = lote("CCAA-TZ-A")
        self.leche_b = lote("CCAA-TZ-B")
        self.polvo = lote("CCAA-TZ-POLVO")

        proceso = Proceso.objects.create(codigo="tz", nombre="Secado tz")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="secado", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        ejecucion = EjecucionProceso.objects.create(codigo="EJ-TZ-1", etapa=etapa)

        for origen in (self.leche_a, self.leche_b):
            EntradaProceso.objects.create(
                ejecucion=ejecucion, lote=origen, cantidad=1000
            )

        SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=self.polvo, cantidad=120
        )

    def _consultar(self, referencia, direccion="atras"):
        return self.cliente.get(
            f"/api/procesos/trazabilidad/lotes/{referencia}/",
            {"direccion": direccion},
        )

    def test_se_consulta_por_codigo_de_lote(self):
        respuesta = self._consultar("CCAA-TZ-POLVO")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        codigos = {n["codigo"] for n in respuesta.data["nodos"]}
        self.assertEqual(codigos, {"CCAA-TZ-POLVO", "CCAA-TZ-A", "CCAA-TZ-B"})

    def test_el_id_sigue_funcionando(self):
        """Lo usan los enlaces internos; solo la persona necesita el código."""
        respuesta = self._consultar(self.polvo.pk)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["raiz"], self.polvo.pk)

    def test_devuelve_la_raiz_para_saber_desde_donde_dibujar(self):
        respuesta = self._consultar("CCAA-TZ-POLVO")

        self.assertEqual(respuesta.data["raiz"], self.polvo.pk)

    def test_los_enlaces_dicen_que_salio_de_que(self):
        """Sin ellos son lotes sueltos: la relación es la trazabilidad."""
        respuesta = self._consultar("CCAA-TZ-POLVO")

        enlaces = {(e["origen"], e["destino"]) for e in respuesta.data["enlaces"]}
        self.assertEqual(
            enlaces,
            {(self.leche_a.pk, self.polvo.pk), (self.leche_b.pk, self.polvo.pk)},
        )

    def test_hacia_adelante_encuentra_la_descendencia(self):
        respuesta = self._consultar("CCAA-TZ-A", direccion="adelante")

        codigos = {n["codigo"] for n in respuesta.data["nodos"]}
        self.assertIn("CCAA-TZ-POLVO", codigos)

    def test_un_lote_que_no_existe_responde_404_con_su_motivo(self):
        respuesta = self._consultar("CCAA-NO-EXISTE")

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("CCAA-NO-EXISTE", str(respuesta.data))
