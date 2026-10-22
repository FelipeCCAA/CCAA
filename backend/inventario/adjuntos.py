"""
Comprobación del contenido de un archivo adjunto.

La extensión y el tamaño ya se validaban. Lo que no se miraba era **lo que el
archivo trae dentro**, y la extensión la elige quien sube: renombrar
`payload.html` a `guia.pdf` bastaba para almacenar HTML con JavaScript en el
sistema y repartir el enlace.

`SECURE_CONTENT_TYPE_NOSNIFF` y la CSP reducen el daño, pero ninguno de los dos
impide guardar el archivo. Esto sí: si la firma no corresponde a la extensión,
no entra.

**No sustituye a un antivirus.** Comprueba que un PDF empiece por `%PDF`, no
que ese PDF sea inofensivo. Eso es otra capa y hoy no existe.
"""

from pathlib import Path
from zipfile import BadZipFile, ZipFile


#: Los primeros bytes de cada formato aceptado. Un formato con varias firmas
#: —JPEG las tiene— las lista todas.
FIRMAS = {
    ".pdf": [b"%PDF-"],
    # XLSX es un ZIP; XLS es un documento OLE2 de los de antes.
    ".xlsx": [b"PK\x03\x04"],
    ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"PK\x03\x04"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".webp": [b"RIFF"],
}

#: Comienzos que delatan un documento que el navegador ejecutaría. Se buscan en
#: los formatos sin firma propia —CSV— porque son la vía real de ataque: un
#: `.csv` que en realidad es HTML con un `<script>` dentro.
COMIENZOS_EJECUTABLES = (b"<!doctype html", b"<html", b"<?xml", b"<svg", b"<script")

#: Cuántos bytes hacen falta para decidir. Las firmas son cortas; el margen es
#: para saltarse espacios en blanco al buscar HTML.
CABECERA = 512


class ContenidoNoCorresponde(ValueError):
    """La firma del archivo no coincide con lo que dice su extensión."""


def verificar(archivo) -> None:
    """
    Lee la cabecera y comprueba que corresponda a la extensión declarada.

    Deja el puntero **donde estaba**: quien llama después calcula el hash y
    guarda el archivo, y un puntero movido produciría un hash de la mitad del
    contenido y un archivo truncado.
    """
    extension = Path(archivo.name or "").suffix.lower()

    posicion = archivo.tell()
    archivo.seek(0)
    cabecera = archivo.read(CABECERA)
    archivo.seek(posicion)

    if not cabecera:
        raise ContenidoNoCorresponde("El archivo está vacío.")

    inicio = cabecera.lstrip()[:64].lower()

    if inicio.startswith(COMIENZOS_EJECUTABLES):
        raise ContenidoNoCorresponde(
            "El archivo contiene HTML o SVG, que el navegador podría ejecutar. "
            "Si es un informe, súbelo en PDF."
        )

    firmas = FIRMAS.get(extension)

    # Un formato sin firma —CSV— ya pasó la comprobación de arriba, que es la
    # que importa en su caso: no hay forma de distinguir un CSV legítimo de
    # texto cualquiera, y tampoco hace falta.
    if firmas and not any(cabecera.startswith(firma) for firma in firmas):
        raise ContenidoNoCorresponde(
            f"El contenido no corresponde a un archivo {extension}. "
            "Cambiarle la extensión a un archivo no cambia lo que es."
        )

    if extension == ".webp" and cabecera[8:12] != b"WEBP":
        raise ContenidoNoCorresponde("El contenido RIFF no es una imagen WEBP.")
    if extension == ".xls" and cabecera.startswith(b"PK"):
        raise ContenidoNoCorresponde("Un archivo ZIP no es un Excel XLS; usa su formato real.")
    if extension == ".csv":
        try:
            archivo.seek(0)
            contenido = archivo.read().decode("utf-8-sig")
            if any(ord(caracter) < 32 and caracter not in "\t\r\n" for caracter in contenido):
                raise ValueError
            if contenido.lstrip().startswith(("MZ", "PK", "%PDF-")):
                raise ValueError
        except (UnicodeDecodeError, ValueError) as error:
            raise ContenidoNoCorresponde("El CSV debe contener texto UTF-8, no un archivo binario renombrado.") from error
        finally:
            archivo.seek(posicion)
    if extension == ".xlsx":
        try:
            archivo.seek(0)
            with ZipFile(archivo) as libro:
                entradas = libro.infolist()
                nombres = {entrada.filename for entrada in entradas}
                if (len(entradas) > 10000
                    or sum(entrada.file_size for entrada in entradas) > 64 * 1024 * 1024
                    or any(entrada.flag_bits & 1 for entrada in entradas)):
                    raise ContenidoNoCorresponde("El Excel excede los límites de descompresión o está cifrado.")
                if not {"[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"} <= nombres:
                    raise ContenidoNoCorresponde("El archivo ZIP no contiene la estructura de un Excel XLSX.")
                if any("vbaproject" in nombre.lower() for nombre in nombres):
                    raise ContenidoNoCorresponde("No se admiten macros en archivos XLSX.")
                # Lee sólo metadatos acotados, sin extraer rutas ni ejecutar XML.
                for nombre in ("[Content_Types].xml", "xl/workbook.xml", "_rels/.rels"):
                    if libro.getinfo(nombre).file_size > 1024 * 1024:
                        raise ContenidoNoCorresponde("Los metadatos del Excel son demasiado grandes.")
                    contenido = libro.read(nombre).decode("utf-8-sig").lower()
                    if "<!doctype" in contenido or "<!entity" in contenido:
                        raise ContenidoNoCorresponde("El Excel contiene declaraciones XML no permitidas.")
                    from xml.etree.ElementTree import ParseError, fromstring
                    try:
                        raiz = fromstring(contenido)
                    except ParseError as error:
                        raise ContenidoNoCorresponde("Los metadatos XML del Excel están dañados.") from error
                    esperado = {
                        "[Content_Types].xml": "{http://schemas.openxmlformats.org/package/2006/content-types}types",
                        "xl/workbook.xml": "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook",
                        "_rels/.rels": "{http://schemas.openxmlformats.org/package/2006/relationships}relationships",
                    }[nombre]
                    if raiz.tag != esperado:
                        raise ContenidoNoCorresponde("Los metadatos no corresponden a un Excel XLSX.")
        except (BadZipFile, RuntimeError, KeyError, OSError, ValueError) as error:
            if isinstance(error, ContenidoNoCorresponde):
                raise
            raise ContenidoNoCorresponde("El archivo Excel está incompleto o dañado.") from error
        finally:
            archivo.seek(posicion)
