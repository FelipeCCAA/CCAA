"""
Soltar un evaporador preparado y anular un lote sin dejar la máquina ocupada.

Abrir el lote sobre un evaporador saca la leche del silo del vale y deja la
corrida preparada (`confirmar-borrador` + `crear_condensacion_guiada`). Antes
no había vuelta atrás: anular el lote no cerraba su ejecución, el evaporador
quedaba «ocupado por otra corrida» indefinidamente (caso 3 de «La pantalla
ofrece lo que el backend va a rechazar», `CLAUDE.md`) y la leche seguía
descontada de un silo del que nunca salió.
"""

from decimal import Decimal

from django.utils import timezone

from procesos.models import (
    CorridaCondensacion, EjecucionProceso, ReservaSiloProceso,
)
from procesos.servicios import transicionar_ejecucion
from recepcion.models import MovimientoSilo
from recepcion.servicios import saldo_silo
from usuarios.models import PerfilUsuario

from .models import Lote
from .servicios import litros_ya_tomados
from .tests_borrador import BaseBorradorLote
from .tests_borrador_evaporacion import BaseEvaporadorDesdeVale


class ConEvaporadorPreparado(BaseEvaporadorDesdeVale):
    """Un lote abierto sobre el evaporador desde el vale, con la corrida preparada."""

    def setUp(self):
        super().setUp()
        # El silo del vale tiene la leche que el vale dejó ahí.
        MovimientoSilo.objects.create(
            silo=self.silo_b, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("20000"), fecha_hora=timezone.now(),
        )
        self.saldo_inicial = saldo_silo(self.silo_b)
        borrador_id = self.borrador_sobre_evaporador()
        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)
        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.lote = Lote.objects.get(pk=borrador_id)
        self.corrida = CorridaCondensacion.objects.get(lote=self.lote)
        self.ejecucion = self.corrida.ejecucion

    def cancelar(self, motivo="Se eligió el vale equivocado.", cliente=None):
        return (cliente or self.cliente).post(
            f"/api/procesos/condensaciones/{self.corrida.pk}/cancelar-preparacion/",
            {"motivo": motivo}, format="json",
        )

    def fila_del_puesto(self):
        respuesta = self.cliente.get("/api/procesos/condensaciones/puesto/")
        self.assertEqual(respuesta.status_code, 200)
        return next(
            item for item in respuesta.json()["evaporadores"]
            if item["equipo_id"] == self.evaporador.pk
        )

    def assertNadaCambio(self):
        self.lote.refresh_from_db()
        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.EN_PROCESO)
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.BORRADOR)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial - Decimal("12000"))


class CancelarPreparacionEvaporacionTests(ConEvaporadorPreparado):
    def test_cancelar_suelta_el_evaporador_anula_el_lote_y_devuelve_la_leche(self):
        self.assertEqual(self.fila_del_puesto()["estado"], "preparada")
        # Una reserva colgada de la ejecución también se suelta.
        ReservaSiloProceso.objects.create(
            ejecucion=self.ejecucion, silo=self.concentrado,
            tipo=ReservaSiloProceso.Tipo.DESTINO, cantidad_planificada=Decimal("12000"),
        )

        respuesta = self.cancelar()

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.lote.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CANCELADA)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        evento = self.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.CANCELADA)
        self.assertEqual(evento.motivo, "Se eligió el vale equivocado.")
        self.assertEqual(self.lote.estado, Lote.Estado.ANULADO)
        self.assertIn("[ANULACIÓN]", self.lote.observacion)
        self.assertIn("Se eligió el vale equivocado.", self.lote.observacion)
        self.assertEqual(self.fila_del_puesto()["estado"], "disponible")
        self.assertFalse(
            ReservaSiloProceso.objects.filter(
                ejecucion=self.ejecucion, estado=ReservaSiloProceso.Estado.ACTIVA,
            ).exists()
        )
        # La leche vuelve al silo del que salió, con un asiento compensatorio:
        # la salida original sigue ahí, porque la trazabilidad no se borra.
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial)
        self.assertTrue(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.SALIDA, origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=self.lote.pk,
        ).exists())
        devolucion = MovimientoSilo.objects.get(
            tipo=MovimientoSilo.Tipo.INGRESO, lote=self.lote,
        )
        self.assertEqual(devolucion.silo, self.silo_b)
        self.assertEqual(devolucion.litros, Decimal("12000.00"))
        # Y el vale recupera esos litros: el próximo lote los puede tomar.
        self.assertEqual(litros_ya_tomados(self.vale), Decimal("0"))

    def test_sin_motivo_no_cancela(self):
        respuesta = self.cancelar(motivo="   ")

        self.assertEqual(respuesta.status_code, 400, respuesta.json())
        self.assertEqual(respuesta.json()["message"], "Indica el motivo de la cancelación.")
        self.assertNadaCambio()

    def test_una_corrida_iniciada_no_se_cancela_como_preparacion(self):
        CorridaCondensacion.objects.filter(pk=self.corrida.pk).update(
            estado=CorridaCondensacion.Estado.EN_PROCESO, iniciada_en=timezone.now(),
        )

        respuesta = self.cancelar()

        self.assertEqual(respuesta.status_code, 400, respuesta.json())
        self.assertIn("solo se cancela un evaporador preparado", respuesta.json()["message"].lower())
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.EN_PROCESO)
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial - Decimal("12000"))

    def test_sin_permiso_de_condensacion_responde_403(self):
        respuesta = self.cancelar(cliente=self._cliente_de_area(PerfilUsuario.Area.SECADO))

        self.assertEqual(respuesta.status_code, 403)
        self.assertNadaCambio()

    def test_si_la_leche_no_cabe_en_el_silo_no_cancela(self):
        # Mientras el evaporador esperaba, el silo se volvió a llenar.
        libre = self.silo_b.capacidad_l - saldo_silo(self.silo_b)
        MovimientoSilo.objects.create(
            silo=self.silo_b, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=libre - Decimal("100"), fecha_hora=timezone.now(),
        )

        respuesta = self.cancelar()

        self.assertEqual(respuesta.status_code, 400, respuesta.json())
        mensaje = respuesta.json()["message"]
        self.assertIn(self.silo_b.codigo, mensaje)
        self.assertIn("capacidad", mensaje)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.EN_PROCESO)
        self.assertFalse(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.INGRESO, lote=self.lote,
        ).exists())

    def test_si_el_silo_esta_en_cip_no_cancela(self):
        self.silo_b.estado = self.silo_b.Estado.EN_CIP
        self.silo_b.save(update_fields=["estado"])

        respuesta = self.cancelar()

        self.assertEqual(respuesta.status_code, 400, respuesta.json())
        self.assertIn(self.silo_b.codigo, respuesta.json()["message"])
        self.assertNadaCambio()

    def test_cancelar_por_la_transicion_generica_tambien_devuelve_la_leche(self):
        """Simétrico a Secado: la bandeja genérica no deja la leche descontada."""
        transicionar_ejecucion(
            ejecucion_id=self.ejecucion.pk, estado_nuevo=EjecucionProceso.Estado.CANCELADA,
            usuario=self.lote.abierto_por, motivo="Cancelada desde la bandeja.",
        )

        self.lote.refresh_from_db()
        self.corrida.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.ANULADO)
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CANCELADA)
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial)


class AnularLoteSobreEvaporadorTests(ConEvaporadorPreparado):
    """Caso 3: anular el lote cierra su ejecución y suelta el evaporador."""

    def anular(self, motivo="La corrida no se hará."):
        return self.cliente.patch(
            f"/api/produccion/lotes/{self.lote.pk}/",
            {"estado": "anulado", "motivo_anulacion": motivo}, format="json",
        )

    def test_anular_el_lote_suelta_el_evaporador(self):
        respuesta = self.anular()

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        evento = self.ejecucion.eventos.get(estado_nuevo=EjecucionProceso.Estado.CANCELADA)
        self.assertIn("La corrida no se hará.", evento.motivo)
        self.assertEqual(self.fila_del_puesto()["estado"], "disponible")
        # Es la misma preparación que se suelta: la leche vuelve igual.
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial)
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.observacion.count("[ANULACIÓN]"), 1)
        # Por el `PATCH` la marca se escribe antes de devolver la leche; igual
        # tiene que decir que volvió, y una sola vez.
        self.assertEqual(
            self.lote.observacion.count(f"La leche volvió a {self.silo_b.codigo}."), 1
        )

    def test_anular_con_la_corrida_iniciada_la_cancela_sin_devolver_la_leche(self):
        CorridaCondensacion.objects.filter(pk=self.corrida.pk).update(
            estado=CorridaCondensacion.Estado.EN_PROCESO, iniciada_en=timezone.now(),
        )

        respuesta = self.anular()

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.lote.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        # Una corrida en proceso con su ejecución cancelada no existe: la
        # corrida queda cancelada con ella.
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CANCELADA)
        # Lo que entró al evaporador no vuelve.
        self.assertEqual(saldo_silo(self.silo_b), self.saldo_inicial - Decimal("12000"))
        self.assertNotIn("La leche volvió", self.lote.observacion)

    def test_sin_permiso_de_la_etapa_anula_si_la_ejecucion_espera_a_calidad(self):
        """
        `pendiente_control` no se cancela (`anular_lote` la deja): anular no
        toca la corrida, así que no pide el permiso de su etapa.
        """
        EjecucionProceso.objects.filter(pk=self.ejecucion.pk).update(
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )

        respuesta = self._cliente_de_area(PerfilUsuario.Area.SECADO).patch(
            f"/api/produccion/lotes/{self.lote.pk}/",
            {"estado": "anulado", "motivo_anulacion": "La corrida no se hará."},
            format="json",
        )

        self.assertNotEqual(respuesta.status_code, 403, respuesta.json())
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)


class AnularLoteEnLineaTests(BaseBorradorLote):
    """
    Una línea abierta desde el vale ya consumió la leche: anular cierra la
    ejecución y suelta la máquina, pero no inventa una devolución.
    """

    def test_anular_cierra_la_ejecucion_sin_devolver_la_leche(self):
        borrador = self.crear_borrador(**self.datos_completos())
        respuesta = self.cliente.post(
            f"/api/produccion/lotes/{borrador['id']}/confirmar-borrador/"
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        lote = Lote.objects.get(pk=borrador["id"])
        saldo_abierto = saldo_silo(self.silo_b)

        respuesta = self.cliente.patch(
            f"/api/produccion/lotes/{lote.pk}/",
            {"estado": "anulado", "motivo_anulacion": "Se cortó la línea."}, format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        lote.refresh_from_db()
        self.assertEqual(lote.estado, Lote.Estado.ANULADO)
        self.assertEqual(lote.ejecucion.estado, EjecucionProceso.Estado.CANCELADA)
        self.assertEqual(saldo_silo(self.silo_b), saldo_abierto)
        self.assertFalse(MovimientoSilo.objects.filter(
            tipo=MovimientoSilo.Tipo.INGRESO, lote=lote,
        ).exists())
        # La máquina vuelve a ofrecerse para abrir.
        opciones = self.cliente.get("/api/produccion/lotes/opciones-inicio/").json()
        linea = next(item for item in opciones["equipos"] if item["id"] == self.linea_envasado.pk)
        self.assertTrue(linea["habilitado"], linea)


class OpcionesInicioSirvenLaReglaTests(BaseBorradorLote):
    """
    `opciones-inicio` sirve qué tipos de máquina abren lote desde un vale, para
    que el frontend no mantenga su propia copia de `abre_desde_vale`.
    """

    def test_los_tipos_servidos_son_los_que_acepta_la_regla(self):
        from maestros.models import Equipo

        from .servicios import abre_desde_vale

        datos = self.cliente.get("/api/produccion/lotes/opciones-inicio/").json()

        esperados = {tipo for tipo in Equipo.Tipo.values if abre_desde_vale(tipo)}
        self.assertEqual(set(datos["tipos_que_abren_desde_vale"]), esperados)
        # Decisión de 2026-10-07: desde un vale abren solo estos tres.
        # `carga`, `descremadora`, `mantequera` y `otro` no abren desde un vale:
        # los tres primeros tienen su propio puesto o flujo.
        self.assertEqual(esperados, {"evaporador", "envasadora", "linea"})



class AnularExigeElPermisoDeLaEtapaTests(ConEvaporadorPreparado):
    """
    Anular un lote con su ejecución abierta la cancela: suelta la máquina y
    devuelve la leche. Es lo mismo que «Cancelar preparación», así que pide el
    mismo permiso — si no, Secado (que escribe lotes) hacía por el `PATCH` lo
    que el puesto le niega con 403.
    """

    def anular(self, cliente):
        return cliente.patch(
            f"/api/produccion/lotes/{self.lote.pk}/",
            {"estado": "anulado", "motivo_anulacion": "La corrida no se hará."},
            format="json",
        )

    def test_secado_no_anula_un_lote_sobre_el_evaporador(self):
        respuesta = self.anular(self._cliente_de_area(PerfilUsuario.Area.SECADO))

        self.assertEqual(respuesta.status_code, 403, respuesta.json())
        self.assertNadaCambio()
        self.assertEqual(self.fila_del_puesto()["estado"], "preparada")

    def test_condensacion_si_lo_anula(self):
        respuesta = self.anular(self.cliente)

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.lote.refresh_from_db()
        self.assertEqual(self.lote.estado, Lote.Estado.ANULADO)


class MarcaDeLaAnulacionTests(ConEvaporadorPreparado):
    def test_la_marca_dice_que_la_leche_volvio_solo_si_volvio(self):
        self.assertEqual(self.cancelar().status_code, 200)
        self.lote.refresh_from_db()
        self.assertIn(f"La leche volvió a {self.silo_b.codigo}.", self.lote.observacion)

    def test_sin_leche_descontada_no_dice_que_volvio(self):
        from recepcion.models import AtribucionRecepcion

        salida = MovimientoSilo.objects.get(
            tipo=MovimientoSilo.Tipo.SALIDA, origen_id=self.lote.pk,
        )
        # Un lote sin consumo de silo (dato histórico): nada que devolver.
        AtribucionRecepcion.objects.filter(movimiento=salida).delete()
        MovimientoSilo.objects.filter(pk=salida.pk).delete()

        self.assertEqual(self.cancelar().status_code, 200)

        self.lote.refresh_from_db()
        self.assertNotIn("La leche volvió", self.lote.observacion)
        self.assertIn("No había leche descontada que devolver.", self.lote.observacion)
