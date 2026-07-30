"""
Pruebas de recepción y silos.

Cubren las dos reglas que, si se rompen, dejan entrar leche que no debería
entrar o hacen mentir al saldo de un silo:

- Delvo o inhibidores positivos retienen el camión de forma automática.
- La ocupación es un SALDO del libro de movimientos, no un acumulado de
  recepciones (MODELO_DATOS.md §2.4).
"""

from datetime import date, datetime, timezone as tz

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from maestros.models import Silo, Vehiculo
from usuarios.models import PerfilUsuario, Rol

from . import dominio
from .models import MovimientoSilo, Recepcion


def instante(dia, hora=12):
    return datetime(2026, 7, dia, hora, 0, tzinfo=tz.utc)


class EvaluarRecepcionTests(TestCase):
    def test_sin_controles_no_hay_motivo_para_retener(self):
        self.assertTrue(dominio.evaluar_recepcion({}).conforme)

    def test_sin_controles_tampoco_se_libera(self):
        """
        No tener motivos para retener no es lo mismo que poder liberar. Sin el
        Delvo nadie midió lo que decide, y la leche sin analizar no entra al
        silo — igual que un lote sin análisis no se libera.
        """
        evaluacion = dominio.evaluar_recepcion({})

        self.assertEqual(evaluacion.estado, "sin_analisis")
        self.assertFalse(evaluacion.analizada)
        self.assertFalse(evaluacion.liberable)
        self.assertIn("delvo", evaluacion.faltantes)

    def test_medir_todo_menos_el_delvo_no_alcanza(self):
        evaluacion = dominio.evaluar_recepcion(
            {"acidez": 16.0, "ph": 6.7, "temperatura": 4.0, "crioscopia": -0.52}
        )

        self.assertTrue(evaluacion.conforme, "nada de lo medido se salió de rango")
        self.assertFalse(evaluacion.liberable, "pero falta el que decide")

    def test_un_motivo_manda_sobre_los_controles_que_falten(self):
        """Delvo positivo retiene aunque no se haya medido nada más."""
        evaluacion = dominio.evaluar_recepcion({"delvo": "Positivo"})

        self.assertEqual(evaluacion.estado, "retenida")
        self.assertTrue(evaluacion.analizada)

    def test_controles_normales_liberan(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Negativo", "acidez": 16.0, "ph": 6.7, "temperatura": 4.0}
        )

        self.assertTrue(evaluacion.conforme)
        self.assertEqual(evaluacion.estado, "liberada")

    def test_delvo_positivo_retiene(self):
        """Presencia de antibióticos: esa leche no entra a la planta."""
        evaluacion = dominio.evaluar_recepcion({"delvo": "Positivo"})

        self.assertFalse(evaluacion.conforme)
        self.assertEqual(evaluacion.estado, "retenida")
        self.assertIn("antibióticos", evaluacion.motivos[0])

    def test_inhibidores_positivos_retienen(self):
        self.assertFalse(dominio.evaluar_recepcion({"inhibidores": "Positivo"}).conforme)

    def test_acidez_alta_retiene_e_informa_el_limite(self):
        evaluacion = dominio.evaluar_recepcion({"acidez": 20.0})

        self.assertFalse(evaluacion.conforme)
        self.assertIn("20.0", evaluacion.motivos[0])
        self.assertIn("18", evaluacion.motivos[0])

    def test_ph_fuera_de_rango_en_ambos_extremos(self):
        self.assertFalse(dominio.evaluar_recepcion({"ph": 6.2}).conforme)
        self.assertFalse(dominio.evaluar_recepcion({"ph": 7.1}).conforme)
        self.assertTrue(dominio.evaluar_recepcion({"ph": 6.7}).conforme)

    def test_temperatura_alta_retiene(self):
        self.assertFalse(dominio.evaluar_recepcion({"temperatura": 12.0}).conforme)

    def test_crioscopia_menos_negativa_sugiere_aguado(self):
        """
        El agua sube el punto de congelación: un valor MENOS negativo que el
        límite es la señal. Es fácil equivocarse de signo al implementarlo.
        """
        self.assertFalse(dominio.evaluar_recepcion({"crioscopia": -0.480}).conforme)
        self.assertTrue(dominio.evaluar_recepcion({"crioscopia": -0.530}).conforme)

    def test_acumula_todos_los_motivos(self):
        evaluacion = dominio.evaluar_recepcion(
            {"delvo": "Positivo", "acidez": 25.0, "temperatura": 15.0}
        )

        self.assertEqual(len(evaluacion.motivos), 3)


class OcupacionSiloTests(TestCase):
    def setUp(self):
        self.silo = Silo.objects.create(
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=100000
        )

    def _movimiento(self, tipo, litros, dia=20):
        return MovimientoSilo.objects.create(
            silo=self.silo, tipo=tipo, litros=litros, fecha_hora=instante(dia)
        )

    def _ocupacion(self, hasta=None):
        return dominio.ocupacion_silo(
            self.silo, list(MovimientoSilo.objects.all()), hasta
        )

    def test_un_silo_sin_movimientos_esta_vacio(self):
        self.assertEqual(self._ocupacion().litros, 0)

    def test_la_ocupacion_descuenta_lo_consumido(self):
        """
        No es el acumulado histórico de recepciones: es lo que hay AHORA.
        """
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 30000)
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 20000)
        self._movimiento(MovimientoSilo.Tipo.SALIDA, 18000)

        self.assertEqual(self._ocupacion().litros, 32000)

    def test_un_ajuste_negativo_resta(self):
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 10000)
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.AJUSTE,
            litros=-500,
            fecha_hora=instante(20),
            motivo="Merma medida en la descarga",
        )

        self.assertEqual(self._ocupacion().litros, 9500)

    def test_calcula_el_porcentaje_sobre_la_capacidad(self):
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 25000)

        self.assertEqual(self._ocupacion().pct, 25)

    def test_avisa_cuando_se_supera_la_capacidad(self):
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 120000)

        self.assertTrue(self._ocupacion().excedido)

    def test_un_saldo_negativo_se_informa_en_vez_de_ocultarse(self):
        """
        Un negativo es imposible físicamente: significa que el registro está
        descuadrado. Recortarlo a cero haría que el error nunca se descubra.
        """
        self._movimiento(MovimientoSilo.Tipo.SALIDA, 5000)

        ocupacion = self._ocupacion()

        self.assertEqual(ocupacion.litros, -5000)
        self.assertTrue(ocupacion.negativo)

    def test_se_puede_consultar_el_saldo_a_una_fecha(self):
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 10000, dia=20)
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 7000, dia=25)

        self.assertEqual(self._ocupacion(hasta=instante(22)).litros, 10000)
        self.assertEqual(self._ocupacion().litros, 17000)

    def test_no_mezcla_los_movimientos_de_otro_silo(self):
        otro = Silo.objects.create(
            codigo="SILO 2", tipo=Silo.Tipo.SILO, capacidad_l=100000
        )
        self._movimiento(MovimientoSilo.Tipo.INGRESO, 10000)
        MovimientoSilo.objects.create(
            silo=otro,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=99999,
            fecha_hora=instante(20),
        )

        self.assertEqual(self._ocupacion().litros, 10000)


class BaseAPIRecepcion(TestCase):
    def setUp(self):
        usuario = User.objects.create_user(username="op", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=Rol.RECEPCION)

        self.cliente = APIClient()
        self.cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )

        self.silo = Silo.objects.create(
            codigo="SILO 1", tipo=Silo.Tipo.SILO, capacidad_l=100000
        )
        self.camion = Vehiculo.objects.create(placa="ABCD-12", transportista="Transp. Sur")

    def _crear(self, **extra):
        datos = {
            "fecha": "2026-07-20",
            "tipo_leche": "Entera",
            "litros": "25000.00",
            "silo": self.silo.id,
            "vehiculo": self.camion.id,
            "procedencia": "Nestlé",
        }
        datos.update(extra)
        return self.cliente.post("/api/recepcion/recepciones/", datos, format="json")


class EstadoSegunControlesTests(BaseAPIRecepcion):
    """
    El estado de la recepción sigue al veredicto de sus controles.

    Existen porque faltaba: el veredicto se calculaba y se mostraba, pero no
    movía la recepción. Toda recepción nacía `registrada`, no había forma de
    llevarla a `liberada` desde la aplicación, el botón de descargar nunca
    aparecía — y como la ocupación de un silo es el saldo de sus movimientos,
    la leche registrada nunca llegaba al silo.
    """

    def test_con_los_controles_en_regla_queda_liberada(self):
        respuesta = self._crear(
            controles={
                "delvo": "Negativo",
                "inhibidores": "Negativo",
                "acidez": 16.0,
                "ph": 6.7,
                "temperatura": 4.0,
            }
        )

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["estado"], "liberada")

    def test_con_delvo_positivo_queda_retenida(self):
        respuesta = self._crear(controles={"delvo": "Positivo"})

        self.assertEqual(respuesta.json()["estado"], "retenida")

    def test_sin_el_control_decisivo_se_queda_registrada(self):
        """No se libera sola leche que nadie midió."""
        respuesta = self._crear(controles={"acidez": 16.0, "ph": 6.7})

        self.assertEqual(respuesta.json()["estado"], "registrada")
        self.assertIn("delvo", respuesta.json()["evaluacion"]["faltantes"])

    def test_los_controles_pueden_llegar_despues(self):
        """El camión se registra al llegar y el laboratorio informa luego."""
        creada = self._crear().json()
        self.assertEqual(creada["estado"], "registrada")

        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{creada['id']}/",
            {"controles": {"delvo": "Negativo", "acidez": 16.0}},
            format="json",
        )

        self.assertEqual(respuesta.json()["estado"], "liberada")

    def test_un_estado_explicito_manda_sobre_el_veredicto(self):
        """Recepción puede retener a mano por algo que los controles no ven."""
        respuesta = self._crear(
            controles={"delvo": "Negativo"},
            estado="retenida",
            motivo="El camión llegó con el precinto roto.",
        )

        self.assertEqual(respuesta.json()["estado"], "retenida")

    def test_una_recepcion_descargada_no_cambia_de_estado_sola(self):
        """Su leche ya entró al silo: recalcular el estado la desharía."""
        creada = self._crear(controles={"delvo": "Negativo"}).json()
        self.cliente.post(f"/api/recepcion/recepciones/{creada['id']}/descargar/")

        self.cliente.patch(
            f"/api/recepcion/recepciones/{creada['id']}/",
            {"controles": {"delvo": "Positivo"}},
            format="json",
        )

        recepcion = Recepcion.objects.get(pk=creada["id"])
        self.assertEqual(recepcion.estado, Recepcion.Estado.DESCARGADA)


class FlujoCompletoTests(BaseAPIRecepcion):
    """De registrar el camión a que el silo cambie de saldo."""

    def test_registrar_con_controles_conformes_llega_al_silo(self):
        vacio = self.cliente.get("/api/recepcion/ocupacion/").json()
        self.assertEqual(vacio["litros_totales"], 0)

        creada = self._crear(
            controles={"delvo": "Negativo", "inhibidores": "Negativo", "ph": 6.7}
        ).json()

        self.assertEqual(creada["estado"], "liberada")

        descarga = self.cliente.post(
            f"/api/recepcion/recepciones/{creada['id']}/descargar/"
        )

        self.assertEqual(descarga.status_code, 200)
        self.assertEqual(descarga.json()["estado"], "descargada")

        ocupacion = self.cliente.get("/api/recepcion/ocupacion/").json()

        self.assertEqual(ocupacion["litros_totales"], 25000)
        self.assertEqual(MovimientoSilo.objects.count(), 1)

    def test_una_retenida_no_llega_al_silo(self):
        creada = self._crear(controles={"delvo": "Positivo"}).json()

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{creada['id']}/descargar/"
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(
            self.cliente.get("/api/recepcion/ocupacion/").json()["litros_totales"], 0
        )


class RecepcionAPITests(BaseAPIRecepcion):
    def test_se_registra_una_recepcion(self):
        respuesta = self._crear()

        self.assertEqual(respuesta.status_code, 201)
        self.assertEqual(respuesta.json()["estado"], "registrada")

    def test_el_operador_queda_registrado_solo(self):
        """El dato es para auditoría: teclearlo lo haría menos fiable."""
        self._crear()

        self.assertEqual(Recepcion.objects.first().operador.username, "op")

    def test_la_evaluacion_de_los_controles_llega_calculada(self):
        respuesta = self._crear(controles={"delvo": "Positivo", "acidez": 16.0})

        evaluacion = respuesta.json()["evaluacion"]

        self.assertFalse(evaluacion["conforme"])
        self.assertEqual(evaluacion["estado_sugerido"], "retenida")
        self.assertIn("antibióticos", evaluacion["motivos"][0])

    def test_rechaza_controles_inventados(self):
        respuesta = self._crear(controles={"inventado": 1})

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("controles", respuesta.json())

    def test_rechaza_un_valor_no_admitido_en_delvo(self):
        respuesta = self._crear(controles={"delvo": "Quizás"})

        self.assertEqual(respuesta.status_code, 400)

    def test_retener_exige_motivo(self):
        """Sin motivo, el registro no sirve para auditar."""
        respuesta = self._crear(estado="retenida")

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_retener_con_motivo_si_se_acepta(self):
        respuesta = self._crear(estado="retenida", motivo="Delvo positivo")

        self.assertEqual(respuesta.status_code, 201)


class DescargaTests(BaseAPIRecepcion):
    def _recepcion(self, estado):
        return Recepcion.objects.create(
            fecha=date(2026, 7, 20),
            tipo_leche="Entera",
            litros=25000,
            silo=self.silo,
            estado=estado,
        )

    def test_descargar_una_liberada_crea_el_ingreso_en_el_silo(self):
        recepcion = self._recepcion(Recepcion.Estado.LIBERADA)

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/descargar/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["estado"], "descargada")

        movimiento = MovimientoSilo.objects.get()
        self.assertEqual(movimiento.tipo, "ingreso")
        self.assertEqual(movimiento.litros, 25000)
        self.assertEqual(movimiento.origen_tipo, "recepcion")
        self.assertEqual(movimiento.origen_id, recepcion.id)

    def test_no_se_descarga_una_retenida(self):
        """
        Es la regla que protege la planta: la leche retenida no entra al silo.
        """
        recepcion = self._recepcion(Recepcion.Estado.RETENIDA)

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/descargar/"
        )

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(MovimientoSilo.objects.count(), 0)

    def test_no_se_descarga_dos_veces(self):
        recepcion = self._recepcion(Recepcion.Estado.LIBERADA)
        ruta = f"/api/recepcion/recepciones/{recepcion.id}/descargar/"

        self.cliente.post(ruta)
        respuesta = self.cliente.post(ruta)

        self.assertEqual(respuesta.status_code, 409)
        self.assertEqual(MovimientoSilo.objects.count(), 1)

    def test_no_se_descarga_sin_silo_asignado(self):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 20),
            tipo_leche="Entera",
            litros=1000,
            estado=Recepcion.Estado.LIBERADA,
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/descargar/"
        )

        self.assertEqual(respuesta.status_code, 400)


class OcupacionAPITests(BaseAPIRecepcion):
    def test_el_endpoint_informa_el_saldo_y_sus_alertas(self):
        MovimientoSilo.objects.create(
            silo=self.silo,
            tipo=MovimientoSilo.Tipo.INGRESO,
            litros=120000,
            fecha_hora=instante(20),
        )

        datos = self.cliente.get("/api/recepcion/ocupacion/").json()

        self.assertEqual(datos["silos"][0]["litros"], 120000)
        self.assertTrue(datos["silos"][0]["excedido"])
        self.assertEqual(datos["alertas"]["excedidos"], ["SILO 1"])
        self.assertEqual(datos["litros_totales"], 120000)

    def test_un_ajuste_sin_motivo_se_rechaza(self):
        respuesta = self.cliente.post(
            "/api/recepcion/movimientos/",
            {
                "silo": self.silo.id,
                "tipo": "ajuste",
                "litros": "-500.00",
                "fecha_hora": "2026-07-20T12:00:00Z",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("motivo", respuesta.json())

    def test_un_ingreso_no_puede_ser_negativo(self):
        respuesta = self.cliente.post(
            "/api/recepcion/movimientos/",
            {
                "silo": self.silo.id,
                "tipo": "ingreso",
                "litros": "-500.00",
                "fecha_hora": "2026-07-20T12:00:00Z",
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)


class PermisosRecepcionTests(BaseAPIRecepcion):
    def _cliente_con_rol(self, rol):
        usuario = User.objects.create_user(username=f"u-{rol}", password="x")
        PerfilUsuario.objects.create(usuario=usuario, rol=rol)

        cliente = APIClient()
        cliente.credentials(
            HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=usuario).key}"
        )
        return cliente

    def test_produccion_y_calidad_leen_pero_no_registran(self):
        for rol in [Rol.PRODUCCION, Rol.CALIDAD, Rol.LECTURA]:
            with self.subTest(rol=rol):
                cliente = self._cliente_con_rol(rol)

                self.assertEqual(
                    cliente.get("/api/recepcion/recepciones/").status_code, 200
                )
                self.assertEqual(
                    cliente.post(
                        "/api/recepcion/recepciones/",
                        {"fecha": "2026-07-20", "tipo_leche": "Entera", "litros": "1"},
                        format="json",
                    ).status_code,
                    403,
                )

    def test_los_silos_solo_los_administra_administracion(self):
        cliente = self._cliente_con_rol(Rol.RECEPCION)

        respuesta = cliente.post(
            "/api/maestros/silos/",
            {"codigo": "SILO 9", "tipo": "silo", "capacidad_l": "1000"},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 403)
