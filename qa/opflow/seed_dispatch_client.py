"""One fictitious dispatch master, no orders, shipments or communications.

Run with the guarded OPFLOW management wrapper, never normal manage.py.
"""
from django.conf import settings
from django.db import transaction

from inventario.models import ClienteDespacho
from usuarios.models import Sucursal


@transaction.atomic
def seed():
    db = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and db["NAME"] == "opflow_circuito"
            and db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "55479"):
        raise RuntimeError("Client fixture refuses every database except OPFLOW")
    planta = Sucursal.objects.get(activa=True)
    if planta.codigo != "INTERNA" or planta.empresa.rut != "TENANT-TEST":
        raise RuntimeError("Unexpected fictitious plant")
    cliente, _ = ClienteDespacho.objects.get_or_create(
        empresa=planta.empresa, codigo="OPFLOW-CLIENTE-FICTICIO",
        defaults={"nombre": "Cliente FICTICIO OPFLOW", "direccion": "Destino ficticio de ensayo local", "activo": True},
    )
    if not cliente.activo or cliente.nombre != "Cliente FICTICIO OPFLOW":
        raise RuntimeError("Incompatible existing fixture client")
    print("OPFLOW_CLIENT_MASTER_OK: no shipment, inventory or external communication")


seed()
