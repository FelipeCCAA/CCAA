"""Permisos operacionales del dominio de procesos productivos."""

from rest_framework.permissions import SAFE_METHODS

from usuarios.models import PerfilUsuario, Rol, rol_de
from usuarios.permisos import EscribeProduccion
from usuarios.tenancy import filtrar_por_scope

from .models import (
    CorridaCondensacion,
    CorridaDescremacion,
    CorridaMantequilla,
    CorridaSecado,
    EjecucionProceso,
    EntradaProceso,
    EtapaProceso,
    SalidaProceso,
)


TIPOS_OPERABLES_POR_AREA = {
    PerfilUsuario.Area.CONDENSACION: {
        EtapaProceso.Tipo.ESTANDARIZACION,
        EtapaProceso.Tipo.DESCREMACION,
        EtapaProceso.Tipo.EVAPORACION,
        EtapaProceso.Tipo.CONDENSACION,
        EtapaProceso.Tipo.MANTEQUILLA,
        EtapaProceso.Tipo.TRANSFERENCIA,
    },
    PerfilUsuario.Area.SECADO: {EtapaProceso.Tipo.SECADO},
}


class OperaProcesoPorEtapa(EscribeProduccion):
    """Permite escribir solamente sobre las etapas operadas por el area."""

    message = "Tu area no puede operar esta etapa del proceso."

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in SAFE_METHODS or rol_de(request.user) == Rol.ADMIN:
            return True

        tipo = self._tipo_solicitado(request, view)
        if tipo is None:
            # Los IDs inexistentes o fuera del alcance deben llegar al
            # serializer/mixin para responder 400/404 sin convertir permisos
            # en un segundo sistema de validacion de datos.
            return True
        return self._puede_operar_tipo(request.user, tipo)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS or rol_de(request.user) == Rol.ADMIN:
            return True
        if getattr(view, "action", None) == "preparar_continuacion":
            tipo = self._tipo_de_etapa(request.data.get("etapa"))
        else:
            tipo = self._tipo_de_objeto(obj)
        return bool(tipo and self._puede_operar_tipo(request.user, tipo))

    @staticmethod
    def _puede_operar_tipo(usuario, tipo):
        perfil = getattr(usuario, "perfil", None)
        return bool(
            perfil and tipo in TIPOS_OPERABLES_POR_AREA.get(perfil.area, set())
        )

    def _tipo_solicitado(self, request, view):
        tipo_fijo = getattr(view, "tipo_etapa_operacional", None)
        if tipo_fijo:
            return tipo_fijo

        action = getattr(view, "action", None)
        modelo = getattr(view, "modelo_operacional", None) or getattr(
            getattr(view, "queryset", None), "model", None
        )
        if action == "preparar_continuacion":
            return self._tipo_de_etapa(request.data.get("etapa"))
        if action != "create":
            return None
        if modelo is EjecucionProceso:
            return self._tipo_de_etapa(request.data.get("etapa"))
        if modelo in {
            EntradaProceso,
            SalidaProceso,
            CorridaCondensacion,
            CorridaDescremacion,
            CorridaMantequilla,
            CorridaSecado,
        }:
            return self._tipo_de_ejecucion(request, request.data.get("ejecucion"))
        return None

    @staticmethod
    def _tipo_de_etapa(etapa_id):
        try:
            return EtapaProceso.objects.filter(pk=etapa_id).values_list(
                "tipo", flat=True
            ).first()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _tipo_de_ejecucion(request, ejecucion_id):
        try:
            queryset = filtrar_por_scope(
                EjecucionProceso.objects.all(),
                request.user,
                campo_sucursal="sucursal_id",
                campo_empresa="sucursal__empresa_id",
            )
            return queryset.filter(pk=ejecucion_id).values_list(
                "etapa__tipo", flat=True
            ).first()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _tipo_de_objeto(obj):
        if isinstance(obj, EjecucionProceso):
            return obj.etapa.tipo
        if isinstance(obj, (EntradaProceso, SalidaProceso)):
            return obj.ejecucion.etapa.tipo
        if isinstance(
            obj, (
                CorridaCondensacion, CorridaDescremacion,
                CorridaMantequilla, CorridaSecado,
            )
        ):
            return obj.ejecucion.etapa.tipo
        return None
