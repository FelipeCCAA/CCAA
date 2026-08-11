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
