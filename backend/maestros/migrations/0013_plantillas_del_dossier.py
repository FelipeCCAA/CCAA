"""
Plantillas reales de los documentos del Dossier que son formularios planos.

Salen de los formatos de planta (`Documentos Planta/`, ignorada por git), no de
la imaginación: una plantilla inventada se completa igual y da el documento
por cumplido, que es exactamente lo que un checklist de liberación no puede
permitirse.

**Solo se cargan las que se pudieron leer completas de su formato.** Las demás
siguen como atestación, y varias no deberían ser plantilla nunca — ver la nota
al final.
"""

from django.db import migrations


#: Estado de cada pieza, tal como lo define el formato: «Ok estado normal,
#: A estado anormal y describir la anomalía, N/A no aplica».
ESTADO = ["OK", "A", "N/A"]


def _pieza(clave, etiqueta):
    """Un punto de chequeo: su estado y la observación de su estado."""
    return [
        {
            "clave": f"{clave}_estado",
            "etiqueta": etiqueta,
            "tipo": "enum",
            "valores": ESTADO,
            "req": True,
        },
        {
            "clave": f"{clave}_obs",
            "etiqueta": f"{etiqueta} — observación",
            "tipo": "texto",
        },
    ]


def _checklist(piezas, cabecera):
    campos = list(cabecera)

    for clave, etiqueta in piezas:
        campos.extend(_pieza(clave, etiqueta))

    campos.append(
        {
            "clave": "acciones_correctivas",
            "etiqueta": "Observaciones / acciones correctivas",
            "tipo": "texto",
        }
    )

    return campos


# --- CCAA.Sec.FORM.007 · Check list de cuerpos extraños Rovemas 3 y 4 -------
#
# Los catorce componentes del formato, en su orden. Estado obligatorio por
# componente y turno; si se marca «A», la observación pasa a ser obligatoria
# —eso lo comprueba quien revisa, la plantilla solo la ofrece—.

ROVEMA = [
    ("acoplamiento_motriz", "Acoplamiento motriz"),
    ("sinfin_alimentador", "Sinfín alimentador"),
    ("acoplamiento_sinfin", "Acoplamiento sinfín"),
    ("inyector_nitrogeno", "Inyector de nitrógeno"),
    ("aspas_tolva", "Aspas interior tolva"),
    ("clapert_cierre", "Clapert o cierre"),
    ("sinfin_dosificador", "Sinfín dosificador"),
    ("tolva_prensa", "Tolva prensa sujeción"),
    ("tubo_formador", "Tubo formador"),
    ("boquilla_retencion", "Boquilla retención"),
    ("boquilla_formadora", "Boquilla formadora"),
    ("empaquetadura_higienica", "Empaquetadura higiénica"),
    ("tapa_tolva", "Tapa tolva"),
    ("indicador_nivel_silo", "Indicador nivel silo"),
]

CABECERA_ROVEMA = [
    {
        "clave": "rovema",
        "etiqueta": "Rovema",
        "tipo": "enum",
        "valores": ["3", "4"],
        "req": True,
    },
    {
        "clave": "fecha",
        "etiqueta": "Fecha",
        "tipo": "fecha",
        "req": True,
        "origen": "lote.fecha",
    },
    {
        "clave": "turno",
        "etiqueta": "Turno",
        "tipo": "enum",
        "valores": ["24-07", "07-17", "17-24"],
        "req": True,
    },
    {"clave": "operador", "etiqueta": "Nombre del operador", "tipo": "texto", "req": True},
]


# --- CCAA.Cond.FORM.005 · Check list de cuerpos extraños Scheffers 2 --------
#
# Del formato de Scheffers 2. Los otros dos evaporadores tienen su propio
# formato (Cond.FORM.014 para el Scheffers 3 y Cond.FORM.016 para el VEB) con
# piezas distintas, así que esta plantilla sirve para el Scheffers 2 y hay que
# revisarla si el documento se usa para los otros.

SCHEFFERS2 = [
    ("precalentador", "Pre-calentador · 1 mirilla"),
    ("condensador", "Condensador · 1 mirilla"),
    ("coil", "Coil · 1 mirilla"),
    ("pulmon_b1", "Pulmón B1 · 2 mirillas, 1 empaquetadura"),
    ("pulmon_b2", "Pulmón B2 · 2 mirillas, 1 empaquetadura"),
    ("tapa_primer_efecto", "Tapa primer efecto · 2 mirillas, 2 empaquetaduras, 10 mariposas"),
    ("primer_efecto", "Primer efecto · 3 mirillas, 2 empaquetaduras, 1 malla impurezas"),
    ("segundo_efecto", "Segundo efecto y separador de gotas · 4 mirillas, 2 empaquetaduras, 5 mariposas"),
    ("tercer_efecto", "Tercer efecto y separador de gotas · 4 mirillas, 2 empaquetaduras, 6 mariposas"),
    ("estanque_balance", "Estanque balance 1-2 · 1 tapa, 2 empaquetaduras, 2 mariposas"),
    ("inyector_arranque", "Inyector arranque · 1 mirilla"),
    ("filtros_triclover", "Filtros triclover (6 unidades) · 2 empaquetaduras, 1 malla, 1 abrazadera, 1 tuerca"),
]

CABECERA_EVAPORADOR = [
    {
        "clave": "fecha",
        "etiqueta": "Fecha",
        "tipo": "fecha",
        "req": True,
        "origen": "lote.fecha",
    },
    {
        "clave": "operador",
        "etiqueta": "Operador de condensación",
        "tipo": "texto",
        "req": True,
    },
]


PLANTILLAS = {
    "CCAA.Sec.FORM.007": _checklist(ROVEMA, CABECERA_ROVEMA),
    "CCAA.Cond.FORM.005": _checklist(SCHEFFERS2, CABECERA_EVAPORADOR),
}


def cargar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for codigo, campos in PLANTILLAS.items():
        Documento.objects.filter(codigo=codigo).update(plantilla=campos)


def vaciar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")
    Documento.objects.filter(codigo__in=PLANTILLAS).update(plantilla=[])


class Migration(migrations.Migration):

    dependencies = [("maestros", "0012_evidencia_del_dossier")]

    operations = [migrations.RunPython(cargar, vaciar)]
