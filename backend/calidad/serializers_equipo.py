"""Serializers de los registros que pertenecen al equipo y su período."""

from rest_framework import serializers

from maestros.models import DocumentoLiberacion, Equipo
from usuarios.models import Sucursal
from usuarios.tenancy import filtrar_por_scope, scope_de

from .models import RegistroEquipo
from . import dominio


class RegistroEquipoSerializer(serializers.ModelSerializer):
    documento_nombre = serializers.CharField(source="documento.nombre", read_only=True)
    documento_codigo = serializers.CharField(source="documento.codigo", read_only=True)
    frecuencia = serializers.CharField(source="documento.frecuencia", read_only=True)
    frecuencia_etiqueta = serializers.CharField(
        source="documento.get_frecuencia_display", read_only=True
    )
    equipo_nombre = serializers.CharField(source="equipo.nombre", read_only=True)
    estado_etiqueta = serializers.CharField(source="get_estado_display", read_only=True)

    # Derivado de la plantilla, igual que en el registro por lote: si al
    # documento le cambian los campos, esto cambia solo.
    completo = serializers.SerializerMethodField()
    faltantes = serializers.SerializerMethodField()

    class Meta:
        model = RegistroEquipo
        fields = [
            "id",
            "sucursal",
            "documento",
            "documento_nombre",
            "documento_codigo",
            "frecuencia",
            "frecuencia_etiqueta",
            "equipo",
            "equipo_nombre",
            "fecha",
            "vigente_hasta",
            "turno",
            "valores",
            "estado",
            "estado_etiqueta",
            "observacion",
            "completado_por",
            "completado_en",
            "completo",
            "faltantes",
        ]
        # Quién lo completó y cuándo los pone el servidor: son la firma del
        # registro, no un dato que el cliente elija.
        read_only_fields = ["completado_por", "completado_en"]
        extra_kwargs = {
            # Participan en la clave de unicidad, y DRF exige todos sus campos
            # aunque el modelo los declare opcionales.
            "turno": {"required": False, "default": ""},
            "equipo": {"required": False, "default": None},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request:
            return
        scope = scope_de(request.user)
        sucursales = Sucursal.objects.filter(activa=True)
        if scope is None:
            sucursales = sucursales.none()
        elif not scope.es_global:
            sucursales = sucursales.filter(empresa_id=scope.empresa_id)
            if scope.es_sucursal:
                sucursales = sucursales.filter(pk=scope.sucursal_id)
        self.fields["sucursal"].queryset = sucursales
        self.fields["documento"].queryset = filtrar_por_scope(
            DocumentoLiberacion.objects.all(), request.user, campo_empresa="empresa_id"
        )
        self.fields["equipo"].queryset = filtrar_por_scope(
            Equipo.objects.all(), request.user,
            campo_sucursal="sucursal_id", campo_empresa="sucursal__empresa_id",
        )

    def get_completo(self, registro):
        return dominio.registro_completo(registro, registro.documento)

    def get_faltantes(self, registro):
        return [c["etiqueta"] for c in dominio.campos_faltantes(registro, registro.documento)]

    def validate(self, datos):
        """
        Un registro «según programa» tiene que decir hasta cuándo cubre.

        Sin eso no cubriría nada —así lo decide el dominio— y el usuario se
        quedaría sin entender por qué su registro no aparece en ningún lote.
        Mejor pedirlo aquí.
        """
        request = self.context.get("request")
        scope = scope_de(getattr(request, "user", None)) if request else None
        if self.instance is None and scope and scope.es_sucursal:
            datos["sucursal"] = Sucursal.objects.get(pk=scope.sucursal_id)

        sucursal = datos.get("sucursal", getattr(self.instance, "sucursal", None))
        documento = datos.get("documento") or getattr(self.instance, "documento", None)
        equipo = datos.get("equipo", getattr(self.instance, "equipo", None))
        hasta = datos.get("vigente_hasta", getattr(self.instance, "vigente_hasta", None))

        if sucursal and documento and sucursal.empresa_id != documento.empresa_id:
            raise serializers.ValidationError(
                {"documento": "El documento debe pertenecer a la empresa de la sucursal."}
            )
        if sucursal and equipo and sucursal.pk != equipo.sucursal_id:
            raise serializers.ValidationError(
                {"equipo": "El equipo debe pertenecer a la sucursal del registro."}
            )

        if documento and documento.frecuencia == "segun_programa" and hasta is None:
            raise serializers.ValidationError(
                {
                    "vigente_hasta": (
                        "Un registro «según programa» debe declarar hasta cuándo "
                        "cubre: su período no se puede deducir."
                    )
                }
            )

        return datos
