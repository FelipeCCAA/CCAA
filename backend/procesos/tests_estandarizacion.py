"""
El vale de estandarización **es** una ejecución de esa etapa.

No es que una acompañe a la otra: son el mismo hecho de planta visto desde dos
sitios. El vale lleva la receta y el RC; la ejecución lleva el lugar en la
cadena, que es lo que después responde de qué salió un saco.

Lo que se fija aquí:

1. La ejecución nace al **transferir**, que es cuando la mezcla ocurre. Un vale
   solo calculado no ha pasado todavía.
2. Sus entradas son **silos**, no lotes — esa leche no es de ningún lote.
3. Cierra solo si el RC quedó conforme. Un vale en corrección sigue en marcha,
   que es lo que está pasando en el silo.
4. La genealogía **no revienta** cuando una entrada viene de un silo.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from estandarizacion import servicios as estandarizacion
from estandarizacion.models import ValeEstandarizacion
from maestros.models import Mandante, Producto, Silo
from procesos.models import EjecucionProceso, EtapaProceso, Proceso, RutaProducto
from procesos.servicios import genealogia_lote
from produccion import servicios as produccion
from recepcion.models import AnalisisSilo, ControlInhibidores, MovimientoSilo
from usuarios.models import Empresa, Sucursal


class BaseCadena(TestCase):

    def setUp(self):
        self.empresa = Empresa.objects.create(rut="76.515.515-1", nombre="CCAA")
        self.planta = Sucursal.objects.create(
            empresa=self.empresa, codigo="PL", nombre="Planta"
        )
        mandante = Mandante.objects.create(
            empresa=self.empresa, nombre="Nestlé", codigo_cliente="nestle"
        )
        self.producto = Producto.objects.create(
            mandante=mandante, nombre="Leche entera en polvo", unidad_base="kg"
        )

        self.entera = self._silo("SILO 1", Silo.Tipo.SILO)
        self.tanque = self._silo("TK LD 1", Silo.Tipo.TK_LD)
        self.destino = self._silo("SILO 2", Silo.Tipo.SILO)

        for silo, litros in ((self.entera, "30000"), (self.tanque, "10000")):
            MovimientoSilo.objects.create(
                silo=silo, tipo=MovimientoSilo.Tipo.INGRESO,
                litros=Decimal(litros), fecha_hora=timezone.now(),
                origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
                motivo="Carga de prueba",
            )

        # Las migraciones siembran «Transformación industrial de leche» también
        # en la base de pruebas, así que sin esto el servicio elegiría **esa**
        # etapa y no la de este escenario. Se desactivan en vez de borrarlas:
        # `EtapaProceso.proceso` es PROTECT, y al servicio lo que le importa es
        # que estén activas.
        EtapaProceso.objects.update(activa=False)

        proceso = Proceso.objects.create(codigo="flujo", nombre="Flujo")
        self.etapa_estandarizacion = EtapaProceso.objects.create(
            proceso=proceso, codigo="est", nombre="Estandarización",
            tipo=EtapaProceso.Tipo.ESTANDARIZACION, orden=1,
        )
        self.etapa_secado = EtapaProceso.objects.create(
            proceso=proceso, codigo="sec", nombre="Secado",
            tipo=EtapaProceso.Tipo.SECADO, orden=2,
        )
        self.ruta = RutaProducto.objects.create(
            sucursal=self.planta, producto=self.producto, proceso=proceso,
        )

        self.operador = User.objects.create_user(username="op", password="x")
        for silo in (self.entera, self.tanque):
            AnalisisSilo.objects.create(
                silo=silo,
                tomado_en=timezone.now(),
                grasa=Decimal("3.60"),
                sng=Decimal("8.60"),
                inhibidores_resultado=ControlInhibidores.Resultado.NEGATIVO,
                metodo=ControlInhibidores.Metodo.DELVO_SP,
                hora_lectura=timezone.localtime().time(),
                analista=self.operador,
                visualizado_por=self.operador,
                visualizado_en=timezone.now(),
                estado=AnalisisSilo.Estado.CONFIRMADO,
            )

    def _silo(self, codigo, tipo):
        return Silo.objects.create(
            sucursal=self.planta, codigo=codigo, tipo=tipo, capacidad_l=100000
        )

    def _vale(self):
        return ValeEstandarizacion.objects.create(
            codigo="VE-1",
            fecha=date(2026, 8, 12),
            producto=self.producto,
            rc_objetivo=Decimal("0.4000"),
            volumen=Decimal("20000.00"),
            silo_entera=self.entera,
            silo_descremada=self.tanque,
            silo_destino=self.destino,
            entera_grasa=Decimal("3.60"), entera_sng=Decimal("8.60"),
            descremada_grasa=Decimal("0.05"), descremada_sng=Decimal("8.90"),
            litros_entera=Decimal("19128.10"), litros_descremada=Decimal("871.90"),
            estado=ValeEstandarizacion.Estado.CALCULADO,
            responsable=self.operador,
        )

    def _hasta_muestrear(self, vale, grasa, sng):
        estandarizacion.transferir(vale_id=vale.pk, usuario=self.operador)
        estandarizacion.iniciar_agitacion(vale_id=vale.pk)
        ValeEstandarizacion.objects.filter(pk=vale.pk).update(
            agitacion_desde=timezone.now() - timedelta(minutes=35)
        )
        estandarizacion.registrar_muestra(vale_id=vale.pk, grasa=grasa, sng=sng)


class ElValeEsUnaEjecucionTests(BaseCadena):

    def test_un_vale_solo_calculado_no_tiene_ejecucion(self):
        """Todavía no pasó nada en la planta: registrarlo inventaría una corrida."""
        self._vale()

        self.assertFalse(EjecucionProceso.objects.exists())

    def test_al_transferir_nace_la_ejecucion_con_sus_silos(self):
        vale = self._vale()

        estandarizacion.transferir(vale_id=vale.pk, usuario=self.operador)

        ejecucion = EjecucionProceso.objects.get(vale=vale)
        self.assertEqual(ejecucion.etapa, self.etapa_estandarizacion)
        self.assertEqual(ejecucion.estado, EjecucionProceso.Estado.EJECUCION)

        entradas = {e.silo.codigo: e.cantidad for e in ejecucion.entradas.all()}
        self.assertEqual(entradas["SILO 1"], Decimal("19128.100"))
        self.assertEqual(entradas["TK LD 1"], Decimal("871.900"))

        salida = ejecucion.salidas.get()
        self.assertEqual(salida.silo, self.destino)
        self.assertIsNone(salida.lote)

    def test_transferir_dos_veces_no_duplica_la_corrida(self):
        vale = self._vale()

        estandarizacion.transferir(vale_id=vale.pk, usuario=self.operador)
        from procesos.servicios import registrar_estandarizacion

        registrar_estandarizacion(vale=vale)

        self.assertEqual(EjecucionProceso.objects.filter(vale=vale).count(), 1)

    def test_sin_ruta_la_transferencia_completa_se_revierte(self):
        vale = self._vale()
        movimientos_antes = MovimientoSilo.objects.count()
        self.ruta.delete()

        with self.assertRaisesMessage(ValidationError, "no tiene una ruta activa"):
            estandarizacion.transferir(vale_id=vale.pk, usuario=self.operador)

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CALCULADO)
        self.assertEqual(MovimientoSilo.objects.count(), movimientos_antes)
        self.assertFalse(EjecucionProceso.objects.filter(vale=vale).exists())

    def test_el_rc_conforme_cierra_la_etapa(self):
        vale = self._vale()
        # 3.44 / 8.61 = 0,3995, dentro de la tolerancia del objetivo 0,4000.
        self._hasta_muestrear(vale, Decimal("3.44"), Decimal("8.61"))

        vale, _ = estandarizacion.decidir(vale_id=vale.pk, usuario=self.operador)

        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.LIBERADO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.CERRADA,
        )

    def test_un_vale_en_correccion_deja_la_etapa_abierta(self):
        """Sigue en marcha, que es exactamente lo que pasa en el silo."""
        vale = self._vale()
        self._hasta_muestrear(vale, Decimal("4.50"), Decimal("8.60"))

        vale, _ = estandarizacion.decidir(vale_id=vale.pk, usuario=self.operador)

        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CORRIGIENDO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.EJECUCION,
        )


class CadenaCompletaTests(BaseCadena):

    def _cadena(self):
        vale = self._vale()
        self._hasta_muestrear(vale, Decimal("3.44"), Decimal("8.61"))
        vale, _ = estandarizacion.decidir(vale_id=vale.pk, usuario=self.operador)

        lote = produccion.abrir_lote_desde_vale(
            vale=vale, producto=self.producto, codigo_lote="LOTE-1",
            fecha=date(2026, 8, 12), litros=Decimal("20000.00"),
        )
        lote.kg_producidos = Decimal("1700.00")
        lote.estado = lote.Estado.PRODUCIDO
        lote.save()
        produccion.registrar_produccion(lote=lote)

        return vale, lote

    def test_quedan_las_dos_etapas_encadenadas(self):
        vale, lote = self._cadena()

        self.assertEqual(EjecucionProceso.objects.count(), 2)

        secado = EjecucionProceso.objects.get(etapa=self.etapa_secado)
        self.assertEqual(secado.entradas.get().silo, vale.silo_destino)
        self.assertEqual(secado.salidas.get().lote, lote)
        self.assertEqual(secado.estado, EjecucionProceso.Estado.CERRADA)

    def test_la_genealogia_no_revienta_con_una_entrada_de_silo(self):
        """
        Reproducido antes de arreglarlo: `genealogia_lote` daba
        `AttributeError: 'NoneType' object has no attribute 'sucursal_id'`, o
        sea un 500 en la pantalla de trazabilidad, en cuanto una entrada venía
        de un silo en vez de un lote.
        """
        _, lote = self._cadena()

        for direccion in ("atras", "adelante"):
            resultado = genealogia_lote(
                lote.pk, direccion, sucursal_id=self.planta.pk
            )
            self.assertEqual(len(resultado["nodos"]), 1)

    def test_sin_kilos_no_se_cierra_la_corrida(self):
        """Un lote sin kilos declarados es uno que todavía está en la torre."""
        from django.core.exceptions import ValidationError

        vale = self._vale()
        self._hasta_muestrear(vale, Decimal("3.44"), Decimal("8.61"))
        vale, _ = estandarizacion.decidir(vale_id=vale.pk, usuario=self.operador)
        lote = produccion.abrir_lote_desde_vale(
            vale=vale, producto=self.producto, codigo_lote="LOTE-2",
            fecha=date(2026, 8, 12), litros=Decimal("1000.00"),
        )

        with self.assertRaises(ValidationError):
            produccion.registrar_produccion(lote=lote)

        secado = EjecucionProceso.objects.get(etapa=self.etapa_secado)
        self.assertEqual(secado.estado, EjecucionProceso.Estado.EJECUCION)
        self.assertFalse(secado.salidas.exists())
