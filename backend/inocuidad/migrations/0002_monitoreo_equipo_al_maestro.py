"""
`MonitoreoPPRO.equipo` pasa de texto libre a referencia al maestro.

Por qué importa más de lo que parece: el checklist de liberación decide con
este campo qué documento del Dossier se da por cumplido. Con texto libre, un
monitoreo de cuerpos extraños escrito «E1», «e1 » o «Egron 1» eran tres
máquinas distintas para el sistema y ninguna para la planta — así que o el
documento no se cumplía nunca, o se cumplía el que no era.

Se hace en cinco pasos y no con un `AlterField` porque PostgreSQL no sabe
convertir una columna de texto en una clave foránea: hay que crear la nueva,
traducir los valores y recién entonces retirar la vieja. La restricción de
unicidad se quita antes y se repone después porque nombra a la columna.
"""

from django.db import migrations, models
import django.db.models.deletion


#: Cómo se escribía cada equipo a mano → código del maestro. Cerrada a
#: propósito: un valor que no esté aquí detiene la migración en vez de
#: adivinar, porque adivinar mal deja un registro de inocuidad colgando de la
#: máquina equivocada.
EQUIVALENCIAS = {
    "e1": "e1",
    "egron 1": "e1",
    "torre 1": "e1",
    "e2": "e2",
    "egron 2": "e2",
    "torre 2": "e2",
    "rovema 3": "rovema3",
    "rovema3": "rovema3",
    "rovema 4": "rovema4",
    "rovema4": "rovema4",
    "veb": "veb",
    "sch2": "scheffers2",
    "scheffers 2": "scheffers2",
    "sch3": "scheffers3",
    "scheffers 3": "scheffers3",
}


def traducir(apps, schema_editor):
    Monitoreo = apps.get_model("inocuidad", "MonitoreoPPRO")
    Equipo = apps.get_model("maestros", "Equipo")

    por_codigo = {e.codigo: e for e in Equipo.objects.all()}
    sin_traduccion = set()

    for monitoreo in Monitoreo.objects.exclude(equipo="").exclude(equipo=None):
        clave = (monitoreo.equipo or "").strip().lower()
        codigo = EQUIVALENCIAS.get(clave)

        if codigo is None:
            sin_traduccion.add(monitoreo.equipo)
            continue

        equipo = por_codigo.get(codigo)

        if equipo is None:
            sin_traduccion.add(monitoreo.equipo)
            continue

        Monitoreo.objects.filter(pk=monitoreo.pk).update(equipo_ref=equipo)

    if sin_traduccion:
        raise RuntimeError(
            "Hay monitoreos PPRO con un equipo que no se puede traducir al "
            f"maestro: {sorted(sin_traduccion)}. Agrega la equivalencia en "
            "inocuidad/migrations/0002_monitoreo_equipo_al_maestro.py o "
            "corrige el dato antes de migrar."
        )


def deshacer(apps, schema_editor):
    Monitoreo = apps.get_model("inocuidad", "MonitoreoPPRO")

    for monitoreo in Monitoreo.objects.select_related("equipo_ref"):
        Monitoreo.objects.filter(pk=monitoreo.pk).update(
            equipo=monitoreo.equipo_ref.codigo if monitoreo.equipo_ref_id else ""
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inocuidad", "0001_initial"),
        # Las torres y las Rovemas tienen que existir antes de traducir.
        ("maestros", "0017_equipos_torres_y_envasadoras"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="monitoreoppro",
            name="monitoreo_ppro_unico_por_turno",
        ),
        migrations.AddField(
            model_name="monitoreoppro",
            name="equipo_ref",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="monitoreos_ppro",
                to="maestros.equipo",
            ),
        ),
        migrations.RunPython(traducir, deshacer),
        migrations.RemoveField(model_name="monitoreoppro", name="equipo"),
        migrations.RenameField(
            model_name="monitoreoppro",
            old_name="equipo_ref",
            new_name="equipo",
        ),
        migrations.AlterField(
            model_name="monitoreoppro",
            name="equipo",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "En qué máquina se hizo. Referencia al maestro y no texto "
                    "libre: el checklist decide con esto qué documento se da "
                    "por cumplido, y «E1», «e1 » y «Egron 1» habrían sido tres "
                    "máquinas distintas."
                ),
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="monitoreos_ppro",
                to="maestros.equipo",
                verbose_name="Equipo",
            ),
        ),
        migrations.AddConstraint(
            model_name="monitoreoppro",
            constraint=models.UniqueConstraint(
                fields=("lote", "tipo", "equipo", "fecha", "turno"),
                name="monitoreo_ppro_unico_por_turno",
                nulls_distinct=False,
            ),
        ),
    ]
