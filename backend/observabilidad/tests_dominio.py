"""
Los cálculos de la medición, sin ORM ni middleware.

Se prueban solos porque son lo que va a sostener decisiones: si el p95 está
mal calculado, la optimización se decide contra un número inventado.
"""

from django.test import TestCase

from observabilidad import dominio


def _muestra(ruta, ms, consultas=1, ms_sql=1.0, t=0.0, usuario="op"):
    return dominio.Muestra(
        ruta=ruta, metodo="GET", estado=200, ms=ms,
        consultas=consultas, ms_sql=ms_sql, t=t, usuario=usuario,
    )


class PercentilTests(TestCase):
    def test_sin_valores_no_hay_percentil(self):
        """
        `None` y no cero: cero es un percentil bajísimo, y leerlo como tal
        haría pasar por rapidísimo a un endpoint que nadie llamó.
        """
        self.assertIsNone(dominio.percentil([], 95))

    def test_con_un_valor_todos_los_percentiles_son_ese(self):
        self.assertEqual(dominio.percentil([7.0], 50), 7.0)
        self.assertEqual(dominio.percentil([7.0], 99), 7.0)

    def test_usa_rango_mas_cercano(self):
        valores = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]

        self.assertEqual(dominio.percentil(valores, 50), 5.0)
        self.assertEqual(dominio.percentil(valores, 90), 9.0)
        self.assertEqual(dominio.percentil(valores, 100), 10.0)

    def test_no_le_importa_el_orden_de_entrada(self):
        self.assertEqual(dominio.percentil([9.0, 1.0, 5.0], 50), 5.0)


class ResumirTests(TestCase):
    def test_agrupa_por_ruta_y_ordena_por_tiempo_total(self):
        """
        Por tiempo **total**, no por el más lento: un endpoint de 20 ms
        llamado 300 veces cuesta más que uno de 900 ms llamado una vez, y es
        el que hay que mirar primero.
        """
        muestras = (
            [_muestra("/api/maestros/productos/", 20.0) for _ in range(300)]
            + [_muestra("/api/calidad/expedientes/", 900.0)]
        )

        resumen = dominio.resumir(muestras)

        self.assertEqual(resumen[0].ruta, "/api/maestros/productos/")
        self.assertEqual(resumen[0].llamadas, 300)
        self.assertEqual(resumen[0].ms_total, 6000.0)

    def test_promedia_consultas_y_tiempo_de_sql(self):
        muestras = [
            _muestra("/api/produccion/lotes/", 10.0, consultas=2, ms_sql=4.0),
            _muestra("/api/produccion/lotes/", 10.0, consultas=8, ms_sql=6.0),
        ]

        resumen = dominio.resumir(muestras)

        self.assertEqual(resumen[0].consultas_media, 5.0)
        self.assertEqual(resumen[0].ms_sql_media, 5.0)


class RepeticionesTests(TestCase):
    def test_cuenta_la_misma_ruta_repetida_dentro_de_la_ventana(self):
        """
        Es el síntoma reportado: `productos/` varias veces en segundos al
        navegar entre módulos.
        """
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0),
            _muestra("/api/maestros/productos/", 5.0, t=1.0),
            _muestra("/api/maestros/productos/", 5.0, t=2.0),
        ]

        self.assertEqual(
            dominio.repeticiones(muestras, ventana_seg=5.0),
            [("/api/maestros/productos/", 3)],
        )

    def test_fuera_de_la_ventana_no_es_repeticion(self):
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0),
            _muestra("/api/maestros/productos/", 5.0, t=60.0),
        ]

        self.assertEqual(dominio.repeticiones(muestras, ventana_seg=5.0), [])

    def test_dos_usuarios_pidiendo_lo_mismo_no_es_una_repeticion(self):
        """
        Dos operadores abriendo la misma pantalla es uso normal. Lo que se
        busca es una pantalla pidiendo lo mismo dos veces.
        """
        muestras = [
            _muestra("/api/maestros/productos/", 5.0, t=0.0, usuario="ana"),
            _muestra("/api/maestros/productos/", 5.0, t=1.0, usuario="luis"),
        ]

        self.assertEqual(dominio.repeticiones(muestras, ventana_seg=5.0), [])
