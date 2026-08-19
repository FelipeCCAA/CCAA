from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from maestros.models import Equipo, Mandante, Producto, Silo
from produccion.models import Lote, OrdenProduccion
from recepcion.models import MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal

from .models import CorridaCondensacion, EjecucionProceso, EtapaProceso, Proceso
from .servicios import cerrar_condensacion, iniciar_condensacion


class FlujoCondensacionTests(TestCase):
    def setUp(self):
        empresa = Empresa.objects.create(rut="COND-1", nombre="Empresa condensación")
        self.planta = Sucursal.objects.create(
            empresa=empresa, codigo="COND", nombre="Planta condensación"
        )
        self.usuario = User.objects.create_user("operador-condensacion")
        PerfilUsuario.objects.create(
            usuario=self.usuario, empresa=empresa, sucursal=self.planta,
            rol=Rol.PRODUCCION, area=PerfilUsuario.Area.CONDENSACION,
        )
        mandante = Mandante.objects.create(
            empresa=empresa, nombre="Mandante condensación", codigo_cliente="cond"
        )
        producto = Producto.objects.create(
            mandante=mandante, nombre="Precondensado", unidad_base="l"
        )
        self.equipo = Equipo.objects.create(
            sucursal=self.planta, codigo="ev-1", nombre="Evaporador 1",
            tipo=Equipo.Tipo.EVAPORADOR, consume_leche=True,
        )
        self.origen = Silo.objects.create(
            sucursal=self.planta, codigo="EST-1", tipo=Silo.Tipo.SILO,
            capacidad_l=2000,
        )
        self.destino = Silo.objects.create(
            sucursal=self.planta, codigo="PC-1", tipo=Silo.Tipo.SILO,
            capacidad_l=1000,
        )
        MovimientoSilo.objects.create(
            silo=self.origen, tipo=MovimientoSilo.Tipo.INGRESO,
            litros=Decimal("1500"), fecha_hora=timezone.now(),
        )
        proceso = Proceso.objects.create(codigo="cond", nombre="Condensación")
        etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="evaporar", nombre="Evaporar",
            tipo=EtapaProceso.Tipo.CONDENSACION, orden=1,
        )
        self.ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-COND-1", etapa=etapa, sucursal=self.planta,
            equipo=self.equipo, responsable=self.usuario,
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.planta, codigo="OP-COND-1", producto=producto,
            cantidad_planificada=1000, unidad="l", equipo=self.equipo,
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.lote = Lote.objects.create(
            sucursal=self.planta, codigo_lote="L-COND-1", orden=self.orden,
            op=self.orden.codigo, producto=producto, fecha=date(2026, 8, 17),
        )
        self.corrida = CorridaCondensacion.objects.create(
            ejecucion=self.ejecucion, orden=self.orden, lote=self.lote,
            silo_origen=self.origen, silo_destino=self.destino,
            litros_entrada=Decimal("600"),
        )

    def test_inicio_consume_saldo_real_y_activa_orden_ejecucion(self):
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.EN_PROCESO)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertEqual(self.orden.estado, OrdenProduccion.Estado.EN_PROCESO)
        consumo = MovimientoSilo.objects.get(
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION,
            tipo=MovimientoSilo.Tipo.SALIDA,
        )
        self.assertEqual(consumo.litros, Decimal("600"))
        self.assertEqual(consumo.lote, self.lote)

    def test_cierre_deja_precondensado_y_balance_de_ejecucion(self):
        iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        cerrar_condensacion(
            corrida_id=self.corrida.pk, usuario=self.usuario,
            litros_precondensado="250",
            controles={"densidad_salida": Decimal("1.180"), "solidos_salida": 48},
        )

        self.corrida.refresh_from_db()
        self.ejecucion.refresh_from_db()
        self.assertEqual(self.corrida.estado, CorridaCondensacion.Estado.CERRADA)
        self.assertEqual(self.ejecucion.estado, EjecucionProceso.Estado.CERRADA)
        ingreso = self.destino.movimientos.get(tipo=MovimientoSilo.Tipo.INGRESO)
        self.assertEqual(ingreso.litros, Decimal("250"))
        self.assertEqual(self.ejecucion.entradas.get().cantidad, Decimal("600"))
        self.assertEqual(self.ejecucion.salidas.get().cantidad, Decimal("250"))

    def test_no_inicia_con_saldo_insuficiente_o_silo_bloqueado(self):
        self.corrida.litros_entrada = Decimal("1600")
        self.corrida.save(update_fields=["litros_entrada"])
        with self.assertRaises(ValidationError):
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)
        self.corrida.litros_entrada = Decimal("600")
        self.corrida.save(update_fields=["litros_entrada"])
        self.origen.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.origen.save(update_fields=["estado"])
        with self.assertRaises(ValidationError):
            iniciar_condensacion(corrida_id=self.corrida.pk, usuario=self.usuario)

        self.assertFalse(MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.PRODUCCION
        ).exists())
