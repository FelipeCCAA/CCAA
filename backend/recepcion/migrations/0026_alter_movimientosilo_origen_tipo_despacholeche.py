import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('maestros', '0031_sembrar_siglas'),
        ('recepcion', '0025_alter_movimientosilo_origen_tipo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='movimientosilo',
            name='origen_tipo',
            field=models.CharField(blank=True, choices=[('recepcion', 'Recepción'), ('estandarizacion', 'Estandarización'), ('descremacion', 'Descremación'), ('lote', 'Consumo de lote'), ('transferencia', 'Transferencia'), ('produccion', 'Producción'), ('merma', 'Merma'), ('devolucion', 'Devolución'), ('rework', 'Reproceso'), ('despacho', 'Despacho de leche'), ('ajuste', 'Ajuste manual')], max_length=20, verbose_name='Origen'),
        ),
        migrations.CreateModel(
            name='DespachoLeche',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('litros', models.DecimalField(decimal_places=2, max_digits=12)),
                ('destino', models.CharField(max_length=160)),
                ('guia_despacho', models.CharField(max_length=60)),
                ('patente', models.CharField(max_length=15)),
                ('fecha_hora', models.DateTimeField()),
                ('operacion_id', models.UUIDField(unique=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('liberacion_analisis', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='despachos_liberados', to='recepcion.analisissilo')),
                ('movimiento', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='despacho_leche', to='recepcion.movimientosilo')),
                ('responsable', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='despachos_leche_registrados', to=settings.AUTH_USER_MODEL)),
                ('silo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='despachos_leche', to='maestros.silo')),
            ],
            options={
                'ordering': ['-fecha_hora', '-id'],
            },
        ),
    ]
