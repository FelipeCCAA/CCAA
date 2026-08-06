from django.contrib import admin

from .models import CargaModulo, ParadaRuta, Recoleccion, RutaRecoleccion


@admin.register(RutaRecoleccion)
class RutaRecoleccionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "fecha", "vehiculo", "conductor", "estado")
    list_filter = ("estado", "fecha")
    search_fields = ("codigo", "vehiculo__placa")


admin.site.register(ParadaRuta)
admin.site.register(Recoleccion)
admin.site.register(CargaModulo)

