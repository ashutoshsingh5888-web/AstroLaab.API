#!/usr/bin/env python3
"""Validate the live Worker against 20 public Vedic astrology platform pages.

This is a compatibility test, not the astronomical truth oracle:
JPL DE440/Swiss Ephemeris remain the precision layers. Here we check that
published platform birth inputs and lunar semantics (Rashi/Nakshatra/Pada)
agree with Astro Laab for the same chart.
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
CASES = json.loads(Path(__file__).with_name("platform-reference-cases.json").read_text())["cases"]

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_ALIASES = {
    "Scorpion": "Scorpio",
}
NAKSHATRA_CANON = {
    "Ashwini": "Ashwini",
    "Bharani": "Bharani",
    "Krittika": "Krittika",
    "Rohini": "Rohini",
    "Mrigashira": "Mrigashira",
    "Ardra": "Ardra",
    "Punarvasu": "Punarvasu",
    "Pushya": "Pushya",
    "Ashlesha": "Ashlesha",
    "Pashyami": "Ashlesha",
    "Magha": "Magha",
    "Purva": "Purva Phalguni",
    "Purvaphalgini": "Purva Phalguni",
    "PurvaPhalguni": "Purva Phalguni",
    "Uttara": "Uttara Phalguni",
    "Uttaraphalgini": "Uttara Phalguni",
    "Hasta": "Hasta",
    "Chitra": "Chitra",
    "Swati": "Swati",
    "Vishakha": "Vishakha",
    "Anuradha": "Anuradha",
    "Jyeshtha": "Jyeshtha",
    "Mula": "Mula",
    "Purvashada": "Purva Ashadha",
    "PurvaAshadha": "Purva Ashadha",
    "Uttarashada": "Uttara Ashadha",
    "UttaraAshadha": "Uttara Ashadha",
    "Sravana": "Shravana",
    "Shravana": "Shravana",
    "Dhanishta": "Dhanishtha",
    "Dhanishtha": "Dhanishtha",
    "Satabhisa": "Shatabhisha",
    "Shatabhisha": "Shatabhisha",
    "Purvabhadra": "Purva Bhadrapada",
    "Uttarabhadra": "Uttara Bhadrapada",
    "Revati": "Revati",
}
MONTHS = {m: i for i, m in enumerate(
    ["January","February","March","April","May","June",
     "July","August","September","October","November","December"], 1
)}

DRIK_COORDS = {
    "Mahatma Gandhi": (21.6417, 69.6293),
    "Narendra Modi": (23.7844, 72.6392),
    "Sachin Tendulkar": (19.0760, 72.8777),
    "Amitabh Bachchan": (25.9500, 81.8333),
    "Swami Vivekananda": (22.5726, 88.3639),
}

def strip_text(raw: str) -> str:
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

def dms_to_decimal(value: str, hemi: str) -> float:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", value)]
    deg = nums[0] if nums else 0.0
    minutes = nums[1] if len(nums) > 1 else 0.0
    seconds = nums[2] if len(nums) > 2 else 0.0
    out = deg + minutes / 60.0 + seconds / 3600.0
    return -out if hemi.upper() in ("S", "W") else out

def parse_astrosage(url: str, raw: str) -> dict:
    text = strip_text(raw)
    def first(patterns, flags=re.I):
        for p in patterns:
            m = re.search(p, text, flags)
            if m:
                return m.group(1).strip()
        raise ValueError(f"field not found: {patterns[0]}")

    date_s = first([
        r"Date of Birth:\s*(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
        r"Date of Birth:\s*([A-Z][a-z]+\s+\d{1,2},\s+\d{4})",
    ])
    dt = datetime.strptime(date_s, "%B %d, %Y")
    time_s = first([r"Time of Birth:\s*(\d{1,2}:\d{2}:\d{2})"])
    place = first([r"Place of Birth:\s*([A-Za-z][A-Za-z .'-]+?)\s+(?:Longitude|Time Zone|Information Source)"])
    lon_s = first([r"Longitude:\s*(\d+)\s*([EW])\s*(\d+(?:\.\d+)?)?"])
    lat_s = first([r"Latitude:\s*(\d+)\s*([NS])\s*(\d+(?:\.\d+)?)?"])
    tz = float(first([r"Time Zone:\s*([+-]?\d+(?:\.\d+)?)"]))
    sign = first([r"Rasi/ Moon Sign:\s*([A-Za-z]+)"])
    sign = SIGN_ALIASES.get(sign, sign)

    moon_row = re.search(
        r"Moon\s+(?:D|R|C)?\s*(Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)"
        r"\s+(\d{1,2})[-:]([0-5]\d)[-:]([0-5]\d)\s+([A-Za-z]+)\s+([1-4])",
        text,
        re.I,
    )
    nak = None
    pada = None
    if moon_row:
        nak_raw = moon_row.group(5)
        nak = NAKSHATRA_CANON.get(nak_raw, nak_raw)
        pada = int(moon_row.group(6))
    else:
        nak_raw = first([r"Nakshatra or star constellations:\s*([A-Za-z]+)"])
        nak = NAKSHATRA_CANON.get(nak_raw, nak_raw)
        # Pada is normally encoded in the Moon row. If unavailable, derive it
        # from the first Moon longitude visible on the page.
        row = re.search(
            r"Moon\s+(?:D|R|C)?\s*[A-Za-z]+\s+(\d{1,2})[-:]([0-5]\d)[-:]([0-5]\d)",
            text,
            re.I,
        )
        if row:
            lon_deg = int(row.group(1)) + int(row.group(2))/60 + int(row.group(3))/3600
            pada = int((lon_deg % (360.0/27.0)) / (360.0/108.0)) + 1

    # Longitude/latitude are printed as integer degrees + minutes; parse from
    # the matched substrings directly so small city-coordinate differences do
    # not enter the lunar semantics comparison.
    lon_match = re.search(r"Longitude:\s*(\d+)\s*([EW])(?:\s*(\d+(?:\.\d+)?))?", text, re.I)
    lat_match = re.search(r"Latitude:\s*(\d+)\s*([NS])(?:\s*(\d+(?:\.\d+)?))?", text, re.I)
    lon = dms_to_decimal(" ".join(filter(None, lon_match.groups()[0:1] + lon_match.groups()[2:3])), lon_match.group(2)) if lon_match else 0.0
    lat = dms_to_decimal(" ".join(filter(None, lat_match.groups()[0:1] + lat_match.groups()[2:3])), lat_match.group(2)) if lat_match else 0.0

    # AstroSage has historically used fractional-hour timezone offsets for its
    # published charts. Asia/Kolkata is correct for the India cases in this set.
    tz_name = "Asia/Kolkata" if abs(tz - 5.5) < 1e-9 else "UTC"

    return {
        "platform": "AstroSage",
        "url": url,
        "date": dt.strftime("%Y-%m-%d"),
        "time": time_s,
        "timeZone": tz_name,
        "tzOffsetHours": tz,
        "place": {"name": place, "country": "India", "latitude": lat, "longitude": lon},
        "expected": {"moonSign": sign, "nakshatra": nak, "pada": pada},
    }

def parse_drik(url: str, raw: str) -> dict:
    text = strip_text(raw)
    name_match = re.search(r"(Mahatma Gandhi|Narendra Modi|Sachin Tendulkar|Amitabh Bachchan|Swami Vivekananda)", text)
    if not name_match:
        raise ValueError("Drik celebrity name not found")
    name = name_match.group(1)

    m = re.search(
        r"([A-Z][a-z]{2})\s+(\d{1,2}),\s+(-?\d{3,4})\s+at\s+(\d{1,2}):(\d{2})\s+(AM|PM)",
        text,
    )
    if not m:
        raise ValueError("Drik birth date/time not found")
    month, day, year, hour, minute, ampm = m.groups()
    hour = int(hour)
    if ampm == "PM" and hour != 12: hour += 12
    if ampm == "AM" and hour == 12: hour = 0
    dt = datetime(int(year), MONTHS[next(k for k in MONTHS if k.startswith(month))], int(day), hour, int(minute))

    moon_sign_m = re.search(r"Moon Sign \(Paya\)\s*([A-Za-z]+)", text)
    nak_m = re.search(r"Nakshatra \(Charana\)\s*([A-Za-z]+)\s*\((\d)\)", text)
    if not moon_sign_m or not nak_m:
        raise ValueError("Drik lunar semantics not found")
    sign = SIGN_ALIASES.get(moon_sign_m.group(1), moon_sign_m.group(1))
    nak = NAKSHATRA_CANON.get(nak_m.group(1), nak_m.group(1))
    pada = int(nak_m.group(2))

    lat, lon = DRIK_COORDS[name]
    return {
        "platform": "Drik Panchang",
        "url": url,
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "timeZone": "Asia/Kolkata",
        "place": {"name": name, "country": "India", "latitude": lat, "longitude": lon},
        "expected": {"moonSign": sign, "nakshatra": nak, "pada": pada},
    }

def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "user-agent": "AstroLaab-Platform-Validation/1.0",
            "accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def worker(case: dict) -> dict:
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
        return json.loads(r.read().decode())

def main() -> int:
    failures = 0
    tested = 0
    by_platform = {"AstroSage": [0, 0], "Drik Panchang": [0, 0]}

    for spec in CASES:
        try:
            raw = fetch(spec["url"])
            case = parse_astrosage(spec["url"], raw) if spec["platform"] == "AstroSage" else parse_drik(spec["url"], raw)
            result = worker(case)
            moon = next(
                p for p in result["planets"]
                if str(p.get("name")) == "Moon" and isinstance(p.get("longitude"), (int, float))
            )
            lon = float(moon["longitude"])
            sign_index = int((lon % 360.0) // 30.0)
            moon_sign = SIGNS[sign_index]
            nak_index = int((lon % 360.0) / (360.0 / 27.0))
            nak_names = [
                "Ashwini","Bharani","Krittika","Rohini","Mrigashira","Ardra",
                "Punarvasu","Pushya","Ashlesha","Magha","Purva Phalguni",
                "Uttara Phalguni","Hasta","Chitra","Swati","Vishakha",
                "Anuradha","Jyeshtha","Mula","Purva Ashadha","Uttara Ashadha",
                "Shravana","Dhanishtha","Shatabhisha","Purva Bhadrapada",
                "Uttara Bhadrapada","Revati"
            ]
            nak = nak_names[nak_index]
            pada = int(((lon % (360.0 / 27.0)) / (360.0 / 108.0))) + 1
            actual = (moon_sign, nak, pada)
            expected = (
                case["expected"]["moonSign"],
                case["expected"]["nakshatra"],
                case["expected"]["pada"],
            )
            tested += 1
            by_platform[case["platform"]][1] += 1
            if actual != expected:
                failures += 1
                by_platform[case["platform"]][0] += 1
                print(f"FAIL {spec['id']}: expected={expected} actual={actual}")
            else:
                print(f"PASS {spec['id']}: {actual[0]} / {actual[1]} / pada {actual[2]}")
        except Exception as exc:
            failures += 1
            print(f"ERROR {spec['id']}: {exc}")

    print(f"\nPlatform references tested: {tested}/{len(CASES)}")
    for platform, (bad, total) in by_platform.items():
        print(f"{platform}: {total-bad}/{total} matched")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
