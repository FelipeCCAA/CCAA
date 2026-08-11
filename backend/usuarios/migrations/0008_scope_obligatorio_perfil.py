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
                "codigo": "TEST",
                "sucursal": "Sucursal aislada de pruebas",
            }
        else:
            datos = {
                "rut": os.getenv("CCAA_INITIAL_COMPANY_RUT", "").strip(),
                "empresa": os.getenv("CCAA_INITIAL_COMPANY_NAME", "").strip(),
                "codigo": os.getenv("CCAA_INITIAL_BRANCH_CODE", "").strip(),
                "sucursal": os.getenv("CCAA_INITIAL_BRANCH_NAME", "").strip(),
            }
            faltantes = [clave for clave, valor in datos.items() if not valor]
            if faltantes:
                raise RuntimeError(
                    "No existe una sucursal inicial. Configure "
                    "CCAA_INITIAL_COMPANY_RUT, CCAA_INITIAL_COMPANY_NAME, "
                    "CCAA_INITIAL_BRANCH_CODE y CCAA_INITIAL_BRANCH_NAME "
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
            perfil.alcance = "sucursal"
        elif perfil.empresa_id:
            candidatas = [s for s in todas if s.empresa_id == perfil.empresa_id]
            es_admin_empresa = (
                perfil.area == "administracion" and perfil.nivel == "admin"
            )
            if es_admin_empresa:
                perfil.alcance = "empresa"
            elif len(candidatas) == 1:
                perfil.sucursal_id = candidatas[0].pk
                perfil.alcance = "sucursal"
            else:
                raise RuntimeError(
                    f"PerfilUsuario {perfil.pk} no tiene una sucursal inequívoca. "
                    "Asigne empresa/sucursal antes de aplicar usuarios.0008."
                )
        elif len(todas) == 1:
            perfil.empresa_id = todas[0].empresa_id
            perfil.sucursal_id = todas[0].pk
            perfil.alcance = "sucursal"
        else:
            raise RuntimeError(
                f"PerfilUsuario {perfil.pk} no tiene tenant y existen "
                f"{len(todas)} sucursales. Asigne su scope antes de aplicar "
                "usuarios.0008."
            )
        perfil.save(update_fields=["empresa", "sucursal", "alcance"])


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
