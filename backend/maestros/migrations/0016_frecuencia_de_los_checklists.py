"""
Marca la frecuencia real de los documentos cuyo formato la declara.

**Solo se cargan las que están escritas en el propio formulario.** El catálogo
del levantamiento tiene una columna de frecuencia, pero no coincide: clasifica
los checklists de cuerpos extraños como «Según programa» mientras el formato
dice, literalmente, «♦ Frecuencia: Al inicio del ciclo de producción». Manda el
formato — el catálogo es un resumen hecho después.

Los demás documentos se quedan en `por_lote`, que es el valor por defecto y
además el **seguro**: un documento por lote se pide en cada lote. Pasarse de
frecuencia solo molesta; quedarse corto es peligroso, porque un registro
cubriría lotes que nunca revisó.
"""

from django.db import migrations


# codigo -> (frecuencia, qué dice el formato)
FRECUENCIAS = {
    "CCAA.Cond.FORM.005": ("por_ciclo", "Al inicio del ciclo de producción"),
    "CCAA.Cond.FORM.014": ("por_ciclo", "Al inicio del ciclo de producción"),
    "CCAA.Cond.FORM.016": ("por_ciclo", "Al inicio del ciclo de producción"),
    "CCAA.Sec.FORM.007": ("por_turno", "Diario y por turno"),
}


def marcar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")

    for codigo, (frecuencia, _) in FRECUENCIAS.items():
        Documento.objects.filter(codigo=codigo).update(frecuencia=frecuencia)


def desmarcar(apps, schema_editor):
    Documento = apps.get_model("maestros", "DocumentoLiberacion")
    Documento.objects.filter(codigo__in=FRECUENCIAS).update(frecuencia="por_lote")


class Migration(migrations.Migration):

    dependencies = [("maestros", "0015_documentoliberacion_frecuencia")]

    operations = [migrations.RunPython(marcar, desmarcar)]
