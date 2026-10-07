// Independent oracles. None of these share code or formulas with src/chart-core.ts.

// Classical rule: the first navamsa of a fire sign is Aries, earth -> Capricorn,
// air -> Libra, water -> Cancer; the nine navamsas then run in zodiac order.
// (Written as an element table, not the movable/fixed/dual arithmetic the
// implementation uses.)
const FIRST_NAVAMSA_BY_SIGN = [0, 9, 6, 3, 0, 9, 6, 3, 0, 9, 6, 3];

export function navamsaOracle(longitude) {
  const x = ((longitude % 360) + 360) % 360;
  const sign = Math.floor(x / 30);
  const part = Math.floor(((x - sign * 30) * 9) / 30 + 1e-9);
  return (FIRST_NAVAMSA_BY_SIGN[sign] + part) % 12;
}

// Integer arc-minute arithmetic: one nakshatra = 800', one pada = 200'.
export function nakshatraPadaOracle(longitude) {
  const x = ((longitude % 360) + 360) % 360;
  const arcmin = Math.floor(x * 60 + 1e-7);
  return { nakshatraIndex: Math.floor(arcmin / 800), pada: Math.floor((arcmin % 800) / 200) + 1 };
}

export const rashiOracle = (longitude) => Math.floor((((longitude % 360) + 360) % 360) / 30);

// Deterministic PRNG so "random" tests are reproducible.
export function mulberry32(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
