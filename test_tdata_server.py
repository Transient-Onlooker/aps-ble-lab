"""Offline tests: no real T-DATA requests, no credentials required."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tdata_server as server


def record(key, ident):
    return {"records": [{"itstId": ident, "timestampUTC": "2026-11-07T01:59:16+00:00",
                         "trsmUtcTime": 1794016756000,
                         "pedestrianFieldsRaw": {
                             "sePdsgStatNm": "permissive-Movement-Allowed",
                             "sePdsgRmdrCs": 118}}]}


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name) / "private" / "state.json"
        self.now = [100000.0]
        self.gateway = server.Gateway("synthetic-secret", state_path=self.state,
                                      max_requests=2, cache_seconds=15, clock=lambda: self.now[0])

    def tearDown(self):
        self.tmp.cleanup()

    def test_cache_no_leak_and_rolling_budget(self):
        with patch.object(server, "get_current", side_effect=record) as lookup:
            code, first = self.gateway.status("710")
            self.assertEqual(code, 200)
            self.assertFalse(first["cached"])
            self.assertEqual(first["snapshot"]["pedestrianFieldsRaw"]["sePdsgRmdrCs"], 118)
            self.assertNotIn("synthetic-secret", json.dumps(first))
            self.now[0] += 3
            code, cached = self.gateway.status("710")
            self.assertTrue(cached["cached"])
            self.assertEqual(lookup.call_count, 1)
            self.now[0] += 16
            code, second = self.gateway.status("710")
            self.assertEqual(code, 200)
            self.assertEqual(lookup.call_count, 2)
            self.now[0] += 16
            code, blocked = self.gateway.status("710")
            self.assertEqual(code, 429)
            self.assertEqual(blocked["attemptsIn24h"], 2)
            self.assertEqual(lookup.call_count, 2)
            self.now[0] += 86400
            code, again = self.gateway.status("710")
            self.assertEqual(code, 200)
            self.assertEqual(lookup.call_count, 3)

    def test_allowlist(self):
        with patch.object(server, "get_current") as request:
            code, _ = self.gateway.status("20386")
            self.assertEqual(code, 400)
            request.assert_not_called()

    def test_persistent_budget_after_restart(self):
        with patch.object(server, "get_current", side_effect=record) as lookup:
            self.gateway.status("710")
            self.now[0] += 20
            self.gateway.status("20710")
            another = server.Gateway("synthetic-secret", state_path=self.state,
                                     max_requests=2, cache_seconds=15, clock=lambda: self.now[0])
            self.now[0] += 20
            self.assertEqual(another.status("710")[0], 429)
            self.assertEqual(lookup.call_count, 2)

    def test_failure_consumes_budget_without_leaking_key(self):
        with patch.object(server, "get_current", side_effect=RuntimeError("upstream problem synthetic-secret")):
            code, data = self.gateway.status("710")
        self.assertEqual(code, 502)
        self.assertNotIn("synthetic-secret", json.dumps(data))
        self.assertEqual(json.loads(self.state.read_text())["attempts"], [100000.0])
        self.assertNotIn("synthetic-secret", self.state.read_text())

    def test_invalid_persistent_state_never_resets_quota(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text("{bad", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            server.Gateway("synthetic-secret", state_path=self.state)

    def test_wrong_intersection_id_in_upstream_is_rejected(self):
        with patch.object(server, "get_current", side_effect=lambda k, i: record(k, "999")):
            code, data = self.gateway.status("710")
        self.assertEqual(code, 502)
        self.assertIn("유효한", data["error"])


if __name__ == "__main__":
    unittest.main()
