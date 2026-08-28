from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from estandarizacion.models import ValeEstandarizacion
from maestros.models import Equipo, Mandante, Producto, Silo
from procesos.models import EjecucionProceso, SalidaProceso
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Lote


class FlujoIntegradoApiTests(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.000.100-1", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PL", nombre="Planta"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Cliente", codigo_cliente="cliente-flujo"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, codigo="LEP", nombre="Leche en polvo"
        )
        self.origen = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 1", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.destino = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 2", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="EGRON-1", nombre="Torre Egron 1",
            tipo=Equipo.Tipo.TORRE,
        )
        self.vale = ValeEstandarizacion.objects.create(
            codigo="VE-100", fecha=date(2026, 8, 13), producto=self.producto,
            rc_objetivo="0.4000", volumen="20000", silo_entera=self.origen,
            silo_destino=self.destino, entera_grasa="3.60", entera_sng="8.60",
            descremada_grasa="0.05", descremada_sng="8.90",
            litros_entera="20000", litros_descremada="0",
            grasa_real="3.44", sng_real="8.61",
            estado=ValeEstandarizacion.Estado.LIBERADO,
        )
        usuario = User.objects.create_user("produccion-flujo", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, rol=Rol.PRODUCCION, area=PerfilUsuario.Area.SECADO,
            empresa=self.empresa, sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)

    def _abrir(self):
        return self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "CCAA6225LEP-01",
                "producto": self.producto.pk,
                "vale": self.vale.pk,
                "litros_estandarizados": "12000",
                "fecha": "2026-08-13",
                "linea": "E1",
                "equipo": self.equipo.pk,
            },
            format="json",
        )

    def test_produccion_ve_solo_vales_liberados_con_saldo(self):
        respuesta = self.cliente.get(
            "/api/produccion/lotes/vales-disponibles/",
            {"producto": self.producto.pk},
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data[0]["codigo"], self.vale.codigo)
        self.assertEqual(respuesta.data[0]["silo_destino_codigo"], "SILO 2")
        self.assertEqual(respuesta.data[0]["litros_disponibles"], Decimal("20000"))

    def test_opciones_inicio_agrupa_entrada_y_maquinas_en_una_llamada(self):
        respuesta = self.cliente.get(
            "/api/produccion/lotes/opciones-inicio/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["entradas"][0]["codigo"], self.vale.codigo)
        equipo = next(item for item in respuesta.data["equipos"] if item["id"] == self.equipo.id)
        self.assertTrue(equipo["habilitado"])

    def test_abre_lote_y_ejecucion_sin_elegir_silo(self):
        respuesta = self._abrir()

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        lote = Lote.objects.get()
        self.assertEqual(lote.vale, self.vale)
        self.assertEqual(lote.equipo, self.equipo)
        self.assertEqual(lote.ejecucion.equipo, self.equipo)
        self.assertEqual(respuesta.data["ejecucion_codigo"], f"EJ-PROD-{lote.pk}")
        movimiento = MovimientoSilo.objects.get(
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE, origen_id=lote.pk
        )
        self.assertEqual(movimiento.silo, self.destino)

        procesos = self.cliente.get("/api/procesos/ejecuciones/")
        ejecucion = next(
            item for item in procesos.data["results"]
            if item["codigo"] == f"EJ-PROD-{lote.pk}"
        )
        self.assertEqual(ejecucion["lote_codigo"], lote.codigo_lote)
        self.assertEqual(ejecucion["entradas"][0]["silo_codigo"], "SILO 2")

    def test_rechaza_el_contrato_antiguo_que_pedia_silo(self):
        respuesta = self.cliente.post(
            "/api/produccion/lotes/",
            {
                "codigo_lote": "ANTIGUO", "producto": self.producto.pk,
                "fecha": "2026-08-13",
                "asignaciones": [{"silo": self.origen.pk, "litros": 1000}],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no selecciona silos", str(respuesta.data))

        # Y rechaza **sin dejar el lote creado**: la guarda corre antes de
        # `super().create()`. Un lote a medias parece completo, y nadie vuelve
        # a completar lo que ya existe.
        self.assertFalse(Lote.objects.filter(codigo_lote="ANTIGUO").exists())

    def test_cerrar_produccion_completa_la_salida_del_proceso(self):
        lote_id = self._abrir().data["id"]

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote_id}/",
            {"estado": "producido", "kg_producidos": "1500"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        ejecucion = EjecucionProceso.objects.get(lote_produccion__id=lote_id)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        self.assertEqual(SalidaProceso.objects.get(ejecucion=ejecucion).lote_id, lote_id)

    def test_procesos_muestra_recepcion_estandarizacion_y_produccion(self):
        recepcion = Recepcion.objects.create(
            sucursal=self.planta, fecha=date(2026, 8, 13), guia="G-100",
            tipo_leche=Recepcion.TipoLeche.ENTERA, litros="20000",
            silo=self.origen, estado=Recepcion.Estado.DESCARGADA,
        )
        antes = timezone.now() - timedelta(minutes=10)
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros="20000",
            fecha_hora=antes, origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
            origen_id=recepcion.pk,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.SALIDA, litros="20000",
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=self.vale.pk,
        )
        lote_id = self._abrir().data["id"]

        respuesta = self.cliente.get(
            f"/api/procesos/trazabilidad/lotes/{lote_id}/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        flujo = respuesta.data["flujo"]
        self.assertEqual(flujo["recepciones"][0]["guia"], "G-100")
        self.assertEqual(flujo["estandarizacion"]["vale_codigo"], "VE-100")
        self.assertEqual(flujo["produccion"]["equipo"], "Torre Egron 1")
