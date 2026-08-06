from django.contrib import admin

from .models import ValeEstandarizacion


@admin.register(ValeEstandarizacion)
class ValeEstandarizacionAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "fecha", "producto", "rc_objetivo", "rc_medido",
        "silo_destino", "estado",
    )
    list_filter = ("estado", "fecha", "producto")
    search_fields = ("codigo", "producto__nombre", "silo_destino__codigo")
    date_hierarchy = "fecha"
    autocomplete_fields = ("producto",)

    # El estado y el análisis los mueven las acciones del ciclo. Editables aquí
    # dejarían liberar un vale sin muestra, que es justo lo que el ciclo impide.
    readonly_fields = (
        "estado", "agitacion_desde", "grasa_real", "sng_real", "creado_en",
    )

    @admin.display(description="RC medido")
    def rc_medido(self, vale):
        rc = vale.rc_real

        return f"{rc:.4f}" if rc is not None else "—"
