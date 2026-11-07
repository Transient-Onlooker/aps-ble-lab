"""Offline unit tests for read-only T-DATA parsing (no network, no API key)."""
import unittest
import io
import json
import argparse
from contextlib import redirect_stdout, redirect_stderr
from urllib.error import HTTPError, URLError
from unittest.mock import patch
import tdata_probe as p


class TDataProbeTests(unittest.TestCase):
    def test_local_env_file_and_environment_precedence(self):
        with patch.dict(p.os.environ, {}, clear=True):
            with patch.object(p.Path, 'read_text', return_value='# local only\nTDATA_API_KEY="synthetic-file-key"\n'):
                self.assertEqual(p.local_api_key(), 'synthetic-file-key')
            with patch.object(p.Path, 'read_text', side_effect=FileNotFoundError):
                self.assertEqual(p.local_api_key(), '')
        with patch.dict(p.os.environ, {'TDATA_API_KEY': 'synthetic-env-key'}):
            with patch.object(p.Path, 'read_text') as read:
                self.assertEqual(p.local_api_key(), 'synthetic-env-key')
                read.assert_not_called()

    def run_main(self, args, response):
        stdout = io.StringIO()
        with patch.dict(p.os.environ, {'TDATA_API_KEY': 'synthetic-unit-test-key'}):
            with patch.object(p, 'request_json', side_effect=response) as request:
                with redirect_stdout(stdout):
                    self.assertEqual(p.main(args), 0)
        return json.loads(stdout.getvalue()), request

    def test_map_cli_single_fetch_cache_dedup_sort_and_lookup_limit(self):
        def fake(endpoint, params):
            if endpoint == p.SIGNAL_URL:
                self.assertEqual(params['itstId'], '101')
                return []
            self.assertEqual(params['apiKey'], 'synthetic-unit-test-key')
            self.assertNotIn('apikey', params)
            self.assertEqual(params['pageNo'], 1)
            return [
                    {'itstId': '102', 'itstNm': 'near', 'mapCtptIntLat': '37.496750', 'mapCtptIntLot': '127.124320'},
                    {'itstId': '101', 'itstNm': 'nearest', 'mapCtptIntLat': 37.495750, 'mapCtptIntLot': 127.124320},
                    {'itstId': '101', 'itstNm': 'duplicate', 'mapCtptIntLat': 37.495750, 'mapCtptIntLot': 127.124320},
                ]
        with patch.object(p.Path, 'is_file', return_value=False), patch.object(p.Path, 'mkdir'):
            with patch.object(p.Path, 'write_text') as save:
                out, request = self.run_main(['--fetch-map', '--check', '1'], fake)
                cache = json.loads(save.call_args.args[0])
                self.assertEqual(len(cache['records']), 3)
                self.assertNotIn('synthetic-unit-test-key', save.call_args.args[0])
        self.assertEqual(request.call_count, 2)
        self.assertEqual([r['itstId'] for r in out['map']['candidates']], ['101', '102'])
        self.assertEqual(out['map']['inputSource']['page'], 1)
        self.assertEqual(out['signals'][0]['count'], 0)

    def test_empty_keyword_does_not_select_remote_or_unlocated_rows(self):
        rows = [{'itstId': '1', 'itstNm': 'unknown'},
                {'itstId': '2', 'itstNm': 'remote', 'mapCtptIntLat': 37.8, 'mapCtptIntLot': 127.5}]
        with patch.object(p, 'load_map', return_value=(rows, {'source': 'synthetic test'})):
            out, request = self.run_main(['--keyword', '', '--check', '0'], lambda *a: rows)
        self.assertEqual(out['map']['candidates'], [])
        self.assertEqual(out['signals'], [])
        self.assertEqual(request.call_count, 0)

    def test_existing_map_cache_prevents_fetch_even_with_fetch_flag(self):
        args = argparse.Namespace(map_csv=None, map_cache=p.Path('private/synthetic-map.json'), fetch_map=True)
        with patch.object(p.Path, 'is_file', return_value=True):
            with patch.object(p.Path, 'read_text', return_value='[{"itstId":"710"}]'):
                with patch.object(p, 'request_json') as request:
                    rows, metadata = p.load_map(args, 'synthetic-key')
                    request.assert_not_called()
        self.assertEqual(rows[0]['itstId'], '710')
        self.assertEqual(metadata['source'], '10121 local cache')

    def test_10144_csv_requires_no_key_or_network_and_normalizes_columns(self):
        content = 'ITST_ID,ITST_NM,MAP_CTPT_INT_LAT,MAP_CTPT_INT_LOT\n710,Synthetic,37.4967525,127.1249471\n'
        with patch.dict(p.os.environ, {}, clear=True), patch.object(p, 'local_api_key', return_value=''):
            with patch.object(p.Path, 'open', return_value=io.StringIO(content)):
                with patch.object(p, 'request_json') as request, redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(p.main(['--map-csv', 'synthetic.csv', '--check', '0']), 0)
                    request.assert_not_called()
        out = json.loads(stdout.getvalue())
        self.assertEqual(out['map']['candidates'][0]['itstId'], '710')
        self.assertEqual(out['map']['inputSource']['source'], '10144 CSV')

    def test_no_automatic_10121_fetch_without_cache(self):
        with patch.object(p.Path, 'is_file', return_value=False):
            with patch.object(p, 'request_json') as request, redirect_stderr(io.StringIO()):
                self.assertEqual(p.main(['--check', '0']), 1)
                request.assert_not_called()

    def test_direct_id_skips_map_and_preserves_null_and_raw_time(self):
        def fake(endpoint, params):
            self.assertEqual(endpoint, p.SIGNAL_URL)
            return [{'itstId': '20386', 'trsmUtcTime': 1790571447594,
                     'ntPdsgStatNm': None, 'nePdsgStatNm': 'stop-And-Remain',
                     'nePdsgRmdrCs': 414.0, 'ntPdsgRmdrCs': None}]
        out, request = self.run_main(['--itst-id', '20386'], fake)
        self.assertNotIn('map', out)
        self.assertEqual(request.call_count, 1)
        record = out['signals'][0]['records'][0]
        self.assertEqual(record['timestampUTC'], '2026-09-28T04:57:27.594000+00:00')
        self.assertIsNone(record['pedestrianFieldsRaw']['ntPdsgStatNm'])
        self.assertEqual(record['pedestrianFieldsRaw']['nePdsgRmdrCs'], 414.0)
        self.assertNotIn('synthetic-unit-test-key', json.dumps(out))

    def test_missing_key_and_invalid_coordinates_fail_before_network(self):
        for args, env in [([], {}), (['--lat', 'nan'], {'TDATA_API_KEY': 'test'}),
                          (['--lon', '181'], {'TDATA_API_KEY': 'test'}),
                          (['--radius', '-1'], {'TDATA_API_KEY': 'test'}),
                          (['--pages', '2'], {'TDATA_API_KEY': 'test'})]:
            with self.subTest(args=args), patch.dict(p.os.environ, env, clear=True):
                with patch.object(p, 'request_json') as request, patch.object(p, 'local_api_key', return_value=''), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit):
                        p.main(args)
                    request.assert_not_called()

    def test_request_errors_never_include_key_or_url(self):
        secret = 'synthetic-private-test-key'
        url = p.SIGNAL_URL + '?apikey=' + secret
        for error in [HTTPError(url, 403, url, {}, None), URLError(url)]:
            with self.subTest(error=type(error).__name__), patch.object(p, 'urlopen', side_effect=error):
                with self.assertRaises(RuntimeError) as caught:
                    p.request_json(p.SIGNAL_URL, {'apikey': secret})
                self.assertNotIn(secret, str(caught.exception))
                self.assertNotIn(url, str(caught.exception))

    def test_rate_limit_is_reported_without_retry(self):
        error = HTTPError(p.MAP_URL, 429, 'Too Many Requests', {'Retry-After': '21514'}, None)
        with patch.object(p, 'urlopen', side_effect=error) as request:
            with self.assertRaisesRegex(RuntimeError, 'Retry-After=21514 seconds'):
                p.request_json(p.MAP_URL, {'apiKey': 'synthetic-test-key'})
            self.assertEqual(request.call_count, 1)

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
