#!/usr/bin/env python3
"""API contract checks for timezone conversion and calendar validation."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from main import ChartRequest
from engine.astronomy import calculate_chart

def main() -> int:
    failures = []

    # Invalid dates must be rejected at validation time, not become HTTP 500s.
    try:
        ChartRequest(
            year=2024, month=2, day=30, hour=12, minute=0,
            latitude=19.076, longitude=72.8777,
        )
        failures.append("invalid calendar date accepted")
    except ValidationError:
        pass

    # 14:30 IST is 09:00 UTC; the Moon longitude is a known Swiss reference.
    local = datetime(1990, 5, 15, 14, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    utc = local.astimezone(timezone.utc)
    chart = calculate_chart(
        utc.year, utc.month, utc.day,
        utc.hour + utc.minute / 60,
        19.076, 72.8777,
    )
    moon = chart["Planets"]["Moon"]["longitude"]
    expected = 271.893544051776
    if abs(moon - expected) * 3600 > 0.5:
        failures.append(f"IST->UTC Moon regression exceeded 0.5 arcsec: {moon} vs {expected}")

    if failures:
        for failure in failures:
            print("FAIL", failure)
        return 1

    print("API contract: invalid-date rejection PASS")
    print(f"API contract: IST->UTC Moon PASS ({moon:.9f} deg)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
