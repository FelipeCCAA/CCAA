"""Aceptación OP-02: litros exactos y hechos físicos ya ejecutados."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from maestros.models import Silo
from procesos.models import (
    EjecucionProceso,
    EntradaProceso,
    EtapaProceso,
    ReservaSiloProceso,
    SalidaProceso,
)
from recepcion.models import AtribucionRecepcion, MovimientoSilo
from usuarios.models import PerfilUsuario, Rol

from .models import ValeEstandarizacion
from .tests_vale import BaseVale


class BalanceOP02Tests(BaseVale):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        PerfilUsuario.objects.update_or_create(
            usuario=cls.usuario,
            defaults={
                "rol": Rol.PRODUCCION,
                "area": PerfilUsuario.Area.CONDENSACION,
                "empresa": cls.silo_entera.sucursal.empresa,
                "sucursal": cls.silo_entera.sucursal,
            },
        )
        cls.calidad = get_user_model().objects.create_user("calidad-op02")
        PerfilUsuario.objects.create(
            usuario=cls.calidad,
            rol=Rol.CALIDAD,
            area=PerfilUsuario.Area.CALIDAD,
            empresa=cls.silo_entera.sucursal.empresa,
            sucursal=cls.silo_entera.sucursal,
        )

    def setUp(self):
        self.cliente = APIClient()
        self.cliente.force_authenticate(self.usuario)
        self.cliente_calidad = APIClient()
        self.cliente_calidad.force_authenticate(self.calidad)

    def _datos(self):
        return {
            "producto": self.producto.pk,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera.pk,
            "silo_descremada": self.silo_descremada.pk,
            "silo_destino": self.silo_destino.pk,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
            "litros_crema": "0.00",
        }

    def _foto_libro(self):
        return {
            modelo._meta.label: list(modelo.objects.order_by("pk").values())
            for modelo in (
                MovimientoSilo,
                AtribucionRecepcion,
                EjecucionProceso,
                EntradaProceso,
                SalidaProceso,
            )
        }

    def _foto_vale(self, vale):
        return ValeEstandarizacion.objects.values().get(pk=vale.pk)

    def _transferir(self, vale):
        return self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/transferir/",
            {},
            format="json",
        )

    def _preparar(self, **datos):
        vale = self.crear_vale(**datos)
        self.abastecer_origenes()
        self.analizar_origenes()
        return vale

    def _transferido(self):
        vale = self._preparar()
        respuesta = self._transferir(vale)
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        vale.refresh_from_db()
        return vale

    def test_transferir_rechaza_sobrante_de_volumen_sin_efectos(self):
        self._rechazo_balance("12000.00")

    def test_transferir_rechaza_faltante_de_un_centilitro_sin_efectos(self):
        self._rechazo_balance("9999.99")

    def _rechazo_balance(self, volumen):
        vale = self._preparar(volumen=volumen)
        libro = self._foto_libro()
        documento = self._foto_vale(vale)

        respuesta = self._transferir(vale)

        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto_libro(), libro)
        self.assertEqual(self._foto_vale(vale), documento)
        self.assertIsNone(self._foto_vale(vale)["ejecutado_en"])

    def test_creacion_rechaza_litros_con_mas_de_dos_decimales(self):
        for campo in (
            "volumen",
            "litros_entera",
            "litros_descremada",
            "litros_crema",
        ):
            with self.subTest(campo=campo):
                datos = self._datos()
                datos[campo] = "1.001"
                antes = ValeEstandarizacion.objects.count()

                respuesta = self.cliente.post(
                    "/api/estandarizacion/vales/",
                    datos,
                    format="json",
                )

                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
                self.assertEqual(ValeEstandarizacion.objects.count(), antes)

    def test_patch_previo_rechaza_precision_excesiva_sin_redondear(self):
        vale = self.crear_vale()
        antes = self._foto_vale(vale)

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"litros_entera": "4000.001"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto_vale(vale), antes)

    def test_calcular_rechaza_precision_excesiva_en_cantidades_l(self):
        base = {
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "crema_grasa": "40.00",
            "crema_sng": "5.50",
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "entera_disponible": "20000.00",
            "descremada_disponible": "20000.00",
            "crema_disponible": "500.00",
        }
        for campo in (
            "volumen",
            "entera_disponible",
            "descremada_disponible",
            "crema_disponible",
        ):
            with self.subTest(campo=campo):
                datos = {**base, campo: "10000.001"}
                respuesta = self.cliente.post(
                    "/api/estandarizacion/vales/calcular/",
                    datos,
                    format="json",
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
        self.assertFalse(ValeEstandarizacion.objects.exists())

    def test_calcular_propone_componentes_a_centilitros_que_suman_125_01(self):
        base = {
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "rc_objetivo": "0.4220",
            "volumen": "125.01",
            "entera_disponible": "20000.00",
            "descremada_disponible": "20000.00",
        }
        for con_crema in (False, True):
            with self.subTest(con_crema=con_crema):
                datos = dict(base)
                if con_crema:
                    datos.update(
                        crema_grasa="40.00",
                        crema_sng="5.50",
                        crema_disponible="500.00",
                    )
                respuesta = self.cliente.post(
                    "/api/estandarizacion/vales/calcular/",
                    datos,
                    format="json",
                )
                self.assertEqual(respuesta.status_code, 200, respuesta.data)
                self.assertTrue(respuesta.data["posible"])
                propuestas = [respuesta.data]
                if con_crema:
                    self.assertIsNotNone(respuesta.data["alternativa_sin_crema"])
                    propuestas.append(respuesta.data["alternativa_sin_crema"])
                for propuesta in propuestas:
                    cantidades = [
                        Decimal(str(propuesta[nombre]))
                        for nombre in ("entera", "descremada", "crema")
                    ]
                    self.assertEqual(sum(cantidades), Decimal("125.01"))
                    self.assertTrue(
                        all(c.as_tuple().exponent >= -2 for c in cantidades)
                    )
                    self.assertTrue(all(c >= 0 for c in cantidades))
                    self.assertTrue(
                        any("0,01 L" in aviso for aviso in propuesta["avisos"])
                    )
        self.assertFalse(ValeEstandarizacion.objects.exists())

    def _borrador_completo(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/crear-borrador/",
            self._datos(),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        return ValeEstandarizacion.objects.get(pk=respuesta.data["id"])

    def _confirmacion_rechazada(self, vale):
        libro = self._foto_libro()
        documento = self._foto_vale(vale)
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/confirmar-borrador/",
            {},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 409, respuesta.data)
        self.assertEqual(self._foto_vale(vale), documento)
        self.assertEqual(self._foto_libro(), libro)

    def test_confirmar_borrador_no_consume_codigo_ni_libro_si_saldo_insuficiente(self):
        vale = self._borrador_completo()
        self.abastecer_origenes()
        self.analizar_origenes()
        MovimientoSilo.objects.create(
            silo=self.silo_entera,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros="19999.00",
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Saldo disponible insuficiente",
        )
        self._confirmacion_rechazada(vale)

    def test_confirmar_borrador_no_persiste_si_capacidad_insuficiente(self):
        vale = self._borrador_completo()
        self.abastecer_origenes()
        self.analizar_origenes()
        self.silo_destino.capacidad_l = Decimal("9999.99")
        self.silo_destino.save(update_fields=["capacidad_l"])
        self._confirmacion_rechazada(vale)

    def test_confirmar_borrador_respeta_reserva_de_origen(self):
        vale = self._borrador_completo()
        self.abastecer_origenes()
        self.analizar_origenes()
        ejecucion = EjecucionProceso.objects.create(
            codigo="EJ-RESERVA-CONFIRMAR",
            etapa=EtapaProceso.objects.get(codigo="estandarizar-test"),
            sucursal=self.silo_entera.sucursal,
            responsable=self.usuario,
            estado=EjecucionProceso.Estado.EJECUCION,
        )
        ReservaSiloProceso.objects.create(
            ejecucion=ejecucion,
            silo=self.silo_entera,
            producto=self.producto,
            tipo=ReservaSiloProceso.Tipo.ORIGEN,
            cantidad_planificada="19999.00",
        )
        self._confirmacion_rechazada(vale)

    def test_confirmar_borrador_valido_no_transfiere_hasta_accion_explicita(self):
        vale = self._borrador_completo()
        self.abastecer_origenes()
        self.analizar_origenes()
        libro = self._foto_libro()
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/confirmar-borrador/",
            {},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        vale.refresh_from_db()
        self.assertEqual(vale.estado, vale.Estado.CALCULADO)
        self.assertIsNone(vale.ejecutado_en)
        self.assertEqual(self._foto_libro(), libro)

    def test_crear_calculado_sin_disponibilidad_no_deja_documento_ni_movimientos(self):
        self.abastecer_origenes()
        self.analizar_origenes()
        self.silo_destino.capacidad_l = Decimal("9999.99")
        self.silo_destino.save(update_fields=["capacidad_l"])
        libro = self._foto_libro()
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/",
            self._datos(),
            format="json",
        )
        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertFalse(ValeEstandarizacion.objects.exists())
        self.assertEqual(self._foto_libro(), libro)

    def test_creacion_rechaza_componentes_negativos(self):
        for campo in ("litros_entera", "litros_descremada", "litros_crema"):
            with self.subTest(campo=campo):
                datos = self._datos()
                datos[campo] = "-0.01"
                respuesta = self.cliente.post(
                    "/api/estandarizacion/vales/",
                    datos,
                    format="json",
                )
                self.assertEqual(respuesta.status_code, 400, respuesta.data)
                self.assertIn(campo, respuesta.data)
        self.assertFalse(ValeEstandarizacion.objects.exists())

    def test_ingreso_exacto_no_se_confunde_con_saldo_previo_del_destino(self):
        vale = self._preparar(
            volumen="125.00",
            litros_entera="100.25",
            litros_descremada="24.75",
        )
        MovimientoSilo.objects.create(
            silo=self.silo_destino,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros="50.00",
            fecha_hora=timezone.now(),
            origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
            motivo="Saldo previo independiente de esta mezcla",
        )

        respuesta = self._transferir(vale)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        movimientos = MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.pk,
        )
        salidas = movimientos.filter(tipo=MovimientoSilo.Tipo.SALIDA)
        ingreso = movimientos.get(tipo=MovimientoSilo.Tipo.INGRESO)
        self.assertEqual(salidas.count(), 2)
        self.assertEqual(
            sum(salidas.values_list("litros", flat=True), Decimal("0")),
            Decimal("125.00"),
        )
        self.assertEqual(ingreso.litros, Decimal("125.00"))
        self.assertEqual(
            list(salidas.order_by("litros").values_list("litros", flat=True)),
            [Decimal("24.75"), Decimal("100.25")],
        )
        saldo = sum(
            (m.litros if m.tipo == MovimientoSilo.Tipo.INGRESO else -m.litros)
            for m in MovimientoSilo.objects.filter(silo=self.silo_destino)
        )
        self.assertEqual(saldo, Decimal("175.00"))
        ejecucion = EjecucionProceso.objects.get(vale=vale)
        self.assertEqual(
            sum(ejecucion.entradas.values_list("cantidad", flat=True), Decimal("0")),
            Decimal("125.00"),
        )
        self.assertEqual(ejecucion.salidas.get().cantidad, Decimal("125.00"))

    def test_reintento_de_transferencia_devuelve_200_sin_duplicar_hechos(self):
        vale = self._transferido()
        antes = self._foto_libro()
        sello = vale.ejecutado_en

        respuesta = self._transferir(vale)

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self._foto_libro(), antes)
        vale.refresh_from_db()
        self.assertEqual(vale.ejecutado_en, sello)

    def test_patch_fisico_balanceado_despues_de_transferir_es_rechazado(self):
        vale = self._transferido()
        antes = self._foto_vale(vale)
        libro = self._foto_libro()

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"litros_entera": "4001.00", "litros_descremada": "5999.00"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto_vale(vale), antes)
        self.assertEqual(self._foto_libro(), libro)

    def test_patch_cambia_origen_despues_de_transferir_es_rechazado(self):
        vale = self._transferido()
        otro = Silo.objects.create(
            codigo="SILO-OP02-OTRO",
            tipo=Silo.Tipo.SILO,
            capacidad_l=50000,
            sucursal=self.silo_entera.sucursal,
        )
        antes = self._foto_vale(vale)
        libro = self._foto_libro()

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"silo_entera": otro.pk},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertEqual(self._foto_vale(vale), antes)
        self.assertEqual(self._foto_libro(), libro)

    def test_patch_sin_cambio_fisico_se_permite(self):
        vale = self._transferido()
        libro = self._foto_libro()

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"volumen": "10000.00", "litros_entera": "4000.00"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self._foto_libro(), libro)
        vale.refresh_from_db()
        self.assertEqual(vale.volumen, Decimal("10000.00"))

    def test_patch_de_observaciones_conserva_hechos_fisicos(self):
        vale = self._transferido()
        libro = self._foto_libro()
        sello = vale.ejecutado_en

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"observaciones": "Cambio de turno documentado"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(self._foto_libro(), libro)
        vale.refresh_from_db()
        self.assertEqual(vale.observaciones, "Cambio de turno documentado")
        self.assertEqual(vale.ejecutado_en, sello)

    def test_produccion_no_puede_liberar_mediante_decidir(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": "1.79", "sng": "8.90"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        antes = self._foto_vale(vale)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/decidir/",
            {},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403, respuesta.data)
        self.assertEqual(self._foto_vale(vale), antes)

    def test_calidad_puede_decidir_con_muestra_conforme(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": "1.79", "sng": "8.90"},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200, respuesta.data)

        respuesta = self.cliente_calidad.post(
            f"/api/estandarizacion/vales/{vale.pk}/decidir/",
            {},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.LIBERADO)
        self.assertEqual(
            EjecucionProceso.objects.get(vale=vale).estado,
            EjecucionProceso.Estado.CERRADA,
        )
