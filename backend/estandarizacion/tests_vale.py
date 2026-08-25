"""
Pruebas del ciclo del vale de estandarización.

Lo que se fija aquí no es que el vale guarde campos, sino las tres reglas que
la planta pone sobre él:

1. **Muestrear antes de los 30 minutos de agitación avisa, no bloquea**
   (decisión de planta, 2026-08-17) — y el vale sella `muestreado_en` para que
   el aviso sea auditable.
2. **Liberar no se pide: se calcula** desde el RC medido.
3. **Corregir reinicia el reloj**, porque agregar leche deshace la mezcla.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Mandante, Producto, Silo
from usuarios.models import PerfilUsuario, Rol
from recepcion.models import MovimientoSilo

from . import servicios
from .models import MINUTOS_DE_AGITACION, ValeEstandarizacion


class BaseVale(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user(
            username="operador", password="x"
        )
        cls.mandante, _ = Mandante.objects.update_or_create(
            nombre="Mandante de prueba"
        )
        cls.producto = Producto.objects.create(
            codigo="TEST-RC", nombre="Precondensado RC 0,201",
            familia=Producto.Familia.LIQUIDO,
            naturaleza=Producto.Naturaleza.INTERMEDIO,
            unidad_base=Producto.Unidad.L,
            mandante=cls.mandante,
        )
        # `update_or_create`: las migraciones de datos siembran también la base
        # de pruebas, y un `create` chocaría con la unicidad del código.
        cls.silo_entera, _ = Silo.objects.update_or_create(
            codigo="SILO-E-TEST",
            defaults={"tipo": Silo.Tipo.SILO, "capacidad_l": 50000},
        )
        cls.silo_descremada, _ = Silo.objects.update_or_create(
            codigo="TK-LD-TEST",
            defaults={"tipo": Silo.Tipo.TK_LD, "capacidad_l": 50000},
        )
        cls.silo_destino, _ = Silo.objects.update_or_create(
            codigo="SILO-D-TEST",
            defaults={"tipo": Silo.Tipo.SILO, "capacidad_l": 50000},
        )

    def crear_vale(self, **extra):
        datos = {
            "codigo": "VE-0001",
            "fecha": timezone.localdate(),
            "producto": self.producto,
            "rc_objetivo": "0.2010",
            "volumen": "10000.00",
            "silo_entera": self.silo_entera,
            "silo_descremada": self.silo_descremada,
            "silo_destino": self.silo_destino,
            "entera_grasa": "3.90",
            "entera_sng": "8.60",
            "descremada_grasa": "0.05",
            "descremada_sng": "8.90",
            "litros_entera": "4000.00",
            "litros_descremada": "6000.00",
        }
        datos.update(extra)

        return ValeEstandarizacion.objects.create(**datos)

    def abastecer_origenes(self):
        ahora = timezone.now()
        MovimientoSilo.objects.bulk_create([
            MovimientoSilo(
                silo=self.silo_entera,
                tipo=MovimientoSilo.Tipo.INGRESO,
                litros="20000.00",
                fecha_hora=ahora,
                origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
                motivo="Preparacion de la prueba",
            ),
            MovimientoSilo(
                silo=self.silo_descremada,
                tipo=MovimientoSilo.Tipo.INGRESO,
                litros="20000.00",
                fecha_hora=ahora,
                origen_tipo=MovimientoSilo.OrigenTipo.AJUSTE,
                motivo="Preparacion de la prueba",
            ),
        ])

    def llevar_a_agitando(self, vale, minutos=MINUTOS_DE_AGITACION):
        """Deja el vale agitando desde hace `minutos`."""
        self.abastecer_origenes()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)
        servicios.iniciar_agitacion(vale_id=vale.pk)

        vale.refresh_from_db()
        vale.agitacion_desde = timezone.now() - timedelta(minutes=minutos)
        vale.save(update_fields=["agitacion_desde"])

        return vale


class AgitacionTests(BaseVale):

    def test_transferir_mueve_litros_entre_silos(self):
        vale = self.crear_vale()
        self.abastecer_origenes()

        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        movimientos = MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.id,
        )
        self.assertEqual(movimientos.count(), 3)
        self.assertTrue(movimientos.filter(
            silo=self.silo_entera,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros="4000.00",
        ).exists())
        self.assertTrue(movimientos.filter(
            silo=self.silo_descremada,
            tipo=MovimientoSilo.Tipo.SALIDA,
            litros="6000.00",
        ).exists())
        self.assertTrue(movimientos.filter(
            silo=self.silo_destino,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros="10000.00",
        ).exists())

    def test_no_transfiere_desde_silo_bloqueado_por_calidad(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        self.silo_entera.estado = Silo.Estado.BLOQUEADO_CALIDAD
        self.silo_entera.save(update_fields=["estado"])

        with self.assertRaises(ValidationError):
            servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        self.assertFalse(MovimientoSilo.objects.filter(
            origen_tipo=MovimientoSilo.OrigenTipo.ESTANDARIZACION,
            origen_id=vale.id,
        ).exists())

    def test_muestrear_antes_de_los_treinta_avisa_pero_no_frena(self):
        """
        Decisión de planta (2026-08-17): la regla de §10.3 dejó de bloquear.
        Una muestra temprana mide una mezcla que todavía no es homogénea, así
        que el vale queda con el aviso y con la hora del muestreo — que es lo
        que permite auditar después cuánto agitó de verdad.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=20)

        actualizado, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.MUESTREADO)
        self.assertEqual(len(avisos), 1)
        self.assertIn("20", avisos[0])

        vale.refresh_from_db()
        self.assertIsNotNone(vale.muestreado_en)
        self.assertAlmostEqual(vale.minutos_agitando, 20, places=0)

    def test_muestrear_a_tiempo_no_devuelve_avisos(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        _, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(avisos, [])

    def test_cumplidos_los_treinta_se_muestrea(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.MUESTREADO)
        self.assertAlmostEqual(vale.rc_real, 0.2011, places=3)

    def test_sin_agitar_no_se_muestrea(self):
        vale = self.crear_vale()
        self.abastecer_origenes()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        with self.assertRaises(ValidationError):
            servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)

    def test_el_reloj_lo_pone_el_servidor(self):
        """
        La hora de inicio no se recibe: es lo que decide si la muestra dispara
        el aviso de agitación corta, y aceptarla de fuera permitiría declarar
        treinta minutos que no ocurrieron.
        """
        vale = self.crear_vale()
        self.abastecer_origenes()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        antes = timezone.now()
        servicios.iniciar_agitacion(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertGreaterEqual(vale.agitacion_desde, antes)

    def test_muestreado_en_congela_los_minutos_de_agitacion(self):
        """
        Sin el sello, `minutos_agitando` cuenta contra el reloj actual: un vale
        mirado más tarde informa el tiempo transcurrido y no el que agitó, y la
        advertencia de muestreo temprano deja de ser auditable.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=40)

        vale.muestreado_en = vale.agitacion_desde + timedelta(minutes=12)
        vale.save(update_fields=["muestreado_en"])
        vale.refresh_from_db()

        # 12, no 40: cuenta hasta la muestra, no hasta ahora.
        self.assertAlmostEqual(vale.minutos_agitando, 12, places=1)

    def test_avisa_cuando_se_muestrea_antes_de_los_treinta(self):
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=12)

        avisos = vale.avisos_de_muestreo

        self.assertEqual(len(avisos), 1)
        self.assertIn("12", avisos[0])
        self.assertIn(str(MINUTOS_DE_AGITACION), avisos[0])

    def test_cumplidos_los_treinta_no_avisa_nada(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        self.assertEqual(vale.avisos_de_muestreo, [])

    def test_sin_agitar_no_hay_nada_que_avisar(self):
        """
        Un vale que no arrancó el reloj no se puede muestrear igual: lo impide
        la transición, no este aviso. Devolver un aviso aquí sería advertir de
        algo que ya está prohibido por otra vía.
        """
        vale = self.crear_vale()

        self.assertIsNone(vale.agitacion_desde)
        self.assertEqual(vale.avisos_de_muestreo, [])

    def test_sin_muestrear_los_minutos_siguen_corriendo(self):
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=40)

        self.assertIsNone(vale.muestreado_en)
        self.assertAlmostEqual(vale.minutos_agitando, 40, places=1)


class DecisionTests(BaseVale):

    def _muestrear(self, grasa, sng):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=grasa, sng=sng)

        return vale

    def test_si_el_rc_cumple_se_libera(self):
        vale = self._muestrear(grasa=1.79, sng=8.9)

        actualizado, evaluacion = servicios.decidir(
            vale_id=vale.pk, usuario=self.usuario
        )

        self.assertTrue(evaluacion.cumple)
        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)

    def test_si_el_rc_no_cumple_va_a_correccion_con_el_motivo(self):
        """
        El motivo queda escrito en el vale: es lo que le dice al operador qué
        agregar. Un vale «no conforme» sin decir qué falta obliga a rehacer el
        cálculo a mano.
        """
        vale = self._muestrear(grasa=2.20, sng=8.9)

        actualizado, evaluacion = servicios.decidir(
            vale_id=vale.pk, usuario=self.usuario
        )

        self.assertFalse(evaluacion.cumple)
        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.CORRIGIENDO)
        self.assertEqual(evaluacion.agregar, "descremada")
        self.assertIn("sobra", actualizado.observaciones)

    def test_la_decision_no_se_recibe_se_calcula(self):
        """
        No hay forma de pedir «liberado»: `decidir` no acepta el destino. Si
        alguien se lo agregara, esta prueba no lo vería —por eso el estado se
        comprueba contra el análisis, que es lo que manda.
        """
        vale = self._muestrear(grasa=2.20, sng=8.9)

        actualizado, _ = servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertNotEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)

    def test_no_se_decide_sin_muestra(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        with self.assertRaises(ValidationError) as fallo:
            servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertIn("muestreado", fallo.exception.messages[0])


class CorreccionTests(BaseVale):

    def test_reagitar_reinicia_el_reloj_y_borra_el_analisis(self):
        """
        Agregar leche deshace la homogeneidad: los treinta minutos se cuentan
        otra vez desde cero, y el análisis anterior ya no describe lo que hay
        en el silo. Conservar cualquiera de los dos dejaría liberar contra una
        medición que no corresponde.
        """
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.AGITANDO)
        self.assertIsNone(vale.grasa_real)
        self.assertLess(vale.minutos_agitando, 1)

        # Se puede muestrear de inmediato, pero avisa: el reloj arrancó de nuevo.
        self.assertIsNone(vale.muestreado_en)

        _, avisos = servicios.registrar_muestra(
            vale_id=vale.pk, grasa=1.79, sng=8.9
        )

        self.assertEqual(len(avisos), 1)

    def test_reagitar_limpia_el_sello_del_muestreo_anterior(self):
        """
        Si `muestreado_en` sobrevive al reagitado queda **antes** del nuevo
        `agitacion_desde`, y `minutos_agitando` sale negativo: el vale diría
        que agitó menos que nada y el aviso quedaría deformado.
        """
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        vale.refresh_from_db()
        self.assertIsNotNone(vale.muestreado_en)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()

        self.assertIsNone(vale.muestreado_en)
        self.assertGreaterEqual(vale.minutos_agitando, 0)

    def test_el_ciclo_completo_termina_liberando(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=2.20, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        servicios.reagitar(vale_id=vale.pk)
        vale.refresh_from_db()
        vale.agitacion_desde = timezone.now() - timedelta(
            minutes=MINUTOS_DE_AGITACION
        )
        vale.save(update_fields=["agitacion_desde"])

        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        actualizado, _ = servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.LIBERADO)


class TransicionesTests(BaseVale):

    def test_un_vale_liberado_no_vuelve_atras(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        for accion in (servicios.reagitar, servicios.iniciar_agitacion):
            with self.subTest(accion=accion.__name__):
                with self.assertRaises(ValidationError):
                    accion(vale_id=vale.pk)

    def test_no_se_agita_lo_que_no_se_transfirio(self):
        vale = self.crear_vale()

        with self.assertRaises(ValidationError):
            servicios.iniciar_agitacion(vale_id=vale.pk)

    def test_anular_exige_motivo(self):
        """
        Un vale anulado en blanco no distingue el error de captura del silo que
        se contaminó, y es lo primero que se pregunta al auditarlo.
        """
        vale = self.crear_vale()

        with self.assertRaises(ValidationError):
            servicios.anular(vale_id=vale.pk, motivo="   ")

        actualizado = servicios.anular(vale_id=vale.pk, motivo="Silo contaminado")

        self.assertEqual(actualizado.estado, ValeEstandarizacion.Estado.ANULADO)
        self.assertIn("Silo contaminado", actualizado.observaciones)

    def test_un_vale_liberado_no_se_anula(self):
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        servicios.decidir(vale_id=vale.pk, usuario=self.usuario)

        with self.assertRaises(ValidationError):
            servicios.anular(vale_id=vale.pk, motivo="me arrepentí")


class ApiTests(BaseVale):
    """
    La API por encima del servicio. Lo que se comprueba no es que responda 200,
    sino que **no ofrezca un atajo alrededor de las reglas**.
    """

    def setUp(self):
        operador = get_user_model().objects.create_user(username="api", password="x")
        PerfilUsuario.objects.create(usuario=operador, rol=Rol.RECEPCION)

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=operador).key}"
        )

    def test_el_estado_no_se_mueve_con_un_patch(self):
        """
        La regla de liberación vive en `decidir`, que la calcula. Si `estado`
        fuera escribible, un `PATCH estado=liberado` liberaría un vale sin
        muestra y sin RC — la regla completa se saltaría con una petición.
        """
        vale = self.crear_vale()

        respuesta = self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"estado": "liberado"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.CALCULADO)

    def test_guia_rc_agrupa_los_objetivos_usados_por_producto(self):
        self.crear_vale(codigo="VE-GUIA-1")
        self.crear_vale(codigo="VE-GUIA-2")

        respuesta = self.cliente.get("/api/estandarizacion/vales/guia-rc/")

        self.assertEqual(respuesta.status_code, 200)
        fila = next(item for item in respuesta.json() if item["rc_objetivo"] == "0.2010")
        self.assertEqual(fila["producto"], self.producto.pk)
        self.assertEqual(fila["usos"], 2)

    def test_el_analisis_tampoco_se_escribe_por_patch(self):
        """
        El análisis entra por la acción, que es la que sella `muestreado_en` y
        calcula los avisos. Un PATCH lo escribiría sin nada de eso.
        """
        vale = self.crear_vale()

        self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"grasa_real": "1.79", "sng_real": "8.90"},
            format="json",
        )

        vale.refresh_from_db()
        self.assertIsNone(vale.grasa_real)

    def test_muestrear_antes_de_tiempo_responde_200_con_aviso(self):
        """
        Era un 409. Desde 2026-08-17 la regla avisa y no bloquea, así que la
        muestra entra y el aviso viaja en el cuerpo.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=5)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)

        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "muestreado")
        self.assertEqual(len(cuerpo["avisos"]), 1)
        self.assertIn("Agitó 5 minutos", cuerpo["avisos"][0])
        self.assertIsNotNone(cuerpo["muestreado_en"])

    def test_muestrear_a_tiempo_responde_sin_avisos(self):
        vale = self.llevar_a_agitando(self.crear_vale())

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["avisos"], [])
        # El sello se escribe siempre, no solo en el camino con aviso: es lo
        # que hace auditable el ciclo completo, con aviso o sin él.
        self.assertIsNotNone(cuerpo["muestreado_en"])

    def test_muestrear_sin_haber_agitado_responde_409(self):
        """
        Única prueba del módulo que ejercita `except DjangoValidationError →
        _conflicto` en `views.py` para la acción `muestrear`. Un vale recién
        transferido no puede muestrearse — lo impide `TRANSICIONES`, que esta
        prueba ancla en la frontera de la API: si alguien quitara el
        `try/except`, esto respondería 500 en vez de 409.
        """
        vale = self.crear_vale()
        self.abastecer_origenes()
        servicios.transferir(vale_id=vale.pk, usuario=self.usuario)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 409)

        vale.refresh_from_db()
        self.assertEqual(vale.estado, ValeEstandarizacion.Estado.TRANSFERIDO)

    def test_muestreado_en_resiste_un_patch(self):
        """
        El serializer lo declara de solo lectura; esta prueba lo comprueba en
        la frontera de la API, igual que ya existe para `estado` y para el
        análisis.
        """
        vale = self.llevar_a_agitando(self.crear_vale())
        servicios.registrar_muestra(vale_id=vale.pk, grasa=1.79, sng=8.9)
        vale.refresh_from_db()
        sellado_original = vale.muestreado_en

        self.cliente.patch(
            f"/api/estandarizacion/vales/{vale.pk}/",
            {"muestreado_en": "2020-01-01T00:00:00Z"},
            format="json",
        )

        vale.refresh_from_db()
        self.assertEqual(vale.muestreado_en, sellado_original)

    def test_el_aviso_sobrevive_a_decidir_y_liberado(self):
        """
        Es la afirmación central de auditabilidad: un vale muestreado temprano
        y liberado después sigue mostrando el aviso, en vez de perderlo al
        cambiar de estado. `muestreado_en` queda congelado y `avisos_de_muestreo`
        se sigue calculando contra él, no contra el estado actual.
        """
        vale = self.llevar_a_agitando(self.crear_vale(), minutos=5)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/muestrear/",
            {"grasa": 1.79, "sng": 8.9},
            format="json",
        )
        self.assertEqual(len(respuesta.json()["avisos"]), 1)

        respuesta = self.cliente.post(
            f"/api/estandarizacion/vales/{vale.pk}/decidir/", format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["estado"], "liberado")
        self.assertEqual(len(cuerpo["avisos"]), 1)
        self.assertIn("Agitó 5 minutos", cuerpo["avisos"][0])

    def test_calcular_no_crea_nada(self):
        """
        Es el paso que el operador repite variando el volumen: guardar cada
        tanteo llenaría la tabla de vales muertos.
        """
        antes = ValeEstandarizacion.objects.count()

        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/calcular/",
            {
                "entera_grasa": 3.9, "entera_sng": 8.6,
                "descremada_grasa": 0.05, "descremada_sng": 8.9,
                "rc_objetivo": 0.201, "volumen": 10000,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.json()["posible"])
        self.assertEqual(ValeEstandarizacion.objects.count(), antes)

    def test_calcular_avisa_cuando_el_rc_no_se_alcanza(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/calcular/",
            {
                "entera_grasa": 3.6, "entera_sng": 8.6,
                "descremada_grasa": 0.05, "descremada_sng": 8.9,
                "rc_objetivo": 0.422, "volumen": 10000,
            },
            format="json",
        )

        cuerpo = respuesta.json()
        self.assertFalse(cuerpo["posible"])
        self.assertIn("no se alcanza", cuerpo["motivo"])

    def test_calcular_solo_entera_no_inventa_falta_de_descremada(self):
        respuesta = self.cliente.post(
            "/api/estandarizacion/vales/calcular/",
            {
                "entera_grasa": 3.9, "entera_sng": 8.6,
                "entera_disponible": 10000,
                "rc_objetivo": 3.9 / 8.6, "volumen": 10000,
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertTrue(cuerpo["posible"])
        self.assertEqual(cuerpo["entera"], 10000)
        self.assertEqual(cuerpo["descremada"], 0)
        self.assertFalse(any("descremada" in aviso for aviso in cuerpo["avisos"]))

    def test_los_minutos_se_sirven_desde_el_backend(self):
        """
        La pantalla dibuja la cuenta regresiva contra este número. Escribirlo
        en el frontend crearía una copia que puede ofrecer el botón antes que
        el servidor.
        """
        respuesta = self.cliente.get("/api/estandarizacion/vales/catalogos/")

        self.assertEqual(
            respuesta.json()["minutos_agitacion"], MINUTOS_DE_AGITACION
        )


class ReglasDelDocumentoTests(BaseVale):

    def test_el_destino_no_puede_ser_el_origen(self):
        vale = ValeEstandarizacion(
            codigo="VE-X", fecha=timezone.localdate(), producto=self.producto,
            rc_objetivo="0.2010", volumen="1000.00",
            silo_entera=self.silo_entera,
            silo_descremada=self.silo_descremada,
            silo_destino=self.silo_entera,
            entera_grasa="3.90", entera_sng="8.60",
            descremada_grasa="0.05", descremada_sng="8.90",
            litros_entera="400.00", litros_descremada="600.00",
        )

        with self.assertRaises(ValidationError):
            vale.clean()

    def test_la_composicion_queda_congelada_en_el_vale(self):
        """
        La composición se guarda **en el vale** y no se lee del silo al
        mirarlo: el silo cambia con cada ingreso, y un vale de mayo tiene que
        poder auditarse contra la leche que había en mayo.
        """
        vale = self.crear_vale()

        self.assertEqual(float(vale.entera_grasa), 3.90)
        self.assertEqual(float(vale.descremada_sng), 8.90)
