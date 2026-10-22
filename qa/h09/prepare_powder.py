"""Only the missing synthetic powder order; never creates a process result."""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction

from maestros.models import Producto
from produccion.models import OrdenProduccion
from usuarios.models import Sucursal


@transaction.atomic
def prepare():
    database = settings.DATABASES["default"]
    assert database["NAME"] == "h09_firmas" and database["HOST"] == "127.0.0.1" and str(database["PORT"]) == "55459"
    product = Producto.objects.get(nombre="Leche entera en polvo")
    branch = Sucursal.objects.filter(activa=True).order_by("pk").first()
    actor = User.objects.get(username="op09_semilla")
    order, created = OrdenProduccion.objects.get_or_create(
        sucursal=branch, codigo="OP-H09-POLVO-01",
        defaults={"producto": product, "cantidad_planificada": Decimal("20000"), "unidad": "l", "estado": OrdenProduccion.Estado.PROGRAMADA, "creada_por": actor},
    )
    print({"synthetic_order": order.codigo, "created": created, "product": product.nombre})


prepare()
