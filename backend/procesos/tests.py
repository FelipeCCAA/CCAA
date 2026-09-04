from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto, Silo
from calidad.models import LiberacionProceso
from produccion.models import Lote
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal
from .models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, RutaProducto, SalidaProceso
from .servicios import (
    destino_salida_de_ruta, etapa_para_producto, genealogia_lote, preparar_continuacion,
    transicionar_ejecucion,
)


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
            codigo="descremadora", nombre="Descremadora", tipo=Equipo.Tipo.DESCREMADORA
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

    def test_destino_final_usa_codigo_estructurado_y_no_texto_libre(self):
        ruta = RutaProducto.objects.create(
            producto=self.leche,
            proceso=self.proceso,
            destino="Enviar a inventario (texto historico)",
            destino_final=RutaProducto.DestinoFinal.DESPACHO_DIRECTO,
        )

        destino = destino_salida_de_ruta(
            producto=self.leche,
            sucursal=ruta.sucursal,
            etapa=self.etapa,
            ruta=ruta,
        )

        self.assertEqual(destino, SalidaProceso.Destino.DESPACHO_DIRECTO)

    def test_bandeja_operativa_excluye_ejecuciones_terminadas(self):
        EjecucionProceso.objects.create(
            codigo="EJ-CERRADA", etapa=self.etapa, equipo=self.equipo,
            responsable=self.usuario, estado=EjecucionProceso.Estado.CERRADA,
        )

        respuesta = self.cliente.get("/api/procesos/ejecuciones/operativas/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual([item["codigo"] for item in respuesta.data], ["EJ-001"])
        self.assertEqual(respuesta.data[0]["equipo_id"], self.equipo.pk)
        self.assertEqual(respuesta.data[0]["equipo_nombre"], self.equipo.nombre)
        self.assertEqual(respuesta.data[0]["version"], self.ejecucion.version)
        self.assertIn("preparacion", respuesta.data[0]["acciones_permitidas"])

    def test_resumen_operacional_cuenta_estados_y_material_liberado(self):
        self.ejecucion.estado = EjecucionProceso.Estado.EJECUCION
        self.ejecucion.save(update_fields=["estado"])
        silo = Silo.objects.create(codigo="TK-RES", capacidad_l=1000)
        salida = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, silo=silo, producto=self.descremada,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal("250"), unidad="L",
        )
        LiberacionProceso.objects.create(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
        )
        espera = EjecucionProceso.objects.create(
            codigo="EJ-CALIDAD", etapa=self.etapa, responsable=self.usuario,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )

        respuesta = self.cliente.get(
            "/api/procesos/ejecuciones/resumen-operacional/"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["procesos_activos"], 1)
        self.assertEqual(respuesta.data["esperando_calidad"], 1)
        self.assertEqual(respuesta.data["equipos_ocupados"], 1)
        self.assertEqual(respuesta.data["materiales_listos"], 1)
        self.assertEqual(respuesta.data["bloqueos"], 0)
        self.assertIsNotNone(espera.pk)

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

    def test_preparacion_reserva_el_equipo_para_una_sola_ejecucion(self):
        otra = EjecucionProceso.objects.create(
            codigo="EJ-002", etapa=self.etapa, equipo=self.equipo,
            responsable=self.usuario,
        )
        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk,
            estado_nuevo=EjecucionProceso.Estado.PREPARACION,
            usuario=self.usuario,
        )

        with self.assertRaisesMessage(ValidationError, "ocupado por EJ-001"):
            transicionar_ejecucion(
                ejecucion_id=otra.pk,
                estado_nuevo=EjecucionProceso.Estado.PREPARACION,
                usuario=self.usuario,
            )

    def test_cinco_procesos_pueden_reservar_equipos_distintos(self):
        configuraciones = [
            ("est", EtapaProceso.Tipo.ESTANDARIZACION, Equipo.Tipo.OTRO),
            ("des", EtapaProceso.Tipo.DESCREMACION, Equipo.Tipo.DESCREMADORA),
            ("eva", EtapaProceso.Tipo.EVAPORACION, Equipo.Tipo.EVAPORADOR),
            ("man", EtapaProceso.Tipo.MANTEQUILLA, Equipo.Tipo.LINEA),
            ("sec", EtapaProceso.Tipo.SECADO, Equipo.Tipo.TORRE),
        ]
        ejecuciones = []
        for indice, (codigo, tipo_etapa, tipo_equipo) in enumerate(configuraciones, 1):
            proceso = Proceso.objects.create(
                codigo=f"sim-{codigo}", nombre=f"Proceso simultaneo {codigo}"
            )
            etapa = EtapaProceso.objects.create(
                proceso=proceso, codigo=f"sim-{codigo}", nombre=codigo,
                tipo=tipo_etapa, orden=1,
            )
            equipo = Equipo.objects.create(
                codigo=f"EQ-SIM-{indice}", nombre=f"Equipo simultaneo {indice}",
                tipo=tipo_equipo,
            )
            ejecucion = EjecucionProceso.objects.create(
                codigo=f"EJ-SIM-{indice}", etapa=etapa, equipo=equipo,
                responsable=self.usuario,
            )
            ejecuciones.append(transicionar_ejecucion(
                ejecucion_id=ejecucion.pk,
                estado_nuevo=EjecucionProceso.Estado.PREPARACION,
                usuario=self.usuario,
            ))

        self.assertEqual(
            {ejecucion.estado for ejecucion in ejecuciones},
            {EjecucionProceso.Estado.PREPARACION},
        )
        self.assertEqual(len({ejecucion.equipo_id for ejecucion in ejecuciones}), 5)

    def test_la_base_impide_dos_ocupaciones_del_mismo_equipo(self):
        self.ejecucion.estado = EjecucionProceso.Estado.PAUSADA
        self.ejecucion.save(update_fields=["estado"])

        with self.assertRaises(IntegrityError), transaction.atomic():
            EjecucionProceso.objects.create(
                codigo="EJ-DUPLICADA", etapa=self.etapa, equipo=self.equipo,
                responsable=self.usuario,
                estado=EjecucionProceso.Estado.BLOQUEADA,
            )

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

    def test_un_intermedio_no_puede_destinarse_a_inventario_terminado(self):
        salida = SalidaProceso(
            ejecucion=self.ejecucion,
            lote=self.lote_descremada,
            cantidad=Decimal("100"),
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.INVENTARIO,
        )

        with self.assertRaisesMessage(ValidationError, "Solo un producto terminado"):
            salida.full_clean()

    def test_crema_de_descremacion_admite_estandarizacion_o_siguiente_proceso(self):
        salida = SalidaProceso(
            ejecucion=self.ejecucion,
            lote=self.lote_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            cantidad=Decimal("100"),
        )

        self.assertIn(SalidaProceso.Destino.ESTANDARIZACION, salida.destinos_permitidos())
        self.assertIn(SalidaProceso.Destino.SIGUIENTE_PROCESO, salida.destinos_permitidos())
        self.assertNotIn(SalidaProceso.Destino.INVENTARIO, salida.destinos_permitidos())

    def test_reproceso_exige_motivo_explicito(self):
        entrada = EntradaProceso(
            ejecucion=self.ejecucion,
            lote=self.lote_origen,
            tipo=EntradaProceso.Tipo.REPROCESO,
            cantidad=Decimal("10"),
        )

        with self.assertRaisesMessage(ValidationError, "debe indicar por qué"):
            entrada.full_clean()

    def test_la_etapa_se_resuelve_desde_la_ruta_del_producto(self):
        ruta = Proceso.objects.create(codigo="ruta-leche-test", nombre="Ruta específica")
        etapa_ruta = EtapaProceso.objects.create(
            proceso=ruta, codigo="secar", nombre="Secado específico",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        RutaProducto.objects.create(
            sucursal=self.ejecucion.sucursal,
            producto=self.leche,
            proceso=ruta,
        )

        encontrada = etapa_para_producto(
            producto=self.leche,
            sucursal=self.ejecucion.sucursal,
            tipo=EtapaProceso.Tipo.SECADO,
        )

        self.assertEqual(encontrada, etapa_ruta)

    def test_una_etapa_de_otro_proceso_no_es_fallback_de_escritura(self):
        encontrada = etapa_para_producto(
            producto=self.leche,
            sucursal=self.ejecucion.sucursal,
            tipo=EtapaProceso.Tipo.DESCREMACION,
        )

        self.assertIsNone(encontrada)

    def test_diagnostico_informa_producto_elaborable_sin_ruta(self):
        producto = Producto.objects.create(
            nombre="Polvo sin ruta", familia=Producto.Familia.POLVO,
            categoria=Producto.Categoria.LECHE_POLVO,
            mandante=self.leche.mandante,
        )

        respuesta = self.cliente.get("/api/procesos/rutas-producto/diagnostico/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        hallazgo = next(
            item for item in respuesta.data["productos"]
            if item["producto"] == producto.pk
            and item["sucursal"] == self.ejecucion.sucursal_id
        )
        self.assertFalse(hallazgo["configurada"])
        self.assertGreaterEqual(respuesta.data["faltantes"], 1)

    def test_diagnostico_informa_inconsistencias_productivas(self):
        EjecucionProceso.objects.create(
            codigo="EJ-SIN-ORIGEN", etapa=self.etapa, equipo=self.equipo,
            responsable=self.usuario, estado=EjecucionProceso.Estado.EJECUCION,
        )
        EjecucionProceso.objects.create(
            codigo="EJ-CIERRE-INCOMPLETO", etapa=self.etapa,
            responsable=self.usuario, estado=EjecucionProceso.Estado.CERRADA,
        )

        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.cliente.get(
                "/api/procesos/rutas-producto/diagnostico/"
            )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        integridad = respuesta.data["integridad"]
        categorias = {item["codigo"]: item for item in integridad["categorias"]}
        self.assertFalse(integridad["completa"])
        self.assertIn("ejecucion_sin_entrada", categorias)
        self.assertIn("cierre_sin_salida", categorias)
        self.assertIn("estado_temporal_inconsistente", categorias)
        self.assertNotIn("equipo_ocupado_multiples_veces", categorias)
        self.assertLessEqual(len(consultas), 20)

    def test_una_continuacion_no_puede_saltarse_una_etapa(self):
        EtapaProceso.objects.create(
            proceso=self.proceso, codigo="control", nombre="Control intermedio",
            tipo=EtapaProceso.Tipo.OTRO, orden=2,
        )
        etapa_tres = EtapaProceso.objects.create(
            proceso=self.proceso, codigo="secar", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=3,
        )
        silo = Silo.objects.create(
            sucursal=self.ejecucion.sucursal, codigo="INT-TEST",
            tipo=Silo.Tipo.SILO, capacidad_l=Decimal("5000"),
        )
        salida = SalidaProceso.objects.create(
            ejecucion=self.ejecucion, silo=silo, cantidad=Decimal("1000"), unidad="L",
        )

        with self.assertRaisesMessage(ValidationError, "no se pueden saltar procesos"):
            preparar_continuacion(
                salida_id=salida.pk, etapa_id=etapa_tres.pk,
                equipo_id=self.equipo.pk, cantidad=100, usuario=self.usuario,
            )

    def test_continuar_a_secado_mueve_el_lote_a_la_torre_sin_perder_origen(self):
        from calidad.models import LiberacionProceso

        proceso = Proceso.objects.create(codigo="polvo-lineal", nombre="Polvo lineal")
        evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="ev", nombre="Evaporación",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1,
        )
        secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        torre = Equipo.objects.create(
            sucursal=self.ejecucion.sucursal, codigo="torre-lineal",
            nombre="Torre lineal", tipo=Equipo.Tipo.TORRE,
        )
        silo = Silo.objects.create(
            sucursal=self.ejecucion.sucursal, codigo="CONC-LINEAL",
            tipo=Silo.Tipo.SILO, capacidad_l=5000,
        )
        origen = EjecucionProceso.objects.create(
            codigo="EJ-EV-LINEAL", etapa=evaporacion,
            sucursal=self.ejecucion.sucursal, equipo=self.equipo,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=origen, lote=self.lote_origen, silo=silo,
            cantidad=500, unidad="L",
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
        )
        LiberacionProceso.objects.create(
            salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
        )

        ejecucion = preparar_continuacion(
            salida_id=salida.pk, etapa_id=secado.pk,
            equipo_id=torre.pk, cantidad=500, usuario=self.usuario,
        )

        self.lote_origen.refresh_from_db()
        self.assertEqual(self.lote_origen.ejecucion, ejecucion)
        self.assertEqual(self.lote_origen.equipo, torre)
        self.assertEqual(ejecucion.entradas.get().salida_origen, salida)
        self.assertEqual(ejecucion.corrida_secado.lote, self.lote_origen)
        self.assertEqual(ejecucion.corrida_secado.orden, self.lote_origen.orden)


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

    def test_el_flujo_completo_con_vale_conserva_su_contrato(self):
        from estandarizacion.models import ValeEstandarizacion
        from maestros.models import Silo

        silo = Silo.objects.create(
            codigo="S-TZ",
            tipo=Silo.Tipo.SILO,
            capacidad_l=10000,
        )
        vale = ValeEstandarizacion.objects.create(
            codigo="V-TZ",
            fecha=date(2026, 8, 1),
            producto=self.polvo.producto,
            silo_destino=silo,
            rc_objetivo=Decimal("0.40"),
            volumen=1000,
            estado=ValeEstandarizacion.Estado.LIBERADO,
        )
        self.polvo.vale = vale
        self.polvo.save(update_fields=["vale"])

        respuesta = self._consultar(self.polvo.pk)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["flujo"]["estandarizacion"]["vale_codigo"], "V-TZ")
        self.assertEqual(respuesta.data["flujo"]["produccion"]["lote_codigo"], "CCAA-TZ-POLVO")
        self.assertEqual(respuesta.data["flujo"]["pallets"], [])

    def test_el_ancho_del_grafo_no_agrega_consultas(self):
        # Raíz y todos sus orígenes se resuelven en dos SQL: una para la
        # raíz y una para las relaciones del nivel. Antes se consultaba de
        # nuevo cada lote de origen, incluso al alcanzar el límite.
        with self.assertNumQueries(2):
            datos = genealogia_lote(
                self.polvo.pk, "atras", profundidad_maxima=1
            )

        self.assertEqual(len(datos["nodos"]), 3)

    def test_un_lote_que_no_existe_responde_404_con_su_motivo(self):
        respuesta = self._consultar("CCAA-NO-EXISTE")

        self.assertEqual(respuesta.status_code, 404)
        self.assertIn("CCAA-NO-EXISTE", str(respuesta.data))


class BalanceDeMasaTests(TestCase):
    """
    No puede salir más masa de la que entró.

    La trampa está en las unidades: una evaporación entra en litros y sale en
    kilos. Ahí no hay exceso, hay una transformación, y sin un factor de
    conversión declarado cualquier comparación sería inventada. Por eso solo se
    comparan las unidades que aparecen en los **dos** lados.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("operador-bal", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        mandante = Mandante.objects.create(nombre="CCAA balance")
        producto = Producto.objects.create(
            nombre="Producto balance", familia="polvo", mandante=mandante
        )
        self.lote = Lote.objects.create(
            codigo_lote="BAL-1", producto=producto, fecha=date(2026, 8, 1)
        )
        self.otro = Lote.objects.create(
            codigo_lote="BAL-2", producto=producto, fecha=date(2026, 8, 1)
        )
        # Un tercer lote para las mezclas: `EntradaProceso` es único por
        # (ejecución, lote, tipo), así que «varios orígenes» significa lotes
        # distintos y no la misma entrada repetida.
        self.tercero = Lote.objects.create(
            codigo_lote="BAL-3", producto=producto, fecha=date(2026, 8, 1)
        )

        proceso = Proceso.objects.create(codigo="bal", nombre="Balance")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="e1", nombre="Etapa",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-BAL-1", etapa=etapa
        )

    def _entrada(self, cantidad, unidad="kg", lote=None):
        return EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=lote or self.lote, cantidad=cantidad,
            unidad=unidad,
        )

    def _salida(self, cantidad, unidad="kg", **extra):
        datos = {
            "ejecucion": self.ejecucion.id,
            "lote": self.otro.id,
            "cantidad": str(cantidad),
            "unidad": unidad,
            "naturaleza": "principal",
        }
        datos.update(extra)

        return self.cliente.post("/api/procesos/salidas/", datos, format="json")

    # ------------------------------------------------- la misma unidad

    def test_no_sale_mas_de_lo_que_entro(self):
        self._entrada(1000)

        respuesta = self._salida(1001)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("más de lo que entró", str(respuesta.data))

    def test_lo_que_entro_si_puede_salir_entero(self):
        self._entrada(1000)

        self.assertEqual(self._salida(1000).status_code, 201)

    def test_las_salidas_se_acumulan(self):
        """Tres salidas de 400 no caben en 1.000 aunque cada una quepa sola."""
        self._entrada(1000)

        self.assertEqual(self._salida(400).status_code, 201)
        self.assertEqual(self._salida(400).status_code, 201)

        respuesta = self._salida(400)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("quedan 200", str(respuesta.data))

    def test_la_merma_cuenta_como_salida(self):
        """
        La pérdida también es masa que se fue. Excluirla dejaría el hueco por
        donde se cuadra cualquier diferencia.
        """
        self._entrada(1000)
        self._salida(900)

        respuesta = self._salida(
            200, lote=None, naturaleza="merma", motivo="Barrido de línea"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("más de lo que entró", str(respuesta.data))

    def test_varias_entradas_suman(self):
        """Una mezcla tiene varios orígenes y todos aportan."""
        self._entrada(600)
        self._entrada(600, lote=self.tercero)

        self.assertEqual(self._salida(1200).status_code, 201)

    # ------------------------------------------------ unidades distintas

    def test_una_transformacion_de_unidad_no_se_bloquea(self):
        """
        Evaporación: entran 20.000 litros y salen 5.000 kilos. No hay exceso,
        hay una transformación — y sin factor de conversión declarado,
        compararlas sería inventar.
        """
        self._entrada(20000, unidad="L")

        self.assertEqual(self._salida(5000, unidad="kg").status_code, 201)

    def test_pero_dentro_de_la_misma_unidad_si_se_controla(self):
        """Aunque haya una transformación en curso, lo que entra y sale en la
        misma unidad sigue teniendo que cuadrar."""
        self._entrada(20000, unidad="L")
        self._entrada(100, unidad="kg", lote=self.tercero)

        self.assertEqual(self._salida(5000, unidad="kg").status_code, 400)

    def test_la_unidad_no_distingue_mayusculas(self):
        """«Kg» y «kg» son la misma unidad; tratarlas como distintas abriría
        la puerta a saltarse el control con un cambio de caja."""
        self._entrada(1000, unidad="kg")

        self.assertEqual(self._salida(1500, unidad="KG").status_code, 400)

    # ----------------------------------------------------------- balance

    def test_el_balance_viaja_agrupado_por_unidad(self):
        self._entrada(20000, unidad="L")
        self._salida(5000, unidad="kg")

        respuesta = self.cliente.get(
            f"/api/procesos/ejecuciones/{self.ejecucion.id}/"
        )
        balance = {b["unidad"]: b for b in respuesta.data["balance"]}

        self.assertEqual(balance["l"]["entro"], 20000)
        self.assertEqual(balance["kg"]["salio"], 5000)
        # Ninguna aparece en los dos lados: no son comparables.
        self.assertFalse(balance["l"]["comparable"])
        self.assertFalse(balance["kg"]["comparable"])


class EquipoHabilitadoPorAseoTests(TestCase):
    """
    Reglas de planta 3 y 15 (`docs/REGLAS_DE_PLANTA.md` §5).

    Un equipo no puede estar produciendo y en CIP a la vez —es física antes que
    informática, hay soda circulando por dentro— y un aseo observado deja el
    equipo no habilitado hasta que otro lo reemplace (§18.5 del flujo de
    fábrica).

    Se prueban **las dos direcciones**: con una sola, la regla se cumple o no
    según cuál de las dos acciones llegue primero.
    """

    def setUp(self):
        from maestros.models import Mandante, Producto

        self.empresa = Empresa.objects.create(rut="76.333.444-5", nombre="Empresa aseo")
        self.sucursal = Sucursal.objects.create(
            empresa=self.empresa, codigo="ASEO", nombre="Planta aseo"
        )
        self.usuario = User.objects.create_user("operador-aseo", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.ADMIN,
            empresa=self.empresa,
            sucursal=self.sucursal,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        self.equipo = Equipo.objects.create(
            sucursal=self.sucursal,
            codigo="torre-aseo", nombre="Torre aseo", tipo=Equipo.Tipo.TORRE
        )

        mandante = Mandante.objects.create(empresa=self.empresa, nombre="CCAA aseo")
        producto = Producto.objects.create(
            nombre="Producto aseo", familia="polvo", mandante=mandante
        )
        lote = Lote.objects.create(
            sucursal=self.sucursal,
            codigo_lote="ASEO-1", producto=producto, fecha=date(2026, 8, 1)
        )

        proceso = Proceso.objects.create(codigo="aseo-p", nombre="Proceso aseo")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="e", nombre="Etapa",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            sucursal=self.sucursal,
            codigo="EJ-ASEO-1", etapa=etapa, equipo=self.equipo,
            responsable=self.usuario,
        )
        EntradaProceso.objects.create(
            ejecucion=self.ejecucion, lote=lote, cantidad=100
        )

    def _cip(self, estado, hace_horas=1):
        from datetime import timedelta

        from django.utils import timezone

        from inventario.models import CicloCIP

        return CicloCIP.objects.create(
            sucursal=self.sucursal,
            area=PerfilUsuario.Area.SECADO, equipo=self.equipo,
            inicio=timezone.now() - timedelta(hours=hace_horas), estado=estado,
        )

    def _arrancar(self):
        """Lleva la ejecución hasta intentar entrar en producción."""
        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk,
            estado_nuevo=EjecucionProceso.Estado.PREPARACION,
            usuario=self.usuario,
        )
        return transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk,
            estado_nuevo=EjecucionProceso.Estado.EJECUCION,
            usuario=self.usuario,
        )

    # ------------------------------------------- el CIP bloquea producir

    def test_sin_cip_el_equipo_arranca(self):
        self.assertEqual(
            self._arrancar().estado, EjecucionProceso.Estado.EJECUCION
        )

    def test_un_equipo_en_cip_no_puede_producir(self):
        from inventario.models import CicloCIP

        self._cip(CicloCIP.Estado.EN_CURSO)

        with self.assertRaisesMessage(ValidationError, "está en CIP"):
            self._arrancar()

    def test_un_aseo_completado_no_estorba(self):
        from inventario.models import CicloCIP

        self._cip(CicloCIP.Estado.COMPLETADO)

        self.assertEqual(
            self._arrancar().estado, EjecucionProceso.Estado.EJECUCION
        )

    def test_un_aseo_observado_avisa_pero_no_bloquea(self):
        """El observado queda trazado como advertencia y la corrida continúa."""
        from inventario.models import CicloCIP

        self._cip(CicloCIP.Estado.OBSERVADO)

        ejecucion = self._arrancar()

        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertIn(
            "Advertencia no bloqueante de aseo",
            ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.EJECUCION).motivo,
        )

    def test_un_aseo_conforme_posterior_rehabilita(self):
        """El observado bloquea hasta que otro lo reemplace, no para siempre."""
        from inventario.models import CicloCIP

        self._cip(CicloCIP.Estado.OBSERVADO, hace_horas=5)
        self._cip(CicloCIP.Estado.COMPLETADO, hace_horas=1)

        self.assertEqual(
            self._arrancar().estado, EjecucionProceso.Estado.EJECUCION
        )

    def test_un_cip_programado_no_bloquea(self):
        """
        Todavía no ocurrió. Tratar un aseo futuro como resultado detendría la
        producción por algo que aún no pasó.
        """
        from inventario.models import CicloCIP

        self._cip(CicloCIP.Estado.PROGRAMADO)

        self.assertEqual(
            self._arrancar().estado, EjecucionProceso.Estado.EJECUCION
        )

    # ------------------------------------------- producir bloquea el CIP

    def test_no_se_asea_un_equipo_que_esta_produciendo(self):
        from django.utils import timezone

        from inventario.models import CicloCIP

        self._arrancar()

        respuesta = self.cliente.post(
            "/api/inventario/cip/",
            {
                "area": PerfilUsuario.Area.SECADO,
                "equipo": self.equipo.id,
                "inicio": timezone.now().isoformat(),
                "estado": CicloCIP.Estado.EN_CURSO,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("está produciendo", str(respuesta.data))

    def test_programar_un_cip_futuro_si_se_puede_mientras_produce(self):
        """Programar no es asear: la máquina se sigue lavando después."""
        from django.utils import timezone

        from inventario.models import CicloCIP

        self._arrancar()

        respuesta = self.cliente.post(
            "/api/inventario/cip/",
            {
                "area": PerfilUsuario.Area.SECADO,
                "equipo": self.equipo.id,
                "inicio": timezone.now().isoformat(),
                "estado": CicloCIP.Estado.PROGRAMADO,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)


class ReworkAutorizadoTests(TestCase):
    """
    Regla de planta № 7: no se agrega rework sin autorización.

    Un reproceso es producto que ya falló una vez y vuelve a entrar a la
    cadena. Meterlo sin que Calidad lo haya evaluado arrastra el defecto al
    lote nuevo — y con la trazabilidad hacia adelante, a todos los que salgan
    de él.
    """

    def setUp(self):
        self.usuario = User.objects.create_user("operador-rw", password="x")
        PerfilUsuario.objects.create(
            usuario=self.usuario,
            area=PerfilUsuario.Area.SECADO,
            nivel=PerfilUsuario.Nivel.ADMIN,
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

        mandante = Mandante.objects.create(nombre="CCAA rework")
        producto = Producto.objects.create(
            nombre="Polvo rework", familia="polvo", mandante=mandante
        )

        def lote(codigo):
            return Lote.objects.create(
                codigo_lote=codigo, producto=producto, fecha=date(2026, 8, 1)
            )

        self.rework = lote("RW-REWORK")
        self.normal = lote("RW-NORMAL")

        proceso = Proceso.objects.create(codigo="rw", nombre="Proceso rework")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="e", nombre="Etapa",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-RW-1", etapa=etapa
        )

    def _liberacion(self, lote, estado):
        from calidad.models import Liberacion

        return Liberacion.objects.create(lote=lote, estado=estado)

    def _entrada(self, lote, tipo):
        motivo = "Mezcla controlada autorizada" if tipo == "reproceso" else ""
        return self.cliente.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": self.ejecucion.id,
                "lote": lote.id,
                "tipo": tipo,
                "cantidad": "100",
                "motivo": motivo,
            },
            format="json",
        )

    def test_un_reproceso_sin_liberacion_no_entra(self):
        """
        La ausencia de liberación no es autorización: un lote sin expediente
        tramitado no es uno aprobado, es uno que nadie miró.
        """
        respuesta = self._entrada(self.rework, "reproceso")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("no está liberado", str(respuesta.data))

    def test_un_reproceso_pendiente_tampoco(self):
        from calidad.models import Liberacion

        self._liberacion(self.rework, Liberacion.Estado.PENDIENTE)

        self.assertEqual(self._entrada(self.rework, "reproceso").status_code, 400)

    def test_un_reproceso_rechazado_tampoco(self):
        from calidad.models import Liberacion

        self._liberacion(self.rework, Liberacion.Estado.RECHAZADO)

        self.assertEqual(self._entrada(self.rework, "reproceso").status_code, 400)

    def test_un_reproceso_liberado_si_entra(self):
        from calidad.models import Liberacion

        self._liberacion(self.rework, Liberacion.Estado.LIBERADO)

        respuesta = self._entrada(self.rework, "reproceso")

        self.assertEqual(respuesta.status_code, 201, respuesta.data)

    def test_la_concesion_tambien_autoriza(self):
        """Es Calidad diciendo «úsalo bajo estas condiciones», que es
        precisamente una autorización."""
        from calidad.models import Liberacion

        self._liberacion(self.rework, Liberacion.Estado.CONCESION)

        self.assertEqual(
            self._entrada(self.rework, "reproceso").status_code, 201
        )

    def test_una_entrada_principal_no_exige_liberacion(self):
        """
        La regla es del reproceso. Exigirla a toda entrada detendría la
        producción normal: la leche que entra al evaporador no se libera, se
        libera lo que sale.
        """
        self.assertEqual(self._entrada(self.normal, "principal").status_code, 201)

    def test_autorizacion_rework_limita_la_cantidad_aprobada(self):
        from procesos.models import AutorizacionReproceso

        AutorizacionReproceso.objects.create(
            lote=self.rework,
            origen=AutorizacionReproceso.Origen.RECHAZO,
            estado=AutorizacionReproceso.Estado.APROBADO,
            cantidad_kg=Decimal("150"),
            motivo="Recuperable bajo mezcla controlada",
        )
        primera = self.cliente.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": self.ejecucion.id, "lote": self.rework.id,
                "tipo": "reproceso", "cantidad": "100",
                "motivo": "Primera mezcla controlada",
            },
            format="json",
        )
        self.assertEqual(primera.status_code, 201, primera.data)

        otra = EjecucionProceso.objects.create(
            codigo="EJ-RW-2", etapa=self.ejecucion.etapa,
        )
        respuesta = self.cliente.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": otra.id, "lote": self.rework.id,
                "tipo": "reproceso", "cantidad": "60",
                "motivo": "Segunda mezcla controlada",
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("Calidad autorizó 150", str(respuesta.data))

        opciones = self.cliente.get("/api/procesos/entradas/opciones-rework/")
        self.assertEqual(opciones.status_code, 200, opciones.data)
        self.assertEqual(opciones.data[0]["lote_codigo"], self.rework.codigo_lote)
        self.assertEqual(opciones.data[0]["cantidad_disponible_kg"], Decimal("50"))
