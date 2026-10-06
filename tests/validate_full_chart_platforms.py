#!/usr/bin/env python3
"""Compare the full-chart engine's Moon semantics with 20 public references."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from engine.astronomy import calculate_chart

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "workers" / "moon-sign" / "tests" / "validate-platform-references.py"
FIXTURE = ROOT / "workers" / "moon-sign" / "tests" / "platform-reference-cases.json"

spec = importlib.util.spec_from_file_location("platform_refs", LEGACY)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load public-platform parser")
platform_refs = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = platform_refs
spec.loader.exec_module(platform_refs)

SIGNS = platform_refs.SIGNS
NAKSHATRAS = platform_refs.NAKSHATRAS

def utc_parts(case: dict):
    local = datetime.fromisoformat(f'{case["date"]}T{case["time"]}').replace(
        tzinfo=ZoneInfo(case["timeZone"])
    )
    utc = local.astimezone(timezone.utc)
    return utc, utc.hour + utc.minute / 60 + utc.second / 3600

def actual(case: dict):
    utc, hour = utc_parts(case)
    chart = calculate_chart(
        utc.year, utc.month, utc.day, hour,
        case["place"]["latitude"], case["place"]["longitude"],
    )
    moon = chart["Planets"]["Moon"]["longitude"]
    sign = SIGNS[int(moon // 30)]
    nak = NAKSHATRAS[int(moon // (360 / 27))]
    pada = int((moon % (360 / 27)) // (360 / 108)) + 1
    return sign, nak, pada

def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    target_astro = int(fixture.get("minimumAstroSageCases", 17))
    astro = list(fixture.get("astroPinnedCases", []))
    seeds = list(dict.fromkeys(fixture.get("astroSageSeeds", []) + platform_refs.discover_astrosage_urls()))

    for url in seeds:
        if len(astro) >= target_astro:
            break
        try:
            parsed = platform_refs.parse_astrosage(url, platform_refs.fetch(url))
            if parsed and not any(x["url"] == parsed["url"] for x in astro):
                year = int(parsed["date"][:4])
                if 1950 <= year <= 2050:
                    astro.append(parsed)
        except Exception as exc:
            print(f"SKIP AstroSage {url}: {exc}")

    astro = astro[:target_astro]
    drik = list(fixture["drikCases"])[:int(fixture.get("minimumDrikCases", 3))]
    cases = [(x, "AstroSage") for x in astro] + [(x, "Drik Panchang") for x in drik]

    if len(astro) < target_astro or len(drik) < 3:
        raise RuntimeError(f"Insufficient public references: AstroSage={len(astro)}/{target_astro}, Drik={len(drik)}/3")

    failures = 0
    pada_reviews = 0
    for case, platform in cases:
        got = actual(case)
        exp = (
            case["expected"]["moonSign"],
            case["expected"]["nakshatra"],
            int(case["expected"]["pada"]),
        )
        if got[:2] != exp[:2]:
            failures += 1
            print(f"FAIL {platform} {case['id']}: expected={exp} actual={got}")
        elif got[2] != exp[2]:
            pada_reviews += 1
            print(f"REVIEW {platform} {case['id']}: Rashi/Nakshatra match, Pada expected={exp[2]} actual={got[2]}")
        else:
            print(f"PASS {platform} {case['id']}: {got}")

    print()
    print(f"Public references tested: {len(cases)}")
    print(f"AstroSage: {len(astro)}")
    print(f"Drik Panchang: {len(drik)}")
    print(f"Hard Rashi/Nakshatra matches: {len(cases) - failures}/{len(cases)}")
    print(f"Pada reviews: {pada_reviews}")
    print(f"Compatibility failures: {failures}")
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
