"""Recepción nueva después de vaciar un silo con salidas históricas sin FK."""
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils import timezone

from maestros.models import Silo, Vehiculo
from procesos.models import EjecucionProceso, EntradaProceso, EtapaProceso, SalidaProceso
from produccion.models import Lote
from recepcion.models import AnalisisSilo, MovimientoSilo, Recepcion
from recepcion.servicios import saldo_silo
from usuarios.models import PerfilUsuario, Rol

from . import tests_f01_f02_materiales as materiales
from .origenes import origenes_catalogo
from .servicios import transferir
from .tests_vale import BaseVale


class ReusoRecepcionTests(BaseVale):
    _fuente = materiales.MaterialesValeF01F02Tests._fuente

    def setUp(self):
        materiales.MaterialesValeF01F02Tests.setUp(self)
        self.inicio = timezone.now() - timedelta(hours=2)
        MovimientoSilo.objects.filter(silo=self.silo_entera).update(fecha_hora=self.inicio)
        anterior = Silo.objects.create(codigo="ORIGEN-ANTERIOR-REUSO", tipo="silo", capacidad_l=50000)
        self.vale_anterior = self.crear_vale(
            codigo="VE-ANTERIOR-REUSO", silo_entera=anterior, silo_destino=self.silo_entera,
            estado="liberado", volumen="20000", litros_entera="20000", litros_descremada="0",
        )
        etapa = EtapaProceso.objects.get(tipo="estandarizacion", proceso__rutas_producto__producto=self.producto)
        productora = EjecucionProceso.objects.create(
            codigo="EJ-ANTERIOR-REUSO", etapa=etapa, sucursal=self.silo_entera.sucursal,
            vale=self.vale_anterior, estado="cerrada",
        )
        self.material_anterior = SalidaProceso.objects.create(
            ejecucion=productora, silo=self.silo_entera, producto=self.producto,
            cantidad="20000", unidad="L", destino="siguiente_proceso",
        )
        SalidaProceso.objects.filter(pk=self.material_anterior.pk).update(registrada_en=self.inicio + timedelta(seconds=1))
        self.consumidora = EjecucionProceso.objects.create(
            codigo="EJ-CONSUMO-REUSO", etapa=etapa, sucursal=self.silo_entera.sucursal,
            estado="cerrada",
        )
        self.lote_anterior = Lote.objects.create(
            codigo_lote="LOTE-ANTERIOR-REUSO", producto=self.producto,
            fecha=timezone.localdate(), vale=self.vale_anterior, ejecucion=self.consumidora,
        )
        self.entrada_anterior = EntradaProceso.objects.create(
            ejecucion=self.consumidora, silo=self.silo_entera, cantidad="20000", unidad="L",
        )
        self.vaciado = MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo="salida", litros="20000",
            fecha_hora=self.inicio + timedelta(minutes=10), origen_tipo="lote",
            origen_id=self.lote_anterior.pk, lote=self.lote_anterior,
        )
        camion = Vehiculo.objects.create(placa="REUSO-FICTICIO")
        self.recepcion = Recepcion.objects.create(
            fecha=timezone.localdate(), vehiculo=camion, tipo_leche="Entera",
            litros="25000", silo=self.silo_entera, estado="descargada",
            sucursal=self.silo_entera.sucursal,
        )
        self.ingreso = MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo="ingreso", litros="25000",
            fecha_hora=self.inicio + timedelta(minutes=20), origen_tipo="recepcion",
            origen_id=self.recepcion.pk,
        )
        self.retiro = MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo="salida", litros="10000",
            fecha_hora=self.inicio + timedelta(minutes=30), origen_tipo="descremacion",
            origen_id=999,
        )
        self.analizar_origenes()
        self.vale.entera_grasa = Decimal("4.20")
        self.vale.entera_sng = Decimal("8.80")
        self.vale.save()

    def _transferir(self, **extra):
        return transferir(vale_id=self.vale.pk, usuario=self.usuario, **extra)

    def _rechaza_sin_escrituras(self):
        antes = (MovimientoSilo.objects.count(), EntradaProceso.objects.count())
        with self.assertRaises(ValidationError):
            self._transferir()
        self.vale.refresh_from_db()
        self.assertEqual(self.vale.estado, "calculado")
        self.assertEqual(antes, (MovimientoSilo.objects.count(), EntradaProceso.objects.count()))

    def test_recepcion_nueva_no_consume_salida_historica_y_reintento_no_duplica(self):
        self._transferir()
        entrada = EntradaProceso.objects.get(ejecucion__vale=self.vale, silo=self.silo_entera)
        self.assertIsNone(entrada.salida_origen_id)
        self.assertEqual(saldo_silo(self.silo_entera), Decimal("4300.53"))
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("4849.55"))
        self.assertFalse(self.material_anterior.usos_como_origen.exists())
        self.entrada_anterior.refresh_from_db()
        self.assertIsNone(self.entrada_anterior.salida_origen_id)
        foto = (MovimientoSilo.objects.count(), EntradaProceso.objects.count())
        self._transferir()
        self.assertEqual(foto, (MovimientoSilo.objects.count(), EntradaProceso.objects.count()))
        retiro = MovimientoSilo.objects.get(silo=self.silo_entera, origen_tipo="estandarizacion", origen_id=self.vale.pk)
        atribuciones = list(retiro.atribuciones_recepcion.all())
        self.assertEqual([(a.recepcion_id, a.litros) for a in atribuciones], [(self.recepcion.pk, Decimal("10699.47"))])

    def test_catalogo_no_presenta_material_del_ciclo_anterior(self):
        foto = origenes_catalogo([self.silo_entera.pk, self.silo_descremada.pk])
        self.assertNotIn(self.material_anterior.pk, {f["id"] for f in foto})
        self.assertIn(self.fuente.pk, {f["id"] for f in foto})

    def test_eleccion_explicita_del_material_anterior_se_rechaza(self):
        with self.assertRaises(ValidationError):
            self._transferir(salidas_origen={"entera": self.material_anterior.pk})

    def test_sin_consumo_correlacionado_al_vaciado_se_rechaza(self):
        self.entrada_anterior.delete()
        self._rechaza_sin_escrituras()

    def test_vaciado_por_ajuste_se_rechaza(self):
        MovimientoSilo.objects.filter(pk=self.vaciado.pk).update(tipo="ajuste", litros=Decimal("-20000"))
        self._rechaza_sin_escrituras()

    def test_saldo_negativo_intermedio_se_rechaza_aunque_termine_igual(self):
        MovimientoSilo.objects.bulk_create([
            MovimientoSilo(silo=self.silo_entera, tipo="salida", litros="1", fecha_hora=self.inicio - timedelta(seconds=2)),
            MovimientoSilo(silo=self.silo_entera, tipo="ingreso", litros="1", fecha_hora=self.inicio - timedelta(seconds=1)),
        ])
        self._rechaza_sin_escrituras()

    def test_segundo_ingreso_compensado_se_rechaza(self):
        ahora = timezone.now() - timedelta(seconds=2)
        MovimientoSilo.objects.create(silo=self.silo_entera, tipo="ingreso", litros="1", fecha_hora=ahora)
        MovimientoSilo.objects.create(silo=self.silo_entera, tipo="salida", litros="1", fecha_hora=ahora)
        self._rechaza_sin_escrituras()

    def test_ajuste_del_ciclo_nuevo_se_rechaza(self):
        MovimientoSilo.objects.create(
            silo=self.silo_entera, tipo="ajuste", litros="0", fecha_hora=timezone.now(), motivo="Prueba ficticia",
        )
        self._rechaza_sin_escrituras()

    def test_recepcion_no_descargada_se_rechaza(self):
        Recepcion.objects.filter(pk=self.recepcion.pk).update(estado="liberada")
        self._rechaza_sin_escrituras()

    def test_recepcion_con_litros_distintos_se_rechaza(self):
        Recepcion.objects.filter(pk=self.recepcion.pk).update(litros="24000")
        self._rechaza_sin_escrituras()

    def test_recepcion_de_otro_silo_se_rechaza(self):
        Recepcion.objects.filter(pk=self.recepcion.pk).update(silo=self.silo_destino)
        self._rechaza_sin_escrituras()

    def test_atribucion_incompleta_del_retiro_se_rechaza(self):
        self.retiro.atribuciones_recepcion.update(litros="9999")
        self._rechaza_sin_escrituras()

    def test_atribucion_ausente_del_retiro_se_rechaza(self):
        self.retiro.atribuciones_recepcion.all().delete()
        self._rechaza_sin_escrituras()

    def test_atribucion_desconocida_del_retiro_se_rechaza(self):
        self.retiro.atribuciones_recepcion.update(recepcion=None, origen_no_atribuible=True)
        self._rechaza_sin_escrituras()

    def test_recepcion_descremada_no_habilita_componente_entera(self):
        Recepcion.objects.filter(pk=self.recepcion.pk).update(tipo_leche="Descremada")
        self._rechaza_sin_escrituras()

    def test_tipo_descargado_no_se_puede_reescribir_por_modelo(self):
        self.recepcion.tipo_leche = Recepcion.TipoLeche.DESCREMADA
        with self.assertRaisesMessage(ValidationError, "trazabilidad"):
            self.recepcion.save()
        self.recepcion.refresh_from_db()
        self.assertEqual(self.recepcion.tipo_leche, Recepcion.TipoLeche.ENTERA)

    def test_tipo_sin_descarga_sigue_editable(self):
        otra = Recepcion.objects.create(
            fecha=timezone.localdate(), vehiculo=self.recepcion.vehiculo,
            tipo_leche="Entera", litros="100", sucursal=self.recepcion.sucursal,
        )
        otra.tipo_leche = Recepcion.TipoLeche.DESCREMADA
        otra.save()
        otra.refresh_from_db()
        self.assertEqual(otra.tipo_leche, Recepcion.TipoLeche.DESCREMADA)

    def test_tipo_descargado_por_api_devuelve_conflicto_sin_modificar(self):
        PerfilUsuario.objects.filter(usuario=self.usuario).update(rol=Rol.RECEPCION, area=PerfilUsuario.Area.RECEPCION)
        self.usuario.refresh_from_db()
        self.cliente.force_authenticate(self.usuario)
        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{self.recepcion.pk}/", {"tipo_leche": "Descremada"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.recepcion.refresh_from_db()
        self.assertEqual(self.recepcion.tipo_leche, Recepcion.TipoLeche.ENTERA)

    def test_tipo_descargado_sin_cambio_sigue_permitido_por_api(self):
        PerfilUsuario.objects.filter(usuario=self.usuario).update(rol=Rol.RECEPCION, area=PerfilUsuario.Area.RECEPCION)
        self.usuario.refresh_from_db()
        self.cliente.force_authenticate(self.usuario)
        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{self.recepcion.pk}/", {"tipo_leche": "Entera"}, format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

    def test_calidad_sin_segundo_revisor_sigue_bloqueando(self):
        AnalisisSilo.objects.filter(silo=self.silo_entera).update(visualizado_por=None, visualizado_en=None)
        self._rechaza_sin_escrituras()

    def test_api_transfiere_conservando_procedencia_de_recepcion(self):
        respuesta = self.cliente.post(f"/api/estandarizacion/vales/{self.vale.pk}/transferir/", {}, format="json")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(MovimientoSilo.objects.filter(origen_tipo="estandarizacion", origen_id=self.vale.pk).count(), 3)

    def test_material_nuevo_sin_ingreso_productor_se_rechaza(self):
        SalidaProceso.objects.create(
            ejecucion=self.consumidora, silo=self.silo_entera, cantidad="1", unidad="L",
        )
        self._rechaza_sin_escrituras()

    def test_material_con_fecha_igual_al_vaciado_es_ambiguo(self):
        SalidaProceso.objects.filter(pk=self.material_anterior.pk).update(registrada_en=self.vaciado.fecha_hora)
        self._rechaza_sin_escrituras()

    def test_muestra_anterior_o_simultanea_al_ingreso_se_rechaza(self):
        muestras = list(AnalisisSilo.objects.filter(silo=self.silo_entera).order_by("tomado_en", "pk"))
        for indice, muestra in enumerate(muestras):
            AnalisisSilo.objects.filter(pk=muestra.pk).update(
                tomado_en=self.ingreso.fecha_hora - timedelta(seconds=len(muestras) - indice - 1),
            )
        self._rechaza_sin_escrituras()

    def test_fk_a_muestra_anterior_con_igual_composicion_se_rechaza(self):
        self.vale.analisis_entera = AnalisisSilo.objects.filter(silo=self.silo_entera).earliest("tomado_en", "pk")
        self.vale.save()
        self._rechaza_sin_escrituras()

    def test_merma_posterior_del_silo_impide_demostrar_recepcion_exclusiva(self):
        SalidaProceso.objects.create(
            ejecucion=self.consumidora, silo=self.silo_entera, cantidad="1", unidad="L",
            naturaleza="merma", motivo="Ficticio",
        )
        self._rechaza_sin_escrituras()

    def test_material_posterior_en_otra_unidad_se_rechaza(self):
        SalidaProceso.objects.create(
            ejecucion=self.consumidora, silo=self.silo_entera, cantidad="1", unidad="kg",
        )
        self._rechaza_sin_escrituras()

    def test_composicion_del_vale_distinta_del_analisis_se_rechaza(self):
        self.vale.entera_grasa = Decimal("0.60")
        self.vale.save()
        self._rechaza_sin_escrituras()
