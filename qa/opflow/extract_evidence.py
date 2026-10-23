"""Read-only operational evidence; execute in the dedicated Django shell.

Example: exec(Path('../qa/opflow/extract_evidence.py').read_text())
No HTTP, domain services, model saves, approval decisions or credential tables.
The collector records facts, never infers that an unexecuted route passed.
"""
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import importlib.util
import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection, transaction
from django.db.models import BinaryField, FileField


MODELS = {
    "maestros": ("Producto", "Silo", "Equipo", "FormatoEnvasado"),
    "recepcion": ("Recepcion", "ModuloRecepcion", "MovimientoSilo", "AtribucionRecepcion", "AnalisisSilo", "DespachoLeche"),
    "estandarizacion": ("ValeEstandarizacion", "ActoValeEstandarizacion", "CorreccionValeEstandarizacion"),
    "procesos": ("Proceso", "EtapaProceso", "RutaProducto", "CorridaCondensacion", "CorridaSecado", "CorridaDescremacion", "CorridaMantequilla", "ReservaSiloProceso", "EjecucionProceso", "EntradaProceso", "SalidaProceso", "EventoProceso", "AutorizacionReproceso"),
    "produccion": ("OrdenProduccion", "Lote", "CorreccionLote", "Analisis", "ControlProceso", "ControlProcesoLectura", "RegistroEnvase", "PalletProducto"),
    "calidad": ("RegistroCalidad", "Liberacion", "LiberacionProceso"),
    "inventario": ("Insumo", "Bodega", "Ubicacion", "LoteInventario", "Existencia", "MovimientoInventario", "ConsumoLoteProduccion", "ExistenciaProductoTerminado", "MovimientoProductoTerminado", "ClienteDespacho", "Despacho", "DetalleDespacho", "DetalleDespachoGranel", "UnidadRework", "MovimientoRework"),
}
ROUTES = (
    ("leche_granel", "Recepción → análisis y dos firmas → silo → despacho de leche"),
    ("polvo", "Recepción → vale → evaporación → secado → envase → Calidad → inventario → despacho"),
    ("precondensado", "Recepción → vale → evaporación → Calidad → despacho directo"),
    ("descremada", "Recepción → silo → descremado → Calidad → destino de descremada"),
    ("crema_directa", "Recepción → descremado → Calidad de crema → despacho directo"),
    ("mantequilla", "Crema del descremado → mantequilla → Calidad → cajas → inventario → despacho"),
    ("suero_externo", "Ingreso externo por pantalla → liberación → secado → Big Bag → inventario → despacho"),
    ("rework", "Segregación real → Calidad → habilitación física de Bodega → consumo en otra ejecución"),
)
EXCLUDED = {"password", "token", "token_hash", "secret", "archivo", "firma_imagen", "evidencia_firmada"}


def write_new(path, data):
    with path.open("x", encoding="utf-8") as output:
        json.dump(data, output, indent=2, ensure_ascii=False, cls=DjangoJSONEncoder)


def export_model(model):
    fields = [f for f in model._meta.concrete_fields if f.name not in EXCLUDED and not isinstance(f, (FileField, BinaryField))]
    names = [f.attname for f in fields]
    rows = list(model.objects.order_by(model._meta.pk.attname).values(*names))
    foreign_keys = {f.attname: f.remote_field.model._meta.label for f in fields if f.is_relation}
    # FK actor IDs are references only: never read auth.User, profiles or sessions.
    return {"table": model._meta.db_table, "count": len(rows), "fields": names, "foreign_keys": foreign_keys, "rows": rows}


def keyed(tables, label):
    return {r["id"]: r for r in tables[label]["rows"]}


def operational_views(tables):
    """Persisted IDs, explicit quantities and joins; no inferred physical recipe."""
    movements = keyed(tables, "recepcion.MovimientoSilo")
    attribution = defaultdict(list)
    for row in tables["recepcion.AtribucionRecepcion"]["rows"]:
        attribution[row["movimiento_id"]].append({"reception_id": row["recepcion_id"], "litres": row["litros"], "fifo_order": row["orden"], "unattributable_reason": row["origen_no_atribuible"]})
    fifo = []
    for movement in movements.values():
        parts = attribution[movement["id"]]
        if movement["tipo"] == "salida" or parts:
            attributed = sum((Decimal(str(p["litres"])) for p in parts), Decimal(0))
            fifo.append({"movement_id": movement["id"], "silo_id": movement["silo_id"], "origin_type": movement["origen_tipo"], "origin_id": movement["origen_id"], "operation_id": movement["operacion_id"], "litres": movement["litros"], "unit": "L", "attributions": parts, "attributed_litres": attributed, "quantity_matches": attributed == Decimal(str(movement["litros"]))})
    # Positive/negative book totals are observations, not initial-stock assumptions.
    silo_totals = defaultdict(Decimal)
    for row in movements.values():
        quantity = Decimal(str(row["litros"]))
        silo_totals[row["silo_id"]] += -quantity if row["tipo"] == "salida" else quantity
    executions = keyed(tables, "procesos.EjecucionProceso")
    stages = keyed(tables, "procesos.EtapaProceso")
    inputs, outputs = defaultdict(list), defaultdict(list)
    for row in tables["procesos.EntradaProceso"]["rows"]:
        inputs[row["ejecucion_id"]].append(row)
    for row in tables["procesos.SalidaProceso"]["rows"]:
        outputs[row["ejecucion_id"]].append(row)
    chains = [{"execution_id": row["id"], "stage_id": row["etapa_id"], "stage_type": stages.get(row["etapa_id"], {}).get("tipo"), "equipment_id": row.get("equipo_id"), "responsible_id": row.get("responsable_id"), "vale_id": row.get("vale_id"), "inputs": inputs[row["id"]], "outputs": outputs[row["id"]]} for row in executions.values()]
    envases = keyed(tables, "produccion.RegistroEnvase")
    pt = defaultdict(list)
    for row in tables["inventario.ExistenciaProductoTerminado"]["rows"]:
        pt[row["pallet_id"]].append(row)
    ptmoves, dispatch_details = defaultdict(list), defaultdict(list)
    for row in tables["inventario.MovimientoProductoTerminado"]["rows"]:
        ptmoves[row["pallet_id"]].append(row)
    for row in tables["inventario.DetalleDespacho"]["rows"]:
        dispatch_details[row["pallet_id"]].append(row)
    pallets = [{"pallet_id": row["id"], "code": row["codigo"], "lot_id": envases[row["envase_id"]]["lote_id"], "packaging_record_id": row["envase_id"], "units": row["unidades"], "net_quantity": row["kg_neto"], "unit": "kg", "logistic_type": row["tipo_unidad_logistica"], "state": row["estado"], "existences": pt[row["id"]], "movements": ptmoves[row["id"]], "dispatch_details": dispatch_details[row["id"]]} for row in tables["produccion.PalletProducto"]["rows"]]
    return {"fifo_attributions": fifo, "silo_book_balances": [{"silo_id": key, "quantity": amount, "unit": "L"} for key, amount in sorted(silo_totals.items())], "process_chains": chains, "packaged_units": pallets}


def main():
    database = settings.DATABASES["default"]
    if not (settings.DJANGO_ENV == "test" and database["ENGINE"] == "django.db.backends.postgresql" and database["NAME"] == "opflow_circuito" and database["HOST"] == "127.0.0.1" and str(database["PORT"]) == "55479"):
        raise RuntimeError("Evidence collector refuses every database except fictitious OPFLOW")
    repo = Path(settings.BASE_DIR).parent
    spec = importlib.util.spec_from_file_location("opflow_isolation", repo / "qa/opflow/manage_isolated.py")
    isolation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(isolation)
    identity = isolation.verify_cluster()
    runtime = isolation.RUNTIME
    tables = {}
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cursor.execute("SET LOCAL statement_timeout='10000ms'")
            cursor.execute("SHOW transaction_read_only")
            if cursor.fetchone()[0] != "on":
                raise RuntimeError("Read-only evidence transaction was not enforced")
        for app, models in MODELS.items():
            for name in models:
                label = f"{app}.{name}"
                tables[label] = export_model(apps.get_model(app, name))
        views = operational_views(tables)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = runtime / f"operational-ledger-{stamp}.json"
    write_new(path, {"collected_utc": stamp, "isolation": {"role": identity["role"], "host": identity["host"], "port": identity["port"], "database": database["NAME"]}, "read_only_repeatable_read": True, "scope": "Fictitious database facts only; no UI route pass inferred; no auth/profiles/sessions/passwords/private-file contents exported", "units": {"MovimientoSilo": "L", "AtribucionRecepcion": "L", "EntradaProceso": "explicit unidad field", "SalidaProceso": "explicit unidad field", "PalletProducto": "kg", "UnidadRework": "kg", "MovimientoRework": "kg", "Existencia": "Insumo.unidad via lote.insumo_id"}, "tables": tables, "views": views})
    coverage = runtime / "operational-coverage.json"
    if not coverage.exists():
        write_new(coverage, {"status": "NOEJECUTADO", "routes": [{"id": key, "description": text, "status": "NOEJECUTADO", "ui_action_evidence": [], "ledger_reference": None, "missing_steps": []} for key, text in ROUTES], "rule": "Only root may update after observed UI actions and ledger reconciliation; existing coverage is never overwritten by collector", "notes": "Initial masters/orders/packaging supplies are prerequisites, never evidence of executed receipt, production or approval"})
    print(json.dumps({"evidence": path.name, "tables": len(tables), "rows": sum(item["count"] for item in tables.values()), "coverage": coverage.name, "route_pass_inferred": False}))


main()
