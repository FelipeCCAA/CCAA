from datetime import date
from decimal import Decimal

from maestros.models import Vehiculo
from recepcion.models import Recepcion
from recepcion.tests import BaseAPIRecepcion


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
