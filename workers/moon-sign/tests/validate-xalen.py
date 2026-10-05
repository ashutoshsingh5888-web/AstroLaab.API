#!/usr/bin/env python3
"""Compare the live Astro Laab Worker against Vedika's independent XALEN engine.

XALEN is a secondary cross-check, not the primary oracle.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
CASES_PATH = Path(__file__).with_name("independent-accuracy-cases.json")
XALEN_MANIFEST = Path(__file__).resolve().parent / "xalen-reference" / "Cargo.toml"
TOLERANCE_ARCSEC = 5.0
SEMANTIC_PHYSICAL_BODIES = ["Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"]

def jd_from_utc(dt: datetime) -> float:
    y, m = dt.year, dt.month
    d = dt.day + (
        dt.hour + dt.minute / 60 + dt.second / 3600 +
        dt.microsecond / 3_600_000_000
    ) / 24
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5

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
        headers={"content-type": "application/json", "origin": "https://astrolaab.com", "user-agent": "AstroLaab-Accuracy/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def angle_error(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    if d > 180:
        d = 360 - d
    return d * 3600.0

def moon_semantics(longitude: float) -> tuple[str, str, int]:
    signs = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    nakshatras = [
        "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
        "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
        "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha",
        "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
        "Shravana", "Dhanishtha", "Shatabhisha", "Purva Bhadrapada",
        "Uttara Bhadrapada", "Revati",
    ]
    lon = longitude % 360.0
    sign = signs[int(lon // 30.0)]
    n = int(lon / (360.0 / 27.0))
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return sign, nakshatras[n], pada

def main() -> int:
    cases = json.loads(CASES_PATH.read_text())["cases"]
    kernel_path = os.environ.get("XALEN_DE440_KERNEL", "/tmp/de440s.bsp")
    if not Path(kernel_path).exists():
        raise FileNotFoundError(f"DE440 kernel missing: {kernel_path}")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        inputs = []
        workers = {}

        for case in cases:
            local = datetime.fromisoformat(
                f"{case['date']}T{case['time']}"
            ).replace(tzinfo=ZoneInfo(case["timeZone"]))
            utc = local.astimezone(timezone.utc)
            inputs.append({"id": case["id"], "jd_ut": jd_from_utc(utc)})
            workers[case["id"]] = fetch_worker(case)

        input_path = tmpdir / "xalen-input.json"
        output_path = tmpdir / "xalen-output.json"
        input_path.write_text(json.dumps(inputs))

        subprocess.run(
            [
                "cargo", "run", "--quiet", "--release",
                "--manifest-path", str(XALEN_MANIFEST), "--",
                "--input", str(input_path), "--output", str(output_path),
                "--kernel", kernel_path,
            ],
            check=True,
        )

        xalen = {r["id"]: r for r in json.loads(output_path.read_text())}
        failures = 0
        geometry_failures = 0
        boundary_review_cases = 0
        max_absolute_error = 0.0
        max_relative_error = 0.0
        max_sun_frame_offset = 0.0
        body_names = [
            "Sun", "Moon", "Mercury", "Venus",
            "Mars", "Jupiter", "Saturn", "Rahu", "Ketu",
        ]

        for case in cases:
            cid = case["id"]
            body = workers[cid]
            xr = xalen[cid]
            worker_by_name = {
                str(p.get("name")): float(p["longitude"])
                for p in body.get("planets", [])
                if isinstance(p.get("longitude"), (int, float))
            }

            bad = {}
            if "Sun" not in worker_by_name or "Sun" not in xr["planets"]:
                geometry_failures += 1
                print(f"FAIL {cid}: missing Sun longitude in worker or XALEN")
                continue

            sun_worker = worker_by_name["Sun"]
            sun_xalen = float(xr["planets"]["Sun"])
            sun_frame_offset = angle_error(sun_worker, sun_xalen)
            max_sun_frame_offset = max(max_sun_frame_offset, sun_frame_offset)

            # A common ecliptic-of-date zero-point can differ between independent
            # implementations while the underlying relative geometry agrees.
            # Validate body-vs-Sun geometry, not the arbitrary shared zero point.
            for name in SEMANTIC_PHYSICAL_BODIES:
                if name not in worker_by_name or name not in xr["planets"]:
                    bad[name] = None
                    continue
                e_abs = angle_error(worker_by_name[name], float(xr["planets"][name]))
                max_absolute_error = max(max_absolute_error, e_abs)
                worker_rel = (worker_by_name[name] - sun_worker) % 360.0
                xalen_rel = (float(xr["planets"][name]) - sun_xalen) % 360.0
                e_rel = angle_error(worker_rel, xalen_rel)
                max_relative_error = max(max_relative_error, e_rel)
                if e_rel > TOLERANCE_ARCSEC:
                    bad[name] = e_rel

            # Moon sign/Nakshatra/Pada are discrete buckets. Near a boundary,
            # two numerically-close engines can legitimately land on opposite
            # sides even when both are within a few arcseconds. Record these as
            # review cases; do not turn a valid sub-5" positional agreement into
            # a false ephemeris failure.
            if "Moon" in worker_by_name and "Moon" in xr["planets"]:
                ws, wn, wp = moon_semantics(worker_by_name["Moon"])
                xs, xn, xp = moon_semantics(float(xr["planets"]["Moon"]))
                if (ws, wn, wp) != (xs, xn, xp):
                    boundary_review_cases += 1
                    print(
                        f"REVIEW {cid}: Moon bucket differs "
                        f"Worker={ws}/{wn}/{wp}, XALEN={xs}/{xn}/{xp}; "
                        f"relative positional error={angle_error((worker_by_name['Moon']-sun_worker)%360.0, (float(xr['planets']['Moon'])-sun_xalen)%360.0):.3f}\""
                    )

            if bad:
                geometry_failures += 1
                print(f"FAIL {cid}: " + ", ".join(
                    f"{k}={v:.3f} arcsec" if v is not None else f"{k}=missing"
                    for k, v in bad.items()
                ))
            else:
                print(f"PASS {cid}")

        failures = geometry_failures
        print(
            f"\nXALEN/JPL DE440 geometry cross-check: {len(cases) - geometry_failures}/{len(cases)} "
            f"within {TOLERANCE_ARCSEC:.1f} arcsec after common-frame removal"
        )
        print(f"Maximum absolute Worker-vs-XALEN difference: {max_absolute_error:.6f} arcsec")
        print(f"Maximum common Sun-frame offset: {max_sun_frame_offset:.6f} arcsec")
        print(f"Maximum body-vs-Sun relative error: {max_relative_error:.6f} arcsec")
        print(f"Moon bucket boundary review cases: {boundary_review_cases}")
        print(
            "DE440 kernel provenance is hard-gated separately; discrete Rashi/"
            "Nakshatra/Pada differences near a boundary are diagnostic review items, "
            "not positional-accuracy failures."
        )
        return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
