"""Selected fictitious evidence only; never copies credentials, sessions or dumps."""
import hashlib
import json
from pathlib import Path
import re

REPO = Path(__file__).resolve().parents[2]
RUNTIME = REPO.parent / "h09-runtime"
FILES = [
    "regresion-red.log", "regresion-green-1.log", "regresion-green-2.log",
    "regresion-green-3.log", "regresion-green-4.log", "backend-full-1.log",
    "regresion-final.log", "web-evaporacion-1.log", "web-evaporacion-2.log",
    "web-polvo-completo-1.log", "web-polvo-continuacion-2.log",
    "frontend-lint.log", "frontend-tests.log", "frontend-build.log",
    "ruff-final.log", "check-final.log", "schema-final.log",
    "powder-browser-evidence.json", "ci-implementation.json",
]


def django_result(name):
    raw = (RUNTIME / name).read_text(encoding="utf-8", errors="replace")
    runs = re.findall(r"Ran (\d+) tests in ([\d.]+)s", raw)
    assert runs and re.search(r"^OK(?: \(skipped=\d+\))?\s*$", raw, re.MULTILINE), name
    omitted = re.findall(r"^OK \(skipped=(\d+)\)", raw, re.MULTILINE)
    count, seconds = runs[-1]
    skipped = int(omitted[-1]) if omitted else 0
    return {"executed": int(count), "passed": int(count) - skipped, "skipped": skipped, "seconds": float(seconds)}


def main():
    destination = REPO / "docs/operacion/evidencias/h09-01"
    destination.mkdir(parents=True, exist_ok=True)
    full, final = django_result("backend-full-1.log"), django_result("regresion-final.log")
    full["scope"] = "Before final deletion/projection fixes; fresh final focused run and CI cover published application. Do not sum overlapping cases."
    facts = {"implementation_commit": "124d56e2a9602641f0d83fd980b245a9de00e8fe", "backend_full_local": full, "backend_focused_final": final, "new_regressions": 18, "frontend": {"executed": 111, "passed": 111, "skipped": 0}, "browser": "Same fictitious lot in preserved cuts: evaporation 2/2 including session, continuation 1/1 after scoped assertion correction, no extra evaporation signature", "scope": "Local fictitious data; no deployment, production access or global OP09/load certification. CI verdict is recorded separately by SHA in PR."}
    manifest = {}
    for name in FILES:
        file = RUNTIME / name
        assert file.is_file() and not file.is_symlink(), name
        data = file.read_bytes()
        manifest[name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    (destination / "validation.json").write_text(json.dumps(facts, indent=2), encoding="utf-8")
    (destination / "powder-browser-evidence.json").write_text((RUNTIME / "powder-browser-evidence.json").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "ci-implementation.json").write_text((RUNTIME / "ci-implementation.json").read_text(encoding="utf-8"), encoding="utf-8")
    (destination / "manifest.json").write_text(json.dumps({"scope": "Hashes of raw files retained only in h09-runtime; no session, credential, dump or private file copied", "files": manifest}, indent=2), encoding="utf-8")
    print(json.dumps({"raw_hashes": len(manifest), "full": full, "fresh_focused": final}))


if __name__ == "__main__":
    main()
