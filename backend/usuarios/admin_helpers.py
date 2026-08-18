from .tenancy import sucursal_para_escritura


class OrganizacionInternaAdminMixin:
    """Completa la FK técnica sin mostrar una entidad que ya no es del negocio."""

    def save_model(self, request, obj, form, change):
        if hasattr(obj, "sucursal_id") and not obj.sucursal_id:
            obj.sucursal = sucursal_para_escritura(request.user, {})
        super().save_model(request, obj, form, change)
