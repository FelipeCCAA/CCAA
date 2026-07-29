from django.db import models
from django.contrib.auth.models import User


class PerfilUsuario(models.Model):

    ROLES = [
        ("ADMIN", "Administrador"),
        ("TRABAJADOR", "Trabajador"),
    ]

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
        choices=ROLES,
        default="TRABAJADOR"
    )

    def __str__(self):
        return self.usuario.username