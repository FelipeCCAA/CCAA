"""Directed real HTTP contention and lost-response replay on synthetic stock."""
import concurrent.futures
import http.client
import json
import time
import uuid
import psycopg2
from load import RUNTIME, TARGET, call, stock_integrity, verify_cluster

verify_cluster()
accounts = json.loads((RUNTIME / "load-accounts.json").read_text())
tokens = json.loads((RUNTIME / "synthetic-sessions.json").read_text())
account = accounts[1]
target = dict(TARGET, dbname="op09_circuito")


def balance():
    with psycopg2.connect(**target) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT cantidad_fisica FROM inventario_existencia WHERE id=%s", (account["existence_a"],))
            return cur.fetchone()[0]


def payload(amount, source="existence_a", destination="location_b"):
    return {"existencia": account[source], "destino": account[destination], "cantidad": str(amount), "motivo": "OP09 carrera o respuesta perdida ficticia", "operacion_id": str(uuid.uuid4()), "documento_tipo": "OP09.PruebaHTTP", "documento_id": account["lot"]}


assert balance() == 10000, "Dedicated race source must start at its known balance"
first, second = payload(7500), payload(7500)
holder = psycopg2.connect(**target)
with holder.cursor() as cur:
    cur.execute("SELECT id FROM inventario_existencia WHERE id=%s FOR UPDATE", (account["existence_a"],))
blocked = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    jobs = [pool.submit(call, "POST", "/api/inventario/movimientos/trasladar/", tokens[accounts[i]["username"]], data) for i, data in [(1, first), (5, second)]]
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with psycopg2.connect(**target) as observer:
                with observer.cursor() as cur:
                    cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='op09_circuito' AND cardinality(pg_blocking_pids(pid)) > 0")
                    blocked = cur.fetchone()[0]
            if blocked >= 2:
                break
            time.sleep(.05)
    finally:
        holder.commit()
        holder.close()
    results = [job.result(timeout=15) for job in jobs]
assert blocked >= 2, "Both independent HTTP requests must actually contend in PostgreSQL"
assert sorted(result[0] for result in results) == [201, 409], [r[:2] for r in results]
assert balance() == 2500
status, body, _ = call("POST", "/api/inventario/movimientos/trasladar/", tokens[account["username"]], payload(7500, "existence_b", "location_a"))
assert status == 201 and balance() == 10000, (status, body)

# Send a complete request then intentionally discard its response. Prove the
# first commit occurred before retrying, rather than assuming a dropped send.
lost = payload(1)
connection = http.client.HTTPConnection("127.0.0.1", 8209, timeout=10)
connection.request("POST", "/api/inventario/movimientos/trasladar/", body=json.dumps(lost), headers={"Content-Type": "application/json", "Authorization": "Token " + tokens[account["username"]]})
connection.close()
committed = None
deadline = time.monotonic() + 5
while time.monotonic() < deadline:
    with psycopg2.connect(**target) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM inventario_movimientoinventario WHERE operacion_id=%s", (lost["operacion_id"],))
            committed = cur.fetchone()
    if committed:
        break
    time.sleep(.05)
assert committed and balance() == 9999, "Lost-response case needs a proven first commit"
status, body, _ = call("POST", "/api/inventario/movimientos/trasladar/", tokens[account["username"]], lost)
assert status == 200 and body["id"] == committed[0] and balance() == 9999
status, body, _ = call("POST", "/api/inventario/movimientos/trasladar/", tokens[account["username"]], payload(1, "existence_b", "location_a"))
assert status == 201 and balance() == 10000
assert not stock_integrity()["invalid_lots"]
report = {"http_concurrent_requests": 2, "postgres_blocked_connections_observed": blocked, "responses": [r[0] for r in results], "single_withdrawal": True, "lost_response_first_commit_proven": True, "lost_response_retry_status": 200, "same_movement_id": committed[0], "final_balance": 10000, "integrity": stock_integrity()}
(RUNTIME / "http-races.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("OP09_REAL_HTTP_RACES_OK " + json.dumps(report))
