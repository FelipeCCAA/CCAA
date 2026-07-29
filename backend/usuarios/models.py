from django.db import models
from django.contrib.auth.models import User


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

    usuario = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="perfil"
    )

    cargo = models.CharField(
        max_length=100,
        blank=True
    )

    area = models.CharField(
        max_length=100,
        blank=True
    )

    turno = models.CharField(
        max_length=50,
        blank=True
    )

    rol = models.CharField(
        max_length=20,
        choices=Rol.choices,
        default=Rol.LECTURA
    )

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"

    def __str__(self):
        return self.usuario.username


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

    return perfil.rol if perfil else None
