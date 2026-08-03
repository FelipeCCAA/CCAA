"""
Documentos del Dossier que cumple el propio dato del sistema.

Once de los diecinueve registros son datos que la aplicación ya captura. Pedir
además una casilla es doble digitación, y algo peor: la casilla puede decir
«cumplido» sobre un PCC 1 incumplido.

Lo que estas pruebas protegen es el lado peligroso. Un documento cumplido **de
más** deja salir producto, así que la coincidencia tiene que ser exacta: el
registro es de ESE lote, y de ESE equipo o tipo.

Desde que `equipo` es una referencia al maestro y no texto libre, el criterio
compara **códigos**. Eso es lo que permitió atar los dos PPRO de máquina
(`Sec.FORM.022` y `Sec.FORM.005`), que antes no se podían distinguir del
checklist de cuerpos extraños de la misma torre.
"""

from django.test import SimpleTestCase, TestCase

from . import dominio


class _Documento:
    def __init__(self, id, evidencia=None):
        self.id = id
        self.evidencia = evidencia or {}


class _Equipo:
    """
    Doble de `maestros.Equipo`.

    El nombre es distinto del código a propósito: así una prueba falla si el
    dominio compara por `str(equipo)` —que devuelve el nombre— en vez de por
    el código, que es el identificador estable.
    """

    def __init__(self, codigo, nombre=None):
        self.codigo = codigo
        self.nombre = nombre or f"Máquina {codigo.upper()}"

    def __str__(self):
        return self.nombre


class _Registro:
    """Sirve de control, monitoreo, análisis o movimiento según qué se le pida."""

    def __init__(self, lote_id=1, **campos):
        self.lote_id = lote_id
        for clave, valor in campos.items():
            setattr(self, clave, valor)


class CoincidenciaTests(SimpleTestCase):

    def test_un_documento_sin_evidencia_sigue_siendo_manual(self):
        cumplidos = dominio.documentos_con_evidencia(
            [_Documento(1)], 1, analisis=[_Registro()]
        )

        self.assertEqual(cumplidos, set())

    def test_una_fuente_desconocida_no_cumple_nada(self):
        """No se inventa una equivalencia con lo que haya a mano."""
        documento = _Documento(1, {"fuente": "inventada"})

        self.assertEqual(
            dominio.documentos_con_evidencia([documento], 1, analisis=[_Registro()]),
            set(),
        )

    def test_el_analisis_del_lote_cumple_su_documento(self):
        documento = _Documento(1, {"fuente": "analisis"})

        self.assertEqual(
            dominio.documentos_con_evidencia([documento], 1, analisis=[_Registro()]),
            {1},
        )

    def test_el_registro_de_otro_lote_no_cumple(self):
        """
        Es el mismo error que ya costó una prueba de regresión en el
        checklist: un registro ajeno da por cumplido un documento que nadie
        completó para este lote, y el checklist completo deja salir producto.
        """
        documento = _Documento(1, {"fuente": "analisis"})

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, analisis=[_Registro(lote_id=99)]
            ),
            set(),
        )

    def test_el_tipo_tiene_que_coincidir(self):
        documento = _Documento(1, {"fuente": "monitoreo_ppro", "tipo": "detector_metales"})

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, monitoreos=[_Registro(tipo="cuerpos_extranos")]
            ),
            set(),
        )

    def test_un_monitoreo_del_tipo_correcto_cumple(self):
        documento = _Documento(1, {"fuente": "monitoreo_ppro", "tipo": "detector_metales"})

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, monitoreos=[_Registro(tipo="detector_metales")]
            ),
            {1},
        )

    def test_un_solo_monitoreo_no_cumple_dos_documentos_distintos(self):
        """
        La razón de exigir el tipo. Los tres checklists de cuerpos extraños
        —evaporadores, E1-E2 y Rovema— se verían cumplidos con un solo
        monitoreo, y dos de los tres controles no se habrían hecho.
        """
        metales = _Documento(1, {"fuente": "monitoreo_ppro", "tipo": "detector_metales"})
        extranos = _Documento(2, {"fuente": "monitoreo_ppro", "tipo": "cuerpos_extranos"})

        cumplidos = dominio.documentos_con_evidencia(
            [metales, extranos], 1, monitoreos=[_Registro(tipo="detector_metales")]
        )

        self.assertEqual(cumplidos, {1})


class CoincidenciaPorListaTests(SimpleTestCase):
    """
    `campo_en` acepta varios valores: el PCC 1 se corre en cualquiera de los
    tres evaporadores, y exigir uno concreto dejaría el documento sin cumplir
    según en cuál se corrió.
    """

    def _pcc1(self):
        return _Documento(
            1,
            {
                "fuente": "control_proceso",
                "equipo_en": ["veb", "scheffers2", "scheffers3"],
            },
        )

    def test_cualquiera_de_la_lista_cumple(self):
        for codigo in ("veb", "scheffers2", "scheffers3"):
            with self.subTest(equipo=codigo):
                self.assertEqual(
                    dominio.documentos_con_evidencia(
                        [self._pcc1()],
                        1,
                        controles=[_Registro(equipo=_Equipo(codigo))],
                    ),
                    {1},
                )

    def test_un_equipo_fuera_de_la_lista_no_cumple(self):
        """
        La hoja de pulverización es de las torres. Un control del evaporador
        no la cumple aunque los dos sean controles de proceso.
        """
        self.assertEqual(
            dominio.documentos_con_evidencia(
                [self._pcc1()], 1, controles=[_Registro(equipo=_Equipo("e1"))]
            ),
            set(),
        )

    def test_el_equipo_se_compara_por_su_codigo_y_no_por_su_nombre(self):
        """
        El nombre se edita desde Maestros; el código no. Si la comparación
        cayera en el nombre —que es lo que da `str(equipo)`—, corregirle una
        tilde a «Torre de secado Egron 1» dejaría el documento sin cumplirse
        y nadie lo notaría hasta que un lote no se pudiera liberar.
        """
        documento = _Documento(1, {"fuente": "control_proceso", "equipo_en": ["e1"]})
        equipo = _Equipo("e1", nombre="Torre de secado Egron 1")

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, controles=[_Registro(equipo=equipo)]
            ),
            {1},
        )

    def test_se_compara_sin_distinguir_mayusculas_ni_espacios(self):
        """Los criterios se escriben a mano: «E1 » no debería fallar."""
        documento = _Documento(1, {"fuente": "control_proceso", "equipo_en": ["E1 "]})

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, controles=[_Registro(equipo=_Equipo("e1"))]
            ),
            {1},
        )

    def test_dos_criterios_se_exigen_juntos(self):
        """
        El PPRO de las Rovemas declara equipo **y** tipo. Sin el tipo, el
        checklist de cuerpos extraños de la misma máquina —que es otro
        documento— lo daría por cumplido, y el PPRO vigila presión de aire:
        algo que nadie habría mirado.
        """
        documento = _Documento(
            1,
            {
                "fuente": "monitoreo_ppro",
                "equipo_en": ["rovema3", "rovema4"],
                "tipo_en": ["aire_transporte", "aire_secundario", "roce_valvulas"],
            },
        )
        cuerpos_extranos = _Registro(
            equipo=_Equipo("rovema3"), tipo="cuerpos_extranos"
        )

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento], 1, monitoreos=[cuerpos_extranos]
            ),
            set(),
        )

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [documento],
                1,
                monitoreos=[_Registro(equipo=_Equipo("rovema3"), tipo="aire_transporte")],
            ),
            {1},
        )


class AsignacionDeLecheTests(SimpleTestCase):
    """La trazabilidad de la leche son las salidas de silo con origen el lote."""

    def _documento(self):
        return _Documento(1, {"fuente": "asignacion_leche"})

    def test_una_salida_del_lote_cumple(self):
        movimiento = _Registro(tipo="salida", origen_tipo="lote", origen_id=1)

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [self._documento()], 1, movimientos=[movimiento]
            ),
            {1},
        )

    def test_un_ingreso_no_cumple(self):
        """
        Un ingreso es leche que llegó al silo, no leche que este lote tomó.
        Confundirlos daría por trazado un lote sin asignación.
        """
        movimiento = _Registro(tipo="ingreso", origen_tipo="recepcion", origen_id=1)

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [self._documento()], 1, movimientos=[movimiento]
            ),
            set(),
        )

    def test_una_salida_de_otro_lote_no_cumple(self):
        movimiento = _Registro(tipo="salida", origen_tipo="lote", origen_id=99)

        self.assertEqual(
            dominio.documentos_con_evidencia(
                [self._documento()], 1, movimientos=[movimiento]
            ),
            set(),
        )


class AvanceConEvidenciaTests(SimpleTestCase):

    def test_el_documento_cumplido_por_dato_cuenta_como_completo(self):
        documento = _Documento(1, {"fuente": "analisis"})

        avance = dominio.avance_checklist([], [documento], 1, {1})

        self.assertEqual(avance.completados, 1)
        self.assertTrue(avance.completo)

    def test_se_distingue_de_uno_marcado_a_mano(self):
        """
        El expediente tiene que poder decir de dónde viene el cumplimiento:
        «hay control de proceso» no es lo mismo que «alguien lo marcó».
        """
        documento = _Documento(1, {"fuente": "analisis"})

        estado = dominio.avance_checklist([], [documento], 1, {1}).detalle[0]

        self.assertTrue(estado.cumplido_por_dato)
        self.assertIsNone(estado.registro)

    def test_sin_evidencia_el_documento_sigue_faltando(self):
        avance = dominio.avance_checklist([], [_Documento(1)], 1, set())

        self.assertEqual(avance.completados, 0)


class SiembraDelDossierTests(TestCase):
    """
    Qué documentos quedaron atados, y por qué solo esos.

    Se prueba contra la siembra real porque el riesgo está justamente ahí: un
    criterio de más da por cumplido un documento que nadie hizo.
    """

    def test_los_siete_inequivocos_tienen_evidencia(self):
        from maestros.models import DocumentoLiberacion

        con_evidencia = {
            d.codigo
            for d in DocumentoLiberacion.objects.exclude(evidencia={})
        }

        self.assertEqual(
            con_evidencia,
            {
                "CCAA.REC.FORM.005",   # trazabilidad de leche
                "CCAA.Cond.FORM.010",  # PCC 1
                "CCAA.Sec.FORM.025",   # hoja de pulverización
                "CCAA.Sec.FORM.001",   # análisis fisicoquímico
                "CCAA.ENV.FORM.001",   # detector de metales
                "CCAA.Sec.FORM.022",   # PPRO 3 · torres E1-E2
                "CCAA.Sec.FORM.005",   # PPRO 4 · Rovemas 3 y 4
            },
        )

    def test_los_ppro_de_maquina_exigen_equipo_y_tipo(self):
        """
        Solo la máquina no basta: el checklist de cuerpos extraños de la misma
        torre es otro documento, y sin el tipo lo daría por cumplido. El PPRO
        vigila presión de aire y roce de válvulas — cosas que nadie habría
        mirado.
        """
        from maestros.models import DocumentoLiberacion

        for codigo in ("CCAA.Sec.FORM.022", "CCAA.Sec.FORM.005"):
            with self.subTest(codigo=codigo):
                criterio = DocumentoLiberacion.objects.get(codigo=codigo).evidencia

                self.assertEqual(criterio["fuente"], dominio.FUENTE_MONITOREO_PPRO)
                self.assertTrue(criterio["equipo_en"])
                self.assertNotIn("cuerpos_extranos", criterio["tipo_en"])
                self.assertNotIn("detector_metales", criterio["tipo_en"])

    def test_los_criterios_nombran_equipos_que_existen_en_el_maestro(self):
        """
        Un código mal escrito no falla: simplemente no coincide nunca, y el
        documento queda pidiendo una casilla que ya nadie va a marcar porque
        el dato sí se registró.
        """
        from maestros.models import DocumentoLiberacion, Equipo

        codigos = set(Equipo.objects.values_list("codigo", flat=True))

        for documento in DocumentoLiberacion.objects.exclude(evidencia={}):
            for esperado in documento.evidencia.get("equipo_en", []):
                with self.subTest(codigo=documento.codigo, equipo=esperado):
                    self.assertIn(esperado, codigos)

    def test_los_checklists_de_cuerpos_extranos_siguen_manuales(self):
        """
        Son tres —evaporadores, E1-E2 y Rovema— y ninguno se cumple con un
        dato: dos son formularios de plantilla que se llenan por ciclo o por
        turno, y el de E1-E2 todavía no tiene su formato cargado. Atarlos a un
        monitoreo daría por revisadas piezas que nadie miró.
        """
        from maestros.models import DocumentoLiberacion

        for codigo in ("CCAA.Cond.FORM.005", "CCAA.Sec.FORM.012", "CCAA.Sec.FORM.007"):
            with self.subTest(codigo=codigo):
                documento = DocumentoLiberacion.objects.get(codigo=codigo)
                self.assertEqual(documento.evidencia, {})

    def test_ningun_criterio_apunta_a_una_fuente_inexistente(self):
        from maestros.models import DocumentoLiberacion

        conocidas = {
            dominio.FUENTE_CONTROL_PROCESO,
            dominio.FUENTE_MONITOREO_PPRO,
            dominio.FUENTE_ANALISIS,
            dominio.FUENTE_ASIGNACION_LECHE,
        }

        for documento in DocumentoLiberacion.objects.exclude(evidencia={}):
            with self.subTest(codigo=documento.codigo):
                self.assertIn(documento.evidencia.get("fuente"), conocidas)
