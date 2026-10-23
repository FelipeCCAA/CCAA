"""Descremado fixture only: no operational stock, users or Planning records.

Values copied from produccion/management/commands/preparar_circuito_descremado.py.
They are synthetic test configuration, not approved industrial specifications.
Run through qa/opflow/manage_isolated.py shell in the fresh OPFLOW database.
"""
from datetime import date

from django.conf import settings
from django.db import transaction

from maestros.models import Equipo, Especificacion, Mandante, Producto
from procesos.models import Proceso, RutaProducto
from usuarios.models import Sucursal


@transaction.atomic
def seed():
    db = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and db["NAME"] == "opflow_circuito"
            and db["HOST"] == "127.0.0.1" and str(db["PORT"]) == "55479"):
        raise RuntimeError("Descremado masters refuse every database except OPFLOW")
    planta = Sucursal.objects.get(activa=True)
    if planta.codigo != "INTERNA" or planta.empresa.rut != "TENANT-TEST":
        raise RuntimeError("Unexpected fictitious plant")
    mandante = Mandante.objects.get(empresa=planta.empresa, codigo_cliente=Mandante.Cliente.NO_DEFINIDO)
    equipo, _ = Equipo.objects.get_or_create(
        sucursal=planta, codigo="des-01",
        defaults={"nombre": "Descremadora DES-01 FICTICIA OPFLOW", "sigla": "D1",
                  "tipo": Equipo.Tipo.DESCREMADORA, "consume_leche": False,
                  "consume_materiales": False, "orden": 25, "activo": True},
    )
    if not equipo.activo or equipo.tipo != Equipo.Tipo.DESCREMADORA:
        raise RuntimeError("Incompatible existing descremadora")
    descremada, _ = Producto.objects.get_or_create(
        mandante=mandante, nombre="Leche descremada líquida intermedia CCAA",
        defaults={"naturaleza_comercial": Producto.NaturalezaComercial.PRODUCTO_PROPIO,
                  "categoria": Producto.Categoria.LECHE_FLUIDA, "tipo": Producto.TipoProducto.DESCREMADA,
                  "formato": Producto.Formato.GRANEL, "mercado": Producto.Mercado.LOCAL,
                  "familia": Producto.Familia.LIQUIDO, "naturaleza": Producto.Naturaleza.INTERMEDIO,
                  "unidad_base": Producto.Unidad.L},
    )
    polvo = Proceso.objects.get(codigo="ruta-polvo", activo=True)
    mantequilla = Proceso.objects.get(codigo="ruta-mantequilla", activo=True)
    RutaProducto.objects.get_or_create(
        sucursal=planta, producto=descremada, proceso=polvo,
        defaults={"prioridad": 1, "destino_final": RutaProducto.DestinoFinal.ENVASADO,
                  "destino": "Estandarización → Evaporación → Secado → Envasado",
                  "observaciones": "Fixture ficticia OPFLOW, sin validez industrial", "activa": True},
    )
    Especificacion.objects.get_or_create(
        producto=descremada, tipo_analisis=Especificacion.TipoAnalisis.SILO, version=1,
        defaults={"vigente_desde": date(2026, 1, 1),
                  "rangos": {"mg": {"min": 0.04, "max": 0.07, "obligatorio": True},
                             "sng": {"min": 8.6, "max": 9.2, "obligatorio": True},
                             "ph": {"min": 6.5, "max": 6.8, "obligatorio": True}},
                  "fuente": "Fixture OPFLOW: valores del preparador E2E existente; no especificación CCAA aprobada."},
    )
    cremas = [Producto.objects.get(mandante=mandante, nombre="Crema fresca 42% Granel CA",
                                  familia=Producto.Familia.CREMA,
                                  naturaleza=Producto.Naturaleza.INTERMEDIO, activo=True)]
    for crema in cremas:
        RutaProducto.objects.get_or_create(
            sucursal=planta, producto=crema, proceso=mantequilla,
            defaults={"prioridad": 2, "destino_final": RutaProducto.DestinoFinal.ENVASADO,
                      "destino": "Mantequilla → Calidad → Envasado",
                      "observaciones": "Fixture ficticia OPFLOW, sin validez industrial", "activa": True},
        )
        Especificacion.objects.get_or_create(
            producto=crema, tipo_analisis=Especificacion.TipoAnalisis.SILO, version=1,
            defaults={"vigente_desde": date(2026, 1, 1),
                      "rangos": {"mg": {"min": 40.0, "max": 44.0, "obligatorio": True},
                                 "ph": {"min": 6.4, "max": 6.8, "obligatorio": True}},
                      "fuente": "Fixture OPFLOW: valores del preparador E2E existente; no especificación CCAA aprobada."},
        )
    print("OPFLOW_DESCREMADO_MASTERS_OK: only Equipo/Producto/RutaProducto/Especificacion; no industrial movements, users or Planning")


seed()
