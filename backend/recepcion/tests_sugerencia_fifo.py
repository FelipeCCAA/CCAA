from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.utils import timezone

from maestros.models import Silo

from . import dominio
from .models import AnalisisSilo, MovimientoSilo
from .tests import BaseAPIRecepcion


class SugerenciaFIFODominioTests(SimpleTestCase):
    def test_prioriza_la_capa_utilizable_mas_antigua(self):
        ahora = timezone.now()
        resultado = dominio.sugerir_origenes([
            {"silo_id": 1, "litros_disponibles": 500, "leche_mas_antigua_en": ahora - timedelta(hours=5), "antiguedad_horas": 5, "motivos_no_disponible": []},
            {"silo_id": 2, "litros_disponibles": 500, "leche_mas_antigua_en": ahora - timedelta(hours=20), "antiguedad_horas": 20, "motivos_no_disponible": []},
        ], 300)
        self.assertEqual(resultado[0].silo_id, 2)
        self.assertEqual(resultado[0].litros_sugeridos, Decimal("300"))

    def test_reparte_volumen_y_deja_bloqueados_al_final(self):
        ahora = timezone.now()
        resultado = dominio.sugerir_origenes([
            {"silo_id": 1, "litros_disponibles": 200, "leche_mas_antigua_en": ahora - timedelta(hours=20), "motivos_no_disponible": []},
            {"silo_id": 2, "litros_disponibles": 500, "leche_mas_antigua_en": ahora - timedelta(hours=10), "motivos_no_disponible": []},
            {"silo_id": 3, "litros_disponibles": 900, "leche_mas_antigua_en": ahora - timedelta(hours=30), "motivos_no_disponible": ["En CIP"]},
        ], 600)
        self.assertEqual([item.silo_id for item in resultado], [1, 2, 3])
        self.assertEqual([item.litros_sugeridos for item in resultado], [Decimal("200"), Decimal("400"), Decimal("0")])


class SugerenciaFIFOAPITests(BaseAPIRecepcion):
    def test_endpoint_sugiere_el_silo_con_leche_mas_antigua(self):
        ahora = timezone.now()
        antiguo = Silo.objects.create(
            codigo="FIFO-ANTIGUO", tipo=Silo.Tipo.SILO, capacidad_l=5000
        )
        nuevo = Silo.objects.create(
            codigo="FIFO-NUEVO", tipo=Silo.Tipo.SILO, capacidad_l=5000
        )
        firma = User.objects.create_user(username="segunda-firma", password="x")
        analista = User.objects.get(username="op")
        for silo, horas in ((antiguo, 20), (nuevo, 5)):
            MovimientoSilo.objects.create(
                silo=silo, tipo=MovimientoSilo.Tipo.INGRESO, litros="1000",
                fecha_hora=ahora - timedelta(hours=horas), motivo="saldo de prueba",
            )
            AnalisisSilo.objects.create(
                silo=silo, tomado_en=ahora - timedelta(hours=1),
                grasa="4.20", sng="8.80", inhibidores_resultado="negativo",
                metodo="delvo_sp", hora_lectura=timezone.localtime().time(),
                analista=analista, visualizado_por=firma, visualizado_en=ahora,
                estado=AnalisisSilo.Estado.CONFIRMADO,
            )

        respuesta = self.cliente.get(
            "/api/recepcion/silos/sugerencia/?volumen=800&tipo=silo"
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        sugerido = next(item for item in respuesta.data["sugerencias"] if item["sugerido"])
        self.assertEqual(sugerido["silo"], antiguo.id)
        self.assertEqual(sugerido["litros_sugeridos"], Decimal("800"))
