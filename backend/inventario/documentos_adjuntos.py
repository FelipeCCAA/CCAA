"""Lista cerrada de documentos y permisos de lectura para sus evidencias."""
from types import SimpleNamespace

from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError


DOCUMENTOS = {
    "inventario.LoteInventario": "LoteInventarioViewSet",
    "inventario.SolicitudCompra": "SolicitudCompraViewSet",
    "inventario.OrdenCompra": "OrdenCompraViewSet",
    "inventario.RecepcionCompra": "RecepcionCompraViewSet",
    "inventario.SolicitudMaterial": "SolicitudMaterialViewSet",
    "inventario.InspeccionMaterial": "InspeccionMaterialViewSet",
    "inventario.NoConformidadMaterial": "NoConformidadViewSet",
    "inventario.LiberacionExcepcionalMaterial": "LiberacionExcepcionalViewSet",
    "inventario.Despacho": "DespachoViewSet",
}


class DocumentoConEvidenciasError(DjangoValidationError):
    pass


def consulta_documento(tipo, request, *, escritura=False):
    # Import diferido: los ViewSets usan a su vez el serializer de adjuntos.
    from . import views

    nombre = DOCUMENTOS.get(tipo)
    if nombre is None:
        raise ValidationError({"documento_tipo": "Tipo de documento no admitido para adjuntos."})
    vista = getattr(views, nombre)()
    consulta = SimpleNamespace(user=request.user, method="POST" if escritura else "GET", query_params={},
                              authenticators=[], successful_authenticator=None)
    vista.request = consulta
    vista.action = "create" if escritura else "retrieve"
    vista.kwargs = {}
    vista.check_permissions(consulta)
    return vista.get_queryset()


def validar_documento(tipo, identificador, request, *, escritura=False):
    try:
        return consulta_documento(tipo, request, escritura=escritura).get(pk=identificador)
    except ObjectDoesNotExist as error:
        raise ValidationError({"documento_id": "El documento no existe o no está disponible."}) from error


def conservar_documento_con_adjuntos(sender, instance, **kwargs):
    from .models import Adjunto

    # DELETE de Django ya está en una transacción. Comparte el bloqueo de
    # subida para que borrar/subir simultáneamente tampoco deje huérfanos.
    sender.objects.select_for_update().filter(pk=instance.pk).exists()
    if Adjunto.objects.filter(documento_tipo=sender._meta.label, documento_id=instance.pk).exists():
        raise DocumentoConEvidenciasError("El documento tiene adjuntos de evidencia y no se puede eliminar.")
