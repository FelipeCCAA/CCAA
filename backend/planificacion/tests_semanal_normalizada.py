from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Mandante, Producto
from usuarios.models import Empresa, PerfilUsuario, Sucursal

from . import dominio
from .models import (
    BalanceDia, BloquePlan, CapacidadProceso, CodigoProduccion, MovimientoPlan, SemanaPlan,
    StockSeguridadPlan, TipoActividadPlan, VersionSemanaPlan,
)


class BasePlanSemanalNormalizado(TestCase):
    def setUp(self):
        self.empresa = Empresa.objects.create(rut="PLAN-NUEVO", nombre="Plan nuevo")
        self.sucursal = Sucursal.objects.create(empresa=self.empresa, codigo="P", nombre="Planta")
        self.propietario = Mandante.objects.create(empresa=self.empresa, nombre="Propietario A")
        self.otro = Mandante.objects.create(empresa=self.empresa, nombre="Propietario B")
        self.producto = Producto.objects.create(nombre="Leche prueba", familia=Producto.Familia.POLVO, mandante=self.propietario)
        self.equipo = Equipo.objects.create(sucursal=self.sucursal, codigo="eq-plan", nombre="Evaporador prueba", tipo=Equipo.Tipo.EVAPORADOR, consume_leche=True)
        self.semana = SemanaPlan.objects.create(sucursal=self.sucursal, codigo="W40", anio=2026, fecha_inicio=date(2026, 9, 28))
        self.codigo = CodigoProduccion.objects.create(codigo="PRUEBA40", producto=self.producto, mandante=self.propietario, categoria="prec_ccaa", rendimiento_lh=Decimal("10"))
        self.tipo = TipoActividadPlan.objects.get(codigo="produccion")

    def momento(self, dia, hora):
        return timezone.make_aware(datetime.combine(self.semana.fecha_del_dia(dia), datetime.min.time()) + timedelta(hours=hora))

    def bloque(self, inicio=8, fin=12, dia=0, capacidad=100):
        return BloquePlan.objects.create(
            semana=self.semana, equipo=self.equipo, dia=dia,
            hora_inicio=inicio, hora_fin=min(fin, 24), tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.codigo, tipo_actividad=self.tipo,
            fecha_hora_inicio=self.momento(dia, inicio),
            fecha_hora_fin=self.momento(dia, fin),
            producto=self.producto, origen_leche=self.propietario,
            capacidad_hora=capacidad, color=self.tipo.color,
        )


class CalculosNormalizadosTests(BasePlanSemanalNormalizado):
    def test_consumo_usa_capacidad_congelada_de_la_actividad(self):
        bloque = self.bloque(capacidad=100)
        self.codigo.rendimiento_lh = 999
        self.codigo.save(update_fields=["rendimiento_lh"])
        consumo = dominio.consumo_dia([bloque], [self.codigo], 0)
        self.assertEqual(consumo.total, 400)

    def test_balance_es_explicable_movimiento_por_movimiento_y_por_propietario(self):
        bloque = self.bloque(capacidad=100)
        movimientos = [
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 0), propietario=self.propietario, tipo=MovimientoPlan.Tipo.STOCK_INICIAL, cantidad=1000),
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 6), propietario=self.propietario, tipo=MovimientoPlan.Tipo.RECEPCION, cantidad=500, documento="REC-1"),
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 18), propietario=self.propietario, tipo=MovimientoPlan.Tipo.DESPACHO, cantidad=200, documento="DES-1"),
        ]
        resultado = dominio.balance_por_movimientos(self.semana, [bloque], movimientos)
        self.assertEqual(resultado["dias"][0]["stock_final"][self.propietario.id], 900)
        self.assertEqual(len(resultado["dias"][0]["movimientos"]), 3)

    def test_trasvasije_conserva_propietarios_separados(self):
        movimientos = [
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 0), propietario=self.propietario, tipo="stock_inicial", cantidad=1000),
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 5), propietario=self.propietario, tipo="trasvasije_salida", cantidad=250, documento="TR-1"),
            MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 5), propietario=self.otro, tipo="trasvasije_entrada", cantidad=250, documento="TR-1"),
        ]
        resultado = dominio.balance_por_movimientos(self.semana, [], movimientos)
        self.assertEqual(resultado["dias"][0]["stock_final"][self.propietario.id], 750)
        self.assertEqual(resultado["dias"][0]["stock_final"][self.otro.id], 250)

    def test_stock_negativo_y_stock_de_seguridad_generan_alertas(self):
        bloque = self.bloque(capacidad=100)
        movimiento = MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 0), propietario=self.propietario, tipo="stock_inicial", cantidad=300)
        resultado = dominio.balance_por_movimientos(self.semana, [bloque], [movimiento], {self.propietario.id: 200})
        self.assertIn("stock_negativo", {item["tipo"] for item in resultado["alertas"]})

    def test_despacho_sin_stock_suficiente_genera_alerta(self):
        movimiento = MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 8), propietario=self.propietario, tipo="despacho", cantidad=500, documento="DES-SIN-STOCK")
        resultado = dominio.balance_por_movimientos(self.semana, [], [movimiento])
        self.assertIn("stock_negativo", {item["tipo"] for item in resultado["alertas"]})

    def test_detecta_solapamiento_que_cruza_medianoche(self):
        primero = self.bloque(inicio=22, fin=26, dia=0)
        segundo = self.bloque(inicio=1, fin=3, dia=1)
        self.assertTrue(dominio.se_solapan(primero, segundo))


class VersionesYDuplicacionTests(BasePlanSemanalNormalizado):
    def setUp(self):
        super().setUp()
        usuario = User.objects.create_user("planificador-nuevo", password="x")
        PerfilUsuario.objects.create(usuario=usuario, area=PerfilUsuario.Area.SECADO, empresa=self.empresa, sucursal=self.sucursal)
        self.cliente = APIClient()
        self.cliente.force_authenticate(usuario)
        for dia in range(6):
            BalanceDia.objects.create(semana=self.semana, dia=dia, stock_inicial=100000 if dia == 0 else None, recepcion_ccaa=100000)
        self.bloque(capacidad=100)

    def test_publicar_crea_version_y_permite_comparar_dos_publicaciones(self):
        primera = self.cliente.post(f"/api/planificacion/semanas/{self.semana.id}/publicar/")
        self.cliente.post(f"/api/planificacion/semanas/{self.semana.id}/reabrir/")
        bloque = self.semana.bloques.get()
        CapacidadProceso.objects.create(equipo=self.equipo, vigente_desde=self.semana.fecha_inicio, capacidad_hora=999, unidad="L/h")
        cambio = self.cliente.patch(f"/api/planificacion/bloques/{bloque.id}/", {"observacion": "Cambio auditable"}, format="json")
        bloque.refresh_from_db()
        segunda = self.cliente.post(f"/api/planificacion/semanas/{self.semana.id}/publicar/")
        comparacion = self.cliente.get(f"/api/planificacion/semanas/{self.semana.id}/comparar-versiones/?desde=1&hasta=2")
        self.assertEqual((primera.status_code, cambio.status_code, segunda.status_code, comparacion.status_code), (200, 200, 200, 200))
        self.assertEqual(VersionSemanaPlan.objects.filter(semana=self.semana).count(), 2)
        self.assertEqual(len(comparacion.data["actividades"]["modificados"]), 1)
        self.assertEqual(bloque.capacidad_hora, 100, "editar no reescribe la capacidad histórica")

    def test_duplicar_copia_movimientos_sin_copiar_versiones(self):
        MovimientoPlan.objects.create(semana=self.semana, fecha_hora=self.momento(0, 8), propietario=self.propietario, tipo="recepcion", cantidad=500)
        respuesta = self.cliente.post(f"/api/planificacion/semanas/{self.semana.id}/duplicar/", {"codigo": "W41", "anio": 2026, "fecha_inicio": "2026-10-05"}, format="json")
        copia = SemanaPlan.objects.get(codigo="W41")
        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(copia.movimientos_plan.count(), 1)
        self.assertEqual(copia.versiones.count(), 0)
