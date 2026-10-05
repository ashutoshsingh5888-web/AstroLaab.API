import fs from "node:fs/promises";

const endpoint = process.env.ASTROLAAB_ENDPOINT || "https://astrolaab-moon-sign.ashutoshsingh5888.workers.dev/birth-chart";
const cases = JSON.parse(await fs.readFile(new URL("./validation-cases.json", import.meta.url), "utf8"));
let failures = 0;

for (const c of cases) {
  const res = await fetch(endpoint, {
    method: "POST",
    headers: {"content-type":"application/json"},
    body: JSON.stringify({
      date:c.date, time:c.time, timeZone:c.timeZone, place:c.place,
      houseSystem:"W"
    })
  });
  let body;
  try { body = await res.json(); } catch { body = null; }
  const checks = [
    ["HTTP success", res.ok && body?.ok === true],
    ["engine", body?.engine === "Swiss Ephemeris"],
    ["Lahiri", body?.calculationProfile?.ayanamsha === "Lahiri (Chitrapaksha)"],
    ["Moon", Number.isFinite(body?.moon?.siderealLongitude)],
    ["Moon sign", typeof body?.moon?.sign?.english === "string"],
    ["Nakshatra", Number.isInteger(body?.moon?.nakshatra?.index) && body.moon.nakshatra.index >= 1 && body.moon.nakshatra.index <= 27],
    ["Pada", Number.isInteger(body?.moon?.nakshatra?.pada) && body.moon.nakshatra.pada >= 1 && body.moon.nakshatra.pada <= 4],
    ["D9", typeof body?.moon?.navamsa?.english === "string"],
    ["Planets", Array.isArray(body?.planets) && body.planets.length >= 7],
    ["Houses", Array.isArray(body?.houses?.cusps) && body.houses.cusps.length >= 12],
    ["Ascendant", Number.isFinite(body?.houses?.ascendant?.degreeInSign)]
  ];

  const expected = c.expected || {};
  if (expected.moonSign) checks.push(["golden Moon sign", body?.moon?.sign?.name === expected.moonSign]);
  if (Number.isFinite(expected.moonLongitude)) checks.push(["golden Moon longitude", Math.abs(body.moon.siderealLongitude - expected.moonLongitude) < 1e-7]);

  const bad = checks.filter(([,ok]) => !ok).map(([name]) => name);
  if (bad.length) {
    failures++;
    console.error("FAIL", c.id, bad.join(", "));
    console.error(JSON.stringify(body, null, 2));
  } else {
    console.log("PASS", c.id);
  }
}

if (failures) process.exit(1);
console.log("All validation cases passed.");
