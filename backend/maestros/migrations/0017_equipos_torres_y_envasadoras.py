"""
El maestro de equipos pasa a cubrir toda máquina que registra algo.

Hasta aquí el maestro solo tenía lo que la planificación programa —los tres
evaporadores, las dos líneas y la de mantequilla—, porque nació del Excel de
la carta Gantt. Pero los registros de planta se llevan además en las torres de
secado y en las envasadoras, y esas máquinas no estaban: quien registraba un
PPRO escribía el nombre a mano.

Dos cambios:

1. `linea1` y `linea2` **son** las torres Egron 1 y 2. Lo dice el propio
   modelo desde antes —`Lote.Linea` rotula «Línea 1 · E1»— y lo confirmó
   Producción. Se renombran en vez de agregar `e1`/`e2` al lado: dos filas
   para la misma máquina harían que un operador eligiera una y el checklist
   buscara la otra. El renombre es seguro porque quien las referencia
   (`BloquePlan`, `RegistroEquipo`) lo hace por id, no por código.

2. Se agregan las **Rovemas 3 y 4**, que no estaban de ninguna forma.

`consume_leche` no se toca: las torres reciben lo que el evaporador ya
concentró, y marcarlas restaría la misma leche dos veces.
"""

from django.db import migrations


# (codigo antiguo, codigo nuevo, nombre nuevo, tipo nuevo)
RENOMBRES = [
    ("linea1", "e1", "Torre de secado Egron 1", "torre"),
    ("linea2", "e2", "Torre de secado Egron 2", "torre"),
]

# (codigo, nombre, tipo, orden)
NUEVOS = [
    ("rovema3", "Envasadora Rovema 3", "envasadora", 70),
    ("rovema4", "Envasadora Rovema 4", "envasadora", 71),
]


def aplicar(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")

    for antiguo, nuevo, nombre, tipo in RENOMBRES:
        # `update` y no `save()`: en una migración el modelo histórico no
        # tiene los métodos del modelo vivo, y basta con estos tres campos.
        Equipo.objects.filter(codigo=antiguo).update(
            codigo=nuevo, nombre=nombre, tipo=tipo
        )

    for codigo, nombre, tipo, orden in NUEVOS:
        # `update_or_create` porque las migraciones de datos corren también
        # sobre la base de pruebas: un `create()` chocaría con la unicidad.
        Equipo.objects.update_or_create(
            codigo=codigo,
            defaults={
                "nombre": nombre,
                "tipo": tipo,
                "consume_leche": False,
                "orden": orden,
                "activo": True,
            },
        )


def revertir(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")

    for antiguo, nuevo, _nombre, _tipo in RENOMBRES:
        Equipo.objects.filter(codigo=nuevo).update(
            codigo=antiguo,
            nombre="Línea 1" if antiguo == "linea1" else "Línea 2",
            tipo="linea",
        )

    # Las Rovemas no se borran al revertir: si ya cuelgan registros de ellas,
    # borrarlas se llevaría los registros por delante. Quedan inactivas.
    Equipo.objects.filter(codigo__in=[c for c, *_ in NUEVOS]).update(activo=False)


class Migration(migrations.Migration):

    dependencies = [
        ("maestros", "0016_frecuencia_de_los_checklists"),
    ]

    operations = [
        migrations.RunPython(aplicar, revertir),
    ]
