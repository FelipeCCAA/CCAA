from .serializers import ValeEstandarizacionSerializer
from .tests_vale import BaseVale


class DesvioSugerenciaFIFOTests(BaseVale):
    def test_elegir_otro_silo_exige_motivo(self):
        vale = self.crear_vale(silo_sugerido_fifo=self.silo_destino)
        serializer = ValeEstandarizacionSerializer(
            vale, data={"silo_entera": self.silo_entera.id}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("motivo_desvio_fifo", serializer.errors)

    def test_desvio_con_motivo_es_valido(self):
        vale = self.crear_vale(silo_sugerido_fifo=self.silo_destino)
        serializer = ValeEstandarizacionSerializer(
            vale,
            data={
                "silo_entera": self.silo_entera.id,
                "motivo_desvio_fifo": "Prioridad operacional de la línea",
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
