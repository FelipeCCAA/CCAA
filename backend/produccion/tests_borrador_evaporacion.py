from decimal import Decimal

from maestros.models import Equipo, Silo
from procesos.models import (
    CorridaCondensacion,
    EjecucionProceso,
    EtapaProceso,
    Proceso,
    RutaProducto,
)
from produccion.models import Lote, OrdenProduccion
from recepcion.models import MovimientoSilo

from .tests_borrador import BaseBorradorLote


class ConfirmarSobreEvaporadorTests(BaseBorradorLote):
    """Abrir el lote sobre un evaporador también prepara su corrida: todo o nada."""

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

    def borrador_sobre_evaporador(self):
        borrador = self.crear_borrador(observacion="Evaporación")
        datos = self.datos_completos()
        datos.pop("producto")
        datos.update({"equipo": self.evaporador.id, "orden": self.orden.id, "linea": ""})
        guardado = self.cliente.patch(
            f"/api/produccion/lotes/{borrador['id']}/guardar-borrador/", datos, format="json",
        )
        self.assertEqual(guardado.status_code, 200, guardado.json())
        return borrador["id"]

    def confirmar(self, borrador_id, **cuerpo):
        return self.cliente.post(
            f"/api/produccion/lotes/{borrador_id}/confirmar-borrador/", cuerpo, format="json",
        )

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
