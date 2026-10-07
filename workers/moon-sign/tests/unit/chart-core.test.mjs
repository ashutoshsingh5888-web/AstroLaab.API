import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as core from "../../src/chart-core.ts";
import { navamsaOracle, nakshatraPadaOracle, rashiOracle, mulberry32 } from "./oracle.mjs";

const SLOT = 10 / 3; // 3 deg 20'
const EPS_IN = 1e-6;

// ------------------------------------------------------------------ D9
test("D9: all 108 navamsa slots, start / interior / end, match the classical oracle", () => {
  for (let k = 0; k < 108; k++) {
    const start = k * SLOT;
    for (const lon of [start + EPS_IN, start + SLOT / 2, start + SLOT - EPS_IN]) {
      assert.equal(core.navamsaSignIndex(lon), navamsaOracle(lon), `slot ${k} lon ${lon}`);
      assert.equal(core.divisionalSign(lon, 9).index - 1, navamsaOracle(lon), `divisionalSign slot ${k}`);
    }
  }
});

test("D9: the exact 3 deg 20' boundary belongs to the NEXT navamsa (no floating-point slip)", () => {
  for (let k = 0; k < 108; k++) {
    const exact = (k * 10) / 3;
    assert.equal(core.padaSlot(exact), k, `exact boundary of slot ${k}`);
    assert.equal(core.navamsaSignIndex(exact), k % 12);
  }
});

test("D9: one arcsecond either side of every boundary flips the navamsa exactly once", () => {
  const ARCSEC = 1 / 3600;
  for (let k = 1; k < 108; k++) {
    const b = k * SLOT;
    const before = core.navamsaSignIndex(b - ARCSEC);
    const after = core.navamsaSignIndex(b + ARCSEC);
    assert.equal(before, navamsaOracle(b - ARCSEC));
    assert.equal(after, navamsaOracle(b + ARCSEC));
    assert.notEqual(before, after, `navamsa must change at boundary ${k}`);
  }
});

test("D9: known textbook anchors", () => {
  const idx = (l) => core.divisionalSign(l, 9).english;
  assert.equal(idx(0.0), "Aries");          // Aries 0 deg -> Aries
  assert.equal(idx(30.0), "Capricorn");     // Taurus 0 deg -> Capricorn
  assert.equal(idx(60.0), "Libra");         // Gemini 0 deg -> Libra
  assert.equal(idx(90.0), "Cancer");        // Cancer 0 deg -> Cancer
  assert.equal(idx(120.0), "Aries");        // Leo 0 deg -> Aries
  assert.equal(idx(359.99999), "Pisces");   // Pisces 9th navamsa -> Pisces (vargottama)
  assert.equal(idx(330.0), "Cancer");       // Pisces 0 deg -> Cancer
  assert.equal(idx(29.99999), "Sagittarius"); // Aries last navamsa -> Sagittarius
});

test("D9: random longitudes agree with the oracle", () => {
  const rnd = mulberry32(9);
  for (let i = 0; i < 20000; i++) {
    const lon = rnd() * 360;
    assert.equal(core.navamsaSignIndex(lon), navamsaOracle(lon));
  }
});

test("divisionalSign: unsupported vargas fail loudly, D1 equals the sign", () => {
  for (const d of [2, 3, 7, 10, 12]) assert.throws(() => core.divisionalSign(10, d), /not implemented/);
  assert.equal(core.divisionalSign(75.5, 1).index, 3);
});

// ----------------------------------------------------- nakshatra / pada
test("Nakshatra + Pada: every pada boundary, edges and interior, vs integer-arcminute oracle", () => {
  for (let k = 0; k < 108; k++) {
    for (const lon of [k * SLOT + EPS_IN, k * SLOT + SLOT / 2, (k + 1) * SLOT - EPS_IN]) {
      const got = core.nakshatraPada(lon % 360);
      const exp = nakshatraPadaOracle(lon % 360);
      assert.equal(got.index - 1, exp.nakshatraIndex, `nakshatra at ${lon}`);
      assert.equal(got.pada, exp.pada, `pada at ${lon}`);
    }
  }
});

test("Nakshatra + Pada: 108 padas are the same partition as the 108 navamsas", () => {
  const rnd = mulberry32(108);
  for (let i = 0; i < 5000; i++) {
    const lon = rnd() * 360;
    const np = core.nakshatraPada(lon);
    assert.equal(np.slot % 12, core.navamsaSignIndex(lon));
    assert.equal(np.slot, (np.index - 1) * 4 + (np.pada - 1));
  }
});

test("Nakshatra table: names are in order and Revati ends the zodiac", () => {
  assert.equal(core.NAKSHATRAS.length, 27);
  assert.equal(core.nakshatraPada(0.0001).name, "Ashwini");
  assert.equal(core.nakshatraPada(359.9999).name, "Revati");
  assert.equal(core.nakshatraPada(359.9999).pada, 4);
  assert.equal(core.nakshatraPada(344.3919).name, "Uttara Bhadrapada"); // AstroSage Bill Gates Moon
  assert.equal(core.nakshatraPada(344.3919).pada, 4);
});

// ------------------------------------------------------------ sign / dms
test("norm: exact for in-range values, wraps negatives, never returns 360", () => {
  assert.equal(core.norm(123.456), 123.456);
  assert.equal(core.norm(0), 0);
  assert.equal(core.norm(360), 0);
  assert.equal(core.norm(720.5), 0.5);
  assert.equal(core.norm(-0.5), 359.5);
  assert.equal(core.norm(-360), 0);
  assert.ok(core.norm(-1e-20) < 360);
});

test("signOf: sign boundaries, wrap-around and negatives", () => {
  for (let s = 0; s < 12; s++) {
    assert.equal(core.signOf(s * 30).index, s + 1);
    assert.equal(core.signOf(s * 30 + 29.9999999).index, s + 1);
  }
  assert.equal(core.signOf(360).index, 1);
  assert.equal(core.signOf(-0.0001).index, 12);
  assert.equal(core.signOf(725).index, rashiOracle(725) + 1);
});

test("dms never prints 30 degrees and never rounds minutes to 60", () => {
  assert.equal(core.dms(29.99999).text, "29° 59′ 59″");
  assert.equal(core.dms(0).text, "0° 00′ 00″");
  assert.equal(core.dms(14 + 23 / 60 + 31 / 3600).text, "14° 23′ 31″");
  const rnd = mulberry32(3);
  for (let i = 0; i < 20000; i++) {
    const d = core.dms(rnd() * 30);
    assert.ok(d.degrees <= 29 && d.minutes <= 59 && d.seconds <= 59, d.text);
  }
});

// ---------------------------------------------------------- Whole Sign
test("Whole Sign: cusp 1 is the start of the Ascendant's sign, cusps step by 30", () => {
  const rnd = mulberry32(12);
  for (let i = 0; i < 2000; i++) {
    const asc = rnd() * 360;
    const c = core.wholeSignCusps(asc);
    assert.equal(c.length, 12);
    assert.equal(c[0], Math.floor(asc / 30) * 30);
    for (let h = 0; h < 12; h++) {
      assert.ok(Math.abs(((c[h] - c[0] + 360) % 360) - h * 30) < 1e-9);
      assert.equal(c[h] % 30, 0);
    }
    assert.equal(new Set(c.map((v) => Math.floor(v / 30))).size, 12);
  }
});

test("Whole Sign: Ascendant at the edges of a sign and across the 360 wrap", () => {
  assert.deepEqual(core.wholeSignCusps(0).slice(0, 3), [0, 30, 60]);
  assert.deepEqual(core.wholeSignCusps(29.9999999).slice(0, 2), [0, 30]);
  assert.deepEqual(core.wholeSignCusps(30).slice(0, 2), [30, 60]);
  assert.deepEqual(core.wholeSignCusps(359.9999).slice(0, 3), [330, 0, 30]);
});

test("Whole Sign houses: planets are numbered from the Ascendant's sign", () => {
  // Ascendant 45.5 (Taurus, AstroSage Pooja Sharma): Taurus = house 1.
  const asc = 45.5;
  const cases = [
    // Taurus is house 1, then Gemini 2, Cancer 3, Leo 4, Virgo 5, Libra 6, Scorpio 7 ...
    [45.0, 1], [59.99, 1], [60.0, 2], [126.7083, 4], // Sun in Leo
    [154.5611, 5], [30.0, 1], [29.99, 12], [0.0, 12], [344.39, 11], [225.0, 7],
  ];
  for (const [lon, house] of cases) assert.equal(core.wholeSignHouse(lon, asc), house, `lon ${lon}`);
});

test("Whole Sign houses: for any Ascendant the 12 signs map to houses 1..12 exactly once", () => {
  const rnd = mulberry32(77);
  for (let i = 0; i < 500; i++) {
    const asc = rnd() * 360;
    const seen = new Set();
    for (let s = 0; s < 12; s++) seen.add(core.wholeSignHouse(s * 30 + 15, asc));
    assert.equal(seen.size, 12);
    assert.equal(core.wholeSignHouse(asc, asc), 1);
    assert.equal(core.wholeSignHouse((Math.floor(asc / 30) * 30 + 180 + 5) % 360, asc), 7);
  }
});

test("Equal houses: cusp 1 is the Ascendant itself", () => {
  const c = core.equalCusps(123.456);
  assert.equal(c[0], 123.456);
  assert.ok(Math.abs(c[6] - 303.456) < 1e-9);
});

test("House system validation", () => {
  for (const s of ["P", "W", "E"]) core.assertHouseSystem(s, 10);
  assert.throws(() => core.assertHouseSystem("K", 10), /P, W or E/);
  assert.throws(() => core.assertHouseSystem("P", 70), /Placidus/);
  assert.throws(() => core.assertHouseSystem("P", -66.6), /Placidus/);
  core.assertHouseSystem("P", 66.4);
  core.assertHouseSystem("W", 89.9);
  core.assertHouseSystem("E", -89.9);
});

// -------------------------------------------------------------- delta-T
const DT = JSON.parse(readFileSync(new URL("../fixtures/deltat-reference.json", import.meta.url), "utf8"));

test("delta-T: every month 1949-2051 is within 0.5 s of swe.deltat (1 s for 2051 extrapolation)", () => {
  let worst = 0;
  for (const r of DT.rows) {
    const dy = r.y + (r.m - 1 + 0.5) / 12;
    const got = core.deltaT(dy);
    const tol = r.y > 2050 ? 1.0 : 0.5;
    const err = Math.max(Math.abs(got - r.min), Math.abs(got - r.max));
    worst = Math.max(worst, err);
    assert.ok(err <= tol, `${r.y}-${r.m}: worker ${got.toFixed(3)} vs swe ${r.min}..${r.max}`);
  }
  assert.ok(worst < 0.5, `worst ${worst}`);
});

test("delta-T: continuous at the 2005 and 2050 seams and outside range throws", () => {
  assert.ok(Math.abs(core.deltaT(2004.9999) - core.deltaT(2005.0001)) < 0.3);
  assert.equal(core.deltaT(2050.5), core.DELTA_T_SECONDS[2050]);
  assert.equal(core.deltaT(2051.04), core.DELTA_T_SECONDS[2050]);
  assert.throws(() => core.deltaT(1948.5));
  assert.throws(() => core.deltaT(2052.5));
});

// ------------------------------------------------------------- local time
const utc = (r) => r.date.toISOString();

test("local time: ordinary conversions (India, Nepal, Newfoundland, UTC, London BST)", () => {
  assert.equal(utc(core.resolveLocalTime("1990-05-15", "14:30:00", "Asia/Kolkata")), "1990-05-15T09:00:00.000Z");
  assert.equal(core.resolveLocalTime("2000-01-01", "12:00", "Asia/Kathmandu").offsetMinutes, 345);
  assert.equal(core.resolveLocalTime("2000-01-01", "12:00", "America/St_Johns").offsetMinutes, -210);
  assert.equal(core.resolveLocalTime("2000-01-01", "12:00", "UTC").offsetMinutes, 0);
  assert.equal(core.resolveLocalTime("1975-03-30", "09:15:00", "Europe/London").offsetMinutes, 60);
  assert.equal(core.resolveLocalTime("1962-06-01", "12:00:00", "Asia/Kolkata").offsetMinutes, 330);
});

test("local time: second-level historical offsets (Monrovia -0:44:30 in 1970)", () => {
  const r = core.resolveLocalTime("1970-01-01", "12:00:00", "Africa/Monrovia");
  assert.equal(r.offsetMinutes, -44.5);
  assert.equal(utc(r), "1970-01-01T12:44:30.000Z");
});

test("local time: DST gap is rejected (northern, southern, half-hour DST)", () => {
  assert.throws(() => core.resolveLocalTime("2020-03-08", "02:30:00", "America/New_York"), /does not exist/);
  assert.throws(() => core.resolveLocalTime("2021-10-03", "02:30:00", "Australia/Sydney"), /does not exist/);
  assert.throws(() => core.resolveLocalTime("2021-10-03", "02:15:00", "Australia/Lord_Howe"), /does not exist/);
  // one minute either side of the gap is fine
  core.resolveLocalTime("2020-03-08", "01:59:59", "America/New_York");
  core.resolveLocalTime("2020-03-08", "03:00:00", "America/New_York");
});

test("local time: DST overlap is accepted with a warning, first occurrence used", () => {
  const ny = core.resolveLocalTime("2020-11-01", "01:30:00", "America/New_York");
  assert.equal(ny.offsetMinutes, -240);
  assert.equal(utc(ny), "2020-11-01T05:30:00.000Z");
  assert.equal(ny.warnings[0].code, "ambiguous_local_time");
  assert.deepEqual(ny.warnings[0].possibleOffsetsMinutes, [-240, -300]);
  const syd = core.resolveLocalTime("2021-04-04", "02:30:00", "Australia/Sydney");
  assert.equal(syd.warnings[0].code, "ambiguous_local_time");
  const lh = core.resolveLocalTime("2021-04-04", "01:45:00", "Australia/Lord_Howe");
  assert.equal(lh.warnings[0].code, "ambiguous_local_time");
  // an explicit offset resolves the ambiguity with no warning
  const est = core.resolveLocalTime("2020-11-01", "01:30:00", "America/New_York", -300);
  assert.equal(utc(est), "2020-11-01T06:30:00.000Z");
  assert.equal(est.warnings.length, 0);
});

test("local time: an explicit offset that contradicts the timezone is used but flagged", () => {
  const r = core.resolveLocalTime("2020-07-15", "12:00:00", "America/New_York", 330);
  assert.equal(r.offsetMinutes, 330);
  assert.equal(r.warnings[0].code, "utc_offset_override");
  assert.equal(core.resolveLocalTime("2020-07-15", "12:00:00", "America/New_York", -240).warnings.length, 0);
});

test("local time: supported range is checked on the LOCAL year, not the UTC year", () => {
  // Local 1950-01-01 03:00 IST is 1949-12-31 UTC: must be accepted.
  const a = core.resolveLocalTime("1950-01-01", "03:00:00", "Asia/Kolkata");
  assert.equal(utc(a), "1949-12-31T21:30:00.000Z");
  // Local 2050-12-31 22:00 New York is 2051-01-01 UTC: must be accepted.
  const b = core.resolveLocalTime("2050-12-31", "22:00:00", "America/New_York");
  assert.equal(utc(b), "2051-01-01T03:00:00.000Z");
  // ...and delta-T must be computable for both of those UTC instants.
  core.deltaT(core.decimalYearOf(a.date));
  core.deltaT(core.decimalYearOf(b.date));
  assert.throws(() => core.resolveLocalTime("1949-12-31", "23:59:59", "Asia/Kolkata"), /supported range/);
  assert.throws(() => core.resolveLocalTime("2051-01-01", "00:00:00", "UTC"), /supported range/);
});

test("local time: input validation", () => {
  const bad = (d, t, z, rx, off) => assert.throws(() => core.resolveLocalTime(d, t, z, off), rx);
  bad("2020-02-30", "12:00", "UTC", /invalid date/);
  bad("2021-02-29", "12:00", "UTC", /invalid date/);
  bad("2020-13-01", "12:00", "UTC", /invalid date/);
  bad("20-01-01", "12:00", "UTC", /YYYY-MM-DD/);
  bad(20200101, "12:00", "UTC", /YYYY-MM-DD/);
  bad("2020-01-01", "24:00", "UTC", /invalid time/);
  bad("2020-01-01", "12:60", "UTC", /invalid time/);
  bad("2020-01-01", "12:00:60", "UTC", /invalid time/);
  bad("2020-01-01", "noon", "UTC", /HH:MM/);
  bad("2020-01-01", "12:00", "Mars/Olympus", /IANA/);
  bad("2020-01-01", "12:00", "", /IANA/);
  bad("2020-01-01", "12:00", undefined, /IANA/);
  bad("2020-01-01", "12:00", "UTC", /utcOffsetMinutes/, "330");
  bad("2020-01-01", "12:00", "UTC", /utcOffsetMinutes/, 900);
  bad("2020-01-01", "12:00", "UTC", /utcOffsetMinutes/, Number.NaN);
  core.resolveLocalTime("2020-02-29", "12:00", "UTC"); // real leap day
  core.resolveLocalTime("2000-02-29", "12:00", "UTC");
  bad("2100-02-29", "12:00", "UTC", /supported range|invalid date/);
});

test("local time: InputError type is used for every user-input failure", () => {
  try { core.resolveLocalTime("2020-02-30", "12:00", "UTC"); assert.fail("should throw"); }
  catch (e) { assert.ok(e instanceof core.InputError); }
});

// ------------------------------------------------------------- warnings
test("boundary warnings: Rashi, Nakshatra and Pada edges, nothing mid-slot", () => {
  const codes = (lon) => core.boundaryWarnings(lon).map((w) => w.code);
  assert.deepEqual(codes(15.0 + 0.3), []);                                // mid-sign, mid-pada
  assert.ok(codes(30 - 10 / 3600).includes("rashi_boundary"));            // 10" before Rashi edge
  assert.ok(codes(30 + 10 / 3600).includes("rashi_boundary"));
  assert.ok(codes(13 + 1 / 3 + 0.02).includes("nakshatra_boundary"));     // 13 deg 20' edge
  assert.ok(codes(5 * SLOT + 0.05).includes("pada_boundary"));            // a pada-only edge
  assert.ok(!codes(5 * SLOT + 0.05).includes("nakshatra_boundary"));
  assert.ok(!codes(5 * SLOT + 0.2).includes("pada_boundary"));            // 12' away: quiet
  assert.equal(core.boundaryWarnings(359.99)[0].code, "rashi_boundary");  // wrap-around
  assert.equal(core.boundaryWarnings(0.01)[0].code, "rashi_boundary");
  const w = core.boundaryWarnings(30 - 10 / 3600)[0];
  assert.ok(w.distanceArcmin > 0 && w.distanceArcmin < 0.2);
});

// ------------------------------------------------------------------ CORS
test("CORS allow-list: https only, exact astrolaab.com family", () => {
  for (const o of ["https://astrolaab.com", "https://www.astrolaab.com", "https://app.astrolaab.com", "https://a.b.astrolaab.com"]) {
    assert.equal(core.isAllowedOrigin(o), true, o);
  }
  for (const o of ["http://astrolaab.com", "http://x.astrolaab.com", "https://evilastrolaab.com", "https://astrolaab.com.evil.com",
                   "https://astrolaab.comx", "https://evil.com/.astrolaab.com", null, "", "null"]) {
    assert.equal(core.isAllowedOrigin(o), false, String(o));
  }
});
