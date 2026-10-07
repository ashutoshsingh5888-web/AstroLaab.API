#!/usr/bin/env python3
"""Pada review check.

Decision rule (agreed in review): if the Moon is within PADA_ROUNDING_ARCMIN of a
Pada edge, a Pada mismatch with a public platform is rounding or birth-time
uncertainty -> REVIEW (non-failing). If it is farther away, a mismatch is a real
discrepancy -> FAIL.

Always runs offline against pyswisseph. If ASTROLAAB_ENDPOINT is set, the Worker
is also called with the exact data AstroSage printed (explicit UTC offset) and
must agree with pyswisseph to MOON_TOL_ARCSEC and with AstroSage on Pada.
"""
import json, os, sys, urllib.request
from pathlib import Path
import swisseph as swe

ROOT = Path(__file__).resolve().parent
PADA_ROUNDING_ARCMIN = 1.5
MOON_TOL_ARCSEC = 0.5
ASTROSAGE_SANITY_ARCSEC = 90.0   # AstroSage vs Swiss differs by tens of arcsec (rounding/ephemeris/dT)
PADA = 360.0 / 108.0


def pada_info(lon):
    slot = int((lon % 360.0) / PADA + 1e-9)
    off = (lon % 360.0) % PADA
    return slot // 4 + 1, slot % 4 + 1, min(off, PADA - off) * 60.0  # nakshatra, pada, edge distance (arcmin)


def swiss_moon(case):
    y, m, d = map(int, case["date"].split("-"))
    hh, mm, ss = map(int, case["time"].split(":"))
    ut_hours = hh + mm / 60 + ss / 3600 - case["utcOffsetMinutes"] / 60.0
    jd = swe.julday(y, m, d, 0.0) + ut_hours / 24.0
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    jt = jd + swe.deltat(jd)
    return swe.calc(jt, swe.MOON, swe.FLG_MOSEPH | swe.FLG_SIDEREAL)[0][0] % 360.0  # Swiss-native sidereal


def worker_moon(endpoint, case):
    body = {k: case[k] for k in ("date", "time", "timeZone", "utcOffsetMinutes", "place")}
    req = urllib.request.Request(endpoint, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "astrolaab-validator/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    cases = json.load(open(ROOT / "fixtures" / "pada-review-cases.json"))["cases"]
    endpoint = os.environ.get("ASTROLAAB_ENDPOINT")
    failures = 0
    for c in cases:
        a = c["astrosage"]
        d, mi, s = a["moonDms"]
        as_lon = a["moonSignIndex"] * 30 + d + mi / 60 + s / 3600
        as_nak, as_pada, as_edge = pada_info(as_lon)
        sw = swiss_moon(c)
        sw_nak, sw_pada, sw_edge = pada_info(sw)
        diff = (sw - as_lon) * 3600
        print(f"[{c['id']}]")
        print(f"  AstroSage printed Moon {as_lon:.5f}  -> nak#{as_nak} pada {as_pada}  edge {as_edge:.2f}'   (page says pada {a['pada']})")
        print(f"  pyswisseph Moon        {sw:.5f}  -> nak#{sw_nak} pada {sw_pada}  edge {sw_edge:.2f}'   diff vs AstroSage {diff:+.1f}\"")
        problems = []
        if as_pada != a["pada"]:
            problems.append("AstroSage's own printed longitude disagrees with its printed Pada (scraper/fixture error)")
        if abs(diff) > ASTROSAGE_SANITY_ARCSEC:
            problems.append(f"pyswisseph Moon is {diff:+.0f}\" from AstroSage's printed Moon: birth data/offset in the fixture is wrong")
        if sw_pada != a["pada"] or sw_nak != as_nak:
            if sw_edge <= PADA_ROUNDING_ARCMIN:
                print(f"  REVIEW: Pada differs but Moon is {sw_edge:.2f}' from a Pada edge (rounding / birth-time uncertainty)")
            else:
                problems.append(f"Pada mismatch with the Moon {sw_edge:.2f}' from the nearest edge: not rounding")
        if endpoint:
            j = worker_moon(endpoint, c)
            wl = j["moon"]["siderealLongitude"]
            werr = abs((wl - sw + 180) % 360 - 180) * 3600
            print(f"  Worker Moon            {wl:.5f}  pada {j['moon']['nakshatra']['pada']}  error vs pyswisseph {werr:.3f}\"")
            if werr > MOON_TOL_ARCSEC:
                problems.append(f"Worker Moon is {werr:.3f}\" from pyswisseph (limit {MOON_TOL_ARCSEC}\")")
            if j["moon"]["nakshatra"]["pada"] != a["pada"] and sw_edge > PADA_ROUNDING_ARCMIN:
                problems.append("Worker Pada differs from AstroSage far from any edge")
        for p in problems:
            print("  FAIL:", p)
        failures += bool(problems)
        if not problems:
            print("  PASS")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
