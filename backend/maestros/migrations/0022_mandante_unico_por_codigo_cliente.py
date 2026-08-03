"""
Un código de cliente, un mandante. Y la fusión de los que ya se duplicaron.

La base de desarrollo tenía «Nestle» y «Nestlé» a la vez, las dos con
`codigo_cliente = "nestle"`, y los productos de ese cliente quedaron repartidos
entre las dos fichas: seis colgando de una y los códigos de producción de la
otra. Nada avisaba, porque nada lo impedía.

Importa más de lo que parece: el segmento de cliente del SKU no tiene forma de
distinguir dos mandantes que lo compartan. Sus productos salen con SKU
idénticos, y como el **código de lote lleva el SKU dentro**, también con el
mismo código de lote.

La restricción va en la migración siguiente y no aquí, y no es cosmético:
PostgreSQL no admite crear un índice único en la misma transacción en que se
borraron filas de esa tabla —quedan disparadores de clave foránea pendientes—
y la migración revienta con «no se puede hacer CREATE INDEX ... porque tiene
eventos de trigger pendientes». Separadas, cada una corre en su transacción.

Sobre cuál sobrevive: **el de id más bajo**, que es una regla y no un criterio.
Elegir «el que tenga más productos» o «el mejor escrito» obliga a inventar un
desempate distinto cada vez. El nombre sí se corrige aparte, y solo el de
Nestlé: «Nestlé» es el nombre de la empresa, es como se llama en los códigos de
producción y es la etiqueta que el propio catálogo del SKU declara.
"""

from django.db import migrations


def fusionar(apps, schema_editor):
    Mandante = apps.get_model("maestros", "Mandante")
    Producto = apps.get_model("maestros", "Producto")
    CodigoProduccion = apps.get_model("planificacion", "CodigoProduccion")

    codigos = (
        Mandante.objects.exclude(codigo_cliente="")
        .values_list("codigo_cliente", flat=True)
        .distinct()
    )

    for codigo in codigos:
        fichas = list(
            Mandante.objects.filter(codigo_cliente=codigo).order_by("id")
        )

        if len(fichas) < 2:
            continue

        superviviente, *duplicados = fichas
        ids = [m.id for m in duplicados]

        Producto.objects.filter(mandante_id__in=ids).update(
            mandante=superviviente
        )
        CodigoProduccion.objects.filter(mandante_id__in=ids).update(
            mandante=superviviente
        )
        Mandante.objects.filter(id__in=ids).delete()

    # El nombre correcto de la empresa lleva tilde. Se corrige aquí y no en la
    # fusión porque no es una regla general: es este cliente.
    Mandante.objects.filter(codigo_cliente="nestle").update(nombre="Nestlé")


def deshacer(apps, schema_editor):
    """
    No se pueden desfusionar: al borrar los duplicados se perdió qué producto
    colgaba de cuál. Revertir la restricción —lo que hace la migración
    siguiente— vuelve a permitir el duplicado, que es lo único reversible de
    este cambio.
    """


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0021_plantilla_inspeccion_preoperativa_egron"),
        # `CodigoProduccion` se repunta aquí, así que su tabla tiene que existir.
        ("planificacion", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(fusionar, deshacer),
    ]
