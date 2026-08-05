"""
Registros que no son por lote: cuándo cubren y cuándo no.

En el catálogo de planta **solo 12 de 204 documentos son por lote**. El resto
—aseos por ciclo, monitoreos por turno, programas semanales— pertenece al
equipo y a su período, y un lote los consume si su fecha cae dentro.

Lo que estas pruebas protegen es la ventana. Una cobertura de más deja liberar
un lote cuya máquina no se aseó en su semana; una de menos deja sin liberar un
lote cuya máquina sí se aseó, y empuja a registrar el aseo dos veces —que es
justo lo que este modelo evita—.
"""

from datetime import date

from django.test import SimpleTestCase

from . import dominio


class _Documento:
    def __init__(self, id=1, frecuencia="semanal"):
        self.id = id
        self.frecuencia = frecuencia


class _Registro:
    def __init__(self, documento_id=1, fecha=None, vigente_hasta=None, turno="",
                 estado="completado"):
        self.documento_id = documento_id
        self.fecha = fecha
        self.vigente_hasta = vigente_hasta
        self.turno = turno
        self.estado = estado


class _Lote:
    def __init__(self, fecha, turno=""):
        self.fecha = fecha
        self.turno = turno


class VentanaSemanalTests(SimpleTestCase):
    """Lunes 27-07-2026 a domingo 02-08-2026 es una semana ISO."""

    def _cubre(self, dia_registro, dia_lote):
        return dominio.cubre_al_lote(
            _Registro(fecha=dia_registro), _Documento(frecuencia="semanal"),
            _Lote(dia_lote),
        )

    def test_el_aseo_del_lunes_cubre_el_viernes(self):
        """
        Es la razón de todo esto: un aseo semanal se llena una vez y cubre
        todos los lotes de esa semana.
        """
        self.assertTrue(self._cubre(date(2026, 7, 27), date(2026, 7, 31)))

    def test_cubre_hasta_el_domingo(self):
        self.assertTrue(self._cubre(date(2026, 7, 27), date(2026, 8, 2)))

    def test_no_cubre_el_lunes_siguiente(self):
        """
        La semana nueva exige su propio aseo. Estirar la ventana un día
        dejaría liberar un lote cuya máquina no se aseó esa semana.
        """
        self.assertFalse(self._cubre(date(2026, 7, 27), date(2026, 8, 3)))

    def test_no_cubre_hacia_atras(self):
        self.assertFalse(self._cubre(date(2026, 8, 3), date(2026, 7, 31)))

    def test_cruza_el_cambio_de_mes(self):
        """31 de julio y 2 de agosto son la misma semana."""
        self.assertTrue(self._cubre(date(2026, 7, 31), date(2026, 8, 2)))


class VentanaDiariaTests(SimpleTestCase):

    def _cubre(self, frecuencia, dia_registro, dia_lote, turno_r="", turno_l=""):
        return dominio.cubre_al_lote(
            _Registro(fecha=dia_registro, turno=turno_r),
            _Documento(frecuencia=frecuencia),
            _Lote(dia_lote, turno_l),
        )

    def test_el_mismo_dia_cubre(self):
        for frecuencia in ("diaria", "por_ciclo", "por_turno"):
            with self.subTest(frecuencia=frecuencia):
                self.assertTrue(
                    self._cubre(frecuencia, date(2026, 7, 31), date(2026, 7, 31))
                )

    def test_otro_dia_no_cubre(self):
        self.assertFalse(self._cubre("diaria", date(2026, 7, 30), date(2026, 7, 31)))

    def test_por_turno_exige_el_mismo_turno(self):
        """Un aseo del turno A no dice nada del turno B."""
        self.assertFalse(
            self._cubre("por_turno", date(2026, 7, 31), date(2026, 7, 31), "A", "B")
        )

    def test_por_turno_con_el_mismo_turno_cubre(self):
        self.assertTrue(
            self._cubre("por_turno", date(2026, 7, 31), date(2026, 7, 31), "A", "A")
        )

    def test_si_alguno_no_declara_turno_basta_el_dia(self):
        """
        Exigirlo dejaría sin cubrir lotes que en planta sí lo están, y
        empujaría a registrar el mismo aseo otra vez.
        """
        self.assertTrue(
            self._cubre("por_turno", date(2026, 7, 31), date(2026, 7, 31), "", "B")
        )


class SegunProgramaTests(SimpleTestCase):
    """Sin período deducible, el registro tiene que declarar su vigencia."""

    def _cubre(self, hasta, dia_lote):
        return dominio.cubre_al_lote(
            _Registro(fecha=date(2026, 7, 1), vigente_hasta=hasta),
            _Documento(frecuencia="segun_programa"),
            _Lote(dia_lote),
        )

    def test_dentro_de_la_vigencia_cubre(self):
        self.assertTrue(self._cubre(date(2026, 12, 31), date(2026, 7, 31)))

    def test_pasada_la_vigencia_no_cubre(self):
        self.assertFalse(self._cubre(date(2026, 7, 15), date(2026, 7, 31)))

    def test_sin_vigencia_declarada_no_cubre_nada(self):
        """
        Es preferible pedir el dato a inventar una vigencia: una calibración
        sin fecha de vencimiento no puede dar por buena una producción de seis
        meses después.
        """
        self.assertFalse(self._cubre(None, date(2026, 7, 31)))


class SeleccionTests(SimpleTestCase):

    def _documentos(self):
        return [
            _Documento(id=1, frecuencia="por_lote"),
            _Documento(id=2, frecuencia="semanal"),
        ]

    def test_los_documentos_por_lote_no_se_cubren_por_periodo(self):
        """
        Tienen su propio formulario en el expediente. Cubrirlos aquí los daría
        por cumplidos sin que nadie los llenara.
        """
        cubiertos = dominio.documentos_cubiertos_por_periodo(
            self._documentos(),
            _Lote(date(2026, 7, 31)),
            [_Registro(documento_id=1, fecha=date(2026, 7, 27))],
        )

        self.assertEqual(cubiertos, {})

    def test_un_registro_en_borrador_no_cubre(self):
        """Trabajo a medias no es un registro."""
        cubiertos = dominio.documentos_cubiertos_por_periodo(
            self._documentos(),
            _Lote(date(2026, 7, 31)),
            [_Registro(documento_id=2, fecha=date(2026, 7, 27), estado="borrador")],
        )

        self.assertEqual(cubiertos, {})

    def test_un_registro_observado_no_cubre(self):
        """Una observación abierta es una alerta, no un cumplimiento."""
        cubiertos = dominio.documentos_cubiertos_por_periodo(
            self._documentos(),
            _Lote(date(2026, 7, 31)),
            [_Registro(documento_id=2, fecha=date(2026, 7, 27), estado="observado")],
        )

        self.assertEqual(cubiertos, {})

    def test_devuelve_cual_lo_cubre_y_no_solo_que_esta_cubierto(self):
        """
        El expediente tiene que poder decir «el aseo del 27-07»: sin eso,
        quien audita no llega al papel.
        """
        registro = _Registro(documento_id=2, fecha=date(2026, 7, 27))

        cubiertos = dominio.documentos_cubiertos_por_periodo(
            self._documentos(), _Lote(date(2026, 7, 31)), [registro]
        )

        self.assertIs(cubiertos[2], registro)


class AvanceConCoberturaTests(SimpleTestCase):

    def test_un_documento_cubierto_cuenta_como_completo(self):
        documento = _Documento(id=1, frecuencia="semanal")
        registro = _Registro(documento_id=1, fecha=date(2026, 7, 27))

        avance = dominio.avance_checklist(
            [], [documento], 1, None, {1: registro}
        )

        self.assertEqual(avance.completados, 1)
        self.assertIs(avance.detalle[0].cubierto_por, registro)

    def test_sin_cobertura_sigue_faltando(self):
        avance = dominio.avance_checklist([], [_Documento(id=1)], 1, None, {})

        self.assertEqual(avance.completados, 0)
