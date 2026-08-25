"""Ayudas para que las pruebas de API usen el contrato de sesión vigente."""

from .models import SesionUsuario
from .sesiones import nueva_credencial


def credencial_sesion(usuario):
    """Crea una sesión opaca real y devuelve solamente su credencial."""
    credencial, digest = nueva_credencial()
    SesionUsuario.objects.create(usuario=usuario, token_hash=digest)
    return credencial
