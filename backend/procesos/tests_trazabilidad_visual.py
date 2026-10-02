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

    def test_cada_enlace_lleva_su_propia_cantidad_y_ejecucion(self):
        # Un lote que recibe precondensado de dos ejecuciones distintas: cada
        # enlace tiene que cuantificar su propia entrada/salida y nombrar su
        # propia corrida, no la última que el primer bucle haya recorrido.
        mandante = Mandante.objects.create(nombre="Dos ejecuciones")
        producto = Producto.objects.create(
            nombre="Producto compartido", familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        origen_a = Lote.objects.create(
            codigo_lote="DOS-ORIGEN-A", producto=producto, fecha=date(2026, 9, 20),
            kg_producidos=Decimal("100"),
        )
        origen_b = Lote.objects.create(
            codigo_lote="DOS-ORIGEN-B", producto=producto, fecha=date(2026, 9, 20),
            kg_producidos=Decimal("50"),
        )
        destino = Lote.objects.create(
            codigo_lote="DOS-DESTINO", producto=producto, fecha=date(2026, 9, 20),
            kg_producidos=Decimal("100"),
        )
        proceso = Proceso.objects.create(codigo="dos-ej", nombre="Dos ejecuciones")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="transformar-2", nombre="Transformación 2",
            tipo=EtapaProceso.Tipo.OTRO, orden=1,
        )
        ejecucion_1 = EjecucionProceso.objects.create(
            codigo="EJ-DOS-1", etapa=etapa, responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion_1, lote=origen_a,
            cantidad=Decimal("100"), unidad="kg",
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion_1, lote=destino,
            cantidad=Decimal("60"), unidad="kg",
        )
        ejecucion_2 = EjecucionProceso.objects.create(
            codigo="EJ-DOS-2", etapa=etapa, responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion_2, lote=origen_b,
            cantidad=Decimal("50"), unidad="kg",
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion_2, lote=destino,
            cantidad=Decimal("40"), unidad="kg",
        )

        respuesta = self.cliente.get(
            "/api/procesos/trazabilidad/lotes/DOS-DESTINO/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        enlaces = {
            enlace["origen"]: enlace for enlace in respuesta.data["enlaces"]
        }
        self.assertEqual(len(enlaces), 2)

        enlace_a = enlaces[origen_a.pk]
        self.assertEqual(enlace_a["ejecucion"]["codigo"], "EJ-DOS-1")
        self.assertEqual(enlace_a["entrada"]["cantidad"], Decimal("100.000"))
        self.assertEqual(enlace_a["salida"]["cantidad"], Decimal("60.000"))

        enlace_b = enlaces[origen_b.pk]
        self.assertEqual(enlace_b["ejecucion"]["codigo"], "EJ-DOS-2")
        self.assertEqual(enlace_b["entrada"]["cantidad"], Decimal("50.000"))
        self.assertEqual(enlace_b["salida"]["cantidad"], Decimal("40.000"))

    def test_hacia_adelante_cada_enlace_lleva_su_propia_cantidad_y_ejecucion(self):
        # El mismo defecto que arriba, mirado hacia adelante: un lote que
        # alimenta dos ejecuciones distintas tiene que cuantificar cada rama
        # con su propia entrada y salida, no la última que el bucle recorrió.
        mandante = Mandante.objects.create(nombre="Un origen, dos corridas")
        producto = Producto.objects.create(
            nombre="Producto compartido hacia adelante", familia=Producto.Familia.POLVO,
            mandante=mandante,
        )
        origen = Lote.objects.create(
            codigo_lote="ADEL-ORIGEN", producto=producto, fecha=date(2026, 9, 21),
            kg_producidos=Decimal("150"),
        )
        destino_a = Lote.objects.create(
            codigo_lote="ADEL-DESTINO-A", producto=producto, fecha=date(2026, 9, 21),
            kg_producidos=Decimal("70"),
        )
        destino_b = Lote.objects.create(
            codigo_lote="ADEL-DESTINO-B", producto=producto, fecha=date(2026, 9, 21),
            kg_producidos=Decimal("45"),
        )
        proceso = Proceso.objects.create(codigo="adel", nombre="Hacia adelante")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="transformar-adel", nombre="Transformación adelante",
            tipo=EtapaProceso.Tipo.OTRO, orden=1,
        )
        ejecucion_1 = EjecucionProceso.objects.create(
            codigo="EJ-ADEL-1", etapa=etapa, responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion_1, lote=origen,
            cantidad=Decimal("90"), unidad="kg",
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion_1, lote=destino_a,
            cantidad=Decimal("70"), unidad="kg",
        )
        ejecucion_2 = EjecucionProceso.objects.create(
            codigo="EJ-ADEL-2", etapa=etapa, responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=ejecucion_2, lote=origen,
            cantidad=Decimal("60"), unidad="kg",
        )
        SalidaProceso.objects.create(
            ejecucion=ejecucion_2, lote=destino_b,
            cantidad=Decimal("45"), unidad="kg",
        )

        respuesta = self.cliente.get(
            "/api/procesos/trazabilidad/lotes/ADEL-ORIGEN/?direccion=adelante"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        enlaces = {
            enlace["destino"]: enlace for enlace in respuesta.data["enlaces"]
        }
        self.assertEqual(len(enlaces), 2)

        enlace_a = enlaces[destino_a.pk]
        self.assertEqual(enlace_a["ejecucion"]["codigo"], "EJ-ADEL-1")
        self.assertEqual(enlace_a["entrada"]["cantidad"], Decimal("90.000"))
        self.assertEqual(enlace_a["salida"]["cantidad"], Decimal("70.000"))

        enlace_b = enlaces[destino_b.pk]
        self.assertEqual(enlace_b["ejecucion"]["codigo"], "EJ-ADEL-2")
        self.assertEqual(enlace_b["entrada"]["cantidad"], Decimal("60.000"))
        self.assertEqual(enlace_b["salida"]["cantidad"], Decimal("45.000"))
