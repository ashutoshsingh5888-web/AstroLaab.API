import test, { beforeEach } from "node:test";
import assert from "node:assert/strict";
import worker from "../../src/index.ts";
import { calls, reset } from "./panchangam-stub.mjs";
import * as core from "../../src/chart-core.ts";

const ORIGIN = "https://astrolaab.com";
const place = (lat = 19.076, lon = 72.8777) => ({ name: "Test", country: "X", latitude: lat, longitude: lon });
const base = (over = {}) => ({ date: "1990-05-15", time: "14:30:00", timeZone: "Asia/Kolkata", place: place(), ...over });

async function post(body, { path = "/birth-chart", raw, headers = {}, env } = {}) {
  const req = new Request("https://w.test" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: ORIGIN, ...headers },
    body: raw ?? JSON.stringify(body),
  });
  const res = await worker.fetch(req, env, undefined);
  return { res, json: await res.json() };
}
async function get(path, { origin = ORIGIN, env } = {}) {
  const res = await worker.fetch(new Request("https://w.test" + path, { headers: origin ? { Origin: origin } : {} }), env, undefined);
  return { res, text: await res.text() };
}

beforeEach(() => { reset(); delete globalThis.caches; });

// ------------------------------------------------------------- happy path
test("birth-chart: response contract is intact (fields other validators rely on)", async () => {
  const { res, json } = await post(base());
  assert.equal(res.status, 200);
  assert.equal(json.ok, true);
  assert.equal(json.engine, "Swiss Ephemeris");
  assert.equal(json.calculationProfile.ayanamsha, "Lahiri (Chitrapaksha)");
  assert.equal(json.calculationProfile.timeScales.planets, "TT");
  assert.equal(json.calculationProfile.timeScales.houses, "UT");
  assert.deepEqual(json.calculationProfile.supportedDeltaTYearRange, { min: 1950, max: 2050 });
  assert.equal(json.calculationProfile.nodeType, "mean");
  assert.equal(typeof json.ayanamsha.degrees, "number");
  assert.equal(json.moon.sign.english, "Cancer");       // stub Moon at 100 deg
  assert.ok(Array.isArray(json.planets) && json.planets.length >= 7);
  assert.ok(Array.isArray(json.warnings));
  assert.equal(json.birth.utc, "1990-05-15T09:00:00.000Z");
});

test("moon sign / nakshatra / pada / navamsa for the stubbed Moon", async () => {
  globalThis.__stub.moon = 344.3919; // Pisces 14 deg 23', Uttara Bhadrapada pada 4
  const { json } = await post(base());
  assert.equal(json.moon.sign.english, "Pisces");
  assert.equal(json.moon.nakshatra.name, "Uttara Bhadrapada");
  assert.equal(json.moon.nakshatra.pada, 4);
  assert.equal(json.moon.navamsa.english, core.divisionalSign(344.3919, 9).english);
  assert.equal(json.moon.degreeInSignDms.text, "14° 23′ 31″");
});

// ------------------------------------------------------------ time scales
test("planets get TT, houses get UT, and the gap equals the reported delta-T", async () => {
  const { json } = await post(base({ date: "2024-03-10", time: "08:00:00" }));
  const tt = calls.planets[0].jd, ut = calls.houses[0].jd;
  const gap = (tt - ut) * 86400;
  assert.ok(Math.abs(gap - json.calculationProfile.timeScales.deltaTSeconds) < 1e-3);
  assert.ok(Math.abs(gap - 69.0) < 1.0, `2024 delta-T ~69 s, got ${gap}`);
  assert.equal(json.birth.julianDayUT, ut);
  assert.equal(json.birth.julianDayTT, tt);
});

// ----------------------------------------------------------------- houses
test("default house system is Whole Sign; cusps come from the Ascendant, not the wrapper", async () => {
  globalThis.__stub.asc = 123.456; // Leo
  const { json } = await post(base());
  assert.equal(json.houses.system, "W");
  assert.equal(json.calculationProfile.houseSystem, "W");
  assert.equal(calls.houses[0].system, "W");
  assert.equal(json.houses.cusps.length, 12);
  assert.equal(json.houses.cusps[0].longitude, 120);   // start of Leo
  assert.equal(json.houses.cusps[1].longitude, 150);
  assert.equal(json.houses.cusps[11].longitude, 90);
  assert.equal(json.houses.ascendant.english, "Leo");
  assert.ok(json.houses.cusps.every((c) => c.longitude % 30 === 0));
});

test("Equal houses: cusp 1 is the Ascendant, ignoring wrapper cusps", async () => {
  globalThis.__stub.asc = 200.25;
  const { json } = await post(base({ houseSystem: "e" }));
  assert.equal(json.houses.system, "E");
  assert.equal(json.houses.cusps[0].longitude, 200.25);
  assert.ok(Math.abs(json.houses.cusps[3].longitude - 290.25) < 1e-9);
});

test("Placidus: wrapper cusps pass through, labelled P, exactly 12", async () => {
  const { json } = await post(base({ houseSystem: "P" }));
  assert.equal(json.houses.system, "P");
  assert.equal(json.houses.cusps.length, 12);
  assert.ok(Math.abs(json.houses.cusps[1].longitude - (123.456 + 31.5)) < 1e-9);
});

test("Placidus above the polar limit is rejected; Whole Sign and Equal still work there", async () => {
  for (const lat of [66.6, 70, -70, 89]) {
    const r = await post(base({ houseSystem: "P", place: place(lat, 25) }));
    assert.equal(r.res.status, 400, `lat ${lat}`);
    assert.match(r.json.error, /Placidus/);
  }
  for (const hs of ["W", "E"]) {
    const r = await post(base({ houseSystem: hs, place: place(78.2, 15.6) })); // Longyearbyen
    assert.equal(r.res.status, 200);
  }
});

test("planets carry Whole Sign house numbers from the Ascendant (null without a place)", async () => {
  globalThis.__stub.asc = 123.456; // Leo = house 1
  const { json } = await post(base());
  const h = Object.fromEntries(json.planets.map((p) => [p.name, p.wholeSignHouse]));
  assert.equal(h.Sun, core.wholeSignHouse(50, 123.456));   // Taurus -> 10
  assert.equal(h.Sun, 10);
  assert.equal(h.Mars, 2);                                   // Virgo
  assert.equal(h.Jupiter, 3);                                // 200 deg = Libra, 3rd from Leo
  const noPlace = await post({ date: "1990-05-15", time: "14:30:00", timeZone: "Asia/Kolkata" });
  assert.equal(noPlace.json.houses, null);
  assert.ok(noPlace.json.planets.every((p) => p.wholeSignHouse === null));
});

test("invalid house system / location are 400s", async () => {
  assert.equal((await post(base({ houseSystem: "K" }))).res.status, 400);
  const badPlaces = [
    place(91, 0), place(0, 181), place(NaN, 0), place("x", 0), { latitude: 1 },
    { latitude: null, longitude: 72 }, { latitude: 19, longitude: null },   // null must not become 0
    { latitude: "", longitude: 72 }, { latitude: true, longitude: 72 }, { latitude: [], longitude: 72 },
    { latitude: {}, longitude: 72 }, { latitude: "  ", longitude: 72 },
  ];
  for (const p of badPlaces) {
    assert.equal((await post(base({ place: p }))).res.status, 400, JSON.stringify(p));
  }
  // numeric strings are still accepted (backwards compatible)
  assert.equal((await post(base({ place: { latitude: "19.07", longitude: "72.87" } }))).res.status, 200);
});

// ------------------------------------------------------------ time & range
test("DST gap -> 400; overlap -> 200 with a warning; explicit offset clears it", async () => {
  const gap = await post(base({ date: "2020-03-08", time: "02:30:00", timeZone: "America/New_York" }));
  assert.equal(gap.res.status, 400);
  assert.match(gap.json.error, /does not exist/);
  const amb = await post(base({ date: "2020-11-01", time: "01:30:00", timeZone: "America/New_York" }));
  assert.equal(amb.res.status, 200);
  assert.equal(amb.json.warnings[0].code, "ambiguous_local_time");
  const fixed = await post(base({ date: "2020-11-01", time: "01:30:00", timeZone: "America/New_York", utcOffsetMinutes: -300 }));
  assert.equal(fixed.res.status, 200);
  assert.equal(fixed.json.warnings.filter((w) => w.code === "ambiguous_local_time").length, 0);
  assert.equal(fixed.json.birth.utc, "2020-11-01T06:30:00.000Z");
});

test("a contradicting utcOffsetMinutes is used but flagged", async () => {
  const { res, json } = await post(base({ timeZone: "America/New_York", date: "2020-07-15", time: "12:00:00", utcOffsetMinutes: 330 }));
  assert.equal(res.status, 200);
  assert.equal(json.birth.utcOffsetMinutes, 330);
  assert.equal(json.warnings[0].code, "utc_offset_override");
});

test("supported range is judged on the local birth year", async () => {
  const cases = [
    ["1949-12-31", "23:59:59", "Asia/Kolkata", 400],
    ["1950-01-01", "00:00:00", "Asia/Kolkata", 200],
    ["1950-01-01", "03:00:00", "Asia/Kolkata", 200],     // UTC is 1949-12-31
    ["2050-12-31", "22:00:00", "America/New_York", 200], // UTC is 2051-01-01
    ["2051-01-01", "00:00:00", "UTC", 400],
    ["2050-06-15", "12:00:00", "Asia/Kolkata", 200],
  ];
  for (const [date, time, timeZone, status] of cases) {
    const r = await post(base({ date, time, timeZone }));
    assert.equal(r.res.status, status, `${date} ${time} ${timeZone}: ${JSON.stringify(r.json.error)}`);
  }
});

// ---------------------------------------------------------------- warnings
test("boundary warnings reach the response; legacy boundaryWarning string kept", async () => {
  globalThis.__stub.moon = 30 - 10 / 3600;
  const near = await post(base());
  assert.ok(near.json.warnings.some((w) => w.code === "rashi_boundary"));
  assert.equal(typeof near.json.boundaryWarning, "string");
  globalThis.__stub.moon = 15.3;
  const quiet = await post(base());
  assert.deepEqual(quiet.json.warnings, []);
  assert.equal(quiet.json.boundaryWarning, null);
});

// ------------------------------------------------------------ error model
test("input errors are 400; internal failures are 500 with no leaked detail", async () => {
  assert.equal((await post(null, { raw: "{not json" })).res.status, 400);
  assert.equal((await post(null, { raw: "" })).res.status, 400);
  assert.equal((await post(null, { raw: "[]" })).res.status, 400);
  assert.equal((await post(null, { raw: "null" })).res.status, 400);
  assert.equal((await post({})).res.status, 400);
  assert.equal((await post({ date: "2020-01-01", time: "12:00" })).res.status, 400);
  assert.equal((await post(base({ timeZone: "Nope/Nope" }))).res.status, 400);
  globalThis.__stub.throwPlanets = true;
  const boom = await post(base());
  assert.equal(boom.res.status, 500);
  assert.equal(boom.json.error, "internal error");
  assert.ok(!JSON.stringify(boom.json).includes("wasm"));
});

test("oversized body is 413", async () => {
  const r = await post(null, { raw: JSON.stringify(base({ junk: "x".repeat(20000) })) });
  assert.equal(r.res.status, 413);
});

test("/moon-sign is an alias of /birth-chart", async () => {
  const a = await post(base(), { path: "/moon-sign" });
  assert.equal(a.res.status, 200);
});

// ------------------------------------------------- routing / diagnostics
test("unknown routes and removed diagnostic endpoints are 404", async () => {
  for (const p of ["/self-test", "/accuracy-test", "/forensic-test", "/nope", "/"]) {
    assert.equal((await get(p)).res.status, 404, p);
  }
  assert.equal((await get("/health")).res.status, 200);
  const wrongMethod = await worker.fetch(new Request("https://w.test/birth-chart"), undefined, undefined);
  assert.equal(wrongMethod.status, 404);
});

test("CORS: allowed origins echoed, others get the canonical origin, preflight works", async () => {
  const ok = await get("/health", { origin: "https://app.astrolaab.com" });
  assert.equal(ok.res.headers.get("access-control-allow-origin"), "https://app.astrolaab.com");
  const bad = await get("/health", { origin: "https://evil.com" });
  assert.equal(bad.res.headers.get("access-control-allow-origin"), "https://astrolaab.com");
  const http = await get("/health", { origin: "http://app.astrolaab.com" });
  assert.equal(http.res.headers.get("access-control-allow-origin"), "https://astrolaab.com");
  const pre = await worker.fetch(new Request("https://w.test/birth-chart", { method: "OPTIONS", headers: { Origin: ORIGIN } }), undefined, undefined);
  assert.equal(pre.status, 204);
  assert.equal(pre.headers.get("vary"), "Origin");
});

// ---------------------------------------------------------------- /location
const photon = (features) => ({ ok: true, status: 200, json: async () => ({ features }) });
const feature = (name, lon, lat) => ({ properties: { name, country: "India", osm_type: "N", osm_id: 1 }, geometry: { coordinates: [lon, lat] } });

test("/location: validation, mapping, upstream failures", async () => {
  const realFetch = globalThis.fetch;
  try {
    assert.equal((await get("/location?q=a")).res.status, 400);
    assert.equal((await get("/location?q=" + "x".repeat(101))).res.status, 400);
    globalThis.fetch = async () => photon([feature("Mumbai", 72.8777, 19.076), { properties: {}, geometry: { coordinates: ["bad", 1] } }]);
    const ok = JSON.parse((await get("/location?q=Mumbai")).text);
    assert.equal(ok.results.length, 1);
    assert.equal(ok.results[0].latitude, 19.076);
    globalThis.fetch = async () => ({ ok: false, status: 503 });
    assert.equal((await get("/location?q=Mumbai")).res.status, 502);
    globalThis.fetch = async () => { throw new DOMException("timeout", "TimeoutError"); };
    assert.equal((await get("/location?q=Mumbai")).res.status, 504);
  } finally { globalThis.fetch = realFetch; }
});

test("/location: rate limiter binding returns 429 with Retry-After", async () => {
  const env = { LOCATION_LIMITER: { limit: async ({ key }) => ({ success: key !== "1.2.3.4" }) } };
  const req = new Request("https://w.test/location?q=Mumbai", { headers: { "CF-Connecting-IP": "1.2.3.4", Origin: ORIGIN } });
  const res = await worker.fetch(req, env, undefined);
  assert.equal(res.status, 429);
  assert.equal(res.headers.get("retry-after"), "60");
});

test("/location: successful lookups are cached; the second call never reaches Photon", async () => {
  const store = new Map();
  globalThis.caches = { default: {
    match: async (k) => (store.has(k.url) ? new Response(store.get(k.url)) : undefined),
    put: async (k, r) => { store.set(k.url, await r.text()); },
  } };
  const realFetch = globalThis.fetch;
  let upstream = 0;
  try {
    globalThis.fetch = async () => { upstream++; return photon([feature("Mumbai", 72.8777, 19.076)]); };
    const a = JSON.parse((await get("/location?q=Mumbai")).text);
    const b = JSON.parse((await get("/location?q=%20mumbai%20")).text); // normalised key
    assert.equal(upstream, 1);
    assert.deepEqual(a.results, b.results);
  } finally { globalThis.fetch = realFetch; }
});
