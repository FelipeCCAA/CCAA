from django.db import migrations, models
import django.db.models.deletion

import usuarios.tenancy


def completar_tenant(apps, schema_editor):
    Empresa = apps.get_model("usuarios", "Empresa")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    empresas = list(Empresa.objects.order_by("pk"))
    sucursales = list(Sucursal.objects.order_by("pk"))

    modelos_empresa = [
        apps.get_model("maestros", "Mandante"),
        apps.get_model("maestros", "DocumentoLiberacion"),
    ]
    modelos_sucursal = [
        apps.get_model("maestros", "Equipo"),
        apps.get_model("maestros", "Silo"),
        apps.get_model("maestros", "Vehiculo"),
    ]

    if any(modelo.objects.filter(empresa__isnull=True).exists() for modelo in modelos_empresa):
        if len(empresas) != 1:
            raise RuntimeError(
                "Los maestros existentes no tienen empresa y no hay una única "
                "empresa inequívoca. Asigne tenant antes de maestros.0027."
            )
        for modelo in modelos_empresa:
            modelo.objects.filter(empresa__isnull=True).update(empresa_id=empresas[0].pk)

    if any(modelo.objects.filter(sucursal__isnull=True).exists() for modelo in modelos_sucursal):
        if len(sucursales) != 1:
            raise RuntimeError(
                "Los activos existentes no tienen sucursal y no hay una única "
                "sucursal inequívoca. Asigne tenant antes de maestros.0027."
            )
        for modelo in modelos_sucursal:
            modelo.objects.filter(sucursal__isnull=True).update(sucursal_id=sucursales[0].pk)


def campo_empresa(modelo, related_name, con_default):
    opciones = dict(
        on_delete=django.db.models.deletion.PROTECT,
        related_name=related_name,
        to="usuarios.empresa",
    )
    if con_default:
        opciones["default"] = usuarios.tenancy.empresa_predeterminada_pruebas
    return models.ForeignKey(**opciones)


def campo_sucursal(modelo, related_name, con_default):
    opciones = dict(
        on_delete=django.db.models.deletion.PROTECT,
        related_name=related_name,
        to="usuarios.sucursal",
    )
    if con_default:
        opciones["default"] = usuarios.tenancy.sucursal_predeterminada_pruebas
    return models.ForeignKey(**opciones)


class Migration(migrations.Migration):
    dependencies = [
        ("maestros", "0026_componentes_nulos_distintos"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]

    operations = [
        migrations.AddField(
            model_name="mandante",
            name="empresa",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="mandantes",
                to="usuarios.empresa",
            ),
        ),
        migrations.AddField(
            model_name="documentoliberacion",
            name="empresa",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="documentos_liberacion",
                to="usuarios.empresa",
            ),
        ),
        migrations.AddField(
            model_name="equipo",
            name="sucursal",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="equipos",
                to="usuarios.sucursal",
            ),
        ),
        migrations.AddField(
            model_name="silo",
            name="sucursal",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="silos",
                to="usuarios.sucursal",
            ),
        ),
        migrations.AddField(
            model_name="vehiculo",
            name="sucursal",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="vehiculos",
                to="usuarios.sucursal",
            ),
        ),
        migrations.RunPython(completar_tenant, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(model_name="mandante", name="empresa", field=campo_empresa("mandante", "mandantes", False)),
                migrations.AlterField(model_name="documentoliberacion", name="empresa", field=campo_empresa("documentoliberacion", "documentos_liberacion", False)),
                migrations.AlterField(model_name="equipo", name="sucursal", field=campo_sucursal("equipo", "equipos", False)),
                migrations.AlterField(model_name="silo", name="sucursal", field=campo_sucursal("silo", "silos", False)),
                migrations.AlterField(model_name="vehiculo", name="sucursal", field=campo_sucursal("vehiculo", "vehiculos", False)),
            ],
            state_operations=[
                migrations.AlterField(model_name="mandante", name="empresa", field=campo_empresa("mandante", "mandantes", True)),
                migrations.AlterField(model_name="documentoliberacion", name="empresa", field=campo_empresa("documentoliberacion", "documentos_liberacion", True)),
                migrations.AlterField(model_name="equipo", name="sucursal", field=campo_sucursal("equipo", "equipos", True)),
                migrations.AlterField(model_name="silo", name="sucursal", field=campo_sucursal("silo", "silos", True)),
                migrations.AlterField(model_name="vehiculo", name="sucursal", field=campo_sucursal("vehiculo", "vehiculos", True)),
            ],
        ),
        migrations.AlterField(
            model_name="mandante",
            name="nombre",
            field=models.CharField(max_length=120, verbose_name="Nombre"),
        ),
        migrations.AlterField(
            model_name="equipo",
            name="codigo",
            field=models.SlugField(
                help_text="Identificador estable. No se cambia: la planificación lo referencia.",
                max_length=40,
                verbose_name="Código",
            ),
        ),
        migrations.AlterField(
            model_name="silo",
            name="codigo",
            field=models.CharField(max_length=40, verbose_name="Código"),
        ),
        migrations.RemoveConstraint(
            model_name="mandante", name="mandante_unico_por_codigo_cliente"
        ),
        migrations.RemoveConstraint(
            model_name="documentoliberacion", name="documento_liberacion_codigo_unico"
        ),
        migrations.AddConstraint(
            model_name="mandante",
            constraint=models.UniqueConstraint(
                condition=~models.Q(codigo_cliente=""),
                fields=("empresa", "codigo_cliente"),
                name="mandante_unico_por_codigo_cliente",
            ),
        ),
        migrations.AddConstraint(
            model_name="mandante",
            constraint=models.UniqueConstraint(
                fields=("empresa", "nombre"), name="mandante_nombre_unico_empresa"
            ),
        ),
        migrations.AddConstraint(
            model_name="equipo",
            constraint=models.UniqueConstraint(
                fields=("sucursal", "codigo"), name="equipo_codigo_unico_sucursal"
            ),
        ),
        migrations.AddConstraint(
            model_name="silo",
            constraint=models.UniqueConstraint(
                fields=("sucursal", "codigo"), name="silo_codigo_unico_sucursal"
            ),
        ),
        migrations.AddConstraint(
            model_name="documentoliberacion",
            constraint=models.UniqueConstraint(
                condition=~models.Q(codigo=""),
                fields=("empresa", "codigo"),
                name="documento_liberacion_codigo_unico",
            ),
        ),
    ]
