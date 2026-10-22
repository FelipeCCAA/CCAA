"""Publish only selected synthetic summaries and hashes, never sessions or database dumps."""
import hashlib
import json

from manage_isolated import REPO, RUNTIME

SUMMARIES = [
    "load-readiness-final.json", "http-races.json", "backup-summary.json",
    "restore-smoke.json", "load-summary.json", "load-reconciliation.json",
    "load-reconciliation-final.json", "load-post-abort-soak-summary.json",
    "login-burst.json", "evidence-upload.json",
]
LOGS = [
    "circuito-polvo-1.log", "evaporacion-polvo-1.log",
    "continuacion-polvo-1.log", "continuacion-polvo-2.log",
    "continuacion-polvo-3.log", "continuacion-polvo-4.log",
    "circuito-precondensado-1.log", "circuito-precondensado-2.log",
    "evaporacion-precondensado-1.log", "despacho-precondensado-1.log",
    "descremado-1.log", "descremado-directo-2.log",
    "mantequilla-produccion-2.log", "mantequilla-continuacion-1.log",
    "suero-1.log", "suero-2.log", "carreras-regresion.log",
    "frontend-lint.log", "frontend-types.log", "http-races.log",
    "backup-restore.log", "restore-smoke.log", "load-live.log",
    "load-post-abort-soak-live.log", "login-burst.log",
    "pantalla-local.png", "pantalla-local-final.png",
]


def main():
    destination = REPO / "docs/operacion/evidencias/op09"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in SUMMARIES + LOGS:
        source = RUNTIME / name
        assert source.is_file() and not source.is_symlink(), name
        raw = source.read_bytes()
        manifest[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "committed_summary": name in SUMMARIES}
        if name in SUMMARIES:
            body = json.loads(raw)
            # The backup identity is relevant but the user's local absolute path is not.
            if name == "backup-summary.json":
                body["identity"]["directory"] = "op09-runtime/pgdata"
            (destination / name).write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
    (destination / "manifest.json").write_text(json.dumps({"scope": "Synthetic OP09 QA only; raw logs/screenshots remain in sibling op09-runtime. No credentials, session files, database dump or private payload copied. Original raw-file hashes precede path sanitization of the backup summary.", "files": manifest}, indent=2), encoding="utf-8")
    print(json.dumps({"summaries": len(SUMMARIES), "raw_evidence_hashes": len(manifest)}))


if __name__ == "__main__":
    main()
