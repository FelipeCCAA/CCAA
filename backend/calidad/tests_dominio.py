"""
Pruebas de las reglas de liberación.

Portadas de `prototipo/js/modelo/pruebas.js` (bloques "Checklist de
liberación", "Formularios de calidad" y "Liberación"). Son las que, si se
rompen, dejan salir producto que no debería salir: por eso cada una nombra la
regla que protege.
"""

from datetime import date

from django.test import TestCase

from maestros.models import DocumentoLiberacion, Especificacion, Mandante, Producto
from produccion.models import Analisis, Lote
from usuarios.models import Rol

from . import dominio
from .models import RegistroCalidad


class BaseLiberacion(TestCase):
    """
    El escenario mínimo del prototipo: un polvo y una crema, con tres
    documentos de los cuales uno no aplica a la crema.
    """

    def setUp(self):
        # El catálogo del Dossier se siembra por migración, así que también
        # existe en la base de pruebas. Estas pruebas arman su propio checklist
        # y tienen que partir de cero: heredando los 19 medirían el avance
        # contra documentos que no crearon.
        DocumentoLiberacion.objects.all().delete()

        self.mandante = Mandante.objects.create(nombre="Nestlé")

        self.polvo = Producto.objects.create(
            nombre="Leche entera en polvo",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        self.crema = Producto.objects.create(
            nombre="Crema 40%",
            familia=Producto.Familia.CREMA,
            mandante=self.mandante,
        )

        self.spec = Especificacion.objects.create(
            producto=self.polvo,
            version=1,
            vigente_desde=date(2026, 1, 1),
            rangos={"mg": {"min": 26.0, "max": 30.0, "obligatorio": True}},
        )

        # d1 y d3 aplican a ambas familias; d2 solo al polvo.
        self.d1 = DocumentoLiberacion.objects.create(
            nombre="Ficha técnica", aplica_a=["polvo", "crema"], orden=1
        )
        self.d2 = DocumentoLiberacion.objects.create(
            nombre="Control Rovemas", aplica_a=["polvo"], orden=2
        )
        self.d3 = DocumentoLiberacion.objects.create(
            nombre="Liberación microbiológica", aplica_a=["polvo", "crema"], orden=3
        )

        self.lote = Lote.objects.create(
            codigo_lote="CCAA6140N",
            producto=self.polvo,
            fecha=date(2026, 7, 20),
            kg_producidos=12500,
            estado=Lote.Estado.PRODUCIDO,
        )

    # -- ayudantes ---------------------------------------------------------

    def _registro(self, documento, lote=None, estado=RegistroCalidad.Estado.COMPLETADO, **extra):
        return RegistroCalidad.objects.create(
            lote=lote or self.lote,
            documento=documento,
            estado=estado,
            valores=extra.pop("valores", {}),
            **extra,
        )

    def _analisis(self, valores, lote=None):
        return Analisis.objects.create(
            lote=lote or self.lote, fecha=date(2026, 7, 20), valores=valores
        )

    def _contexto(self, **cambios):
        """El contexto completo de `puede_liberar`, para variarlo por partes."""
        contexto = {
            "lote": self.lote,
            "producto": self.polvo,
            "documentos": list(DocumentoLiberacion.objects.all()),
            "registros": list(RegistroCalidad.objects.all()),
            "analisis": list(Analisis.objects.all()),
            "especificaciones": list(Especificacion.objects.all()),
            "rol": Rol.CALIDAD,
        }
        contexto.update(cambios)
        return contexto

    def _checklist_completo(self, lote=None):
        for documento in (self.d1, self.d2, self.d3):
            self._registro(documento, lote=lote)

    def _texto(self, bloqueos):
        return " ".join(bloqueos)


class DocumentosAplicablesTests(BaseLiberacion):
    def test_a_la_crema_no_se_le_exigen_documentos_de_las_lineas_de_polvo(self):
        documentos = list(DocumentoLiberacion.objects.all())

        de_polvo = dominio.documentos_aplicables(documentos, self.polvo)
        de_crema = dominio.documentos_aplicables(documentos, self.crema)

        self.assertEqual(len(de_polvo), 3)
        self.assertEqual(len(de_crema), 2, "Rovemas no aplica a crema")
        self.assertNotIn(self.d2, de_crema)

    def test_un_documento_inactivo_deja_de_exigirse(self):
        """Retirar un documento del checklist no debe obligar a borrar su histórico."""
        self.d2.activo = False
        self.d2.save()

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.polvo
        )

        self.assertEqual(len(aplicables), 2)

    def test_los_documentos_salen_en_el_orden_declarado(self):
        """El checklist se completa en un orden, y no es el de creación."""
        self.d3.orden = 0
        self.d3.save()

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.polvo
        )

        self.assertEqual(aplicables[0], self.d3)


class AvanceChecklistTests(BaseLiberacion):
    def test_el_avance_se_calcula_sobre_los_exigibles_no_sobre_los_registros(self):
        self._registro(self.d1)

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.polvo
        )
        avance = dominio.avance_checklist(
            list(RegistroCalidad.objects.all()), aplicables, self.lote.id
        )

        self.assertEqual(avance.completados, 1)
        self.assertEqual(avance.total, 3)
        self.assertEqual(avance.pct, 33)
        self.assertFalse(avance.completo)

    def test_un_formulario_de_un_documento_que_no_aplica_no_infla_el_avance(self):
        lote_crema = Lote.objects.create(
            codigo_lote="CR001",
            producto=self.crema,
            fecha=date(2026, 7, 20),
            kg_producidos=800,
            estado=Lote.Estado.PRODUCIDO,
        )
        self._registro(self.d1, lote=lote_crema)
        self._registro(self.d2, lote=lote_crema)

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.crema
        )
        avance = dominio.avance_checklist(
            list(RegistroCalidad.objects.all()), aplicables, lote_crema.id
        )

        self.assertEqual(avance.completados, 1, "d2 no aplica a crema y no debe contar")
        self.assertEqual(avance.total, 2)

    def test_el_formulario_de_otro_lote_no_cuenta_para_este(self):
        """
        Regresión. Sin filtrar por lote, el formulario de otro lote da por
        cumplido un documento que nadie completó para este — y como el
        checklist completo es lo que habilita la liberación, deja salir
        producto (MODELO_DATOS.md §2.6).
        """
        otro = Lote.objects.create(
            codigo_lote="CCAA6141N",
            producto=self.polvo,
            fecha=date(2026, 7, 21),
            kg_producidos=9000,
            estado=Lote.Estado.PRODUCIDO,
        )
        self._registro(self.d1)
        self._registro(self.d2, lote=otro)

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.polvo
        )
        avance = dominio.avance_checklist(
            list(RegistroCalidad.objects.all()), aplicables, self.lote.id
        )

        self.assertEqual(
            avance.completados, 1, "d2 lo completó otro lote: no cuenta para este"
        )

    def test_un_formulario_en_borrador_no_cuenta_como_cumplido(self):
        self._registro(self.d1, estado=RegistroCalidad.Estado.BORRADOR)

        aplicables = dominio.documentos_aplicables(
            list(DocumentoLiberacion.objects.all()), self.polvo
        )
        avance = dominio.avance_checklist(
            list(RegistroCalidad.objects.all()), aplicables, self.lote.id
        )

        self.assertEqual(avance.completados, 0)

    def test_sin_documentos_exigibles_el_checklist_no_esta_completo(self):
        """Un checklist vacío no es un checklist cumplido."""
        avance = dominio.avance_checklist([], [], self.lote.id)

        self.assertFalse(avance.completo)
        self.assertEqual(avance.pct, 0)


class FormularioDigitalTests(BaseLiberacion):
    """Los formularios son datos, no código (MODELO_DATOS.md §2.6)."""

    def setUp(self):
        super().setUp()
        self.doc_fq = DocumentoLiberacion.objects.create(
            nombre="Formulario fisicoquímicos",
            aplica_a=["polvo"],
            orden=4,
            plantilla=[
                {
                    "clave": "lote",
                    "etiqueta": "Lote",
                    "tipo": "texto",
                    "req": True,
                    "origen": "lote.codigo_lote",
                },
                {
                    "clave": "mg",
                    "etiqueta": "Materia grasa",
                    "tipo": "decimal",
                    "req": True,
                    "parametro": "mg",
                },
                {"clave": "operador", "etiqueta": "Operador", "tipo": "texto", "req": True},
            ],
        )

    def test_un_formulario_al_que_le_faltan_campos_obligatorios_no_esta_completo(self):
        registro = self._registro(
            self.doc_fq, valores={"lote": "CCAA6140N", "mg": 28}
        )

        self.assertFalse(
            dominio.registro_completo(registro, self.doc_fq), "falta el operador"
        )

        validacion = dominio.validar_registro(registro, self.doc_fq)

        self.assertFalse(validacion.permitido)
        self.assertIn("Operador", self._texto(validacion.bloqueos))

    def test_con_todos_los_campos_obligatorios_el_formulario_queda_completo(self):
        registro = self._registro(
            self.doc_fq,
            valores={"lote": "CCAA6140N", "mg": 28, "operador": "J. Andrade"},
        )

        self.assertTrue(dominio.registro_completo(registro, self.doc_fq))
        self.assertTrue(dominio.validar_registro(registro, self.doc_fq).permitido)

    def test_marcar_completado_no_basta_si_la_plantilla_pide_datos(self):
        """La debilidad del checklist en papel: el visto bueno sin el dato detrás."""
        registro = self._registro(self.doc_fq, valores={})

        self.assertEqual(registro.estado, RegistroCalidad.Estado.COMPLETADO)
        self.assertFalse(dominio.registro_completo(registro, self.doc_fq))

    def test_los_datos_que_el_sistema_ya_conoce_se_prellenan_solos(self):
        valores = dominio.prellenar(self.doc_fq, {"lote": self.lote})

        self.assertEqual(
            valores["lote"], "CCAA6140N", "no se vuelve a teclear lo que ya está en el lote"
        )
        self.assertNotIn("mg", valores, "solo los campos con origen declarado")

    def test_el_sistema_avisa_si_el_formulario_discrepa_del_analisis(self):
        self._analisis({"mg": 28})
        registro = self._registro(
            self.doc_fq, valores={"lote": "x", "mg": 22, "operador": "x"}
        )
        resultado = self._resultado_calidad()

        discrepancias = dominio.cotejar_con_analisis(
            registro, self.doc_fq, resultado, list(Analisis.objects.all())
        )

        self.assertTrue(
            any(d.tipo == "discrepa_del_analisis" for d in discrepancias),
            "un papel que no cuadra con el laboratorio es justo lo que hay que detectar",
        )
        self.assertIn("el análisis del lote", self._texto(d.mensaje for d in discrepancias))

    def test_si_el_formulario_coincide_con_el_analisis_no_hay_discrepancia(self):
        self._analisis({"mg": 28})
        registro = self._registro(
            self.doc_fq, valores={"lote": "x", "mg": 28, "operador": "x"}
        )

        discrepancias = dominio.cotejar_con_analisis(
            registro, self.doc_fq, self._resultado_calidad(), list(Analisis.objects.all())
        )

        self.assertEqual([d for d in discrepancias if d.tipo == "discrepa_del_analisis"], [])

    def test_el_sistema_avisa_si_lo_declarado_se_sale_de_la_especificacion(self):
        self._analisis({"mg": 28})
        registro = self._registro(
            self.doc_fq, valores={"lote": "x", "mg": 40, "operador": "x"}
        )

        discrepancias = dominio.cotejar_con_analisis(
            registro, self.doc_fq, self._resultado_calidad(), list(Analisis.objects.all())
        )

        self.assertTrue(any(d.tipo == "fuera_de_especificacion" for d in discrepancias))

    def test_el_cotejo_ignora_los_analisis_de_otro_lote(self):
        """Cotejar contra la muestra de otro lote inventa o esconde discrepancias."""
        otro = Lote.objects.create(
            codigo_lote="CCAA6141N",
            producto=self.polvo,
            fecha=date(2026, 7, 21),
            kg_producidos=9000,
            estado=Lote.Estado.PRODUCIDO,
        )
        self._analisis({"mg": 28})
        self._analisis({"mg": 15}, lote=otro)

        registro = self._registro(
            self.doc_fq, valores={"lote": "x", "mg": 28, "operador": "x"}
        )

        discrepancias = dominio.cotejar_con_analisis(
            registro, self.doc_fq, self._resultado_calidad(), list(Analisis.objects.all())
        )

        self.assertEqual([d for d in discrepancias if d.tipo == "discrepa_del_analisis"], [])

    def _resultado_calidad(self):
        from produccion import dominio as calidad_producto

        return calidad_producto.resultado_calidad_lote(
            self.lote, list(Analisis.objects.all()), list(Especificacion.objects.all())
        )


class LiberacionTests(BaseLiberacion):
    """La regla central: un despacho exige un lote liberado."""

    def test_lote_conforme_checklist_completo_y_rol_calidad_se_libera(self):
        self._checklist_completo()
        self._analisis({"mg": 28})

        decision = dominio.puede_liberar(**self._contexto())

        self.assertTrue(decision.permitido, self._texto(decision.bloqueos))
        self.assertFalse(decision.via_concesion)

    def test_producto_envasado_no_se_libera_comercialmente_antes_de_terminar_envase(self):
        self._checklist_completo()
        self._analisis({"mg": 28})
        contexto = self._contexto()
        contexto["envasado_completo"] = False

        decision = dominio.puede_liberar(**contexto)

        self.assertFalse(decision.permitido)
        self.assertIn("terminar Envasado", self._texto(decision.bloqueos))

    def test_lote_no_conforme_con_checklist_completo_solo_por_concesion(self):
        self._checklist_completo()
        self._analisis({"mg": 35})

        decision = dominio.puede_liberar(**self._contexto())

        self.assertFalse(
            decision.permitido, "Un lote no conforme NUNCA se libera por la vía normal"
        )
        self.assertTrue(decision.via_concesion)
        self.assertIn("no conforme", self._texto(decision.bloqueos))

    def test_checklist_incompleto_bloquea_incluso_con_calidad_conforme(self):
        self._registro(self.d1)
        self._analisis({"mg": 28})

        decision = dominio.puede_liberar(**self._contexto())

        self.assertFalse(decision.permitido)
        self.assertFalse(decision.via_concesion, "Sin documentos no hay concesión posible")
        self.assertIn("Faltan 2 de 3 formularios", self._texto(decision.bloqueos))

    def test_un_formulario_observado_bloquea_aunque_el_checklist_este_completo(self):
        self._checklist_completo()
        self._analisis({"mg": 28})

        observado = RegistroCalidad.objects.get(documento=self.d1)
        observado.estado = RegistroCalidad.Estado.OBSERVADO
        observado.observacion = "El peso declarado no cuadra con la balanza."
        observado.save()

        decision = dominio.puede_liberar(**self._contexto(registros=list(RegistroCalidad.objects.all())))

        self.assertFalse(decision.permitido)
        self.assertIn("observación sin resolver", self._texto(decision.bloqueos))

    def test_sin_especificacion_no_hay_liberacion_ni_siquiera_por_concesion(self):
        """No se concede una excepción sobre algo que nunca se midió."""
        sin_spec = Producto.objects.create(
            nombre="Producto sin especificación",
            familia=Producto.Familia.POLVO,
            mandante=self.mandante,
        )
        lote = Lote.objects.create(
            codigo_lote="SS001",
            producto=sin_spec,
            fecha=date(2026, 7, 20),
            kg_producidos=100,
            estado=Lote.Estado.PRODUCIDO,
        )
        for documento in (self.d1, self.d2, self.d3):
            self._registro(documento, lote=lote)

        decision = dominio.puede_liberar(
            **self._contexto(
                lote=lote,
                producto=sin_spec,
                registros=list(RegistroCalidad.objects.all()),
            )
        )

        self.assertFalse(decision.permitido)
        self.assertFalse(decision.via_concesion)
        self.assertIn("no tiene especificación", self._texto(decision.bloqueos))

    def test_sin_analisis_no_hay_liberacion_ni_siquiera_por_concesion(self):
        self._checklist_completo()

        decision = dominio.puede_liberar(**self._contexto())

        self.assertFalse(decision.permitido)
        self.assertFalse(decision.via_concesion)
        self.assertIn("no tiene análisis", self._texto(decision.bloqueos))

    def test_un_usuario_de_produccion_no_puede_autorizar_liberaciones(self):
        self._checklist_completo()
        self._analisis({"mg": 28})

        decision = dominio.puede_liberar(**self._contexto(rol=Rol.PRODUCCION))

        self.assertFalse(decision.permitido)
        self.assertIn("no puede autorizar", self._texto(decision.bloqueos))

    def test_un_lote_todavia_en_proceso_no_se_libera(self):
        self._checklist_completo()
        self._analisis({"mg": 28})
        self.lote.estado = Lote.Estado.EN_PROCESO
        self.lote.save()

        decision = dominio.puede_liberar(**self._contexto())

        self.assertFalse(decision.permitido)
        self.assertIn("en proceso", self._texto(decision.bloqueos))

    def test_un_lote_anulado_no_se_libera(self):
        self._checklist_completo()
        self._analisis({"mg": 28})
        self.lote.estado = Lote.Estado.ANULADO
        self.lote.save()

        decision = dominio.puede_liberar(**self._contexto())

        self.assertFalse(decision.permitido)
        self.assertIn("anulado", self._texto(decision.bloqueos))

    def test_sin_documentos_configurados_para_la_familia_no_se_libera(self):
        """Un checklist vacío no es un checklist cumplido: es uno sin configurar."""
        DocumentoLiberacion.objects.all().delete()
        self._analisis({"mg": 28})

        decision = dominio.puede_liberar(**self._contexto(documentos=[], registros=[]))

        self.assertFalse(decision.permitido)
        self.assertIn("No hay documentos configurados", self._texto(decision.bloqueos))


class ConcesionTests(BaseLiberacion):
    def setUp(self):
        super().setUp()
        self._checklist_completo()
        self._analisis({"mg": 35})  # fuera de rango: solo puede salir por concesión

    def test_la_concesion_exige_un_motivo_escrito(self):
        corto = dominio.validar_concesion(
            "ok", autorizador_identificado=True, **self._contexto()
        )
        largo = dominio.validar_concesion(
            "Aceptado por el mandante según correo del 21-05.",
            autorizador_identificado=True,
            **self._contexto(),
        )

        self.assertFalse(corto.permitido, "Un motivo de dos letras no es un motivo")
        self.assertTrue(largo.permitido, self._texto(largo.bloqueos))

    def test_la_concesion_exige_un_usuario_identificado(self):
        resultado = dominio.validar_concesion(
            "Aceptado por el mandante según correo del 21-05.",
            autorizador_identificado=False,
            **self._contexto(),
        )

        self.assertFalse(resultado.permitido)
        self.assertIn("firmada", self._texto(resultado.bloqueos))

    def test_la_concesion_no_salta_el_checklist_incompleto(self):
        """Se concede la no conformidad, no el expediente sin terminar."""
        RegistroCalidad.objects.filter(documento=self.d2).delete()

        resultado = dominio.validar_concesion(
            "Aceptado por el mandante según correo del 21-05.",
            autorizador_identificado=True,
            **self._contexto(registros=list(RegistroCalidad.objects.all())),
        )

        self.assertFalse(resultado.permitido)
        self.assertIn("formularios por completar", self._texto(resultado.bloqueos))


class RolesDelDominioTests(TestCase):
    """
    El dominio no importa Django, así que duplica los nombres de los roles.

    Esta prueba vigila esa duplicación: si alguien renombra un rol en
    `usuarios.models.Rol`, aquí se entera, en vez de descubrirlo cuando Calidad
    no pueda firmar una liberación.
    """

    def test_los_roles_autorizadores_del_dominio_existen_en_usuarios(self):
        self.assertEqual(
            set(dominio.ROLES_AUTORIZADORES), {Rol.CALIDAD.value, Rol.ADMIN.value}
        )

    def test_los_estados_de_registro_del_dominio_existen_en_el_modelo(self):
        self.assertEqual(
            {dominio.BORRADOR, dominio.COMPLETADO, dominio.OBSERVADO},
            set(RegistroCalidad.Estado.values),
        )
