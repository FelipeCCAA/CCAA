"""Separate bounded soak after reconciliation; never rewrites the failed load report."""
import hashlib
import json

import psycopg2

import load


def operations():
    with psycopg2.connect(**dict(load.TARGET, dbname="op09_circuito")) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT operacion_id::text FROM inventario_movimientoinventario WHERE documento_tipo='OP09.Carga'")
            return {row[0] for row in cur.fetchall()}


def main():
    load.verify_cluster()
    output = load.RUNTIME / "load-post-abort-soak-summary.json"
    assert not output.exists(), "Preserve previous soak evidence"
    reconciled = json.loads((load.RUNTIME / "load-reconciliation.json").read_text())
    assert not reconciled["mismatches"] and reconciled["null_operations"] == 0
    baseline = operations()
    assert len(baseline) == reconciled["movement_count"] == reconciled["distinct_operations"]
    assert not load.stock_integrity()["invalid_lots"]
    assert load.resources()["ram_percent"] < 85
    accounts = json.loads((load.RUNTIME / "load-accounts.json").read_text())[:10]
    report = {"baseline_count": len(baseline), "baseline_sha256": hashlib.sha256("\n".join(sorted(baseline)).encode()).hexdigest(), "scope": "Separate subsequent 30-minute run at previously stable 10 users. Does not change failed 25-user result or execute 50/70. Normal HTTP login; unchanged safety guards and workload."}
    try:
        for account in accounts:
            status, body, _ = load.call("POST", "/api/usuarios/login/", data={"username": account["username"], "password": "OP09-carga-ficticia-2026"})
            assert status == 200 and body.get("token"), f"Normal login rejected: {status}"
            account["token"] = body["token"]
            status, _, _ = load.call("GET", "/api/usuarios/yo/", account["token"])
            assert status == 200
            if account["area"] == "recepcion":
                status, draft, _ = load.call("POST", "/api/recepcion/recepciones/crear-borrador/", account["token"], {})
                if status == 409:
                    draft = draft.get("borrador", {})
                else:
                    assert status == 201
                account["draft"] = draft["id"]
        load.ACCOUNTS = accounts
        report["result"] = load.stage("post-abort-soak-10", 10, 1800)
    except Exception as error:
        report["error"] = str(error)
    finally:
        database = operations()
        report["new_http_success_uuids"] = sorted(load.OPERATIONS)
        report["new_database_uuids"] = sorted(database - baseline)
        report["old_operations_preserved"] = baseline <= database
        report["database_matches_new_http_successes"] = database - baseline == load.OPERATIONS
        report["integrity"] = load.stock_integrity()
        report["passed"] = report.get("result", {}).get("passed", False) and report["old_operations_preserved"] and report["database_matches_new_http_successes"]
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for account in accounts:
            if "token" in account:
                load.call("POST", "/api/usuarios/logout/", account["token"], {})
        print(json.dumps({"soak_passed": report["passed"], "error": report.get("error"), "new_operations": len(load.OPERATIONS)}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
