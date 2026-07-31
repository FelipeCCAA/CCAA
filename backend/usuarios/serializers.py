from django.contrib.auth.models import User
from rest_framework import serializers

from .models import PerfilUsuario, rol_de


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    rol_etiqueta = serializers.CharField(source="get_rol_display", read_only=True)
    nivel_etiqueta = serializers.CharField(source="get_nivel_display", read_only=True)
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            "cargo", "area", "area_etiqueta", "turno", "rol", "rol_etiqueta",
            "nivel", "nivel_etiqueta",
        ]


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

    # Rol efectivo, que no siempre es el del perfil: un superusuario es
    # administrador aunque no tenga uno. La interfaz usa este campo para
    # decidir qué acciones mostrar, así que tiene que coincidir con lo que
    # el backend va a permitir.
    rol = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "nombre", "apellido", "email", "rol", "perfil"]

    def get_perfil(self, usuario):
        perfil = getattr(usuario, "perfil", None)

        return PerfilUsuarioSerializer(perfil).data if perfil else None

    def get_rol(self, usuario):
        return rol_de(usuario)


class TrabajadorSerializer(UsuarioSerializer):
    """Datos de personal visibles en el panel administrativo."""

    activo = serializers.BooleanField(source="is_active", read_only=True)
    ultimo_acceso = serializers.DateTimeField(source="last_login", read_only=True)

    class Meta(UsuarioSerializer.Meta):
        fields = UsuarioSerializer.Meta.fields + ["activo", "ultimo_acceso"]


class SolicitudRecuperacionSerializer(serializers.Serializer):
    """Valida la dirección a la que se enviarán las instrucciones."""

    email = serializers.EmailField(max_length=254)


class ConfirmacionRecuperacionSerializer(serializers.Serializer):
    """Valida los datos públicos del enlace y la nueva contraseña."""

    uid = serializers.CharField(max_length=128)
    token = serializers.CharField(max_length=256)
    nueva_contrasena = serializers.CharField(
        max_length=128,
        trim_whitespace=False,
        write_only=True,
    )
    confirmar_contrasena = serializers.CharField(
        max_length=128,
        trim_whitespace=False,
        write_only=True,
    )

    def validate(self, datos):
        if datos["nueva_contrasena"] != datos["confirmar_contrasena"]:
            raise serializers.ValidationError(
                {"confirmar_contrasena": "Las contraseñas no coinciden."}
            )

        return datos
