from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Empresa, PerfilUsuario, Sucursal, rol_de


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    rol_etiqueta = serializers.CharField(source="get_rol_display", read_only=True)
    nivel_etiqueta = serializers.CharField(source="get_nivel_display", read_only=True)
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            "cargo", "area", "area_etiqueta", "turno", "rol", "rol_etiqueta",
            "nivel", "nivel_etiqueta", "empresa", "sucursal",
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
    """Lectura y escritura segura de usuarios junto con su perfil."""

    nombre = serializers.CharField(source="first_name", required=False, allow_blank=True)
    apellido = serializers.CharField(source="last_name", required=False, allow_blank=True)
    activo = serializers.BooleanField(source="is_active", required=False)
    ultimo_acceso = serializers.DateTimeField(source="last_login", read_only=True)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    area = serializers.ChoiceField(
        choices=PerfilUsuario.Area.choices, write_only=True, required=False
    )
    nivel = serializers.ChoiceField(
        choices=PerfilUsuario.Nivel.choices, write_only=True, required=False
    )
    cargo = serializers.CharField(write_only=True, required=False, allow_blank=True)
    turno = serializers.CharField(write_only=True, required=False, allow_blank=True)
    empresa = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.filter(activa=True), write_only=True, required=False,
        allow_null=True,
    )
    sucursal = serializers.PrimaryKeyRelatedField(
        queryset=Sucursal.objects.filter(activa=True), write_only=True, required=False,
        allow_null=True,
    )

    class Meta(UsuarioSerializer.Meta):
        fields = UsuarioSerializer.Meta.fields + [
            "activo", "ultimo_acceso", "password", "area", "nivel", "cargo",
            "turno", "empresa", "sucursal",
        ]
        extra_kwargs = {"email": {"required": False, "allow_blank": True}}

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError(
                {"password": "La contraseña inicial es obligatoria."}
            )
        if password:
            candidato = self.instance or User(username=attrs.get("username", ""))
            try:
                validate_password(password, user=candidato)
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": error.messages}) from error

        perfil_actual = getattr(self.instance, "perfil", None)
        empresa = attrs.get("empresa", getattr(perfil_actual, "empresa", None))
        sucursal = attrs.get("sucursal", getattr(perfil_actual, "sucursal", None))
        if sucursal and empresa and sucursal.empresa_id != empresa.id:
            raise serializers.ValidationError(
                {"sucursal": "La sucursal no pertenece a la empresa seleccionada."}
            )
        return attrs

    @staticmethod
    def _extraer_perfil(validated_data):
        return {
            campo: validated_data.pop(campo)
            for campo in ("area", "nivel", "cargo", "turno", "empresa", "sucursal")
            if campo in validated_data
        }

    @transaction.atomic
    def create(self, validated_data):
        datos_perfil = self._extraer_perfil(validated_data)
        password = validated_data.pop("password")
        usuario = User.objects.create_user(password=password, **validated_data)
        perfil = PerfilUsuario(usuario=usuario, **datos_perfil)
        perfil.full_clean()
        perfil.save()
        return usuario

    @transaction.atomic
    def update(self, instance, validated_data):
        datos_perfil = self._extraer_perfil(validated_data)
        password = validated_data.pop("password", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        if password:
            instance.set_password(password)
        instance.save()

        perfil, _ = PerfilUsuario.objects.get_or_create(usuario=instance)
        for campo, valor in datos_perfil.items():
            setattr(perfil, campo, valor)
        perfil.full_clean()
        perfil.save()
        return instance


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
