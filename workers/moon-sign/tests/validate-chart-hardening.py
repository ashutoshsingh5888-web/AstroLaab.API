#!/usr/bin/env python3
"""Live validation of houses, D9, Whole Sign house numbers and API behaviour.

Covers what the planet/Moon accuracy gates do not:
  A. House cusps + Ascendant vs pyswisseph (Whole Sign, Equal, Placidus)
  B. D9/Navamsa of every planet vs an independent oracle on pyswisseph longitudes
  C. Whole Sign house number of every planet vs the Ascendant
  D. API contract: DST gap/overlap, supported-range edges, polar Placidus, bad
     coordinates, malformed/oversized bodies, removed diagnostics, CORS
Needs: pip install pyswisseph==2.10.3.2. Endpoint: ASTROLAAB_ENDPOINT (default live Worker).
"""
import json, os, sys, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import swisseph as swe

ROOT = Path(__file__).resolve().parent
ENDPOINT = os.environ.get("ASTROLAAB_ENDPOINT", "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart")
BASE = ENDPOINT.rsplit("/", 1)[0]
ORIGIN = "https://astrolaab.com"
HOUSE_TOL_ARCSEC = 1.0
BOUNDARY_SKIP_ARCSEC = 2.0
FIRST_NAVAMSA = [0, 9, 6, 3, 0, 9, 6, 3, 0, 9, 6, 3]

failures = []
checks = 0


def check(ok, label, detail=""):
    global checks
    checks += 1
    if not ok:
        failures.append(f"{label} {detail}".strip())
        print("  FAIL", label, detail)


def call(path, body=None, raw=None, method="POST", origin=ORIGIN):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json", "Origin": origin, "User-Agent": "AstroLaab-Hardening/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null"), r.headers
    except urllib.error.HTTPError as e:
        txt = e.read()
        try:
            return e.code, json.loads(txt), e.headers
        except Exception:
            return e.code, txt.decode(errors="replace"), e.headers


def chart(case, **over):
    body = {k: case[k] for k in ("date", "time", "timeZone", "place")}
    body.update(over)
    return call("/birth-chart", body)


def arcsec_diff(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0) * 3600.0


def utc_jd(case):
    y, m, d = map(int, case["date"].split("-"))
    hh, mi, ss = (list(map(int, case["time"].split(":"))) + [0])[:3]
    u = datetime(y, m, d, hh, mi, ss, tzinfo=ZoneInfo(case["timeZone"])).astimezone(timezone.utc)
    return swe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600)


def navamsa_oracle(lon):
    lon %= 360.0
    sign = int(lon // 30)
    part = int((lon - sign * 30) * 9 / 30 + 1e-9)
    return (FIRST_NAVAMSA[sign] + part) % 12


def near_navamsa_edge(lon):
    off = (lon % 360.0) % (10.0 / 3.0)
    return min(off, 10.0 / 3.0 - off) * 3600.0 < BOUNDARY_SKIP_ARCSEC


def whole_sign_house(p, asc):
    return ((int(p % 360 // 30) - int(asc % 360 // 30)) % 12) + 1


def pick_cases():
    d = json.load(open(ROOT / "independent-accuracy-cases.json"))
    cs = d if isinstance(d, list) else d["cases"]
    return cs[::2]  # 25 cases spread across latitudes and years


def section_houses_d9():
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    print("A/B/C: houses, D9 and Whole Sign house numbers")
    for c in pick_cases():
        jd = utc_jd(c)
        lat, lon = c["place"]["latitude"], c["place"]["longitude"]
        systems = ["W", "E"] + (["P"] if abs(lat) <= 66.0 else [])
        for hs in systems:
            st, j, _ = chart(c, houseSystem=hs)
            check(st == 200, f"{c['id']} {hs} status", str(st))
            if st != 200:
                continue
            cusps, ascmc = swe.houses_ex(jd, lat, lon, hs.encode(), swe.FLG_SIDEREAL)
            asc = ascmc[0]
            got = [x["longitude"] for x in j["houses"]["cusps"]]
            check(j["houses"]["system"] == hs, f"{c['id']} {hs} label", j["houses"]["system"])
            check(len(got) == 12, f"{c['id']} {hs} cusp count", str(len(got)))
            if hs == "W":
                exp = [(int(asc // 30) * 30 + 30 * i) % 360 for i in range(12)]
                tol = 0.001
            elif hs == "E":
                exp, tol = [(asc + 30 * i) % 360 for i in range(12)], HOUSE_TOL_ARCSEC
            else:
                exp, tol = list(cusps), HOUSE_TOL_ARCSEC
            for i in range(12):
                e = arcsec_diff(got[i], exp[i])
                check(e <= (0.001 if hs == "W" else tol), f"{c['id']} {hs} cusp {i+1}", f"{e:.3f}\"")
            if hs == "W":
                asc_resp = (j["houses"]["ascendant"]["index"] - 1) * 30 + j["houses"]["ascendant"]["degreeInSign"]
                check(arcsec_diff(asc_resp, asc) <= HOUSE_TOL_ARCSEC, f"{c['id']} ascendant", f"{arcsec_diff(asc_resp, asc):.3f}\"")
                for p in j["planets"]:
                    exp_h = whole_sign_house(p["longitude"], asc_resp)
                    check(p["wholeSignHouse"] == exp_h, f"{c['id']} {p['name']} house", f"{p['wholeSignHouse']} != {exp_h}")
                    if p["name"] in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu") and not near_navamsa_edge(p["longitude"]):
                        got_n = p["navamsa"]["index"] - 1
                        check(got_n == navamsa_oracle(p["longitude"]), f"{c['id']} {p['name']} D9", f"{got_n} != {navamsa_oracle(p['longitude'])}")
                # D9 against pyswisseph-derived longitudes (independent of the Worker's positions)
                jt = jd + swe.deltat(jd)
                for name, pid in (("Sun", 0), ("Moon", 1), ("Mercury", 2), ("Venus", 3), ("Mars", 4), ("Jupiter", 5), ("Saturn", 6)):
                    sl = swe.calc(jt, pid, swe.FLG_MOSEPH | swe.FLG_SIDEREAL)[0][0] % 360  # Swiss-native sidereal
                    if near_navamsa_edge(sl):
                        continue
                    wp = next(p for p in j["planets"] if p["name"] == name)
                    check(wp["navamsa"]["index"] - 1 == navamsa_oracle(sl), f"{c['id']} {name} D9 vs pyswisseph", "")


def section_contract():
    print("D: API contract")
    base = {"date": "1990-05-15", "time": "14:30:00", "timeZone": "Asia/Kolkata",
            "place": {"name": "Mumbai", "country": "India", "latitude": 19.076, "longitude": 72.8777}}
    st, j, _ = call("/birth-chart", {**base, "date": "2020-03-08", "time": "02:30:00", "timeZone": "America/New_York"})
    check(st == 400 and "does not exist" in str(j.get("error")), "DST gap rejected", f"{st} {j}")
    st, j, _ = call("/birth-chart", {**base, "date": "2020-11-01", "time": "01:30:00", "timeZone": "America/New_York"})
    check(st == 200 and any(w["code"] == "ambiguous_local_time" for w in j.get("warnings", [])), "DST overlap warns", f"{st}")
    st, j, _ = call("/birth-chart", {**base, "date": "2020-11-01", "time": "01:30:00", "timeZone": "America/New_York", "utcOffsetMinutes": -300})
    check(st == 200 and j["birth"]["utc"] == "2020-11-01T06:30:00.000Z", "explicit offset resolves overlap", f"{st}")
    for date, time, tz, want in [("1949-12-31", "23:59:59", "Asia/Kolkata", 400), ("1950-01-01", "03:00:00", "Asia/Kolkata", 200),
                                 ("2050-12-31", "22:00:00", "America/New_York", 200), ("2051-01-01", "00:00:00", "UTC", 400)]:
        st, j, _ = call("/birth-chart", {**base, "date": date, "time": time, "timeZone": tz})
        check(st == want, f"range {date} {time} {tz}", f"{st}")
    for lat in (66.6, 70, -70):
        st, j, _ = call("/birth-chart", {**base, "houseSystem": "P", "place": {**base["place"], "latitude": lat}})
        check(st == 400 and "Placidus" in str(j.get("error")), f"Placidus rejected at lat {lat}", f"{st}")
    st, j, _ = call("/birth-chart", {**base, "houseSystem": "W", "place": {**base["place"], "latitude": 70}})
    check(st == 200, "Whole Sign works at lat 70", f"{st}")
    for bad in ({"latitude": None, "longitude": 72}, {"latitude": "", "longitude": 72}, {"latitude": 91, "longitude": 0}, {"latitude": 1}):
        st, _, _ = call("/birth-chart", {**base, "place": bad})
        check(st == 400, f"bad place {bad}", f"{st}")
    st, _, _ = call("/birth-chart", raw=b"{not json")
    check(st == 400, "malformed JSON -> 400", str(st))
    st, _, _ = call("/birth-chart", raw=json.dumps({**base, "junk": "x" * 20000}).encode())
    check(st == 413, "oversized body -> 413", str(st))
    st, j, _ = call("/birth-chart", base)
    check(st == 200 and j["calculationProfile"]["nodeType"] == "mean" and j["houses"]["system"] == "W", "defaults: mean node + Whole Sign", f"{st}")
    for path in ("/self-test", "/accuracy-test", "/forensic-test"):
        st, _, _ = call(path, method="GET")
        check(st == 404, f"{path} removed", str(st))
    st, _, h = call("/health", method="GET", origin="https://app.astrolaab.com")
    check(st == 200 and h.get("access-control-allow-origin") == "https://app.astrolaab.com", "CORS allowed origin echoed", str(h.get("access-control-allow-origin")))
    st, _, h = call("/health", method="GET", origin="https://evil.example")
    check(h.get("access-control-allow-origin") == ORIGIN, "CORS disallowed origin not echoed", str(h.get("access-control-allow-origin")))
    st, _, h = call("/health", method="GET", origin="http://app.astrolaab.com")
    check(h.get("access-control-allow-origin") == ORIGIN, "CORS http origin not echoed", str(h.get("access-control-allow-origin")))


if __name__ == "__main__":
    print("Endpoint:", ENDPOINT, "| pyswisseph", swe.version)
    only = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--only=")), "all")
    if only in ("all", "houses"):
        section_houses_d9()
    if only in ("all", "contract"):
        section_contract()
    print(f"\n{checks - len(failures)}/{checks} checks passed")
    for f in failures[:40]:
        print(" -", f)
    sys.exit(1 if failures else 0)
