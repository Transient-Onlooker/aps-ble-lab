"""Offline unit tests for read-only T-DATA parsing (no network, no API key)."""
import unittest
from unittest.mock import patch
import tdata_probe as p


class TDataProbeTests(unittest.TestCase):
    def test_records_and_distance(self):
        nested = {"response": {"items": [{"itstId": "11", "itstNm": "경찰병원역"}]}}
        self.assertEqual(list(p.find_records(nested))[0]["itstId"], "11")
        self.assertEqual(p.distance_m(37.5, 127.1, 37.5, 127.1), 0)
        self.assertIsNone(p.location_distance({"itstId": "11"}, 37.5, 127.1))

    def test_current_raw_pedestrian_fields_and_key_case(self):
        sample = [{
            "itstId": "20386", "trsmUtcTime": 1790571447594,
            "nePdsgStatNm": "stop-And-Remain",
            "nePdsgRmdrCs": 414,
            "nwStsgStatNm": "protected-Movement-Allowed"
        }]
        def fake(endpoint, params):
            self.assertIn("apikey", params)
            self.assertNotIn("apiKey", params)
            self.assertEqual(params["itstId"], "20386")
            return sample
        with patch.object(p, "request_json", side_effect=fake):
            out = p.get_current("secret-key", "20386")
        self.assertEqual(out["count"], 1)
        self.assertEqual(out["records"][0]["pedestrianFieldsRaw"]["nePdsgRmdrCs"], 414)
        self.assertNotIn("nwStsgStatNm", out["records"][0]["pedestrianFieldsRaw"])
        self.assertNotIn("secret-key", str(out))

    def test_map_key_case_and_nearby_filter(self):
        map_response = [
            {"itstId": "101", "itstNm": "경찰병원 앞",
             "mapCtptIntLat": 37.495750, "mapCtptIntLot": 127.124320},
            {"itstId": "102", "itstNm": "먼 교차로",
             "mapCtptIntLat": 37.8, "mapCtptIntLot": 127.5},
        ]
        # Ensure the helper does not mistakenly convert remote map results into a live status.
        def fake(endpoint, params):
            self.assertIn("apiKey", params)
            self.assertNotIn("apikey", params)
            return map_response
        with patch.object(p, "request_json", side_effect=fake):
            got = list(p.find_records(p.request_json(p.MAP_URL, {"apiKey": "test"})))
        self.assertEqual(len(got), 2)
        self.assertEqual(p.location_distance(got[0], 37.495750, 127.124320), 0)
        self.assertGreater(p.location_distance(got[1], 37.495750, 127.124320), 1000)


if __name__ == "__main__":
    unittest.main()
