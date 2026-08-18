"""Serializers de los registros que pertenecen al equipo y su período."""

from rest_framework import serializers

from maestros.models import DocumentoLiberacion, Equipo
from usuarios.tenancy import filtrar_por_scope, sucursal_para_escritura

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
        documento = datos.get("documento") or getattr(self.instance, "documento", None)
        equipo = datos.get("equipo", getattr(self.instance, "equipo", None))
        hasta = datos.get("vigente_hasta", getattr(self.instance, "vigente_hasta", None))

        if self.instance is None:
            sucursal = sucursal_para_escritura(
                getattr(request, "user", None), datos
            )
            repetido = RegistroEquipo.objects.filter(
                sucursal=sucursal,
                documento=documento,
                equipo=equipo,
                fecha=datos.get("fecha"),
                turno=datos.get("turno", ""),
            )
            if repetido.exists():
                raise serializers.ValidationError(
                    {"fecha": "Ya existe un registro para este período."}
                )

        if equipo and documento and equipo.sucursal.empresa_id != documento.empresa_id:
            raise serializers.ValidationError(
                {"documento": "El documento y el equipo deben pertenecer a la misma organización."}
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
