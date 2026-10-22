"""H09-01: una firma sigue al material de su etapa y a sus orígenes reales."""

from datetime import date
from datetime import timedelta
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from queue import Queue
import time
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Especificacion, Mandante, Producto, Silo
from procesos.models import EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, SalidaProceso
from produccion.models import Lote, RegistroEnvase
from recepcion.models import AnalisisSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import Liberacion, LiberacionProceso
from .vigencia import (
    exigir_liberacion_lote_vigente,
    exigir_liberacion_salida_vigente,
    registrar_firma_lote,
    registrar_firma_salida,
)


class _FixtureFirmasPorEtapa:
    """Grafo pequeño: evaporación → secado, con ramas independientes opcionales."""

    def setUp(self):
        empresa = Empresa.objects.create(rut="H09-FICTICIO", nombre="Ensayo H09")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="H09", nombre="Planta ficticia H09",
        )
        self.usuario = User.objects.create_user("calidad-h09")
        mandante = Mandante.objects.create(empresa=empresa, nombre="Mandante H09")
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Producto ficticio H09", familia=Producto.Familia.POLVO,
        )
        proceso = Proceso.objects.create(codigo="h09-polvo", nombre="Polvo H09")
        self.evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-evaporacion", nombre="Evaporación H09",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1, requiere_calidad=True,
        )
        self.secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-secado", nombre="Secado H09",
            tipo=EtapaProceso.Tipo.SECADO, orden=2, requiere_calidad=True,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.planta, codigo="EV-H09", nombre="Evaporador ficticio",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        self.torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-H09", nombre="Torre ficticia",
            tipo=Equipo.Tipo.TORRE,
        )
        self.torre_alterna = Equipo.objects.create(
            sucursal=self.planta, codigo="TOR-H09-B", nombre="Torre alterna ficticia",
            tipo=Equipo.Tipo.TORRE,
        )
        self.silo = Silo.objects.create(
            sucursal=self.planta, codigo="TK-H09", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        self.lote = self._lote("H09-RAIZ")
        self.origen = self._salida(
            self.evaporacion, self.lote, "EV-H09-1", Decimal("500"),
            silo=self.silo, unidad="L", equipo=self.evaporador,
        )
        self._firmar_salida(self.origen)

    def _lote(self, codigo, *, producto=None):
        return Lote.objects.create(
            sucursal=self.planta, codigo_lote=codigo, producto=producto or self.producto,
            fecha=date(2026, 10, 20), estado=Lote.Estado.EN_PROCESO,
            kg_producidos=Decimal("0"),
        )

    def _salida(self, etapa, lote, codigo, cantidad, *, silo=None, unidad="kg", equipo=None, producto=None):
        ejecucion = EjecucionProceso.objects.create(
            codigo=codigo, etapa=etapa, sucursal=self.planta, equipo=equipo,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        return SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, silo=silo, producto=producto or self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            cantidad=cantidad, unidad=unidad,
        )

    def _firmar_salida(self, salida, *, analisis_silo=None):
        with transaction.atomic():
            decision = LiberacionProceso.objects.create(
                salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
                decidida_por=self.usuario, decidida_en=timezone.now(),
                analisis_silo=analisis_silo,
            )
            registrar_firma_salida(decision)
        return decision

    def _firmar_lote(self, lote):
        lote.estado = Lote.Estado.PRODUCIDO
        lote.kg_producidos = Decimal("40")
        lote.save(update_fields=["estado", "kg_producidos"])
        with transaction.atomic():
            decision = Liberacion.objects.create(
                lote=lote, estado=Liberacion.Estado.LIBERADO,
                autorizada_por=self.usuario, autorizada_en=timezone.now(),
            )
            registrar_firma_lote(decision)
        return decision

    def _descendiente(self, codigo, *, lote=None, origen=None, producto=None):
        origen = origen or self.origen
        lote = lote or self.lote
        ejecucion = EjecucionProceso.objects.create(
            codigo=f"EJ-{codigo}", etapa=self.secado, sucursal=self.planta,
            equipo=self.torre, estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        entrada = EntradaProceso(
            ejecucion=ejecucion, silo=origen.silo, salida_origen=origen,
            cantidad=Decimal("100"), unidad="L",
        )
        entrada.full_clean()
        entrada.save()
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, producto=producto or self.producto,
            naturaleza=SalidaProceso.Naturaleza.PRINCIPAL,
            destino=SalidaProceso.Destino.ENVASADO,
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            cantidad=Decimal("40"), unidad="kg",
        )
        self._firmar_salida(salida)
        return entrada, salida

    def _assert_vigente(self, salida):
        decision = LiberacionProceso.objects.get(salida=salida)
        with transaction.atomic():
            self.assertEqual(
                exigir_liberacion_salida_vigente(salida.pk), str(decision.firma_id),
            )

    def _assert_no_vigente(self, salida):
        with self.assertRaises(ValidationError), transaction.atomic():
            exigir_liberacion_salida_vigente(salida.pk)

    def _origen_sin_firma_requerida(self):
        # El modelo permite consumir una salida declarada LIBERADA; la etapa
        # sin Calidad no aporta, ni debe fingir, una firma de Calidad.
        self.evaporacion.requiere_calidad = False
        self.evaporacion.save(update_fields=["requiere_calidad"])
        decision = LiberacionProceso.objects.get(salida=self.origen)
        decision.estado = LiberacionProceso.Estado.LIBERADO
        decision.firma_id = None
        decision.version_firmada = None
        decision.evidencia_firmada = {}
        decision.save(update_fields=[
            "estado", "firma_id", "version_firmada", "evidencia_firmada",
        ])

    def _final_de_otro_producto(self, codigo):
        producto = Producto.objects.create(
            mandante=self.producto.mandante, nombre=f"Producto final ficticio {codigo}",
            familia=Producto.Familia.POLVO,
        )
        lote = self._lote(f"LOTE-{codigo}", producto=producto)
        _, salida = self._descendiente(codigo, lote=lote, producto=producto)
        self._firmar_lote(lote)
        return lote, salida

    def _assert_final_retirado(self, lote, salida):
        self.assertEqual(
            LiberacionProceso.objects.get(salida=salida).estado,
            LiberacionProceso.Estado.PENDIENTE,
        )
        self.assertEqual(
            Liberacion.objects.get(lote=lote).estado,
            Liberacion.Estado.EN_REVISION,
        )
        self._assert_no_vigente(salida)
        with self.assertRaises(ValidationError), transaction.atomic():
            exigir_liberacion_lote_vigente(lote.pk)


class FirmasPorEtapaH09Tests(_FixtureFirmasPorEtapa, TestCase):
    def test_borrar_salida_sin_firma_no_rompe_la_invalidacion_transaccional(self):
        salida = SalidaProceso.objects.create(
            ejecucion=self.origen.ejecucion, silo=self.silo, producto=self.producto,
            naturaleza=SalidaProceso.Naturaleza.COPRODUCTO,
            cantidad=Decimal("5"), unidad="L",
        )
        identificador = salida.pk
        salida.delete()
        self.assertFalse(SalidaProceso.objects.filter(pk=identificador).exists())
        self._assert_vigente(self.origen)

    def test_continuar_y_cerrar_secado_no_caduca_firma_de_evaporacion(self):
        self.lote.equipo = self.torre
        self.lote.save(update_fields=["equipo"])
        self._assert_vigente(self.origen)
        self.lote.kg_producidos = Decimal("40")
        self.lote.estado = Lote.Estado.PRODUCIDO
        self.lote.save(update_fields=["kg_producidos", "estado"])
        self._assert_vigente(self.origen)

    def test_correccion_material_del_origen_retira_firmas_descendientes_y_lote_final(self):
        _, final = self._descendiente("H09-FINAL")
        firma_final = self._firmar_lote(self.lote)
        self.origen.cantidad = Decimal("490")
        self.origen.save(update_fields=["cantidad"])
        self._assert_no_vigente(self.origen)
        self._assert_no_vigente(final)
        firma_final.refresh_from_db()
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)

    def test_corregir_analisis_firmado_del_origen_retira_descendientes(self):
        muestra = AnalisisSilo.objects.create(
            silo=self.silo, tomado_en=timezone.now(),
            estado=AnalisisSilo.Estado.CONFIRMADO,
            grasa=Decimal("3.50"), sng=Decimal("9.00"),
            inhibidores_resultado="negativo", metodo="tri_sensor",
            hora_lectura=timezone.now().time(),
        )
        decision = LiberacionProceso.objects.get(salida=self.origen)
        decision.analisis_silo = muestra
        decision.save(update_fields=["analisis_silo"])
        registrar_firma_salida(decision)
        _, final = self._descendiente("H09-ANALISIS")
        self._firmar_lote(self.lote)
        muestra.grasa = Decimal("3.60")
        muestra.save(update_fields=["grasa"])
        self._assert_no_vigente(self.origen)
        self._assert_no_vigente(final)
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)

    def test_corregir_una_rama_no_caduca_su_hermana(self):
        lote_a = self._lote("H09-RAMA-A")
        lote_b = self._lote("H09-RAMA-B")
        _, rama_a = self._descendiente("H09-A", lote=lote_a)
        _, rama_b = self._descendiente("H09-B", lote=lote_b)
        self._firmar_lote(lote_a)
        self._firmar_lote(lote_b)
        rama_a.cantidad = Decimal("39")
        rama_a.save(update_fields=["cantidad"])
        self._assert_no_vigente(rama_a)
        self._assert_vigente(rama_b)
        self._assert_vigente(self.origen)
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(lote_a.pk)
        exigir_liberacion_lote_vigente(lote_b.pk)

    def test_cambiar_cantidad_de_entrada_caduca_etapa_consumidora_y_lote(self):
        entrada, final = self._descendiente("H09-ENTRADA")
        self._firmar_lote(self.lote)
        entrada.cantidad = Decimal("90")
        entrada.save(update_fields=["cantidad"])
        self._assert_vigente(self.origen)
        self._assert_no_vigente(final)
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)

    def test_cambiar_equipo_de_la_etapa_caduca_su_salida_no_el_origen(self):
        _, final = self._descendiente("H09-EQUIPO")
        self._firmar_lote(self.lote)
        ejecucion = final.ejecucion
        ejecucion.equipo = self.torre_alterna
        ejecucion.save(update_fields=["equipo"])
        self._assert_vigente(self.origen)
        self._assert_no_vigente(final)
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)

    def test_corregir_y_revertir_origen_no_resucita_las_firmas(self):
        _, final = self._descendiente("H09-ABA")
        firma_original = LiberacionProceso.objects.get(salida=final).firma_id
        self.origen.cantidad = Decimal("490")
        self.origen.save(update_fields=["cantidad"])
        self.origen.cantidad = Decimal("500")
        self.origen.save(update_fields=["cantidad"])
        self._assert_no_vigente(final)
        decision = LiberacionProceso.objects.get(salida=final)
        self.assertEqual(decision.firma_id, firma_original)
        self.assertFalse(decision.firma_vigente)

    def test_firma_historica_v1_conserva_comparacion_estricta_sin_actualizacion_automatica(self):
        # La compatibilidad se limita a verificar la foto previa; no la transforma
        # en formato 2 ni adjudica un acto nuevo de Calidad.
        from .vigencia import evidencia_salida_v1

        decision = LiberacionProceso.objects.get(salida=self.origen)
        firma_original = decision.firma_id
        decision.evidencia_firmada = evidencia_salida_v1(self.origen.pk)
        decision.save(update_fields=["evidencia_firmada"])
        self.assertEqual(decision.evidencia_firmada["formato"], 1)
        self._assert_vigente(self.origen)
        decision.refresh_from_db()
        self.assertEqual(decision.firma_id, firma_original)
        self.assertEqual(decision.evidencia_firmada["formato"], 1)

        self.lote.equipo = self.torre
        self.lote.save(update_fields=["equipo"])
        self._assert_no_vigente(self.origen)
        decision.refresh_from_db()
        self.assertEqual(decision.firma_id, firma_original)
        self.assertEqual(decision.evidencia_firmada["formato"], 1)

    def test_lote_de_origen_sin_firma_caduca_solo_su_descendiente(self):
        self._origen_sin_firma_requerida()
        lote_b, final_b = self._final_de_otro_producto("H09-SIN-FIRMA-B")

        producto_c = Producto.objects.create(
            mandante=self.producto.mandante, nombre="Producto hermano ficticio",
            familia=Producto.Familia.POLVO,
        )
        lote_c = self._lote("H09-HERMANO-C", producto=producto_c)
        silo_c = Silo.objects.create(
            sucursal=self.planta, codigo="TK-H09-C", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        origen_c = self._salida(
            self.evaporacion, lote_c, "EV-H09-C", Decimal("500"),
            silo=silo_c, unidad="L", equipo=self.evaporador, producto=producto_c,
        )
        LiberacionProceso.objects.create(
            salida=origen_c, estado=LiberacionProceso.Estado.LIBERADO,
        )
        _, final_c = self._descendiente(
            "H09-C", lote=lote_c, origen=origen_c, producto=producto_c,
        )
        self._firmar_lote(lote_c)

        self.lote.fecha = date(2026, 10, 21)
        self.lote.save(update_fields=["fecha"])
        self._assert_final_retirado(lote_b, final_b)
        self._assert_vigente(final_c)
        with transaction.atomic():
            exigir_liberacion_lote_vigente(lote_c.pk)

    def test_producto_del_origen_sin_firma_caduca_descendiente_de_otro_producto(self):
        self._origen_sin_firma_requerida()
        lote_b, final_b = self._final_de_otro_producto("H09-PRODUCTO-B")
        self.producto.formato = Producto.Formato.GRANEL
        self.producto.save(update_fields=["formato"])
        self._assert_final_retirado(lote_b, final_b)

    def test_especificacion_aplicable_del_origen_sin_firma_caduca_descendiente(self):
        self._origen_sin_firma_requerida()
        especificacion = Especificacion.objects.create(
            producto=self.producto,
            tipo_analisis=Especificacion.TipoAnalisis.SILO,
            version=1, vigente_desde=date(2026, 1, 1),
            rangos={"mg": {"min": 26, "max": 30, "obligatorio": True}},
        )
        lote_b, final_b = self._final_de_otro_producto("H09-ESPEC-B")
        especificacion.rangos = {"mg": {"min": 26, "max": 31, "obligatorio": True}}
        especificacion.save(update_fields=["rangos"])
        self._assert_final_retirado(lote_b, final_b)


class ConcurrenciaFirmasH09Tests(_FixtureFirmasPorEtapa, TransactionTestCase):
    def test_correccion_del_origen_en_vuelo_no_deja_pasar_descendiente(self):
        if connection.vendor != "postgresql":
            self.skipTest("La carrera exige los bloqueos reales de PostgreSQL")
        _, final = self._descendiente("H09-CARRERA")
        fuente_guardada = Event()
        liberar_escritura = Event()
        pids_escritor, pids_lector = Queue(), Queue()

        def corregir():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        pids_escritor.put(cursor.fetchone()[0])
                    origen = SalidaProceso.objects.select_for_update().get(pk=self.origen.pk)
                    origen.cantidad = Decimal("490")
                    origen.save(update_fields=["cantidad"])
                    fuente_guardada.set()
                    if not liberar_escritura.wait(10):
                        raise TimeoutError("No se liberó la corrección de origen")
            finally:
                connections.close_all()

        def verificar_descendiente():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pids_lector.put(cursor.fetchone()[0])
                    try:
                        exigir_liberacion_salida_vigente(final.pk, bloquear=True)
                    except ValidationError:
                        return "rechazado"
                    return "aceptado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            escritor = ejecutor.submit(corregir)
            lector = None
            try:
                self.assertTrue(fuente_guardada.wait(10))
                lector = ejecutor.submit(verificar_descendiente)
                pid_lector = pids_lector.get(timeout=10)
                pid_escritor = pids_escritor.get(timeout=10)
                plazo = time.monotonic() + 3
                bloqueado_por_origen = False
                while time.monotonic() < plazo:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid_lector])
                        bloqueado_por_origen = pid_escritor in cursor.fetchone()[0]
                    if bloqueado_por_origen:
                        break
                    time.sleep(0.01)
                self.assertTrue(
                    bloqueado_por_origen,
                    "El lector no esperó la transacción que corregía el origen.",
                )
            finally:
                liberar_escritura.set()
            escritor.result(timeout=15)
            self.assertIsNotNone(lector)
            self.assertEqual(lector.result(timeout=15), "rechazado")
        self._assert_no_vigente(final)

    def test_lote_ancestro_sin_firma_serializa_por_decision_descendiente(self):
        if connection.vendor != "postgresql":
            self.skipTest("La carrera exige los bloqueos reales de PostgreSQL")
        self._origen_sin_firma_requerida()
        lote_b, final = self._final_de_otro_producto("H09-CARRERA-SIN-FIRMA")
        fuente_guardada = Event()
        liberar_escritura = Event()
        pids_escritor, pids_lector = Queue(), Queue()

        def corregir_lote_ancestro():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        pids_escritor.put(cursor.fetchone()[0])
                    lote = Lote.objects.select_for_update().get(pk=self.lote.pk)
                    lote.fecha = date(2026, 10, 21)
                    lote.save(update_fields=["fecha"])
                    fuente_guardada.set()
                    if not liberar_escritura.wait(10):
                        raise TimeoutError("No se liberó la corrección del lote ancestro")
            finally:
                connections.close_all()

        def comprobar_final():
            close_old_connections()
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '5s'")
                        cursor.execute("SELECT pg_backend_pid()")
                        pids_lector.put(cursor.fetchone()[0])
                    try:
                        exigir_liberacion_salida_vigente(final.pk, bloquear=True)
                    except ValidationError:
                        return "rechazado"
                    return "aceptado"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as ejecutor:
            escritor = ejecutor.submit(corregir_lote_ancestro)
            lector = None
            try:
                self.assertTrue(fuente_guardada.wait(10))
                lector = ejecutor.submit(comprobar_final)
                pid_lector = pids_lector.get(timeout=10)
                pid_escritor = pids_escritor.get(timeout=10)
                plazo = time.monotonic() + 3
                bloqueado_por_decision = False
                while time.monotonic() < plazo:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pid_lector])
                        bloqueado_por_decision = pid_escritor in cursor.fetchone()[0]
                    if bloqueado_por_decision:
                        break
                    time.sleep(0.01)
                self.assertTrue(
                    bloqueado_por_decision,
                    "El lector no esperó la invalidación de su decisión de Calidad.",
                )
            finally:
                liberar_escritura.set()
            escritor.result(timeout=15)
            self.assertIsNotNone(lector)
            self.assertEqual(lector.result(timeout=15), "rechazado")
        self._assert_final_retirado(lote_b, final)


class BandejaYEnvaseH09Tests(TestCase):
    def test_bandeja_explica_firma_de_origen_pendiente_sin_mostrar_conforme_como_permiso(self):
        origen = LiberacionProceso.objects.get(salida=self.origen)
        origen.estado = LiberacionProceso.Estado.PENDIENTE
        origen.save(update_fields=["estado"])
        respuesta = self.cliente.get("/api/produccion/envases/bandeja/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        fila = next(f for f in respuesta.data["bloqueados_calidad"] if f["salida_id"] == self.final.pk)
        self.assertEqual(fila["calidad"], LiberacionProceso.Estado.PENDIENTE)
        self.assertIn("Evaporación", fila["motivo_bloqueo"])
        self.assertNotIn(self.final.pk, {f["salida_id"] for f in respuesta.data["materiales"]})
        self.assertEqual(LiberacionProceso.objects.get(salida=self.final).estado, LiberacionProceso.Estado.LIBERADO)

    def setUp(self):
        # Reutiliza sólo la preparación industrial de Envase: formato, receta,
        # existencias y rol. Ninguna prueba ajena se hereda ni se ejecuta.
        from produccion.tests_envase import EnvasePalletTests

        EnvasePalletTests.setUp(self)
        proceso = Proceso.objects.create(codigo="h09-envase", nombre="Cadena H09")
        evaporacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-ev", nombre="Evaporación H09",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1, requiere_calidad=True,
        )
        secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-sec", nombre="Secado H09",
            tipo=EtapaProceso.Tipo.SECADO, orden=2, requiere_calidad=True,
        )
        silo = Silo.objects.create(
            sucursal=self.planta, codigo="TK-H09-ENV", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("2000"),
        )
        origen_ejecucion = EjecucionProceso.objects.create(
            codigo="EV-H09-ENV", etapa=evaporacion, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        self.origen = SalidaProceso.objects.create(
            ejecucion=origen_ejecucion, lote=self.lote, silo=silo,
            producto=self.producto, cantidad=Decimal("1000"), unidad="L",
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
        )
        secado_ejecucion = EjecucionProceso.objects.create(
            codigo="SEC-H09-ENV", etapa=secado, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        EntradaProceso.objects.create(
            ejecucion=secado_ejecucion, silo=silo, salida_origen=self.origen,
            cantidad=Decimal("1000"), unidad="L",
        )
        self.final = SalidaProceso.objects.create(
            ejecucion=secado_ejecucion, lote=self.lote, producto=self.producto,
            cantidad=Decimal("1000"), unidad="kg",
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
        )
        for salida in (self.origen, self.final):
            decision = LiberacionProceso.objects.create(
                salida=salida, estado=LiberacionProceso.Estado.LIBERADO,
                decidida_por=self.usuario, decidida_en=timezone.now(),
            )
            registrar_firma_salida(decision)
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)

    def test_bandeja_y_post_rechazan_material_cuyo_origen_perdio_firma(self):
        disponible = self.cliente.get("/api/produccion/envases/materiales-habilitados/")
        self.assertEqual(disponible.status_code, 200, disponible.data)
        self.assertIn(self.final.pk, {fila["salida_id"] for fila in disponible.data})

        self.origen.cantidad = Decimal("999")
        self.origen.save(update_fields=["cantidad"])
        bandeja = self.cliente.get("/api/produccion/envases/materiales-habilitados/")
        self.assertEqual(bandeja.status_code, 200, bandeja.data)
        self.assertNotIn(self.final.pk, {fila["salida_id"] for fila in bandeja.data})

        ahora = timezone.now()
        respuesta = self.cliente.post(
            "/api/produccion/envases/",
            {
                "operacion_id": str(uuid4()), "lote": self.lote.pk,
                "equipo": self.envasadora.pk, "formato": self.formato.pk,
                "inicio": (ahora - timedelta(hours=1)).isoformat(),
                "termino": ahora.isoformat(),
                "pallets_datos": [
                    {"codigo": "PAL-H09-BLOQUEADO", "unidades": 20, "kg_neto": "500"},
                ],
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(RegistroEnvase.objects.filter(lote=self.lote).exists())


class DespachoAncestroH09Tests(TestCase):
    def setUp(self):
        from inventario.pruebas_base import EscenarioProductoTerminado

        EscenarioProductoTerminado.setUp(self)

    def test_despacho_autorizado_rechaza_origen_corregido_sin_descontar_pallet(self):
        from inventario.models import (
            Despacho, DetalleDespacho, ExistenciaProductoTerminado,
            MovimientoProductoTerminado,
        )
        from inventario.pruebas_base import EscenarioProductoTerminado
        from inventario.pruebas_firmas import firmar_salida_de_prueba
        from inventario.servicios import autorizar_despacho, ejecutar_despacho, ingresar_pallet
        from produccion.models import PalletProducto

        proceso = Proceso.objects.create(codigo="h09-despacho", nombre="Cadena despacho H09")
        origen_etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-origen-despacho", nombre="Origen H09",
            tipo=EtapaProceso.Tipo.EVAPORACION, orden=1, requiere_calidad=False,
        )
        final_etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="h09-final-despacho", nombre="Final H09",
            tipo=EtapaProceso.Tipo.SECADO, orden=2, requiere_calidad=True,
        )
        lote_origen = Lote.objects.create(
            sucursal=self.planta, codigo_lote="H09-DESP-ORIGEN",
            producto=self.producto, fecha=self.lote.fecha,
            estado=Lote.Estado.EN_PROCESO, kg_producidos=Decimal("0"),
        )
        silo = Silo.objects.create(
            sucursal=self.planta, codigo="TK-H09-DESP", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        ejecucion_origen = EjecucionProceso.objects.create(
            codigo="H09-DESP-ORIGEN", etapa=origen_etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        origen = SalidaProceso.objects.create(
            ejecucion=ejecucion_origen, lote=lote_origen, producto=self.producto,
            silo=silo, cantidad=Decimal("500"), unidad="L",
            destino=SalidaProceso.Destino.SIGUIENTE_PROCESO,
        )
        LiberacionProceso.objects.create(
            salida=origen, estado=LiberacionProceso.Estado.LIBERADO,
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        ejecucion_final = EjecucionProceso.objects.create(
            codigo="H09-DESP-FINAL", etapa=final_etapa, sucursal=self.planta,
            estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
        )
        entrada = EntradaProceso(
            ejecucion=ejecucion_final, silo=silo, salida_origen=origen,
            cantidad=Decimal("500"), unidad="L",
        )
        entrada.full_clean()
        entrada.save()
        final = SalidaProceso.objects.create(
            ejecucion=ejecucion_final, lote=self.lote, producto=self.producto,
            cantidad=Decimal("500"), unidad="kg",
            clasificacion=SalidaProceso.Clasificacion.GRANEL,
            destino=SalidaProceso.Destino.ENVASADO,
        )
        firmar_salida_de_prueba(final, self.usuario)
        EscenarioProductoTerminado.liberar(self)
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)
        hoja = Despacho.objects.create(
            sucursal=self.planta, numero="H09-DESPACHO", cliente=self.cliente,
            creado_por=self.usuario,
        )
        DetalleDespacho.objects.create(despacho=hoja, pallet=self.pallet)
        autorizar_despacho(hoja, self.usuario)
        hoja.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.AUTORIZADO)
        movimientos_antes = MovimientoProductoTerminado.objects.filter(pallet=self.pallet).count()

        lote_origen.fecha += timedelta(days=1)
        lote_origen.save(update_fields=["fecha"])

        with self.assertRaises(ValidationError):
            ejecutar_despacho(hoja, self.usuario)
        hoja.refresh_from_db()
        self.pallet.refresh_from_db()
        self.assertEqual(hoja.estado, Despacho.Estado.AUTORIZADO)
        self.assertEqual(self.pallet.estado, PalletProducto.Estado.EN_INVENTARIO)
        self.assertTrue(ExistenciaProductoTerminado.objects.get(pallet=self.pallet).activo)
        self.assertEqual(
            MovimientoProductoTerminado.objects.filter(pallet=self.pallet).count(),
            movimientos_antes,
        )
        self.assertFalse(MovimientoProductoTerminado.objects.filter(
            despacho=hoja, tipo=MovimientoProductoTerminado.Tipo.DESPACHO,
        ).exists())


class RefirmaYPermisosH09Tests(TestCase):
    def setUp(self):
        from .tests_rechazo_resultado import RechazoResultadoProcesoTests

        RechazoResultadoProcesoTests.setUp(self)

    def _muestra(self):
        ahora = timezone.now()
        return AnalisisSilo.objects.create(
            silo=self.salida.silo, tomado_en=ahora,
            estado=AnalisisSilo.Estado.CONFIRMADO,
            grasa=Decimal("3.50"), sng=Decimal("9.00"),
            inhibidores_resultado="negativo", metodo="tri_sensor",
            hora_lectura=ahora.time(), analista=self.calidad,
            visualizado_por=self.calidad, visualizado_en=ahora,
        )

    def test_solo_calidad_renueva_firma_con_nueva_muestra_y_nuevo_identificador(self):
        url = f"/api/calidad/resultados-proceso/{self.salida.pk}/liberar/"
        primera = self.cliente.post(url, {"analisis_id": self._muestra().pk}, format="json")
        self.assertEqual(primera.status_code, 200, primera.data)
        decision = LiberacionProceso.objects.get(salida=self.salida)
        firma_anterior = decision.firma_id

        self.salida.cantidad = Decimal("490")
        self.salida.save(update_fields=["cantidad"])
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(self.salida.pk)

        operador = User.objects.create_user("operador-h09-refirma")
        PerfilUsuario.objects.create(
            usuario=operador, empresa=self.planta.empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.SECADO,
        )
        cliente_operador = APIClient()
        cliente_operador.force_authenticate(operador)
        intento = cliente_operador.post(url, {"analisis_id": self._muestra().pk}, format="json")
        self.assertEqual(intento.status_code, 403, intento.data)
        decision.refresh_from_db()
        self.assertEqual(decision.firma_id, firma_anterior)

        nueva = self._muestra()
        renovada = self.cliente.post(url, {"analisis_id": nueva.pk}, format="json")
        self.assertEqual(renovada.status_code, 200, renovada.data)
        decision.refresh_from_db()
        self.assertNotEqual(decision.firma_id, firma_anterior)
        self.assertEqual(decision.analisis_silo_id, nueva.pk)
        self.assertEqual(decision.evidencia_firmada["formato"], 2)
        self.assertEqual(
            exigir_liberacion_salida_vigente(self.salida.pk), str(decision.firma_id),
        )
