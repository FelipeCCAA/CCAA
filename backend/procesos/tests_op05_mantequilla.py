"""OP-05 regressions for traceable cream feeding and idempotent butter runs."""

from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from maestros.models import Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import PerfilUsuario

from . import tests_mantequilla as fixtures
from .models import (
    CorridaMantequilla, EjecucionProceso, EntradaProceso, EtapaProceso,
    EventoProceso, Proceso, RutaProducto, SalidaProceso,
)
from .servicios import cerrar_mantequilla, crear_mantequilla_guiada, iniciar_mantequilla


class MantequillaOp05BaselineTests(TestCase):
    def setUp(self):
        fixtures.MantequillaTests.setUp(self)

    def _origen_tk(self, *, firmar=True):
        tk = Silo.objects.create(
            sucursal=self.planta, codigo="TK-OP05-CREMA",
            tipo=Silo.Tipo.TK_CREMA, capacidad_l=Decimal("2000"),
        )
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("1000"), fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        proceso = Proceso.objects.create(codigo="op05-origen", nombre="Origen OP05")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="op05-descremar", nombre="Descremación",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        origen = EjecucionProceso.objects.create(
            codigo="EJ-OP05-ORIGEN", etapa=etapa,
            sucursal=self.planta, estado=EjecucionProceso.Estado.CERRADA,
        )
        ruta_crema = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.lote_crema.producto,
            proceso=self.corrida.ejecucion.etapa.proceso,
        )
        salida = SalidaProceso.objects.create(
            ejecucion=origen, lote=self.lote_crema, silo=tk,
            producto=self.lote_crema.producto, ruta_producto=ruta_crema,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            clasificacion=SalidaProceso.Clasificacion.INTERMEDIO,
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
            cantidad=Decimal("1000"), unidad="L",
        )
        analisis = AnalisisSilo.objects.create(
            silo=tk, tomado_en=timezone.now(), grasa=Decimal("40"),
            sng=Decimal("5"), densidad=Decimal("1000"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        decision = LiberacionProceso.objects.create(
            salida=salida, analisis_silo=analisis,
            estado=LiberacionProceso.Estado.LIBERADO,
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        if firmar:
            registrar_firma_salida(decision)
        self.corrida.kg_crema = Decimal("200")
        self.corrida.salida_crema = salida
        self.corrida.save(update_fields=["kg_crema", "salida_crema"])
        return salida, analisis, tk

    def test_no_inicia_crema_sin_salida_de_origen(self):
        with self.assertRaises(ValidationError):
            iniciar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                operacion_id=uuid4(),
            )
        self.assertEqual(self.corrida.ejecucion.entradas.count(), 0)
        self.assertEqual(MovimientoSilo.objects.filter(tipo=MovimientoSilo.Tipo.SALIDA).count(), 0)

    def test_firma_de_origen_obsoleta_impide_consumo(self):
        _, analisis, _ = self._origen_tk()
        AnalisisSilo.objects.filter(pk=analisis.pk).update(densidad=Decimal("1010"))
        with self.assertRaises(ValidationError):
            iniciar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                operacion_id=uuid4(),
            )
        self.assertEqual(self.corrida.ejecucion.entradas.count(), 0)
        self.assertEqual(MovimientoSilo.objects.filter(tipo=MovimientoSilo.Tipo.SALIDA).count(), 0)

    def test_reintento_inicio_mismo_uuid_recupera_sin_reconsumir(self):
        self._origen_tk()
        self.usuario.perfil.area = PerfilUsuario.Area.CONDENSACION
        self.usuario.perfil.save(update_fields=["area"])
        cliente = APIClient()
        cliente.force_authenticate(self.usuario)
        operacion_id = str(uuid4())
        url = f"/api/procesos/mantequillas/{self.corrida.pk}/iniciar/"

        primera = cliente.post(url, {"operacion_id": operacion_id}, format="json")
        segunda = cliente.post(url, {"operacion_id": operacion_id}, format="json")

        self.assertEqual(primera.status_code, 200, primera.data)
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.assertEqual(self.corrida.ejecucion.entradas.count(), 1)
        self.assertEqual(MovimientoSilo.objects.filter(tipo=MovimientoSilo.Tipo.SALIDA).count(), 1)

    def test_no_registra_mazada_como_suero(self):
        self._origen_tk()
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=uuid4(),
        )

        with self.assertRaises(ValidationError):
            cerrar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                kg_mantequilla="100", kg_suero="90", kg_merma="10",
                operacion_id=uuid4(),
            )
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)

    def test_tk_con_densidad_real_consume_litros_y_cierra_balance(self):
        salida, analisis, tk = self._origen_tk()
        AnalisisSilo.objects.filter(pk=analisis.pk).update(densidad=Decimal("1010"))
        decision = salida.liberacion_calidad
        registrar_firma_salida(decision)
        self.corrida.kg_crema = Decimal("202")
        self.corrida.save(update_fields=["kg_crema"])

        inicio_id = uuid4()
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=inicio_id,
        )
        entrada = EntradaProceso.objects.get(ejecucion=self.corrida.ejecucion)
        retiro = MovimientoSilo.objects.get(
            operacion_id=self.corrida.operacion_id,
            tipo=MovimientoSilo.Tipo.SALIDA,
        )
        self.assertEqual(entrada.salida_origen_id, salida.pk)
        self.assertEqual(entrada.silo_id, tk.pk)
        self.assertEqual(entrada.unidad, "L")
        self.assertEqual(entrada.cantidad, Decimal("200"))
        self.assertEqual(retiro.litros, entrada.cantidad)
        self.assertEqual(self.corrida.kg_crema, Decimal("202"))
        evento = EventoProceso.objects.get(operacion_id=inicio_id)
        self.assertEqual(evento.datos["analisis_silo_id"], analisis.pk)
        self.assertEqual(Decimal(evento.datos["densidad_kg_m3"]), Decimal("1010"))

        cierre_id = uuid4()
        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="197", kg_merma="5", operacion_id=cierre_id,
        )
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.kg_suero, Decimal("0"))
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 2)
        self.assertEqual(self.corrida.controles["_op05"]["cierre"]["litros_consumidos"], "200.00")

    def test_replay_cierre_recupera_sin_duplicar_y_otro_payload_rechaza(self):
        self._origen_tk()
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=uuid4(),
        )
        cierre_id = uuid4()
        parametros = dict(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="195", kg_merma="5", operacion_id=cierre_id,
        )
        primera = cerrar_mantequilla(**parametros)
        segunda = cerrar_mantequilla(**parametros)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 2)
        self.assertEqual(EventoProceso.objects.filter(operacion_id=cierre_id).count(), 1)
        with self.assertRaises(ValidationError):
            cerrar_mantequilla(**{**parametros, "kg_mantequilla": "194"})

    def test_replay_alta_usa_misma_corrida_y_payload_distinto_rechaza(self):
        salida, _, _ = self._origen_tk()
        alta_id = uuid4()
        parametros = dict(
            orden_id=self.corrida.orden_id, lote_crema_id=self.lote_crema.pk,
            salida_crema_id=salida.pk, equipo_id=self.corrida.ejecucion.equipo_id,
            codigo_lote_mantequilla="MANT-OP05-REPLAY", kg_crema="200",
            usuario=self.usuario, operacion_id=alta_id,
        )
        primera = crear_mantequilla_guiada(**parametros)
        segunda = crear_mantequilla_guiada(**parametros)
        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(CorridaMantequilla.objects.filter(operacion_id=alta_id).count(), 1)
        with self.assertRaises(ValidationError):
            crear_mantequilla_guiada(**{**parametros, "kg_crema": "201"})

    def test_alta_rechaza_tk_en_cip_sin_crear_lote(self):
        salida, _, tk = self._origen_tk()
        tk.estado = tk.Estado.EN_CIP
        tk.save(update_fields=["estado"])
        cantidad_antes = CorridaMantequilla.objects.count()
        with self.assertRaises(ValidationError):
            crear_mantequilla_guiada(
                orden_id=self.corrida.orden_id, lote_crema_id=self.lote_crema.pk,
                salida_crema_id=salida.pk,
                equipo_id=self.corrida.ejecucion.equipo_id,
                codigo_lote_mantequilla="MANT-OP05-CIP", kg_crema="200",
                usuario=self.usuario, operacion_id=uuid4(),
            )
        self.assertEqual(CorridaMantequilla.objects.count(), cantidad_antes)

    def test_alta_rechaza_saldo_tk_insuficiente_aun_con_salida_libre(self):
        salida, _, tk = self._origen_tk()
        MovimientoSilo.objects.create(
            silo=tk, tipo=MovimientoSilo.Tipo.SALIDA,
            litros=Decimal("900"), fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.DESCREMACION,
        )
        cantidad_antes = CorridaMantequilla.objects.count()
        with self.assertRaises(ValidationError):
            crear_mantequilla_guiada(
                orden_id=self.corrida.orden_id, lote_crema_id=self.lote_crema.pk,
                salida_crema_id=salida.pk,
                equipo_id=self.corrida.ejecucion.equipo_id,
                codigo_lote_mantequilla="MANT-OP05-SALDO", kg_crema="200",
                usuario=self.usuario, operacion_id=uuid4(),
            )
        self.assertEqual(CorridaMantequilla.objects.count(), cantidad_antes)

    def test_calidad_revocada_tras_inicio_no_cierra(self):
        salida, analisis, _ = self._origen_tk()
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=uuid4(),
        )
        AnalisisSilo.objects.filter(pk=analisis.pk).update(densidad=Decimal("1010"))
        with self.assertRaises(ValidationError):
            cerrar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                kg_mantequilla="195", kg_merma="5", operacion_id=uuid4(),
            )
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)
        self.assertEqual(salida.usos_como_origen.count(), 1)

    def test_nueva_firma_de_densidad_no_reescribe_conversion_del_inicio(self):
        salida, analisis, _ = self._origen_tk()
        inicio_id = uuid4()
        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=inicio_id,
        )
        evento_inicio = EventoProceso.objects.get(operacion_id=inicio_id)
        firma_inicio = evento_inicio.datos["firma_salida"]
        self.assertEqual(Decimal(evento_inicio.datos["densidad_kg_m3"]), Decimal("1000"))
        self.assertEqual(Decimal(evento_inicio.datos["litros_consumidos"]), Decimal("200"))

        AnalisisSilo.objects.filter(pk=analisis.pk).update(densidad=Decimal("1010"))
        registrar_firma_salida(salida.liberacion_calidad)
        cerrar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            kg_mantequilla="195", kg_merma="5", operacion_id=uuid4(),
        )
        self.corrida.refresh_from_db()
        evidencia = self.corrida.controles["_op05"]["cierre"]
        self.assertEqual(evidencia["firma_salida_inicio"], firma_inicio)
        self.assertNotEqual(evidencia["firma_vigente_al_cierre"], firma_inicio)
        self.assertEqual(Decimal(evidencia["densidad_inicio_kg_m3"]), Decimal("1000"))
        self.assertEqual(Decimal(evidencia["densidad_vigente_al_cierre_kg_m3"]), Decimal("1010"))
        self.assertEqual(Decimal(evidencia["litros_consumidos"]), Decimal("200"))

    def test_cliente_no_puede_sobrescribir_metadata_y_rollback_inicio(self):
        self._origen_tk()
        with patch.object(EventoProceso.objects, "create", side_effect=RuntimeError("fallo inyectado")):
            with self.assertRaises(RuntimeError):
                iniciar_mantequilla(
                    corrida_id=self.corrida.pk, usuario=self.usuario,
                    operacion_id=uuid4(),
                )
        self.corrida.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaMantequilla.Estado.BORRADOR)
        self.assertEqual(self.corrida.ejecucion.entradas.count(), 0)
        self.assertEqual(MovimientoSilo.objects.filter(tipo=MovimientoSilo.Tipo.SALIDA).count(), 0)

        iniciar_mantequilla(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            operacion_id=uuid4(),
        )
        with self.assertRaises(ValidationError):
            cerrar_mantequilla(
                corrida_id=self.corrida.pk, usuario=self.usuario,
                kg_mantequilla="195", kg_merma="5", operacion_id=uuid4(),
                controles={"_op05": {"firma_salida": "falsa"}},
            )
        self.assertEqual(self.corrida.ejecucion.salidas.count(), 0)
