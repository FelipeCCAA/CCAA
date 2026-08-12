from django.apps import AppConfig
from django.core.checks import register


class UsuariosConfig(AppConfig):
    name = 'usuarios'

    def ready(self):
        # Avisa de los perfiles con un área fuera del catálogo. `choices` no
        # valida en la base, y un área inventada deja a esa persona invisible
        # para los permisos y para los avisos de planta, sin dar ningún error.
        from .checks import areas_dentro_del_catalogo

        register(areas_dentro_del_catalogo)
