# AstroLaab API

Vedic Astrology Engine using Swiss Ephemeris and Lahiri (Chitrapaksha) ayanamsha.

## API

- `GET /api/v1/health`
- `POST /api/v1/chart` — birth inputs are local India Standard Time (Asia/Kolkata/IST).
- Chart calculations convert IST to UTC once at the API boundary, then use Swiss Ephemeris UT calculations.
- Planetary positions are sidereal Lahiri.
- Houses use whole-sign chart layout with a Swiss Ephemeris sidereal Ascendant.
- Vimshottari Mahadasha timeline is included.
- Panchang tithi, yoga, karana, and weekday are included.
- North and South chart layout metadata is included.
- API key authentication uses the `x-api-key` header.

## Accuracy gates

The repository includes strict CI validation for the full-chart engine:

- Direct Swiss Ephemeris oracle across 128 deterministic birth cases.
- Rashi, Nakshatra, and Pada boundary cases.
- Planet tolerances: Sun/Mercury/Venus/Mars/Jupiter/Saturn/Rahu/Ketu ≤ 0.1 arcsec; Moon ≤ 0.5 arcsec.
- Ascendant ≤ 1.0 arcsec.
- 20 public compatibility references: 17 AstroSage + 3 Drik Panchang.
- Invalid calendar dates are rejected during request validation.

## Local setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API is version-pinned through `requirements.txt`, including `pyswisseph==2.10.3.2`.
