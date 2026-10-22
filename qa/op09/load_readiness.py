"""Verify real role-authorized requests before spending time on load."""
import json
import uuid
from load import RUNTIME, call, identity, stock_integrity, verify_cluster

verify_cluster()
accounts = json.loads((RUNTIME / "load-accounts.json").read_text())[:4]
results = []
paths = {
    "recepcion": ["/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
    "bodega": ["/api/inventario/existencias/?page_size=25"],
    "calidad": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
    "condensacion": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
}
for account in accounts:
    identity(account)
    for path in paths[account["area"]]:
        status, _, elapsed = call("GET", path, account["token"])
        results.append({"area": account["area"], "path": path, "status": status, "seconds": elapsed})
        assert status == 200, results[-1]
reception, warehouse = accounts[:2]
status, body, _ = call("PATCH", f"/api/recepcion/recepciones/{reception['draft']}/guardar-borrador/", reception["token"], {"observacion": "OP09 prueba de escritura ficticia"})
assert status == 200 and body["observacion"] == "OP09 prueba de escritura ficticia"
for source, target in [("existence_a", "location_b"), ("existence_b", "location_a")]:
    payload = {"existencia": warehouse[source], "destino": warehouse[target], "cantidad": "1.000", "motivo": "OP09 smoke ficticio", "documento_tipo": "OP09.Smoke", "documento_id": warehouse["lot"], "operacion_id": str(uuid.uuid4())}
    status, body, _ = call("POST", "/api/inventario/movimientos/trasladar/", warehouse["token"], payload)
    assert status == 201, (status, body)
    status2, repeated, _ = call("POST", "/api/inventario/movimientos/trasladar/", warehouse["token"], payload)
    assert status2 == 200 and repeated["id"] == body["id"], (status2, repeated)
integrity = stock_integrity()
assert not integrity["invalid_lots"]
report = {"reads": results, "draft_write": True, "transfers_and_replays": 4, "integrity": integrity}
(RUNTIME / "load-readiness-final.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("OP09_LOAD_READINESS_OK " + json.dumps({"reads": len(results), "draft_write": True, "transfers_and_replays": 4, "integrity": integrity}))
