// Pure chart helpers. No WASM, no I/O, no globals: everything here is unit-tested
// in plain Node (tests/unit) against independent oracles.
//
// Only erasable TypeScript syntax is used (no enums, no parameter properties)
// so Node can run this file directly with type stripping.

export class InputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InputError";
  }
}

export type Warning = { code: string; message: string; [key: string]: unknown };

export const SUPPORTED_MIN_YEAR = 1950;
export const SUPPORTED_MAX_YEAR = 2050;
// Placidus is undefined above roughly 90 deg minus the obliquity (about 66.56 deg).
export const PLACIDUS_MAX_LATITUDE = 66.5;
export const BOUNDARY_THRESHOLD_DEGREES = 0.1;

export const SIGNS: string[][] = [
  ["Mesha", "Aries", "♈"], ["Vrishabha", "Taurus", "♉"], ["Mithuna", "Gemini", "♊"],
  ["Karka", "Cancer", "♋"], ["Simha", "Leo", "♌"], ["Kanya", "Virgo", "♍"],
  ["Tula", "Libra", "♎"], ["Vrishchika", "Scorpio", "♏"], ["Dhanu", "Sagittarius", "♐"],
  ["Makara", "Capricorn", "♑"], ["Kumbha", "Aquarius", "♒"], ["Meena", "Pisces", "♓"],
];

export const NAKSHATRAS: string[] = [
  "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
  "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta",
  "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha",
  "Uttara Ashadha", "Shravana", "Dhanishtha", "Shatabhisha", "Purva Bhadrapada",
  "Uttara Bhadrapada", "Revati",
];

// ---------------------------------------------------------------- angles

export function norm(x: number): number {
  // Exact for values already in range (the old ((x % 360) + 360) % 360 added
  // about 1e-14 deg of rounding noise to every longitude).
  const r = x % 360;
  const n = r < 0 ? r + 360 : r;
  return n >= 360 || n === 0 ? 0 : n; // also normalises -0
}

export function dms(x: number) {
  // Truncating display value; never rolls over to 30 deg 00' 00" (rounding at
  // 29.99999 deg used to print "30° 00′ 00″").
  const total = Math.min(30 * 3600 - 1, Math.round((x % 30) * 3600));
  const deg = Math.floor(total / 3600);
  const min = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  return {
    degrees: deg,
    minutes: min,
    seconds: sec,
    text: `${deg}° ${String(min).padStart(2, "0")}′ ${String(sec).padStart(2, "0")}″`,
  };
}

export function signOf(longitude: number) {
  const x = norm(longitude);
  const i = Math.min(11, Math.floor(x / 30));
  const inSign = x - i * 30;
  return {
    index: i + 1,
    name: SIGNS[i][0],
    english: SIGNS[i][1],
    symbol: SIGNS[i][2],
    degreeInSign: inSign,
    degreeInSignDms: dms(inSign),
  };
}

// ------------------------------------------- 108 padas == 108 navamsas
// The zodiac divides into 108 slots of 3 deg 20'. Each slot is simultaneously
// one nakshatra pada and one navamsa, so both are derived from one index.
// EPS snaps floating-point noise at exact boundaries (about 3e-9 deg).

const SLOT_EPS = 1e-9;

export function padaSlot(longitude: number): number {
  const slot = Math.floor((norm(longitude) * 3) / 10 + SLOT_EPS);
  return slot % 108;
}

export function nakshatraPada(longitude: number) {
  const slot = padaSlot(longitude);
  const index = Math.floor(slot / 4); // 0..26
  return { index: index + 1, name: NAKSHATRAS[index], pada: (slot % 4) + 1, slot };
}

export function navamsaSignIndex(longitude: number): number {
  return padaSlot(longitude) % 12;
}

export function divisionalSign(longitude: number, division: number) {
  if (division === 1) return signOf(longitude);
  if (division !== 9) {
    // The old generic formula was wrong for every varga except D9; fail loudly.
    throw new Error(`divisional chart D${division} is not implemented`);
  }
  return signOf(navamsaSignIndex(longitude) * 30);
}

// ---------------------------------------------------------------- houses

export function wholeSignCusps(ascendant: number): number[] {
  const base = Math.floor(norm(ascendant) / 30) * 30;
  return Array.from({ length: 12 }, (_, i) => norm(base + 30 * i));
}

export function equalCusps(ascendant: number): number[] {
  return Array.from({ length: 12 }, (_, i) => norm(ascendant + 30 * i));
}

export function wholeSignHouse(planetLongitude: number, ascendant: number): number {
  const p = Math.min(11, Math.floor(norm(planetLongitude) / 30));
  const a = Math.min(11, Math.floor(norm(ascendant) / 30));
  return ((p - a + 12) % 12) + 1;
}

export function assertHouseSystem(system: string, latitude: number): void {
  if (!["P", "W", "E"].includes(system)) throw new InputError("houseSystem must be P, W or E");
  if (system === "P" && Math.abs(latitude) > PLACIDUS_MAX_LATITUDE) {
    throw new InputError(
      `Placidus houses are undefined above ${PLACIDUS_MAX_LATITUDE}° latitude; use houseSystem W or E`,
    );
  }
}

// ---------------------------------------------------------------- delta-T

export const DELTA_T_SECONDS: Record<number, number> = {
  2005: 64.752416, 2006: 64.984080, 2007: 65.300753, 2008: 65.617544, 2009: 65.927825,
  2010: 66.197555, 2011: 66.459474, 2012: 66.747477, 2013: 67.090086, 2014: 67.456277,
  2015: 67.860476, 2016: 68.352592, 2017: 68.795957, 2018: 69.107456, 2019: 69.306882,
  2020: 69.373681, 2021: 69.333821, 2022: 69.239692, 2023: 69.140582, 2024: 69.051739,
  2025: 68.951216, 2026: 68.842899, 2027: 68.800000, 2028: 68.917748, 2029: 69.155609,
  2030: 69.395779, 2031: 69.638285, 2032: 69.883824, 2033: 70.131078, 2034: 70.380740,
  2035: 70.632833, 2036: 70.888083, 2037: 71.145118, 2038: 71.404658, 2039: 71.666725,
  2040: 71.932074, 2041: 72.199277, 2042: 72.469082, 2043: 72.741511, 2044: 73.017346,
  2045: 73.295104, 2046: 73.575560, 2047: 73.858737, 2048: 74.145448, 2049: 74.434148,
  2050: 74.725642,
};

// Models decimal years 1949..2051 so a UTC instant a few hours outside the
// supported *local* year range never throws. The user-facing range check is on
// the local calendar year (assertSupportedLocalYear).
export function deltaT(year: number): number {
  const cy = Math.floor(year);
  if (cy < SUPPORTED_MIN_YEAR - 1 || cy > SUPPORTED_MAX_YEAR + 1) {
    throw new Error("Delta-T requested outside the modelled range");
  }
  if (year >= 2005) {
    if (year >= 2050) return DELTA_T_SECONDS[2050];
    const y0 = Math.floor(year);
    const f = year - y0;
    const a = DELTA_T_SECONDS[y0];
    const b = DELTA_T_SECONDS[Math.min(2050, y0 + 1)] ?? a;
    return a + (b - a) * f;
  }
  let t: number;
  if (year < 1961) { t = year - 1950; return 29.07 + 0.407 * t - t ** 2 / 233 + t ** 3 / 2547; }
  if (year < 1986) { t = year - 1975; return 45.45 + 1.067 * t - t ** 2 / 260 - t ** 3 / 718; }
  t = year - 2000;
  return 63.86 + 0.3345 * t - 0.060374 * t ** 2 + 0.0017275 * t ** 3 + 0.000651814 * t ** 4 + 0.00002373599 * t ** 5;
}

export function decimalYearOf(utc: Date): number {
  return utc.getUTCFullYear() + (utc.getUTCMonth() + 0.5) / 12;
}

// ------------------------------------------------------------- nutation
// IAU 1980 nutation in longitude (Meeus, Astronomical Algorithms, table 22.A,
// the 46 largest terms). Swiss Ephemeris' native sidereal mode removes nutation:
// sidereal = true-of-date tropical - (mean ayanamsha + nutation in longitude).
// The ephemeris wrapper only subtracts the MEAN ayanamsha, so every longitude it
// returns is off by this value (up to about 18 arcsec). Tests pin this series
// to swe.calc(ECL_NUT) over 1949-2051.
// Columns: D, M, M', F, Omega, sine coefficient (0.0001"), sine coefficient per century.
const NUTATION_TERMS: number[][] = [
  [0, 0, 0, 0, 1, -171996, -174.2], [-2, 0, 0, 2, 2, -13187, -1.6], [0, 0, 0, 2, 2, -2274, -0.2],
  [0, 0, 0, 0, 2, 2062, 0.2], [0, 1, 0, 0, 0, 1426, -3.4], [0, 0, 1, 0, 0, 712, 0.1],
  [-2, 1, 0, 2, 2, -517, 1.2], [0, 0, 0, 2, 1, -386, -0.4], [0, 0, 1, 2, 2, -301, 0],
  [-2, -1, 0, 2, 2, 217, -0.5], [-2, 0, 1, 0, 0, -158, 0], [-2, 0, 0, 2, 1, 129, 0.1],
  [0, 0, -1, 2, 2, 123, 0], [2, 0, 0, 0, 0, 63, 0], [0, 0, 1, 0, 1, 63, 0.1],
  [2, 0, -1, 2, 2, -59, 0], [0, 0, -1, 0, 1, -58, -0.1], [0, 0, 1, 2, 1, -51, 0],
  [-2, 0, 2, 0, 0, 48, 0], [0, 0, -2, 2, 1, 46, 0], [2, 0, 0, 2, 2, -38, 0],
  [0, 0, 2, 2, 2, -31, 0], [0, 0, 2, 0, 0, 29, 0], [-2, 0, 1, 2, 2, 29, 0],
  [0, 0, 0, 2, 0, 26, 0], [-2, 0, 0, 2, 0, -22, 0], [0, 0, -1, 2, 1, 21, 0],
  [0, 2, 0, 0, 0, 17, -0.1], [2, 0, -1, 0, 1, 16, 0], [-2, 2, 0, 2, 2, -16, 0.1],
  [0, 1, 0, 0, 1, -15, 0], [-2, 0, 1, 0, 1, -13, 0], [0, -1, 0, 0, 1, -12, 0],
  [0, 0, 2, -2, 0, 11, 0], [2, 0, -1, 2, 1, -10, 0], [2, 0, 1, 2, 2, -8, 0],
  [0, 1, 0, 2, 2, 7, 0], [-2, 1, 1, 0, 0, -7, 0], [0, -1, 0, 2, 2, -7, 0],
  [2, 0, 0, 2, 1, -7, 0], [2, 0, 1, 0, 0, 6, 0], [-2, 0, 2, 2, 2, 6, 0],
  [-2, 0, 1, 2, 1, 6, 0], [2, 0, -2, 0, 1, -6, 0], [2, 0, 0, 0, 1, -6, 0],
];

// Nutation in longitude, arcseconds, for a Julian Day in TT.
export function nutationLongitudeArcsec(jdTT: number): number {
  const T = (jdTT - 2451545.0) / 36525.0;
  const rad = Math.PI / 180;
  const D = 297.85036 + 445267.11148 * T - 0.0019142 * T * T + (T * T * T) / 189474;
  const M = 357.52772 + 35999.05034 * T - 0.0001603 * T * T - (T * T * T) / 300000;
  const Mp = 134.96298 + 477198.867398 * T + 0.0086972 * T * T + (T * T * T) / 56250;
  const F = 93.27191 + 483202.017538 * T - 0.0036825 * T * T + (T * T * T) / 327270;
  const Om = 125.04452 - 1934.136261 * T + 0.0020708 * T * T + (T * T * T) / 450000;
  let sum = 0;
  for (const [d, m, mp, f, om, a, b] of NUTATION_TERMS) {
    const arg = (d * D + m * M + mp * Mp + f * F + om * Om) * rad;
    sum += (a + b * T) * Math.sin(arg);
  }
  return sum * 0.0001;
}

// ------------------------------------------------------------ local time

export function parseDate(v: unknown) {
  if (typeof v !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new InputError("date must be YYYY-MM-DD");
  const [y, m, d] = v.split("-").map(Number);
  const x = new Date(Date.UTC(y, m - 1, d));
  if (x.getUTCFullYear() !== y || x.getUTCMonth() !== m - 1 || x.getUTCDate() !== d) throw new InputError("invalid date");
  return { y, m, d };
}

export function parseTime(v: unknown) {
  if (typeof v !== "string" || !/^\d{2}:\d{2}(:\d{2})?$/.test(v)) throw new InputError("time must be HH:MM or HH:MM:SS");
  const [h, mi, s = 0] = v.split(":").map(Number);
  if (h > 23 || mi > 59 || s > 59) throw new InputError("invalid time");
  return { h, mi, s };
}

export function assertSupportedLocalYear(y: number): void {
  if (y < SUPPORTED_MIN_YEAR || y > SUPPORTED_MAX_YEAR) {
    throw new InputError(`birth year outside supported range ${SUPPORTED_MIN_YEAR}-${SUPPORTED_MAX_YEAR}`);
  }
}

// UTC offset (minutes, may be fractional for historical second-level offsets).
export function offsetFor(date: Date, tz: string): number {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat("en-US", {
      timeZone: tz, timeZoneName: "longOffset", hour: "2-digit", hourCycle: "h23",
    }).formatToParts(date);
  } catch {
    throw new InputError("invalid IANA timezone");
  }
  const v = parts.find((p) => p.type === "timeZoneName")?.value ?? "GMT";
  if (v === "GMT" || v === "UTC") return 0;
  const m = v.match(/^GMT([+-])(\d{1,2})(?::?(\d{2}))?(?::(\d{2}))?$/);
  if (!m) throw new InputError("invalid IANA timezone or unavailable historical offset");
  return (m[1] === "+" ? 1 : -1) * (Number(m[2]) * 60 + Number(m[3] || 0) + Number(m[4] || 0) / 60);
}

// Offsets that map a wall-clock time to a UTC instant whose own offset agrees.
// 0 results: DST gap (time never existed). 2 results: DST overlap (ambiguous).
export function validOffsets(wallClockAsUtcMs: number, tz: string): number[] {
  const DAY = 86400000;
  const candidates = new Set([
    offsetFor(new Date(wallClockAsUtcMs - DAY), tz),
    offsetFor(new Date(wallClockAsUtcMs + DAY), tz),
  ]);
  const ok: number[] = [];
  for (const c of candidates) {
    if (offsetFor(new Date(wallClockAsUtcMs - c * 60000), tz) === c) ok.push(c);
  }
  return ok.sort((a, b) => b - a); // larger offset first = earlier instant
}

export function resolveLocalTime(date: unknown, time: unknown, tz: unknown, explicitOffset?: unknown) {
  const { y, m, d } = parseDate(date);
  const { h, mi, s } = parseTime(time);
  assertSupportedLocalYear(y);
  if (typeof tz !== "string" || tz.length === 0 || tz.length > 64) throw new InputError("timeZone must be an IANA timezone name");
  const wall = Date.UTC(y, m - 1, d, h, mi, s);
  const warnings: Warning[] = [];
  let offset: number;

  if (explicitOffset !== undefined && explicitOffset !== null) {
    if (typeof explicitOffset !== "number" || !Number.isFinite(explicitOffset) || Math.abs(explicitOffset) > 14 * 60) {
      throw new InputError("utcOffsetMinutes must be a number between -840 and 840");
    }
    offset = explicitOffset;
    const valid = validOffsets(wall, tz); // also rejects an invalid timezone name
    if (!valid.includes(offset)) {
      warnings.push({
        code: "utc_offset_override",
        message: "utcOffsetMinutes differs from the offset the timezone database gives for this local time; the supplied offset was used.",
        suppliedOffsetMinutes: offset,
        timeZoneOffsetsMinutes: valid,
      });
    }
  } else {
    const valid = validOffsets(wall, tz);
    if (valid.length === 0) {
      throw new InputError(
        "This local time does not exist in the given timezone (daylight-saving gap). Check the birth time, or send utcOffsetMinutes.",
      );
    }
    offset = valid[0];
    if (valid.length > 1) {
      warnings.push({
        code: "ambiguous_local_time",
        message: "This local time occurred twice (daylight-saving overlap). The first occurrence was used; send utcOffsetMinutes to choose.",
        usedOffsetMinutes: offset,
        possibleOffsetsMinutes: valid,
      });
    }
  }
  return { date: new Date(wall - offset * 60000), offsetMinutes: offset, localYear: y, warnings };
}

// -------------------------------------------------------------- warnings

export function boundaryWarnings(moonLongitude: number): Warning[] {
  const x = norm(moonLongitude);
  const edge = (span: number) => {
    const off = x % span;
    return Math.min(off, span - off);
  };
  const rashi = edge(30);
  const nak = edge(360 / 27);
  const pada = edge(360 / 108);
  const out: Warning[] = [];
  const T = BOUNDARY_THRESHOLD_DEGREES;
  const arcmin = (d: number) => Math.round(d * 60 * 100) / 100;
  if (rashi < T) {
    out.push({ code: "rashi_boundary", message: "Moon is very close to a Rashi boundary. Recheck birth time and timezone.", distanceArcmin: arcmin(rashi) });
  }
  if (nak < T) {
    out.push({ code: "nakshatra_boundary", message: "Moon is very close to a Nakshatra boundary. Recheck birth time and timezone.", distanceArcmin: arcmin(nak) });
  } else if (pada < T) {
    out.push({ code: "pada_boundary", message: "Moon is very close to a Pada boundary. Recheck birth time and timezone.", distanceArcmin: arcmin(pada) });
  }
  return out;
}

// ------------------------------------------------------------------ CORS

export function isAllowedOrigin(origin: string | null): boolean {
  if (!origin) return false;
  return /^https:\/\/([a-z0-9-]+\.)*astrolaab\.com$/.test(origin);
}
