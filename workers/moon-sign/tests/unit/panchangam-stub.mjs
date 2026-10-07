// Deterministic stand-in for @fusionstrings/panchangam/browser. It tests the
// Worker's own logic (routing, validation, time scales, house handling), not
// astronomy: astronomical accuracy is covered by the pyswisseph validators.
export const calls = { planets: [], houses: [] };

export function reset() {
  calls.planets.length = 0;
  calls.houses.length = 0;
  globalThis.__stub = { moon: 100.0, sun: 50.0, asc: 123.456, throwPlanets: false };
}
reset();

export function p_julday(y, m, d, h) {
  let Y = y, M = m;
  if (M <= 2) { Y -= 1; M += 12; }
  const A = Math.floor(Y / 100), B = 2 - A + Math.floor(A / 4);
  return Math.floor(365.25 * (Y + 4716)) + Math.floor(30.6001 * (M + 1)) + d + B - 1524.5 + h / 24;
}
export const get_ayanamsha = (_mode, jd) => 23.85 + ((jd - 2451545) / 365.25) * (50.29 / 3600);
export const get_swisseph_version = () => "stub-2.10.03";

export function calculate_planets(jd, mode) {
  calls.planets.push({ jd, mode });
  const s = globalThis.__stub;
  if (s.throwPlanets) throw new Error("boom: wasm exploded with secret detail");
  const p = (id, name, longitude, retro = false) => ({ id, name, longitude, latitude: 0, speed: 1, is_retrograde: retro });
  return [
    p(0, "Sun", s.sun), p(1, "Moon", s.moon), p(2, "Mercury", 61), p(3, "Venus", 75),
    p(4, "Mars", 155), p(5, "Jupiter", 200), p(6, "Saturn", 344.39, true),
    p(10, "Rahu", 154.5, true), p(11, "Ketu", 334.5, true),
  ];
}

export function calculate_houses(jd, lat, lon, system, mode) {
  calls.houses.push({ jd, lat, lon, system, mode });
  const s = globalThis.__stub;
  // Placidus-like cusps for 'P'. Deliberately WRONG cusps for W/E: the Worker
  // must derive those from the Ascendant, so any use of these shows up in tests.
  const cusps = system === "P"
    ? Array.from({ length: 12 }, (_, i) => (s.asc + i * 31.5) % 360)
    : Array(12).fill(1.2345);
  return { ascendant: s.asc, cusps };
}
