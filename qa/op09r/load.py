"""OP09 retry: bounded real HTTP load, durable intentions, exact reconciliation.

Only this newly prepared fictitious cluster/API is accepted. Importing does not
connect or issue requests. Failed stages remain failed after recovery.
"""
import collections
import concurrent.futures
import ctypes
from ctypes import wintypes
from decimal import Decimal
import http.client
import json
import math
from pathlib import Path
import random
import threading
import time
import uuid

import psycopg2
from manage_isolated import RUNTIME, TARGET, verify_cluster

DATABASE = "op09r_carga"
DOCUMENT = "OP09R.Carga"
PORT = 8229
READS = {
    "recepcion": ["/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
    "bodega": ["/api/inventario/existencias/?page_size=25"],
    "calidad": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
    "condensacion": ["/api/produccion/resumen/", "/api/recepcion/ocupacion/", "/api/inventario/existencias/?page_size=25"],
}


class Recorder:
    """Exclusive, append-only evidence; callers must never supply secrets."""

    def __init__(self, path):
        self.lock = threading.RLock()
        self.file = Path(path).open("x", encoding="utf-8")
        self.sequence = 0
        self.intents = {}
        self.results = []

    def record(self, kind, **fields):
        with self.lock:
            self.sequence += 1
            row = {"sequence": self.sequence, "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "kind": kind, **fields}
            self.file.write(json.dumps(row, ensure_ascii=False) + "\n")
            self.file.flush()
            return row

    def intent(self, *, stage, account, method, path, payload=None, replay=False, recovery=False):
        request_id = str(uuid.uuid4())
        row = self.record("intent", request_id=request_id, stage=stage, account=account, method=method, path=path, payload=payload, operation_id=(payload or {}).get("operacion_id"), replay=replay, recovery=recovery)
        with self.lock:
            self.intents[request_id] = row
        return request_id

    def result(self, request_id, response, expected):
        status, body, elapsed, error = response
        row = self.record("result", request_id=request_id, status=status, elapsed_seconds=elapsed, exception_class=error, confirmed_id=body.get("id"), ok=status in expected)
        with self.lock:
            self.results.append(row)
        return row

    def close(self):
        self.file.close()


def call(method, path, token=None, data=None):
    if not path.startswith("/api/") or "http" in path:
        raise ValueError("Only local API paths accepted")
    conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
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
            if not isinstance(body, dict):
                body = {}
        except ValueError:
            body = {}
        return response.status, body, time.perf_counter() - started, None
    except (OSError, http.client.HTTPException) as error:
        return 0, {}, time.perf_counter() - started, type(error).__name__
    finally:
        conn.close()


class Memory(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [(n, ctypes.c_ulonglong) for n in ("total_phys", "avail_phys", "total_page", "avail_page", "total_virtual", "avail_virtual", "avail_extended")]


def resources():
    memory = Memory()
    memory.length = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise OSError("Cannot measure RAM")
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError("Cannot measure CPU")

    def ticks(value):
        return (value.dwHighDateTime << 32) | value.dwLowDateTime
    return {"ram_percent": memory.load, "total_ram": memory.total_phys, "idle": ticks(idle), "total": ticks(kernel) + ticks(user)}


def percentile(values):
    return sorted(values)[max(0, math.ceil(len(values) * .95) - 1)] if values else None


def snapshot():
    """One repeatable-read snapshot: no transient ledger/stock disagreement."""
    with psycopg2.connect(**dict(TARGET, dbname=DATABASE), connect_timeout=5) as conn:
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='5000ms'")
            cur.execute("SELECT l.id,l.codigo,e.id,e.ubicacion_id,e.cantidad_fisica,e.cantidad_reservada FROM inventario_loteinventario l LEFT JOIN inventario_existencia e ON e.lote_id=l.id WHERE l.codigo LIKE 'op09r_carga_%' ORDER BY l.id,e.ubicacion_id")
            balances = [{"lot": row[0], "code": row[1], "existence": row[2], "location": row[3], "physical": str(row[4]), "reserved": str(row[5])} for row in cur.fetchall()]
            cur.execute("SELECT id,operacion_id::text,tipo,lote_id,origen_id,destino_id,cantidad,documento_tipo,documento_id,usuario_id,motivo FROM inventario_movimientoinventario WHERE documento_tipo=%s ORDER BY id", [DOCUMENT])
            keys = ("id", "operation_id", "type", "lot", "origin", "destination", "quantity", "document_type", "document_id", "user", "reason")
            moves = [dict(zip(keys, (*r[:6], str(r[6]), *r[7:]))) for r in cur.fetchall()]
            cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s", [DATABASE])
            connections = cur.fetchone()[0]
    return {"balances": balances, "movements": moves, "connections": connections}


def integrity(current, baseline):
    expected = {(r["lot"], r["location"]): Decimal(r["physical"]) for r in baseline["balances"]}
    lots = collections.defaultdict(Decimal)
    invalid = []
    base_ids = {m["id"] for m in baseline["movements"]}
    for move in current["movements"]:
        if move["id"] not in base_ids:
            if move["type"] != "traslado":
                invalid.append(f"unexpected_type:{move['id']}")
                continue
            quantity = Decimal(move["quantity"])
            origin, destination = (move["lot"], move["origin"]), (move["lot"], move["destination"])
            expected[origin] = expected.get(origin, Decimal(0)) - quantity
            expected[destination] = expected.get(destination, Decimal(0)) + quantity
    seen = set()
    for row in current["balances"]:
        key = (row["lot"], row["location"])
        seen.add(key)
        if row["existence"] is None:
            invalid.append(f"missing_existence:{row['lot']}")
            continue
        physical, reserved = Decimal(row["physical"]), Decimal(row["reserved"])
        lots[row["lot"]] += physical
        if physical != expected.get(key, Decimal(0)) or physical < 0 or reserved != 0:
            invalid.append(f"balance:{row['lot']}:{row['location']}")
    invalid.extend(f"missing_location:{lot}:{location}" for lot, location in expected.keys() - seen)
    invalid.extend(f"lot_total:{lot}" for lot, total in lots.items() if total != Decimal(10000))
    if len(lots) != 18:
        invalid.append("expected_18_lots")
    return {"invalid": invalid, "lots": len(lots), "locations": len(seen), "movements": len(current["movements"]), "connections": current["connections"]}


class Workload:
    def __init__(self, recorder, baseline, accounts):
        self.recorder, self.baseline, self.accounts = recorder, baseline, accounts
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.reason = None
        self.rows = []
        self.directions = {}

    def halt(self, reason):
        with self.lock:
            if self.reason is None:
                self.reason = reason
                self.recorder.record("stop", reason=reason)
            self.stop.set()

    def request(self, stage, account, method, path, payload=None, expected=(200,), replay=False, recovery=False):
        # The STOP transition and issuance of a new intention are serialized.
        with self.lock:
            if self.stop.is_set() and not recovery:
                return None
            request_id = self.recorder.intent(stage=stage, account=account["username"], method=method, path=path, payload=payload, replay=replay, recovery=recovery)
        response = call(method, path, account["token"], payload)
        row = self.recorder.result(request_id, response, expected)
        with self.lock:
            if not recovery:
                self.rows.append((method, row["elapsed_seconds"], row["status"], row["ok"]))
        if method != "GET" and not row["ok"] and not recovery:
            self.halt("uncertain_or_failed_write")
        return response

    def prepare(self, accounts):
        for account in accounts:
            response = self.request("setup", account, "GET", "/api/usuarios/yo/")
            if response is None or response[0] != 200:
                raise RuntimeError("Synthetic identity rejected")
            account["user_id"] = response[1].get("id")
            if account["area"] == "recepcion" and "draft" not in account:
                response = self.request("setup", account, "POST", "/api/recepcion/recepciones/crear-borrador/", {}, expected=(201,))
                if response is None or response[0] != 201:
                    raise RuntimeError("Expected new fictitious reception draft")
                account["draft"] = response[1]["id"]

    def worker(self, stage, account, deadline):
        rng, index = random.Random(account["username"]), 0
        try:
            while time.monotonic() < deadline and not self.stop.is_set():
                method, path, payload, expected = "GET", READS[account["area"]][index % len(READS[account["area"]])], None, (200,)
                operation = None
                if index % 4 == 3 and account["area"] == "recepcion":
                    method, path = "PATCH", f"/api/recepcion/recepciones/{account['draft']}/guardar-borrador/"
                    payload = {"observacion": f"OP09R ficticio {stage} {index}"}
                elif index % 4 == 3 and account["area"] == "bodega":
                    direction = self.directions.get(account["username"], False)
                    operation = str(uuid.uuid4())
                    method, path, expected = "POST", "/api/inventario/movimientos/trasladar/", (201,)
                    payload = {"existencia": account["existence_b"] if direction else account["existence_a"], "destino": account["location_a"] if direction else account["location_b"], "cantidad": "1.000", "motivo": "OP09R traslado ficticio", "operacion_id": operation, "documento_tipo": DOCUMENT, "documento_id": account["lot"]}
                response = self.request(stage, account, method, path, payload, expected)
                if response is None:
                    break
                if method == "PATCH" and response[0] == 200 and response[1].get("observacion") != payload["observacion"]:
                    self.halt("draft_payload_mismatch")
                if operation and response[0] == 201:
                    self.directions[account["username"]] = not direction
                    if index % 20 == 3 and not self.stop.is_set():
                        repeated = self.request(stage, account, method, path, payload, (200,), replay=True)
                        if repeated is not None and (repeated[0] != 200 or repeated[1].get("id") != response[1].get("id")):
                            self.halt("idempotent_replay_differs")
                index += 1
                self.stop.wait(rng.uniform(1, 3))
        except Exception as error:
            self.recorder.record("worker_exception", account=account["username"], stage=stage, exception_class=type(error).__name__)
            self.halt("worker_exception")

    def stage(self, name, users, seconds):
        if seconds not in (300, 600, 1800) or users not in (10, 25, 50, 70):
            raise ValueError("Unapproved load level/duration")
        output = RUNTIME / f"load-{name}.json"
        if output.exists():
            raise RuntimeError("Preserve previous stage evidence")
        self.rows = []
        start, samples, failure = time.monotonic(), [], None
        deadline, high_cpu = start + seconds, 0
        old, last_cpu = resources(), start
        before = snapshot()
        self.recorder.record("stage_start", stage=name, users=users, planned_seconds=seconds)
        try:
            if old["ram_percent"] > 85 or integrity(before, self.baseline)["invalid"]:
                self.halt("preflight_resources_or_inventory")
            if not self.stop.is_set():
                with concurrent.futures.ThreadPoolExecutor(max_workers=users) as pool:
                    jobs = [pool.submit(self.worker, name, a, deadline) for a in self.accounts[:users]]
                    while time.monotonic() < deadline and not self.stop.is_set():
                        self.stop.wait(min(5, max(0, deadline - time.monotonic())))
                        current = resources()
                        if current["ram_percent"] > 85:
                            self.halt("host_ram_above_85")
                        now = time.monotonic()
                        if now - last_cpu >= 30 or now >= deadline or self.stop.is_set():
                            cpu = 100 * (1 - (current["idle"] - old["idle"]) / max(1, current["total"] - old["total"]))
                            old, last_cpu = current, now
                            check = integrity(snapshot(), self.baseline)
                            with self.lock:
                                rows = list(self.rows)
                            errors = sum(not row[3] for row in rows)
                            sample = {"elapsed": round(now - start, 3), "requests": len(rows), "errors": errors, "cpu_percent": round(cpu, 2), "ram_percent": current["ram_percent"], "read_p95": percentile([r[1] for r in rows if r[0] == "GET"]), "write_p95": percentile([r[1] for r in rows if r[0] != "GET"]), **check}
                            samples.append(sample)
                            self.recorder.record("sample", stage=name, **sample)
                            print(json.dumps({"stage": name, "users": users, **sample}), flush=True)
                            high_cpu = high_cpu + 1 if cpu > 80 else 0
                            if check["invalid"]:
                                self.halt("inventory_invariant")
                            elif high_cpu >= 2 or check["connections"] > 80:
                                self.halt("host_cpu_or_connections")
                            elif len(rows) >= 100 and errors / len(rows) >= .01:
                                self.halt("unexpected_error_budget")
                    for job in jobs:
                        job.result()
        except Exception as error:
            failure = type(error).__name__
            self.halt("stage_exception")
        finally:
            elapsed = time.monotonic() - start
            with self.lock:
                rows = list(self.rows)
            reads, writes = [r[1] for r in rows if r[0] == "GET"], [r[1] for r in rows if r[0] != "GET"]
            errors = sum(not r[3] for r in rows)
            result = {"name": name, "users": users, "planned_seconds": seconds, "actual_seconds": round(elapsed, 3), "requests": len(rows), "rps": len(rows) / max(elapsed, 1), "writes": len(writes), "errors": errors, "status_counts": dict(collections.Counter(str(r[2]) for r in rows)), "read_p95": percentile(reads), "write_p95": percentile(writes), "samples": samples, "stop_reason": self.reason, "exception_class": failure, "integrity_before": integrity(before, self.baseline)}
            try:
                result["integrity_after"] = integrity(snapshot(), self.baseline)
            except Exception as error:
                result["integrity_after"] = {"exception_class": type(error).__name__}
                self.halt("final_snapshot_failed")
                result["stop_reason"] = self.reason
            result["passed"] = elapsed >= seconds and not self.stop.is_set() and not failure and errors / max(1, len(rows)) < .01 and bool(reads) and bool(writes) and percentile(reads) < 1 and percentile(writes) < 2 and result["integrity_after"].get("invalid") == []
            write_json(output, result)
            self.recorder.record("stage_end", stage=name, passed=result["passed"], requests=len(rows), stop_reason=result["stop_reason"])
        return result


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2)


def drain(timeout=60):
    deadline = time.monotonic() + timeout
    while True:
        with psycopg2.connect(**dict(TARGET, dbname=DATABASE), connect_timeout=5) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid() AND (state<>'idle' OR xact_start IS NOT NULL)", [DATABASE])
                active = cur.fetchone()[0]
        if active == 0:
            return {"drained": True, "active": 0}
        if time.monotonic() >= deadline:
            return {"drained": False, "active": active}
        time.sleep(1)


def reconcile(workload):
    """Attribute all movements to original client intentions and check replays."""
    rec = workload.recorder
    report = {"drain": drain(), "recoveries": []}
    results = {r["request_id"]: r for r in rec.results}
    accounts = {a["username"]: a for a in workload.accounts}
    uncertain = [i for key, i in list(rec.intents.items()) if i["method"] != "GET" and (key not in results or not results[key]["ok"])]
    if report["drain"]["drained"]:
        for intent in uncertain:
            if intent["operation_id"]:
                response = workload.request("recovery", accounts[intent["account"]], intent["method"], intent["path"], intent["payload"], (200, 201), replay=True, recovery=True)
                report["recoveries"].append({"original_request_id": intent["request_id"], "operation_id": intent["operation_id"], "status": response[0], "confirmed_id": response[1].get("id"), "exception_class": response[3]})
            else:
                report.setdefault("unresolved_other_writes", []).append(intent["request_id"])
        report["post_recovery_drain"] = drain()
    current = snapshot()
    baseline = workload.baseline
    base_moves = {m["id"]: m for m in baseline["movements"]}
    current_moves = {m["id"]: m for m in current["movements"]}
    originals = {}
    operation_results = collections.defaultdict(list)
    by_request = {r["request_id"]: r for r in rec.results}
    for intent in rec.intents.values():
        if intent["operation_id"] and not intent["replay"]:
            originals[intent["operation_id"]] = intent
        result = by_request.get(intent["request_id"])
        if intent["operation_id"] and result and result["ok"]:
            operation_results[intent["operation_id"]].append(result)
    grouped = collections.defaultdict(list)
    for move in current["movements"]:
        if move["id"] not in base_moves:
            grouped[move["operation_id"]].append(move)
    mismatches, resolved = [], []
    existence = {r["existence"]: r for r in baseline["balances"]}
    for operation, intent in originals.items():
        moves = grouped.get(operation, [])
        if len(moves) != 1:
            mismatches.append({"operation_id": operation, "movement_count": len(moves)})
            continue
        move, payload = moves[0], intent["payload"]
        origin = existence.get(payload["existencia"], {})
        correct = (move["type"] == "traslado" and move["lot"] == origin.get("lot") and move["origin"] == origin.get("location") and move["destination"] == payload["destino"] and Decimal(move["quantity"]) == Decimal(payload["cantidad"]) and move["document_type"] == payload["documento_tipo"] and move["document_id"] == payload["documento_id"] and move["reason"] == payload["motivo"])
        account = accounts[intent["account"]]
        if account.get("user_id") is not None:
            correct = correct and move["user"] == account["user_id"]
        confirmations = operation_results[operation]
        if not correct or any(r["confirmed_id"] != move["id"] for r in confirmations) or not confirmations:
            mismatches.append({"operation_id": operation, "error": "fields_or_confirmation_mismatch"})
        else:
            resolved.append(operation)
    unknown = sorted(str(key) for key in grouped.keys() - originals.keys())
    preserved = all(current_moves.get(key) == value for key, value in base_moves.items())
    check = integrity(current, baseline)
    report.update({"original_transfer_operations": len(originals), "resolved_operations": len(resolved), "new_movement_rows": sum(len(v) for v in grouped.values()), "unknown_operations": unknown, "null_operation_rows": len(grouped.get(None, [])), "mismatches": mismatches, "baseline_preserved": preserved, "integrity": check, "final_snapshot": current})
    report["passed"] = report["drain"]["drained"] and report.get("post_recovery_drain", {}).get("drained", True) and preserved and not unknown and not mismatches and not report.get("unresolved_other_writes") and not check["invalid"]
    write_json(RUNTIME / "load-reconciliation.json", report)
    return report


def main():
    identity = verify_cluster()
    assert TARGET["port"] == 55469 and TARGET["user"] == "op09r_test"
    accounts = json.loads((RUNTIME / "load-accounts.json").read_text(encoding="utf-8"))
    sessions = json.loads((RUNTIME / "synthetic-sessions.json").read_text(encoding="utf-8"))
    assert len(accounts) == 70 and len({a["username"] for a in accounts}) == 70
    assert all(a["username"].startswith("op09r_carga_") for a in accounts)
    for account in accounts:
        account["token"] = sessions[account["username"]]
    rec = Recorder(RUNTIME / "load-journal.jsonl")
    baseline = snapshot()
    assert not baseline["movements"], "Old OP09R load exists; do not reuse namespace"
    assert not integrity(baseline, baseline)["invalid"], "Synthetic baseline invalid"
    write_json(RUNTIME / "load-baseline.json", baseline)
    workload = Workload(rec, baseline, accounts)
    results, stable, error, reconciliation = [], None, None, None
    try:
        rec.record("isolation", **identity)
        workload.prepare(accounts[:10])
        results.append(workload.stage("warmup", 10, 300))
        if not results[-1]["passed"]:
            raise RuntimeError("Warmup failed; do not escalate")
        for count in (10, 25, 50, 70):
            workload.prepare(accounts[:count])
            result = workload.stage(f"users-{count}", count, 600)
            results.append(result)
            if not result["passed"]:
                break
            stable = count
        # After any failure/guard STOP remains set; never conceal it with soak.
        if stable is not None and not workload.stop.is_set():
            results.append(workload.stage("soak", stable, 1800))
    except Exception as problem:
        error = type(problem).__name__
        rec.record("main_exception", exception_class=error)
        workload.halt("main_exception")
    finally:
        try:
            reconciliation = reconcile(workload)
        except Exception as problem:
            reconciliation = {"passed": False, "exception_class": type(problem).__name__}
            rec.record("reconciliation_exception", exception_class=type(problem).__name__)
        summary = {"stages": results, "stable_users": stable, "exception_class": error, "reconciliation_passed": reconciliation.get("passed", False), "stop_reason": workload.reason, "passed": len(results) == 6 and all(r["passed"] for r in results) and reconciliation.get("passed", False), "scope": "New fictitious PG55469/API8229, Django development server; preauthenticated70accounts, four areas, 1–3second think time. Not production capacity certification; no production/deployment/purchase."}
        write_json(RUNTIME / "load-summary.json", summary)
        rec.record("finished", passed=summary["passed"], stable_users=stable)
        rec.close()
        print("OP09R_LOAD_FINISHED " + json.dumps({"passed": summary["passed"], "stable_users": stable, "stop_reason": workload.reason}), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
