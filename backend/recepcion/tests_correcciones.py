from decimal import Decimal

from django.utils import timezone

from auditoria.models import RegistroAuditoria
from maestros.models import Silo

from .models import (
    AlertaCalidadSilo,
    CorreccionRecepcion,
    ModuloRecepcion,
    MovimientoSilo,
    Recepcion,
)
from .tests import BaseAPIRecepcion


class CorreccionCrioscopiaTests(BaseAPIRecepcion):
    def recepcion_conforme(self, estado):
        recepcion = Recepcion.objects.create(
            fecha="2026-08-25",
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("12000.00"),
            silo=self.silo,
            controles={"delvo": "Negativo"},
            estado=estado,
        )
        modulo = ModuloRecepcion.objects.create(
            recepcion=recepcion, numero=1, crioscopia=Decimal("-0.521")
        )
        return recepcion, modulo

    def corregir(self, recepcion, modulo, valor="-0.400"):
        return self.cliente.patch(
            f"/api/recepcion/recepciones/{recepcion.id}/corregir-crioscopias/",
            {
                "motivo": "Corrección por transcripción de laboratorio",
                "modulos": [{"id": modulo.id, "crioscopia": valor}],
            },
            format="json",
        )

    def test_corrige_en_analizada_recalcula_y_deja_motivo_auditable(self):
        recepcion, modulo = self.recepcion_conforme(Recepcion.Estado.ANALIZADA)

        respuesta = self.corregir(recepcion, modulo)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertFalse(respuesta.data["evaluacion"]["conforme"])
        self.assertEqual(respuesta.data["estado"], Recepcion.Estado.ANALIZADA)
        correccion = CorreccionRecepcion.objects.get(recepcion=recepcion)
        self.assertIn("transcripción", correccion.motivo)
        self.assertIn("M1.crioscopia", correccion.cambios)
        self.assertTrue(RegistroAuditoria.objects.filter(
            modelo="recepcion.ModuloRecepcion",
            objeto_id=str(modulo.id),
            cambios__has_key="crioscopia",
        ).exists())

    def test_si_ya_se_descargo_retiene_alerta_el_silo_y_no_toca_el_libro(self):
        recepcion, modulo = self.recepcion_conforme(Recepcion.Estado.DESCARGADA)
        movimiento = MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=recepcion.litros,
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
            origen_id=recepcion.id,
        )

        respuesta = self.corregir(recepcion, modulo)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        recepcion.refresh_from_db()
        self.silo.refresh_from_db()
        movimiento.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.RETENIDA)
        self.assertTrue(respuesta.data["alerta_silo_activa"])
        self.assertTrue(AlertaCalidadSilo.objects.filter(
            recepcion=recepcion, silo=self.silo, activa=True
        ).exists())
        self.assertEqual(self.silo.estado, Silo.Estado.DISPONIBLE)
        self.assertEqual(movimiento.litros, Decimal("12000.00"))
        self.assertEqual(MovimientoSilo.objects.count(), 1)

    def test_un_documento_cerrado_rechaza_cualquier_patch(self):
        recepcion, _ = self.recepcion_conforme(Recepcion.Estado.CERRADA)

        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{recepcion.id}/",
            {"observacion": "Intento tardío"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.observacion, "")

    def test_litros_ya_descargados_indican_usar_un_ajuste(self):
        recepcion, _ = self.recepcion_conforme(Recepcion.Estado.DESCARGADA)
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=recepcion.litros,
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
            origen_id=recepcion.id,
        )

        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{recepcion.id}/",
            {"litros": "10000.00"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertIn("ajuste", respuesta.data["litros"].lower())
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.litros, Decimal("12000.00"))

    def test_reanalizar_permite_corregir_ph_camion_y_audita(self):
        recepcion = Recepcion.objects.create(
            fecha="2026-08-25",
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("12000.00"),
            ph_camion=Decimal("9.00"),
            controles={"delvo": "Negativo"},
            estado=Recepcion.Estado.RETENIDA,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/decidir-calidad/",
            {
                "controles": {"delvo": "Negativo"},
                "ph_camion": "7.00",
                "motivo_correccion": "Lectura digitada incorrectamente",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], Recepcion.Estado.LIBERADA)
        recepcion.refresh_from_db()
        self.assertEqual(recepcion.ph_camion, Decimal("7.00"))
        correccion = CorreccionRecepcion.objects.get(recepcion=recepcion)
        self.assertEqual(correccion.paso, "calidad")
        self.assertIn("ph_camion", correccion.cambios)
