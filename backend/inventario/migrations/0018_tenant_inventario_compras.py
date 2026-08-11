import django.db.models.deletion
from django.db import migrations, models

import usuarios.tenancy


EMPRESA_MODELOS = ("Insumo", "Proveedor", "PlantillaInspeccion")
SUCURSAL_MODELOS = (
    "Bodega", "LoteInventario", "SolicitudCompra", "Adjunto",
    "SolicitudMaterial", "EjecucionMRP", "Alerta", "CicloCIP", "Aprobacion",
)


def completar_tenant(apps, schema_editor):
    Empresa = apps.get_model("usuarios", "Empresa")
    Sucursal = apps.get_model("usuarios", "Sucursal")
    empresas = list(Empresa.objects.values_list("pk", flat=True))
    sucursales = list(Sucursal.objects.values_list("pk", flat=True))

    for nombre in EMPRESA_MODELOS:
        modelo = apps.get_model("inventario", nombre)
        if modelo.objects.filter(empresa__isnull=True).exists():
            if len(empresas) != 1:
                raise RuntimeError(
                    f"{nombre} contiene datos sin empresa y no existe una única empresa. "
                    "Asigna tenant antes de inventario.0018."
                )
            modelo.objects.filter(empresa__isnull=True).update(empresa_id=empresas[0])

    for nombre in SUCURSAL_MODELOS:
        modelo = apps.get_model("inventario", nombre)
        if modelo.objects.filter(sucursal__isnull=True).exists():
            if len(sucursales) != 1:
                raise RuntimeError(
                    f"{nombre} contiene datos sin sucursal y no existe una única sucursal. "
                    "Asigna tenant antes de inventario.0018."
                )
            modelo.objects.filter(sucursal__isnull=True).update(sucursal_id=sucursales[0])


def fk_empresa(nulo, default=False, relacionado=None):
    opciones = dict(
        null=nulo,
        on_delete=django.db.models.deletion.PROTECT,
        to="usuarios.empresa",
    )
    if relacionado:
        opciones["related_name"] = relacionado
    if default:
        opciones["default"] = usuarios.tenancy.empresa_predeterminada_pruebas
    return models.ForeignKey(**opciones)


def fk_sucursal(relacionado, nulo, default=False):
    opciones = dict(
        null=nulo,
        on_delete=django.db.models.deletion.PROTECT,
        related_name=relacionado,
        to="usuarios.sucursal",
    )
    if default:
        opciones["default"] = usuarios.tenancy.sucursal_predeterminada_pruebas
    return models.ForeignKey(**opciones)


class Migration(migrations.Migration):
    dependencies = [
        ("inventario", "0017_movimiento_bajo_concesion"),
        ("usuarios", "0008_scope_obligatorio_perfil"),
    ]

    operations = [
        migrations.AddField(model_name="insumo", name="empresa", field=fk_empresa(True, relacionado="insumos")),
        migrations.AddField(model_name="proveedor", name="empresa", field=fk_empresa(True, relacionado="proveedores_inventario")),
        migrations.AddField(model_name="plantillainspeccion", name="empresa", field=fk_empresa(True, relacionado="plantillas_inspeccion_inventario")),
        migrations.AddField(model_name="ciclocip", name="sucursal", field=fk_sucursal("ciclos_cip", True)),
        migrations.AddField(model_name="aprobacion", name="sucursal", field=fk_sucursal("aprobaciones_inventario", True)),
        migrations.AddField(model_name="loteinventario", name="sucursal", field=fk_sucursal("lotes_inventario", True)),
        migrations.AddField(model_name="solicitudcompra", name="sucursal", field=fk_sucursal("solicitudes_compra", True)),
        migrations.AddField(model_name="adjunto", name="sucursal", field=fk_sucursal("adjuntos_inventario", True)),
        migrations.AddField(model_name="solicitudmaterial", name="sucursal", field=fk_sucursal("solicitudes_material", True)),
        migrations.AddField(model_name="ejecucionmrp", name="sucursal", field=fk_sucursal("ejecuciones_mrp", True)),
        migrations.AddField(model_name="alerta", name="sucursal", field=fk_sucursal("alertas_inventario", True)),
        migrations.RunPython(completar_tenant, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(model_name="insumo", name="empresa", field=fk_empresa(False, relacionado="insumos")),
                migrations.AlterField(model_name="proveedor", name="empresa", field=fk_empresa(False, relacionado="proveedores_inventario")),
                migrations.AlterField(model_name="plantillainspeccion", name="empresa", field=fk_empresa(False, relacionado="plantillas_inspeccion_inventario")),
                migrations.AlterField(model_name="ciclocip", name="sucursal", field=fk_sucursal("ciclos_cip", False)),
                migrations.AlterField(model_name="aprobacion", name="sucursal", field=fk_sucursal("aprobaciones_inventario", False)),
                migrations.AlterField(model_name="bodega", name="sucursal", field=fk_sucursal("bodegas", False)),
                migrations.AlterField(model_name="loteinventario", name="sucursal", field=fk_sucursal("lotes_inventario", False)),
                migrations.AlterField(model_name="solicitudcompra", name="sucursal", field=fk_sucursal("solicitudes_compra", False)),
                migrations.AlterField(model_name="adjunto", name="sucursal", field=fk_sucursal("adjuntos_inventario", False)),
                migrations.AlterField(model_name="solicitudmaterial", name="sucursal", field=fk_sucursal("solicitudes_material", False)),
                migrations.AlterField(model_name="ejecucionmrp", name="sucursal", field=fk_sucursal("ejecuciones_mrp", False)),
                migrations.AlterField(model_name="alerta", name="sucursal", field=fk_sucursal("alertas_inventario", False)),
            ],
            state_operations=[
                migrations.AlterField(model_name="insumo", name="empresa", field=fk_empresa(False, True, "insumos")),
                migrations.AlterField(model_name="proveedor", name="empresa", field=fk_empresa(False, True, "proveedores_inventario")),
                migrations.AlterField(model_name="plantillainspeccion", name="empresa", field=fk_empresa(False, True, "plantillas_inspeccion_inventario")),
                migrations.AlterField(model_name="ciclocip", name="sucursal", field=fk_sucursal("ciclos_cip", False, True)),
                migrations.AlterField(model_name="aprobacion", name="sucursal", field=fk_sucursal("aprobaciones_inventario", False, True)),
                migrations.AlterField(model_name="bodega", name="sucursal", field=fk_sucursal("bodegas", False, True)),
                migrations.AlterField(model_name="loteinventario", name="sucursal", field=fk_sucursal("lotes_inventario", False, True)),
                migrations.AlterField(model_name="solicitudcompra", name="sucursal", field=fk_sucursal("solicitudes_compra", False, True)),
                migrations.AlterField(model_name="adjunto", name="sucursal", field=fk_sucursal("adjuntos_inventario", False, True)),
                migrations.AlterField(model_name="solicitudmaterial", name="sucursal", field=fk_sucursal("solicitudes_material", False, True)),
                migrations.AlterField(model_name="ejecucionmrp", name="sucursal", field=fk_sucursal("ejecuciones_mrp", False, True)),
                migrations.AlterField(model_name="alerta", name="sucursal", field=fk_sucursal("alertas_inventario", False, True)),
            ],
        ),
        migrations.AlterField(model_name="insumo", name="codigo", field=models.CharField(max_length=40)),
        migrations.AlterField(model_name="proveedor", name="rut", field=models.CharField(max_length=20)),
        migrations.AlterField(model_name="bodega", name="codigo", field=models.CharField(max_length=30)),
        migrations.AlterField(model_name="solicitudcompra", name="numero", field=models.CharField(max_length=30)),
        migrations.AlterField(model_name="solicitudmaterial", name="numero", field=models.CharField(max_length=30)),
        migrations.RemoveConstraint(model_name="loteinventario", name="lote_inventario_unico"),
        migrations.AddConstraint(model_name="insumo", constraint=models.UniqueConstraint(fields=("empresa", "codigo"), name="insumo_codigo_unico_empresa")),
        migrations.AddConstraint(model_name="proveedor", constraint=models.UniqueConstraint(fields=("empresa", "rut"), name="proveedor_rut_unico_empresa")),
        migrations.AddConstraint(model_name="bodega", constraint=models.UniqueConstraint(fields=("sucursal", "codigo"), name="bodega_codigo_unico_sucursal")),
        migrations.AddConstraint(model_name="loteinventario", constraint=models.UniqueConstraint(fields=("sucursal", "insumo", "codigo", "proveedor"), name="lote_inventario_unico")),
        migrations.AddConstraint(model_name="solicitudcompra", constraint=models.UniqueConstraint(fields=("sucursal", "numero"), name="solicitud_compra_numero_unico_sucursal")),
        migrations.AddConstraint(model_name="solicitudmaterial", constraint=models.UniqueConstraint(fields=("sucursal", "numero"), name="solicitud_material_numero_unico_sucursal")),
    ]
