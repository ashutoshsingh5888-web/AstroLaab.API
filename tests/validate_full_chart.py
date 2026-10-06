#!/usr/bin/env python3
"""Strict full-chart regression against a direct Swiss Ephemeris oracle."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe

from engine.astronomy import calculate_chart

FIXTURE = Path(__file__).resolve().parents[1] / "workers" / "moon-sign" / "tests" / "independent-accuracy-cases.json"

TOLERANCES_ARCSEC = {
    "Sun": 0.1,
    "Moon": 0.5,
    "Mercury": 0.1,
    "Venus": 0.1,
    "Mars": 0.1,
    "Jupiter": 0.1,
    "Saturn": 0.1,
    "Rahu": 0.1,
    "Ketu": 0.1,
    "Ascendant": 1.0,
}

def norm(x: float) -> float:
    return x % 360.0

def angular_error_arcsec(a: float, b: float) -> float:
    d = abs(norm(a) - norm(b))
    d = min(d, 360.0 - d)
    return d * 3600.0

def utc_datetime(case: dict) -> datetime:
    local = datetime.fromisoformat(f'{case["date"]}T{case["time"]}').replace(
        tzinfo=ZoneInfo(case["timeZone"])
    )
    return local.astimezone(timezone.utc)

def oracle(case: dict) -> dict:
    utc = utc_datetime(case)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    jd = swe.julday(utc.year, utc.month, utc.day, hour)
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    out = {}
    for name, planet in {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY,
        "Venus": swe.VENUS, "Mars": swe.MARS, "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN, "Rahu": swe.TRUE_NODE,
    }.items():
        flags = swe.FLG_SWIEPH | swe.FLG_SIDEREAL | swe.FLG_SPEED
        out[name] = norm(float(swe.calc_ut(jd, planet, flags)[0][0]))

    out["Ketu"] = norm(out["Rahu"] + 180.0)
    out["Ascendant"] = norm(float(swe.houses_ex(
        jd, case["place"]["latitude"], case["place"]["longitude"],
        b"W", swe.FLG_SIDEREAL
    )[1][0]))
    out["jdUT"] = jd
    return out

def engine(case: dict) -> dict:
    utc = utc_datetime(case)
    hour = utc.hour + utc.minute / 60 + utc.second / 3600
    chart = calculate_chart(
        utc.year, utc.month, utc.day, hour,
        case["place"]["latitude"], case["place"]["longitude"],
    )
    out = {name: data["longitude"] for name, data in chart["Planets"].items()}
    out["Ascendant"] = chart["Ascendant"]["longitude"]
    return out

def lunar_bucket(lon: float) -> tuple[int, int, int]:
    rashi = int(norm(lon) // 30) + 1
    nak = int(norm(lon) // (360 / 27)) + 1
    pada = int((norm(lon) % (360 / 27)) // (360 / 108)) + 1
    return rashi, nak, pada

def main() -> int:
    cases = json.loads(FIXTURE.read_text())["cases"]
    failures = []
    max_error = {name: 0.0 for name in TOLERANCES_ARCSEC}
    boundary_count = 0

    for case in cases:
        if case.get("metadata", {}).get("boundaryCase"):
            boundary_count += 1
        ref = oracle(case)
        got = engine(case)
        for name, limit in TOLERANCES_ARCSEC.items():
            err = angular_error_arcsec(got[name], ref[name])
            max_error[name] = max(max_error[name], err)
            if err > limit:
                failures.append((case["id"], name, err, limit, got[name], ref[name]))

    print(f"Full-chart direct Swiss oracle: {len(cases)} cases")
    print(f"Boundary cases exercised: {boundary_count}")
    for name, value in max_error.items():
        print(f"max {name}: {value:.9f} arcsec (limit {TOLERANCES_ARCSEC[name]:.3f})")

    # Explicit boundary semantic smoke test: every fixture boundary remains in
    # the same Rashi/Nakshatra/Pada bucket as the direct oracle.
    bucket_failures = []
    for case in cases:
        if not case.get("metadata", {}).get("boundaryCase"):
            continue
        ref_bucket = lunar_bucket(oracle(case)["Moon"])
        got_bucket = lunar_bucket(engine(case)["Moon"])
        if ref_bucket != got_bucket:
            bucket_failures.append((case["id"], got_bucket, ref_bucket))

    print(f"Boundary bucket matches: {len(cases) and (boundary_count - len(bucket_failures))}/{boundary_count}")
    print(f"Positional failures: {len(failures)}")
    print(f"Boundary bucket failures: {len(bucket_failures)}")

    if failures:
        for row in failures[:10]:
            print("FAIL", row)
    if bucket_failures:
        for row in bucket_failures[:10]:
            print("FAIL BOUNDARY", row)

    return 1 if failures or bucket_failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
