"""
El lote nace del vale, no elige silo.

Quien consume la leche de los silos es el **vale**: al transferirse saca de la
entera y del TK de descremada y deja la mezcla en el silo de destino. Esa leche
ya está estandarizada al RC que un producto pide, pero todavía no es de ningún
producto — abrir el lote es lo que formaliza a cuál va.

Las dos reglas que se fijan aquí:

1. Solo un vale **liberado** puede dar origen a un lote. Uno en corrección tiene
   un RC medido que no cumple.
2. No se puede sacar **más de lo que el vale preparó**, ni siquiera repartido
   entre varios lotes.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from estandarizacion.models import ValeEstandarizacion
from maestros.models import Equipo, Mandante, Producto, Silo
from procesos.models import CorridaSecado, EtapaProceso, Proceso, RutaProducto
from produccion import servicios
from produccion.dominio import puede_abrir_lote_desde
from produccion.models import Lote
from recepcion.models import MovimientoSilo
from usuarios.models import Empresa, PerfilUsuario, Rol, Sucursal


class BaseValeLote(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.313.313-1", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PL", nombre="Planta"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Nestlé", codigo_cliente="nestle"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche entera en polvo", unidad_base="kg"
        )
        self.origen = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 1", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.destino = Silo.objects.create(
            sucursal=self.planta, codigo="SILO 2", tipo=Silo.Tipo.SILO,
            capacidad_l=100000,
        )
        self.operador = User.objects.create_user(username="op", password="x")
        proceso = Proceso.objects.create(codigo="ruta-prueba", nombre="Ruta prueba")
        EtapaProceso.objects.create(
            proceso=proceso, codigo="secado", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=1,
        )
        self.ruta = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso,
        )

    def _vale(self, estado=ValeEstandarizacion.Estado.LIBERADO, volumen="20000.00"):
        return ValeEstandarizacion.objects.create(
            codigo=f"VE-{estado}-{volumen}",
            fecha=date(2026, 8, 12),
            producto=self.producto,
            rc_objetivo=Decimal("0.4000"),
            volumen=Decimal(volumen),
            silo_entera=self.origen,
            silo_destino=self.destino,
            entera_grasa=Decimal("3.60"), entera_sng=Decimal("8.60"),
            descremada_grasa=Decimal("0.05"), descremada_sng=Decimal("8.90"),
            litros_entera=Decimal("19128.10"), litros_descremada=Decimal("871.90"),
            estado=estado,
        )

    def _abrir(self, vale, litros, codigo="CCAA6224010102010201-01"):
        return servicios.abrir_lote_desde_vale(
            vale=vale,
            producto=self.producto,
            codigo_lote=codigo,
            fecha=date(2026, 8, 12),
            litros=litros,
        )


class AperturaTests(BaseValeLote):

    def test_abrir_en_torre_crea_la_corrida_especializada_de_secado(self):
        torre = Equipo.objects.create(
            sucursal=self.planta, codigo="TORRE-1", nombre="Torre 1",
            tipo=Equipo.Tipo.TORRE,
        )
        vale = self._vale()

        lote = servicios.abrir_lote_desde_vale(
            vale=vale, producto=self.producto, codigo_lote="SEC-ESPECIALIZADO",
            fecha=date(2026, 8, 12), litros=Decimal("1000.00"),
            equipo=torre, usuario=self.operador,
        )

        corrida = CorridaSecado.objects.get(lote=lote)
        self.assertEqual(corrida.ejecucion, lote.ejecucion)
        self.assertEqual(corrida.ejecucion.equipo, torre)
        self.assertIsNone(corrida.kg_polvo)

    def test_el_lote_queda_atado_al_vale_y_descuenta_su_silo(self):
        vale = self._vale()

        lote = self._abrir(vale, Decimal("20000.00"))

        self.assertEqual(lote.vale, vale)
        # No eligió silo: tomó el del vale.
        movimiento = MovimientoSilo.objects.get(origen_id=lote.id)
        self.assertEqual(movimiento.silo, vale.silo_destino)
        self.assertEqual(movimiento.litros, Decimal("20000.00"))

    def test_un_vale_no_liberado_no_abre_lote(self):
        """Su RC medido no cumple: esa leche no es la de ningún producto."""
        vale = self._vale(estado=ValeEstandarizacion.Estado.CORRIGIENDO)

        with self.assertRaises(ValidationError) as fallo:
            self._abrir(vale, Decimal("1000.00"))

        self.assertIn("liberado", str(fallo.exception))
        self.assertFalse(Lote.objects.exists())

    def test_no_se_puede_sacar_mas_de_lo_preparado(self):
        vale = self._vale(volumen="10000.00")

        with self.assertRaises(ValidationError):
            self._abrir(vale, Decimal("12000.00"))

        self.assertFalse(Lote.objects.exists())

    def test_un_vale_alimenta_varias_corridas_hasta_agotarse(self):
        """Veinte mil litros no se secan de una vez."""
        vale = self._vale(volumen="20000.00")

        self._abrir(vale, Decimal("12000.00"), codigo="LOTE-A")
        self._abrir(vale, Decimal("8000.00"), codigo="LOTE-B")

        self.assertEqual(vale.lotes.count(), 2)

        with self.assertRaises(ValidationError) as fallo:
            self._abrir(vale, Decimal("1.00"), codigo="LOTE-C")

        self.assertIn("quedan", str(fallo.exception))

    def test_si_la_regla_falla_no_queda_el_silo_descontado(self):
        """
        Todo o nada. Un descuento sin lote deja el saldo del silo mintiendo, y
        nadie lo nota porque no hay lote al que reclamarle esos litros.
        """
        vale = self._vale(volumen="5000.00")

        with self.assertRaises(ValidationError):
            self._abrir(vale, Decimal("9000.00"))

        self.assertFalse(MovimientoSilo.objects.exists())

    def test_sin_ruta_no_quedan_lote_ni_movimiento_huerfanos(self):
        vale = self._vale()
        self.ruta.delete()

        with self.assertRaisesMessage(ValidationError, "no tiene una ruta activa"):
            self._abrir(vale, Decimal("1000.00"))

        self.assertFalse(Lote.objects.exists())
        self.assertFalse(MovimientoSilo.objects.exists())

    def test_no_permite_saltar_la_etapa_inicial_posterior_al_vale(self):
        secado = self.ruta.proceso.etapas.get(tipo=EtapaProceso.Tipo.SECADO)
        secado.orden = 3
        secado.save(update_fields=["orden"])
        EtapaProceso.objects.create(
            proceso=self.ruta.proceso,
            codigo="estandarizacion",
            nombre="EstandarizaciÃ³n",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION,
            orden=1,
        )
        evaporacion = EtapaProceso.objects.create(
            proceso=self.ruta.proceso,
            codigo="evaporacion",
            nombre="EvaporaciÃ³n",
            tipo=EtapaProceso.Tipo.EVAPORACION,
            orden=2,
        )
        evaporador = Equipo.objects.create(
            sucursal=self.planta,
            codigo="EV-1",
            nombre="Evaporador 1",
            tipo=Equipo.Tipo.EVAPORADOR,
        )
        torre = Equipo.objects.create(
            sucursal=self.planta,
            codigo="TORRE-SALTO",
            nombre="Torre no inicial",
            tipo=Equipo.Tipo.TORRE,
        )
        vale = self._vale()

        with self.assertRaisesMessage(ValidationError, "no permite comenzar directamente"):
            servicios.abrir_lote_desde_vale(
                vale=vale,
                producto=self.producto,
                codigo_lote="SALTO-SECADO",
                fecha=date(2026, 8, 12),
                litros=Decimal("1000"),
                equipo=torre,
                usuario=self.operador,
            )

        self.assertFalse(Lote.objects.filter(codigo_lote="SALTO-SECADO").exists())
        self.assertFalse(MovimientoSilo.objects.filter(origen_tipo="lote").exists())

        PerfilUsuario.objects.create(
            usuario=self.operador,
            empresa=self.empresa,
            sucursal=self.planta,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
            rol=Rol.PRODUCCION,
            area=PerfilUsuario.Area.CONDENSACION,
        )
        cliente = APIClient()
        cliente.force_authenticate(self.operador)
        respuesta = cliente.get("/api/produccion/lotes/opciones-inicio/")

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        entrada = respuesta.data["entradas"][0]
        self.assertEqual(
            [etapa["id"] for etapa in entrada["etapas_iniciales"]],
            [evaporacion.pk],
        )
        self.assertEqual(entrada["equipos_compatibles"], [evaporador.pk])
        self.assertEqual(
            [equipo["id"] for equipo in respuesta.data["equipos"]],
            [evaporador.pk],
        )

    def test_un_lote_sin_ejecucion_no_puede_cerrar_trazabilidad(self):
        lote = Lote.objects.create(
            sucursal=self.planta, producto=self.producto,
            codigo_lote="LEGADO-SIN-EJECUCION", fecha=date(2026, 8, 12),
            estado=Lote.Estado.PRODUCIDO, kg_producidos=Decimal("100.00"),
        )

        with self.assertRaisesMessage(ValidationError, "no tiene una ejecución"):
            servicios.registrar_produccion(lote=lote)


class DecisionSinBaseTests(TestCase):
    """La regla pura, sin tocar la base: es lo que la hace comprobable."""

    class ValeDoble:
        codigo = "VE-1"
        estado = "liberado"
        volumen = Decimal("1000")

        def get_estado_display(self):
            return "Liberado"

    def test_liberado_y_dentro_del_volumen(self):
        decision = puede_abrir_lote_desde(self.ValeDoble(), Decimal("400"))

        self.assertTrue(decision.permitido)
        self.assertEqual(decision.litros_disponibles, Decimal("1000"))

    def test_descuenta_lo_que_ya_se_llevaron_otros(self):
        decision = puede_abrir_lote_desde(
            self.ValeDoble(), Decimal("400"), consumido_por_otros_lotes=Decimal("700")
        )

        self.assertFalse(decision.permitido)
        self.assertEqual(decision.litros_disponibles, Decimal("300"))

    def test_cero_litros_no_es_un_lote(self):
        self.assertFalse(
            puede_abrir_lote_desde(self.ValeDoble(), Decimal("0")).permitido
        )
