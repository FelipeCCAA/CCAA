"""Bounded local OP09 HTTP workload; no production URL or credentials accepted."""
import collections
import concurrent.futures
import ctypes
from ctypes import wintypes
import http.client
import json
import math
import random
import threading
import time
import uuid

import psycopg2
from manage_isolated import RUNTIME, TARGET, verify_cluster

LOCK = threading.Lock()
STOP = threading.Event()
ROWS = []
FAILURES = []
ACCOUNTS = []
OPERATIONS = set()


def call(method, path, token=None, data=None):
    assert path.startswith("/api/") and "http" not in path
    conn = http.client.HTTPConnection("127.0.0.1", 8209, timeout=10)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Token " + token
    started = time.perf_counter()
    try:
        conn.request(method, path, body=json.dumps(data) if data is not None else None, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        try:
            body = json.loads(raw)
        except ValueError:
            body = {}
        return response.status, body, time.perf_counter() - started
    except (OSError, http.client.HTTPException):
        return 0, {}, time.perf_counter() - started
    finally:
        conn.close()


def identity(account):
    token = json.loads((RUNTIME / "synthetic-sessions.json").read_text(encoding="utf-8"))[account["username"]]
    status, body, elapsed = call("GET", "/api/usuarios/yo/", token)
    if status != 200:
        raise RuntimeError(f"Login {account['username']}: HTTP {status}; {body.get('detail', body.get('error', 'not accepted'))}")
    account["token"] = token
    if account["area"] == "recepcion":
        status, draft, _ = call("POST", "/api/recepcion/recepciones/crear-borrador/", account["token"], {})
        if status == 409:
            draft = draft.get("borrador", {})
        elif status != 201:
            raise RuntimeError(f"Reception fixture {account['username']}: HTTP {status}")
        account["draft"] = draft["id"]


def stock_integrity():
    target = dict(TARGET, dbname="op09_circuito")
    with psycopg2.connect(**target) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT l.codigo,sum(e.cantidad_fisica),sum(e.cantidad_reservada),min(e.cantidad_fisica) FROM inventario_loteinventario l JOIN inventario_existencia e ON e.lote_id=l.id WHERE l.codigo LIKE 'op09_carga_%' GROUP BY l.codigo")
            lots = cur.fetchall()
            invalid = [r[0] for r in lots if r[1] != 10000 or r[2] != 0 or r[3] < 0]
            if len(lots) != 18:
                invalid.append("expected_18_synthetic_lots")
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname='op09_circuito'")
            connections = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM inventario_movimientoinventario WHERE documento_tipo='OP09.Carga'")
            moves = cur.fetchone()[0]
    return {"invalid_lots": invalid, "lots": len(lots), "connections": connections, "movements": moves}


class Memory(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [(n, ctypes.c_ulonglong) for n in ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")]


def resources():
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Cannot measure host RAM")
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("Cannot measure host CPU")
    def ticks(value):
        return (value.dwHighDateTime << 32) | value.dwLowDateTime
    return {"ram_percent": memory.load, "total_ram": memory.total_phys, "idle": ticks(idle), "total": ticks(kernel) + ticks(user)}


def percentile(values, quantile=0.95):
    return sorted(values)[max(0, math.ceil(len(values) * quantile) - 1)] if values else None


def worker(account, deadline):
    rng = random.Random(account["username"])
    index = 0
    reads = {
        "recepcion": ["/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
        "bodega": ["/api/inventario/existencias/?page_size=25"],
        "calidad": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
        "condensacion": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
    }[account["area"]]
    direction = False
    while time.monotonic() < deadline and not STOP.is_set():
        method, path, data, expected = "GET", reads[index % len(reads)], None, {200}
        operation = None
        if index % 4 == 3 and account["area"] == "recepcion":
            method, path = "PATCH", f"/api/recepcion/recepciones/{account['draft']}/guardar-borrador/"
            data = {"observacion": f"OP09 carga ficticia {index}"}
        elif index % 4 == 3 and account["area"] == "bodega":
            operation = str(uuid.uuid4())
            method, path, expected = "POST", "/api/inventario/movimientos/trasladar/", {201}
            data = {"existencia": account["existence_b"] if direction else account["existence_a"], "destino": account["location_a"] if direction else account["location_b"], "cantidad": "1.000", "motivo": "OP09 traslado ficticio", "operacion_id": operation, "documento_tipo": "OP09.Carga", "documento_id": account["lot"]}
        status, body, elapsed = call(method, path, account["token"], data)
        ok = status in expected
        with LOCK:
            ROWS.append((method, elapsed, status, ok))
            if not ok and len(FAILURES) < 10:
                FAILURES.append({"account": account["username"], "method": method, "path": path, "status": status, "body": body})
            if operation and ok:
                OPERATIONS.add(operation)
        if operation and not ok:
            # No iniciar un movimiento distinto si el primero quedó incierto.
            STOP.set()
        if operation and ok:
            direction = not direction
            if index % 20 == 3:
                repeat_status, repeat_body, repeat_time = call(method, path, account["token"], data)
                repeated = repeat_status == 200 and repeat_body.get("id") == body.get("id")
                with LOCK:
                    ROWS.append((method, repeat_time, repeat_status, repeated))
                    if not repeated:
                        FAILURES.append({"error": "Idempotent replay differs", "status": repeat_status})
                        STOP.set()
        index += 1
        STOP.wait(rng.uniform(1, 3))


def stage(name, users, seconds):
    start = time.monotonic()
    deadline = start + seconds
    with LOCK:
        ROWS.clear()
        FAILURES.clear()
    before = stock_integrity()
    old = resources()
    samples = []
    reason = None
    high_cpu = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
        jobs = [pool.submit(worker, account, deadline) for account in ACCOUNTS[:users]]
        while time.monotonic() < deadline and not STOP.is_set():
            STOP.wait(min(30, max(0, deadline - time.monotonic())))
            current = resources()
            cpu = 100 * (1 - (current["idle"] - old["idle"]) / max(1, current["total"] - old["total"]))
            old = current
            integrity = stock_integrity()
            with LOCK:
                snapshot = list(ROWS)
            errors = sum(not row[3] for row in snapshot)
            sample = {"elapsed": round(time.monotonic() - start, 1), "requests": len(snapshot), "errors": errors, "cpu_percent": round(cpu, 2), "ram_percent": current["ram_percent"], **integrity}
            sample["read_p95"] = percentile([row[1] for row in snapshot if row[0] == "GET"])
            sample["write_p95"] = percentile([row[1] for row in snapshot if row[0] != "GET"])
            samples.append(sample)
            print(json.dumps({"stage": name, "users": users, **sample}), flush=True)
            high_cpu = high_cpu + 1 if cpu > 80 else 0
            if integrity["invalid_lots"]:
                reason = "inventory_invariant"
            elif current["ram_percent"] > 85 or high_cpu >= 2 or integrity["connections"] > 80:
                reason = "host_saturation"
            elif len(snapshot) >= 100 and errors / len(snapshot) >= 0.01:
                reason = "unexpected_error_budget"
            if reason:
                STOP.set()
        for job in jobs:
            job.result()
    if STOP.is_set() and reason is None:
        reason = "stopped_after_uncertain_write_or_replay"
    elapsed = time.monotonic() - start
    reads = [r[1] for r in ROWS if r[0] == "GET"]
    writes = [r[1] for r in ROWS if r[0] != "GET"]
    errors = sum(not r[3] for r in ROWS)
    result = {"name": name, "users": users, "planned_seconds": seconds, "actual_seconds": round(elapsed, 3), "requests": len(ROWS), "rps": len(ROWS) / max(1, elapsed), "read_p95": percentile(reads), "write_p95": percentile(writes), "writes": len(writes), "errors": errors, "status_counts": dict(collections.Counter(str(r[2]) for r in ROWS)), "samples": samples, "failures": FAILURES[:10], "stop_reason": reason, "integrity_before": before, "integrity_after": stock_integrity()}
    result["passed"] = elapsed >= seconds and not reason and errors / max(1, len(ROWS)) < .01 and result["read_p95"] is not None and result["read_p95"] < 1 and result["write_p95"] is not None and result["write_p95"] < 2 and not result["integrity_after"]["invalid_lots"]
    (RUNTIME / f"load-{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print("OP09_LOAD_ISOLATION " + json.dumps(verify_cluster()), flush=True)
    ACCOUNTS = json.loads((RUNTIME / "load-accounts.json").read_text(encoding="utf-8"))
    results, stable = [], None
    try:
        assert stock_integrity()["movements"] == 0, "Prior load exists; preserve results instead of silently repeating"
        for account in ACCOUNTS[:10]:
            identity(account)
        results.append(stage("warmup", 10, 300))
        if STOP.is_set() or not results[-1]["passed"]:
            raise RuntimeError("Warmup stopped by safety guard")
        for count in [10, 25, 50, 70]:
            for account in ACCOUNTS[:count]:
                if "token" not in account:
                    identity(account)
            result = stage(f"users-{count}", count, 600)
            results.append(result)
            if not result["passed"]:
                break
            stable = count
        if stable and not STOP.is_set():
            results.append(stage("soak", stable, 1800))
    except Exception as error:
        results.append({"error": str(error), "passed": False})
    finally:
        with psycopg2.connect(**dict(TARGET, dbname="op09_circuito")) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT operacion_id::text FROM inventario_movimientoinventario WHERE documento_tipo='OP09.Carga'")
                database_operations = {row[0] for row in cur.fetchall()}
        final = {"results": results, "stable_users": stable, "unique_transfer_operations": len(OPERATIONS), "database_operations_match_http_successes": database_operations == OPERATIONS, "integrity": stock_integrity(), "scope": "local Django development server; 70 synthetic pre-authenticated accounts, real session hashes and authorization; login burst tested separately, no throttle disabled; 1-3 second think time; no production capacity certification"}
        (RUNTIME / "load-summary.json").write_text(json.dumps(final, indent=2), encoding="utf-8")
        for account in ACCOUNTS:
            if "token" in account:
                call("POST", "/api/usuarios/logout/", account["token"], {})
        print("OP09_LOAD_FINISHED " + json.dumps({"stable_users": stable, "stages": len(results)}), flush=True)
    raise SystemExit(0 if len(results) == 6 and all(r.get("passed") for r in results) and final["database_operations_match_http_successes"] else 1)
