from django.db import models
from django.contrib.auth.models import User


class Empresa(models.Model):
    rut = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=160)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Sucursal(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="sucursales")
    codigo = models.CharField(max_length=30)
    nombre = models.CharField(max_length=140)
    direccion = models.CharField(max_length=250, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["empresa", "codigo"], name="sucursal_codigo_unico_empresa")]
        ordering = ["empresa", "nombre"]

    def __str__(self):
        return f"{self.empresa} · {self.nombre}"


class Rol(models.TextChoices):
    """
    Los cinco roles del proceso, tal como los define el prototipo
    (prototipo/js/modelo/esquema.js, CATALOGOS.roles).

    No son categorías administrativas: cada uno corresponde a quién hace qué
    en planta, y de ahí sale la regla central del sistema — solo Calidad y
    Administración autorizan la liberación de un lote.
    """

    RECEPCION = "recepcion", "Recepción"
    PRODUCCION = "produccion", "Producción"
    CALIDAD = "calidad", "Calidad"
    ADMIN = "admin", "Administrador"
    LECTURA = "lectura", "Solo lectura"


# Quiénes pueden autorizar una liberación (MODELO_DATOS.md §1).
ROLES_AUTORIZADORES = (Rol.CALIDAD, Rol.ADMIN)


class PerfilUsuario(models.Model):

    class Nivel(models.TextChoices):
        ADMIN = "admin", "Administrador de área"
        TRABAJADOR = "trabajador", "Trabajador"

    class Area(models.TextChoices):
        RECEPCION = "recepcion", "Recepción"
        CONDENSACION = "condensacion", "Condensación"
        SECADO = "secado", "Secado"
        ENVASE = "envase", "Envase"
        CALIDAD = "calidad", "Calidad"
        BODEGA = "bodega", "Bodega"
        COMPRAS = "compras", "Compras"
        DESPACHO = "despacho", "Despacho"
        ADMINISTRACION = "administracion", "Administración general"

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil"
    )

    cargo = models.CharField(
        max_length=100,
        blank=True
    )

    area = models.CharField(max_length=30, choices=Area.choices, blank=True)

    turno = models.CharField(
        max_length=50,
        blank=True
    )

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.LECTURA
    )

    empresa = models.ForeignKey(
        Empresa, on_delete=models.PROTECT, related_name="perfiles", null=True, blank=True
    )

    sucursal = models.ForeignKey(
        Sucursal, on_delete=models.PROTECT, related_name="perfiles", null=True, blank=True
    )

    nivel = models.CharField(
        max_length=20,
        choices=Nivel.choices,
        default=Nivel.TRABAJADOR,
    )

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"

    def __str__(self):
        return self.usuario.username

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.sucursal_id and self.empresa_id and self.sucursal.empresa_id != self.empresa_id:
            raise ValidationError({"sucursal": "La sucursal no pertenece a la empresa seleccionada."})


def rol_de(usuario) -> str | None:
    """
    Rol efectivo de un usuario.

    Un superusuario de Django es administrador aunque no tenga perfil: es
    quien creó la instalación con `createsuperuser`, y dejarlo sin permisos
    lo encerraría fuera de su propio sistema.

    Un usuario normal sin perfil no tiene rol, y por tanto no escribe nada.
    """
    if usuario is None or not usuario.is_authenticated:
        return None

    if usuario.is_superuser:
        return Rol.ADMIN

    perfil = getattr(usuario, "perfil", None)

    if not perfil:
        return None

    # El área determina el permiso operativo. Un administrador de Secado
    # administra su personal, pero no se convierte por eso en administrador
    # global de maestros o de otras áreas.
    por_area = {
        PerfilUsuario.Area.RECEPCION: Rol.RECEPCION,
        PerfilUsuario.Area.CONDENSACION: Rol.PRODUCCION,
        PerfilUsuario.Area.SECADO: Rol.PRODUCCION,
        PerfilUsuario.Area.ENVASE: Rol.PRODUCCION,
        PerfilUsuario.Area.CALIDAD: Rol.CALIDAD,
    }
    if perfil.area == PerfilUsuario.Area.ADMINISTRACION:
        return Rol.ADMIN
    return por_area.get(perfil.area, perfil.rol)
