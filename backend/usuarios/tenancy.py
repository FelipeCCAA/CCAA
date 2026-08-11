"""Scope de empresa/sucursal, separado de los permisos por rol."""

from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import PermissionDenied
from rest_framework import serializers


RUT_EMPRESA_PRUEBAS = "TENANT-TEST"
CODIGO_SUCURSAL_PRUEBAS = "TEST"


def _exigir_entorno_pruebas() -> None:
    if settings.DJANGO_ENV not in {"test", "ci"}:
        raise ImproperlyConfigured(
            "Empresa y sucursal son obligatorias. Deben obtenerse del actor "
            "autenticado o indicarse explícitamente; no existe tenant por defecto."
        )


def empresa_predeterminada_pruebas():
    """Default exclusivo de tests para no introducir fallbacks productivos."""
    _exigir_entorno_pruebas()
    from .models import Empresa

    empresa, _ = Empresa.objects.get_or_create(
        rut=RUT_EMPRESA_PRUEBAS,
        defaults={"nombre": "Empresa aislada de pruebas"},
    )
    return empresa.pk


def sucursal_predeterminada_pruebas():
    _exigir_entorno_pruebas()
    from .models import Empresa, Sucursal

    empresa, _ = Empresa.objects.get_or_create(
        rut=RUT_EMPRESA_PRUEBAS,
        defaults={"nombre": "Empresa aislada de pruebas"},
    )
    sucursal, _ = Sucursal.objects.get_or_create(
        empresa=empresa,
        codigo=CODIGO_SUCURSAL_PRUEBAS,
        defaults={"nombre": "Sucursal aislada de pruebas"},
    )
    return sucursal.pk


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
    if perfil and perfil.empresa_id:
        if perfil.alcance == perfil.Alcance.EMPRESA:
            scope = ScopeUsuario(perfil.empresa_id, None)
        elif perfil.sucursal_id:
            scope = ScopeUsuario(perfil.empresa_id, perfil.sucursal_id)

    if requerido and scope is None:
        raise PermissionDenied(
            "Tu cuenta no tiene un alcance de empresa/sucursal válido. "
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
    """Filtra un queryset; fuera del scope se comporta como objeto inexistente."""
    scope = scope_de(usuario)
    if scope is None:
        return queryset.none()
    if scope.es_global:
        return queryset
    if scope.es_sucursal and campo_sucursal:
        return queryset.filter(**{campo_sucursal: scope.sucursal_id})
    if campo_empresa:
        return queryset.filter(**{campo_empresa: scope.empresa_id})
    raise ImproperlyConfigured(
        "El queryset tenant no declaró un camino de empresa compatible con "
        "usuarios de alcance empresarial."
    )


def exigir_sucursal_permitida(usuario, sucursal) -> None:
    scope = scope_de(usuario, requerido=True)
    if not scope.permite_sucursal(sucursal.pk, sucursal.empresa_id):
        raise PermissionDenied("La sucursal indicada está fuera de tu alcance.")


def unica_sucursal_activa(empresa_id: int | None):
    """
    La única sucursal activa, o `None` si hay cero o varias.

    Devolver `None` cuando hay varias es lo que hace segura la resolución
    automática: con dos plantas, elegir una por el operador sería escribir en
    la equivocada sin que nadie lo pida.

    `empresa_id` en `None` mira todas: es el caso del superusuario, que no está
    acotado a ninguna.
    """
    from .models import Sucursal

    consulta = Sucursal.objects.filter(activa=True)

    if empresa_id is not None:
        consulta = consulta.filter(empresa_id=empresa_id)

    candidatas = list(consulta.order_by("pk")[:2])

    return candidatas[0] if len(candidatas) == 1 else None


def sucursal_para_escritura(usuario, validated_data, campo: str = "sucursal"):
    """
    Resuelve la sucursal sin confiar en un tenant enviado por el cliente.

    **La organización de CCAA no tiene sucursales**: hay una sola planta. El
    modelo conserva la dimensión porque quitarla costaría migrar quince modelos
    con datos encima, y volvería a costar lo mismo el día que haya una segunda.
    Lo que sí se hace es que nadie tenga que verla.

    Por eso la resolución automática cubre también a los perfiles de **alcance
    empresa** —los de Administración— y no solo al superusuario. Sin esto, un
    administrador recibía «Debes indicar una sucursal permitida» sobre un
    concepto que en su organización no existe, y no podía crear nada.

    En cuanto haya dos plantas la ambigüedad vuelve, y entonces sí hay que
    indicarla: es la diferencia entre resolver lo que solo tiene una respuesta
    y adivinar entre dos.
    """
    scope = scope_de(usuario, requerido=True)

    if scope.es_sucursal:
        from .models import Sucursal

        return Sucursal.objects.get(pk=scope.sucursal_id)

    sucursal = validated_data.get(campo)

    if sucursal is None:
        # El superusuario no está acotado a una empresa; el de alcance empresa
        # solo puede caer en la suya.
        unica = unica_sucursal_activa(None if scope.es_global else scope.empresa_id)

        if unica is not None:
            return unica

        raise serializers.ValidationError({
            campo: (
                "Hay más de una planta activa: indica en cuál se registra. "
                "Con una sola, el sistema la resuelve solo."
            )
        })

    exigir_sucursal_permitida(usuario, sucursal)

    return sucursal


class QuerysetTenantMixin:
    """Aplica 404 fuera del scope a list/retrieve/update/delete/actions."""

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
    """Restringe PK relacionadas recibidas por serializers de un ViewSet."""

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
        scope = scope_de(self.request.user, requerido=True)
        if scope.es_global:
            empresa = serializer.validated_data.get(self.tenant_write_field)
            if empresa is None:
                raise serializers.ValidationError(
                    {self.tenant_write_field: "Un superusuario debe indicar la empresa."}
                )
            serializer.save()
            return
        from .models import Empresa

        serializer.save(
            **{self.tenant_write_field: Empresa.objects.get(pk=scope.empresa_id)}
        )

    def perform_update(self, serializer):
        if self.tenant_write_field in self.request.data:
            raise PermissionDenied(
                "El tenant no se cambia mediante una edición genérica."
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
                "La sucursal no se cambia mediante una edición genérica."
            )
        serializer.save()
