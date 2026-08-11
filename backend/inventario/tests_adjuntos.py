"""
Pruebas de la comprobación de contenido de un adjunto.

La extensión y el tamaño ya se validaban. Lo que no se miraba era lo que el
archivo trae dentro, y la extensión la elige quien sube: renombrar
`payload.html` a `guia.pdf` bastaba para almacenar HTML con JavaScript.
"""

from io import BytesIO
from unittest import TestCase

from .adjuntos import ContenidoNoCorresponde, verificar


class ArchivoFalso(BytesIO):
    """Un archivo en memoria con nombre, como el que llega de una subida."""

    def __init__(self, nombre, contenido):
        super().__init__(contenido)
        self.name = nombre


class VerificarTests(TestCase):

    def test_un_pdf_de_verdad_pasa(self):
        verificar(ArchivoFalso("guia.pdf", b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"))

    def test_un_html_disfrazado_de_pdf_no_pasa(self):
        """El ataque concreto: el navegador ejecutaría lo que hay dentro."""
        with self.assertRaises(ContenidoNoCorresponde) as fallo:
            verificar(ArchivoFalso("guia.pdf", b"<html><script>alert(1)</script>"))

        self.assertIn("HTML", str(fallo.exception))

    def test_un_svg_disfrazado_de_imagen_no_pasa(self):
        """
        SVG es el caso que se olvida: parece una imagen y admite `<script>`.
        """
        with self.assertRaises(ContenidoNoCorresponde):
            verificar(ArchivoFalso("logo.png", b"<svg xmlns='...'><script/></svg>"))

    def test_un_csv_con_html_dentro_no_pasa(self):
        """
        CSV no tiene firma propia, así que la comprobación de HTML es la única
        que lo protege — y es justamente la que importa.
        """
        with self.assertRaises(ContenidoNoCorresponde):
            verificar(ArchivoFalso("datos.csv", b"  <!DOCTYPE html><body>"))

    def test_un_csv_normal_pasa(self):
        verificar(ArchivoFalso("datos.csv", b"codigo;cantidad\nA-1;30\n"))

    def test_un_ejecutable_renombrado_no_pasa(self):
        with self.assertRaises(ContenidoNoCorresponde):
            verificar(ArchivoFalso("informe.pdf", b"MZ\x90\x00\x03"))

    def test_un_xlsx_es_un_zip(self):
        verificar(ArchivoFalso("libro.xlsx", b"PK\x03\x04\x14\x00"))

    def test_un_archivo_vacio_no_pasa(self):
        with self.assertRaises(ContenidoNoCorresponde):
            verificar(ArchivoFalso("vacio.pdf", b""))

    def test_deja_el_puntero_donde_estaba(self):
        """
        Quien llama después calcula el hash y guarda el archivo. Un puntero
        movido daría un hash de la mitad del contenido y un archivo truncado —
        y el archivo se vería «guardado».
        """
        archivo = ArchivoFalso("guia.pdf", b"%PDF-1.7 con mas contenido detras")

        verificar(archivo)

        self.assertEqual(archivo.tell(), 0)
        self.assertTrue(archivo.read().startswith(b"%PDF-1.7"))
