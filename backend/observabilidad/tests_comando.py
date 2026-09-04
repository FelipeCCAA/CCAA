"""
El comando convierte el registro en las dos respuestas que se buscan.

No se prueba el formato de la tabla —eso cambiaría con cualquier retoque de
ancho de columna— sino que los números que sostienen decisiones estén ahí: las
llamadas, el percentil y la racha de repeticiones.
"""

import json
from io import StringIO
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase


class ResumenMetricasTests(TestCase):
    def _archivo(self, filas):
        # En Windows el runner aislado puede crear una carpeta temporal global
        # sin heredar permisos de escritura. El archivo sigue siendo efímero,
        # pero vive dentro del workspace autorizado del backend.
        ruta = Path(settings.BASE_DIR) / f".metricas-test-{uuid4().hex}.jsonl"
        ruta.write_text("\n".join(json.dumps(f) for f in filas), encoding="utf-8")
        self.addCleanup(ruta.unlink, missing_ok=True)
        return str(ruta)

    def _fila(
        self, ruta, ms, t, consultas=1, usuario="op", metodo="GET", estado=200,
    ):
        return {
            "ruta": ruta, "metodo": metodo, "estado": estado, "ms": ms,
            "consultas": consultas, "ms_sql": 1.0, "t": t, "usuario": usuario,
        }

    def _correr(self, archivo, **opciones):
        salida = StringIO()
        call_command("resumen_metricas", archivo, stdout=salida, **opciones)
        return salida.getvalue()

    def test_informa_la_ruta_con_sus_llamadas_y_su_percentil(self):
        archivo = self._archivo([
            self._fila("/api/maestros/productos/", 10.0, 0.0),
            self._fila("/api/maestros/productos/", 30.0, 1.0),
            self._fila("/api/maestros/productos/", 20.0, 2.0),
        ])

        texto = self._correr(archivo)

        self.assertIn("/api/maestros/productos/", texto)
        self.assertIn("3 requests medidos", texto)
        # p50 de [10, 20, 30] por rango más cercano es 20.
        self.assertRegex(texto, r"/api/maestros/productos/\s+3\s+20")

    def test_delata_la_racha_de_repeticiones(self):
        """
        Es el síntoma reportado: `productos/` varias veces en segundos al
        navegar entre módulos.
        """
        archivo = self._archivo([
            self._fila("/api/maestros/productos/", 5.0, 0.0),
            self._fila("/api/maestros/productos/", 5.0, 1.0),
            self._fila("/api/maestros/productos/", 5.0, 2.0),
        ])

        texto = self._correr(archivo)

        self.assertRegex(texto, r"3x\s+/api/maestros/productos/")

    def test_sin_repeticiones_lo_dice(self):
        archivo = self._archivo([
            self._fila("/api/produccion/lotes/", 5.0, 0.0),
            self._fila("/api/produccion/lotes/", 5.0, 600.0),
        ])

        texto = self._correr(archivo)

        self.assertIn("ninguna", texto)

    def test_una_linea_corrupta_no_tumba_el_informe(self):
        """
        El registro se escribe en producción y puede quedar cortado a mitad
        de línea. Perder el informe entero por eso sería perder la medición.
        """
        ruta = Path(self._archivo([]))
        ruta.write_text(
            json.dumps(self._fila("/api/produccion/lotes/", 5.0, 0.0))
            + "\n{ esto no es json\n",
            encoding="utf-8",
        )

        texto = self._correr(str(ruta))

        self.assertIn("/api/produccion/lotes/", texto)
        self.assertIn("1 línea ilegible", texto)

    def test_un_registro_vacio_avisa_en_vez_de_reventar(self):
        archivo = self._archivo([])

        texto = self._correr(archivo)

        self.assertIn("no trae muestras", texto)

    def test_muestra_conflictos_409_por_endpoint(self):
        archivo = self._archivo([
            self._fila(
                "/api/procesos/ejecuciones/:id/", 5.0, 0.0,
                metodo="PATCH", estado=409,
            ),
            self._fila(
                "/api/procesos/ejecuciones/:id/", 6.0, 1.0,
                metodo="PATCH", estado=409,
            ),
        ])

        texto = self._correr(archivo)

        self.assertRegex(
            texto, r"2x\s+PATCH\s+/api/procesos/ejecuciones/:id/"
        )
