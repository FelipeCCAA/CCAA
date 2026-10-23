"""Seventy valid synthetic logins behind one IP; never alter throttle/cache."""
import collections
import http.client
import json
import time

from load import PORT, call, resources, write_json
from manage_isolated import RUNTIME, verify_cluster


def passed(report):
    """A successful HTTP status alone does not prove an authenticated turn."""
    return (
        report["executed"] == 70
        and len(report["results"]) == 70
        and all(row["status"] == 200 for row in report["results"])
        and len(report["identities"]) == 70
        and all(row["status"] == 200 and row["username_matches"] for row in report["identities"])
        and len(report["session_cleanup_before"]) == 70
        and all(row["status"] == 200 for row in report["session_cleanup_before"])
        and len(report["session_cleanup_after"]) == 70
        and all(row["status"] == 200 for row in report["session_cleanup_after"])
        and not report["stop_reason"]
    )


def main():
    verify_cluster()
    output = RUNTIME / "login-turn.json"
    if output.exists() or not (RUNTIME / "load-summary.json").exists():
        raise RuntimeError("Run once, after load has ended")
    accounts = json.loads((RUNTIME / "load-accounts.json").read_text())
    sessions = json.loads((RUNTIME / "synthetic-sessions.json").read_text())
    rows, cleanup, identities, opened = [], [], [], {}
    stopped = None
    start = time.monotonic()
    try:
        for account in accounts:
            if resources()["ram_percent"] > 85:
                stopped = "host_ram_above_85"
                break
            status, _, elapsed, error = call("POST", "/api/usuarios/logout/", sessions[account["username"]], {})
            cleanup.append({"account": account["username"], "status": status, "seconds": elapsed, "exception_class": error})
            if status != 200:
                stopped = "synthetic_session_logout_not_confirmed"
                break
        if not stopped:
            for account in accounts:
                if resources()["ram_percent"] > 85:
                    stopped = "host_ram_above_85"
                    break
                conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
                tick = time.perf_counter()
                status, body, error, retry = 0, {}, None, None
                try:
                    conn.request("POST", "/api/usuarios/login/", body=json.dumps({"username": account["username"], "password": "OP09R-carga-ficticia-2026"}), headers={"Content-Type": "application/json"})
                    response = conn.getresponse()
                    status, retry = response.status, response.getheader("Retry-After")
                    body = json.loads(response.read())
                except (OSError, http.client.HTTPException, ValueError) as problem:
                    error = type(problem).__name__
                finally:
                    conn.close()
                rows.append({"account": account["username"], "status": status, "seconds": time.perf_counter() - tick, "exception_class": error, "retry_after": retry})
                if status == 200 and body.get("token"):
                    token = body["token"]
                    opened[account["username"]] = token
                    check, identity, _, _ = call("GET", "/api/usuarios/yo/", token)
                    identities.append({"account": account["username"], "status": check, "username_matches": identity.get("username") == account["username"]})
                elif status != 429:
                    stopped = "unexpected_login_result"
                    break
                # Realistic arrival window, not 70 simultaneous in-flight requests.
                time.sleep(1)
    finally:
        closed = []
        for username, token in opened.items():
            status, _, _, error = call("POST", "/api/usuarios/logout/", token, {})
            closed.append({"account": username, "status": status, "exception_class": error})
        report = {"scope": "70 valid fictitious credentials, sequential arrivals one second apart from same 127.0.0.1 IP; no cache reset or throttle changes; not simultaneous login benchmark", "planned": 70, "executed": len(rows), "status_counts": dict(collections.Counter(str(r["status"]) for r in rows)), "elapsed_seconds": time.monotonic() - start, "session_cleanup_before": cleanup, "results": rows, "identities": identities, "session_cleanup_after": closed, "stop_reason": stopped}
        report["passed"] = passed(report)
        write_json(output, report)
        print(json.dumps({"executed": len(rows), "status_counts": report["status_counts"], "passed": report["passed"], "stop_reason": stopped}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
