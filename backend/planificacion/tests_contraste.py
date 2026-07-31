"""
Pruebas del contraste plan / real y del consumo real de silo.

Lo que protegen: que los dos lados se midan con datos distintos. Si el lado
real se copiara del plan, el contraste siempre cuadraría y no serviría para
nada — que es exactamente el fallo que no se ve.
"""

from datetime import date, datetime, time
from datetime import timezone as tz

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import (
    Equipo,
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
    Silo,
)
from produccion.models import Lote
from recepcion.models import MovimientoSilo, Recepcion
from usuarios.models import PerfilUsuario, Rol

from . import contraste, dominio
from .models import (
    BalanceDia,
    BloquePlan,
    CategoriaConsumo,
    CodigoProduccion,
    SemanaPlan,
)


class BaseContraste(TestCase):
    def setUp(self):
        self.mandante = Mandante.objects.create(nombre="Nestlé")

        self.leche = Producto.objects.create(
            nombre="Leche fresca",
            familia=Producto.Familia.LIQUIDO,
            naturaleza=Producto.Naturaleza.MATERIA_PRIMA,
            unidad_base="L",
            mandante=self.mandante,
        )
        self.polvo = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            unidad_base="kg",
            mandante=self.mandante,
        )

        # 1 kg de polvo ← 8 L de leche
        receta = Receta.objects.create(
            producto=self.polvo, vigente_desde=date(2026, 1, 1)
        )
        RecetaComponente.objects.create(
            receta=receta, producto=self.leche, cantidad=8, unidad="L"
        )

        self.silo = Silo.objects.create(
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )

        self.semana = SemanaPlan.objects.create(
            codigo="W7", anio=2026, fecha_inicio=date(2026, 2, 9)  # lunes
        )
        # Ya existe: los equipos se siembran por migración de datos y esa
        # migración también corre en la base de pruebas.
        self.scheffers2, _ = Equipo.objects.update_or_create(
            codigo="scheffers2",
            defaults={
                "nombre": "Evaporador Scheffers 2",
                "tipo": Equipo.Tipo.EVAPORADOR,
                "consume_leche": True,
            },
        )
        self.codigo = CodigoProduccion.objects.create(
            codigo="LNSH2",
            categoria=CategoriaConsumo.SECADO_NESTLE,
            rendimiento_lh=11000,
            producto=self.polvo,
            mandante=self.mandante,
        )

    def _cliente(self, rol=Rol.PRODUCCION):
        usuario = User.objects.create_user(f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def _lote(self, fecha=date(2026, 2, 9), kg=1000, codigo="L1"):
        return Lote.objects.create(
            codigo_lote=codigo,
            producto=self.polvo,
            fecha=fecha,
            kg_producidos=kg,
            estado=Lote.Estado.PRODUCIDO,
        )


class ConsumoRealTests(BaseContraste):
    """
    La costura entre asignar leche y contrastar la semana.

    El lado real del contraste lee salidas de silo con origen LOTE. Quien las
    escribe es la asignación de Producción (`produccion/tests_asignacion.py`,
    que es donde viven sus reglas). Aquí solo se prueba que las dos mitades
    encajen: si la asignación cambiara la forma del movimiento, el contraste
    seguiría verde marcando cero consumo real, que es el fallo que no se ve.
    """

    def _asignar(self, cliente, lote, lineas):
        return cliente.post(
            f"/api/produccion/lotes/{lote.id}/asignacion/",
            {"asignaciones": lineas},
            format="json",
        )

    def test_lo_asignado_llega_al_contraste_como_consumo_real(self):
        cliente = self._cliente()
        BloquePlan.objects.create(
            semana=self.semana, equipo=self.scheffers2, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.codigo,
        )  # 4 h × 11.000 = 44.000 planificados
        lote = self._lote(kg=1000)

        # La hora se declara: el contraste imputa cada salida a su día, y la
        # semana del plan es febrero.
        respuesta = self._asignar(
            cliente,
            lote,
            [
                {
                    "silo": self.silo.id,
                    "litros": 8000,
                    "fecha_hora": datetime(2026, 2, 9, 10, tzinfo=tz.utc).isoformat(),
                }
            ],
        )
        self.assertEqual(respuesta.status_code, 200)

        fila = contraste.contrastar_semana(
            self.semana,
            list(BloquePlan.objects.all()),
            list(CodigoProduccion.objects.all()),
            list(BalanceDia.objects.all()),
            [],
            list(MovimientoSilo.objects.all()),
            list(Lote.objects.all()),
        )[0]

        self.assertEqual(fila.leche_consumida.plan, 44000)
        self.assertEqual(fila.leche_consumida.real, 8000)
        self.assertTrue(fila.hubo_actividad)

    def test_la_mezcla_de_varios_silos_suma_como_un_solo_consumo(self):
        """
        Un lote puede tomar leche de más de un estanque. El contraste mide
        leche, no estanques: las líneas se suman.
        """
        cliente = self._cliente()
        otro = Silo.objects.create(
            codigo="SILO 2", tipo=Silo.Tipo.SILO, capacidad_l=200000
        )
        lote = self._lote(kg=1000)
        cuando = datetime(2026, 2, 9, 10, tzinfo=tz.utc).isoformat()

        self._asignar(
            cliente,
            lote,
            [
                {"silo": self.silo.id, "litros": 5000, "fecha_hora": cuando},
                {"silo": otro.id, "litros": 3000, "fecha_hora": cuando},
            ],
        )

        fila = contraste.contrastar_semana(
            self.semana,
            list(BloquePlan.objects.all()),
            list(CodigoProduccion.objects.all()),
            list(BalanceDia.objects.all()),
            [],
            list(MovimientoSilo.objects.all()),
            list(Lote.objects.all()),
        )[0]

        self.assertEqual(fila.leche_consumida.real, 8000)

    def test_el_saldo_del_silo_baja(self):
        """Sin descontar, el saldo del estanque solo subiría."""
        cliente = self._cliente()
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=50000,
            fecha_hora=datetime(2026, 2, 9, 8, tzinfo=tz.utc),
        )
        lote = self._lote(kg=1000)

        self._asignar(cliente, lote, [{"silo": self.silo.id, "litros": 8000}])

        ocupacion = cliente.get("/api/recepcion/ocupacion/").json()
        self.assertEqual(ocupacion["litros_totales"], 42000)

    def test_un_producto_sin_receta_igual_se_puede_trazar(self):
        """
        Los litros los declara Producción, así que no hace falta receta para
        saber de qué silo salió la leche. Antes esto se rechazaba, porque la
        cantidad se derivaba de la receta; el precio era quedarse sin
        trazabilidad justo en los productos que no la tienen cargada.
        """
        cliente = self._cliente()
        sin_receta = Producto.objects.create(
            nombre="Suero en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        lote = Lote.objects.create(
            codigo_lote="SR-1",
            producto=sin_receta,
            fecha=date(2026, 2, 9),
            kg_producidos=100,
        )

        respuesta = self._asignar(
            cliente, lote, [{"silo": self.silo.id, "litros": 900}]
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["asignado"], 900)
        # Sin receta no hay expectativa contra la que comparar; no se inventa.
        self.assertIsNone(respuesta.json()["teorico"])
        self.assertEqual(MovimientoSilo.objects.count(), 1)

    def test_calidad_no_descuenta_leche(self):
        cliente = self._cliente(Rol.CALIDAD)
        lote = self._lote()

        respuesta = self._asignar(
            cliente, lote, [{"silo": self.silo.id, "litros": 8000}]
        )

        self.assertEqual(respuesta.status_code, 403)


class ContrasteTests(BaseContraste):
    def _ctx(self):
        return (
            list(BloquePlan.objects.all()),
            list(CodigoProduccion.objects.all()),
            list(BalanceDia.objects.all()),
            list(Recepcion.objects.filter(estado=Recepcion.Estado.DESCARGADA)),
            list(MovimientoSilo.objects.all()),
            list(Lote.objects.all()),
        )

    def test_sin_nada_real_no_hay_actividad(self):
        BalanceDia.objects.create(
            semana=self.semana, dia=0, recepcion_nestle=100000
        )

        filas = contraste.contrastar_semana(self.semana, *self._ctx())

        self.assertFalse(filas[0].hubo_actividad)
        self.assertEqual(filas[0].leche_recibida.real, 0)

    def test_contrasta_los_kilos_planificados_con_los_producidos(self):
        BloquePlan.objects.create(
            semana=self.semana, equipo=self.scheffers2, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.codigo, cantidad_kg=5000,
        )
        self._lote(kg=4200)

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.kilos.plan, 5000)
        self.assertEqual(fila.kilos.real, 4200)
        self.assertEqual(fila.kilos.diferencia, -800)
        self.assertEqual(fila.kilos.pct, -16.0)

    def test_contrasta_la_leche_consumida_contra_el_libro_mayor(self):
        """
        El plan la deriva del programa; lo real, de las salidas de silo. Dos
        fuentes distintas: si fueran la misma, el contraste siempre cuadraría.
        """
        BloquePlan.objects.create(
            semana=self.semana, equipo=self.scheffers2, dia=0,
            hora_inicio=8, hora_fin=12, tipo=BloquePlan.Tipo.PRODUCCION,
            codigo=self.codigo,
        )  # 4 h × 11.000 = 44.000 planificados

        lote = self._lote(kg=1000)  # receta: 8.000 L reales
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros=8000,
            fecha_hora=datetime(2026, 2, 9, 10, tzinfo=tz.utc),
            origen_tipo=MovimientoSilo.OrigenTipo.LOTE,
            origen_id=lote.id,
        )

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.leche_consumida.plan, 44000)
        self.assertEqual(fila.leche_consumida.real, 8000)
        self.assertTrue(fila.hubo_actividad)

    def test_los_ingresos_no_cuentan_como_consumo(self):
        lote = self._lote()
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=90000,
            fecha_hora=datetime(2026, 2, 9, 8, tzinfo=tz.utc),
        )

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.leche_consumida.real, 0)
        self.assertEqual(fila.lotes, [lote.id])

    def test_contrasta_la_leche_recibida_contra_las_recepciones_descargadas(self):
        BalanceDia.objects.create(
            semana=self.semana, dia=0, recepcion_nestle=100000
        )
        Recepcion.objects.create(
            fecha=date(2026, 2, 9),
            tipo_leche="Entera",
            litros=87000,
            silo=self.silo,
            estado=Recepcion.Estado.DESCARGADA,
        )

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.leche_recibida.plan, 100000)
        self.assertEqual(fila.leche_recibida.real, 87000)
        self.assertEqual(fila.leche_recibida.diferencia, -13000)

    def test_una_recepcion_no_descargada_no_es_leche_recibida(self):
        """Registrada no es lo mismo que dentro del silo."""
        Recepcion.objects.create(
            fecha=date(2026, 2, 9),
            tipo_leche="Entera",
            litros=50000,
            silo=self.silo,
            estado=Recepcion.Estado.REGISTRADA,
        )

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.leche_recibida.real, 0)

    def test_cada_dia_se_contrasta_con_su_fecha_real(self):
        self._lote(fecha=date(2026, 2, 11), kg=3000, codigo="L-MIE")

        filas = contraste.contrastar_semana(self.semana, *self._ctx())

        self.assertEqual(filas[0].kilos.real, 0)
        self.assertEqual(filas[2].kilos.real, 3000, "miércoles")
        self.assertEqual(filas[2].fecha, date(2026, 2, 11))

    def test_sin_plan_no_se_inventa_un_porcentaje(self):
        """Decir «0 % de desvío» sobre un plan vacío parece que se cumplió."""
        self._lote(kg=1000)

        fila = contraste.contrastar_semana(self.semana, *self._ctx())[0]

        self.assertEqual(fila.kilos.plan, 0)
        self.assertIsNone(fila.kilos.pct)

    def test_el_resumen_suma_la_semana(self):
        self._lote(fecha=date(2026, 2, 9), kg=1000, codigo="A")
        self._lote(fecha=date(2026, 2, 10), kg=2000, codigo="B")

        filas = contraste.contrastar_semana(self.semana, *self._ctx())
        resumen = contraste.resumir(filas)

        self.assertEqual(resumen.kilos.real, 3000)
        self.assertEqual(resumen.dias_con_actividad, 2)
