import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


def asignar_sucursal(apps, schema_editor):
    Lote = apps.get_model("produccion", "Lote")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    ControlProceso = apps.get_model("produccion", "ControlProceso")

    for lote in Lote.objects.select_related("producto__mandante").all().iterator():
        empresa_id = lote.producto.mandante.empresa_id
        candidatas_control = set(
            ControlProceso.objects.filter(lote_id=lote.pk)
            .exclude(equipo__sucursal_id=None)
            .values_list("equipo__sucursal_id", flat=True)
        )
        candidatas_empresa = list(
            Sucursal.objects.filter(empresa_id=empresa_id).values_list("pk", flat=True)
        )

        if len(candidatas_control) == 1:
            sucursal_id = next(iter(candidatas_control))
            if sucursal_id not in candidatas_empresa:
                raise RuntimeError(
                    f"El lote {lote.pk} referencia equipos de otra empresa; "
                    "corrige esos datos antes de migrar."
                )
        elif not candidatas_control and len(candidatas_empresa) == 1:
            sucursal_id = candidatas_empresa[0]
        else:
            raise RuntimeError(
                f"No se puede inferir una única sucursal para el lote {lote.pk}. "
                "Asigna una sucursal inequívoca mediante sus controles/equipos "
                "o deja una sola sucursal activa para su empresa antes de migrar."
            )

        lote.sucursal_id = sucursal_id
        lote.save(update_fields=["sucursal"])


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0027_tenant_maestros"),
        ("produccion", "0004_control_proceso_equipo_al_maestro"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]

    operations = [
        migrations.AddField(
            model_name="lote",
            name="sucursal",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="lotes_produccion",
                to="usuarios.sucursal",
                verbose_name="Sucursal",
            ),
        ),
        migrations.RunPython(asignar_sucursal, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="lote",
                    name="sucursal",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lotes_produccion",
                        to="usuarios.sucursal",
                        verbose_name="Sucursal",
                    ),
                )
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="lote",
                    name="sucursal",
                    field=models.ForeignKey(
                        default=usuarios.tenancy.sucursal_predeterminada_pruebas,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lotes_produccion",
                        to="usuarios.sucursal",
                        verbose_name="Sucursal",
                    ),
                )
            ],
        ),
        migrations.RemoveConstraint(
            model_name="lote", name="lote_clave_natural_unica"
        ),
        migrations.AddConstraint(
            model_name="lote",
            constraint=models.UniqueConstraint(
                fields=("sucursal", "codigo_lote", "producto", "fecha"),
                name="lote_clave_natural_unica",
            ),
        ),
    ]
