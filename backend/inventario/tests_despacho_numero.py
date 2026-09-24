from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from usuarios.tenancy import unica_sucursal_activa

from . import dominio
from .models import Despacho
from .pruebas_base import EscenarioProductoTerminado
from .servicios import ingresar_pallet

DIA = date(2026, 9, 24)  # día juliano 267


class DominioNumeroDespachoTests(SimpleTestCase):
    def test_prefijo_es_de_mas_ultimo_digito_del_anio_y_dia_juliano(self):
        self.assertEqual(dominio.prefijo_numero_despacho(DIA), "DE6267-")
        self.assertEqual(dominio.prefijo_numero_despacho(date(2026, 1, 5)), "DE6005-")

    def test_el_correlativo_va_siempre_con_dos_cifras_minimo(self):
        self.assertEqual(dominio.generar_numero_despacho(DIA, 1), "DE6267-01")
        self.assertEqual(dominio.generar_numero_despacho(DIA, 123), "DE6267-123")

    def test_correlativo_de_numero_ignora_lo_que_no_tiene_la_forma(self):
        self.assertEqual(dominio.correlativo_de_numero("DE6267-07", "DE6267-"), 7)
        self.assertIsNone(dominio.correlativo_de_numero("D-1", "DE6267-"))
        self.assertIsNone(dominio.correlativo_de_numero("DE6267-xx", "DE6267-"))
        self.assertIsNone(dominio.correlativo_de_numero("", "DE6267-"))


class NumeroDespachoApiTests(EscenarioProductoTerminado):
    def setUp(self):
        super().setUp()
        reloj = mock.patch("inventario.models.timezone.localdate", return_value=DIA)
        reloj.start()
        self.addCleanup(reloj.stop)
        self.dar_permiso("despacho_crear")
        self.liberar()
        ingresar_pallet(self.pallet, self.ubicacion, self.usuario)

    def crear(self, **extra):
        return self.api.post("/api/inventario/despachos/", {
            "cliente": self.cliente.pk, "pallet_ids": [self.pallet.pk], **extra,
        }, format="json")

    def previo(self, numero):
        # La API resuelve la sucursal del despacho con `sucursal_para_escritura`
        # (el registro interno canónico), no con `self.planta`: este despacho
        # previo tiene que vivir en esa misma sucursal para que el correlativo
        # lo vea, igual que hará el que cree `crear()`.
        return Despacho.objects.create(
            sucursal=unica_sucursal_activa(None), numero=numero, cliente=self.cliente,
            creado_por=self.usuario, estado=Despacho.Estado.CANCELADO,
        )

    def test_el_sistema_asigna_el_primer_numero_del_dia(self):
        respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-01")

    def test_el_correlativo_sigue_desde_el_maximo_existente(self):
        self.previo("DE6267-07")
        self.assertEqual(self.crear().data["numero"], "DE6267-08")

    def test_el_numero_que_manda_el_cliente_se_ignora(self):
        respuesta = self.crear(numero="MIO-1")
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-01")

    def test_numeros_antiguos_sin_la_forma_no_rompen_el_calculo(self):
        self.previo("D-1")
        self.previo("DE6267-xx")
        self.assertEqual(self.crear().data["numero"], "DE6267-01")

    def test_una_colision_reintenta_con_el_siguiente(self):
        self.previo("DE6267-01")
        with mock.patch.object(Despacho, "_siguiente_correlativo", side_effect=[1, 2]):
            respuesta = self.crear()
        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(respuesta.data["numero"], "DE6267-02")
