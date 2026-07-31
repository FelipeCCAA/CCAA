from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """
    Solo lectura, también aquí.

    Un registro de auditoría que se puede editar no prueba nada. Se deja
    consultable desde el admin, pero sin formulario de edición ni acción de
    borrado.
    """

    list_display = ["fecha_hora", "usuario_nombre", "accion", "etiqueta_modelo", "objeto_desc"]
    list_filter = ["accion", "modelo", "origen"]
    search_fields = ["usuario_nombre", "objeto_desc", "objeto_id"]
    date_hierarchy = "fecha_hora"
    readonly_fields = [f.name for f in RegistroAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
