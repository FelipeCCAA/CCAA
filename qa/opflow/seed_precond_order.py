"""One expressly authorized fictitious 2000 L order, restricted to OPFLOW.

No users, specifications, industrial material, approvals or clients are changed.
Use the isolated management wrapper, which verifies cluster identity first.
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from maestros.models import Producto
from procesos.models import RutaProducto
from produccion.models import OrdenProduccion
from usuarios.models import Sucursal


@transaction.atomic
def seed():
    db = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and db["NAME"] == "opflow_circuito"
            and db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "55479"):
        raise RuntimeError("Precondensate order refuses every database except OPFLOW")
    planta = Sucursal.objects.get(activa=True)
    if planta.codigo != "INTERNA" or planta.empresa.rut != "TENANT-TEST":
        raise RuntimeError("Unexpected fictitious plant")
    autor = User.objects.get(username="opflow_semilla", is_active=False)
    if autor.has_usable_password():
        raise RuntimeError("Fixture author must not be able to sign in")
    producto = Producto.objects.get(nombre="Precondensado Entero NE Granel", activo=True)
    RutaProducto.objects.get(
        sucursal=planta, producto=producto, activa=True,
        destino_final=RutaProducto.DestinoFinal.DESPACHO_DIRECTO,
    )
    orden, creada = OrdenProduccion.objects.get_or_create(
        sucursal=planta, codigo="OPFLOW-OP-PRECOND-01",
        defaults={"producto": producto, "cantidad_planificada": Decimal("2000"),
                  "unidad": "l", "estado": OrdenProduccion.Estado.PROGRAMADA,
                  "creada_por": autor,
                  "observacion": "Orden FICTICIA local2000L expresamente autorizada. Sin compromiso comercial ni producción real."},
    )
    if (orden.producto_id != producto.id or orden.cantidad_planificada != Decimal("2000")
            or orden.unidad != "l"):
        raise RuntimeError("Existing precondensate order is incompatible")
    print(f"OPFLOW_PRECOND_ORDER_OK: {orden.codigo}; 2000L; created={creada}; no industrial stock or approvals")


seed()
