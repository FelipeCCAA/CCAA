"""
La mantequera es un tipo de máquina (`Equipo.Tipo.MANTEQUERA`).

Hasta aquí la etapa Mantequilla aceptaba cualquier `linea` u `otro`: una línea
de envasado aparecía como mantequera y la mantequera como línea de envasado.
Se reclasifican las candidatas —la `linea_mantequilla` sembrada en `0010` (el
batido de la crema, `prototipo/PLANIFICADOR.md`) y los equipos que ya usó una
`CorridaMantequilla`— **solo si ninguna ejecución de otra etapa las usó**:
cambiarle el tipo a una máquina que también hizo otra cosa rompería esa otra
etapa. Esas se nombran en la salida y quedan como estaban. Las demás líneas y
«otro» no se tocan, y solo se reclasifican `linea` u `otro`: los tipos que la
regla vieja aceptaba.

Una mantequera reclasificada sale de `FormatoEnvasado.equipos`: el envasado
acepta solo envasadora o línea (`FormatoEnvasado`, `Envase.clean()`). Los
envases históricos conservan su clave foránea; nadie vuelve a validarlos. Si
un formato activo queda sin máquinas, la salida lo dice: hay que autorizar una
envasadora en Maestros antes de envasar ese producto.

`sigla`, `consume_materiales` y `consume_leche` no cambian: el código de lote y
el MRP siguen igual.

La reversa devuelve a `linea` toda mantequera: antes de `0039` el tipo no
existía, así que cada una viene de este paso o se creó después, y `linea` es
el tipo que la etapa aceptaba. Los formatos no se restauran: volver a
autorizar una máquina es una decisión, no un deshacer.
"""

import sys

from django.db import migrations, models

CODIGO_SEMBRADO = "linea_mantequilla"
TIPOS_ANTERIORES = ("linea", "otro")


def _decir(texto):
    sys.stdout.write(f"  {texto}\n")


def reclasificar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    FormatoEnvasado = apps.get_model("maestros", "FormatoEnvasado")
    EjecucionProceso = apps.get_model("procesos", "EjecucionProceso")
    CorridaMantequilla = apps.get_model("procesos", "CorridaMantequilla")

    candidatas = Equipo.objects.filter(tipo__in=TIPOS_ANTERIORES).filter(
        models.Q(codigo=CODIGO_SEMBRADO)
        | models.Q(pk__in=CorridaMantequilla.objects.values("ejecucion__equipo_id"))
    )
    con_otro_uso = set(
        EjecucionProceso.objects.filter(equipo_id__in=candidatas.values("pk"))
        .exclude(etapa__tipo="mantequilla")
        .values_list("equipo_id", flat=True)
    )
    for equipo in candidatas.filter(pk__in=con_otro_uso).order_by("codigo"):
        _decir(
            f"{equipo.codigo}: queda como «{equipo.tipo}» porque también la usó otra "
            "etapa; reclasifícala a mano en Maestros si es la mantequera."
        )

    ids = list(candidatas.exclude(pk__in=con_otro_uso).values_list("pk", flat=True))
    if not ids:
        return
    Equipo.objects.filter(pk__in=ids).update(tipo="mantequera")

    autorizaciones = FormatoEnvasado.equipos.through.objects.filter(equipo_id__in=ids)
    formatos = set(autorizaciones.values_list("formatoenvasado_id", flat=True))
    autorizaciones.delete()
    for formato in FormatoEnvasado.objects.filter(
        pk__in=formatos, activo=True, equipos__isnull=True,
    ).order_by("pk"):
        _decir(
            f"El formato «{formato.nombre}» quedó sin máquinas autorizadas: autoriza "
            "una envasadora en Maestros antes de envasar ese producto."
        )


def restaurar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(tipo="mantequera").update(tipo="linea")


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0039_equipo_tipo_mantequera"),
        ("procesos", "0023_evento_operacion_id"),
    ]

    operations = [
        migrations.RunPython(reclasificar, restaurar),
    ]
