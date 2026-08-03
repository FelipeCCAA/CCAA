"""
`ControlProceso.equipo` pasa de lista fija a referencia al maestro.

Era un `TextChoices` —VEB, SCH2, SCH3, E1, E2— declarado provisional en su
propio comentario: agregar una máquina obligaba a editar código y desplegar.
Ahora que el maestro de equipos existe y cubre las torres y las envasadoras,
la lista sobra, y tenerla obligaba además a mantener dos vocabularios para lo
mismo: «SCH2» aquí y «scheffers2» en la planificación.

Importa para el checklist: los documentos `Cond.FORM.010` (PCC 1) y
`Sec.FORM.025` (pulverización) se dan por cumplidos según en qué equipo se
registró el control, y ese criterio no podía compararse contra el maestro
mientras aquí hubiera otro alfabeto.

El equipo es obligatorio —un control de proceso sin máquina no dice nada—,
así que la columna termina en `NOT NULL`. Por eso la traducción tiene que
cubrir todas las filas: si alguna queda sin equipo, la migración se detiene
con el detalle en vez de fallar con un error de restricción.
"""

from django.db import migrations, models
import django.db.models.deletion


#: Valor antiguo → código del maestro. Cerrada: eran cinco y se conocen todos.
EQUIVALENCIAS = {
    "VEB": "veb",
    "SCH2": "scheffers2",
    "SCH3": "scheffers3",
    "E1": "e1",
    "E2": "e2",
}


def traducir(apps, schema_editor):
    Control = apps.get_model("produccion", "ControlProceso")
    Equipo = apps.get_model("maestros", "Equipo")

    por_codigo = {e.codigo: e for e in Equipo.objects.all()}
    problemas = set()

    for control in Control.objects.all():
        codigo = EQUIVALENCIAS.get((control.equipo or "").strip().upper())
        equipo = por_codigo.get(codigo) if codigo else None

        if equipo is None:
            problemas.add(control.equipo)
            continue

        Control.objects.filter(pk=control.pk).update(equipo_ref=equipo)

    if problemas:
        raise RuntimeError(
            "Hay controles de proceso con un equipo que no está en el maestro: "
            f"{sorted(problemas)}. Cárgalo en maestros.Equipo o corrige el "
            "dato antes de migrar."
        )


def deshacer(apps, schema_editor):
    Control = apps.get_model("produccion", "ControlProceso")
    inverso = {v: k for k, v in EQUIVALENCIAS.items()}

    for control in Control.objects.select_related("equipo_ref"):
        Control.objects.filter(pk=control.pk).update(
            equipo=inverso.get(control.equipo_ref.codigo, "") if control.equipo_ref_id else ""
        )


class Migration(migrations.Migration):

    dependencies = [
        ("produccion", "0003_alter_lote_kg_producidos"),
        ("maestros", "0017_equipos_torres_y_envasadoras"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="controlproceso",
            name="control_proceso_unico_por_lote_equipo_fecha_turno",
        ),
        migrations.AddField(
            model_name="controlproceso",
            name="equipo_ref",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="controles_proceso",
                to="maestros.equipo",
            ),
        ),
        migrations.RunPython(traducir, deshacer),
        migrations.RemoveField(model_name="controlproceso", name="equipo"),
        migrations.RenameField(
            model_name="controlproceso",
            old_name="equipo_ref",
            new_name="equipo",
        ),
        migrations.AlterField(
            model_name="controlproceso",
            name="equipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="controles_proceso",
                to="maestros.equipo",
                verbose_name="Equipo",
            ),
        ),
        migrations.AlterModelOptions(
            name="controlproceso",
            options={
                "ordering": ["-fecha", "equipo__orden"],
                "verbose_name": "Control de proceso",
                "verbose_name_plural": "Controles de proceso",
            },
        ),
        migrations.AddConstraint(
            model_name="controlproceso",
            constraint=models.UniqueConstraint(
                fields=("lote", "equipo", "fecha", "turno"),
                name="control_proceso_unico_por_lote_equipo_fecha_turno",
            ),
        ),
    ]
