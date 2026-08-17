from django.contrib.auth.models import Permission, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import Empresa, PerfilUsuario, Sucursal, rol_de
from .permisos_industriales import permisos_asignables_por
from .tenancy import unica_sucursal_activa, scope_de


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    rol_etiqueta = serializers.CharField(source="get_rol_display", read_only=True)
    nivel_etiqueta = serializers.CharField(source="get_nivel_display", read_only=True)
    area_etiqueta = serializers.CharField(source="get_area_display", read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = [
            "cargo", "area", "area_etiqueta", "turno", "rol", "rol_etiqueta",
            "nivel", "nivel_etiqueta", "empresa", "sucursal", "alcance",
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
    capacidades = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "nombre", "apellido", "email", "rol",
            "capacidades", "perfil",
        ]

    def get_perfil(self, usuario):
        perfil = getattr(usuario, "perfil", None)

        return PerfilUsuarioSerializer(perfil).data if perfil else None

    def get_rol(self, usuario):
        return rol_de(usuario)

    def get_capacidades(self, usuario):
        from .permisos_industriales import capacidades_de

        return capacidades_de(usuario)


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
    alcance = serializers.ChoiceField(
        choices=PerfilUsuario.Alcance.choices, write_only=True, required=False
    )
    empresa = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.filter(activa=True), write_only=True, required=False,
        allow_null=True,
    )
    sucursal = serializers.PrimaryKeyRelatedField(
        queryset=Sucursal.objects.filter(activa=True), write_only=True, required=False,
        allow_null=True,
    )
    permisos = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )
    permisos_asignados = serializers.SerializerMethodField()

    class Meta(UsuarioSerializer.Meta):
        fields = UsuarioSerializer.Meta.fields + [
            "activo", "ultimo_acceso", "password", "area", "nivel", "cargo",
            "turno", "empresa", "sucursal", "alcance",
            "permisos", "permisos_asignados",
        ]
        extra_kwargs = {"email": {"required": False, "allow_blank": True}}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        scope = scope_de(getattr(request, "user", None)) if request else None
        if scope is None:
            self.fields["empresa"].queryset = Empresa.objects.none()
            self.fields["sucursal"].queryset = Sucursal.objects.none()
        elif not scope.es_global:
            self.fields["empresa"].queryset = Empresa.objects.filter(
                pk=scope.empresa_id, activa=True
            )
            sucursales = Sucursal.objects.filter(
                empresa_id=scope.empresa_id, activa=True
            )
            if scope.es_sucursal:
                sucursales = sucursales.filter(pk=scope.sucursal_id)
            self.fields["sucursal"].queryset = sucursales

    @staticmethod
    def _completar_tenant(attrs, scope_actor):
        """
        Deduce empresa/sucursal/alcance cuando el alta no los manda.

        El formulario de personal **no los pide** —la organización tiene una
        sola planta y no hay nada que elegir—, así que sin esto el alta fallaba
        con «Debes indicar una sucursal» sobre un campo que la pantalla no
        muestra.

        Dos deducciones, y la primera es la que pidió Administración:

        - **Administración general nace con alcance de empresa.** Es quien
          responde por toda la empresa; atarla a una planta le negaría lo que
          su propio nivel dice que abarca.
        - El resto trabaja en una planta, y se resuelve sola **si hay una**.
          Con dos, la elección vuelve a importar y se pide: elegir por el que
          da de alta es crear al operario en la planta equivocada.

        Solo rellena lo ausente. Un valor enviado a propósito manda, y se sigue
        validando después contra el alcance de quien crea.
        """
        if scope_actor.es_sucursal:
            # Su planta es la única que puede tocar: no hay nada que deducir.
            attrs.setdefault("empresa", Empresa.objects.get(pk=scope_actor.empresa_id))
            attrs.setdefault("sucursal", Sucursal.objects.get(pk=scope_actor.sucursal_id))
            attrs.setdefault("alcance", PerfilUsuario.Alcance.SUCURSAL)
            return

        if scope_actor.es_empresa:
            attrs.setdefault("empresa", Empresa.objects.get(pk=scope_actor.empresa_id))

        empresa = attrs.get("empresa")
        if empresa is None:
            # Superusuario que no la indicó: el reproche lo da el modelo, y con
            # su nombre. Adivinar la empresa sí sería grave.
            return

        if attrs.get("sucursal") is not None:
            return

        alcance = attrs.get("alcance")
        es_administracion_general = (
            attrs.get("area") == PerfilUsuario.Area.ADMINISTRACION
            and attrs.get("nivel") == PerfilUsuario.Nivel.ADMIN
        )

        if alcance == PerfilUsuario.Alcance.EMPRESA or (
            alcance is None and es_administracion_general
        ):
            attrs["alcance"] = PerfilUsuario.Alcance.EMPRESA
            # Explícito, y no ausente: el campo del modelo tiene un valor por
            # omisión —la sucursal sembrada en pruebas, y una excepción fuera
            # de ellas—, así que no mandarlo no es lo mismo que mandar nada.
            attrs["sucursal"] = None
            return

        unica = unica_sucursal_activa(empresa.pk)
        if unica is not None:
            attrs["sucursal"] = unica
            attrs["alcance"] = PerfilUsuario.Alcance.SUCURSAL

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
        request = self.context.get("request")
        scope_actor = scope_de(getattr(request, "user", None)) if request else None

        if self.instance is None and scope_actor is not None:
            self._completar_tenant(attrs, scope_actor)

        empresa = attrs.get("empresa", getattr(perfil_actual, "empresa", None))
        sucursal = attrs.get("sucursal", getattr(perfil_actual, "sucursal", None))
        alcance = attrs.get(
            "alcance",
            getattr(perfil_actual, "alcance", PerfilUsuario.Alcance.SUCURSAL),
        )
        if sucursal and empresa and sucursal.empresa_id != empresa.id:
            raise serializers.ValidationError(
                {"sucursal": "La sucursal no pertenece a la empresa seleccionada."}
            )
        if alcance == PerfilUsuario.Alcance.SUCURSAL and not sucursal:
            raise serializers.ValidationError(
                {"sucursal": "Debes indicar una sucursal para este alcance."}
            )
        if alcance == PerfilUsuario.Alcance.EMPRESA and sucursal:
            raise serializers.ValidationError(
                {"sucursal": "Un perfil de alcance empresa no lleva sucursal."}
            )
        area = attrs.get("area", getattr(perfil_actual, "area", ""))
        nivel = attrs.get(
            "nivel", getattr(perfil_actual, "nivel", PerfilUsuario.Nivel.TRABAJADOR)
        )
        if alcance == PerfilUsuario.Alcance.EMPRESA and not (
            area == PerfilUsuario.Area.ADMINISTRACION
            and nivel == PerfilUsuario.Nivel.ADMIN
        ):
            raise serializers.ValidationError(
                {"alcance": "Solo Administración general puede abarcar toda la empresa."}
            )
        return attrs

    @staticmethod
    def _extraer_perfil(validated_data):
        return {
            campo: validated_data.pop(campo)
            for campo in (
                "area", "nivel", "cargo", "turno", "empresa", "sucursal", "alcance"
            )
            if campo in validated_data
        }

    def get_permisos_asignados(self, usuario):
        return list(
            usuario.user_permissions.filter(
                content_type__app_label="usuarios",
                content_type__model="perfilusuario",
            ).values_list("codename", flat=True)
        )

    def _validar_permisos(self, codigos):
        if codigos is None:
            return None
        actor = getattr(self.context.get("request"), "user", None)
        desconocidos = sorted(set(codigos) - permisos_asignables_por(actor))
        if desconocidos:
            raise serializers.ValidationError({
                "permisos": "No puedes asignar estos permisos: " + ", ".join(desconocidos)
            })
        return list(dict.fromkeys(codigos))

    @staticmethod
    def _guardar_permisos(usuario, codigos):
        if codigos is None:
            return
        permisos = Permission.objects.filter(
            content_type__app_label="usuarios",
            content_type__model="perfilusuario",
            codename__in=codigos,
        )
        usuario.user_permissions.set(permisos)

    @transaction.atomic
    def create(self, validated_data):
        permisos = self._validar_permisos(validated_data.pop("permisos", None))
        datos_perfil = self._extraer_perfil(validated_data)
        password = validated_data.pop("password")
        usuario = User.objects.create_user(password=password, **validated_data)
        perfil = PerfilUsuario(usuario=usuario, **datos_perfil)
        perfil.full_clean()
        perfil.save()
        self._guardar_permisos(usuario, permisos)
        return usuario

    @transaction.atomic
    def update(self, instance, validated_data):
        permisos = self._validar_permisos(validated_data.pop("permisos", None))
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
        self._guardar_permisos(instance, permisos)
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
