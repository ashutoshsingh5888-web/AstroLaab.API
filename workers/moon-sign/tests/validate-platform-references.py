#!/usr/bin/env python3
"""Validate Astro Laab against 20 public Vedic astrology platform references.

At least 15 AstroSage celebrity charts are discovered from known public chart
pages and/or the site's public sitemap. Five Drik Panchang celebrity Kundalis
are then checked. This is a consumer-compatibility layer; JPL DE440/Swiss
Ephemeris remain the numerical precision layers.
"""

from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from datetime import datetime
from pathlib import Path

ENDPOINT = os.environ.get(
    "ASTROLAAB_ENDPOINT",
    "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart",
)
FIXTURE = json.loads(Path(__file__).with_name("platform-reference-cases.json").read_text())

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
NAKSHATRAS = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni",
    "Uttara Phalguni", "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha",
    "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana",
    "Dhanishtha", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada",
    "Revati",
]
SIGN_ALIASES = {
    "Scorpion": "Scorpio",
    "Mesha": "Aries", "Vrishabha": "Taurus", "Mithuna": "Gemini",
    "Kark": "Cancer", "Simha": "Leo", "Kanya": "Virgo", "Tula": "Libra",
    "Vrishchika": "Scorpio", "Dhanu": "Sagittarius", "Makara": "Capricorn",
    "Kumb": "Aquarius", "Meena": "Pisces",
}
NAK_ALIASES = {
    "Pashyami": "Pushya", "Pashyami": "Pushya",
    "Purvaphalgini": "Purva Phalguni", "PurvaPhalguni": "Purva Phalguni",
    "Uttaraphalgini": "Uttara Phalguni", "UttaraPhalguni": "Uttara Phalguni",
    "Uttaraphal": "Uttara Phalguni", "Purvashadha": "Purva Ashadha",
    "PurvaAshadha": "Purva Ashadha", "Uttarashada": "Uttara Ashadha",
    "UttaraAshadha": "Uttara Ashadha", "Sravana": "Shravana",
    "Dhanishta": "Dhanishtha", "Satabhisa": "Shatabhisha",
    "Purvabhadra": "Purva Bhadrapada", "Uttarabhadra": "Uttara Bhadrapada",
}
CITY_COORDS = {
    "Mumbai": (19.0760, 72.8777), "Bangalore": (12.9716, 77.5946),
    "Mangalore": (12.9141, 74.8560), "Indore": (22.7196, 75.8577),
    "Madras": (13.0827, 80.2707), "Delhi": (28.6139, 77.2090),
    "Allahabad": (25.4358, 81.8463), "Mehsana": (23.5880, 72.3693),
    "Kolkata": (22.5726, 88.3639), "Porbandar": (21.6417, 69.6293),
    "Vadnagar": (23.7844, 72.6392),
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
            "user-agent": "Mozilla/5.0 AstroLaab-Platform-Validation/1.0",
            "accept": "text/html,application/xhtml+xml,application/xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def normalize_sign(value: str) -> str:
    return SIGN_ALIASES.get(value.strip().title(), value.strip().title())

def normalize_nak(value: str) -> str:
    value = value.strip()
    if value in NAK_ALIASES:
        return NAK_ALIASES[value]
    return value

def lunar_semantics(sign: str, deg: float, minute: float, second: float) -> tuple[str, str, int, float]:
    sign = normalize_sign(sign)
    lon = (SIGNS.index(sign) * 30.0 + deg + minute / 60.0 + second / 3600.0) % 360.0
    sign_name = SIGNS[int(lon // 30.0)]
    n = int(lon / (360.0 / 27.0))
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return sign_name, NAKSHATRAS[n], pada, lon

def parse_coords(text: str) -> tuple[float, float]:
    lat_m = re.search(r"Latitude\s*:\s*(\d+)\s*([NS])(?:\s+(\d+))?(?:\s+(\d+(?:\.\d+)?))?", text, re.I)
    lon_m = re.search(r"Longitude\s*:\s*(\d+)\s*([EW])(?:\s+(\d+))?(?:\s+(\d+(?:\.\d+)?))?", text, re.I)
    if not (lat_m and lon_m):
        return 0.0, 0.0
    lat = float(lat_m.group(1)) + float(lat_m.group(3) or 0) / 60.0 + float(lat_m.group(4) or 0) / 3600.0
    lon = float(lon_m.group(1)) + float(lon_m.group(3) or 0) / 60.0 + float(lon_m.group(4) or 0) / 3600.0
    if lat_m.group(2).upper() == "S": lat = -lat
    if lon_m.group(2).upper() == "W": lon = -lon
    return lat, lon

def parse_astrosage(url: str, raw: str) -> dict | None:
    text = strip_text(raw)
    date_m = re.search(
        r"Date of Birth\s*:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        text,
        re.I,
    )
    time_m = re.search(r"Time of Birth\s*:\s*(\d{1,2}:\d{2}:\d{2})", text, re.I)
    place_m = re.search(
        r"Place of Birth\s*:\s*([A-Za-z][A-Za-z .'-]+?)\s+(?=Longitude|Latitude|Time Zone|Information Source)",
        text,
        re.I,
    )
    moon_m = re.search(
        r"\bMoon\s+(?:[A-Z]\s+)?(?:D\s+)?"
        r"(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)"
        r"\s+(\d{1,2})[-:]([0-5]\d)[-:]([0-5]\d)\s+([A-Za-z]+)(?:\s+([1-4]))?",
        text,
        re.I,
    )
    if not (date_m and time_m and place_m and moon_m):
        return None
    dt = datetime.strptime(date_m.group(1), "%B %d, %Y")
    sign, deg, minute, second = moon_m.group(1), float(moon_m.group(2)), float(moon_m.group(3)), float(moon_m.group(4))
    expected = lunar_semantics(sign, deg, minute, second)
    lat, lon = parse_coords(text)
    place = place_m.group(1).strip()
    if abs(lat) < 1e-12 and abs(lon) < 1e-12 and place in CITY_COORDS:
        lat, lon = CITY_COORDS[place]
    if abs(lat) < 1e-12 and abs(lon) < 1e-12:
        return None
    return {
        "id": Path(url).stem,
        "platform": "AstroSage",
        "url": url,
        "date": dt.strftime("%Y-%m-%d"),
        "time": time_m.group(1),
        "timeZone": "Asia/Kolkata",
        "place": {"name": place, "country": "India", "latitude": lat, "longitude": lon},
        "expected": {"moonSign": expected[0], "nakshatra": expected[1], "pada": expected[2]},
    }

def discover_astrosage_urls() -> list[str]:
    queue = list(FIXTURE.get("astroSageSitemapCandidates", []))
    seen_sitemaps: set[str] = set()
    found: list[str] = []
    while queue and len(found) < 80:
        sitemap = queue.pop(0)
        if sitemap in seen_sitemaps:
            continue
        seen_sitemaps.add(sitemap)
        try:
            raw = fetch(sitemap)
        except Exception:
            continue
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", raw, re.I | re.S):
            loc = html.unescape(loc.strip())
            if "/celebrity-horoscope/" in loc and re.search(r"-(?:birth-chart|horoscope)\.asp$", loc, re.I):
                if loc not in found:
                    found.append(loc)
            elif loc.endswith(".xml") and len(queue) < 100:
                queue.append(loc)
    return found

def worker(case: dict) -> tuple[str, str, int]:
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
    moon = next(
        p for p in result["planets"]
        if p.get("name") == "Moon" and isinstance(p.get("longitude"), (int, float))
    )
    lon = float(moon["longitude"]) % 360.0
    sign = SIGNS[int(lon // 30.0)]
    n = int(lon / (360.0 / 27.0))
    nak = NAKSHATRAS[n]
    pada = int((lon % (360.0 / 27.0)) / (360.0 / 108.0)) + 1
    return sign, nak, pada

def parse_drik_expected(raw: str) -> dict:
    text = strip_text(raw)
    sign_m = re.search(
        r"Moon\s+Sign(?:\s*\(Paya\))?[^A-Za-z]{0,120}"
        r"(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces|Mesha|Vrishabha|Mithuna|Kark|Simha|Kanya|Tula|Vrishchika|Dhanu|Makara|Kumb|Meena)",
        text,
        re.I,
    )
    nak_m = re.search(
        r"Nakshatra(?:\s*\(Charana\))?[^A-Za-z]{0,120}"
        r"([A-Za-z]+)\s*\(\s*([1-4])\s*\)",
        text,
        re.I,
    )
    if sign_m and nak_m:
        sign = normalize_sign(sign_m.group(1))
        nak = normalize_nak(nak_m.group(1))
        return {"moonSign": sign, "nakshatra": nak, "pada": int(nak_m.group(2))}
    # Fallback to a Chandra/Moon longitude row if the page uses a compact layout.
    moon_row = re.search(
        r'(?:Chandra|Moon)[^0-9]{0,160}'
        r'(\d{1,2})\s*[°:]\s*'
        r'(Mesha|Vrishabha|Mithuna|Kark|Cancer|Simha|Leo|Kanya|Virgo|Tula|Libra|Vrishchika|Scorpio|Dhanu|Sagittarius|Makara|Capricorn|Kumb|Aquarius|Meena|Pisces)'
        r'[^0-9]{0,80}(\d{1,2})\s*[′\']\s*(\d{1,2})\s*[″\"]',
        text,
        re.I,
    )
    if not moon_row:
        raise RuntimeError("Drik Moon Sign/Nakshatra data not found")
    sign = normalize_sign(moon_row.group(2))
    sem = lunar_semantics(sign, float(moon_row.group(1)), float(moon_row.group(3)), float(moon_row.group(4)))
    return {"moonSign": sem[0], "nakshatra": sem[1], "pada": sem[2]}

def main() -> int:
    astro: list[dict] = []
    seeds = list(FIXTURE["astroSageSeeds"])
    discovered = discover_astrosage_urls()
    for url in discovered:
        if url not in seeds:
            seeds.append(url)

    for url in seeds:
        if len(astro) >= FIXTURE["minimumAstroSageCases"]:
            break
        try:
            case = parse_astrosage(url, fetch(url))
            if case and not any(x["url"] == case["url"] for x in astro):
                astro.append(case)
        except Exception as exc:
            print(f"SKIP AstroSage {url}: {exc}")

    if len(astro) < FIXTURE["minimumAstroSageCases"]:
        raise RuntimeError(
            f"Only {len(astro)} AstroSage references parsed; "
            f"need at least {FIXTURE['minimumAstroSageCases']}"
        )

    drik: list[dict] = []
    for spec in FIXTURE["drikCases"]:
        try:
            expected = parse_drik_expected(fetch(spec["url"]))
            case = dict(spec)
            case["expected"] = expected
            drik.append(case)
        except Exception as exc:
            print(f"SKIP Drik {spec['id']}: {exc}")

    if len(drik) < len(FIXTURE["drikCases"]):
        raise RuntimeError(f"Only {len(drik)} Drik references parsed; need {len(FIXTURE['drikCases'])}")

    failures = 0
    tested = 0

    for case in astro:
        try:
            actual = worker(case)
            expected = (
                case["expected"]["moonSign"],
                case["expected"]["nakshatra"],
                int(case["expected"]["pada"]),
            )
            tested += 1
            if actual != expected:
                failures += 1
                print(f"FAIL AstroSage {case['id']}: expected={expected} actual={actual}")
            else:
                print(f"PASS AstroSage {case['id']}: {actual}")
        except Exception as exc:
            failures += 1
            print(f"ERROR AstroSage {case['id']}: {exc}")

    for case in drik:
        try:
            actual = worker(case)
            expected = (
                case["expected"]["moonSign"],
                case["expected"]["nakshatra"],
                int(case["expected"]["pada"]),
            )
            tested += 1
            if actual != expected:
                failures += 1
                print(f"FAIL Drik Panchang {case['id']}: expected={expected} actual={actual}")
            else:
                print(f"PASS Drik Panchang {case['id']}: {actual}")
        except Exception as exc:
            failures += 1
            print(f"ERROR Drik Panchang {case['id']}: {exc}")

    print(f"\nPublic platform references tested: {tested}")
    print(f"AstroSage: {sum(1 for _ in astro) - sum(1 for case in astro if False)}/{len(astro)} total")
    print(f"Drik Panchang: {len(drik) - 0}/{len(drik)} total")
    print(f"Compatibility failures: {failures}")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
