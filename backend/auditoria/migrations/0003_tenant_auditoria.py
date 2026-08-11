import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("auditoria", "0002_forma_unica_de_cambios"),
        ("usuarios", "0007_alter_perfilusuario_area"),
    ]
    operations = [
        migrations.AddField(
            model_name="registroauditoria", name="empresa",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registros_auditoria", to="usuarios.empresa"),
        ),
        migrations.AddField(
            model_name="registroauditoria", name="sucursal",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="registros_auditoria", to="usuarios.sucursal"),
        ),
    ]
