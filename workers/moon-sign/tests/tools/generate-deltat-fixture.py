#!/usr/bin/env python3
"""Generate tests/fixtures/deltat-reference.json from pyswisseph.

For every month 1949-2051 this stores the min and max of swe.deltat() over days
1..28, so the Worker's month-resolution Delta-T can be checked offline against
an independent reference. CI regenerates the file and fails on any diff, so the
fixture can never silently drift from the pinned pyswisseph version.
"""
import json
import sys
from pathlib import Path

import swisseph as swe

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "deltat-reference.json"


def build():
    rows = []
    for y in range(1949, 2052):
        for m in range(1, 13):
            vals = [swe.deltat(swe.julday(y, m, d, 12.0)) * 86400.0 for d in range(1, 29)]
            rows.append({"y": y, "m": m, "min": round(min(vals), 6), "max": round(max(vals), 6)})
    return {"generator": "tests/tools/generate-deltat-fixture.py", "swissephVersion": swe.version, "rows": rows}


if __name__ == "__main__":
    text = json.dumps(build(), separators=(",", ":")).replace('{"y"', '\n{"y"') + "\n"
    if "--check" in sys.argv:
        if OUT.read_text() != text:
            print("deltat-reference.json is out of date; rerun the generator", file=sys.stderr)
            raise SystemExit(1)
        print("deltat-reference.json is up to date")
    else:
        OUT.write_text(text)
        print(f"wrote {OUT} ({len(text)} bytes)")
