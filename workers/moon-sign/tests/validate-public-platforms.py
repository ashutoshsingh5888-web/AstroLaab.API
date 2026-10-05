#!/usr/bin/env python3
"""Validate stable Moon-sign semantics against pinned public astrology platforms.

The platforms are treated as consumer-facing compatibility references, not
astronomical ground truth. Raw lunar longitudes can differ across platforms,
so the hard gate is Moon sign + nakshatra + pada for identical birth inputs.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
FIXTURE_PATH = Path(__file__).with_name("public-platform-reference.json")

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira",
    "Ardra", "Punarvasu", "Pushya", "Ashlesha", "Magha",
    "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra",
    "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula",
    "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishtha",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

def normalize_deg(x: float) -> float:
    return x % 360.0

def semantic(longitude: float) -> tuple[str, str, int]:
    lon = normalize_deg(longitude)
    sign_index = int(lon // 30.0)
    nak_index = int(lon / (360.0 / 27.0))
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return SIGNS[sign_index], NAKSHATRAS[nak_index], pada

def fetch_worker(case: dict) -> dict:
    payload = {
        "date": case["date"],
        "time": case["time"],
        "timeZone": case["timeZone"],
        "place": case["place"],
        "houseSystem": "W",
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode(),
        headers={
            "content-type": "application/json",
            "origin": "https://astrolaab.com",
            "user-agent": "AstroLaab-PublicPlatformValidation/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def main() -> int:
    fixture = json.loads(FIXTURE_PATH.read_text())
    case = fixture["case"]
    response = fetch_worker(case)

    moon = next(
        (
            p for p in response.get("planets", [])
            if str(p.get("name")) == "Moon"
            and isinstance(p.get("longitude"), (int, float))
        ),
        None,
    )
    if moon is None:
        print("FAIL: Worker did not return a numeric Moon longitude")
        return 1

    worker_lon = float(moon["longitude"])
    worker_semantics = semantic(worker_lon)
    failures = 0

    print(f"Worker Moon longitude: {worker_lon:.9f}°")
    print(
        "Worker semantics: "
        f"{worker_semantics[0]} / {worker_semantics[1]} / pada {worker_semantics[2]}"
    )

    for source in case["sources"]:
        expected = (
            source["moonSign"],
            source["nakshatra"],
            int(source["pada"]),
        )
        ok = worker_semantics == expected
        delta_arcsec = abs(worker_lon - float(source["moonLongitude"]))
        delta_arcsec = min(delta_arcsec, 360.0 - delta_arcsec) * 3600.0
        print(
            f"{'PASS' if ok else 'FAIL'} {source['name']}: "
            f"expected {expected[0]} / {expected[1]} / pada {expected[2]}; "
            f"published longitude {float(source['moonLongitude']):.9f}°; "
            f"raw longitude delta {delta_arcsec:.3f}\""
        )
        if not ok:
            failures += 1

    print(
        f"\nPublic-platform semantic cross-check: "
        f"{len(case['sources']) - failures}/{len(case['sources'])} platform references matched"
    )
    print(
        "Note: raw longitude is informational here because the published "
        "platforms themselves differ by ~36 arcmin on this historical chart "
        "while agreeing on Rashi/Nakshatra/Pada."
    )
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
