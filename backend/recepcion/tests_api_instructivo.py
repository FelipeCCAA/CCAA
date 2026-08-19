from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.utils import timezone

from maestros.models import Vehiculo
from recepcion.models import ModuloRecepcion, Recepcion
from recepcion.tests import BaseAPIRecepcion
from recoleccion.models import CargaModulo, ParadaRuta, RutaRecoleccion
from recoleccion.models import Recoleccion as RecoleccionRecolectada


class RegistrarLlegadaTests(BaseAPIRecepcion):
    def test_un_camion_crea_un_registro_con_sus_modulos(self):
        vehiculo = Vehiculo.objects.create(placa="JLKD92", numero="109")

        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "vehiculo": vehiculo.id,
                "tipo_leche": "Entera",
                "procedencia": "CCAA",
                "litros": "5321",
                "kg_romana": "5430",
                "uso": "semi",
                "uso_numero": 2,
                "certificada": True,
                "hora_arribo_porteria": "07:45",
                "hora_termino_cip": "09:15",
                "modulos": [
                    {"numero": 1, "crioscopia": "-0.521"},
                    {"numero": 2, "crioscopia": "-0.527"},
                ],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 201, respuesta.data)
        self.assertEqual(Recepcion.objects.count(), 1)

        recepcion = Recepcion.objects.get()
        self.assertEqual(recepcion.litros, Decimal("5321.00"))
        self.assertEqual(recepcion.modulos.count(), 2)

    def test_sin_modulos_no_se_registra(self):
        """La crioscopía se mide por compartimiento: sin módulos no hay dónde."""
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "tipo_leche": "Entera",
                "litros": "5321",
                "modulos": [],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_no_se_repite_el_numero_de_modulo(self):
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "tipo_leche": "Entera",
                "litros": "5321",
                "modulos": [{"numero": 1}, {"numero": 1}],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)

    def test_el_numero_de_modulo_no_supera_las_columnas_del_formato(self):
        """El formato solo tiene cuatro columnas (M1-M4): un 99 no es ninguna."""
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-31",
                "tipo_leche": "Entera",
                "litros": "5321",
                "modulos": [{"numero": 99}],
            },
            format="json",
        )

        self.assertEqual(respuesta.status_code, 400)


class DerivadosEnLaApiTests(BaseAPIRecepcion):
    def test_la_ficha_trae_los_calculos_del_formato(self):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5321"),
            kg_romana=Decimal("5430"),
            controles={"grasa": 4.5, "sng": 9.06, "delvo": "Negativo"},
        )

        respuesta = self.cliente.get(
            f"/api/recepcion/recepciones/{recepcion.id}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["kg_guia"], "5480.63")
        self.assertEqual(respuesta.data["diferencia_kg"], "-50.63")
        self.assertAlmostEqual(respuesta.data["solidos_totales"], 13.56, places=2)

    def test_los_catalogos_vienen_del_backend(self):
        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/catalogos-flujo/"
        )

        self.assertEqual(respuesta.status_code, 200)
        valores = [opcion["valor"] for opcion in respuesta.data["usos"]]
        self.assertIn("semi", valores)
        self.assertIn("despacho", valores)


class ResumenDiarioTests(BaseAPIRecepcion):
    def test_totaliza_el_dia_como_el_pie_de_la_planilla(self):
        for litros in ("5321", "8560"):
            Recepcion.objects.create(
                fecha=date(2026, 7, 31),
                tipo_leche=Recepcion.TipoLeche.ENTERA,
                procedencia=Recepcion.Procedencia.CCAA,
                litros=Decimal(litros),
            )

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/resumen-diario/?fecha=2026-07-31"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["litros"], "13881.00")
        self.assertEqual(respuesta.data["por_procedencia"]["CCAA"], "13881.00")

    def test_una_fecha_invalida_responde_400_y_no_revienta(self):
        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/resumen-diario/?fecha=2026-13-45"
        )

        self.assertEqual(respuesta.status_code, 400)
        self.assertIn("fecha", respuesta.data)

    def test_la_romana_ausente_no_contamina_el_total_ni_la_diferencia(self):
        """
        Un camión sin pesar aporta CERO a `kg_romana` y sus kilos completos de
        guía a `diferencia_kg` si se trata la ausencia como cero — el mismo
        defecto que las 254 horas fantasma, trasladado a la hoja
        `Diferencia`. `kg_romana` y `diferencia_kg` se calculan solo sobre
        los camiones que sí tienen romana.
        """
        Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            kg_romana=Decimal("5100"),
        )
        Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            # Sin romana.
        )

        respuesta = self.cliente.get(
            "/api/recepcion/recepciones/resumen-diario/?fecha=2026-07-31"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.data["kg_romana"], "5100.00")
        # kg_guia del ÚNICO camión con romana: 5000 × 1,03 = 5150,00.
        # diferencia = 5100 − 5150 = −50,00. La versión con el defecto daba
        # −5100,00: la contaminación del camión sin pesar (kg_guia 5150 más).
        self.assertEqual(respuesta.data["diferencia_kg"], "-50.00")
        self.assertEqual(respuesta.data["camiones_sin_romana"], 1)


class DecidirCalidadCrioscopiaYPhTests(BaseAPIRecepcion):
    """
    Regresión: `decidir-calidad` dejó de pasarle a `dominio.evaluar_recepcion`
    la crioscopía de los módulos y el `ph_camion`, así que una recepción con
    cualquiera de los dos fuera de rango salía `liberada` en vez de
    `retenida` — y `Recepcion.motivo` quedaba vacío, aunque la evaluación
    embebida en la misma respuesta (que sí los evalúa) mostrara el motivo.
    """

    def _recepcion_muestreada(self, **extra):
        datos = {
            "fecha": date(2026, 7, 31),
            "tipo_leche": Recepcion.TipoLeche.ENTERA,
            "litros": Decimal("5000"),
            "estado": Recepcion.Estado.MUESTREADA,
        }
        datos.update(extra)
        return Recepcion.objects.create(**datos)

    def test_crioscopia_fuera_de_rango_retiene(self):
        recepcion = self._recepcion_muestreada()
        ModuloRecepcion.objects.create(
            recepcion=recepcion, numero=1, crioscopia=Decimal("-0.400")
        )

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/decidir-calidad/",
            {"controles": {"delvo": "Negativo"}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "retenida")
        self.assertIn("Crioscopía", respuesta.data["motivo"])

        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.RETENIDA)
        self.assertIn("Crioscopía", recepcion.motivo)

    def test_ph_camion_fuera_de_rango_retiene(self):
        recepcion = self._recepcion_muestreada(ph_camion=Decimal("12.00"))
        ModuloRecepcion.objects.create(recepcion=recepcion, numero=1)

        respuesta = self.cliente.post(
            f"/api/recepcion/recepciones/{recepcion.id}/decidir-calidad/",
            {"controles": {"delvo": "Negativo"}},
            format="json",
        )

        self.assertEqual(respuesta.status_code, 200, respuesta.data)
        self.assertEqual(respuesta.data["estado"], "retenida")
        self.assertIn("pH del camión", respuesta.data["motivo"])

        recepcion.refresh_from_db()
        self.assertEqual(recepcion.estado, Recepcion.Estado.RETENIDA)
        self.assertIn("pH del camión", recepcion.motivo)


class UsoNumeroApiTests(BaseAPIRecepcion):
    """
    `Recepcion.clean()` («solo los precondensados llevan número de destino»)
    es inalcanzable desde el API porque DRF no llama `full_clean()`. La
    regla se replica en `RecepcionSerializer.validate` con la misma
    constante `Recepcion.USOS_NUMERADOS`.
    """

    def test_un_uso_no_numerado_con_numero_de_destino_se_rechaza(self):
        respuesta = self._crear(uso="despacho", uso_numero=7)

        self.assertEqual(respuesta.status_code, 400, respuesta.data)
        self.assertIn("uso_numero", respuesta.data)
        self.assertEqual(Recepcion.objects.count(), 0)

    def test_un_uso_numerado_con_su_numero_se_acepta(self):
        respuesta = self._crear(uso="semi", uso_numero=2)

        self.assertEqual(respuesta.status_code, 201, respuesta.data)


class DiferenciaRecoleccionLitrosTipoTests(BaseAPIRecepcion):
    """
    `diferencia_recoleccion_litros` es la única derivada `Decimal` que el
    serializer no declaraba explícitamente, así que salía como número JSON
    en vez de string — distinto de sus hermanas y del tipo que declara
    `frontend/src/services/recepcion.service.ts`.
    """

    def _crear_carga(self, litros):
        usuario = User.objects.create_user(username="conductor-test", password="x")
        ruta = RutaRecoleccion.objects.create(
            codigo="RUTA-DRL-1",
            fecha=date(2026, 7, 31),
            vehiculo=self.camion,
            creada_por=usuario,
        )
        parada = ParadaRuta.objects.create(
            ruta=ruta, orden=1, proveedor="Predio X", predio="Predio X",
        )
        recoleccion = RecoleccionRecolectada.objects.create(
            parada=parada,
            fecha_hora=timezone.now(),
            litros_medidos=litros,
            alcohol=RecoleccionRecolectada.Alcohol.CONFORME,
            operador=usuario,
        )
        return CargaModulo.objects.create(
            codigo="CARGA-DRL-1", recoleccion=recoleccion, modulo="M1", litros=litros,
        )

    def test_sale_como_string_no_como_numero(self):
        carga = self._crear_carga(Decimal("4900.00"))
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000.00"),
        )
        ModuloRecepcion.objects.create(
            recepcion=recepcion, numero=1, carga_recoleccion=carga
        )

        respuesta = self.cliente.get(
            f"/api/recepcion/recepciones/{recepcion.id}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        valor = respuesta.json()["diferencia_recoleccion_litros"]
        self.assertIsInstance(valor, str)
        self.assertEqual(valor, "100.00")


class PermanenciaMotivoApiTests(BaseAPIRecepcion):
    """
    `dominio.permanencia` calcula un motivo cuando falta una marca horaria
    («Falta la hora de arribo a portería…»), pero hasta ahora ninguna
    propiedad del modelo ni campo del serializer lo exponía: la pantalla
    mostraba «—» sin decir qué faltaba.
    """

    def test_expone_el_motivo_cuando_falta_una_marca_horaria(self):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            # Sin hora_arribo_porteria ni hora_termino_cip.
        )

        respuesta = self.cliente.get(
            f"/api/recepcion/recepciones/{recepcion.id}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNone(respuesta.data["permanencia_horas"])
        self.assertIn("arribo a portería", respuesta.data["permanencia_motivo"])

    def test_vacio_cuando_si_se_pudo_calcular(self):
        recepcion = Recepcion.objects.create(
            fecha=date(2026, 7, 31),
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=Decimal("5000"),
            hora_arribo_porteria="07:00",
            hora_termino_cip="08:00",
        )

        respuesta = self.cliente.get(
            f"/api/recepcion/recepciones/{recepcion.id}/"
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertIsNotNone(respuesta.data["permanencia_horas"])
        self.assertEqual(respuesta.data["permanencia_motivo"], "")
