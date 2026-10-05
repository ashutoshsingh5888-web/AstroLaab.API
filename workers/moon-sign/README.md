# Astro Laab Moon Sign Worker

Cloudflare Worker API for Janma Rashi / Moon Sign.

Endpoints:
- `GET /health`
- `GET /location?q=Mumbai`
- `GET /self-test`
- `GET /accuracy-test`
- `GET /forensic-test` (diagnostic only)
- `POST /moon-sign`
- `POST /birth-chart`

The user enters birth date, exact time, place name, and confirms the suggested IANA timezone. Latitude/longitude are obtained from the selected place result and are never typed by the user.

Calculation:
- Swiss Ephemeris via `@fusionstrings/panchangam`
- Lahiri / Chitrapaksha ayanamsha
- sidereal Moon longitude
- Janma Rashi
- Nakshatra and Pada
- boundary warning

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

## Forensic validation

`/forensic-test` compares the canonical TT planetary path with the raw UT Swiss Ephemeris call using the same embedded Swiss engine. It is diagnostic only and does not alter production calculation behavior.
