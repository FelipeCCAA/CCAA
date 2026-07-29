from django.contrib.auth.models import User
from rest_framework import serializers

from .models import PerfilUsuario


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    rol_etiqueta = serializers.CharField(source="get_rol_display", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ["cargo", "area", "turno", "rol", "rol_etiqueta"]


class UsuarioSerializer(serializers.ModelSerializer):
    """
    El usuario tal como lo necesita la interfaz.

    Incluye el perfil, que es de donde salen el cargo y el rol que el menú
    lateral muestra bajo el nombre. Un usuario sin perfil devuelve `null`
    en vez de romper: los usuarios creados desde `createsuperuser` no lo
    tienen.
    """

    nombre = serializers.CharField(source="first_name", read_only=True)
    apellido = serializers.CharField(source="last_name", read_only=True)
    perfil = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "nombre", "apellido", "email", "perfil"]

    def get_perfil(self, usuario):
        perfil = getattr(usuario, "perfil", None)

        return PerfilUsuarioSerializer(perfil).data if perfil else None
