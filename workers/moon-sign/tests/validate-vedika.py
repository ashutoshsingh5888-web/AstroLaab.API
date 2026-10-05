#!/usr/bin/env python3
"""Optional Vedika production cross-check.

This is informational, not the astronomical accuracy gate. Vedika's keyless
sandbox uses realistic mock data, so only a real production API key is suitable
for a genuine external-engine comparison.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path


ENDPOINT = os.environ.get("VEDIKA_ENDPOINT", "https://api.vedika.io/v2/astrology/kundli")
API_KEY = os.environ.get("VEDIKA_API_KEY")
CASES_PATH = Path(__file__).with_name("independent-accuracy-cases.json")

if not API_KEY:
    print("VEDIKA: SKIP (VEDIKA_API_KEY is not configured)")
    raise SystemExit(0)


def fetch(case: dict) -> dict:
    payload = {
        "datetime": f"{case['date']}T{case['time']}",
        "latitude": case["place"]["latitude"],
        "longitude": case["place"]["longitude"],
        "timezone": case["timeZone"],
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    failures = 0

    for case in cases:
        try:
            data = fetch(case)
            if data.get("success") is not True:
                raise RuntimeError(data.get("error", "unknown Vedika error"))

            chart = data.get("data", {})
            moon = chart.get("moon", {})
            vedika_sign = moon.get("sign")

            if not vedika_sign:
                raise RuntimeError("Moon sign missing from Vedika response")

            print(f"PASS {case['id']}: Vedika Moon Sign={vedika_sign}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {case['id']}: {exc}")
            time.sleep(1)

    print(f"Vedika production cross-check: {len(cases) - failures}/{len(cases)} responses valid")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
