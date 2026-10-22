"""Authenticated recovery check against restored API 8219 only."""
import hashlib
import http.client
import json
import time
import uuid
from datetime import datetime, timezone
import psycopg2
from manage_isolated import RUNTIME, TARGET, verify_cluster

verify_cluster()
started = time.perf_counter()
account = json.loads((RUNTIME / "load-accounts.json").read_text())[1]
token = json.loads((RUNTIME / "synthetic-sessions.json").read_text())[account["username"]]


def call(method, path, data=None):
    assert path.startswith("/api/")
    connection = http.client.HTTPConnection("127.0.0.1", 8219, timeout=15)
    connection.request(method, path, body=json.dumps(data) if data else None, headers={"Authorization": "Token " + token, "Content-Type": "application/json"})
    response = connection.getresponse()
    raw = response.read()
    status = response.status
    connection.close()
    return status, raw


status, body = call("GET", "/api/salud/listo/")
assert status == 200, (status, body)
status, body = call("GET", "/api/usuarios/yo/")
assert status == 200 and json.loads(body)["username"] == account["username"], (status, body)
evidence = json.loads((RUNTIME / "evidence-upload.json").read_text())
status, content = call("GET", evidence["path"])
assert status == 200 and hashlib.sha256(content).hexdigest() == evidence["sha256"]


def balances(database):
    with psycopg2.connect(**dict(TARGET, dbname=database)) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id,cantidad_fisica,cantidad_reservada FROM inventario_existencia WHERE lote_id=%s ORDER BY id", (account["lot"],))
            return cur.fetchall()


source_before, target_before = balances("op09_circuito"), balances("op09_restaurada")
assert source_before == target_before
payload = {"existencia": account["existence_a"], "destino": account["location_b"], "cantidad": "1.000", "motivo": "OP09 operación tras restauración ficticia", "operacion_id": str(uuid.uuid4()), "documento_tipo": "OP09.Restauracion", "documento_id": account["lot"]}
status, body = call("POST", "/api/inventario/movimientos/trasladar/", payload)
assert status == 201, (status, body)
status2, body2 = call("POST", "/api/inventario/movimientos/trasladar/", payload)
assert status2 == 200 and json.loads(body)["id"] == json.loads(body2)["id"]
target_after = balances("op09_restaurada")
assert source_before == balances("op09_circuito")
assert sum(row[1] for row in target_before) == sum(row[1] for row in target_after) == 10000
assert all(row[1] >= 0 and row[2] == 0 for row in target_after)
assert target_before != target_after
freeze = json.loads((RUNTIME / "freeze-source.json").read_text(encoding="utf-8-sig"))
elapsed_since_freeze = (datetime.now(timezone.utc) - datetime.fromisoformat(freeze["timestamp_utc"])).total_seconds()
report = {"ready": True, "authenticated_user": account["username"], "private_download_sha256_matches": True, "transfer_status": status, "repeat_status": status2, "stock_conserved": True, "source_unchanged": True, "seconds": time.perf_counter() - started, "elapsed_since_freeze_seconds_including_manual_test_orchestration": elapsed_since_freeze, "api": "127.0.0.1:8219", "database": "op09_restaurada"}
(RUNTIME / "restore-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("OP09_RESTORED_OPERATION_OK " + json.dumps(report))
