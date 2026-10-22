"""Bounded real login throttle check on the isolated API; no quota reset."""
import http.client
import json
import time
import uuid

from manage_isolated import RUNTIME, verify_cluster


def main():
    verify_cluster()
    output = RUNTIME / "login-burst.json"
    assert not output.exists(), "Do not overwrite prior evidence"
    nonce = uuid.uuid4().hex[:12]
    rows = []
    for index in range(65):
        conn = http.client.HTTPConnection("127.0.0.1", 8209, timeout=10)
        started = time.perf_counter()
        try:
            # Different nonexistent fictitious names isolate the shared IP quota.
            conn.request("POST", "/api/usuarios/login/", json.dumps({"username": f"op09_inexistente_{nonce}_{index}", "password": "OP09-invalid-fictitious-only"}), {"Content-Type": "application/json"})
            response = conn.getresponse()
            response.read()
            rows.append({"attempt": index + 1, "status": response.status, "seconds": time.perf_counter() - started, "retry_after": response.getheader("Retry-After")})
        except (OSError, http.client.HTTPException) as error:
            rows.append({"attempt": index + 1, "status": 0, "exception_type": type(error).__name__, "seconds": time.perf_counter() - started})
        finally:
            conn.close()
        if rows[-1]["status"] != 401:
            break
    report = {"requests": rows, "throttle_observed": rows[-1]["status"] == 429, "scope": "One loopback IP, real normal login, max 65 requests, no throttle/cache reset. Prior legitimate logins share the existing hourly quota; count does not establish a fresh 60-request window. No production rate or simultaneous-shift capacity certified."}
    report["passed"] = report["throttle_observed"] and all(row["status"] == 401 for row in rows[:-1]) and bool(rows[-1].get("retry_after"))
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"attempts": len(rows), "last_status": rows[-1]["status"], "passed": report["passed"]}), flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
