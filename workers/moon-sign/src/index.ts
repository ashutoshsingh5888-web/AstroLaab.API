import {
  calculate_houses,
  calculate_planets,
  get_ayanamsha,
  get_swisseph_version,
  p_julday,
} from "@fusionstrings/panchangam/browser";
import {
  InputError,
  SUPPORTED_MAX_YEAR,
  SUPPORTED_MIN_YEAR,
  assertHouseSystem,
  boundaryWarnings,
  decimalYearOf,
  deltaT,
  divisionalSign,
  equalCusps,
  isAllowedOrigin,
  nakshatraPada,
  norm,
  resolveLocalTime,
  signOf,
  wholeSignCusps,
  wholeSignHouse,
} from "./chart-core.ts";

type Env = {
  // Optional Cloudflare Rate Limiting binding. See README for the wrangler snippet.
  LOCATION_LIMITER?: { limit(options: { key: string }): Promise<{ success: boolean }> };
};
type Ctx = { waitUntil(p: Promise<unknown>): void };

const MAX_BODY_BYTES = 16 * 1024;

function cors(origin: string | null) {
  return {
    "Access-Control-Allow-Origin": isAllowedOrigin(origin) ? origin! : "https://astrolaab.com",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Vary": "Origin",
  };
}
function json(data: unknown, status = 200, req?: Request, extra: Record<string, string> = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...cors(req?.headers.get("Origin") ?? null), ...extra },
  });
}
function err(message: string, req: Request, status = 400, extra: Record<string, string> = {}) {
  return json({ ok: false, error: message }, status, req, extra);
}

// Number(null), Number("") and Number(true) are 0, 0 and 1: a missing coordinate
// must not silently become the equator or the prime meridian.
function toCoordinate(v: unknown): number {
  if (typeof v === "number") return v;
  if (typeof v === "string" && v.trim() !== "") return Number(v);
  return Number.NaN;
}

function calculate(body: any) {
  if (!body || typeof body !== "object" || Array.isArray(body)) throw new InputError("invalid JSON body");
  if (!body.date || !body.time || !body.timeZone) throw new InputError("date, time and timeZone are required");

  let lat = 0, lon = 0, hs = "W";
  if (body.place) {
    lat = toCoordinate(body.place.latitude);
    lon = toCoordinate(body.place.longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) {
      throw new InputError("invalid selected location");
    }
    hs = String(body.houseSystem ?? "W").toUpperCase();
    assertHouseSystem(hs, lat);
  }

  const lt = resolveLocalTime(body.date, body.time, body.timeZone, body.utcOffsetMinutes);
  const x = lt.date;
  const hour = x.getUTCHours() + x.getUTCMinutes() / 60 + x.getUTCSeconds() / 3600 + x.getUTCMilliseconds() / 3600000;
  const jd = p_julday(x.getUTCFullYear(), x.getUTCMonth() + 1, x.getUTCDate(), hour, 1);
  const deltaTSeconds = deltaT(decimalYearOf(x));
  const jdTT = jd + deltaTSeconds / 86400;
  const ay = get_ayanamsha(1, jdTT);

  // calculate_planets() is the wrapper's canonical sidereal path and expects TT.
  const planetsRaw = calculate_planets(jdTT, 1) as any[];
  const basePlanets = planetsRaw.map((p: any) => {
    const longitude = norm(Number(p.longitude));
    return {
      id: Number(p.id), name: p.name, longitude,
      latitude: Number(p.latitude ?? 0), speed: Number(p.speed ?? 0),
      retrograde: Boolean(p.is_retrograde),
      sign: signOf(longitude), navamsa: divisionalSign(longitude, 9),
    };
  });
  const moon = basePlanets.find((p) => p.id === 1);
  if (!moon) throw new Error("Moon position unavailable");
  const nak = nakshatraPada(moon.longitude);

  let houses: any = null;
  let ascLon: number | null = null;
  if (body.place) {
    // Houses use UT. Whole Sign and Equal cusps are derived from the sidereal
    // Ascendant here so they cannot depend on wrapper internals; Placidus
    // comes from the wrapper (rejected above 66.5 deg latitude, where Swiss
    // Ephemeris would silently fall back to another system).
    const h = calculate_houses(jd, lat, lon, hs, 1) as any;
    ascLon = norm(Number(h.ascendant));
    let cuspLongitudes: number[];
    if (hs === "W") cuspLongitudes = wholeSignCusps(ascLon);
    else if (hs === "E") cuspLongitudes = equalCusps(ascLon);
    else {
      cuspLongitudes = Array.from(h.cusps ?? []).slice(0, 12).map((v: any) => norm(Number(v)));
      if (cuspLongitudes.length !== 12) throw new Error("unexpected house cusp count from ephemeris wrapper");
    }
    houses = {
      system: hs,
      ascendant: signOf(ascLon),
      cusps: cuspLongitudes.map((v, i) => ({ house: i + 1, longitude: v, sign: signOf(v) })),
    };
  }

  const planets = basePlanets.map((p) => ({
    ...p,
    wholeSignHouse: ascLon === null ? null : wholeSignHouse(p.longitude, ascLon),
  }));

  const boundary = boundaryWarnings(moon.longitude);
  return {
    ok: true,
    engine: "Swiss Ephemeris",
    swissephVersion: get_swisseph_version(),
    calculationProfile: {
      zodiac: "sidereal",
      ayanamsha: "Lahiri (Chitrapaksha)",
      ayanamshaMode: 1,
      nodeType: "mean",
      houseSystem: houses?.system ?? null,
      ephemeris: "Swiss Ephemeris",
      supportedBirthYearRange: { min: SUPPORTED_MIN_YEAR, max: SUPPORTED_MAX_YEAR },
      supportedDeltaTYearRange: { min: SUPPORTED_MIN_YEAR, max: SUPPORTED_MAX_YEAR },
      timeScales: { planets: "TT", houses: "UT", ayanamsha: "TT", deltaTSeconds },
    },
    ayanamsha: { name: "Lahiri (Chitrapaksha)", mode: 1, degrees: Number(ay) },
    birth: {
      localDate: body.date, localTime: body.time, timeZone: body.timeZone,
      utcOffsetMinutes: lt.offsetMinutes, utc: x.toISOString(), julianDayUT: jd, julianDayTT: jdTT,
    },
    location: body.place
      ? { name: body.place.name ?? null, country: body.place.country ?? null, latitude: lat, longitude: lon }
      : null,
    moon: {
      siderealLongitude: moon.longitude, sign: moon.sign,
      degreeInSign: moon.sign.degreeInSign, degreeInSignDms: moon.sign.degreeInSignDms,
      nakshatra: { name: nak.name, index: nak.index, pada: nak.pada },
      navamsa: moon.navamsa,
    },
    planets,
    houses,
    warnings: [...lt.warnings, ...boundary],
    boundaryWarning: boundary.length ? String(boundary[0].message) : null,
  };
}

async function locations(q: string, req: Request, env?: Env, ctx?: Ctx) {
  const query = q.trim();
  if (query.length < 2 || query.length > 100) return err("location query must be 2–100 characters", req);

  if (env?.LOCATION_LIMITER) {
    const key = req.headers.get("CF-Connecting-IP") ?? "anonymous";
    const { success } = await env.LOCATION_LIMITER.limit({ key });
    if (!success) return err("too many requests", req, 429, { "Retry-After": "60" });
  }

  const cache: any = typeof caches !== "undefined" ? (caches as any).default : null;
  const cacheKey = new Request("https://cache.astrolaab.invalid/location?q=" + encodeURIComponent(query.toLowerCase()));
  if (cache) {
    const hit = await cache.match(cacheKey);
    if (hit) return json(await hit.json(), 200, req);
  }

  const u = new URL("https://photon.komoot.io/api/");
  u.searchParams.set("q", query); u.searchParams.set("limit", "6"); u.searchParams.set("lang", "en");
  let r: Response;
  try {
    r = await fetch(u, {
      headers: { "Accept": "application/json", "User-Agent": "AstroLaab/1.0 (https://astrolaab.com)" },
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    return err("location service timed out", req, 504);
  }
  if (!r.ok) return err("location service unavailable", req, 502);
  const data: any = await r.json();
  const results = (data.features ?? []).map((f: any) => {
    const p = f.properties ?? {}, [lon, lat] = f.geometry?.coordinates ?? [];
    return {
      id: `${p.osm_type ?? "place"}:${p.osm_id ?? `${lat},${lon}`}`,
      name: p.name ?? p.city ?? p.state ?? p.country ?? query,
      city: p.city ?? p.name ?? null, state: p.state ?? null, country: p.country ?? null,
      countryCode: p.countrycode ?? null, latitude: lat, longitude: lon,
      label: [p.name ?? p.city, p.state, p.country].filter(Boolean).join(", "),
    };
  }).filter((x: any) => Number.isFinite(x.latitude) && Number.isFinite(x.longitude));
  const payload = { ok: true, source: "Photon / OpenStreetMap", attribution: "Location data © OpenStreetMap contributors", results };
  if (cache) {
    const put = cache.put(cacheKey, new Response(JSON.stringify(payload), { headers: { "Cache-Control": "public, max-age=86400" } }));
    if (ctx) ctx.waitUntil(put); else await put;
  }
  return json(payload, 200, req);
}

export default {
  async fetch(req: Request, env?: Env, ctx?: Ctx) {
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors(req.headers.get("Origin")) });
    const u = new URL(req.url);
    try {
      if (req.method === "GET" && u.pathname === "/health") {
        return json({ ok: true, service: "astrolaab-moon-sign", engine: "Swiss Ephemeris", swissephVersion: get_swisseph_version(), ayanamsha: "Lahiri (Chitrapaksha)" }, 200, req);
      }
      if (req.method === "GET" && u.pathname === "/location") return await locations(u.searchParams.get("q") ?? "", req, env, ctx);
      if (req.method === "POST" && (u.pathname === "/moon-sign" || u.pathname === "/birth-chart")) {
        const text = await req.text();
        if (text.length > MAX_BODY_BYTES) return err("request body too large", req, 413);
        let body: any;
        try { body = JSON.parse(text); } catch { throw new InputError("invalid JSON body"); }
        return json(calculate(body), 200, req);
      }
      return err("not found", req, 404);
    } catch (e) {
      if (e instanceof InputError) return err(e.message, req, 400);
      console.error(e);
      return err("internal error", req, 500);
    }
  },
};
