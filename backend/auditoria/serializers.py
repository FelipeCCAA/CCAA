from rest_framework import serializers

from .models import RegistroAuditoria


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    accion_etiqueta = serializers.CharField(source="get_accion_display", read_only=True)

    class Meta:
        model = RegistroAuditoria
        fields = [
            "id",
            "fecha_hora",
            "usuario",
            "usuario_nombre",
            "accion",
            "accion_etiqueta",
            "modelo",
            "etiqueta_modelo",
            "objeto_id",
            "objeto_desc",
            "cambios",
            "ip",
            "origen",
        ]
