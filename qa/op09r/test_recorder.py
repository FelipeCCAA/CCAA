"""QA helper checks only: no HTTP, PostgreSQL or real load."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from load import Recorder, Workload, integrity, percentile
from login_turn import passed as login_passed


class RecorderTests(unittest.TestCase):
    def test_exclusive_file_and_intent_is_on_disk_before_result(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp) / "events.jsonl"
            recorder = Recorder(path)
            try:
                request = recorder.intent(stage="test", account="fiction", method="POST", path="/api/test/", payload={"operacion_id": "uuid"})
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["operation_id"], "uuid")
                self.assertEqual(rows[0]["kind"], "intent")
                recorder.result(request, (0, {}, 10.01, "TimeoutError"), (201,))
                result = json.loads(path.read_text().splitlines()[1])
                self.assertEqual(result["exception_class"], "TimeoutError")
                self.assertFalse(result["ok"])
                with self.assertRaises(FileExistsError):
                    Recorder(path)
            finally:
                recorder.close()

    def test_concurrent_writes_have_contiguous_unique_sequence(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            path = Path(temp) / "events.jsonl"
            recorder = Recorder(path)
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                    list(pool.map(lambda i: recorder.record("test", n=i), range(200)))
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual([r["sequence"] for r in rows], list(range(1, 201)))
                self.assertEqual({r["n"] for r in rows}, set(range(200)))
            finally:
                recorder.close()

    def test_location_error_not_hidden_by_preserved_lot_total(self):
        balances = []
        for lot in range(18):
            for location, value in ((1, "10000"), (2, "0")):
                balances.append({"lot": lot, "location": location, "existence": lot * 2 + location, "physical": value, "reserved": "0"})
        baseline = {"balances": balances, "movements": [], "connections": 1}
        altered = [{**row} for row in balances]
        altered[0]["physical"], altered[1]["physical"] = "9999", "1"
        current = {"balances": altered, "movements": [], "connections": 1}
        self.assertEqual(integrity(baseline, baseline)["invalid"], [])
        self.assertEqual(integrity(current, baseline)["invalid"], ["balance:0:1", "balance:0:2"])
        current["movements"] = [{"id": 1, "type": "traslado", "lot": 0, "origin": 1, "destination": 2, "quantity": "1"}]
        self.assertEqual(integrity(current, baseline)["invalid"], [])

    def test_percentile_definition(self):
        self.assertIsNone(percentile([]))
        self.assertEqual(percentile(list(range(1, 101))), 95)

    def test_failed_patch_stops_all_new_requests_but_allows_explicit_recovery(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
            recorder = Recorder(Path(temp) / "events.jsonl")
            account = {"username": "fiction", "token": "never_logged"}
            workload = Workload(recorder, {}, [account])
            try:
                with patch("load.call", return_value=(0, {}, 10.0, "TimeoutError")) as http:
                    workload.request("test", account, "PATCH", "/api/test/", {"observacion": "fiction"})
                    self.assertTrue(workload.stop.is_set())
                    self.assertIsNone(workload.request("test", account, "POST", "/api/test/", {"operacion_id": "new"}))
                    self.assertEqual(http.call_count, 1)
                    workload.request("recovery", account, "POST", "/api/test/", {"operacion_id": "old"}, recovery=True)
                    self.assertEqual(http.call_count, 2)
                evidence = recorder.file.name
                self.assertNotIn("never_logged", Path(evidence).read_text())
                self.assertEqual(len(recorder.intents), 2)
                self.assertEqual(workload.reason, "uncertain_or_failed_write")
            finally:
                recorder.close()

    def test_seventy_http_200_without_identity_or_confirmed_cleanup_cannot_pass(self):
        # Pure recorded evidence: no API, DB, credentials, sleeps or live service.
        report = {
            "executed": 70,
            "results": [{"status": 200} for _ in range(70)],
            "identities": [],
            "session_cleanup_before": [{"status": 200} for _ in range(70)],
            "session_cleanup_after": [{"status": 200} for _ in range(70)],
            "stop_reason": None,
        }
        # The old all(empty) expression incorrectly accepted this aggregation.
        self.assertFalse(login_passed(report))
        report["identities"] = [{"status": 200, "username_matches": True} for _ in range(70)]
        self.assertTrue(login_passed(report))
        for field in ("identities", "session_cleanup_before", "session_cleanup_after"):
            with self.subTest(missing=field):
                self.assertFalse(login_passed({**report, field: []}))
        for field in ("session_cleanup_before", "session_cleanup_after"):
            with self.subTest(failed=field):
                self.assertFalse(login_passed({**report, field: [{"status": 200} for _ in range(69)] + [{"status": 0}]}))
        self.assertFalse(login_passed({**report, "stop_reason": "host_ram_above_85"}))


if __name__ == "__main__":
    unittest.main()
