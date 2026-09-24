"""
El código del vale lo asigna el sistema.

Se prueba sobre el modelo porque la regla vive en su `save()`: así la cubren la
confirmación, la creación directa, el admin y los scripts, sin que ninguno tenga
que acordarse de llamarla.
"""

from datetime import date
from unittest.mock import patch

from .models import CodigoValeNoAsignado, ValeEstandarizacion
from .tests_vale import BaseVale

#: Un día fijo, para que los códigos esperados no dependan de cuándo se corre.
DIA = date(2026, 9, 23)

BORRADOR = ValeEstandarizacion.Estado.BORRADOR
ANULADO = ValeEstandarizacion.Estado.ANULADO

#: Otro día cualquiera, para comprobar que la fecha que se pasa no manda.
OTRO_DIA = date(2026, 1, 1)


def fijar_reloj(prueba):
    """
    Fija `timezone.localdate()` en `DIA` durante la prueba.

    La fecha de creación la sella el sistema al confirmar con el día de hoy, así
    que los códigos esperados (`VE6266-…`) dependen del reloj.
    """
    reloj = patch("django.utils.timezone.localdate", return_value=DIA)
    reloj.start()
    prueba.addCleanup(reloj.stop)


class AsignacionCodigoValeTests(BaseVale):

    def setUp(self):
        fijar_reloj(self)

    def confirmado(self, **extra):
        """Un vale ya confirmado (`calculado`) sin código: el modelo se lo asigna."""
        return self.crear_vale(codigo="", **extra)

    def borrador(self, **extra):
        vale = self.crear_vale(
            codigo=ValeEstandarizacion.nuevo_codigo_borrador(),
            estado=BORRADOR, **extra,
        )
        # Como la vista: confirmar() opera sobre el vale leído de la base, con
        # Decimal reales. `crear_vale` deja los decimales como texto en memoria.
        vale.refresh_from_db()
        return vale

    def anular(self, vale):
        vale.estado = ANULADO
        vale.save(update_fields=["estado", "actualizado_en"])
        vale.refresh_from_db()

    def test_el_primer_vale_del_dia_es_el_01(self):
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_el_segundo_vale_del_dia_es_el_02(self):
        self.confirmado()

        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_la_fecha_la_sella_la_confirmacion_y_no_quien_crea_el_vale(self):
        """Fecha y código se sellan juntos: no pueden decir días distintos."""
        vale = self.confirmado(fecha=OTRO_DIA)

        self.assertEqual(vale.fecha, DIA)
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_confirmar_un_borrador_sella_la_fecha_de_hoy(self):
        vale = self.borrador(fecha=OTRO_DIA)

        self.assertEqual(vale.confirmar(self.usuario), [])

        vale.refresh_from_db()
        self.assertEqual(vale.fecha, DIA)
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_un_borrador_conserva_su_fecha_provisional(self):
        self.assertEqual(self.borrador(fecha=OTRO_DIA).fecha, OTRO_DIA)

    def test_un_borrador_no_recibe_codigo(self):
        self.assertTrue(self.borrador().codigo.startswith("BORRADOR-"))

    def test_un_borrador_descartado_no_consume_numero(self):
        """Descartar anula el borrador; con su `BORRADOR-…` y sin número."""
        descartado = self.borrador()
        self.anular(descartado)

        self.assertTrue(descartado.codigo.startswith("BORRADOR-"))
        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_vale_anulado_conserva_su_numero_y_no_se_reutiliza(self):
        primero = self.confirmado()
        self.anular(primero)

        self.assertEqual(primero.codigo, "VE6266-01")
        self.assertEqual(self.confirmado().codigo, "VE6266-02")

    def test_los_codigos_de_antes_no_cuentan(self):
        for codigo in ("VE-316256", "VE-20260901-01", "jkjfd"):
            self.crear_vale(codigo=codigo, fecha=DIA)

        self.assertEqual(self.confirmado().codigo, "VE6266-01")

    def test_un_codigo_explicito_se_respeta(self):
        """Las pruebas y el histórico crean vales con código propio."""
        self.assertEqual(self.crear_vale(codigo="VE-1", fecha=DIA).codigo, "VE-1")

    def test_confirmar_un_borrador_le_asigna_el_codigo(self):
        vale = self.borrador()

        self.assertEqual(vale.confirmar(self.usuario), [])

        vale.refresh_from_db()
        self.assertEqual(vale.codigo, "VE6266-01")
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CALCULADO)

    def test_una_colision_reintenta_con_el_siguiente_libre(self):
        """
        Dos confirmaciones simultáneas calculan el mismo número. Se simula
        forzando el primer cálculo a proponer uno ya ocupado.
        """
        self.confirmado()  # ocupa VE6266-01
        original = ValeEstandarizacion._siguiente_correlativo
        propuestas = iter([1])

        def forzado(vale, prefijo):
            return next(propuestas, None) or original(vale, prefijo)

        with patch.object(ValeEstandarizacion, "_siguiente_correlativo", forzado):
            vale = self.confirmado()

        self.assertEqual(vale.codigo, "VE6266-02")

    def test_agotados_los_intentos_falla_sin_guardar(self):
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            with self.assertRaises(CodigoValeNoAsignado):
                self.confirmado()

        self.assertEqual(ValeEstandarizacion.objects.filter(fecha=DIA).count(), 1)

    def test_confirmar_sin_codigo_libre_devuelve_motivo_y_sigue_en_borrador(self):
        vale = self.borrador()
        self.confirmado()  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            motivos = vale.confirmar(self.usuario)

        self.assertEqual(
            motivos, ["No se pudo asignar un código de vale; vuelve a confirmar."]
        )
        vale.refresh_from_db()
        self.assertEqual(vale.estado, BORRADOR)
        self.assertTrue(vale.codigo.startswith("BORRADOR-"))


class CodigoValeApiTests(BaseVale):
    """Ningún camino de la API deja escribir el código."""

    def setUp(self):
        fijar_reloj(self)

        from rest_framework.authtoken.models import Token
        from rest_framework.test import APIClient

        from usuarios.models import PerfilUsuario, Rol

        PerfilUsuario.objects.create(usuario=self.usuario, rol=Rol.RECEPCION)
        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.usuario).key}"
        )

    def cuerpo(self, **extra):
        datos = {
            "producto": self.producto.id,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera.id,
            "silo_descremada": self.silo_descremada.id,
            "silo_destino": self.silo_destino.id,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
        }
        datos.update(extra)
        return datos

    def test_la_creacion_directa_asigna_el_codigo_e_ignora_el_del_cliente(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/", self.cuerpo(codigo="jkjfd"), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertEqual(respuesta.json()["codigo"], "VE6266-01")

    def test_la_respuesta_ya_no_trae_codigo_propuesto(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/", self.cuerpo(), format="json"
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertNotIn("codigo_propuesto", respuesta.json())

    def test_un_patch_no_cambia_el_codigo(self):
        vale = self.crear_vale(codigo="", fecha=DIA)

        self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/", {"codigo": "jkjfd"}, format="json"
        )

        vale.refresh_from_db()
        self.assertEqual(vale.codigo, "VE6266-01")

    def test_la_creacion_directa_sin_codigo_libre_responde_400_con_motivo(self):
        self.crear_vale(codigo="", fecha=DIA)  # ocupa VE6266-01

        with patch.object(
            ValeEstandarizacion, "_siguiente_correlativo", lambda vale, prefijo: 1
        ):
            respuesta = self.cliente.post(
                "/api/estandarizacion/vales/", self.cuerpo(), format="json"
            )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("vuelve a confirmar", str(respuesta.json()))

    def test_la_creacion_directa_ignora_la_fecha_del_cliente(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/",
            self.cuerpo(fecha=OTRO_DIA.isoformat()),
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.json())
        self.assertEqual(respuesta.json()["fecha"], DIA.isoformat())

    def test_un_patch_no_cambia_la_fecha(self):
        vale = self.crear_vale(codigo="")

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.id}/",
            {"fecha": OTRO_DIA.isoformat()},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.json())
        vale.refresh_from_db()
        self.assertEqual(vale.fecha, DIA)
