#!/usr/bin/env python3
"""Validate the public API's explicit 1950-2050 Delta-T support contract."""
from __future__ import annotations
import json, os, urllib.error, urllib.request

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
CASES = [
    ("below-minimum", "1949-12-31", 400),
    ("minimum-supported", "1950-01-01", 200),
    ("maximum-supported", "2050-12-31", 200),
    ("above-maximum", "2051-01-01", 400),
]
PAYLOAD_BASE = {
    "time": "12:00:00",
    "timeZone": "Asia/Kolkata",
    "place": {"name": "Mumbai", "country": "India", "latitude": 19.076, "longitude": 72.8777},
    "houseSystem": "W",
}
def call(date: str):
    payload = {**PAYLOAD_BASE, "date": date}
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", "origin": "https://astrolaab.com", "user-agent": "AstroLaab-API-Boundary/1.0", "accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try: body = json.loads(raw)
        except Exception: body = {"raw": raw}
        return exc.code, body

failures = 0
for label, date, expected_status in CASES:
    status, body = call(date)
    ok = status == expected_status
    if expected_status == 200:
        profile = body.get("calculationProfile", {})
        rng = profile.get("supportedDeltaTYearRange")
        ok = ok and body.get("ok") is True and rng == {"min": 1950, "max": 2050}
        print(f"{'PASS' if ok else 'FAIL'} {label}: HTTP {status}, range={rng}")
    else:
        ok = ok and body.get("ok") is False and "outside supported range" in str(body.get("error", ""))
        print(f"{'PASS' if ok else 'FAIL'} {label}: HTTP {status}, error={body.get('error')}")
    failures += 0 if ok else 1
print(f"\nAPI year-boundary contract: {len(CASES)-failures}/{len(CASES)} passed")
raise SystemExit(1 if failures else 0)
