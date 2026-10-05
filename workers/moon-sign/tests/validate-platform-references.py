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
    seen: set[str] = set()
    found: list[str] = []
    while queue and len(found) < 200:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            raw = fetch(url)
        except Exception:
            continue

        # Ordinary page/category HTML.
        for href in re.findall(r'''href\\s*=\\s*["']([^"']*birth-chart\\.asp)["']''', raw, re.I):
            if href.startswith("//"):
                href = "https:" + href
            elif href.startswith("/"):
                href = "https://www.astrosage.com" + href
            elif not href.startswith("http"):
                href = "https://www.astrosage.com/" + href.lstrip("./")
            href = html.unescape(href)
            if href not in found:
                found.append(href)

        # XML sitemap/index.
        for loc in re.findall(r"<loc>\\s*(.*?)\\s*</loc>", raw, re.I | re.S):
            loc = html.unescape(loc.strip())
            if "/celebrity-horoscope/" in loc and re.search(r"-(?:birth-chart|horoscope)\\.asp$", loc, re.I):
                if loc not in found:
                    found.append(loc)
            elif loc.endswith(".xml"):
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
    # Preserve table boundaries before stripping HTML. Drik Panchang often
    # places the label and value in adjacent cells; plain text stripping can
    # concatenate them and defeat a proximity regex.
    table_text = re.sub(r"(?is)<br\\s*/?>", " ", raw)
    table_text = re.sub(r"(?is)</(?:td|th)>", " | ", table_text)
    table_text = re.sub(r"(?is)</tr>", "\\n", table_text)
    table_text = strip_text(table_text)

    s_names = (
        "Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces|"
        "Mesha|Vrishabha|Mithuna|Kark|Simha|Kanya|Tula|Vrishchika|Dhanu|Makara|Kumb|Meena"
    )
    sign_m = re.search(
        rf"Moon\\s*(?:Sign|Rashi|Rasi)\\s*(?:\\(Paya\\))?\\s*\\|?\\s*({s_names})",
        table_text,
        re.I,
    )
    nak_m = re.search(
        r"Nakshatra\\s*(?:\\(Charana\\))?\\s*\\|?\\s*([A-Za-z]+)\\s*"
        r"(?:\\(\\s*([1-4])\\s*\\))?",
        table_text,
        re.I,
    )
    if sign_m and nak_m:
        sign = normalize_sign(sign_m.group(1))
        nak = normalize_nak(nak_m.group(1))
        if nak in NAKSHATRAS:
            pada = int(nak_m.group(2)) if nak_m.group(2) else None
            if pada is not None:
                return {"moonSign": sign, "nakshatra": nak, "pada": pada}

    # A second row layout sometimes puts the Moon longitude itself in a
    # planetary table. Restrict the search to a line containing "Moon" rather
    # than scanning the entire page.
    for line in table_text.splitlines():
        if not re.search(r"\\bMoon\\b|Chandra", line, re.I):
            continue
        row = re.search(
            rf"(?:Moon|Chandra)[^0-9]{{0,120}}"
            rf"(\\d{{1,2}})\\s*[°:]\\s*({s_names})"
            rf'[^0-9]{{0,80}}(\\d{{1,2}})\\D+(\\d{{1,2}})\\D+(\\d{{1,2}})',
            line,
            re.I,
        )
        if row:
            sign = normalize_sign(row.group(2))
            sem = lunar_semantics(sign, float(row.group(1)), float(row.group(3)), float(row.group(4)))
            return {"moonSign": sem[0], "nakshatra": sem[1], "pada": sem[2]}

    raise RuntimeError("Drik Moon Sign/Nakshatra data not found")

def main() -> int:
    astro_target = 15
    drik_target = 5

    astro: list[dict] = []
    seeds = list(dict.fromkeys(FIXTURE["astroSageSeeds"] + discover_astrosage_urls()))

    # Parse enough real public AstroSage pages to establish the target sample.
    # Mismatches are retained as failures; only unreadable/invalid pages are
    # skipped as unusable references.
    for url in seeds:
        if len(astro) >= astro_target:
            break
        try:
            case = parse_astrosage(url, fetch(url))
            if case and not any(x["url"] == case["url"] for x in astro):
                astro.append(case)
        except Exception as exc:
            print(f"SKIP AstroSage {url}: {exc}")

    if len(astro) < astro_target:
        raise RuntimeError(f"Only {len(astro)} AstroSage references parsed; need {astro_target}")

    drik: list[dict] = []
    drik_specs = list(FIXTURE["drikCases"])

    # Also discover public Drik celebrity Kundali URLs so a parser failure on a
    # single fixed profile does not prevent us from reaching five genuine
    # platform references.
    try:
        listing = fetch("https://www.drikpanchang.com/jyotisha/kundali/celebrities-kundali-list.html")
        for href in re.findall(r'''href\\s*=\\s*["']([^"']*kundali-id=[0-9]+[^"']*)["']''', listing, re.I):
            if href.startswith("/"):
                href = "https://www.drikpanchang.com" + href
            elif href.startswith("//"):
                href = "https:" + href
            if href.startswith("http") and not any(x.get("url") == href for x in drik_specs):
                # Unknown birth fields are filled from the individual page below.
                drik_specs.append({"id": "drik-dynamic", "url": href})
    except Exception as exc:
        print(f"INFO Drik discovery unavailable: {exc}")

    for spec in drik_specs:
        if len(drik) >= drik_target:
            break
        try:
            raw = fetch(spec["url"])
            expected = parse_drik_expected(raw)
            case = dict(spec)
            # Fixed cases already carry exact published birth details. Dynamic
            # entries need those fields; parse common Drik labels when present.
            if "date" not in case:
                text = strip_text(raw)
                dm = re.search(
                    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                    r"\\s+(\\d{1,2}),\\s+(\\d{4})\\s+at\\s+(\\d{1,2}):?(\\d{2})\\s*(AM|PM)",
                    text, re.I
                )
                place_m = re.search(r"(?:Place of Birth|Birth Place)\\s*[:|]\\s*([A-Za-z][A-Za-z .'-]+)", text, re.I)
                if not dm:
                    continue
                hour = int(dm.group(4))
                if dm.group(6).upper() == "PM" and hour != 12:
                    hour += 12
                if dm.group(6).upper() == "AM" and hour == 12:
                    hour = 0
                month = __import__("datetime").datetime.strptime(dm.group(1), "%B").month
                case["date"] = f"{int(dm.group(3)):04d}-{month:02d}-{int(dm.group(2)):02d}"
                case["time"] = f"{hour:02d}:{int(dm.group(5)):02d}:00"
                case["timeZone"] = "Asia/Kolkata"
                place = place_m.group(1).strip() if place_m else "India"
                lat, lon = CITY_COORDS.get(place, (0.0, 0.0))
                if abs(lat) < 1e-12 and abs(lon) < 1e-12:
                    continue
                case["place"] = {"name": place, "country": "India", "latitude": lat, "longitude": lon}
            case["expected"] = expected
            drik.append(case)
        except Exception as exc:
            print(f"SKIP Drik {spec.get('id', spec.get('url'))}: {exc}")

    if len(drik) < drik_target:
        raise RuntimeError(f"Only {len(drik)} Drik references parsed; need {drik_target}")

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

    print(f"\\nPublic platform references tested: {tested} (target {astro_target + drik_target})")
    print(f"AstroSage references: {len(astro)}")
    print(f"Drik Panchang references: {len(drik)}")
    print(f"Combined platform references: {tested}")
    print(f"Compatibility failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
