"""
`BloquePlan.equipo` pasa de texto a referencia al maestro de equipos.

En tres pasos para no perder los bloques ya programados: se agrega la clave
foránea, se rellena buscando cada código de texto en el maestro, y recién
entonces se retira la columna vieja.

Un bloque cuyo texto no exista en el maestro conservaría `NULL` y quedaría
huérfano, así que la conversión falla en vez de dejarlo pasar: un bloque sin
equipo no se puede dibujar ni sumar al balance.
"""

from django.db import migrations, models
import django.db.models.deletion


def texto_a_referencia(apps, schema_editor):
    BloquePlan = apps.get_model("planificacion", "BloquePlan")
    Equipo = apps.get_model("maestros", "Equipo")

    por_codigo = {e.codigo: e for e in Equipo.objects.all()}

    for bloque in BloquePlan.objects.all().iterator():
        equipo = por_codigo.get(bloque.equipo_texto)

        if equipo is None:
            raise RuntimeError(
                f"El bloque {bloque.pk} usa el equipo «{bloque.equipo_texto}», "
                "que no está en el maestro. Créalo antes de migrar."
            )

        bloque.equipo = equipo
        bloque.save(update_fields=["equipo"])


def referencia_a_texto(apps, schema_editor):
    BloquePlan = apps.get_model("planificacion", "BloquePlan")

    for bloque in BloquePlan.objects.select_related("equipo").iterator():
        bloque.equipo_texto = bloque.equipo.codigo if bloque.equipo else ""
        bloque.save(update_fields=["equipo_texto"])


class Migration(migrations.Migration):

    dependencies = [
        ("planificacion", "0001_initial"),
        ("maestros", "0010_sembrar_equipos"),
    ]

    operations = [
        migrations.RenameField(
            model_name="bloqueplan", old_name="equipo", new_name="equipo_texto"
        ),
        migrations.AddField(
            model_name="bloqueplan",
            name="equipo",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bloques",
                to="maestros.equipo",
                verbose_name="Equipo",
            ),
        ),
        migrations.RunPython(texto_a_referencia, referencia_a_texto),
        migrations.RemoveField(model_name="bloqueplan", name="equipo_texto"),
        migrations.AlterField(
            model_name="bloqueplan",
            name="equipo",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="bloques",
                to="maestros.equipo",
                verbose_name="Equipo",
            ),
        ),
    ]
