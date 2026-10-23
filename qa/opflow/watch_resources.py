"""Observe host memory; latch STOP without killing unrelated processes."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "op09r"))
from load import resources  # noqa: E402

runtime = Path(__file__).resolve().parents[3] / "opflow-runtime"
stopped = False
with (runtime / "resources.jsonl").open("x", encoding="utf-8") as journal:
    while not (runtime / "guard-stop.request").exists():
        row = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **resources()}
        stopped = stopped or row["ram_percent"] > 85
        row["stopped"] = stopped
        journal.write(json.dumps(row) + "\n")
        journal.flush()
        # Readers fail closed if a transient partial write is observed.
        (runtime / "guard-state.json").write_text(json.dumps(row), encoding="utf-8")
        time.sleep(5)
