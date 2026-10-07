#!/usr/bin/env python3
"""Generate tests/fixtures/nutation-reference.json from pyswisseph.

Nutation in longitude (arcsec) at mid-month TT Julian Days 1949-2051, used to pin
the Worker's nutation series. `--check` fails if the committed file differs.
"""
import json, sys
from pathlib import Path
import swisseph as swe

OUT = Path(__file__).resolve().parents[1] / "fixtures" / "nutation-reference.json"

def build():
    rows = []
    for y in range(1949, 2052):
        for m in range(1, 13):
            jd_tt = swe.julday(y, m, 15, 12.0)
            rows.append({"jdTT": round(jd_tt, 4), "dpsi": round(swe.calc(jd_tt, swe.ECL_NUT, 0)[0][2] * 3600.0, 5)})
    return {"generator": "tests/tools/generate-nutation-fixture.py", "swissephVersion": swe.version, "rows": rows}

if __name__ == "__main__":
    text = json.dumps(build(), separators=(",", ":")).replace('{"jdTT"', '\n{"jdTT"') + "\n"
    if "--check" in sys.argv:
        try:
            committed = json.loads(OUT.read_text())
        except Exception as exc:
            print(f"nutation-reference.json is invalid: {exc}; rerun the generator", file=sys.stderr)
            raise SystemExit(1)
        generated = build()
        if committed != generated:
            print("nutation-reference.json data is out of date; rerun the generator", file=sys.stderr)
            raise SystemExit(1)
        print("nutation-reference.json is up to date")
    else:
        OUT.write_text(text); print(f"wrote {OUT} ({len(text)} bytes)")
