"""
Separa el checklist de cuerpos extraños en uno por evaporador.

El Dossier lo lista como un solo registro —«Checklist de Cuerpos Extraños
Evaporadores», con los códigos `Cond.FORM.005/014/016`—, pero en planta son
tres formatos distintos con **piezas distintas**: el Scheffers 2 tiene pulmones
y coil, el Scheffers 3 tiene tapas por efecto y el VEB tiene cuatro efectos.

Una plantilla única obligaría a elegir uno y dejar los otros dos sin sus
piezas, o a mezclar las tres listas y pedir el estado de piezas que ese
evaporador no tiene. Cualquiera de las dos convierte el checklist en un
trámite: se marca igual y no dice nada de lo que se revisó.

El checklist pasa de 19 a 21 documentos. Los que iban después se corren dos
lugares para que el orden siga el flujo del Dossier (Recepción →
Condensación → Secado → Envase).
"""

from django.db import migrations


ESTADO = ["OK", "A", "N/A"]

CABECERA = [
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


def _plantilla(piezas):
    campos = list(CABECERA)

    for clave, etiqueta in piezas:
        campos.append(
            {
                "clave": f"{clave}_estado",
                "etiqueta": etiqueta,
                "tipo": "enum",
                "valores": ESTADO,
                "req": True,
            }
        )
        campos.append(
            {
                "clave": f"{clave}_obs",
                "etiqueta": f"{etiqueta} — observación",
                "tipo": "texto",
            }
        )

    campos.append(
        {
            "clave": "acciones_correctivas",
            "etiqueta": "Observaciones / acciones correctivas",
            "tipo": "texto",
        }
    )

    return campos


# CCAA.Cond.FORM.005.01 — Scheffers 2
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

# CCAA.Cond.FORM.014.01 — Scheffers 3
SCHEFFERS3 = [
    ("tapa_sup_1", "Tapa superior primer efecto · 1 mirilla, 8 pernos y tuercas, 1 empaquetadura"),
    ("tapa_sup_2", "Tapa superior segundo efecto · 1 mirilla, 1 empaquetadura, 8 pernos y tuercas"),
    ("tapa_sup_3", "Tapa superior tercer efecto · 1 mirilla, 1 empaquetadura, 8 pernos y tuercas"),
    ("separador_1", "Separador de gotas primer efecto · 1 tapa, 2 mirillas, 1 empaquetadura, 1 mariposa"),
    ("separador_2", "Separador de gotas segundo efecto · 1 tapa, 2 mirillas, 1 empaquetadura, 1 mariposa"),
    ("separador_3", "Separador de gotas tercer efecto · 1 tapa, 2 mirillas, 1 empaquetadura, 1 mariposa"),
    ("tapa_hombre_1", "Tapa hombre inferior primer efecto · 1 tapa, 1 mirilla, 1 empaquetadura, 1 mariposa"),
    ("tapa_hombre_2", "Tapa hombre inferior segundo efecto · 1 tapa, 1 empaquetadura, 1 mariposa, 1 mirilla"),
    ("tapa_hombre_3", "Tapa hombre inferior tercer efecto · 1 tapa, 1 empaquetadura, 1 mariposa, 1 mirilla"),
    ("filtros_triclover", "Filtros triclover (cada filtro) · 2 empaquetaduras, 1 malla, 1 tuerca"),
]

# CCAA.Cond.FORM.016.01 — VEB. Es el único con cuatro efectos.
VEB = [
    ("tapa_sup_1", "Tapa superior primer efecto · 1 mirilla, 12 pernos y tuercas, 2 empaquetaduras"),
    ("tapa_sup_2", "Tapa superior segundo efecto · 1 mirilla, 2 empaquetaduras, 6 pernos y tuercas"),
    ("tapa_sup_3", "Tapa superior tercer efecto · 1 mirilla, 2 empaquetaduras, 6 pernos y tuercas"),
    ("tapa_sup_4", "Tapa superior cuarto efecto · 2 mirillas, 2 empaquetaduras, 6 pernos y tuercas"),
    ("tapa_inf_1", "Tapa inferior primer efecto · 1 empaquetadura, 4 pernos y tuercas, 1 tapa"),
    ("tapa_inf_2", "Tapa inferior segundo efecto · 1 empaquetadura, 4 pernos y tuercas, 1 tapa"),
    ("tapa_inf_3", "Tapa inferior tercer efecto · 1 empaquetadura, 4 pernos y tuercas, 1 tapa"),
    ("tapa_inf_4", "Tapa inferior cuarto efecto · 1 empaquetadura, 4 pernos y tuercas, 1 tapa"),
    ("separador_1", "Separador de gotas primer efecto · 2 mirillas, 2 empaquetaduras"),
    ("separador_2", "Separador de gotas segundo efecto · 2 mirillas, 1 empaquetadura"),
    ("separador_3", "Separador de gotas tercer efecto · 2 mirillas, 1 empaquetadura"),
    ("separador_4", "Separador de gotas cuarto efecto · 2 mirillas, 1 empaquetadura"),
    ("filtros_triclover", "Filtros triclover (cada filtro) · 1 empaquetadura, 1 malla, 1 tuerca"),
]


NUEVOS = [
    ("CCAA.Cond.FORM.014", "Checklist de Cuerpos Extraños Scheffers 3", 4, SCHEFFERS3),
    ("CCAA.Cond.FORM.016", "Checklist de Cuerpos Extraños VEB", 5, VEB),
]


def separar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    # Los que van después de la condensación se corren dos lugares. De atrás
    # hacia adelante para no chocar con los que todavía no se movieron.
    for documento in Documento.objects.filter(orden__gte=4).order_by("-orden"):
        documento.orden += 2
        documento.save(update_fields=["orden"])

    # El que existía pasa a ser el del Scheffers 2, que es de donde salió su
    # plantilla.
    Documento.objects.filter(codigo="CCAA.Cond.FORM.005").update(
        nombre="Checklist de Cuerpos Extraños Scheffers 2",
        plantilla=_plantilla(SCHEFFERS2),
        orden=3,
    )

    for codigo, nombre, orden, piezas in NUEVOS:
        Documento.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "area": "condensacion",
                "aplica_a": ["polvo"],
                "plantilla": _plantilla(piezas),
                "orden": orden,
                "activo": True,
            },
        )


def unir(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    Documento.objects.filter(codigo__in=[c for c, *_ in NUEVOS]).delete()

    Documento.objects.filter(codigo="CCAA.Cond.FORM.005").update(
        nombre="Checklist de Cuerpos Extraños Evaporadores",
        plantilla=_plantilla(SCHEFFERS2),
        orden=3,
    )

    for documento in Documento.objects.filter(orden__gte=6).order_by("orden"):
        documento.orden -= 2
        documento.save(update_fields=["orden"])


class Migration(migrations.Migration):

    dependencies = [("maestros", "0013_plantillas_del_dossier")]

    operations = [migrations.RunPython(separar, unir)]
