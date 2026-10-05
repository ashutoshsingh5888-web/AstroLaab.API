#!/usr/bin/env python3
"""Validate Astro Laab against 20 public Vedic astrology platform references.

15 AstroSage celebrity-chart pages are selected from known good seeds plus the
public AstroSage sitemap. Five Drik Panchang celebrity Kundalis are fixed.
The production calculation path is not altered by this test.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
FIXTURE = json.loads(Path(__file__).with_name("platform-reference-cases.json").read_text())

SIGNS = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
NAKSHATRAS = [
    "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra","Punarvasu",
    "Pushya","Ashlesha","Magha","Purva Phalguni","Uttara Phalguni","Hasta",
    "Chitra","Swati","Vishakha","Anuradha","Jyeshtha","Mula","Purva Ashadha",
    "Uttara Ashadha","Shravana","Dhanishtha","Shatabhisha","Purva Bhadrapada",
    "Uttara Bhadrapada","Revati"
]
SIGN_ALIASES = {"Scorpion": "Scorpio"}
NAK_ALIASES = {
    "Pashyami": "Pushya",
    "Purvaphalgini": "Purva Phalguni",
    "Uttaraphalgini": "Uttara Phalguni",
    "Uttaraphal": "Uttara Phalguni",
    "Purvashadha": "Purva Ashadha",
    "Uttarashada": "Uttara Ashadha",
    "Sravana": "Shravana",
    "Dhanishta": "Dhanishtha",
    "Satabhisa": "Shatabhisha",
    "Purvabhadra": "Purva Bhadrapada",
    "Uttarabhadra": "Uttara Bhadrapada",
}

def strip_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "user-agent": "Mozilla/5.0 (AstroLaab-Platform-Validation/1.0)",
            "accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def angle_semantics(sign: str, deg: float, minute: float, second: float) -> tuple[str,str,int,float]:
    lon = SIGNS.index(SIGN_ALIASES.get(sign, sign)) * 30.0 + deg + minute/60.0 + second/3600.0
    lon %= 360.0
    sign_name = SIGNS[int(lon // 30.0)]
    n = int(lon / (360.0 / 27.0))
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return sign_name, NAKSHATRAS[n], pada, lon

def parse_astrosage(url: str, raw: str) -> dict | None:
    text = strip_text(raw)
    d = re.search(
        r"Date of Birth:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        text,
        re.I,
    )
    tm = re.search(r"Time of Birth:\s*(\d{1,2}:\d{2}:\d{2})", text, re.I)
    place = re.search(r"Place of Birth:\s*([A-Za-z][A-Za-z .'-]+?)\s+(?:Longitude|Latitude|Time Zone|Information Source)", text, re.I)
    tz = re.search(r"Time Zone:\s*([+-]?\d+(?:\.\d+)?)", text, re.I)
    if not (d and tm and place and tz):
        return None
    try:
        dt = datetime.strptime(d.group(1), "%B %d, %Y")
    except ValueError:
        return None

    moon = re.search(
        r"Moon\s+(?:D|R|C)?\s*(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)"
        r"\s+(\d{1,2})[-:](\d{2})[-:](\d{2})\s+([A-Za-z]+)\s+([1-4])",
        text,
        re.I,
    )
    if not moon:
        return None
    sign, deg, minute, second = moon.group(1), float(moon.group(2)), float(moon.group(3)), float(moon.group(4))
    semantics = angle_semantics(sign, deg, minute, second)
    # AstroSage's published Indian charts in this suite all use IST.
    return {
        "id": Path(url).stem,
        "platform": "AstroSage",
        "url": url,
        "date": dt.strftime("%Y-%m-%d"),
        "time": tm.group(1),
        "timeZone": "Asia/Kolkata",
        "place": {
            "name": place.group(1).strip(),
            "country": "India",
            "latitude": 0.0,
            "longitude": 0.0,
        },
        "expected": {"moonSign": semantics[0], "nakshatra": semantics[1], "pada": semantics[2]},
    }

def discover_astrosage_urls() -> list[str]:
    found: list[str] = []
    for sitemap in FIXTURE["astroSageSitemapCandidates"]:
        try:
            raw = fetch(sitemap)
        except Exception:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", raw, re.I | re.S):
            loc = html.unescape(loc.strip())
            if "/celebrity-horoscope/" in loc and re.search(r"(?:-birth-chart|-horoscope)\.asp$", loc, re.I):
                if loc not in found:
                    found.append(loc)
    return found

def worker(case: dict) -> tuple[str,str,int]:
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
        headers={
            "content-type": "application/json",
            "origin": "https://astrolaab.com",
            "user-agent": "AstroLaab-Platform-Validation/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        result = json.loads(r.read().decode())
    moon = next(p for p in result["planets"] if p.get("name") == "Moon")
    lon = float(moon["longitude"]) % 360.0
    sign = SIGNS[int(lon // 30.0)]
    n = int(lon / (360.0 / 27.0))
    nak = NAKSHATRAS[n]
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return sign, nak, pada

def main() -> int:
    sources = []
    for url in FIXTURE["astroSageSeeds"]:
        if len(sources) >= FIXTURE["minimumAstroSageCases"]:
            break
        try:
            case = parse_astrosage(url, fetch(url))
            if case:
                sources.append(case)
        except Exception as exc:
            print(f"SKIP AstroSage seed {url}: {exc}")

    if len(sources) < FIXTURE["minimumAstroSageCases"]:
        for url in discover_astrosage_urls():
            if len(sources) >= FIXTURE["minimumAstroSageCases"]:
                break
            if any(x["url"] == url for x in sources):
                continue
            try:
                case = parse_astrosage(url, fetch(url))
                if case:
                    sources.append(case)
            except Exception:
                continue

    # For AstroSage pages where the chart row gave us the Moon longitude, the
    # page's longitude/latitude is not needed for lunar semantics. Use stable
    # city coordinates for the known seeds to make the Worker request valid.
    city_coords = {
        "Mumbai": (19.0760, 72.8777), "Bangalore": (12.9716, 77.5946),
        "Mangalore": (12.9141, 74.8560), "Indore": (22.7196, 75.8577),
        "Madras": (13.0827, 80.2707), "Delhi": (28.6139, 77.2090),
        "Allahabad": (25.4358, 81.8463), "Mehsana": (23.5880, 72.3693),
        "Kolkata": (22.5726, 88.3639), "Porbandar": (21.6417, 69.6293),
    }
    for case in sources:
        if case["place"]["name"] in city_coords:
            lat, lon = city_coords[case["place"]["name"]]
            case["place"]["latitude"], case["place"]["longitude"] = lat, lon

    # Add five fixed Drik Panchang celebrity Kundalis. Expected lunar semantics
    # are read from the same public pages at test time.
    for spec in FIXTURE["drikCases"]:
        raw = fetch(spec["url"])
        text = strip_text(raw)
        moon = re.search(
            r"(?:☾)?Chandra[^0-9]{0,120}(\d{1,2})°\s*(Mesha|Vrishabha|Mithuna|Kark|Cancer|Simha|Leo|Kanya|Virgo|Tula|Libra|Vrishchika|Scorpio|Dhanu|Sagittarius|Makara|Capricorn|Kumb|Aquarius|Meena|Pisces)\s+(\d{1,2})[′']\s+(\d{1,2})[″"]",
            text,
            re.I,
        )
        if not moon:
            raise RuntimeError(f"Drik lunar longitude not found for {spec['id']}")
        s_map = {"Mesha":"Aries","Vrishabha":"Taurus","Mithuna":"Gemini","Kark":"Cancer","Simha":"Leo","Kanya":"Virgo","Tula":"Libra","Vrishchika":"Scorpio","Dhanu":"Sagittarius","Makara":"Capricorn","Kumb":"Aquarius","Meena":"Pisces"}
        sign = s_map.get(moon.group(2), SIGN_ALIASES.get(moon.group(2), moon.group(2)))
        sem = angle_semantics(sign, float(moon.group(1)), float(moon.group(3)), float(moon.group(4)))
        spec["expected"] = {"moonSign": sem[0], "nakshatra": sem[1], "pada": sem[2]}
        sources.append(spec)

    failures = 0
    tested = 0
    by_platform = {"AstroSage": [0,0], "Drik Panchang": [0,0]}

    if len(sources) < FIXTURE["minimumAstroSageCases"] + len(FIXTURE["drikCases"]):
        raise RuntimeError(
            f"Only {len(sources)} usable platform references found; "
            f"need at least {FIXTURE['minimumAstroSageCases'] + len(FIXTURE['drikCases'])}"
        )

    for case in sources[:FIXTURE["minimumAstroSageCases"]]:
        try:
            actual = worker(case)
            expected = (case["expected"]["moonSign"], case["expected"]["nakshatra"], case["expected"]["pada"])
            tested += 1; by_platform["AstroSage"][1] += 1
            if actual != expected:
                failures += 1; by_platform["AstroSage"][0] += 1
                print(f"FAIL {case['id']}: expected={expected} actual={actual}")
            else:
                print(f"PASS AstroSage {case['id']}: {actual}")
        except Exception as exc:
            failures += 1
            print(f"ERROR AstroSage {case['id']}: {exc}")

    for case in sources[FIXTURE["minimumAstroSageCases"]:FIXTURE["minimumAstroSageCases"] + len(FIXTURE["drikCases"])]:
        try:
            actual = worker(case)
            expected = (case["expected"]["moonSign"], case["expected"]["nakshatra"], case["expected"]["pada"])
            tested += 1; by_platform["Drik Panchang"][1] += 1
            if actual != expected:
                failures += 1; by_platform["Drik Panchang"][0] += 1
                print(f"FAIL {case['id']}: expected={expected} actual={actual}")
            else:
                print(f"PASS Drik Panchang {case['id']}: {actual}")
        except Exception as exc:
            failures += 1
            print(f"ERROR Drik Panchang {case['id']}: {exc}")

    print(f"\nPublic platform references tested: {tested}")
    print(f"AstroSage: {by_platform['AstroSage'][1]-by_platform['AstroSage'][0]}/{by_platform['AstroSage'][1]} matched")
    print(f"Drik Panchang: {by_platform['Drik Panchang'][1]-by_platform['Drik Panchang'][0]}/{by_platform['Drik Panchang'][1]} matched")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
