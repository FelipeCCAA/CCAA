"""
Los módulos de un camión comparten los controles de la carga.

Solo la crioscopía se mide por compartimiento; el resto describe la leche que
trae el camión, y Calidad la teclea una vez. Lo que se fija aquí son los dos
límites de esa comodidad, que es donde estaba el riesgo:

1. **No se reescribe lo ya decidido.** El veredicto se deriva de los controles
   en vez de guardarse, así que tocarlos después de liberar cambia el veredicto
   de leche que ya está en el silo.
2. **No se agrupa lo que no es un camión.** Sin patente y sin guía no hay carga
   común que compartir.
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

    def test_un_modulo_pendiente_hereda_los_controles_del_camion(self):
        """Es la comodidad que justifica todo esto: se teclean una vez."""
        primero = self._crear(modulo="M1", guia="G-1").json()
        segundo = self._crear(modulo="M2", guia="G-1").json()

        self.assertEqual(self._decidir(primero["id"], CARGA_LIMPIA).status_code, 200)

        self.assertEqual(self._controles(segundo["id"])["delvo"], "Negativo")

    def test_no_reescribe_los_controles_de_un_hermano_ya_liberado(self):
        """
        El caso que motivó el arreglo, y se reprodujo tal cual: el primero
        quedaba «Aprobada por Calidad» con delvo Negativo, y decidir el segundo
        con delvo Positivo se lo cambiaba. Estado liberado, análisis positivo:
        el registro afirmaba dos cosas incompatibles sobre la misma leche.
        """
        liberado = self._crear(modulo="M1", guia="G-2").json()
        segundo = self._crear(modulo="M2", guia="G-2").json()

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
        retenido = self._crear(modulo="M1", guia="G-3").json()
        segundo = self._crear(modulo="M2", guia="G-3").json()

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

    def test_sin_patente_ni_guia_cada_modulo_va_solo(self):
        """
        No hay camión que compartir. Agruparlos juntaría recepciones que no
        tienen nada que ver — la base de planta ya trae dos filas así del mismo
        día.
        """
        suelto = self._crear(modulo="M1", vehiculo=None, guia="").json()
        otro = self._crear(modulo="M2", vehiculo=None, guia="").json()

        self.assertEqual(self._decidir(suelto["id"], CARGA_LIMPIA).status_code, 200)

        self.assertEqual(self._controles(otro["id"]), {})

    def test_con_guia_pero_sin_patente_si_son_el_mismo_camion(self):
        """La guía identifica la carga aunque no se haya cargado la patente."""
        primero = self._crear(modulo="M1", vehiculo=None, guia="G-4").json()
        segundo = self._crear(modulo="M2", vehiculo=None, guia="G-4").json()

        self._decidir(primero["id"], CARGA_LIMPIA)

        self.assertEqual(self._controles(segundo["id"])["delvo"], "Negativo")

    def test_la_crioscopia_no_se_comparte(self):
        """Se mide por compartimiento: copiarla daría por medido lo que no lo está."""
        primero = self._crear(modulo="M1", guia="G-5").json()
        segundo = self._crear(modulo="M2", guia="G-5").json()

        self._decidir(primero["id"], CARGA_LIMPIA)

        self.assertNotIn("crioscopia", self._controles(segundo["id"]))
