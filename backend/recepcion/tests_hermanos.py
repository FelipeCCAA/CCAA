"""
Lo que este archivo fijaba —que los módulos hermanos de un camión comparten
los controles de la carga— dejó de ser un problema: un camión es **un**
registro, así que no hay hermanos que sincronizar. La crioscopía, lo único que
se mide por compartimiento, vive en `ModuloRecepcion` (ver `tests_modulos`).

Lo que sigue vigente y por eso se conserva: **no se reescribe lo ya decidido.**
El veredicto se deriva de los controles en vez de guardarse, así que tocarlos
después de liberar cambiaría el veredicto de leche que ya está en el silo.
"""

from recepcion.models import Recepcion
from recepcion.tests import BaseAPIRecepcion


CARGA_LIMPIA = {
    "delvo": "Negativo",
    "inhibidores": "Negativo",
    "temperatura": 4.0,
    "acidez": 16.0,
    "ph": 6.7,
}


class NoSeReescribeLoDecididoTests(BaseAPIRecepcion):
    def test_una_recepcion_liberada_no_admite_cambio_de_controles(self):
        recepcion = Recepcion.objects.create(
            fecha="2026-07-20",
            tipo_leche=Recepcion.TipoLeche.ENTERA,
            litros=5000,
            controles=CARGA_LIMPIA,
            estado=Recepcion.Estado.LIBERADA,
        )

        respuesta = self.cliente.patch(
            f"/api/recepcion/recepciones/{recepcion.id}/",
            {"controles": {**CARGA_LIMPIA, "delvo": "Positivo"}},
            format="json",
        )

        recepcion.refresh_from_db()
        self.assertEqual(
            recepcion.controles["delvo"],
            "Negativo",
            "los controles de una recepción liberada no se reescriben",
        )
