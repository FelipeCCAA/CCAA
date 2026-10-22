"""Complete synthetic catalog using the existing migration 0018 route."""
from django.conf import settings
from django.db import transaction
from inventario.models import ClienteDespacho
from maestros.models import Producto
from procesos.models import Proceso, RutaProducto
from usuarios.models import Sucursal

assert settings.DJANGO_ENV == "test" and settings.DATABASES["default"]["NAME"] == "op09_circuito"
with transaction.atomic():
    branch = Sucursal.objects.filter(activa=True).get()
    route = Proceso.objects.get(codigo="ruta-crema-despacho", version=1)
    for product in Producto.objects.filter(activo=True, categoria="crema", formato="granel"):
        RutaProducto.objects.get_or_create(sucursal=branch, producto=product, proceso=route, defaults={"prioridad": 1, "destino": "Despacho directo después de liberación — fixture OP09", "destino_final": "despacho_directo", "activa": True})
    ClienteDespacho.objects.get_or_create(empresa=branch.empresa, codigo="OP09-FICTICIO", defaults={"nombre": "Cliente ficticio OP09", "direccion": "Dirección ficticia, sin transporte real"})
print("OP09 existing direct-cream route linked to synthetic products; fictitious customer ready")
