from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from recepcion.models import AnalisisSilo, MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .dominio import calcular_balance_descremacion
from .models import (
    CorridaDescremacion, EjecucionProceso, EtapaProceso, Proceso,
)
from .servicios import cerrar_descremacion, iniciar_descremacion


class BalanceDescremacionTests(TestCase):
    def test_calcula_las_dos_salidas_sin_inventar_una_tolerancia(self):
        balance = calcular_balance_descremacion(1000, 4, 8.7, 0.1, 40)

        self.assertAlmostEqual(balance.crema_esperada_l, Decimal("97.74436"), places=4)
        self.assertAlmostEqual(balance.descremada_esperada_l, Decimal("902.25564"), places=4)
        self.assertEqual(balance.avisos, ())


class CierreDescremacionTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="76.999.111-2", nombre="Descremación")
        sucursal = Sucursal.objects.create(empresa=empresa, codigo="DES", nombre="Planta")
        self.sucursal = sucursal
        self.usuario = User.objects.create_user("operador-descremacion")
        self.origen = Silo.objects.create(
            sucursal=sucursal, codigo="ENTERA-D", tipo=Silo.Tipo.SILO, capacidad_l=5000
        )
        self.descremada = Silo.objects.create(
            sucursal=sucursal, codigo="DESCREMADA-D", tipo=Silo.Tipo.TK_LD,
            capacidad_l=5000,
        )
        self.crema = Silo.objects.create(
            sucursal=sucursal, codigo="CREMA-D", tipo=Silo.Tipo.TK_CREMA,
            capacidad_l=1000,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO, litros=1000,
            fecha_hora=timezone.now() - timedelta(hours=2),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
        )
        analisis = AnalisisSilo.objects.create(
            silo=self.origen, tomado_en=timezone.now() - timedelta(hours=1),
            grasa=Decimal("4.000"), sng=Decimal("8.700"),
            inhibidores_resultado="negativo", metodo="snap",
            hora_lectura=timezone.localtime().time(), estado=AnalisisSilo.Estado.CONFIRMADO,
            analista=self.usuario, visualizado_por=self.usuario,
        )
        equipo = Equipo.objects.create(
            sucursal=sucursal, codigo="DES-1", nombre="Descremadora 1",
            tipo=Equipo.Tipo.OTRO,
        )
        proceso = Proceso.objects.create(codigo="descremar", nombre="Descremación")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="des", nombre="Descremar",
            tipo=EtapaProceso.Tipo.DESCREMACION, orden=1,
        )
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-DES-1", etapa=etapa, sucursal=sucursal,
            equipo=equipo, responsable=self.usuario,
        )
        self.ejecucion = ejecucion
        self.corrida = CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.origen, analisis_entrada=analisis,
            litros_entrada=1000, grasa_entrada=Decimal("4.000"),
            sng_entrada=Decimal("8.700"), silo_descremada=self.descremada,
            estanque_crema=self.crema,
        )

    def test_cierre_genera_dos_saldos_y_hereda_fifo_en_una_operacion(self):
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        resultado = cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada=Decimal("0.1"),
            litros_crema=90, grasa_crema=Decimal("40"),
            controles={"ph_salida": "6.7"},
        )

        movimientos = MovimientoSilo.objects.filter(operacion_id=self.corrida.operacion_id)
        self.assertEqual(movimientos.count(), 3)
        self.assertEqual(resultado.estado, CorridaDescremacion.Estado.CERRADA)
        self.assertEqual(resultado.ejecucion.salidas.count(), 2)
        self.assertEqual(
            sum(m.atribuciones_recepcion.count() for m in movimientos.filter(tipo="ingreso")),
            2,
        )
        self.assertTrue(resultado.controles["avisos_balance"])

    def test_calidad_decide_descremada_y_crema_por_separado(self):
        self.ejecucion.etapa.requiere_calidad = True
        self.ejecucion.etapa.save(update_fields=["requiere_calidad"])
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=self.sucursal.empresa, sucursal=self.sucursal,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.CONDENSACION,
        )
        etapa_siguiente = EtapaProceso.objects.create(
            proceso=self.ejecucion.etapa.proceso, codigo="continuar",
            nombre="Secado", tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        torre = Equipo.objects.create(
            sucursal=self.sucursal, codigo="TORRE-D", nombre="Torre de secado",
            tipo=Equipo.Tipo.TORRE,
        )
        ejecucion_siguiente = EjecucionProceso.objects.create(
            codigo="EJ-DES-SIG", etapa=etapa_siguiente, sucursal=self.sucursal,
            responsable=self.usuario,
        )
        iniciar_descremacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        cerrar_descremacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_descremada=900, grasa_descremada="0.1",
            litros_crema=90, grasa_crema="40",
        )
        self.ejecucion.refresh_from_db()
        self.descremada.refresh_from_db()
        self.crema.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self.assertEqual(self.descremada.estado, Silo.Estado.BLOQUEADO_CALIDAD)
        self.assertEqual(self.crema.estado, Silo.Estado.BLOQUEADO_CALIDAD)

        analisis = {}
        for silo, grasa, sng in (
            (self.descremada, "0.10", "8.70"),
            (self.crema, "40.00", "5.00"),
        ):
            analisis[silo.pk] = AnalisisSilo.objects.create(
                silo=silo, tomado_en=timezone.now(), grasa=grasa, sng=sng,
                inhibidores_resultado="negativo", metodo="snap",
                hora_lectura=timezone.localtime().time(),
                estado=AnalisisSilo.Estado.CONFIRMADO,
                analista=self.usuario, visualizado_por=self.usuario,
            )
        calidad = User.objects.create_user("calidad-descremacion")
        PerfilUsuario.objects.create(
            usuario=calidad, empresa=self.sucursal.empresa, sucursal=self.sucursal,
            rol=Rol.CALIDAD, area=PerfilUsuario.Area.CALIDAD,
        )
        cliente = APIClient()
        cliente.force_authenticate(calidad)
        salidas = {salida.silo_id: salida for salida in self.ejecucion.salidas.all()}
        produccion = APIClient()
        produccion.force_authenticate(self.usuario)
        bloqueada = produccion.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": ejecucion_siguiente.pk,
                "silo": self.descremada.pk,
                "salida_origen": salidas[self.descremada.pk].pk,
                "cantidad": "400",
                "unidad": "L",
            },
            format="json",
        )
        self.assertEqual(bloqueada.status_code, 400)
        cola = cliente.get(
            "/api/calidad/expedientes/", {"incluir_procesos": "1"}
        )
        self.assertEqual(cola.status_code, 200, cola.data)
        self.assertEqual(
            {item["producto_nombre"] for item in cola.data["procesos"]},
            {"Leche descremada", "Crema"},
        )

        primera = cliente.post(
            f"/api/calidad/resultados-proceso/{salidas[self.descremada.pk].pk}/liberar/",
            {"analisis_id": analisis[self.descremada.pk].pk}, format="json",
        )
        self.assertEqual(primera.status_code, 200, primera.data)
        self.ejecucion.refresh_from_db()
        self.crema.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.PENDIENTE_CONTROL)
        self.assertEqual(self.crema.estado, Silo.Estado.BLOQUEADO_CALIDAD)
        entrada = produccion.post(
            "/api/procesos/entradas/",
            {
                "ejecucion": ejecucion_siguiente.pk,
                "silo": self.descremada.pk,
                "salida_origen": salidas[self.descremada.pk].pk,
                "cantidad": "400",
                "unidad": "L",
            },
            format="json",
        )
        self.assertEqual(entrada.status_code, 201, entrada.data)

        segunda = cliente.post(
            f"/api/calidad/resultados-proceso/{salidas[self.crema.pk].pk}/liberar/",
            {"analisis_id": analisis[self.crema.pk].pk}, format="json",
        )
        self.assertEqual(segunda.status_code, 200, segunda.data)
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        disponibles = produccion.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(disponibles.status_code, 200, disponibles.data)
        descremada = next(
            item for item in disponibles.data if item["id"] == salidas[self.descremada.pk].pk
        )
        self.assertEqual(descremada["cantidad_disponible"], Decimal("500"))
        self.assertEqual(
            descremada["etapas_siguientes"][0]["equipos"][0]["id"], torre.pk
        )
        continuacion = produccion.post(
            f"/api/procesos/salidas/{salidas[self.descremada.pk].pk}/preparar-continuacion/",
            {"etapa": etapa_siguiente.pk, "equipo": torre.pk, "cantidad": "200"},
            format="json",
        )
        self.assertEqual(continuacion.status_code, 201, continuacion.data)
        self.assertEqual(
            continuacion.data["estado"], EjecucionProceso.Estado.PREPARACION
        )
        self.assertEqual(
            continuacion.data["entradas"][0]["salida_origen"],
            salidas[self.descremada.pk].pk,
        )
