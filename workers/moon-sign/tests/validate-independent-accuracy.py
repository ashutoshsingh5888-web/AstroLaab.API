#!/usr/bin/env python3
"""
Independent Astro Laab birth-chart regression test.

This test deliberately computes reference positions with the independently
maintained pyswisseph Python binding rather than importing the Worker package.
The Worker is queried over HTTP, and its output is compared to the reference.

The reference is generated at runtime, so expected astronomical values are
never copied into the production Worker.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import swisseph as swe


ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)

CASES_PATH = Path(__file__).with_name("independent-accuracy-cases.json")

# Strict regression tolerances sized from the observed post-Delta-T-fix error.
# These are deliberately much tighter than the old 5 arcsecond Moon gate.
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
    "Ayanamsha": 0.1,
}

DELTA_T_TOLERANCE_SECONDS = 0.5

BODY_IDS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mercury": swe.MERCURY,
    "Venus": swe.VENUS,
    "Mars": swe.MARS,
    "Jupiter": swe.JUPITER,
    "Saturn": swe.SATURN,
    "Rahu": swe.MEAN_NODE,
}

SIGNS = [
    "Mesha", "Vrishabha", "Mithuna", "Karka", "Simha", "Kanya",
    "Tula", "Vrishchika", "Dhanu", "Makara", "Kumbha", "Meena",
]


def angular_error_arcsec(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    if d > 180.0:
        d = 360.0 - d
    return d * 3600.0


def local_datetime(case: dict) -> datetime:
    return datetime.fromisoformat(
        f"{case['date']}T{case['time']}"
    ).replace(tzinfo=ZoneInfo(case["timeZone"]))


def reference_chart(case: dict) -> dict:
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    local = local_datetime(case)
    utc = local.astimezone(timezone.utc)

    hour = (
        utc.hour
        + utc.minute / 60.0
        + utc.second / 3600.0
        + utc.microsecond / 3_600_000_000.0
    )
    jd_ut = swe.julday(utc.year, utc.month, utc.day, hour)

    # Use Swiss Ephemeris' own delta-T model independently in the reference.
    delta_t_seconds = swe.deltat(jd_ut) * 86400.0
    jd_tt = jd_ut + delta_t_seconds / 86400.0

    ay_tt = swe.get_ayanamsa_ut(jd_tt)
    ay_ut = swe.get_ayanamsa_ut(jd_ut)

    expected: dict[str, float] = {}
    for name, body_id in BODY_IDS.items():
        values, _ = swe.calc(jd_tt, body_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
        expected[name] = (values[0] - ay_tt) % 360.0

    expected["Ketu"] = (expected["Rahu"] + 180.0) % 360.0

    _, ascmc = swe.houses_ex(
        jd_ut,
        float(case["place"]["latitude"]),
        float(case["place"]["longitude"]),
        b"P",
        0,
    )
    expected["Ascendant"] = (ascmc[0] - ay_ut) % 360.0
    expected["Ayanamsha"] = ay_tt

    moon_lon = expected["Moon"]
    moon_sign_index = int(math.floor(moon_lon / 30.0)) + 1
    nakshatra_index = int(math.floor(moon_lon / (360.0 / 27.0))) + 1
    pada = int(
        math.floor(
            (moon_lon % (360.0 / 27.0))
            / ((360.0 / 27.0) / 4.0)
        )
    ) + 1

    rashi_index = moon_sign_index - 1
    part = int(math.floor((moon_lon % 30.0) / (30.0 / 9.0)))
    if rashi_index % 3 == 0:
        navamsa_index = rashi_index
    elif rashi_index % 3 == 1:
        navamsa_index = (rashi_index + 8) % 12
    else:
        navamsa_index = (rashi_index + 4) % 12
    navamsa_index = (navamsa_index + part) % 12

    return {
        "utc": utc,
        "utcOffsetMinutes": int(local.utcoffset().total_seconds() / 60),
        "julianDayUT": jd_ut,
        "julianDayTT": jd_tt,
        "deltaTSeconds": delta_t_seconds,
        "expected": expected,
        "moonSignIndex": moon_sign_index,
        "moonSignName": SIGNS[moon_sign_index - 1],
        "nakshatraIndex": nakshatra_index,
        "pada": pada,
        "navamsaIndex": navamsa_index + 1,
    }


def fetch_chart(case: dict, attempts: int = 1) -> dict:
    payload = {
        "date": case["date"],
        "time": case["time"],
        "timeZone": case["timeZone"],
        "place": case["place"],
        "houseSystem": "W",
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ENDPOINT,
        data=data,
        headers={"content-type": "application/json", "origin": "https://astrolaab.com", "user-agent": "AstroLaab-Accuracy/1.0"},
        method="POST",
    )
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(10)
    raise RuntimeError(f"HTTP request failed: {last_error}")


def planet_longitudes(body: dict) -> dict[str, float]:
    out: dict[str, float] = {}
    for planet in body.get("planets", []):
        name = str(planet.get("name", ""))
        if name in TOLERANCES_ARCSEC:
            value = planet.get("longitude")
            if isinstance(value, (int, float)) and math.isfinite(value):
                out[name] = float(value)
    return out


def run() -> int:
    cases_doc = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = cases_doc["cases"]
    print(f"Independent reference: pyswisseph {swe.version}")
    print("Worker dependency contract: @fusionstrings/panchangam npm:@jsr/fusionstrings__panchangam@0.2.1")
    print(f"Delta-T guard: <= {DELTA_T_TOLERANCE_SECONDS:.1f}s vs pyswisseph")
    print(f"Endpoint: {ENDPOINT}")
    print(f"Cases: {len(cases)}")

    failures = 0
    worker_swisseph_version = None
    max_errors: dict[str, float] = {k: 0.0 for k in TOLERANCES_ARCSEC}

    for case in cases:
        ref = reference_chart(case)
        body = fetch_chart(case, attempts=2)

        bad: list[str] = []

        case_year = int(case["date"][:4])
        if not (SUPPORTED_YEAR_MIN <= case_year <= SUPPORTED_YEAR_MAX):
            bad.append("supported-year-range")

        if body.get("ok") is not True:
            bad.append("HTTP/ok")
        worker_swisseph_version = worker_swisseph_version or body.get("swissephVersion")
        if body.get("swissephVersion") is None:
            bad.append("swisseph-version")
        if body.get("engine") != "Swiss Ephemeris":
            bad.append("engine")
        current_worker_version = body.get("swissephVersion")
        if worker_swisseph_version is None:
            worker_swisseph_version = current_worker_version
            print(f"Worker Swiss Ephemeris version: {worker_swisseph_version}")
        elif current_worker_version != worker_swisseph_version:
            bad.append("swisseph-version-drift")
        if body.get("calculationProfile", {}).get("ayanamsha") != "Lahiri (Chitrapaksha)":
            bad.append("Lahiri")
        if body.get("calculationProfile", {}).get("timeScales", {}).get("planets") != "TT":
            bad.append("planets=TT")
        if body.get("calculationProfile", {}).get("timeScales", {}).get("houses") != "UT":
            bad.append("houses=UT")

        worker_delta_t = body.get("calculationProfile", {}).get("timeScales", {}).get("deltaTSeconds")
        if not isinstance(worker_delta_t, (int, float)) or not math.isfinite(worker_delta_t):
            bad.append("deltaTSeconds")
        else:
            delta_t_error = abs(float(worker_delta_t) - ref["deltaTSeconds"])
            max_delta_t_error = max(max_delta_t_error, delta_t_error)
            if delta_t_error > DELTA_T_TOLERANCE_SECONDS:
                bad.append(f"deltaT={delta_t_error:.3f} s")

        birth = body.get("birth", {})
        if birth.get("utcOffsetMinutes") != ref["utcOffsetMinutes"]:
            bad.append("utc-offset")
        try:
            worker_utc = datetime.fromisoformat(
                str(birth.get("utc")).replace("Z", "+00:00")
            )
            if abs((worker_utc - ref["utc"]).total_seconds()) > 0.5:
                bad.append("UTC")
        except Exception:
            bad.append("UTC")

        time_scales = body.get("calculationProfile", {}).get("timeScales", {})
        worker_delta_t = time_scales.get("deltaTSeconds")
        if not isinstance(worker_delta_t, (int, float)) or not math.isfinite(worker_delta_t):
            bad.append("deltaTSeconds")
        elif abs(float(worker_delta_t) - ref["deltaTSeconds"]) > DELTA_T_TOLERANCE_SECONDS:
            bad.append(
                f"deltaT={float(worker_delta_t):.3f}s vs ref={ref['deltaTSeconds']:.3f}s"
            )

        actual_planets = planet_longitudes(body)
        expected = ref["expected"]

        for name in TOLERANCES_ARCSEC:
            if name == "Ascendant":
                asc = body.get("houses", {}).get("ascendant", {})
                if not isinstance(asc.get("degreeInSign"), (int, float)):
                    bad.append("Ascendant")
                    continue
                actual = (
                    (int(asc.get("index", 1)) - 1) * 30.0
                    + float(asc["degreeInSign"])
                )
            elif name == "Ayanamsha":
                try:
                    actual = float(body["ayanamsha"]["degrees"])
                except Exception:
                    bad.append("Ayanamsha")
                    continue
            else:
                if name not in actual_planets:
                    bad.append(name)
                    continue
                actual = actual_planets[name]

            error = (
                abs(actual - expected[name]) * 3600.0
                if name == "Ayanamsha"
                else angular_error_arcsec(actual, expected[name])
            )
            max_errors[name] = max(max_errors[name], error)
            if error > TOLERANCES_ARCSEC[name]:
                bad.append(f"{name}={error:.3f} arcsec")

        moon = body.get("moon", {})
        if moon.get("sign", {}).get("index") != ref["moonSignIndex"]:
            bad.append("Moon sign")
        if moon.get("nakshatra", {}).get("index") != ref["nakshatraIndex"]:
            bad.append("Nakshatra")
        if moon.get("nakshatra", {}).get("pada") != ref["pada"]:
            bad.append("Pada")
        if moon.get("navamsa", {}).get("index") != ref["navamsaIndex"]:
            bad.append("D9")

        if case.get("metadata", {}).get("boundaryCase"):
            if not body.get("boundaryWarning"):
                bad.append("boundary-warning")

        if bad:
            failures += 1
            print(f"FAIL {case['id']}: {', '.join(bad)}")
            print(json.dumps({
                "expected": expected,
                "actualMoon": body.get("moon", {}).get("siderealLongitude"),
                "actualPlanets": actual_planets,
                "actualAyanamsha": body.get("ayanamsha", {}).get("degrees"),
                "actualAscendant": body.get("houses", {}).get("ascendant"),
            }, indent=2))
        else:
            print(f"PASS {case['id']}")

    print("\nMaximum observed errors (arcsec):")
    for name, value in max_errors.items():
        print(f"  {name}: {value:.6f} arcsec (limit {TOLERANCES_ARCSEC[name]:.1f} arcsec)")

    if failures:
        print(f"\nFAILED: {failures}/{len(cases)} cases")
        return 1

    print(f"\nPASSED: {len(cases)}/{len(cases)} independent regression cases")
    return 0


if __name__ == "__main__":
    sys.exit(run())
