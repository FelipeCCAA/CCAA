import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recepcion', '0026_alter_movimientosilo_origen_tipo_despacholeche'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='despacholeche',
            name='anulado_en',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='despacholeche',
            name='anulado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='despachos_leche_anulados', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='despacholeche',
            name='motivo_anulacion',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='despacholeche',
            name='reversa',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='reversa_despacho_leche', to='recepcion.movimientosilo'),
        ),
    ]
