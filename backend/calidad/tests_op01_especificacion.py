"""La vigencia conserva la especificación que Calidad realmente evaluó."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from maestros.models import Especificacion, Mandante, Producto
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, SalidaProceso
from produccion.models import Analisis, Lote
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import LiberacionProceso
from .vigencia import exigir_liberacion_salida_vigente


class EspecificacionCongeladaOP01Tests(TestCase):
    def _escenario_firmado(self):
        with patch("django.utils.timezone.now", return_value=datetime(2026, 8, 1, 12, tzinfo=UTC)):
            empresa = Empresa.objects.create(rut="OP01-SPEC", nombre="Empresa sintética")
            planta = Sucursal.objects.create(empresa=empresa, codigo="SPEC", nombre="Planta sintética")
            usuario = User.objects.create_user("op01-calidad-spec")
            PerfilUsuario.objects.create(
                usuario=usuario, empresa=empresa, sucursal=planta,
                rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
            )
            mandante = Mandante.objects.create(empresa=empresa, nombre="Mandante sintético")
            producto = Producto.objects.create(
                mandante=mandante, nombre="Material sintético OP01",
                familia=Producto.Familia.CREMA, formato=Producto.Formato.GRANEL,
            )
            congelada = Especificacion.objects.create(
                producto=producto, version=1, vigente_desde=date(2026, 1, 1),
                rangos={"mg": {"min": 26, "max": 30, "obligatorio": True}},
            )
            vigente = Especificacion.objects.create(
                producto=producto, version=2, vigente_desde=date(2026, 7, 1),
                rangos={"mg": {"min": 26, "max": 31, "obligatorio": True}},
            )
            lote = Lote.objects.create(
                sucursal=planta, codigo_lote="OP01-SPEC-LOTE", producto=producto,
                fecha=date(2026, 8, 1), kg_producidos=Decimal("100"),
                estado=Lote.Estado.PRODUCIDO,
            )
            proceso = Proceso.objects.create(codigo="op01-spec", nombre="Proceso sintético")
            etapa = EtapaProceso.objects.create(
                proceso=proceso, codigo="op01-spec-etapa", nombre="Etapa sintética",
                tipo=EtapaProceso.Tipo.MANTEQUILLA, orden=1, requiere_calidad=True,
            )
            ejecucion = EjecucionProceso.objects.create(
                codigo="OP01-SPEC-EJ", sucursal=planta, etapa=etapa,
                estado=EjecucionProceso.Estado.PENDIENTE_CONTROL,
            )
            salida = SalidaProceso.objects.create(
                ejecucion=ejecucion, lote=lote, producto=producto,
                cantidad=Decimal("100"), unidad="kg", destino=SalidaProceso.Destino.ENVASADO,
            )
            analisis = Analisis.objects.create(
                lote=lote, fecha=date(2026, 8, 1), valores={"mg": 28}, especificacion=congelada,
            )
            cliente = APIClient()
            cliente.force_authenticate(usuario)

            respuesta = cliente.post(
                f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
                {"analisis_lote_id": analisis.pk}, format="json",
            )

            self.assertEqual(respuesta.status_code, 200, respuesta.data)
            decision = LiberacionProceso.objects.get(salida=salida)
            self.assertNotEqual(congelada.pk, vigente.pk)
            self.assertEqual(decision.evidencia_firmada["especificacion"]["id"], congelada.pk)
            self.assertEqual(exigir_liberacion_salida_vigente(salida.pk), str(decision.firma_id))
            return congelada, decision, salida, lote, producto, cliente

    def test_corregir_la_version_evaluada_invalida_aunque_otra_version_este_vigente(self):
        congelada, decision, salida, *_ = self._escenario_firmado()

        # El resultado sigue dentro de rango: se exige otro acto por haber
        # cambiado la evidencia evaluada, no por volverse no conforme.
        congelada.rangos = {"mg": {"min": 26, "max": 29, "obligatorio": True}}
        congelada.save(update_fields=["rangos"])

        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertFalse(decision.firma_vigente)
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(salida.pk)

    def test_cambiar_identidad_del_lote_invalida_la_salida_con_producto_explicito(self):
        _, decision, salida, lote, _, _ = self._escenario_firmado()
        identificador = decision.firma_id

        lote.codigo_lote = "OP01-SPEC-IDENTIDAD-CORREGIDA"
        lote.save(update_fields=["codigo_lote"])

        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(decision.firma_id, identificador)
        self.assertFalse(decision.firma_vigente)
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(salida.pk)

    def test_refirma_no_acepta_especificacion_del_producto_anterior_del_lote(self):
        _, decision, salida, lote, producto, cliente = self._escenario_firmado()
        identificador = decision.firma_id
        otro = Producto.objects.create(
            mandante=producto.mandante, nombre="Otro material sintético OP01",
            familia=Producto.Familia.CREMA, formato=Producto.Formato.GRANEL,
        )
        lote.producto = otro
        lote.save(update_fields=["producto"])
        salida.producto = otro
        salida.save(update_fields=["producto"])

        respuesta = cliente.post(
            f"/api/calidad/resultados-proceso/{salida.pk}/liberar/",
            {"analisis_lote_id": decision.analisis_lote_id}, format="json",
        )

        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertIn("especificación", respuesta.data["detail"])
        decision.refresh_from_db()
        self.assertEqual(decision.estado, LiberacionProceso.Estado.PENDIENTE)
        self.assertEqual(decision.firma_id, identificador)
        self.assertFalse(decision.firma_vigente)
