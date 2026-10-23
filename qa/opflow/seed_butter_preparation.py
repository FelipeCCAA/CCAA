"""Existing E2E butter fixtures, excluding every industrial input/output lot.

Prepares specification, packaging recipe/initial packaging stock and one test
order. It never calls the full preparator, which also creates a mazada lot.
All numeric configuration is from preparar_circuito_mantequilla.py, not a new
industrial tolerance. No users, permissions or Planning capacities are edited.
"""
from datetime import date

from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max

from maestros.models import Equipo, Especificacion, Producto
from procesos.models import RutaProducto
from produccion.management.commands.preparar_circuito_mantequilla import Command
from produccion.models import OrdenProduccion
from usuarios.models import Sucursal


@transaction.atomic
def seed():
    db = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and db["NAME"] == "opflow_circuito"
            and db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "55479"):
        raise RuntimeError("Butter preparation refuses every database except OPFLOW")
    planta = Sucursal.objects.get(activa=True)
    if planta.codigo != "INTERNA" or planta.empresa.rut != "TENANT-TEST":
        raise RuntimeError("Unexpected fictitious plant")
    autor = User.objects.get(username="opflow_semilla", is_active=False)
    if autor.has_usable_password():
        raise RuntimeError("Fixture author must not be able to sign in")
    producto = Producto.objects.get(nombre="Mantequilla S-sal 20kg", activo=True)
    RutaProducto.objects.get(sucursal=planta, producto=producto, proceso__codigo="ruta-mantequilla", activa=True)
    linea = Equipo.objects.get(sucursal=planta, activo=True, tipo=Equipo.Tipo.LINEA, nombre__icontains="mantequilla")
    # The generic initial catalogue already has a v1 temperature-only spec.
    # Follow the existing preparator: add a new version, never overwrite it.
    existentes = producto.especificaciones.filter(tipo_analisis=Especificacion.TipoAnalisis.LOTE)
    if not any({"mg", "humedad"} <= set(item.rangos) for item in existentes):
        version = (producto.especificaciones.aggregate(maxima=Max("version"))["maxima"] or 0) + 1
        Especificacion.objects.create(
            producto=producto, tipo_analisis=Especificacion.TipoAnalisis.LOTE,
            version=version, vigente_desde=date.today(),
            rangos={"mg": {"min": 80.0, "max": 100.0, "obligatorio": True},
                    "humedad": {"min": 0.0, "max": 16.0, "obligatorio": True},
                    "sng": {"min": 0.0, "max": 2.0, "obligatorio": True}},
            fuente="Fixture OPFLOW: rangos del preparador E2E de mantequilla; sin validez industrial.",
        )
    receta, materiales = Command()._preparar_materiales_envase(planta=planta, producto=producto, usuario=autor)
    orden, _ = OrdenProduccion.objects.get_or_create(
        sucursal=planta, codigo="OPFLOW-OP-MANT-01",
        defaults={"producto": producto, "cantidad_planificada": 40, "unidad": "kg",
                  "equipo": linea, "linea": linea.nombre,
                  "estado": OrdenProduccion.Estado.PROGRAMADA, "creada_por": autor,
                  "observacion": "Orden FICTICIA local de prueba. No representa producción ni compromiso comercial."},
    )
    if orden.producto_id != producto.id or orden.equipo_id != linea.id:
        raise RuntimeError("Existing butter test order is incompatible")
    print(f"OPFLOW_BUTTER_PREPARATION_OK: order={orden.codigo}; recipe={receta.id}; packaging_types={materiales}; no industrial lots or approvals")


seed()
