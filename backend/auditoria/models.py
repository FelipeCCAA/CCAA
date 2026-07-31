"""
Registro de auditoría: quién cambió qué, cuándo, y de qué a qué.

Es un requisito de HACCP/FSSC y no una comodidad: cuando una auditoría
pregunta quién modificó el rango de humedad de una especificación y qué decía
antes, la respuesta tiene que existir. Hasta ahora el sistema solo guardaba
`Liberacion.autorizada_por` —quién firmó— y el `LogEntry` de Django, que
únicamente registra lo hecho desde el admin.

Se escribe **una fila por cambio**, con los campos que cambiaron y sus valores
antes y después. Guardar solo el autor respondería «quién lo dejó así», que no
es la pregunta que hace un auditor.
"""

from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    """Un cambio sobre un registro del sistema."""

    class Accion(models.TextChoices):
        CREACION = "creacion", "Creación"
        MODIFICACION = "modificacion", "Modificación"
        BORRADO = "borrado", "Borrado"

    fecha_hora = models.DateTimeField("Fecha y hora", auto_now_add=True, db_index=True)

    # SET_NULL y no CASCADE: borrar un usuario no puede borrar la historia de
    # lo que hizo, que es justamente lo que la auditoría existe para conservar.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditoria",
        verbose_name="Usuario",
    )
    # Copia del nombre al momento del cambio. Si el usuario se borra o se
    # renombra, el registro sigue diciendo quién fue.
    usuario_nombre = models.CharField("Usuario (al momento)", max_length=150, blank=True)

    accion = models.CharField("Acción", max_length=20, choices=Accion.choices)

    # 'produccion.Lote'. Texto y no ContentType: un modelo que se elimina del
    # código no puede llevarse por delante su historial.
    modelo = models.CharField("Modelo", max_length=100, db_index=True)
    etiqueta_modelo = models.CharField("Modelo (nombre)", max_length=100, blank=True)
    objeto_id = models.CharField("ID del objeto", max_length=40, db_index=True)
    # `str()` del objeto al momento del cambio: después de un borrado es lo
    # único que queda para saber de qué se hablaba.
    objeto_desc = models.CharField("Objeto", max_length=300, blank=True)

    cambios = models.JSONField(
        "Cambios",
        default=dict,
        blank=True,
        help_text='{"kg_producidos": ["1000.00", "1200.00"]}',
    )

    ip = models.GenericIPAddressField("IP", null=True, blank=True)
    # 'api', 'admin' o 'sistema' (migraciones, scripts, shell).
    origen = models.CharField("Origen", max_length=20, blank=True)

    class Meta:
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"
        ordering = ["-fecha_hora", "-id"]
        indexes = [
            models.Index(fields=["modelo", "objeto_id"]),
            models.Index(fields=["usuario", "-fecha_hora"]),
        ]

    def __str__(self):
        quien = self.usuario_nombre or "sistema"
        return f"{quien} · {self.get_accion_display()} · {self.objeto_desc or self.modelo}"

    @property
    def campos_cambiados(self) -> list[str]:
        return sorted(self.cambios or {})
