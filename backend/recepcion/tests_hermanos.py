"""
Los módulos de un camión comparten los controles de la carga.

Solo la crioscopía se mide por compartimiento; el resto describe la leche que
trae el camión, y Calidad la teclea una vez. Quién pertenece a la misma carga lo
dice `llegada_id`, que se asigna al registrar el camión — no se deduce de la
guía ni de la patente, que son opcionales las dos.

Lo que se fija aquí son los tres límites de esa comodidad:

1. **No se reescribe lo ya decidido.** El veredicto se deriva de los controles
   en vez de guardarse, así que tocarlos después de liberar cambia el veredicto
   de leche que ya está en el silo.
2. **Dos llegadas distintas no se tocan**, aunque compartan camión, guía y día.
3. **La crioscopía no se comparte.**
"""

from recepcion.models import Recepcion
from recepcion.tests import BaseAPIRecepcion


CARGA_LIMPIA = {
    "delvo": "Negativo",
    "inhibidores": "Negativo",
    "temperatura": 4.0,
    "acidez": 0.15,
    "ph": 6.7,
    "crioscopia": -0.520,
    "organoleptico": "Conforme",
}


class ControlesCompartidosTests(BaseAPIRecepcion):

    def _llegada(self, *modulos, guia="G-1"):
        """Registra un camión con sus compartimientos, como hace la pantalla."""
        respuesta = self.cliente.post(
            "/api/recepcion/recepciones/registrar-llegada/",
            {
                "fecha": "2026-07-20",
                "guia": guia,
                "vehiculo": self.camion.id,
                "procedencia": "Nestlé",
                "tipo_leche": "Entera",
                "modulos": [
                    {"modulo": nombre, "litros": "10000.00"} for nombre in modulos
                ],
            },
            format="json",
        )
        self.assertEqual(respuesta.status_code, 201, respuesta.data)

        return respuesta.json()

    def _decidir(self, identificador, controles, **extra):
        self.cliente.post(
            f"/api/recepcion/recepciones/{identificador}/tomar-muestra/",
            {"codigo_muestra": f"M-{identificador}"},
            format="json",
        )

        return self.cliente.post(
            f"/api/recepcion/recepciones/{identificador}/decidir-calidad/",
            {"controles": controles, **extra},
            format="json",
        )

    def _controles(self, identificador):
        return Recepcion.objects.get(pk=identificador).controles or {}

    def test_los_modulos_de_una_llegada_comparten_el_identificador(self):
        primero, segundo = self._llegada("M1", "M2")

        self.assertEqual(primero["llegada_id"], segundo["llegada_id"])

    def test_un_modulo_pendiente_hereda_los_controles_del_camion(self):
        """La comodidad que justifica todo esto: se teclean una vez."""
        primero, segundo = self._llegada("M1", "M2")

        self.assertEqual(self._decidir(primero["id"], CARGA_LIMPIA).status_code, 200)

        self.assertEqual(self._controles(segundo["id"])["delvo"], "Negativo")

    def test_no_reescribe_los_controles_de_un_hermano_ya_liberado(self):
        """
        El caso que motivó el arreglo, y se reprodujo tal cual: el primer módulo
        quedaba «Aprobada por Calidad» con delvo Negativo, y decidir el segundo
        con delvo Positivo se lo cambiaba. Estado liberado, análisis positivo:
        el registro afirmaba dos cosas incompatibles sobre la misma leche.
        """
        liberado, segundo = self._llegada("M1", "M2")

        self._decidir(liberado["id"], CARGA_LIMPIA)
        self.assertEqual(
            Recepcion.objects.get(pk=liberado["id"]).estado, Recepcion.Estado.LIBERADA
        )

        self._decidir(
            segundo["id"],
            {**CARGA_LIMPIA, "delvo": "Positivo", "crioscopia": -0.521},
            decision="retener",
            motivo="Delvo positivo en el segundo módulo.",
        )

        self.assertEqual(self._controles(liberado["id"])["delvo"], "Negativo")

    def test_tampoco_los_de_un_hermano_retenido(self):
        """Su retención se justificó con los valores que tiene."""
        retenido, segundo = self._llegada("M1", "M2")

        self._decidir(
            retenido["id"],
            {**CARGA_LIMPIA, "delvo": "Positivo"},
            decision="retener",
            motivo="Delvo positivo.",
        )
        self.assertEqual(
            Recepcion.objects.get(pk=retenido["id"]).estado, Recepcion.Estado.RETENIDA
        )

        self._decidir(segundo["id"], {**CARGA_LIMPIA, "crioscopia": -0.521})

        self.assertEqual(self._controles(retenido["id"])["delvo"], "Positivo")

    def test_dos_llegadas_no_se_contaminan_aunque_coincida_todo(self):
        """
        Mismo camión, misma guía, mismo día — y aun así son dos cargas. Es lo
        que gana `llegada_id` frente a deducir el grupo de campos opcionales:
        dos viajes del mismo camión con la misma guía existen, y antes se
        habrían mezclado.
        """
        (primera,) = self._llegada("M1", guia="G-IGUAL")
        (segunda,) = self._llegada("M1", guia="G-IGUAL")

        self.assertNotEqual(primera["llegada_id"], segunda["llegada_id"])

        self._decidir(primera["id"], CARGA_LIMPIA)

        self.assertEqual(self._controles(segunda["id"]), {})

    def test_la_crioscopia_no_se_comparte(self):
        """Se mide por compartimiento: copiarla daría por medido lo que no lo está."""
        primero, segundo = self._llegada("M1", "M2")

        self._decidir(primero["id"], CARGA_LIMPIA)

        self.assertNotIn("crioscopia", self._controles(segundo["id"]))
