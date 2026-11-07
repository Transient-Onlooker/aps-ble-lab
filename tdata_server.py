#!/usr/bin/env python3
"""Local, read-only T-DATA web gateway. No key or raw provider URL reaches clients.

Start with: py -3 tdata_server.py
Open http://127.0.0.1:8765/
"""
from __future__ import annotations

import argparse
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from tdata_probe import get_current, local_api_key

ROOT = Path(__file__).resolve().parent
DEFAULT_STATE = ROOT / "private" / "tdata-web-state.json"
HTML_PATH = ROOT / "tdata.html"
ARCHIVE_PATH = ROOT / "research" / "tdata" / "validation_2026-11-07.json"
INTERSECTIONS = {
    "710": "경찰병원후문",
    "20710": "경찰병원후문(연등)",
}
SAFETY_NOTE = "연구·검증용. 현장 신호 대조 전이며 보행 안전 판단에 사용 금지."


class Gateway:
    def __init__(self, key, state_path=DEFAULT_STATE, max_requests=800, cache_seconds=15, clock=time.time):
        if not key:
            raise ValueError("TDATA_API_KEY is required (environment variable or local .env)")
        if not (1 <= max_requests <= 1000 and 1 <= cache_seconds <= 3600):
            raise ValueError("Invalid local budget/cache settings")
        self.key = key
        self.state_path = Path(state_path)
        self.max_requests = max_requests
        self.cache_seconds = cache_seconds
        self.clock = clock
        self.lock = threading.Lock()
        self.attempts = []
        self.cache = {}
        self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
                self.attempts = [float(v) for v in state["attempts"]]
                self.cache = dict(state.get("cache", {}))
            except (KeyError, ValueError, TypeError, OSError) as exc:
                raise RuntimeError("Local rate-limit state invalid; refusing to reset quota automatically") from exc

    def _save(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        path = self.state_path.with_name(self.state_path.name + ".tmp")
        state = {"attempts": self.attempts, "cache": self.cache,
                 "note": "Local requests only; other tools may also consume provider quota."}
        path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(path, self.state_path)

    def status(self, itst_id):
        if itst_id not in INTERSECTIONS:
            return 400, {"error": "허용된 교차로 ID는 710, 20710뿐입니다."}
        with self.lock:
            now = float(self.clock())
            self.attempts = [v for v in self.attempts if 0 <= now - v < 86400]
            cached = self.cache.get(itst_id)
            if cached and 0 <= now - cached["fetchedUnix"] < self.cache_seconds:
                return 200, self._response(itst_id, cached, now, True)
            if len(self.attempts) >= self.max_requests:
                return 429, {"error": "로컬 API 요청 예산 소진. 자동 재시도하지 않습니다.",
                             "attemptsIn24h": len(self.attempts), "maxRequests24h": self.max_requests,
                             "note": SAFETY_NOTE}
            # Count before the network call, including errors, to avoid uncontrolled retries.
            self.attempts.append(now)
            self._save()
            try:
                result = get_current(self.key, itst_id)
            except RuntimeError:
                return 502, {"error": "T-DATA 조회 실패. 인증·연결·호출 제한을 로컬에서 확인하세요.",
                             "attemptsIn24h": len(self.attempts), "note": SAFETY_NOTE}
            matching = [r for r in result.get("records", [])
                        if str(r.get("itstId")) == itst_id]
            if not matching:
                return 502, {"error": "해당 ID의 유효한 실시간 레코드가 없습니다.",
                             "attemptsIn24h": len(self.attempts), "note": SAFETY_NOTE}
            row = matching[0]
            record = {"itstId": itst_id, "timestampUTC": row.get("timestampUTC"),
                      "trsmUtcTime": row.get("trsmUtcTime"),
                      "pedestrianFieldsRaw": {
                          k: v for k, v in row.get("pedestrianFieldsRaw", {}).items()
                          if k.endswith(("PdsgStatNm", "PdsgRmdrCs")) and
                          isinstance(v, (int, float, str, type(None))) and len(k) <= 32
                      }}
            entry = {"fetchedUnix": now, "record": record}
            self.cache[itst_id] = entry
            self._save()
            return 200, self._response(itst_id, entry, now, False)

    def _response(self, itst_id, entry, now, cache_hit):
        return {"itstId": itst_id, "name": INTERSECTIONS[itst_id],
                "snapshot": entry["record"],
                "serverFetchedUTC": datetime.fromtimestamp(entry["fetchedUnix"], timezone.utc).isoformat(),
                "cacheAgeSeconds": round(max(0, now - entry["fetchedUnix"]), 1),
                "cached": cache_hit, "cacheTTLSeconds": self.cache_seconds,
                "attemptsIn24h": len(self.attempts), "maxRequests24h": self.max_requests,
                "note": SAFETY_NOTE}


def make_handler(gateway):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, status, value, mime="application/json; charset=utf-8"):
            if isinstance(value, (dict, list)):
                data = json.dumps(value, ensure_ascii=False).encode("utf-8")
            elif isinstance(value, str):
                data = value.encode("utf-8")
            else:
                data = value
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'self' 'unsafe-inline'; "
                             "script-src 'self' 'unsafe-inline'; connect-src 'self'; "
                             "img-src 'self' data:; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            # Only loopback-origin requests; never accept arbitrary Host/Origin.
            host = self.headers.get("Host", "")
            if host not in (f"127.0.0.1:{self.server.server_port}",
                            f"localhost:{self.server.server_port}"):
                return self.respond(403, {"error": "로컬 호스트 전용입니다."})
            origin = self.headers.get("Origin")
            if origin and origin not in (f"http://127.0.0.1:{self.server.server_port}",
                                         f"http://localhost:{self.server.server_port}"):
                return self.respond(403, {"error": "외부 출처 요청 거부"})
            target = urlsplit(self.path)
            if target.path in ("/", "/tdata.html"):
                return self.respond(200, HTML_PATH.read_bytes(), "text/html; charset=utf-8")
            if target.path == "/research/tdata/validation_2026-11-07.json":
                return self.respond(200, ARCHIVE_PATH.read_bytes(), "application/json; charset=utf-8")
            if target.path == "/api/status":
                # Cross-origin simple requests cannot set this custom header.
                if self.headers.get("X-APS-Request") != "1":
                    return self.respond(403, {"error": "요청 헤더 누락"})
                qs = parse_qs(target.query)
                if set(qs) != {"itstId"} or len(qs["itstId"]) != 1:
                    return self.respond(400, {"error": "itstId 파라미터 오류"})
                code, body = gateway.status(qs["itstId"][0])
                return self.respond(code, body)
            return self.respond(404, {"error": "지원하지 않는 경로"})

        def log_message(self, fmt, *args):
            # Never log credentials; URL requests here contain ID only.
            super().log_message(fmt, *args)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Local T-DATA dashboard gateway (loopback-only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--budget", type=int, default=800,
                        help="Maximum this server's upstream attempts per rolling 24 h (default 800)")
    parser.add_argument("--cache-seconds", type=int, default=15)
    args = parser.parse_args()
    if not (1024 <= args.port <= 65535):
        parser.error("port must be in 1024..65535")
    try:
        gateway = Gateway(local_api_key(), max_requests=args.budget,
                          cache_seconds=args.cache_seconds)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(gateway))
    except (ValueError, RuntimeError, OSError) as error:
        parser.error(str(error))
    print(f"T-DATA local dashboard: http://127.0.0.1:{args.port}/")
    print("Key stays server-side. No automatic polling. Press Ctrl+C to exit.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
