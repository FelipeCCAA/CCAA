"""
`CicloCIP.equipo` pasa de texto libre a referencia al maestro.

Mismo motivo que en `MonitoreoPPRO`: un CIP es la limpieza de una máquina
concreta, y con el nombre escrito a mano no hay forma de responder «¿esta
torre está aseada?» — que es justo lo que un aseo por ciclo tiene que poder
responder cuando el checklist del lote lo consuma.

Se traduce lo que se reconoce; lo que no, queda sin equipo. Aquí sí puede
quedar nulo —a diferencia del control de proceso— porque el campo ya era
opcional en la práctica y un ciclo sin máquina identificada sigue siendo un
registro histórico válido. El texto original se conserva en `observaciones`
para que nada se pierda en silencio.
"""

from django.db import migrations, models
import django.db.models.deletion


EQUIVALENCIAS = {
    "e1": "e1",
    "egron 1": "e1",
    "torre 1": "e1",
    "linea 1": "e1",
    "línea 1": "e1",
    "e2": "e2",
    "egron 2": "e2",
    "torre 2": "e2",
    "linea 2": "e2",
    "línea 2": "e2",
    "veb": "veb",
    "sch2": "scheffers2",
    "scheffers 2": "scheffers2",
    "sch3": "scheffers3",
    "scheffers 3": "scheffers3",
    "rovema 3": "rovema3",
    "rovema3": "rovema3",
    "rovema 4": "rovema4",
    "rovema4": "rovema4",
}


def traducir(apps, schema_editor):
    Ciclo = apps.get_model("inventario", "CicloCIP")
    Equipo = apps.get_model("maestros", "Equipo")

    por_codigo = {e.codigo: e for e in Equipo.objects.all()}

    for ciclo in Ciclo.objects.exclude(equipo=""):
        original = (ciclo.equipo or "").strip()
        equipo = por_codigo.get(EQUIVALENCIAS.get(original.lower(), ""))

        if equipo is not None:
            Ciclo.objects.filter(pk=ciclo.pk).update(equipo_ref=equipo)
            continue

        # No se reconoce: se guarda el texto en las observaciones antes de
        # perderlo. Un dato que desaparece sin dejar rastro es peor que uno
        # que quedó en el lugar equivocado, porque nadie lo va a echar de menos.
        nota = f"Equipo registrado como «{original}» antes de usar el maestro."
        Ciclo.objects.filter(pk=ciclo.pk).update(
            observaciones=f"{ciclo.observaciones}\n{nota}".strip()
        )


def deshacer(apps, schema_editor):
    Ciclo = apps.get_model("inventario", "CicloCIP")

    for ciclo in Ciclo.objects.select_related("equipo_ref"):
        Ciclo.objects.filter(pk=ciclo.pk).update(
            equipo=ciclo.equipo_ref.nombre if ciclo.equipo_ref_id else ""
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventario", "0009_consumoloteproduccion"),
        ("maestros", "0017_equipos_torres_y_envasadoras"),
    ]

    operations = [
        migrations.AddField(
            model_name="ciclocip",
            name="equipo_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="ciclos_cip",
                to="maestros.equipo",
            ),
        ),
        migrations.RunPython(traducir, deshacer),
        migrations.RemoveField(model_name="ciclocip", name="equipo"),
        migrations.RenameField(
            model_name="ciclocip",
            old_name="equipo_ref",
            new_name="equipo",
        ),
    ]
