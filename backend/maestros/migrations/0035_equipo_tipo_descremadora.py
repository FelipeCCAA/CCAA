from django.db import migrations, models


def clasificar_descremadoras_existentes(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(tipo="otro", nombre__icontains="descrem").update(
        tipo="descremadora"
    )
    Equipo.objects.filter(tipo="otro", codigo__icontains="descrem").update(
        tipo="descremadora"
    )


def restaurar_tipo_anterior(apps, schema_editor):
    Equipo = apps.get_model("maestros", "Equipo")
    Equipo.objects.filter(tipo="descremadora").update(tipo="otro")


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0034_normalizar_codigos_silos_recepcion_confirmados"),
    ]

    operations = [
        migrations.AlterField(
            model_name="equipo",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("descremadora", "Descremadora"),
                    ("evaporador", "Evaporador"),
                    ("torre", "Torre de secado"),
                    ("envasadora", "Envasadora"),
                    ("linea", "Línea"),
                    ("carga", "Carga"),
                    ("otro", "Otro"),
                ],
                max_length=20,
                verbose_name="Tipo",
            ),
        ),
        migrations.RunPython(
            clasificar_descremadoras_existentes,
            restaurar_tipo_anterior,
        ),
    ]
