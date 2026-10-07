from decimal import Decimal

from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Equipo, Silo
from procesos.models import (
    CorridaCondensacion,
    EjecucionProceso,
    EtapaProceso,
    Proceso,
    ReservaSiloProceso,
    RutaProducto,
)
from produccion.models import Lote, OrdenProduccion
from recepcion.models import MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from .tests_borrador import BaseBorradorLote


class BaseEvaporadorDesdeVale(BaseBorradorLote):
    """
    Un vale liberado, un evaporador con su ruta real y un silo para el
    concentrado, sin pruebas propias: así otras fixtures (cancelar la
    preparación, anular el lote) lo reutilizan sin volver a correr las de
    `ConfirmarSobreEvaporadorTests` (ver `BaseBorradorLote`).
    """

    def setUp(self):
        super().setUp()
        # `BaseBorradorLote` no trae pruebas propias (ver su docstring), así
        # que esta fixture puede reemplazar la ruta torre → secado directo
        # por la ruta real del evaporador sin romper ninguna prueba heredada.
        RutaProducto.objects.filter(producto=self.polvo).delete()
        proceso = Proceso.objects.create(codigo="ruta-evap", nombre="Polvo por evaporador")
        for orden, (codigo, tipo) in enumerate([
            ("estandarizar", EtapaProceso.Tipo.ESTANDARIZACION),
            ("evaporar", EtapaProceso.Tipo.EVAPORACION),
            ("secar", EtapaProceso.Tipo.SECADO),
        ], start=1):
            EtapaProceso.objects.create(
                proceso=proceso, codigo=codigo, nombre=codigo, tipo=tipo, orden=orden,
            )
        RutaProducto.objects.create(
            sucursal=self.sucursal, producto=self.polvo, proceso=proceso, prioridad=1,
        )
        self.evaporador = Equipo.objects.create(
            sucursal=self.sucursal, codigo="ev-p", nombre="Evaporador P",
            tipo=Equipo.Tipo.EVAPORADOR, sigla="EP",
        )
        self.orden = OrdenProduccion.objects.create(
            sucursal=self.sucursal, codigo="OP-EVAP-1", producto=self.polvo,
            cantidad_planificada=12000, unidad="l", equipo=self.evaporador,
            estado=OrdenProduccion.Estado.PROGRAMADA,
        )
        self.concentrado = Silo.objects.create(
            sucursal=self.sucursal, codigo="PC-9", tipo=Silo.Tipo.SILO, capacidad_l=50000,
        )
        # Evaporar es una etapa de Condensación: el cliente por defecto de
        # `BaseApertura` es de Secado, que escribe lotes pero no opera el
        # evaporador (`procesos.permisos.TIPOS_OPERABLES_POR_AREA`).
        self.cliente_secado = self.cliente
        self.cliente = self._cliente_de_area(PerfilUsuario.Area.CONDENSACION)

    def _cliente_de_area(self, area):
        usuario = User.objects.create_user(f"u-evap-{area}", password="x")
        PerfilUsuario.objects.create(
            usuario=usuario, rol=Rol.PRODUCCION, area=area,
            empresa=self.empresa, sucursal=self.sucursal,
            alcance=PerfilUsuario.Alcance.SUCURSAL,
        )
        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def borrador_sobre_evaporador(self, cliente=None):
        cliente = cliente or self.cliente
        respuesta = cliente.post(
            "/api/produccion/lotes/crear-borrador/", {"observacion": "Evaporación"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        borrador = respuesta.json()
        datos = self.datos_completos()
        datos.pop("producto")
        datos.update({"equipo": self.evaporador.id, "orden": self.orden.id, "linea": ""})
        guardado = cliente.patch(
            f"/api/produccion/lotes/{borrador['id']}/guardar-borrador/", datos, format="json",
        )
        self.assertEqual(guardado.status_code, 200, guardado.json())
        return borrador["id"]

    def confirmar(self, borrador_id, cliente=None, **cuerpo):
        return (cliente or self.cliente).post(
            f"/api/produccion/lotes/{borrador_id}/confirmar-borrador/", cuerpo, format="json",
        )


class ConfirmarSobreEvaporadorTests(BaseEvaporadorDesdeVale):
    """Abrir el lote sobre un evaporador también prepara su corrida: todo o nada."""

    def test_sin_destino_no_abre_nada(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("silo_destino", respuesta.json())
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_con_destino_abre_el_lote_y_prepara_la_corrida(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        corrida = CorridaCondensacion.objects.get(lote_id=borrador_id)
        self.assertEqual(corrida.silo_destino, self.concentrado)
        self.assertEqual(corrida.estado, CorridaCondensacion.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.filter(origen_id=borrador_id).count(), 1)

    def test_si_la_corrida_falla_no_queda_lote_ni_movimiento(self):
        self.concentrado.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.concentrado.save(update_fields=["estado"])
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)
        self.assertFalse(CorridaCondensacion.objects.exists())
        # Todo o nada también para la máquina: una corrida que no llegó a
        # crearse no puede dejar el evaporador ocupado para la próxima.
        self.assertFalse(
            EjecucionProceso.objects.filter(equipo=self.evaporador).exists()
        )

    def test_destino_inexistente_responde_400(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=999999)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("silo_destino", respuesta.json())
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_destino_malformado_responde_400(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino="abc")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("silo_destino", respuesta.json())
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def assertNadaAbierto(self, borrador_id):
        self.assertEqual(Lote.objects.get(pk=borrador_id).estado, Lote.Estado.BORRADOR)
        self.assertEqual(MovimientoSilo.objects.count(), 0)
        self.assertFalse(CorridaCondensacion.objects.exists())
        self.assertFalse(
            EjecucionProceso.objects.filter(equipo=self.evaporador).exists()
        )

    def test_secado_no_abre_un_lote_sobre_un_evaporador(self):
        """
        Secado escribe lotes (`EscribeProduccion`), pero no opera la
        evaporación: sin esta puerta abría el lote y dejaba la corrida
        preparada, y recién «Iniciar» lo rechazaba.
        """
        borrador_id = self.borrador_sobre_evaporador(self.cliente_secado)

        respuesta = self.confirmar(
            borrador_id, cliente=self.cliente_secado, silo_destino=self.concentrado.id,
        )

        self.assertEqual(respuesta.status_code, 403, respuesta.json())
        self.assertNadaAbierto(borrador_id)

    def test_condensacion_abre_un_lote_sobre_un_evaporador(self):
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        self.assertTrue(CorridaCondensacion.objects.filter(lote_id=borrador_id).exists())

    def test_destino_sin_capacidad_responde_400_sin_abrir_nada(self):
        self.concentrado.capacidad_l = Decimal("5000")
        self.concentrado.save(update_fields=["capacidad_l"])
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("PC-9", str(respuesta.json()))
        self.assertIn("capacidad", str(respuesta.json()))
        self.assertNadaAbierto(borrador_id)

    def test_destino_reservado_por_otra_ejecucion_responde_400_sin_abrir_nada(self):
        etapa = EtapaProceso.objects.get(proceso__codigo="ruta-evap", codigo="evaporar")
        otra = EjecucionProceso.objects.create(
            codigo="EJ-OTRA-EVAP", etapa=etapa, sucursal=self.sucursal,
        )
        ReservaSiloProceso.objects.create(
            ejecucion=otra, silo=self.concentrado,
            tipo=ReservaSiloProceso.Tipo.DESTINO, cantidad_planificada=Decimal("100"),
        )
        borrador_id = self.borrador_sobre_evaporador()

        respuesta = self.confirmar(borrador_id, silo_destino=self.concentrado.id)

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("reservado por EJ-OTRA-EVAP", str(respuesta.json()))
        self.assertNadaAbierto(borrador_id)
