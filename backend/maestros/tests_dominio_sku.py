"""
Pruebas del codificador de SKU de producto.

La prueba que manda es `PRODUCTOS_DEL_ARCHIVO`: los 24 productos reales de
`Recetas_Cod_Producto.xlsx` con sus atributos y el SKU que el archivo trae.
Recomponer los 24 desde sus atributos fija el orden de los segmentos, que fue
lo difícil de este código — las columnas de la planilla están desalineadas
respecto de los SKU que ella misma contiene, así que el orden se dedujo de los
datos y no de los encabezados. Si alguien reordena `SEGMENTOS`, esto falla.

`SimpleTestCase`: son funciones puras y no tocan la base.
"""

from django.test import SimpleTestCase

from .dominio import (
    SkuInvalido,
    describir_sku,
    generar_sku,
    peso_del_formato,
    sku_valido,
)


# (nombre, naturaleza, cliente, categoria, tipo, formato, sku esperado)
# Todos son mercado local: en el archivo no hay ninguno de exportación.
PRODUCTOS_DEL_ARCHIVO = [
    ("Precondensado Entero NE Granel",
     "servicio_terceros", "nestle", "precondensado", "entera", "granel", "010103010101"),
    ("Leche Entera Estándar 28% NE 25kg",
     "servicio_terceros", "nestle", "crema", "entera", "saco_25kg", "010104010201"),
    ("Leche Entera Instantánea 27% CN 25kg",
     "servicio_terceros", "colun", "lp_instantanea", "entera", "saco_25kg", "010210010201"),
    ("Precondensado SemiDescremado Rc0.201 Granel",
     "producto_propio", "no_definido", "precondensado", "semidescremada", "granel", "020003020101"),
    ("Crema fresca 42% Granel NE",
     "servicio_terceros", "nestle", "crema", "entera", "granel", "010104010101"),
    ("Crema fresca 42% Granel CA",
     "producto_propio", "no_definido", "crema", "entera", "granel", "020004010101"),
    ("Mantequilla S-sal 20kg",
     "producto_propio", "no_definido", "mantequilla", "sin_sal", "caja_20kg", "020005050301"),
    ("Leche Entera Estándar 27% SP 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg", "010302010201"),
    ("Leche Entera c/LdS 27% SP 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg", "010302010201"),
    ("Leche Descremada MH SP 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "descremada", "saco_25kg", "010302030201"),
    ("Leche Descremada c/LdS MH SP 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "descremada", "saco_25kg", "010302030201"),
    ("Mantequilla C-sal 20kg",
     "producto_propio", "no_definido", "mantequilla", "con_sal", "caja_20kg", "020005040301"),
    ("Suero WPC CN 25kg",
     "servicio_terceros", "colun", "suero", "descremada", "saco_25kg", "010208030201"),
    ("PROTOMALT NE 25kg",
     "servicio_terceros", "nestle", "extracto_malta", "entera", "saco_25kg", "010109010201"),
    ("Leche Entera en Polvo Regular 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg", "010302010201"),
    ("Leche Entera en Polvo Instantánea 25kg",
     "servicio_terceros", "soprole", "lp_instantanea", "entera", "saco_25kg", "010310010201"),
    ("Leche en Polvo Descremada Regular 25kg",
     "servicio_terceros", "soprole", "leche_polvo", "descremada", "saco_25kg", "010302030201"),
    ("Leche en Polvo Descremada Instantánea 25kg",
     "servicio_terceros", "soprole", "lp_instantanea", "descremada", "saco_25kg", "010310030201"),
    ("Rework",
     "producto_propio", "no_definido", "materiales_diversos", "no_definido", "saco_25kg", "020006070201"),
    ("P. Semidescremado ST 45% CCAA",
     "producto_propio", "no_definido", "precondensado", "semidescremada", "granel", "020003020101"),
    ("P. Semidescremado ST 45%",
     "servicio_terceros", "nestle", "precondensado", "semidescremada", "granel", "010103020101"),
    ("Leche Descremada en Polvo c/Lec",
     "servicio_terceros", "soprole", "lp_con_lecitina", "descremada", "saco_25kg", "010311030201"),
    ("Leche estandarizada",
     "producto_propio", "no_definido", "leche_fluida", "estandarizada", "granel", "020012080101"),
]


class GenerarSkuTests(SimpleTestCase):

    def test_reproduce_los_sku_reales_del_archivo(self):
        """
        Fija el orden de los segmentos contra los datos, no contra los
        encabezados de la planilla —que están desalineados—.
        """
        for nombre, nat, cli, cat, tipo, formato, esperado in PRODUCTOS_DEL_ARCHIVO:
            with self.subTest(producto=nombre):
                self.assertEqual(
                    generar_sku(nat, cli, cat, tipo, formato), esperado
                )

    def test_el_mercado_local_es_el_valor_por_defecto(self):
        """En el archivo no hay ningún producto de exportación."""
        self.assertEqual(
            generar_sku("servicio_terceros", "nestle", "precondensado", "entera", "granel"),
            generar_sku("servicio_terceros", "nestle", "precondensado", "entera", "granel", "local"),
        )

    def test_la_exportacion_cambia_el_ultimo_segmento(self):
        self.assertTrue(
            generar_sku(
                "servicio_terceros", "nestle", "precondensado", "entera", "granel",
                "exportacion",
            ).endswith("02")
        )

    def test_un_producto_propio_no_lleva_cliente(self):
        """
        El segmento de cliente dice de quién es el producto. Un producto
        propio con cliente describe algo que no existe.
        """
        with self.assertRaises(SkuInvalido):
            generar_sku("producto_propio", "nestle", "crema", "entera", "granel")

    def test_un_servicio_a_terceros_exige_cliente(self):
        with self.assertRaises(SkuInvalido):
            generar_sku("servicio_terceros", "no_definido", "crema", "entera", "granel")

    def test_un_valor_fuera_de_catalogo_falla_en_vez_de_improvisar(self):
        """
        Un SKU con un segmento inventado se ve igual de válido que uno
        correcto, y termina impreso en un saco.
        """
        with self.assertRaises(SkuInvalido) as caso:
            generar_sku("servicio_terceros", "nestle", "queso", "entera", "granel")

        self.assertIn("categoria", str(caso.exception))

    def test_el_error_dice_que_valores_se_admiten(self):
        with self.assertRaises(SkuInvalido) as caso:
            generar_sku("servicio_terceros", "nestle", "crema", "entera", "bidon")

        self.assertIn("granel", str(caso.exception))

    def test_una_naturaleza_desconocida_falla(self):
        with self.assertRaises(SkuInvalido):
            generar_sku("maquila", "nestle", "crema", "entera", "granel")

    def test_la_variante_agrega_dos_digitos(self):
        self.assertEqual(
            generar_sku(
                "servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg",
                variante=1,
            ),
            "01030201020101",
        )

    def test_la_variante_desempata_a_dos_productos_iguales(self):
        """
        Es para lo que existe: hoy tres productos comparten 010302010201
        (SKU_PRODUCTOS.md §4.1).
        """
        base = ("servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg")

        self.assertNotEqual(
            generar_sku(*base, variante=1), generar_sku(*base, variante=2)
        )

    def test_una_variante_que_no_cabe_en_dos_digitos_falla(self):
        with self.assertRaises(SkuInvalido):
            generar_sku(
                "servicio_terceros", "soprole", "leche_polvo", "entera", "saco_25kg",
                variante=100,
            )

    def test_sin_variante_el_sku_queda_en_doce_digitos(self):
        """Mientras negocio no adopte el correlativo, se compone como el archivo."""
        self.assertEqual(
            len(generar_sku("producto_propio", "no_definido", "crema", "entera", "granel")),
            12,
        )


class SkuValidoTests(SimpleTestCase):

    def test_acepta_los_sku_del_archivo(self):
        for nombre, *_, sku in PRODUCTOS_DEL_ARCHIVO:
            with self.subTest(producto=nombre):
                self.assertTrue(sku_valido(sku))

    def test_rechaza_lo_que_no_tiene_la_forma(self):
        for malo in ["", None, "0101", "01010301010", "0101030101011", "ABC103010101"]:
            with self.subTest(sku=malo):
                self.assertFalse(sku_valido(malo))

    def test_rechaza_un_segmento_fuera_de_catalogo(self):
        # Categoría 99 no existe.
        self.assertFalse(sku_valido("010199010101"))

    def test_rechaza_la_categoria_01_que_nadie_uso(self):
        """
        Se dejó sin asignar en vez de reciclarla: ocuparla ahora chocaría con
        lo que signifique en los códigos que ya están impresos.
        """
        self.assertFalse(sku_valido("010101010101"))

    def test_rechaza_lo_que_el_generador_se_negaria_a_componer(self):
        """
        Producto propio (02) con cliente Nestlé (01). Sin esta comprobación el
        validador aprobaría algo que el generador considera imposible, y las
        dos mitades del codificador dirían cosas distintas.
        """
        self.assertFalse(sku_valido("020103010101"))

    def test_acepta_los_catorce_digitos_de_la_variante(self):
        self.assertTrue(sku_valido("01030201020101"))


class DescribirSkuTests(SimpleTestCase):

    def test_traduce_los_seis_segmentos(self):
        self.assertEqual(
            describir_sku("010103010101"),
            {
                "naturaleza": "servicio_terceros",
                "cliente": "nestle",
                "categoria": "precondensado",
                "tipo": "entera",
                "formato": "granel",
                "mercado": "local",
            },
        )

    def test_incluye_la_variante_cuando_la_hay(self):
        self.assertEqual(describir_sku("01030201020107")["variante"], "07")

    def test_un_sku_invalido_no_se_describe_a_medias(self):
        """Media descripción se leería como una lectura completa."""
        self.assertIsNone(describir_sku("010199010101"))
        self.assertIsNone(describir_sku(None))

    def test_ida_y_vuelta(self):
        for nombre, nat, cli, cat, tipo, formato, sku in PRODUCTOS_DEL_ARCHIVO:
            with self.subTest(producto=nombre):
                self.assertEqual(
                    describir_sku(sku),
                    {
                        "naturaleza": nat,
                        "cliente": cli,
                        "categoria": cat,
                        "tipo": tipo,
                        "formato": formato,
                        "mercado": "local",
                    },
                )


class PesoDelFormatoTests(SimpleTestCase):

    def test_el_saco_y_la_caja_tienen_peso(self):
        self.assertEqual(peso_del_formato("saco_25kg"), 25)
        self.assertEqual(peso_del_formato("caja_20kg"), 20)

    def test_el_granel_no_pesa_cero_sino_nada(self):
        """Cero sería una afirmación; None dice que se mide de otra manera."""
        self.assertIsNone(peso_del_formato("granel"))


class ColisionesConocidasTests(SimpleTestCase):
    """
    Deja fijado el problema abierto de `SKU_PRODUCTOS.md` §4.1, para que se
    note si alguien cree haberlo resuelto sin decidirlo.
    """

    def test_ocho_productos_del_archivo_comparten_tres_codigos(self):
        skus = [p[-1] for p in PRODUCTOS_DEL_ARCHIVO]
        repetidos = {s for s in skus if skus.count(s) > 1}

        self.assertEqual(len(skus), 23)
        self.assertEqual(len(repetidos), 3)
        self.assertEqual(sum(skus.count(s) for s in repetidos), 8)

    def test_la_lecitina_ya_tiene_categoria_propia(self):
        """
        `lp_con_lecitina` (11) existe y un producto la usa, pero los dos
        «c/LdS» que colisionan están cargados como `leche_polvo` (02). Parte
        de la colisión es carga inconsistente, no falta de estructura.
        """
        con_lecitina = [
            p for p in PRODUCTOS_DEL_ARCHIVO if "c/Lec" in p[0] or "c/LdS" in p[0]
        ]
        categorias = {p[3] for p in con_lecitina}

        self.assertEqual(len(con_lecitina), 3)
        self.assertEqual(categorias, {"leche_polvo", "lp_con_lecitina"})
