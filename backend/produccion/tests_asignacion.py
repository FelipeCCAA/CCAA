"""
Pruebas de la asignación de leche a un lote y de su trazabilidad.

Aquí empieza la trazabilidad real: qué leche, de qué estanques, entró a este
lote. Lo que protegen estas pruebas es la honestidad de esa respuesta —que el
libro mayor registre lo que se tomó y no lo que un cálculo supone, y que las
recepciones se devuelvan con las cantidades FIFO efectivamente atribuidas. Los
datos históricos sin atribución se identifican expresamente como inferidos.
"""

from datetime import date, datetime
from datetime import timezone as tz

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from calidad.models import Liberacion
from maestros.models import (
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
    Silo,
)
from recepcion.models import AtribucionRecepcion, MovimientoSilo, Recepcion
from usuarios.models import PerfilUsuario, Rol

from .models import Lote


def instante(dia, hora=12):
    return datetime(2026, 7, dia, hora, tzinfo=tz.utc)


class BaseAsignacion(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")

        self.leche = Producto.objects.create(
            nombre="Leche fresca",
            familia=Producto.Familia.LIQUIDO,
            naturaleza=Producto.Naturaleza.MATERIA_PRIMA,
            unidad_base="L",
            mandante=self.mandante,
        )
        self.polvo = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )

        # 1 kg de polvo ← 8 L de leche
        receta = Receta.objects.create(
            producto=self.polvo, vigente_desde=date(2026, 1, 1)
        )
        RecetaComponente.objects.create(
            receta=receta, producto=self.leche, cantidad=8, unidad="L"
        )

        self.silo_a = Silo.objects.create(
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )
        self.silo_b = Silo.objects.create(
            codigo="SILO 2", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )

        self.cliente = self._cliente(Rol.PRODUCCION)

        self.lote = Lote.objects.create(
            codigo_lote="CCAA6197",
            producto=self.polvo,
            fecha=date(2026, 7, 16),
            kg_producidos=12000,  # receta: 96.000 L
        )

    def _cliente(self, rol):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _asignar(self, lineas, cliente=None):
        return (cliente or self.cliente).post(
            f"/api/produccion/lotes/{self.lote.id}/asignacion/",
            {"asignaciones": lineas},
            format="json",
        )

    def _estado(self):
        return self.cliente.get(
            f"/api/produccion/lotes/{self.lote.id}/asignacion/"
        ).json()


class AsignarLecheTests(BaseAsignacion):
    def test_un_lote_puede_mezclar_leche_de_varios_silos(self):
        """Es lo normal cuando ningún estanque alcanza solo."""
        respuesta = self._asignar(
            [
                {"silo": self.silo_a.id, "litros": 60000},
                {"silo": self.silo_b.id, "litros": 40000},
            ]
        )

        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.json()
        self.assertEqual(len(datos["lineas"]), 2)
        self.assertEqual(datos["asignado"], 100000)

    def test_cada_linea_es_un_asiento_del_libro_mayor(self):
        self._asignar(
            [
                {"silo": self.silo_a.id, "litros": 60000},
                {"silo": self.silo_b.id, "litros": 40000},
            ]
        )

        salidas = MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA,
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=self.lote.id,
        )

        self.assertEqual(salidas.count(), 2)
        self.assertEqual({s.silo_id for s in salidas}, {self.silo_a.id, self.silo_b.id})

    def test_los_litros_los_declara_produccion_no_la_receta(self):
        """
        El libro mayor registra lo que salió del estanque. Guardar la
        estimación de la receta haría que el saldo dejara de ser un saldo.
        """
        self._asignar([{"silo": self.silo_a.id, "litros": 91000}])

        datos = self._estado()

        self.assertEqual(datos["asignado"], 91000, "lo declarado")
        self.assertEqual(datos["teorico"], 96000, "lo que la receta esperaba")

    def test_se_pueden_agregar_lineas_despues(self):
        self._asignar([{"silo": self.silo_a.id, "litros": 60000}])
        self._asignar([{"silo": self.silo_b.id, "litros": 30000}])

        self.assertEqual(self._estado()["asignado"], 90000)

    def test_el_saldo_del_silo_baja_con_la_asignacion(self):
        MovimientoSilo.objects.create(
            silo=self.silo_a,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=150000,
            fecha_hora=instante(15),
        )

        self._asignar([{"silo": self.silo_a.id, "litros": 60000}])

        ocupacion = self.cliente.get("/api/recepcion/ocupacion/").json()
        del_silo = next(
            s for s in ocupacion["silos"] if s["silo_id"] == self.silo_a.id
        )

        self.assertEqual(del_silo["litros"], 90000)

    def test_sin_lineas_no_se_asigna(self):
        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{self.lote.id}/asignacion/", {}, format="json"
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_litros_no_positivos_se_rechazan(self):
        respuesta = self._asignar([{"silo": self.silo_a.id, "litros": 0}])

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(MovimientoSilo.objects.exists())

    def test_una_linea_incompleta_no_deja_nada_a_medias(self):
        """La transacción es todo o nada: media asignación miente igual."""
        respuesta = self._asignar(
            [
                {"silo": self.silo_a.id, "litros": 50000},
                {"silo": self.silo_b.id},
            ]
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertFalse(MovimientoSilo.objects.exists())

    def test_calidad_no_asigna_leche(self):
        respuesta = self._asignar(
            [{"silo": self.silo_a.id, "litros": 1000}], self._cliente(Rol.CALIDAD)
        )

        self.assertEqual(respuesta.status_code, 403)


class RendimientoRealTests(BaseAsignacion):
    """
    Lo asignado y lo teórico se guardan aparte a propósito: su diferencia es
    el rendimiento real, que antes no se medía en ninguna parte.
    """

    def test_informa_la_diferencia_entre_lo_asignado_y_lo_teorico(self):
        self._asignar([{"silo": self.silo_a.id, "litros": 104000}])

        datos = self._estado()

        self.assertEqual(datos["asignado"], 104000)
        self.assertEqual(datos["teorico"], 96000)
        self.assertEqual(datos["diferencia"], 8000)

    def test_gastar_mas_leche_de_la_prevista_pasa_del_cien_por_ciento(self):
        """
        La razón va asignado / teórico, no al revés.

        Invertida sube cuando se consume menos, y un indicador que crece al
        gastar menos se lee como un logro justo cuando lo más probable es que
        falte cargar una línea de asignación.
        """
        self._asignar([{"silo": self.silo_a.id, "litros": 120000}])  # teórico 96.000

        self.assertEqual(self._estado()["consumo_pct"], 125.0)

    def test_gastar_menos_de_lo_previsto_queda_por_debajo_del_cien(self):
        self._asignar([{"silo": self.silo_a.id, "litros": 48000}])

        self.assertEqual(self._estado()["consumo_pct"], 50.0)

    def test_el_rendimiento_se_mide_en_litros_por_kilo(self):
        """Es como lo mide la planta, y se compara contra el de la receta."""
        self._asignar([{"silo": self.silo_a.id, "litros": 120000}])

        datos = self._estado()

        # 120.000 L para 12.000 kg = 10 L/kg; la receta decía 8.
        self.assertEqual(datos["litros_por_kg"], 10.0)
        self.assertEqual(datos["litros_por_kg_receta"], 8.0)

    def test_sin_kilos_declarados_no_hay_rendimiento(self):
        """Un lote sin producción declarada todavía no rinde nada."""
        self.lote.kg_producidos = 0
        self.lote.save()

        self._asignar([{"silo": self.silo_a.id, "litros": 60000}])

        self.assertIsNone(self._estado()["litros_por_kg"])

    def test_una_merma_mayor_de_la_prevista_no_bloquea(self):
        """Es algo que explicar, no algo que impedir."""
        respuesta = self._asignar([{"silo": self.silo_a.id, "litros": 500000}])

        self.assertEqual(respuesta.status_code, 200)

    def test_sin_receta_no_se_inventa_un_teorico(self):
        sin_receta = Producto.objects.create(
            nombre="Suero en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.lote.producto = sin_receta
        self.lote.save()

        datos = self._estado()

        self.assertIsNone(datos["teorico"])
        self.assertIsNone(datos["diferencia"])
        self.assertIsNone(datos["consumo_pct"])
        self.assertIsNone(datos["litros_por_kg_receta"])


class QuitarAsignacionTests(BaseAsignacion):
    def test_mientras_esta_en_proceso_una_linea_se_puede_quitar(self):
        self._asignar([{"silo": self.silo_a.id, "litros": 60000}])
        linea = self._estado()["lineas"][0]

        respuesta = self.cliente.delete(
            f"/api/produccion/lotes/{self.lote.id}/asignacion/{linea['id']}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["asignado"], 0)

    def test_un_lote_producido_ya_no_borra_asientos(self):
        """
        Después es histórico, y un asiento del libro mayor no se borra: se
        corrige con un ajuste que deja rastro.
        """
        self._asignar([{"silo": self.silo_a.id, "litros": 60000}])
        linea = self._estado()["lineas"][0]

        self.lote.estado = Lote.Estado.PRODUCIDO
        self.lote.save()

        respuesta = self.cliente.delete(
            f"/api/produccion/lotes/{self.lote.id}/asignacion/{linea['id']}/"
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("ajuste", respuesta.json()["detail"])
        self.assertTrue(MovimientoSilo.objects.exists())


class GuardasDeAsignacionTests(BaseAsignacion):
    def test_un_lote_cerrado_no_cambia_su_asignacion(self):
        self.lote.estado = Lote.Estado.CERRADO
        self.lote.save()

        respuesta = self._asignar([{"silo": self.silo_a.id, "litros": 1000}])

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("histórico", respuesta.json()["detail"])

    def test_un_lote_liberado_no_cambia_de_que_leche_salio(self):
        """
        Cambiarlo dejaría la firma de Calidad respaldando otra materia prima,
        que es justo lo que la trazabilidad existe para impedir.
        """
        firmante = User.objects.create_user("calidad9", password="x")
        Liberacion.objects.create(
            lote=self.lote,
            estado=Liberacion.Estado.LIBERADO,
            autorizada_por=firmante,
        )

        respuesta = self._asignar([{"silo": self.silo_a.id, "litros": 1000}])

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("revisar/", respuesta.json()["detail"])

    def test_el_estado_dice_si_es_editable_y_por_que_no(self):
        self.lote.estado = Lote.Estado.ANULADO
        self.lote.save()

        datos = self._estado()

        self.assertFalse(datos["editable"])
        self.assertIn("histórico", datos["motivo_bloqueo"])


class TrazabilidadTests(BaseAsignacion):
    """La composición congelada de cada retiro es la trazabilidad primaria."""

    def _recepcion(self, silo, litros, dia, hora=8):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, dia),
            tipo_leche="Entera",
            litros=litros,
            silo=silo,
            guia=f"G-{dia}{hora}",
            estado=Recepcion.Estado.DESCARGADA,
        )
        MovimientoSilo.objects.create(
            silo=silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=litros,
            fecha_hora=instante(dia, hora),
            origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
            origen_id=recepcion.id,
        )
        return recepcion

    def _trazabilidad(self):
        return self.cliente.get(
            f"/api/produccion/lotes/{self.lote.id}/trazabilidad/"
        ).json()

    def test_devuelve_las_recepciones_que_habia_en_cada_silo(self):
        a1 = self._recepcion(self.silo_a, 50000, 15)
        a2 = self._recepcion(self.silo_a, 40000, 16, hora=6)
        b1 = self._recepcion(self.silo_b, 30000, 15)

        self._asignar(
            [
                {"silo": self.silo_a.id, "litros": 60000},
                {"silo": self.silo_b.id, "litros": 20000},
            ]
        )

        tramos = self._trazabilidad()["tramos"]

        por_silo = {t["silo_codigo"]: t for t in tramos}

        self.assertEqual(
            {r["id"] for r in por_silo["SILO 1"]["recepciones"]}, {a1.id, a2.id}
        )
        self.assertEqual(
            {r["id"] for r in por_silo["SILO 2"]["recepciones"]}, {b1.id}
        )

    def test_no_arrastra_recepciones_posteriores_al_consumo(self):
        """
        Leche que llegó después no tocó este lote. Es la razón de registrar la
        asignación al inicio y no al cerrar: la hora del asiento acota el
        conjunto de candidatas.
        """
        antes = self._recepcion(self.silo_a, 50000, 15)
        despues = self._recepcion(self.silo_a, 70000, 20)

        # Se declara la hora porque la asignación se está cargando después de
        # que ocurrió. Sin declararla valdría `ahora`, y arrastraría la leche
        # del día 20 que este lote nunca vio.
        self._asignar(
            [
                {
                    "silo": self.silo_a.id,
                    "litros": 40000,
                    "fecha_hora": instante(16, 10).isoformat(),
                }
            ]
        )

        ids = {r["id"] for r in self._trazabilidad()["tramos"][0]["recepciones"]}

        self.assertIn(antes.id, ids)
        self.assertNotIn(despues.id, ids)

    def test_fifo_no_muestra_una_recepcion_que_no_fue_consumida(self):
        primera = self._recepcion(self.silo_a, 50000, 15)
        tardia = self._recepcion(self.silo_a, 70000, 20)

        self._asignar([{"silo": self.silo_a.id, "litros": 40000}])

        ids = {r["id"] for r in self._trazabilidad()["tramos"][0]["recepciones"]}

        self.assertIn(primera.id, ids)
        self.assertNotIn(tardia.id, ids)
        origen = self._trazabilidad()["tramos"][0]["recepciones"][0]
        self.assertEqual(origen["litros_atribuidos"], 40000)
        self.assertEqual(origen["trazabilidad"], "confirmada")

    def test_un_lote_sin_asignacion_no_tiene_trazabilidad(self):
        self.assertEqual(self._trazabilidad()["tramos"], [])

    def test_la_respuesta_explica_que_fifo_es_confirmado(self):
        self._recepcion(self.silo_a, 50000, 15)
        self._asignar([{"silo": self.silo_a.id, "litros": 40000}])

        self.assertIn("confirmadas", self._trazabilidad()["nota"])

    def test_solo_el_movimiento_historico_sin_atribucion_es_inferido(self):
        primera = self._recepcion(self.silo_a, 50000, 15)
        segunda = self._recepcion(self.silo_a, 70000, 20)
        self._asignar([{"silo": self.silo_a.id, "litros": 40000}])
        movimiento = MovimientoSilo.objects.get(
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=self.lote.pk,
        )
        AtribucionRecepcion.objects.filter(movimiento=movimiento).delete()

        trazabilidad = self._trazabilidad()
        origenes = trazabilidad["tramos"][0]["recepciones"]

        self.assertEqual(
            {origen["id"] for origen in origenes}, {primera.pk, segunda.pk}
        )
        self.assertTrue(all(
            origen["trazabilidad"] == "inferida" for origen in origenes
        ))
        self.assertTrue(all(
            origen["litros_atribuidos"] is None for origen in origenes
        ))
        self.assertIn("históricos", trazabilidad["nota"])

    def test_los_ajustes_de_silo_no_son_recepciones(self):
        self._recepcion(self.silo_a, 50000, 15)
        MovimientoSilo.objects.create(
            silo=self.silo_a,
            tipo=MovimientoSilo.Tipo.AJUSTE,
            litros=-2000,
            fecha_hora=instante(15, 20),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Corrección de medición",
        )

        self._asignar([{"silo": self.silo_a.id, "litros": 40000}])

        self.assertEqual(len(self._trazabilidad()["tramos"][0]["recepciones"]), 1)
