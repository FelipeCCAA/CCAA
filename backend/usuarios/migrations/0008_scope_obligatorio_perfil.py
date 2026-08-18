import os

from django.db import migrations, models
import django.db.models.deletion

import usuarios.tenancy


def completar_scope(apps, schema_editor):
    Empresa = apps.get_model("usuarios", "Empresa")
    Perfil = apps.get_model("usuarios", "PerfilUsuario")
    Sucursal = apps.get_model("usuarios", "Sucursal")

    todas = list(Sucursal.objects.order_by("pk"))
    if not todas:
        entorno = os.getenv("DJANGO_ENV", "development").strip().lower()
        if entorno in {"test", "ci"}:
            datos = {
                "rut": "TENANT-TEST",
                "empresa": "Empresa aislada de pruebas",
                "codigo": "INTERNA",
                "sucursal": "Configuración interna",
            }
        else:
            datos = {
                "rut": os.getenv("CCAA_INITIAL_COMPANY_RUT", "").strip(),
                "empresa": os.getenv("CCAA_INITIAL_COMPANY_NAME", "").strip(),
                "codigo": "INTERNA",
                "sucursal": "Configuración interna",
            }
            faltantes = [clave for clave, valor in datos.items() if not valor]
            if faltantes:
                raise RuntimeError(
                    "No existe una organización inicial. Configure "
                    "CCAA_INITIAL_COMPANY_RUT y CCAA_INITIAL_COMPANY_NAME "
                    "antes de aplicar usuarios.0008."
                )

        empresa, _ = Empresa.objects.get_or_create(
            rut=datos["rut"], defaults={"nombre": datos["empresa"]}
        )
        sucursal, _ = Sucursal.objects.get_or_create(
            empresa=empresa,
            codigo=datos["codigo"],
            defaults={"nombre": datos["sucursal"]},
        )
        todas = [sucursal]
    for perfil in Perfil.objects.select_related("sucursal").order_by("pk"):
        if perfil.sucursal_id:
            perfil.empresa_id = perfil.sucursal.empresa_id
            perfil.sucursal_id = None
            perfil.alcance = "empresa"
        elif perfil.empresa_id:
            candidatas = [s for s in todas if s.empresa_id == perfil.empresa_id]
            if not candidatas:
                raise RuntimeError(
                    f"PerfilUsuario {perfil.pk} no tiene una organización inequívoca."
                )
            perfil.sucursal_id = None
            perfil.alcance = "empresa"
        elif len(todas) == 1:
            perfil.empresa_id = todas[0].empresa_id
            perfil.sucursal_id = None
            perfil.alcance = "empresa"
        else:
            raise RuntimeError(
                f"PerfilUsuario {perfil.pk} no tiene tenant y existen "
                f"{len(todas)} sucursales. Asigne su scope antes de aplicar "
                "usuarios.0008."
            )
        perfil.save(update_fields=["empresa", "sucursal", "alcance"])

    # PostgreSQL aplaza la comprobación de las claves foráneas que acaban de
    # escribirse, y **no admite `ALTER TABLE` sobre una tabla con eventos de
    # trigger pendientes**. Las operaciones que siguen a este `RunPython` son
    # justamente `AlterField` sobre esta tabla, así que sin vaciar la cola la
    # migración falla con:
    #
    #     no se puede hacer ALTER TABLE en «usuarios_perfilusuario»
    #     porque tiene eventos de «trigger» pendientes
    #
    # Solo ocurre cuando hay perfiles que actualizar: con la base vacía el
    # bucle no escribe nada, no hay eventos pendientes y la migración pasa. Por
    # eso el CI —que parte de una base limpia— no lo ve, y sí lo ve cualquier
    # servidor con datos. Se descubrió sobre una base con siete perfiles.
    schema_editor.execute("SET CONSTRAINTS ALL IMMEDIATE")


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0007_alter_perfilusuario_area")]

    operations = [
        migrations.AddField(
            model_name="perfilusuario",
            name="alcance",
            field=models.CharField(
                choices=[("sucursal", "Sucursal"), ("empresa", "Toda la empresa")],
                default="sucursal",
                max_length=10,
            ),
        ),
        migrations.RunPython(completar_scope, migrations.RunPython.noop),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="perfilusuario",
                    name="empresa",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perfiles",
                        to="usuarios.empresa",
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name="perfilusuario",
                    name="empresa",
                    field=models.ForeignKey(
                        default=usuarios.tenancy.empresa_predeterminada_pruebas,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perfiles",
                        to="usuarios.empresa",
                    ),
                ),
            ],
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="perfilusuario",
                    name="sucursal",
                    field=models.ForeignKey(
                        blank=True,
                        default=usuarios.tenancy.sucursal_predeterminada_pruebas,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perfiles",
                        to="usuarios.sucursal",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="perfilusuario",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("alcance", "sucursal"), sucursal__isnull=False)
                    | models.Q(("alcance", "empresa"), sucursal__isnull=True)
                ),
                name="perfil_scope_coherente",
            ),
        ),
    ]
