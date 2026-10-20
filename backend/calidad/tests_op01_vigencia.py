"""OP-01: una firma no habilita evidencia distinta de la revisada."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from auditoria.models import RegistroAuditoria
from maestros.models import Especificacion
from produccion.models import Lote
from procesos.models import AutorizacionReproceso, EjecucionProceso

from .models import Liberacion, RegistroCalidad
from .tests_api import BaseAPI
from . import tests_rechazo_resultado as escenarios_rechazo
from .vigencia import exigir_liberacion_lote_vigente


class VigenciaFirmaTests(BaseAPI):
    def setUp(self):
        super().setUp()
        self.analisis = self._analisis()
        self._checklist_completo()
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/liberar/", {}, format="json"
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.firma = Liberacion.objects.get(lote=self.lote)

    def test_no_se_puede_reasignar_la_firma_a_otro_lote(self):
        otro = Lote.objects.create(
            codigo_lote="OP01-OTRO", producto=self.producto,
            fecha=date(2026, 7, 21), kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )
        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{self.firma.pk}/",
            {"lote": otro.pk}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.lote_id, self.lote.pk)

    def test_corregir_resultado_conforme_exige_nueva_aprobacion(self):
        respuesta = self.cliente.patch(
            f"/api/produccion/analisis/{self.analisis.pk}/",
            {"valores": {"mg": 29.0}}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.estado, Liberacion.Estado.EN_REVISION)
        self.assertFalse(self.firma.liberado)

    def test_editar_y_revertir_no_reactiva_la_firma_anterior(self):
        self.analisis.valores = {"mg": 29.0}
        self.analisis.save(update_fields=["valores"])
        self.analisis.valores = {"mg": 28.0}
        self.analisis.save(update_fields=["valores"])
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.estado, Liberacion.Estado.EN_REVISION)
        self.assertFalse(self.firma.liberado)

    def test_cambio_documental_completado_requiere_revision(self):
        registro = RegistroCalidad.objects.get(lote=self.lote, documento=self.ficha)
        registro.valores = {"lote": self.lote.codigo_lote, "mg": 29.0}
        registro.save(update_fields=["valores"])
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.estado, Liberacion.Estado.EN_REVISION)

    def test_nueva_especificacion_aplicable_exige_revision(self):
        Especificacion.objects.create(
            producto=self.producto, version=2, vigente_desde=date(2026, 7, 1),
            rangos={"mg": {"min": 26.0, "max": 30.0, "obligatorio": True}},
        )
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.estado, Liberacion.Estado.EN_REVISION)

    def test_nota_administrativa_no_retira_la_aprobacion(self):
        self.analisis.observacion = "Corrección ortográfica administrativa"
        self.analisis.save(update_fields=["observacion"])
        self.firma.refresh_from_db()
        self.assertEqual(self.firma.estado, Liberacion.Estado.LIBERADO)
        self.assertTrue(self.firma.liberado)

    def test_guardar_el_mismo_resultado_no_invalida(self):
        self.analisis.save(update_fields=["valores"])
        self.firma.refresh_from_db()
        self.assertTrue(self.firma.liberado)

    def test_nuevo_analisis_conforme_tambien_exige_revision(self):
        self._analisis(mg=29.0)
        self.firma.refresh_from_db()
        self.assertFalse(self.firma.liberado)

    def test_cambiar_cantidad_producida_retira_la_aprobacion(self):
        self.lote.kg_producidos = Decimal("13000")
        self.lote.save(update_fields=["kg_producidos"])
        self.firma.refresh_from_db()
        self.assertFalse(self.firma.liberado)

    def test_una_especificacion_futura_no_afecta_la_firma_del_lote(self):
        Especificacion.objects.create(
            producto=self.producto, version=2, vigente_desde=date(2027, 1, 1),
            rangos={"mg": {"min": 26.0, "max": 30.0}},
        )
        self.firma.refresh_from_db()
        self.assertEqual(exigir_liberacion_lote_vigente(self.lote.pk), str(self.firma.firma_id))

    def test_el_registro_historico_sin_respaldo_no_se_autoaprueba(self):
        self.firma.firma_id = None
        self.firma.evidencia_firmada = {}
        self.firma.save(update_fields=["firma_id", "evidencia_firmada"])
        with self.assertRaises(ValidationError):
            exigir_liberacion_lote_vigente(self.lote.pk)
        self.firma.refresh_from_db()
        self.assertIsNone(self.firma.firma_id)
        self.assertFalse(self.firma.liberado)
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.firma.refresh_from_db()
        self.assertIsNotNone(self.firma.firma_id)

    def test_renovar_genera_otro_identificador_y_conserva_la_foto_anterior(self):
        anterior = self.firma.firma_id
        self.analisis.valores = {"mg": 29.0}
        self.analisis.save(update_fields=["valores"])
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.firma.refresh_from_db()
        self.assertNotEqual(self.firma.firma_id, anterior)
        self.assertEqual(exigir_liberacion_lote_vigente(self.lote.pk), str(self.firma.firma_id))
        eventos = RegistroAuditoria.objects.filter(
            modelo="calidad.Liberacion", objeto_id=str(self.firma.pk),
        )
        cambios_foto = [evento.cambios["evidencia_firmada"] for evento in eventos if "evidencia_firmada" in evento.cambios]
        self.assertTrue(any(
            antes and antes["analisis"][0]["valores"]["mg"] == 28.0
            for antes, _ in cambios_foto
        ))

    def test_no_se_puede_fabricar_una_firma_por_patch(self):
        respuesta = self.cliente.patch(
            f"/api/calidad/liberaciones/{self.firma.pk}/",
            {"firma_id": "00000000-0000-0000-0000-000000000001"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_un_cambio_documental_fallido_revierte_tambien_la_invalidez(self):
        from django.db import transaction

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                self.analisis.valores = {"mg": 29.0}
                self.analisis.save(update_fields=["valores"])
                raise RuntimeError("Error sintético después de corregir evidencia")
        self.analisis.refresh_from_db()
        self.firma.refresh_from_db()
        self.assertEqual(self.analisis.valores, {"mg": 28.0})
        self.assertTrue(self.firma.liberado)

    def test_guardar_un_formulario_identico_no_genera_otra_firma_documental(self):
        registro = RegistroCalidad.objects.get(lote=self.lote, documento=self.ficha)
        respuesta = self.cliente.patch(
            f"/api/calidad/registros/{registro.pk}/",
            {"valores": registro.valores, "estado": registro.estado}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.firma.refresh_from_db()
        self.assertTrue(self.firma.liberado)

    def test_retirar_disposicion_del_excedente_retira_la_aprobacion(self):
        disposicion = AutorizacionReproceso.objects.create(
            lote=self.lote, origen=AutorizacionReproceso.Origen.EXCEDENTE,
            estado=AutorizacionReproceso.Estado.APROBADO, cantidad_kg=Decimal("10"),
            motivo="Disposición sintética del excedente",
        )
        respuesta = self.cliente.post(
            f"/api/calidad/expedientes/{self.lote.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        disposicion.estado = AutorizacionReproceso.Estado.BLOQUEADO
        disposicion.save(update_fields=["estado"])
        self.firma.refresh_from_db()
        self.assertFalse(self.firma.liberado)


class RestriccionesRefirmaProcesoTests(TestCase):
    def setUp(self):
        escenarios_rechazo.RechazoResultadoProcesoTests.setUp(self)

    def test_un_rechazo_explicito_no_es_una_firma_pendiente_de_renovar(self):
        respuesta = self.cliente.post(
            f"/api/calidad/resultados-proceso/{self.salida.pk}/rechazar/",
            {"motivo": "Material rechazado por Calidad"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        intento = self.cliente.post(
            f"/api/calidad/resultados-proceso/{self.salida.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(intento.status_code, 409)

    def test_no_se_reabre_una_ejecucion_cancelada_mediante_refirma(self):
        from .models import LiberacionProceso

        LiberacionProceso.objects.create(salida=self.salida, estado=LiberacionProceso.Estado.LIBERADO)
        self.ejecucion.estado = EjecucionProceso.Estado.CANCELADA
        self.ejecucion.save(update_fields=["estado"])
        respuesta = self.cliente.post(
            f"/api/calidad/resultados-proceso/{self.salida.pk}/liberar/", {}, format="json",
        )
        self.assertEqual(respuesta.status_code, 409)

    def test_nuevo_origen_exige_muestra_actual_y_otro_acto_de_calidad(self):
        from django.utils import timezone
        from maestros.models import Silo
        from recepcion.models import AnalisisSilo
        from .models import LiberacionProceso
        from .vigencia import exigir_liberacion_salida_vigente

        def muestra(silo_id):
            ahora = timezone.now()
            return AnalisisSilo.objects.create(
                silo_id=silo_id, tomado_en=ahora, estado=AnalisisSilo.Estado.CONFIRMADO,
                grasa=Decimal("3.5"), sng=Decimal("9"), inhibidores_resultado="negativo",
                metodo="tri_sensor", hora_lectura=ahora.time(),
                analista=self.calidad, visualizado_por=self.calidad, visualizado_en=ahora,
            )

        url = f"/api/calidad/resultados-proceso/{self.salida.pk}/liberar/"
        anterior = muestra(self.salida.silo_id)
        respuesta = self.cliente.post(url, {"analisis_id": anterior.pk}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        firma_anterior = LiberacionProceso.objects.get(salida=self.salida).firma_id
        otro = Silo.objects.create(
            sucursal=self.planta, codigo="OP01-NUEVO-SILO", tipo=Silo.Tipo.SILO,
            capacidad_l=Decimal("1000"),
        )
        self.salida.silo = otro
        self.salida.save(update_fields=["silo"])
        respuesta = self.cliente.post(url, {"analisis_id": anterior.pk}, format="json")
        self.assertEqual(respuesta.status_code, 404)
        actual = muestra(otro.pk)
        respuesta = self.cliente.post(url, {"analisis_id": actual.pk}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        decision = LiberacionProceso.objects.get(salida=self.salida)
        self.assertNotEqual(decision.firma_id, firma_anterior)
        self.assertEqual(decision.analisis_silo_id, actual.pk)
        self.assertEqual(exigir_liberacion_salida_vigente(self.salida.pk), str(decision.firma_id))
