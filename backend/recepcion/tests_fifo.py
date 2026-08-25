import uuid
from datetime import date, datetime, timedelta, timezone as tz
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from maestros.models import Silo

from . import dominio
from .models import AtribucionRecepcion, MovimientoSilo, Recepcion
from .servicios import atribuir_salida, transferir_silo


class AtribucionFIFODominioTests(TestCase):
    def capas(self):
        return [
            dominio.CapaSilo(1, Decimal("100"), 1),
            dominio.CapaSilo(2, Decimal("200"), 2),
            dominio.CapaSilo(3, Decimal("300"), 3),
        ]

    def test_salida_menor_que_la_capa_mas_antigua(self):
        resultado = dominio.atribuir_fifo(self.capas(), Decimal("40"))
        self.assertEqual([(p.recepcion_id, p.litros) for p in resultado.partes], [(1, Decimal("40"))])
        self.assertEqual(resultado.remanente_no_atribuible, 0)

    def test_salida_cruza_tres_camiones(self):
        resultado = dominio.atribuir_fifo(self.capas(), Decimal("450"))
        self.assertEqual(
            [(p.recepcion_id, p.litros) for p in resultado.partes],
            [(1, Decimal("100")), (2, Decimal("200")), (3, Decimal("150"))],
        )

    def test_exceso_se_declara_no_atribuible(self):
        resultado = dominio.atribuir_fifo(self.capas(), Decimal("700"))
        self.assertEqual(sum((p.litros for p in resultado.partes), Decimal("0")), Decimal("600"))
        self.assertEqual(resultado.remanente_no_atribuible, Decimal("100"))

    def test_ajuste_inicial_es_una_capa_explicita(self):
        movimientos = [{
            "id": 1, "tipo": "ajuste", "litros": Decimal("80"),
            "fecha_hora": datetime(2026, 1, 1, tzinfo=tz.utc),
            "motivo": "inventario inicial",
        }]
        self.assertEqual(
            dominio.saldo_por_recepcion(movimientos, []),
            [dominio.CapaSilo(None, Decimal("80"), 1, "inventario inicial")],
        )


class AtribucionFIFOIntegracionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user(username="fifo", password="x")
        self.silo = Silo.objects.create(codigo="FIFO-1", tipo=Silo.Tipo.SILO, capacidad_l=2000)
        self.destino = Silo.objects.create(codigo="FIFO-2", tipo=Silo.Tipo.SILO, capacidad_l=2000)
        self.inicio = datetime(2026, 1, 1, 8, tzinfo=tz.utc)
        self.recepciones = []
        for indice, litros in enumerate(("100", "200", "300"), start=1):
            recepcion = Recepcion.objects.create(
                fecha=date(2026, 1, indice), tipo_leche=Recepcion.TipoLeche.ENTERA,
                litros=litros, silo=self.silo,
            )
            self.recepciones.append(recepcion)
            MovimientoSilo.objects.create(
                silo=self.silo, tipo=MovimientoSilo.Tipo.INGRESO, litros=litros,
                fecha_hora=self.inicio + timedelta(hours=indice),
                origen_tipo=MovimientoSilo.OrigenTipo.RECEPCION,
                origen_id=recepcion.id,
            )

    def salida(self, litros, horas):
        movimiento = MovimientoSilo.objects.create(
            silo=self.silo, tipo=MovimientoSilo.Tipo.SALIDA, litros=litros,
            fecha_hora=self.inicio + timedelta(hours=horas),
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
        )
        return movimiento, atribuir_salida(movimiento)

    def test_dos_consumos_secuenciales_no_reutilizan_litros(self):
        primera, attrs_primera = self.salida("150", 10)
        segunda, attrs_segunda = self.salida("200", 11)

        self.assertEqual(
            [(a.recepcion_id, a.litros) for a in attrs_primera],
            [(self.recepciones[0].id, Decimal("100")), (self.recepciones[1].id, Decimal("50"))],
        )
        self.assertEqual(
            [(a.recepcion_id, a.litros) for a in attrs_segunda],
            [(self.recepciones[1].id, Decimal("150")), (self.recepciones[2].id, Decimal("50"))],
        )
        self.assertEqual(primera.atribuciones_recepcion.count(), 2)
        self.assertEqual(segunda.atribuciones_recepcion.count(), 2)

    def test_la_suma_atribuida_siempre_iguala_la_salida(self):
        movimiento, atribuciones = self.salida("700", 10)
        self.assertEqual(sum((a.litros for a in atribuciones), Decimal("0")), movimiento.litros)
        self.assertEqual(atribuciones[-1].recepcion_id, None)
        self.assertTrue(atribuciones[-1].origen_no_atribuible)

    def test_transferencia_propaga_las_capas_al_silo_destino(self):
        salida, ingreso = transferir_silo(
            silo_origen_id=self.silo.id, silo_destino_id=self.destino.id,
            litros=Decimal("250"), operacion_id=uuid.uuid4(),
            usuario=self.usuario,
        )
        self.assertEqual(
            list(ingreso.atribuciones_recepcion.values_list("recepcion_id", "litros")),
            [(self.recepciones[0].id, Decimal("100")), (self.recepciones[1].id, Decimal("150"))],
        )
        self.assertEqual(
            AtribucionRecepcion.objects.filter(movimiento=salida).count(), 2
        )
