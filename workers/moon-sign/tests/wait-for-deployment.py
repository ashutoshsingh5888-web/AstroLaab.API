#!/usr/bin/env python3
"""Wait for the live Moon Sign Worker to answer a known-good request."""
from __future__ import annotations
import json, os, time, urllib.request

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
PAYLOAD = {
    "date": "2000-01-01",
    "time": "12:00:00",
    "timeZone": "Asia/Kolkata",
    "place": {"name": "Kolkata", "country": "India", "latitude": 22.5726, "longitude": 88.3639},
    "houseSystem": "W",
}
for attempt in range(1, 19):
    try:
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(PAYLOAD).encode(),
            headers={"content-type": "application/json", "origin": "https://astrolaab.com", "user-agent": "AstroLaab-Readiness/1.0", "accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            body = json.loads(response.read().decode())
            if response.status == 200 and body.get("ok") is True:
                profile = body.get("calculationProfile", {})
                print(f"Deployment ready on attempt {attempt}: HTTP 200")
                print(f"Swiss Ephemeris: {body.get('swissephVersion')}")
                print(f"Delta-T range: {profile.get('supportedDeltaTYearRange')}")
                raise SystemExit(0)
            print(f"Attempt {attempt}: HTTP {response.status}, ok={body.get('ok')}")
    except Exception as exc:
        print(f"Attempt {attempt}: {exc}")
    if attempt < 18:
        time.sleep(5)
raise SystemExit("Live Worker did not become ready within 90 seconds")
