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


## Python chart engine notes

- Sidereal mode in Swiss Ephemeris is thread-local, so `engine/astronomy.py` selects Lahiri inside every calculation (regression-tested in `tests/test_engine_unit.py`).
- Rahu/Ketu use the mean node by default (matches AstroSage and the Worker); pass `"node": "true"` to opt in to the true node.
- Request fields `timezone` (IANA, default `Asia/Kolkata`) and `utc_offset_minutes` (optional) control local-to-UTC conversion. Supported years: 1950-2050.
- Rate limits: `RATE_LIMIT` (default `20/minute` per verified API key), `AUTH_FAILURE_MAX` failed keys per client per minute. Counters are per process; run uvicorn with `--proxy-headers` behind a proxy so the real client address is used.
- Tests: `pip install -r requirements.txt -r requirements-dev.txt && PYTHONPATH=. python -m unittest tests/test_engine_unit.py`
- Repo hygiene: run `./repo-cleanup.sh` once to stop tracking the committed `venv/` and `__pycache__`.
