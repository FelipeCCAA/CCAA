from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto
from produccion.models import Lote
from usuarios.models import PerfilUsuario

from .models import (
    EjecucionProceso, EntradaProceso, EventoProceso, EtapaProceso, Proceso,
    SalidaProceso,
)


class TrazabilidadVisualTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user("jefatura-traza", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.CALIDAD,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        mandante = Mandante.objects.create(nombre="Trazabilidad visual")
        producto = Producto.objects.create(
            nombre="Producto trazable", familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        self.origen = Lote.objects.create(
            codigo_lote="TZV-ORIGEN", producto=producto, fecha=date(2026, 9, 11),
            kg_producidos=Decimal("100"),
        )
        self.destino = Lote.objects.create(
            codigo_lote="TZV-DESTINO", producto=producto, fecha=date(2026, 9, 11),
            kg_producidos=Decimal("80"),
        )
        proceso = Proceso.objects.create(codigo="tzv", nombre="Proceso trazable")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="transformar", nombre="Transformación",
            tipo=EtapaProceso.Tipo.OTRO, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-TZV-1", etapa=etapa, responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.origen,
            cantidad=Decimal("100"), unidad="kg",
        )
        self.salida = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, lote=self.destino,
            cantidad=Decimal("80"), unidad="kg",
        )
        SalidaProceso.objects.create(
            ejecucion=self.ejecucion, naturaleza=SalidaProceso.Naturaleza.MERMA,
            cantidad=Decimal("20"), unidad="kg", motivo="Pérdida declarada",
        )
        EventoProceso.objects.create(
            ejecucion=self.ejecucion, usuario=self.usuario,
            tipo="cambio_estado", estado_anterior="borrador",
            estado_nuevo="preparacion", motivo="Inicio autorizado",
        )

    def test_genealogia_cuantifica_entrada_salida_y_transformacion(self):
        respuesta = self.cliente.get(
            "/api/procesos/trazabilidad/lotes/TZV-DESTINO/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        enlace = respuesta.data["enlaces"][0]
        self.assertEqual(enlace["ejecucion"]["codigo"], "EJ-TZV-1")
        self.assertEqual(enlace["entrada"]["cantidad"], Decimal("100.000"))
        self.assertEqual(enlace["salida"]["cantidad"], Decimal("80.000"))
        self.assertEqual(enlace["origen"], self.origen.pk)
        self.assertEqual(enlace["destino"], self.destino.pk)

    def test_acepta_corrida_o_salida_como_punto_de_entrada(self):
        por_corrida = self.cliente.get(
            "/api/procesos/trazabilidad/ejecucion/EJ-TZV-1/"
        )
        por_salida = self.cliente.get(
            f"/api/procesos/trazabilidad/salida/{self.salida.pk}/"
        )

        self.assertEqual(por_corrida.status_code, 200, por_corrida.data)
        self.assertEqual(por_salida.status_code, 200, por_salida.data)
        self.assertEqual(por_corrida.data["raiz"], self.destino.pk)
        self.assertEqual(por_corrida.data["foco"]["tipo"], "ejecucion")
        self.assertEqual(por_salida.data["foco"]["tipo"], "salida")

    def test_timeline_usa_hechos_persistidos_y_responsables_reales(self):
        respuesta = self.cliente.get(
            "/api/procesos/trazabilidad/lotes/TZV-DESTINO/"
        )

        categorias = {hecho["categoria"] for hecho in respuesta.data["timeline"]}
        self.assertTrue({"proceso", "entrada", "salida", "estado"} <= categorias)
        hecho_estado = next(
            hecho for hecho in respuesta.data["timeline"]
            if hecho["categoria"] == "estado"
        )
        self.assertEqual(hecho_estado["responsable"], "jefatura-traza")
        self.assertEqual(hecho_estado["detalle"], "Inicio autorizado")
        self.assertIn("ubicacion_actual", respuesta.data)

    def test_tipo_invalido_no_expone_un_error_tecnico(self):
        respuesta = self.cliente.get(
            "/api/procesos/trazabilidad/desconocido/cualquier-cosa/"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Tipo de referencia inválido", respuesta.data["error"])
