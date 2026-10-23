"""Publish only explicitly selected fictitious summaries, never sessions/dumps."""
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "op09r-runtime"
DESTINATION = REPO / "docs/operacion/evidencias/op09r"
RAW = (
    "environment.json", "restore-source.json", "seed.log", "load-baseline.json",
    "load-journal.jsonl", "load-live.log", "load-warmup.json", "load-users-10.json",
    "load-summary.json", "load-reconciliation.json", "journal-verification.json",
    "login-turn.json", "login-live.log", "qa-unit-initial5.log",
    "qa-unit-final6.log", "qa-ruff-final.log", "postflight.json", "closure.json",
    "executed-load.py", "executed-login_turn.py", "api.log", "postgres.log",
)


def main():
    if (RUNTIME / "pgdata/postmaster.pid").exists():
        raise RuntimeError("Finish and stop the owned test cluster first")
    closure = json.loads((RUNTIME / "closure.json").read_text())
    assert closure["api_8229_listening"] is False and closure["pg_55469_stopped"]
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in RAW:
        raw = (RUNTIME / name).read_bytes()
        manifest[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    write("manifest.json", {"scope": "Raw originals remain local; no sessions, passwords, dump or private contents copied", "files": manifest})
    for name in ("environment.json", "load-summary.json", "journal-verification.json"):
        write(name, json.loads((RUNTIME / name).read_text()))
    reconciliation = json.loads((RUNTIME / "load-reconciliation.json").read_text())
    del reconciliation["final_snapshot"]
    write("reconciliation.json", reconciliation)
    login = json.loads((RUNTIME / "login-turn.json").read_text())
    write("login-turn.json", login)
    write("validation.json", {
        "qa_unit_final": {"executed": 6, "passed": 6, "skipped": 0},
        "ruff": "passed", "application_changed": False,
        "independent_review": "Recorder sequence, original/replay UUIDs, per-stage counts/p95 and reconciliation verified read-only by one QA helper",
        "overall_verdict": "PARTIAL; load and login incomplete due host RAM guard; no production capacity certification",
        "closure": closure,
        "historical_25_user_uncertain_responses": "Not reached or reproduced in this rerun; cause remains unresolved",
        "login_harness_followup": "All70 identities and cleanup required after run; negative regression added; actual4/70 result remains failed; exact executed script hashes recorded",
    })
    print(f"Selected six summaries and manifest for {len(manifest)} raw files")


def write(name, value):
    with (DESTINATION / name).open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=False)
        output.write("\n")


if __name__ == "__main__":
    main()
