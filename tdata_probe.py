#!/usr/bin/env python3
"""Read-only Seoul T-DATA Map (10121) + live SPaT (10381) probe.

Requires TDATA_API_KEY environment variable. Does not write to BLE devices.
Raw remaining-time units intentionally not interpreted.
"""
import argparse
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
            "note": "Raw values only; no live coverage if empty; units unverified"}


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only Seoul T-DATA crossing coverage probe")
    p.add_argument("--itst-id", help="Query known intersection ID directly (skip 10121)")
    p.add_argument("--lat", type=float, default=37.495750)
    p.add_argument("--lon", type=float, default=127.124320)
    p.add_argument("--radius", type=int, default=1200)
    p.add_argument("--keyword", default="경찰병원")
    p.add_argument("--pages", type=int, default=2)
    p.add_argument("--rows", type=int, default=100)
    p.add_argument("--check", type=int, default=3, help="Max live lookups for nearby IDs; 0 skips")
    p.add_argument("--output", help="Local JSON result file (never contains key)")
    args = p.parse_args(argv)
    if not 1 <= args.pages <= 10 or not 1 <= args.rows <= 500 or not 0 <= args.check <= 10:
        p.error("Limits: pages 1..10, rows 1..500, check 0..10")
    key = os.environ.get("TDATA_API_KEY", "").strip()
    if not key:
        p.error("Set TDATA_API_KEY in the environment (never commit it)")
    out = {"source": "Seoul T-DATA 10121/10381", "retrievedUTC": datetime.now(timezone.utc).isoformat(),
           "warning": "Do NOT use for crossing safety decisions"}
    try:
        if args.itst_id:
            out["signals"] = [get_current(key, args.itst_id)]
        else:
            matches = {}
            page_stats = []
            for page in range(1, args.pages + 1):
                # IMPORTANT: older 10121 endpoint uses camel-case 'apiKey'.
                raw = request_json(MAP_URL, {"apiKey": key, "type": "json",
                                             "pageNo": page, "numOfRows": args.rows})
                rows = list(find_records(raw))
                page_stats.append({"page": page, "rows": len(rows)})
                for r in rows:
                    ident = r.get("itstId")
                    if ident is None:
                        continue
                    metres = location_distance(r, args.lat, args.lon)
                    name = str(r.get("itstNm", ""))
                    if (metres is not None and metres <= args.radius) or (args.keyword in name):
                        matches[str(ident)] = {"itstId": str(ident), "itstNm": name,
                                               "distanceM": metres,
                                               "latitude": r.get("mapCtptIntLat"),
                                               "longitude": r.get("mapCtptIntLot")}
                if len(rows) < args.rows:
                    break
            nearest = sorted(matches.values(), key=lambda r: r["distanceM"]
                             if r["distanceM"] is not None else 10**9)
            out["map"] = {"refLat": args.lat, "refLon": args.lon, "pages": page_stats,
                          "candidates": nearest,
                          "note": "No candidates may mean incomplete pagination, not absent coverage"}
            out["signals"] = [get_current(key, r["itstId"]) for r in nearest[:args.check]]
    except RuntimeError as e:
        print("ERROR:", e, file=sys.stderr)
        return 1
    serialized = json.dumps(out, ensure_ascii=False, indent=2)
    print(serialized)
    if args.output:
        Path(args.output).write_text(serialized, encoding="utf-8")
        print("Saved result to:", args.output, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
