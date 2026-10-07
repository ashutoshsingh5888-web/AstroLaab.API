# Astro Laab Moon Sign Worker

Cloudflare Worker API for Janma Rashi / Moon Sign.

Endpoints:
- `GET /health`
- `GET /location?q=Mumbai`
- `POST /moon-sign`
- `POST /birth-chart`

The user enters birth date, exact time, place name, and confirms the suggested IANA timezone. Latitude/longitude are obtained from the selected place result and are never typed by the user.

Calculation:
- Swiss Ephemeris via `@fusionstrings/panchangam`
- Lahiri / Chitrapaksha ayanamsha
- sidereal Moon longitude
- Janma Rashi
- Nakshatra and Pada
- boundary warnings (Rashi, Nakshatra and Pada edges within 0.1 deg)
- D9/Navamsa, mean Rahu/Ketu, Whole Sign house numbers per planet
- houses: Whole Sign (`W`, default), Equal (`E`), Placidus (`P`, rejected above 66.5 deg latitude)

Supported birth years: 1950-2050, judged on the LOCAL calendar year. Local times that never existed (DST gap) are rejected with HTTP 400; times that occurred twice (DST overlap) are accepted with an `ambiguous_local_time` warning (first occurrence). Send `utcOffsetMinutes` to choose. Bad input returns 400, internal failures 500 with no detail.

Example request:

```json
{
  "date":"1990-01-15",
  "time":"14:35:00",
  "timeZone":"Asia/Kolkata",
  "utcOffsetMinutes":330,
  "place":{
    "name":"Mumbai",
    "country":"India",
    "latitude":19.076,
    "longitude":72.8777
  }
}
```

## Deploy

```
cd workers/moon-sign
npm install
npm run dry-run
npm run deploy
```

Before public commercial use, verify the Swiss Ephemeris licensing terms. The package is a Swiss Ephemeris wrapper and licensing must be compatible with Astro Laab's distribution model.

## Location search

The first implementation uses Photon / OpenStreetMap for place suggestions. It is intentionally isolated behind `/location`, so it can later be replaced with a dedicated geocoder or self-hosted service without changing the Moon Sign API.

## Diagnostics

The public `/self-test`, `/accuracy-test` and `/forensic-test` endpoints were removed: they carried stale golden values and exposed internals. Validation now lives in CI (see Tests).

## Rate limiting `/location`

Responses are cached for 24 h. To add a hard per-IP limit, bind Cloudflare's Rate Limiting API (requires a wrangler version that supports `ratelimits`), then the Worker enforces it automatically:

```jsonc
"ratelimits": [{ "name": "LOCATION_LIMITER", "namespace_id": "1001", "simple": { "limit": 30, "period": 60 } }]
```

## Tests

```
npm test                                   # Node unit tests: D9, Whole Sign, delta-T, DST, HTTP layer (WASM stubbed)
python tests/tools/generate-deltat-fixture.py --check
python tests/validate-pada-boundaries.py   # Pada review vs pyswisseph (+ live Worker if ASTROLAAB_ENDPOINT is set)
python tests/validate-chart-hardening.py   # live: houses, D9, Whole Sign numbers, API contract
```

`src/chart-core.ts` holds all pure logic so it can be tested without the WASM package. Unit tests use independent oracles (classical navamsa table, integer-arc-minute pada arithmetic, a pyswisseph-generated delta-T fixture), not the implementation's own formulas.

## Independent accuracy regression

The primary accuracy gate is intentionally independent of the Worker runtime.

- 50 deterministic birth-chart inputs are stored in `tests/independent-accuracy-cases.json`.
- Reference positions are generated at test time with the independently maintained `pyswisseph` Python binding.
- Reference uses Lahiri sidereal mode, Swiss Ephemeris delta-T, TT for planets and UT for houses.
- The suite validates planetary longitudes, Moon sign, Nakshatra, Pada, Navamsa (D9), Ascendant, ayanamsha, timezone conversion, and Moon-boundary warnings.
- Ten boundary pairs place the Moon 10 arcseconds before/after a Rashi boundary.
- The expected astronomical values are not embedded in the production Worker.

Run locally:

```
cd workers/moon-sign
python -m pip install pyswisseph==2.10.03
python tests/validate-independent-accuracy.py
```

GitHub Actions runs the same regression automatically on changes under `workers/moon-sign` and can also be started manually from the Actions tab.
