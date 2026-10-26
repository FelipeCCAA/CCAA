"""Regresiones del consumo de intermedios en un vale, con PostgreSQL real."""
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from calidad.models import LiberacionProceso
from calidad.vigencia import registrar_firma_salida
from calidad.vigencia import exigir_liberacion_salida_vigente
from maestros.models import Producto, Silo
from procesos.models import CorridaDescremacion, EjecucionProceso, EntradaProceso, EtapaProceso, Proceso, RutaProducto, SalidaProceso
from produccion.models import Lote
from recepcion.models import AnalisisSilo, MovimientoSilo
from recepcion.servicios import saldo_silo
from usuarios.models import PerfilUsuario, Rol

from .servicios import transferir
from .tests_vale import BaseVale


class MaterialesValeF01F02Tests(BaseVale):
    def setUp(self):
        PerfilUsuario.objects.update_or_create(
            usuario=self.usuario,
            defaults={"rol": Rol.PRODUCCION, "area": PerfilUsuario.Area.CONDENSACION},
        )
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)
        self.vale = self.crear_vale(
            volumen="15000.00", litros_entera="10699.47", litros_descremada="4300.53",
        )
        ahora = timezone.now()
        for silo, litros in ((self.silo_entera, "20000.00"),):
            MovimientoSilo.objects.create(
                silo=silo, tipo="ingreso", litros=litros, fecha_hora=ahora,
                origen_tipo="ajuste", motivo="Datos ficticios de regresión",
            )
        self.analizar_origenes()
        self.producto_ld = Producto.objects.create(
            codigo="LD-F02", nombre="Descremada ficticia", mandante=self.mandante,
            familia="liquido", naturaleza="intermedio", tipo="descremada", unidad_base="L",
        )
        proceso = Proceso.objects.create(codigo="F02-DES", nombre="Descremado ficticio")
        self.etapa = EtapaProceso.objects.create(
            proceso=proceso, codigo="F02-DES", nombre="Descremado", tipo="descremacion", orden=1,
        )
        self.ruta_ld = RutaProducto.objects.create(
            sucursal=self.silo_descremada.sucursal, producto=self.producto_ld,
            proceso=RutaProducto.objects.get(producto=self.producto).proceso,
        )
        self.fuente = self._fuente("F02-LD-1", "9150.08")

    def _fuente(self, codigo, litros):
        ejecucion = EjecucionProceso.objects.create(
            codigo=codigo, etapa=self.etapa, sucursal=self.silo_descremada.sucursal,
            responsable=self.usuario, estado="cerrada",
        )
        lote = Lote.objects.create(
            codigo_lote=codigo, producto=self.producto_ld, fecha=timezone.localdate(),
        )
        salida = SalidaProceso.objects.create(
            ejecucion=ejecucion, lote=lote, silo=self.silo_descremada,
            producto=self.producto_ld, ruta_producto=self.ruta_ld,
            cantidad=litros, unidad="L", destino="estandarizacion",
        )
        crema, _ = Silo.objects.get_or_create(
            codigo="CREMA-F02", defaults={"tipo": "tk_crema", "capacidad_l": 50000},
        )
        corrida = CorridaDescremacion.objects.create(
            ejecucion=ejecucion, silo_entera=self.silo_entera,
            analisis_entrada=AnalisisSilo.objects.filter(silo=self.silo_entera).latest("id"),
            silo_descremada=self.silo_descremada, estanque_crema=crema,
            litros_entrada=Decimal(litros) + Decimal("100"), grasa_entrada=Decimal("3.6"),
            sng_entrada=Decimal("8.6"), estado="cerrada",
        )
        MovimientoSilo.objects.create(
            silo=self.silo_descremada, tipo="ingreso", litros=litros,
            fecha_hora=timezone.now(), origen_tipo="descremacion", origen_id=corrida.pk,
            operacion_id=corrida.operacion_id,
        )
        self.analizar_origenes()
        analisis = AnalisisSilo.objects.filter(silo=self.silo_descremada).latest("id")
        decision = LiberacionProceso.objects.create(
            salida=salida, analisis_silo=analisis, estado="liberado",
            decidida_por=self.usuario, decidida_en=timezone.now(),
        )
        registrar_firma_salida(decision)
        return salida

    def _transferir(self, **extra):
        return transferir(vale_id=self.vale.pk, usuario=self.usuario, **extra)

    def test_consumo_conserva_fuente_y_un_solo_retiro(self):
        self._transferir()
        entrada = EntradaProceso.objects.get(ejecucion__vale=self.vale, silo=self.silo_descremada)
        self.assertEqual(entrada.salida_origen_id, self.fuente.pk)
        self.assertEqual(entrada.cantidad, Decimal("4300.530"))
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("4849.55"))
        self.assertEqual(MovimientoSilo.objects.filter(silo=self.silo_descremada, tipo="salida").count(), 1)

    def test_disponible_de_produccion_coincide_con_saldo_fisico(self):
        self._transferir()
        respuesta = self.cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        fila = next(f for f in respuesta.data if f["id"] == self.fuente.pk)
        self.assertEqual(fila["cantidad_consumida"], Decimal("4300.53"))
        self.assertEqual(fila["cantidad_disponible"], Decimal("4849.55"))

    def test_reintento_del_vale_no_duplica_consumos(self):
        self._transferir()
        foto = (MovimientoSilo.objects.count(), EntradaProceso.objects.count())
        self._transferir()
        self.assertEqual(foto, (MovimientoSilo.objects.count(), EntradaProceso.objects.count()))

    def test_firma_vencida_rechaza_sin_movimientos(self):
        analisis = self.fuente.liberacion_calidad.analisis_silo
        analisis.ph = Decimal("6.55")
        analisis.save(update_fields=["ph"])
        antes = MovimientoSilo.objects.count()
        with self.assertRaises(ValidationError):
            self._transferir()
        self.assertEqual(MovimientoSilo.objects.count(), antes)
        self.assertFalse(EjecucionProceso.objects.filter(vale=self.vale).exists())

    def test_no_reconstruye_consumo_historico_por_compartir_tanque(self):
        MovimientoSilo.objects.create(
            silo=self.silo_descremada, tipo="salida", litros="100.00",
            fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Historia sin fuente explícita",
        )
        self.analizar_origenes()
        decision = self.fuente.liberacion_calidad
        decision.analisis_silo = AnalisisSilo.objects.filter(silo=self.silo_descremada).latest("id")
        decision.save(update_fields=["analisis_silo"])
        registrar_firma_salida(decision)
        antes = MovimientoSilo.objects.count()
        with self.assertRaisesMessage(ValidationError, "conciliar"):
            self._transferir()
        self.assertEqual(MovimientoSilo.objects.count(), antes)
        self.assertEqual(self.fuente.usos_como_origen.count(), 0)

    def test_varias_fuentes_se_bloquean_sin_un_fifo_inventado(self):
        self._fuente("F02-LD-2", "100.00")
        antes = MovimientoSilo.objects.count()
        with self.assertRaisesMessage(ValidationError, "origen"):
            self._transferir()
        self.assertEqual(MovimientoSilo.objects.count(), antes)

    def test_eleccion_explicita_no_resuelve_composicion_ambigua(self):
        segunda = self._fuente("F02-LD-2", "100.00")
        self.analizar_origenes()
        for fuente in (self.fuente, segunda):
            decision = fuente.liberacion_calidad
            decision.analisis_silo = AnalisisSilo.objects.filter(silo=self.silo_descremada).latest("id")
            decision.save(update_fields=["analisis_silo"])
            registrar_firma_salida(decision)
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{self.vale.pk}/transferir/",
            {"salidas_origen": {"descremada": self.fuente.pk}}, format="json",
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self.fuente.usos_como_origen.count(), 0)
        self.assertEqual(segunda.usos_como_origen.count(), 0)

    def test_ingreso_posterior_compensado_no_inventa_identidad_por_saldo_igual(self):
        for tipo in ("ingreso", "salida"):
            MovimientoSilo.objects.create(
                silo=self.silo_descremada, tipo=tipo, litros="25.00",
                fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Composición desconocida ficticia",
            )
        self.analizar_origenes()
        decision = self.fuente.liberacion_calidad
        decision.analisis_silo = AnalisisSilo.objects.filter(silo=self.silo_descremada).latest("id")
        decision.save(update_fields=["analisis_silo"])
        registrar_firma_salida(decision)
        with self.assertRaisesMessage(ValidationError, "otros ingresos"):
            self._transferir()
        self.assertFalse(self.fuente.usos_como_origen.exists())

    def test_entrada_y_movimiento_etiquetado_son_el_mismo_consumo(self):
        self._transferir()
        # Fixture de compatibilidad: el escritor normal conserva movimiento
        # inmutable; aquí se simula un registro legado etiquetado con el lote.
        MovimientoSilo.objects.filter(
            silo=self.silo_descremada, tipo="salida", origen_id=self.vale.pk,
        ).update(lote=self.fuente.lote)
        respuesta = self.cliente.get("/api/procesos/salidas/disponibles/")
        fila = next(f for f in respuesta.data if f["id"] == self.fuente.pk)
        self.assertEqual(fila["cantidad_disponible"], Decimal("4849.55"))
        self.assertEqual(fila["cantidad_consumida"], Decimal("4300.53"))

    def test_retiro_parcial_posterior_conserva_saldo_acumulado(self):
        self._transferir()
        destino = Silo.objects.create(codigo="DESTINO-PARCIAL-F02", tipo="silo", capacidad_l=50000)
        siguiente = self.crear_vale(
            codigo="VE-PARCIAL-F02", litros_entera="1000.00", litros_descremada="3000.00",
            volumen="4000.00", silo_destino=destino,
        )
        transferir(vale_id=siguiente.pk, usuario=self.usuario)
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("1849.55"))
        self.assertEqual(self.fuente.usos_como_origen.count(), 2)
        self.assertEqual(MovimientoSilo.objects.filter(silo=self.silo_descremada, tipo="salida").count(), 2)

    def test_saldo_previo_compensado_no_acredita_tanque_vacio(self):
        ingreso = MovimientoSilo.objects.get(silo=self.silo_descremada, tipo="ingreso")
        MovimientoSilo.objects.create(
            silo=self.silo_descremada, tipo="ingreso", litros="25.00",
            fecha_hora=ingreso.fecha_hora - timedelta(minutes=1), origen_tipo="ajuste", motivo="Saldo previo ficticio",
        )
        MovimientoSilo.objects.create(
            silo=self.silo_descremada, tipo="salida", litros="25.00",
            fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Retiro ficticio",
        )
        self.analizar_origenes()
        decision = self.fuente.liberacion_calidad
        decision.analisis_silo = AnalisisSilo.objects.filter(silo=self.silo_descremada).latest("id")
        decision.save(update_fields=["analisis_silo"])
        registrar_firma_salida(decision)
        with self.assertRaisesMessage(ValidationError, "saldo previo"):
            self._transferir()
        self.assertFalse(self.fuente.usos_como_origen.exists())

    def test_fallo_tardio_revierte_libro_origenes_y_vale(self):
        antes = MovimientoSilo.objects.count()
        with patch("estandarizacion.servicios.registrar_estandarizacion", side_effect=ValidationError("fallo controlado")):
            with self.assertRaisesMessage(ValidationError, "fallo controlado"):
                self._transferir()
        self.vale.refresh_from_db()
        self.assertIsNone(self.vale.ejecutado_en)
        self.assertEqual(MovimientoSilo.objects.count(), antes)
        self.assertEqual(self.fuente.usos_como_origen.count(), 0)

    def test_consulta_legacy_no_ofrece_mas_que_el_libro_sin_inventar_origen(self):
        MovimientoSilo.objects.create(
            silo=self.silo_descremada, tipo="salida", litros="4300.53",
            fecha_hora=timezone.now(), origen_tipo="estandarizacion", origen_id=self.vale.pk,
        )
        respuesta = self.cliente.get("/api/procesos/salidas/disponibles/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertNotIn(self.fuente.pk, {f["id"] for f in respuesta.data})
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("4849.55"))
        self.assertEqual(self.fuente.usos_como_origen.count(), 0)

    def test_vale_lote_parcial_y_firma_conservan_antecedentes_reales(self):
        from .servicios import decidir, iniciar_agitacion, registrar_muestra
        from procesos.servicios import genealogia_lote
        from produccion.servicios import abrir_lote_desde_vale, registrar_produccion

        ruta = RutaProducto.objects.get(producto=self.producto)
        EtapaProceso.objects.create(
            proceso=ruta.proceso, codigo="SEC-F02", nombre="Secado ficticio", tipo="secado", orden=2,
        )
        self._transferir()
        iniciar_agitacion(vale_id=self.vale.pk)
        registrar_muestra(vale_id=self.vale.pk, grasa=Decimal("1.74"), sng=Decimal("8.66"))
        decidir(vale_id=self.vale.pk, usuario=self.usuario)
        lote = abrir_lote_desde_vale(
            vale=self.vale, codigo_lote="F02-POL-PARCIAL", fecha=timezone.localdate(),
            litros=Decimal("6000.00"), usuario=self.usuario,
        )
        self.assertEqual(lote.ejecucion.entradas.get().salida_origen.ejecucion.vale_id, self.vale.pk)
        lote.kg_producidos = Decimal("500")
        lote.estado = Lote.Estado.PRODUCIDO
        lote.save()
        registrar_produccion(lote=lote)
        datos = genealogia_lote(lote.pk, "atras")
        self.assertIn(self.fuente.lote_id, {n["id"] for n in datos["nodos"]})
        self.assertEqual({t["entrada"]["cantidad"] for t in datos["tramos"]}, {Decimal("4300.53"), Decimal("6000")})
        salida_final = lote.ejecucion.salidas.get()
        decision = LiberacionProceso.objects.create(
            salida=salida_final, estado="liberado", decidida_por=self.usuario,
            decidida_en=timezone.now(),
        )
        registrar_firma_salida(decision)
        exigir_liberacion_salida_vigente(salida_final.pk)
        origen = self.fuente.liberacion_calidad.analisis_silo
        origen.ph = Decimal("6.50")
        origen.save(update_fields=["ph"])
        decision.refresh_from_db()
        self.assertEqual(decision.estado, "pendiente")
        with self.assertRaises(ValidationError):
            exigir_liberacion_salida_vigente(salida_final.pk)
        self.assertEqual(saldo_silo(self.silo_descremada), Decimal("4849.55"))

    def test_otro_ingreso_al_vale_impide_atribuir_lote_y_revierte_retiro(self):
        from .servicios import decidir, iniciar_agitacion, registrar_muestra
        from produccion.servicios import abrir_lote_desde_vale

        ruta = RutaProducto.objects.get(producto=self.producto)
        EtapaProceso.objects.create(
            proceso=ruta.proceso, codigo="SEC-MEZCLA-F02", nombre="Secado ficticio", tipo="secado", orden=2,
        )
        self._transferir()
        iniciar_agitacion(vale_id=self.vale.pk)
        registrar_muestra(vale_id=self.vale.pk, grasa=Decimal("1.74"), sng=Decimal("8.66"))
        decidir(vale_id=self.vale.pk, usuario=self.usuario)
        MovimientoSilo.objects.create(
            silo=self.silo_destino, tipo="ingreso", litros="10.00",
            fecha_hora=timezone.now(), origen_tipo="ajuste", motivo="Otro material ficticio",
        )
        antes = Lote.objects.count()
        with self.assertRaisesMessage(ValidationError, "otro material"):
            abrir_lote_desde_vale(
                vale=self.vale, codigo_lote="F02-NO-ATRIBUIR", fecha=timezone.localdate(),
                litros=Decimal("6000.00"), usuario=self.usuario,
            )
        self.assertEqual(Lote.objects.count(), antes)
        self.assertEqual(saldo_silo(self.silo_destino), Decimal("15010.00"))

    def test_api_advierte_correcciones_fisicas_sin_inventar_aristas(self):
        from uuid import uuid4
        from .models import ActoValeEstandarizacion

        self._transferir()
        lote = Lote.objects.create(
            codigo_lote="F02-CORREGIDO", producto=self.producto,
            fecha=timezone.localdate(), vale=self.vale,
        )
        # Dato documental ficticio para ejercitar la advertencia de lectura;
        # el movimiento de una corrección real se valida en tests OP02.
        ActoValeEstandarizacion.objects.create(
            vale=self.vale, usuario=self.usuario, clave=uuid4(), tipo="adicion",
            motivo="Adición ficticia pendiente de atribución por tramo", litros=Decimal("25.00"),
            silo_contraparte=self.silo_entera,
        )
        respuesta = self.cliente.get(f"/api/procesos/trazabilidad/lotes/{lote.pk}/")
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(len(respuesta.data["advertencias"]), 1)
        self.assertIn("no está atribuida", respuesta.data["advertencias"][0])
