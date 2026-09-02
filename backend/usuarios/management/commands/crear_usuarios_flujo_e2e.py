"""Cuentas operacionales reproducibles para el circuito Playwright de polvo."""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from config.seguridad import ENTORNOS_ENDURECIDOS
from usuarios.models import PerfilUsuario, Rol, Sucursal
from usuarios.sesiones import revocar_sesiones


CLAVE = "flujo-e2e-ccaa"
CUENTAS = (
    ("e2e_produccion", Rol.PRODUCCION, PerfilUsuario.Area.CONDENSACION),
    ("e2e_calidad", Rol.CALIDAD, PerfilUsuario.Area.CALIDAD),
    ("e2e_secado", Rol.PRODUCCION, PerfilUsuario.Area.SECADO),
    ("e2e_envasado", Rol.PRODUCCION, PerfilUsuario.Area.ENVASE),
    ("e2e_inventario", Rol.OPERARIO, PerfilUsuario.Area.BODEGA),
)


class Command(BaseCommand):
    help = "Crea las cuentas por área usadas por el E2E productivo."

    def add_arguments(self, parser):
        parser.add_argument("--clave", default=CLAVE)

    @transaction.atomic
    def handle(self, *args, **opciones):
        if settings.DJANGO_ENV in ENTORNOS_ENDURECIDOS:
            raise CommandError("Las cuentas E2E solo pueden crearse en desarrollo o pruebas.")
        planta = Sucursal.objects.filter(activa=True).select_related("empresa").order_by("id").first()
        if planta is None:
            raise CommandError("No existe una planta activa para asociar las cuentas E2E.")

        for username, rol, area in CUENTAS:
            usuario, _ = User.objects.get_or_create(username=username)
            usuario.set_password(opciones["clave"])
            usuario.is_active = True
            usuario.save()
            revocar_sesiones(usuario, "password")
            perfil = PerfilUsuario.objects.filter(usuario=usuario).first() or PerfilUsuario(usuario=usuario)
            perfil.empresa = planta.empresa
            perfil.sucursal = planta
            perfil.alcance = PerfilUsuario.Alcance.SUCURSAL
            perfil.rol = rol
            perfil.area = area
            perfil.cargo = "Operación E2E"
            perfil.full_clean()
            perfil.save()
            self.stdout.write(f"{username}: {rol}/{area}")
