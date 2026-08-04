from decimal import Decimal
from math import sqrt

from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from usuarios.models import PerfilUsuario


class Insumo(models.Model):
    class Categoria(models.TextChoices):
        MATERIA_PRIMA = "materia_prima", "Materia prima"
        EMPAQUE = "empaque", "Material de empaque"
        PRODUCCION = "produccion", "Insumo de producción"
        QUIMICO = "quimico", "Producto químico"
        REPUESTO = "repuesto", "Repuesto"
        LIMPIEZA = "limpieza", "Artículo de limpieza"
        SEGURIDAD = "seguridad", "Elemento de seguridad"
        OTRO = "otro", "Otro"

    class Unidad(models.TextChoices):
        KG = "kg", "Kilogramos"
        L = "L", "Litros"
        UN = "un", "Unidades"

    codigo = models.CharField(max_length=40, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    codigo_barras = models.CharField(max_length=80, blank=True, db_index=True)
    categoria = models.CharField(max_length=30, choices=Categoria.choices, default=Categoria.OTRO)
    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    unidad = models.CharField(max_length=5, choices=Unidad.choices)
    contenido_envase = models.DecimalField(max_digits=12, decimal_places=3, default=1)
    requiere_lote = models.BooleanField(default=True)
    requiere_vencimiento = models.BooleanField(default=False)
    requiere_calidad = models.BooleanField(default=False)
    requiere_certificado = models.BooleanField(default=False)
    requiere_temperatura = models.BooleanField(default=False)
    vida_util_dias = models.PositiveIntegerField(default=0)
    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_maximo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    # No hay `stock_actual`. El saldo se calcula desde `Existencia`, que a su
    # vez solo cambia junto a un `MovimientoInventario` — un número guardado
    # al lado, editable y sin movimiento que lo respalde, se desincroniza y
    # además parece autorizado. Los que sí se guardan son los **parámetros**
    # (mínimo, máximo, seguridad): esos los decide alguien, no se deducen.
    stock_seguridad = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    demanda_anual = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    costo_por_pedido = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    costo_mantencion_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    plazo_reposicion_dias = models.PositiveIntegerField(default=0)
    consumo_diario = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["area", "nombre"]

    @property
    def eoq(self):
        if self.demanda_anual <= 0 or self.costo_por_pedido <= 0 or self.costo_mantencion_unitario <= 0:
            return None
        return Decimal(str(sqrt(float(2 * self.demanda_anual * self.costo_por_pedido / self.costo_mantencion_unitario))))

    @property
    def punto_reposicion(self):
        return self.consumo_diario * self.plazo_reposicion_dias + self.stock_seguridad

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class ConsumoLoteProduccion(models.Model):
    """Cabecera auditable del descuento automático de una receta."""
    lote_produccion = models.OneToOneField(
        "produccion.Lote", on_delete=models.PROTECT, related_name="consumo_inventario"
    )
    kg_base = models.DecimalField(max_digits=14, decimal_places=3)
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    registrado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Consumo {self.lote_produccion}"


class CicloCIP(models.Model):
    class Estado(models.TextChoices):
        PROGRAMADO = "programado", "Programado"
        EN_CURSO = "en_curso", "En curso"
        COMPLETADO = "completado", "Completado"
        OBSERVADO = "observado", "Observado"

    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    # Referencia al maestro y no texto libre: un CIP es la limpieza de una
    # máquina concreta, y con el nombre escrito a mano no hay forma de saber
    # si la torre quedó aseada o si alguien escribió «Egron 1» donde el resto
    # del sistema dice «E1».
    equipo = models.ForeignKey(
        "maestros.Equipo",
        on_delete=models.PROTECT,
        related_name="ciclos_cip",
        null=True,
        blank=True,
    )
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROGRAMADO)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-inicio"]


class Proveedor(models.Model):
    rut = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=160)
    email = models.EmailField(blank=True)
    telefono = models.CharField(max_length=40, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class InsumoProveedor(models.Model):
    insumo = models.ForeignKey(Insumo, on_delete=models.CASCADE, related_name="proveedores")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="insumos")
    principal = models.BooleanField(default=False)
    codigo_proveedor = models.CharField(max_length=80, blank=True)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    compra_minima = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    multiplo_compra = models.DecimalField(max_digits=14, decimal_places=3, default=1)
    lead_time_dias = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["insumo", "proveedor"], name="insumo_proveedor_unico")]


class Bodega(models.Model):
    sucursal = models.ForeignKey(
        "usuarios.Sucursal", on_delete=models.PROTECT, related_name="bodegas",
        null=True, blank=True,
    )
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=120)
    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices, default=PerfilUsuario.Area.BODEGA)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Ubicacion(models.Model):
    class Tipo(models.TextChoices):
        DISPONIBLE = "disponible", "Disponible"
        CUARENTENA = "cuarentena", "Cuarentena"
        RECHAZADO = "rechazado", "Rechazado"
        PRODUCCION = "produccion", "Producción"

    bodega = models.ForeignKey(Bodega, on_delete=models.PROTECT, related_name="ubicaciones")
    codigo = models.CharField(max_length=60)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.DISPONIBLE)
    descripcion = models.CharField(max_length=180, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["bodega", "codigo"], name="ubicacion_unica_bodega")]

    def __str__(self):
        return f"{self.bodega.codigo}/{self.codigo}"


class LoteInventario(models.Model):
    class EstadoCalidad(models.TextChoices):
        NO_REQUIERE = "no_requiere", "No requiere inspección"
        PENDIENTE = "pendiente", "Pendiente de inspección"
        MUESTRA = "muestra", "Muestra tomada"
        ANALISIS = "analisis", "En análisis"
        APROBADO = "aprobado", "Aprobado"
        OBSERVADO = "observado", "Aprobado con observaciones"
        BLOQUEADO = "bloqueado", "Bloqueado"
        RECHAZADO = "rechazado", "Rechazado"

    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, related_name="lotes")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="lotes", null=True, blank=True)
    codigo = models.CharField(max_length=100)
    elaboracion = models.DateField(null=True, blank=True)
    vencimiento = models.DateField(null=True, blank=True)
    estado_calidad = models.CharField(max_length=20, choices=EstadoCalidad.choices)
    recibido_en = models.DateTimeField(default=timezone.now)
    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["insumo", "codigo", "proveedor"], name="lote_inventario_unico")]
        ordering = ["vencimiento", "recibido_en"]

    @property
    def vencido(self):
        return bool(self.vencimiento and self.vencimiento < timezone.localdate())

    @property
    def utilizable(self):
        return self.activo and not self.vencido and self.estado_calidad in {
            self.EstadoCalidad.NO_REQUIERE, self.EstadoCalidad.APROBADO,
            self.EstadoCalidad.OBSERVADO,
        }


class Existencia(models.Model):
    lote = models.ForeignKey(LoteInventario, on_delete=models.PROTECT, related_name="existencias")
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="existencias")
    cantidad_fisica = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    cantidad_reservada = models.DecimalField(max_digits=16, decimal_places=3, default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["lote", "ubicacion"], name="existencia_unica_lote_ubicacion"),
            models.CheckConstraint(condition=models.Q(cantidad_fisica__gte=0), name="existencia_fisica_no_negativa"),
            models.CheckConstraint(condition=models.Q(cantidad_reservada__gte=0), name="existencia_reservada_no_negativa"),
            models.CheckConstraint(condition=models.Q(cantidad_reservada__lte=models.F("cantidad_fisica")), name="reserva_no_supera_fisico"),
        ]

    @property
    def cantidad_disponible(self):
        if not self.lote.utilizable or self.ubicacion.tipo != Ubicacion.Tipo.DISPONIBLE:
            return Decimal("0")
        return self.cantidad_fisica - self.cantidad_reservada


class MovimientoInventario(models.Model):
    class Tipo(models.TextChoices):
        RECEPCION = "recepcion", "Recepción"
        LIBERACION = "liberacion", "Liberación de Calidad"
        BLOQUEO = "bloqueo", "Bloqueo"
        RECHAZO = "rechazo", "Rechazo"
        TRASLADO = "traslado", "Traslado"
        RESERVA = "reserva", "Reserva"
        LIBERAR_RESERVA = "liberar_reserva", "Liberación de reserva"
        ENTREGA = "entrega", "Entrega a Producción"
        SALIDA = "salida", "Salida de Bodega"
        CONSUMO = "consumo", "Consumo de material"
        DEVOLUCION = "devolucion", "Devolución desde Producción"
        AJUSTE_POSITIVO = "ajuste_positivo", "Ajuste positivo"
        AJUSTE_NEGATIVO = "ajuste_negativo", "Ajuste negativo"
        MERMA = "merma", "Merma"

    tipo = models.CharField(max_length=25, choices=Tipo.choices)
    lote = models.ForeignKey(LoteInventario, on_delete=models.PROTECT, related_name="movimientos")
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    origen = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="movimientos_salida", null=True, blank=True)
    destino = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name="movimientos_entrada", null=True, blank=True)
    documento_tipo = models.CharField(max_length=80)
    documento_id = models.PositiveBigIntegerField()
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField(blank=True)
    saldo_anterior = models.DecimalField(max_digits=16, decimal_places=3)
    saldo_posterior = models.DecimalField(max_digits=16, decimal_places=3)

    class Meta:
        ordering = ["-fecha", "-id"]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor que cero."})
        if self.tipo in {self.Tipo.AJUSTE_POSITIVO, self.Tipo.AJUSTE_NEGATIVO, self.Tipo.MERMA} and not self.motivo.strip():
            raise ValidationError({"motivo": "El ajuste o merma exige un motivo."})

    def delete(self, *args, **kwargs):
        raise ValidationError("Los movimientos de inventario son inmutables.")


class SolicitudCompra(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADA = "enviada", "Enviada"
        PENDIENTE = "pendiente", "Pendiente de aprobación"
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"
        CONVERTIDA = "convertida", "Convertida en orden de compra"
        CANCELADA = "cancelada", "Cancelada"

    numero = models.CharField(max_length=30, unique=True)
    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes_compra")
    motivo = models.TextField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    creada_en = models.DateTimeField(auto_now_add=True)


class Aprobacion(models.Model):
    class Decision(models.TextChoices):
        APROBADA = "aprobada", "Aprobada"
        RECHAZADA = "rechazada", "Rechazada"

    documento_tipo = models.CharField(max_length=80)
    documento_id = models.PositiveBigIntegerField()
    etapa = models.CharField(max_length=80, default="jefatura")
    aprobador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=20, choices=Decision.choices)
    comentario = models.TextField(blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["documento_tipo", "documento_id", "etapa"],
                name="aprobacion_unica_por_etapa",
            )
        ]

    def delete(self, *args, **kwargs):
        raise ValidationError("El historial de aprobaciones es inmutable.")


class DetalleSolicitudCompra(models.Model):
    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    fecha_requerida = models.DateField()
    origen_mrp = models.BooleanField(default=False)


class OrdenCompra(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        APROBADA = "aprobada", "Aprobada"
        ENVIADA = "enviada", "Enviada"
        PARCIAL = "parcial", "Recibida parcialmente"
        RECIBIDA = "recibida", "Recibida"
        CERRADA = "cerrada", "Cerrada"
        CANCELADA = "cancelada", "Cancelada"

    numero = models.CharField(max_length=30, unique=True)
    solicitud = models.ForeignKey(SolicitudCompra, on_delete=models.PROTECT, related_name="ordenes", null=True, blank=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="ordenes")
    bodega_entrega = models.ForeignKey(Bodega, on_delete=models.PROTECT)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    creada_en = models.DateTimeField(auto_now_add=True)
    fecha_comprometida = models.DateField(null=True, blank=True)


class DetalleOrdenCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=14, decimal_places=2)
    cantidad_recibida = models.DecimalField(max_digits=16, decimal_places=3, default=0)


class RecepcionCompra(models.Model):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name="recepciones")
    guia = models.CharField(max_length=80)
    factura = models.CharField(max_length=80, blank=True)
    recibida_en = models.DateTimeField(default=timezone.now)
    receptor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    observaciones = models.TextField(blank=True)


class DetalleRecepcionCompra(models.Model):
    recepcion = models.ForeignKey(RecepcionCompra, on_delete=models.CASCADE, related_name="detalles")
    detalle_orden = models.ForeignKey(DetalleOrdenCompra, on_delete=models.PROTECT, related_name="recepciones")
    lote = models.OneToOneField(LoteInventario, on_delete=models.PROTECT, related_name="detalle_recepcion")
    ubicacion_temporal = models.ForeignKey(Ubicacion, on_delete=models.PROTECT)
    cantidad_recibida = models.DecimalField(max_digits=16, decimal_places=3)
    cantidad_danada = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    temperatura = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    embalaje_conforme = models.BooleanField(default=True)
    certificado_recibido = models.BooleanField(default=False)


class InspeccionMaterial(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        MUESTRA = "muestra", "Muestra tomada"
        ANALISIS = "analisis", "En análisis"
        APROBADA = "aprobada", "Aprobada"
        OBSERVADA = "observada", "Aprobada con observaciones"
        RECHAZADA = "rechazada", "Rechazada"
        BLOQUEADA = "bloqueada", "Bloqueada"

    lote = models.OneToOneField(LoteInventario, on_delete=models.PROTECT, related_name="inspeccion")
    plantilla = models.ForeignKey("PlantillaInspeccion", on_delete=models.PROTECT, null=True, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    prioridad = models.PositiveSmallIntegerField(default=3)
    responsable = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="inspecciones_material")
    resultados = models.JSONField(default=dict, blank=True)
    observaciones = models.TextField(blank=True)
    decidida_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)


class PlantillaInspeccion(models.Model):
    nombre = models.CharField(max_length=160)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, null=True, blank=True, related_name="plantillas_inspeccion")
    categoria = models.CharField(max_length=30, choices=Insumo.Categoria.choices, blank=True)
    version = models.PositiveIntegerField(default=1)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)
    campos = models.JSONField(default=list, help_text="Campos configurables y sus límites")
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["nombre", "version"], name="plantilla_inspeccion_version_unica")]

    def clean(self):
        if not self.insumo_id and not self.categoria:
            raise ValidationError("La plantilla debe aplicar a un insumo o categoría.")
        if not isinstance(self.campos, list):
            raise ValidationError({"campos": "Debe ser una lista de campos."})


class NoConformidadMaterial(models.Model):
    class Destino(models.TextChoices):
        DEVOLUCION = "devolucion", "Devolución al proveedor"
        DESTRUCCION = "destruccion", "Destrucción"
        REINSPECCION = "reinspeccion", "Reinspección"
        REPROCESO = "reproceso", "Reproceso"
        EXCEPCIONAL = "excepcional", "Liberación excepcional"

    inspeccion = models.ForeignKey(InspeccionMaterial, on_delete=models.PROTECT, related_name="no_conformidades")
    descripcion = models.TextField()
    destino = models.CharField(max_length=20, choices=Destino.choices)
    cerrada = models.BooleanField(default=False)
    creada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creada_en = models.DateTimeField(auto_now_add=True)


class LiberacionExcepcionalMaterial(models.Model):
    lote = models.ForeignKey(LoteInventario, on_delete=models.PROTECT, related_name="liberaciones_excepcionales")
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    uso_especifico = models.TextField()
    justificacion = models.TextField()
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="excepciones_solicitadas")
    aprobada_calidad_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="excepciones_calidad")
    aprobada_jefatura_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="excepciones_jefatura", null=True, blank=True)
    autorizada_en = models.DateTimeField(auto_now_add=True)
    vence_en = models.DateTimeField()
    activa = models.BooleanField(default=True)

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError({"cantidad": "Debe ser mayor que cero."})
        if not self.justificacion.strip() or not self.uso_especifico.strip():
            raise ValidationError("La justificación y el uso específico son obligatorios.")


class Adjunto(models.Model):
    documento_tipo = models.CharField(max_length=80)
    documento_id = models.PositiveBigIntegerField()
    tipo = models.CharField(max_length=40)
    archivo = models.FileField(upload_to="abastecimiento/%Y/%m/")
    hash_sha256 = models.CharField(max_length=64, blank=True)
    autor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)


class SolicitudMaterial(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        ENVIADA = "enviada", "Enviada"
        APROBADA = "aprobada", "Aprobada"
        PREPARANDO = "preparando", "En preparación"
        PREPARADA = "preparada", "Preparada"
        PARCIAL = "parcial", "Entrega parcial"
        ENTREGADA = "entregada", "Entregada"
        RECHAZADA = "rechazada", "Rechazada"
        CANCELADA = "cancelada", "Cancelada"

    numero = models.CharField(max_length=30, unique=True)
    area = models.CharField(max_length=30, choices=PerfilUsuario.Area.choices)
    lote_produccion = models.ForeignKey("produccion.Lote", on_delete=models.PROTECT, null=True, blank=True, related_name="solicitudes_material")
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mrq_solicitadas")
    fecha_requerida = models.DateField()
    prioridad = models.PositiveSmallIntegerField(default=3)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.BORRADOR)
    observaciones = models.TextField(blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)


class DetalleSolicitudMaterial(models.Model):
    solicitud = models.ForeignKey(SolicitudMaterial, on_delete=models.CASCADE, related_name="detalles")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    cantidad_solicitada = models.DecimalField(max_digits=16, decimal_places=3)
    cantidad_aprobada = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    cantidad_entregada = models.DecimalField(max_digits=16, decimal_places=3, default=0)


class ReservaInventario(models.Model):
    detalle = models.ForeignKey(DetalleSolicitudMaterial, on_delete=models.PROTECT, related_name="reservas")
    existencia = models.ForeignKey(Existencia, on_delete=models.PROTECT, related_name="reservas")
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)


class EntregaProduccion(models.Model):
    solicitud = models.ForeignKey(SolicitudMaterial, on_delete=models.PROTECT, related_name="entregas")
    entregada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="entregas_realizadas")
    recibida_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="entregas_recibidas")
    fecha = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)


class DetalleEntregaProduccion(models.Model):
    entrega = models.ForeignKey(EntregaProduccion, on_delete=models.PROTECT, related_name="detalles")
    detalle_solicitud = models.ForeignKey(DetalleSolicitudMaterial, on_delete=models.PROTECT)
    lote = models.ForeignKey(LoteInventario, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)


class AjusteInventario(models.Model):
    class Tipo(models.TextChoices):
        POSITIVO = "positivo", "Ajuste positivo"
        NEGATIVO = "negativo", "Ajuste negativo"
        MERMA = "merma", "Merma"

    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente de aprobación"
        APROBADO = "aprobado", "Aprobado"
        APLICADO = "aplicado", "Aplicado"
        RECHAZADO = "rechazado", "Rechazado"

    existencia = models.ForeignKey(Existencia, on_delete=models.PROTECT, related_name="ajustes")
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    motivo = models.TextField()
    solicitante = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ajustes_solicitados")
    aprobador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ajustes_aprobados", null=True, blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.PENDIENTE)
    creado_en = models.DateTimeField(auto_now_add=True)
    aplicado_en = models.DateTimeField(null=True, blank=True)

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError({"cantidad": "Debe ser mayor que cero."})
        if not self.motivo.strip():
            raise ValidationError({"motivo": "Todo ajuste exige un motivo."})


class DevolucionProduccion(models.Model):
    class EstadoMaterial(models.TextChoices):
        UTILIZABLE = "utilizable", "Utilizable"
        DANADO = "danado", "Dañado"
        MERMA = "merma", "Merma"

    detalle_entrega = models.ForeignKey(DetalleEntregaProduccion, on_delete=models.PROTECT, related_name="devoluciones")
    cantidad = models.DecimalField(max_digits=16, decimal_places=3)
    estado_material = models.CharField(max_length=15, choices=EstadoMaterial.choices)
    motivo = models.TextField()
    registrada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.cantidad <= 0 or self.cantidad > self.detalle_entrega.cantidad:
            raise ValidationError({"cantidad": "La devolución debe ser positiva y no superar lo entregado."})
        if not self.motivo.strip():
            raise ValidationError({"motivo": "La devolución exige un motivo."})


class EjecucionMRP(models.Model):
    creada_en = models.DateTimeField(auto_now_add=True)
    fecha_corte = models.DateField()
    horizonte_hasta = models.DateField()
    ejecutada_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    parametros = models.JSONField(default=dict)

    class Meta:
        # La más reciente primero. Sin `ordering` el orden lo decide la base y
        # es arbitrario: la pantalla tomaba la primera de la lista creyendo que
        # era la última ejecución y mostraba una vieja y vacía justo después de
        # haber corrido el cálculo. Que «la última» sea la primera es una
        # propiedad de la colección, no de una pantalla.
        ordering = ["-creada_en", "-id"]


class ResultadoMRP(models.Model):
    ejecucion = models.ForeignKey(EjecucionMRP, on_delete=models.CASCADE, related_name="resultados")
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT)
    fecha_requerida = models.DateField()
    necesidad_bruta = models.DecimalField(max_digits=16, decimal_places=3)
    disponible_proyectado = models.DecimalField(max_digits=16, decimal_places=3)
    recepciones_programadas = models.DecimalField(max_digits=16, decimal_places=3, default=0)
    necesidad_neta = models.DecimalField(max_digits=16, decimal_places=3)
    compra_sugerida = models.DecimalField(max_digits=16, decimal_places=3)
    fecha_sugerida_orden = models.DateField()
    explicacion = models.JSONField(default=dict)


class Notificacion(models.Model):
    destinatario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notificaciones")
    tipo = models.CharField(max_length=60)
    titulo = models.CharField(max_length=180)
    mensaje = models.TextField()
    documento_tipo = models.CharField(max_length=80, blank=True)
    documento_id = models.PositiveBigIntegerField(null=True, blank=True)
    leida_en = models.DateTimeField(null=True, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]


class Alerta(models.Model):
    class Severidad(models.TextChoices):
        INFO = "info", "Informativa"
        ADVERTENCIA = "advertencia", "Advertencia"
        CRITICA = "critica", "Crítica"

    tipo = models.CharField(max_length=60)
    severidad = models.CharField(max_length=15, choices=Severidad.choices)
    insumo = models.ForeignKey(Insumo, on_delete=models.PROTECT, null=True, blank=True)
    lote = models.ForeignKey(LoteInventario, on_delete=models.PROTECT, null=True, blank=True)
    mensaje = models.TextField()
    activa = models.BooleanField(default=True)
    creada_en = models.DateTimeField(auto_now_add=True)
    resuelta_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada_en"]
