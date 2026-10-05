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
XALEN_MANIFEST = Path(__file__).with_name("xalen-reference/Cargo.toml")
TOLERANCE_ARCSEC = 5.0

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
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode())

def angle_error(a: float, b: float) -> float:
    d = abs((a - b) % 360.0)
    if d > 180:
        d = 360 - d
    return d * 3600.0

def main() -> int:
    cases = json.loads(CASES_PATH.read_text())["cases"]

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
            ],
            check=True,
        )

        xalen = {r["id"]: r for r in json.loads(output_path.read_text())}
        failures = 0
        max_error = 0.0
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
            for name in body_names:
                if name not in worker_by_name or name not in xr["planets"]:
                    bad[name] = None
                    continue
                e = angle_error(worker_by_name[name], float(xr["planets"][name]))
                max_error = max(max_error, e)
                if e > TOLERANCE_ARCSEC:
                    bad[name] = e

            if bad:
                failures += 1
                print(f"FAIL {cid}: " + ", ".join(
                    f"{k}={v:.3f} arcsec" if v is not None else f"{k}=missing"
                    for k, v in bad.items()
                ))
            else:
                print(f"PASS {cid}")

        print(
            f"\nXALEN cross-check: {len(cases) - failures}/{len(cases)} "
            f"within {TOLERANCE_ARCSEC:.1f} arcsec"
        )
        print(f"Maximum Worker-vs-XALEN difference: {max_error:.6f} arcsec")
        print(
            "Secondary implementation cross-check only; pyswisseph remains "
            "the primary accuracy gate."
        )
        return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
