"""Compatibilidad de persistencia para campos históricos de organización.

Empresa y Sucursal no son dimensiones funcionales de CCAA. Los nombres
``tenant`` se conservan para no romper imports ni migraciones antiguas, pero
no conceden permisos ni recortan el trabajo visible.
"""

from dataclasses import dataclass
import sys

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers


RUT_EMPRESA_PRUEBAS = "TENANT-TEST"
CODIGO_SUCURSAL_PRUEBAS = "TEST"

#: El código de la sucursal que siembra `usuarios.0008`, en sus dos ramas.
#:
#: La organización inicial se busca **por este código y no por su RUT**: el RUT
#: cambia con el entorno —`TENANT-TEST` bajo `DJANGO_ENV=test`, `TENANT-CI` en
#: el flujo de CI, y el de `CCAA_INITIAL_COMPANY_RUT` en cualquier otro caso—,
#: así que ninguna constante puede acertarle a los tres. El código de la
#: sucursal, en cambio, es literal en la migración y vale en las tres ramas.
#:
#: Antes se buscaba por `rut="RUT-LOCAL-DESARROLLO"`, un valor que **ningún
#: camino del código escribe**. La búsqueda no acertaba nunca, así que los
#: `default` creaban una segunda organización y los maestros sembrados
#: quedaban fuera del alcance de todo perfil de pruebas. Ver
#: `tests_tenant_sembrado.py`.
CODIGO_SUCURSAL_INICIAL = "INTERNA"


def _en_pruebas() -> bool:
    return settings.DJANGO_ENV in {"test", "ci"} or "test" in sys.argv


def _es_construccion_inicial_de_pruebas() -> bool:
    """Evita crear el tenant auxiliar antes de que la migración 0008 siembre el real."""
    if "test" not in sys.argv:
        return False
    try:
        from django.db.migrations.recorder import MigrationRecorder

        return not MigrationRecorder.Migration.objects.filter(
            app="usuarios", name="0008_scope_obligatorio_perfil"
        ).exists()
    except Exception:  # La tabla de migraciones aún puede no existir.
        return True


def empresa_predeterminada_pruebas():
    """
    El tenant de pruebas, y **nada** fuera de ellas.

    Estas dos funciones son el `default` de dos docenas de campos. Antes
    lanzaban `ImproperlyConfigured` fuera de pruebas, para dejar claro que no
    existe un tenant por omisión. La intención era buena y el mecanismo no:
    Django pide el `default` de cada campo al construir un modelo vacío, así
    que **la página «Añadir» del admin reventaba en 22 modelos** —perfiles,
    lotes, recepciones, equipos, silos— con un error de configuración que no
    decía nada al que lo veía.

    Devolver `None` conserva la garantía y pierde el ruido: no se inventa
    ningún tenant, y como el campo es obligatorio en el esquema, el formulario
    lo pide y `clean()` lo rechaza si falta. Quien olvide indicarlo se lleva un
    «este campo es obligatorio», que es el reproche correcto, en el sitio
    correcto y sin tumbar la página.

    El nombre sigue diciendo `_pruebas` porque eso es exactamente lo que hace:
    fuera de pruebas no hay valor predeterminado. Las migraciones lo referencian
    por ese nombre, así que no se renombra a la ligera.
    """
    if not _en_pruebas():
        return None

    from .models import Empresa

    inicial = (
        Empresa.objects.filter(
            sucursales__codigo=CODIGO_SUCURSAL_INICIAL, activa=True
        )
        .order_by("pk")
        .first()
    )
    if inicial is not None:
        return inicial
    if _es_construccion_inicial_de_pruebas():
        # Durante la construcción de la base de pruebas aún no corrió la
        # migración que siembra la empresa local. Crear aquí un segundo tenant
        # lo dejaría contando como otra planta durante toda la suite.
        return None

    empresa, _ = Empresa.objects.get_or_create(
        rut=RUT_EMPRESA_PRUEBAS,
        defaults={"nombre": "Empresa aislada de pruebas"},
    )
    # El objeto, no su `pk`. Django admite ambos en el `default` de una FK y los
    # normaliza, pero **DRF copia este mismo callable al serializer**: con el
    # `pk` a secas, `validated_data["empresa"]` llegaba como entero y guardar
    # reventaba con «Cannot assign "1": debe ser una instancia de Empresa».
    return empresa


def sucursal_predeterminada_pruebas():
    if not _en_pruebas():
        return None

    from .models import Empresa, Sucursal

    inicial = Sucursal.objects.filter(
        codigo=CODIGO_SUCURSAL_INICIAL, activa=True,
    ).order_by("pk").first()
    if inicial is not None:
        return inicial
    if _es_construccion_inicial_de_pruebas():
        return None

    empresa, _ = Empresa.objects.get_or_create(
        rut=RUT_EMPRESA_PRUEBAS,
        defaults={"nombre": "Empresa aislada de pruebas"},
    )
    sucursal, _ = Sucursal.objects.get_or_create(
        empresa=empresa,
        codigo=CODIGO_SUCURSAL_PRUEBAS,
        defaults={"nombre": "Configuración interna de pruebas"},
    )
    return sucursal


@dataclass(frozen=True, slots=True)
class ScopeUsuario:
    empresa_id: int | None
    sucursal_id: int | None
    es_global: bool = False

    @property
    def es_empresa(self) -> bool:
        return not self.es_global and self.empresa_id is not None and self.sucursal_id is None

    @property
    def es_sucursal(self) -> bool:
        return not self.es_global and self.sucursal_id is not None

    def permite_empresa(self, empresa_id: int | None) -> bool:
        return self.es_global or (
            self.empresa_id is not None and empresa_id == self.empresa_id
        )

    def permite_sucursal(
        self, sucursal_id: int | None, empresa_id: int | None = None
    ) -> bool:
        if self.es_global:
            return True
        if sucursal_id is None:
            return False
        if self.es_sucursal:
            return sucursal_id == self.sucursal_id
        return self.es_empresa and empresa_id == self.empresa_id


def scope_de(usuario, *, requerido: bool = False) -> ScopeUsuario | None:
    if usuario and usuario.is_authenticated and usuario.is_superuser:
        return ScopeUsuario(None, None, es_global=True)

    perfil = getattr(usuario, "perfil", None)
    scope = None
    if perfil and not perfil.empresa_id and _en_pruebas():
        # Compatibilidad con pruebas históricas anteriores al multi-tenant:
        # sus objetos pertenecen a distintos tenants sembrados por migraciones
        # y sus perfiles no lo declaraban. Solo en test/CI se preserva ese
        # comportamiento global; en producción un perfil incompleto no ve nada.
        scope = ScopeUsuario(None, None, es_global=True)
    if perfil and perfil.empresa_id:
        if perfil.alcance == perfil.Alcance.EMPRESA:
            scope = ScopeUsuario(perfil.empresa_id, None)
        elif perfil.sucursal_id:
            scope = ScopeUsuario(perfil.empresa_id, perfil.sucursal_id)

    if requerido and scope is None:
        raise PermissionDenied(
            "Tu cuenta no tiene una organización válida. "
            "Solicita a Administración que complete el perfil."
        )
    return scope


def filtrar_por_scope(
    queryset,
    usuario,
    *,
    campo_sucursal: str | None = None,
    campo_empresa: str | None = None,
):
    """Adaptador legado: autentica, pero nunca aísla por Empresa/Sucursal."""
    if not (usuario and usuario.is_authenticated):
        return queryset.none()
    return queryset


def exigir_sucursal_permitida(usuario, sucursal) -> None:
    """Nombre legado; la autorización se decide por área, rol y relación real."""
    if not (usuario and usuario.is_authenticated):
        raise PermissionDenied("Debes iniciar sesión para realizar esta operación.")


def unica_empresa_activa():
    """
    Registro técnico canónico para completar claves históricas obligatorias.

    La elección nunca depende del usuario ni concede alcance. Se prefiere la
    empresa asociada al registro interno sembrado y, si no existe, la primera
    activa de forma determinista.
    """
    from .models import Empresa

    empresa = (
        Empresa.objects.filter(
            activa=True, sucursales__codigo=CODIGO_SUCURSAL_INICIAL
        )
        .order_by("pk")
        .first()
        or Empresa.objects.filter(activa=True).order_by("pk").first()
    )
    if empresa is None and _en_pruebas():
        return empresa_predeterminada_pruebas()
    return empresa


def unica_sucursal_activa(empresa_id: int | None):
    """Registro interno canónico; nunca se ofrece como opción de negocio."""
    from .models import Sucursal

    consulta = Sucursal.objects.filter(activa=True)

    if empresa_id is not None:
        consulta = consulta.filter(empresa_id=empresa_id)

    return consulta.order_by("pk").first()


def sucursal_para_escritura(usuario, validated_data, campo: str = "sucursal"):
    """
    Resuelve el registro técnico de partición sin aceptar una selección del cliente.

    Existe solo para completar claves foráneas históricas. No consulta el
    perfil del actor, no concede acceso y no acepta una selección funcional.
    """
    if not (usuario and usuario.is_authenticated):
        raise PermissionDenied("Debes iniciar sesión para realizar esta operación.")
    interna = unica_sucursal_activa(None)
    if interna is None:
        raise serializers.ValidationError({
            campo: "Falta la configuración interna de la organización."
        })
    return interna


class QuerysetTenantMixin:
    """Compatibilidad: ya no recorta querysets por Empresa/Sucursal."""

    tenant_lookup_sucursal: str | None = None
    tenant_lookup_empresa: str | None = None

    def get_queryset(self):
        queryset = super().get_queryset()
        return filtrar_por_scope(
            queryset,
            self.request.user,
            campo_sucursal=self.tenant_lookup_sucursal,
            campo_empresa=self.tenant_lookup_empresa,
        )


class RelacionesTenantMixin:
    """Compatibilidad: conserva contratos sin filtrar relaciones por tenant."""

    tenant_relation_fields: dict[str, tuple[str | None, str | None]] = {}

    def get_serializer(self, *args, **kwargs):
        serializer = super().get_serializer(*args, **kwargs)
        objetivo = getattr(serializer, "child", serializer)
        for nombre, (campo_sucursal, campo_empresa) in self.tenant_relation_fields.items():
            campo = objetivo.fields.get(nombre)
            if campo is None or getattr(campo, "queryset", None) is None:
                continue
            campo.queryset = filtrar_por_scope(
                campo.queryset,
                self.request.user,
                campo_sucursal=campo_sucursal,
                campo_empresa=campo_empresa,
            )
        return serializer


class EmpresaTenantViewSetMixin(QuerysetTenantMixin):
    tenant_write_field = "empresa"

    def perform_create(self, serializer):
        # Algunos serializers históricos aún aportan un default técnico. Se
        # acepta solo como compatibilidad de persistencia, nunca desde el
        # perfil del usuario ni como selector de alcance.
        empresa = (
            serializer.validated_data.get(self.tenant_write_field)
            or unica_empresa_activa()
        )
        if empresa is None:
            raise serializers.ValidationError({
                self.tenant_write_field: (
                    "Falta la configuración técnica histórica requerida."
                )
            })

        serializer.save(**{self.tenant_write_field: empresa})

    def perform_update(self, serializer):
        if self.tenant_write_field in self.request.data:
            raise PermissionDenied(
                "La configuración histórica no forma parte de esta edición."
            )
        serializer.save()


class SucursalTenantViewSetMixin(QuerysetTenantMixin):
    tenant_write_field = "sucursal"

    def perform_create(self, serializer):
        sucursal = sucursal_para_escritura(
            self.request.user, serializer.validated_data, self.tenant_write_field
        )
        serializer.save(**{self.tenant_write_field: sucursal})

    def perform_update(self, serializer):
        if self.tenant_write_field in self.request.data:
            raise PermissionDenied(
                "La organización interna no se cambia mediante una edición genérica."
            )
        serializer.save()
