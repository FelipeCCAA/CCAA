"""
Plantilla de `CCAA.Sec.FORM.003` · Inspección Pre-operativa E1-E2.

Transcrita de `Inspeccion preoperativa egron 1.xlsx` (Documentos Planta,
«16.- Procedimiento y formularios en Word»), cuyo encabezado declara el código
`CCAA.SEC.FORM.003.01`. No está inventada: los cinco grupos, sus subpuntos y
el orden son los del formato.

**La frecuencia también sale del formato**, que dice al pie «FRECUENCIA:
REALIZAR AL INICIO DE CADA PROCESO». Pasa de `por_lote` a `por_ciclo`, con lo
que el registro deja el expediente del lote y se lleva en `/registros`, colgado
de la torre. Es lo correcto: la inspección se hace una vez al arrancar el
ciclo, no una por cada lote que salga de él.

Qué NO va en la plantilla:

- **Egrón** y **Fecha**, que el formato pide en la cabecera. `RegistroEquipo`
  ya los tiene como equipo y fecha, y el formulario los dibuja aparte. Un
  campo más sería volver a teclear lo que el modelo captura, y peor: dos
  fechas que pueden discrepar.
- Los estados son `OK`/`NO OK` y no `OK`/`A`/`N/A` como en los checklists de
  cuerpos extraños, porque es lo que este formato manda escribir: «CUANDO LA
  INSPECCIÓN PRESENTE DESVIACIONES RELLENAR CON "NO OK" Y DEJAR REGISTRADO LA
  ACCIÓN CORRECTIVA».
"""

from django.db import migrations


CODIGO = "CCAA.Sec.FORM.003"

ESTADOS = ["OK", "NO OK"]

#: (clave, etiqueta) de cada punto revisable, en el orden del formato. Los
#: cinco grupos numerados se aplanan en sus subpuntos porque el «sí/no» del
#: formato se marca por subpunto, no por grupo.
PUNTOS = [
    ("rtd5_ducto1", "1. RTD 5° piso, instaladas · Ducto aire exhausto 1"),
    ("rtd5_ducto2", "1. RTD 5° piso, instaladas · Ducto aire exhausto 2"),
    ("lonas_ducto1", "2. Lonas aire exhausto 4° piso, apretadas · Ducto aire exhausto 1"),
    ("lonas_ducto2", "2. Lonas aire exhausto 4° piso, apretadas · Ducto aire exhausto 2"),
    ("rtd3_termocupla", "3. RTD 3° piso, instaladas · Termocupla y vacío colector"),
    ("llaves_test", "4. Llaves de seguridad en posición · Modo test (producción)"),
    ("llaves_aseo", "4. Llaves de seguridad en posición · Modo aseo (término proceso)"),
    (
        "llaves_mantencion",
        "4. Llaves de seguridad en posición · Modo mantención (mantenimiento equipos)",
    ),
    ("switch_fluidbed", "5. 1er Piso Switch Modo Producción · Fluidbed"),
]


def _plantilla():
    campos = [
        {"clave": "producto", "etiqueta": "Producto", "tipo": "texto", "req": True},
        {"clave": "operacion", "etiqueta": "Operación", "tipo": "texto", "req": True},
        {
            "clave": "responsable",
            "etiqueta": "Nombre responsable",
            "tipo": "texto",
            "req": True,
        },
    ]

    for clave, etiqueta in PUNTOS:
        campos.append(
            {
                "clave": f"{clave}_estado",
                "etiqueta": etiqueta,
                "tipo": "enum",
                "valores": ESTADOS,
                "req": True,
            }
        )
        # La acción correctiva es opcional porque solo aplica al «NO OK». Que
        # el formato tenga la columna no significa que haya que llenarla
        # siempre; exigirla obligaría a escribir «sin novedad» nueve veces.
        campos.append(
            {
                "clave": f"{clave}_accion",
                "etiqueta": f"{etiqueta} — acción correctiva",
                "tipo": "texto",
            }
        )

    return campos


def aplicar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    Documento.objects.filter(codigo=CODIGO).update(
        plantilla=_plantilla(), frecuencia="por_ciclo"
    )


def revertir(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    Documento.objects.filter(codigo=CODIGO).update(plantilla=[], frecuencia="por_lote")


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0020_alter_recetacomponente_options_and_more"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
