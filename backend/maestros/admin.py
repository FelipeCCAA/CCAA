from django.contrib import admin

from .models import (
    DocumentoLiberacion,
    Equipo,
    Especificacion,
    Mandante,
    Producto,
    Receta,
    RecetaComponente,
    Silo,
    Vehiculo,
)


@admin.register(Mandante)
class MandanteAdmin(admin.ModelAdmin):
    list_display = ["nombre", "codigo_cliente", "activo"]
    list_filter = ["activo"]
    search_fields = ["nombre"]


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    """
    Alta de productos con el SKU generado desde sus atributos.

    El SKU es de solo lectura a propósito: se compone de catálogos y se
    recalcula al guardar. Dejarlo escribible invitaría a teclear un código
    que contradiga los atributos del mismo producto, que es exactamente el
    problema que trae el archivo de origen (`SKU_PRODUCTOS.md` §4.2).
    """

    list_display = [
        "nombre",
        "codigo",
        "mandante",
        "categoria",
        "tipo",
        "formato",
        "activo",
    ]
    list_filter = ["categoria", "formato", "familia", "naturaleza", "mandante", "activo"]
    search_fields = ["nombre", "codigo"]
    autocomplete_fields = ["mandante"]
    readonly_fields = ["codigo", "sku_explicado"]

    fieldsets = [
        (
            None,
            {"fields": ["nombre", "mandante", "familia", "naturaleza", "unidad_base", "activo"]},
        ),
        (
            "SKU",
            {
                "fields": [
                    "naturaleza_comercial",
                    "categoria",
                    "tipo",
                    "formato",
                    "mercado",
                    "variante",
                    "codigo",
                    "sku_explicado",
                ],
                "description": (
                    "El SKU se arma con estos atributos más el código de "
                    "cliente del mandante. Completa naturaleza, categoría, "
                    "tipo y formato, y se genera solo al guardar; si falta "
                    "alguno, el SKU queda como esté y el producto se guarda "
                    "igual."
                ),
            },
        ),
    ]

    @admin.display(description="Cómo se lee el SKU")
    def sku_explicado(self, obj):
        """
        Traduce el SKU guardado de vuelta a sus valores.

        Es la comprobación que faltaba en el archivo de origen: si lo que se
        lee no coincide con los atributos de arriba, el código está mal y se
        ve sin tener que descomponerlo a mano.
        """
        from .dominio import describir_sku

        if not obj or not obj.codigo:
            return "— (completa los atributos y guarda)"

        descripcion = describir_sku(obj.codigo)

        if descripcion is None:
            return f"{obj.codigo} · no tiene la forma de un SKU (código antiguo)"

        return " · ".join(f"{k}: {v}" for k, v in descripcion.items())


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    """
    Máquinas de la planta.

    `consume_leche` es una regla del balance, no una etiqueta: marcarlo en una
    línea que recibe lo que el evaporador ya produjo restaría la misma leche
    dos veces.
    """

    list_display = ["nombre", "codigo", "tipo", "consume_leche", "orden", "activo"]
    list_filter = ["tipo", "consume_leche", "activo"]
    list_editable = ["orden", "activo"]
    search_fields = ["nombre", "codigo"]


@admin.register(Silo)
class SiloAdmin(admin.ModelAdmin):
    # Sin columna de ocupación: es un saldo del libro de movimientos.
    list_display = ["codigo", "tipo", "capacidad_l", "activo"]
    list_filter = ["tipo", "activo"]
    search_fields = ["codigo"]


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ["placa", "numero", "transportista", "capacidad_l", "chofer_am", "chofer_pm", "activo"]
    list_filter = ["activo", "transportista"]
    search_fields = ["placa", "numero", "transportista", "chofer_am", "chofer_pm"]


@admin.register(Especificacion)
class EspecificacionAdmin(admin.ModelAdmin):
    list_display = ["producto", "version", "vigente_desde", "vigente_hasta", "fuente"]
    list_filter = ["producto__familia", "producto__mandante"]
    search_fields = ["producto__nombre", "fuente"]
    autocomplete_fields = ["producto"]


@admin.register(DocumentoLiberacion)
class DocumentoLiberacionAdmin(admin.ModelAdmin):
    """
    Es desde aquí que Calidad arma el checklist. Cambiar la plantilla de un
    documento cambia su formulario en la aplicación (MODELO_DATOS.md §2.6), sin
    desplegar nada: por eso esta pantalla es parte del producto y no una
    herramienta de mantenimiento.
    """

    list_display = [
        "orden",
        "nombre",
        "codigo",
        "area",
        "frecuencia",
        "aplica_a",
        "campos_en_plantilla",
        "activo",
    ]
    list_display_links = ["nombre"]
    # `frecuencia` se edita desde la lista porque decide dónde vive el
    # registro: cambiarla mueve el formulario entre el expediente del lote y
    # los registros de planta.
    list_editable = ["frecuencia"]
    list_filter = ["area", "frecuencia", "activo"]
    search_fields = ["nombre", "codigo", "fuente"]
    ordering = ["orden", "nombre"]

    @admin.display(description="Campos")
    def campos_en_plantilla(self, documento):
        """Una plantilla vacía es válida: el documento es solo una atestación."""
        total = len(documento.plantilla or [])
        return total or "solo atestación"


class RecetaComponenteInline(admin.TabularInline):
    """Los componentes se cargan desde su receta: así se lee un escandallo."""

    model = RecetaComponente
    extra = 1
    fields = ["producto", "cantidad", "unidad", "merma"]
    autocomplete_fields = ["producto"]


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ["producto", "version", "cantidad_base", "vigente_desde",
                    "vigente_hasta", "fuente"]
    list_filter = ["producto__familia", "producto__mandante"]
    search_fields = ["producto__nombre", "fuente"]
    autocomplete_fields = ["producto"]
    inlines = [RecetaComponenteInline]
