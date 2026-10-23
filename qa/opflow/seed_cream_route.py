"""Link the existing commercial cream route in fictitious OPFLOW only.

Same relation as migration procesos.0018, which ran before test products existed.
No orders, users, industrial lots, movements or approvals are created.
"""
from django.conf import settings
from django.db import transaction

from maestros.models import Producto
from procesos.models import Proceso, RutaProducto
from usuarios.models import Sucursal


@transaction.atomic
def seed():
    db = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and db["NAME"] == "opflow_circuito"
            and db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "55479"):
        raise RuntimeError("Cream route preparation refuses databases except OPFLOW")
    planta = Sucursal.objects.get(activa=True)
    if planta.codigo != "INTERNA" or planta.empresa.rut != "TENANT-TEST":
        raise RuntimeError("Unexpected fictitious plant")
    producto = Producto.objects.get(nombre="Crema fresca 42% Granel CA", activo=True)
    proceso = Proceso.objects.get(codigo="ruta-crema-despacho", activo=True)
    RutaProducto.objects.get_or_create(
        sucursal=planta, producto=producto, proceso=proceso,
        defaults={"prioridad": 1, "destino_final": RutaProducto.DestinoFinal.DESPACHO_DIRECTO,
                  "destino": "Despacho directo despues de liberacion",
                  "observaciones": "Fixture OPFLOW: relacion existente en migracion 0018; sin validez industrial.",
                  "activa": True},
    )
    print("OPFLOW_CREAM_ROUTE_OK: relation only; no industrial stock or approvals")


seed()
