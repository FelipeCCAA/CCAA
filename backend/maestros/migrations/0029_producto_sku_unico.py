"""
Un SKU, un producto.

La desambiguación va **antes** de la restricción y en la misma migración: si
fueran dos, aplicar la segunda sobre una base sin desempatar reventaría a mitad
de camino.

Qué hace con los repetidos: al primero de cada grupo —por `pk`, para que el
resultado sea el mismo corriéndola donde sea— le deja el SKU como está, y a los
demás les asigna una `variante` correlativa. No borra ni fusiona nada: decidir
si dos filas son el mismo producto duplicado o dos productos distintos es de
negocio, y una migración que lo resuelva sola borraría la evidencia de la
pregunta. Con la variante puesta, los dos quedan visibles, distinguibles y
corregibles.

`variante` lleva el SKU de 12 a 14 dígitos; `generar_sku` ya lo admite.
"""

from django.db import migrations, models


def desempatar(apps, schema_editor):
    Producto = apps.get_model("maestros", "Producto")

    repetidos = (
        Producto.objects.exclude(codigo="")
        .values("codigo")
        .annotate(cuantos=models.Count("id"))
        .filter(cuantos__gt=1)
        .values_list("codigo", flat=True)
    )

    for codigo in list(repetidos):
        # El primero conserva el SKU corto; el orden por `pk` hace que esto dé
        # el mismo resultado en cualquier base.
        hermanos = list(Producto.objects.filter(codigo=codigo).order_by("pk"))

        for numero, producto in enumerate(hermanos[1:], start=1):
            producto.variante = numero
            # El SKU se recompone aquí y no con `save()`: el modelo histórico
            # de una migración no trae los métodos del modelo real.
            producto.codigo = f"{codigo}{numero:02d}"
            producto.save(update_fields=["variante", "codigo"])


def revertir(apps, schema_editor):
    """
    Quita las variantes que puso `desempatar`, devolviendo el SKU corto.

    Vuelve a dejar duplicados, que es exactamente el estado anterior: una
    reversión que no restaura el estado anterior no es una reversión.
    """
    Producto = apps.get_model("maestros", "Producto")

    for producto in Producto.objects.exclude(variante=None).exclude(codigo=""):
        if len(producto.codigo) == 14:
            producto.codigo = producto.codigo[:12]
            producto.variante = None
            producto.save(update_fields=["variante", "codigo"])


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0028_remove_silo_silo_capacidad_no_negativa_silo_estado_and_more"),
    ]

    operations = [
        migrations.RunPython(desempatar, revertir),
        migrations.AddConstraint(
            model_name="producto",
            constraint=models.UniqueConstraint(
                condition=models.Q(("codigo", ""), _negated=True),
                fields=("codigo",),
                name="producto_sku_unico",
            ),
        ),
    ]
