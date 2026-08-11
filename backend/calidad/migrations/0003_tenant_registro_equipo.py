import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


def asignar_sucursal(apps, schema_editor):
    RegistroEquipo = apps.get_model("calidad", "RegistroEquipo")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    for registro in RegistroEquipo.objects.select_related("documento", "equipo").all().iterator():
        if registro.equipo_id:
            sucursal_id = registro.equipo.sucursal_id
            if registro.documento.empresa_id != registro.equipo.sucursal.empresa_id:
                raise RuntimeError(
                    f"El registro de equipo {registro.pk} cruza documento y equipo de empresas distintas."
                )
        else:
            candidatas = list(
                Sucursal.objects.filter(empresa_id=registro.documento.empresa_id)
                .values_list("pk", flat=True)
            )
            if len(candidatas) != 1:
                raise RuntimeError(
                    f"No se puede inferir una única sucursal para el registro de planta {registro.pk}."
                )
            sucursal_id = candidatas[0]
        registro.sucursal_id = sucursal_id
        registro.save(update_fields=["sucursal"])


class Migration(migrations.Migration):
    dependencies = [
        ("calidad", "0002_registroequipo"),
        ("maestros", "0027_tenant_maestros"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]

    operations = [
        migrations.AddField(
            model_name="registroequipo",
            name="sucursal",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="registros_equipo_planta",
                to="usuarios.sucursal",
                verbose_name="Sucursal",
            ),
        ),
        migrations.RunPython(asignar_sucursal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="registroequipo",
                    name="sucursal",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="registros_equipo_planta",
                        to="usuarios.sucursal",
                        verbose_name="Sucursal",
                    ),
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="registroequipo",
                    name="sucursal",
                    field=models.ForeignKey(
                        default=usuarios.tenancy.sucursal_predeterminada_pruebas,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="registros_equipo_planta",
                        to="usuarios.sucursal",
                        verbose_name="Sucursal",
                    ),
                )
            ],
        ),
        migrations.RemoveConstraint(
            model_name="registroequipo", name="registro_equipo_unico_por_periodo"
        ),
        migrations.AddConstraint(
            model_name="registroequipo",
            constraint=models.UniqueConstraint(
                fields=("sucursal", "documento", "equipo", "fecha", "turno"),
                name="registro_equipo_unico_por_periodo",
            ),
        ),
    ]
