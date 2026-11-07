#!/usr/bin/env python3
"""Read-only Seoul T-DATA Map (10121) + live SPaT (10381) probe.

Requires TDATA_API_KEY in environment or local .env. Does not write to BLE devices.
Raw remaining-time units intentionally not interpreted.
"""
import argparse
import csv
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = "https://t-data.seoul.go.kr/apig/apiman-gateway/tapi/"
MAP_URL = ROOT + "v2xCrossroadMapInformation/1.0"
SIGNAL_URL = ROOT + "v2xSignalPhaseTimingFusionCurrentInfo/1.0"


def local_api_key():
    key = os.environ.get("TDATA_API_KEY", "").strip()
    if key:
        return key
    try:
        lines = Path(__file__).with_name(".env").read_text(encoding="utf-8-sig").splitlines()
    except FileNotFoundError:
        return ""
    for line in lines:
        if line.lstrip().startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if sep and name.strip() == "TDATA_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value.strip()
    return ""


def request_json(endpoint, params):
    # Never print URLs/exceptions containing the query-string API key.
    req = Request(endpoint + "?" + urlencode(params),
                  headers={"Accept": "application/json", "User-Agent": "aps-ble-lab/0.3"})
    try:
        with urlopen(req, timeout=20) as res:
            raw = res.read(8000001)
            if len(raw) > 8000000:
                raise RuntimeError("T-DATA response > 8 MB")
            return json.loads(raw.decode("utf-8-sig"))
    except HTTPError as e:
        if e.code == 429:
            retry = e.headers.get('Retry-After', '') if e.headers else ''
            suffix = ' Retry-After=' + retry + ' seconds.' if retry.isdigit() and len(retry) < 12 else ''
            raise RuntimeError('T-DATA HTTP 429 (rate limit; do not retry immediately).' + suffix) from None
        raise RuntimeError("T-DATA HTTP " + str(e.code) + " (check API approval/key)") from None
    except URLError:
        raise RuntimeError("T-DATA connection failed (URL and API key suppressed)") from None
    except (ValueError, UnicodeError):
        raise RuntimeError("T-DATA returned non-JSON content (authentication/endpoint?)") from None


def find_records(value):
    if isinstance(value, dict):
        if "itstId" in value:
            yield value
        else:
            for v in value.values():
                if isinstance(v, (dict, list)):
                    yield from find_records(v)
    elif isinstance(value, list):
        for item in value:
            yield from find_records(item)


def distance_m(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat = b-a
    dlon = math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return round(12742000*math.asin(min(1, math.sqrt(h))))


def location_distance(row, lat, lon):
    try:
        x, y = float(row["mapCtptIntLat"]), float(row["mapCtptIntLot"])
        if 35 < x < 39 and 125 < y < 130:
            return distance_m(lat, lon, x, y)
    except (KeyError, ValueError, TypeError):
        pass
    return None


def load_map(args, key):
    if args.map_csv:
        with args.map_csv.open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.DictReader(stream)
            columns = {'ITST_ID': 'itstId', 'ITST_NM': 'itstNm',
                       'MAP_CTPT_INT_LAT': 'mapCtptIntLat', 'MAP_CTPT_INT_LOT': 'mapCtptIntLot'}
            if not set(columns).issubset(reader.fieldnames or []):
                raise RuntimeError('10144 CSV is missing required MAP columns')
            rows = [{value: row[name] for name, value in columns.items()} for row in reader]
        return rows, {'source': '10144 CSV', 'file': args.map_csv.name, 'rows': len(rows)}
    if args.map_cache.is_file():
        cached = json.loads(args.map_cache.read_text(encoding='utf-8-sig'))
        rows = list(find_records(cached))
        if not rows:
            raise RuntimeError('MAP cache has no records; not requesting 10121 automatically')
        return rows, {'source': '10121 local cache', 'file': args.map_cache.name, 'rows': len(rows)}
    if not args.fetch_map:
        raise RuntimeError('Use --map-csv FILE or an existing --map-cache FILE; '
                           '10121 network fetch requires explicit --fetch-map (6-hour cooldown)')
    raw = request_json(MAP_URL, {'apiKey': key, 'type': 'json', 'pageNo': 1, 'numOfRows': args.rows})
    rows = list(find_records(raw))
    if not rows:
        raise RuntimeError('10121 returned no records; response not cached; coverage is unverified')
    args.map_cache.parent.mkdir(parents=True, exist_ok=True)
    args.map_cache.write_text(json.dumps({'source': '10121', 'page': 1, 'requestedRows': args.rows,
                                         'fetchedUTC': datetime.now(timezone.utc).isoformat(),
                                         'records': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    return rows, {'source': '10121 one request, cached', 'rows': len(rows), 'page': 1}


def get_current(key, itst_id):
    # IMPORTANT: newer endpoint uses lowercase 'apikey'.
    raw = request_json(SIGNAL_URL, {"apikey": key, "itstId": str(itst_id),
                                    "type": "json", "pageNo": 1, "numOfRows": 10})
    records = list(find_records(raw))
    summary = []
    for r in records:
        ms = r.get("trsmUtcTime")
        try:
            x = float(ms)
            at = datetime.fromtimestamp(x/(1000 if x > 1e11 else 1), timezone.utc).isoformat()
        except (TypeError, ValueError, OverflowError, OSError):
            at = None
        summary.append({
            "itstId": r.get("itstId"),
            "timestampUTC": at,
            "trsmUtcTime": ms,
            "pedestrianFieldsRaw": {k: v for k, v in r.items()
                                    if "Pdsg" in k and
                                    (k.endswith("StatNm") or k.endswith("RmdrCs"))}
        })
    return {"itstId": str(itst_id), "count": len(records), "records": summary,
            "note": "Raw values only; empty records do not prove absent coverage; units not converted"}


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only Seoul T-DATA crossing coverage probe")
    p.add_argument("--itst-id", help="Query known intersection ID directly (skip 10121)")
    p.add_argument("--lat", type=float, default=37.495750)
    p.add_argument("--lon", type=float, default=127.124320)
    p.add_argument("--radius", type=int, default=1200)
    p.add_argument("--keyword", default="경찰병원")
    p.add_argument("--pages", type=int, default=1, help="Only 1 allowed: 10121 has a 6-hour cooldown")
    p.add_argument("--rows", type=int, default=500)
    p.add_argument("--map-csv", type=Path, help="Local official 10144 CSV; no 10121 call")
    p.add_argument("--map-cache", type=Path, default=Path(__file__).with_name('private') / 'tdata-map-cache.json')
    p.add_argument("--fetch-map", action='store_true', help="Explicit one-page 10121 fetch only if cache missing")
    p.add_argument("--check", type=int, default=3, help="Max live lookups for nearby IDs; 0 skips")
    p.add_argument("--output", help="Local JSON result file (never contains key)")
    args = p.parse_args(argv)
    if args.pages != 1 or not 1 <= args.rows <= 500 or not 0 <= args.check <= 10:
        p.error("Limits: pages must be 1 (6-hour 10121 cooldown), rows 1..500, check 0..10")
    if not (math.isfinite(args.lat) and -90 <= args.lat <= 90
            and math.isfinite(args.lon) and -180 <= args.lon <= 180 and args.radius >= 0):
        p.error("Coordinates must be finite and in range; radius must be nonnegative")
    key = local_api_key()
    if not key and (args.itst_id or args.check or args.fetch_map):
        p.error("Set TDATA_API_KEY in the environment or local .env (never commit it)")
    out = {"source": "Seoul T-DATA 10144/10121/10381", "retrievedUTC": datetime.now(timezone.utc).isoformat(),
           "warning": "Do NOT use for crossing safety decisions"}
    try:
        if args.itst_id:
            out["signals"] = [get_current(key, args.itst_id)]
        else:
            matches = {}
            rows, map_source = load_map(args, key)
            for r in rows:
                ident = r.get("itstId")
                if ident is None:
                    continue
                metres = location_distance(r, args.lat, args.lon)
                name = str(r.get("itstNm", ""))
                if (metres is not None and metres <= args.radius) or (args.keyword and args.keyword in name):
                    matches[str(ident)] = {"itstId": str(ident), "itstNm": name,
                                           "distanceM": metres,
                                           "latitude": r.get("mapCtptIntLat"),
                                           "longitude": r.get("mapCtptIntLot")}
            nearest = sorted(matches.values(), key=lambda r: r["distanceM"]
                             if r["distanceM"] is not None else 10**9)
            out["map"] = {"refLat": args.lat, "refLon": args.lon, "inputSource": map_source,
                          "candidates": nearest,
                          "note": "MAP data may be incomplete/stale; no candidates do not prove absent coverage"}
            out["signals"] = [get_current(key, r["itstId"]) for r in nearest[:args.check]]
    except RuntimeError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print('ERROR: Could not read/write local MAP or cache file', file=sys.stderr)
        return 1
    serialized = json.dumps(out, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
        print("Saved result to:", args.output, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
