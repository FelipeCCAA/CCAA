from django.db import migrations, models


AREAS = [
    ("aseo", "Aseo y saneamiento"),
    ("recepcion", "Recepción"),
    ("condensacion", "Condensación"),
    ("secado", "Secado"),
    ("envase", "Envase"),
    ("calidad", "Calidad"),
    ("bodega", "Bodega"),
    ("compras", "Compras"),
    ("despacho", "Despacho"),
    ("mantenimiento", "Mantenimiento"),
    ("administracion", "Administración general"),
]


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0012_alter_perfilusuario_rol_areadeperfil")]

    operations = [
        migrations.AlterField(
            model_name="perfilusuario",
            name="area",
            field=models.CharField(blank=True, choices=AREAS, max_length=30),
        ),
        migrations.AlterField(
            model_name="areadeperfil",
            name="area",
            field=models.CharField("Área", choices=AREAS, max_length=30),
        ),
    ]
