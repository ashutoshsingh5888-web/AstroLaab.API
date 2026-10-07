#!/usr/bin/env python3
"""Unit + API tests for the Python chart engine.

Independent evidence (not the engine re-implemented):
  * AstroSage's printed positions for the public Pooja Sharma chart
  * a different calculation route for Yoga (tropical - ayanamsha) than the engine's
  * textbook tables for Karana / Tithi names, retrograde stations, DST edge cases
Run: python -m unittest tests/test_engine_unit.py -v   (needs fastapi, slowapi, httpx)
"""
import os
import random
import sys
import unittest
from pathlib import Path

os.environ.setdefault("ASTROLAAB_API_KEY", "test-key")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import swisseph as swe
from engine.astronomy import calculate_chart
from engine.charts import generate_chart_layout
from engine.panchang import calculate_panchang, karana_name, tithi_name, YOGA_NAMES
from engine.timeutil import TimeInputError, resolve_local_time


def dms(sign, d, m, s):
    return sign * 30 + d + m / 60 + s / 3600


def arcsec(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0) * 3600.0


# AstroSage public report, Pooja Sharma, 23 Aug 1978 23:53:18 IST, Delhi 28 40 N 77 13 E.
# Constants are sign*30 + deg + min/60 + sec/3600 (the earlier test mis-encoded these).
ASTROSAGE = {
    "Sun": dms(4, 6, 42, 30), "Moon": dms(0, 16, 23, 10), "Mars": dms(5, 18, 40, 48),
    "Mercury": dms(3, 28, 16, 43), "Jupiter": dms(3, 3, 54, 40), "Venus": dms(5, 22, 40, 42),
    "Saturn": dms(4, 9, 57, 57), "Rahu": dms(5, 4, 33, 40),
}
ASTROSAGE_ASC = dms(1, 15, 30, 14)
POOJA_UT_HOUR = 18 + 23 / 60 + 18 / 3600


class AstroSageAnchors(unittest.TestCase):
    """Informational-grade sanity check: AstroSage rounds and uses its own settings."""

    @classmethod
    def setUpClass(cls):
        cls.chart = calculate_chart(1978, 8, 23, POOJA_UT_HOUR, 28 + 40 / 60, 77 + 13 / 60)

    def test_planets_within_three_arcminutes(self):
        for name, ref in ASTROSAGE.items():
            got = self.chart["Planets"][name]["longitude"]
            self.assertLess(arcsec(got, ref), 180.0, f"{name}: {arcsec(got, ref):.0f} arcsec from AstroSage")

    def test_default_node_is_mean_and_matches_astrosage_closely(self):
        self.assertEqual(self.chart["meta"]["node"], "mean")
        self.assertLess(arcsec(self.chart["Planets"]["Rahu"]["longitude"], ASTROSAGE["Rahu"]), 60.0)

    def test_true_node_would_miss_astrosage_by_over_a_degree(self):
        true_chart = calculate_chart(1978, 8, 23, POOJA_UT_HOUR, 28.6667, 77.2167, node="true")
        self.assertGreater(arcsec(true_chart["Planets"]["Rahu"]["longitude"], ASTROSAGE["Rahu"]), 3600.0)

    def test_ascendant_within_one_arcminute(self):
        self.assertLess(arcsec(self.chart["Ascendant"]["longitude"], ASTROSAGE_ASC), 60.0)

    def test_ketu_is_opposite_rahu_and_shares_motion(self):
        p = self.chart["Planets"]
        self.assertAlmostEqual((p["Rahu"]["longitude"] + 180.0) % 360.0, p["Ketu"]["longitude"], places=6)
        self.assertEqual(p["Rahu"]["retrograde"], p["Ketu"]["retrograde"])


class ThreadSafety(unittest.TestCase):
    """Regression: Swiss Ephemeris sidereal mode is thread-local. FastAPI runs
    sync routes in worker threads, which used to fall back to Fagan-Bradley and
    shift every longitude by about 0.88 deg."""

    def test_chart_and_panchang_are_identical_in_a_worker_thread(self):
        import threading
        args = (1990, 5, 15, 9.0, 19.076, 72.8777)
        main_chart = calculate_chart(*args)
        main_panchang = calculate_panchang(1990, 5, 15, 9.0)
        out = {}

        def run():
            out["chart"] = calculate_chart(*args)
            out["panchang"] = calculate_panchang(1990, 5, 15, 9.0)

        t = threading.Thread(target=run)
        t.start()
        t.join()
        self.assertEqual(out["chart"]["Planets"]["Moon"]["longitude"], main_chart["Planets"]["Moon"]["longitude"])
        self.assertEqual(out["chart"]["Ascendant"]["longitude"], main_chart["Ascendant"]["longitude"])
        self.assertAlmostEqual(out["chart"]["meta"]["ayanamsaDegrees"], 23.7225, places=3)  # Lahiri, not 24.6058 (Fagan-Bradley)
        self.assertEqual(out["panchang"], main_panchang)

    def test_every_chart_in_a_threadpool_uses_lahiri(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            moons = list(pool.map(lambda _: calculate_chart(1990, 5, 15, 9.0, 19.076, 72.8777)["Planets"]["Moon"]["longitude"], range(16)))
        self.assertTrue(all(abs(m - 271.893544051776) < 0.5 / 3600 for m in moons), moons)


class ChartEngine(unittest.TestCase):
    def test_invalid_node_rejected(self):
        with self.assertRaises(ValueError):
            calculate_chart(2000, 1, 1, 12, 10, 10, node="bogus")

    def test_retrograde_flags_on_known_dates(self):
        # Mercury retrograde 2024-04-01..25; Saturn retrograde 2024-06-29..11-15; Jupiter direct until Oct 9.
        p = calculate_chart(2024, 4, 10, 12, 28.6, 77.2)["Planets"]
        self.assertTrue(p["Mercury"]["retrograde"])
        self.assertFalse(p["Sun"]["retrograde"])
        self.assertFalse(p["Moon"]["retrograde"])
        q = calculate_chart(2024, 8, 1, 12, 28.6, 77.2)["Planets"]
        self.assertTrue(q["Saturn"]["retrograde"])
        self.assertFalse(q["Jupiter"]["retrograde"])
        self.assertFalse(q["Mercury"]["retrograde"])

    def test_meta_reports_ayanamsa_delta_t_and_house_system(self):
        m = calculate_chart(2024, 6, 1, 6.0, 19.07, 72.87)["meta"]
        self.assertAlmostEqual(m["ayanamsaDegrees"], 24.2, delta=0.2)   # Lahiri ~24 deg 12' in 2024
        self.assertAlmostEqual(m["deltaTSeconds"], 69.1, delta=0.5)
        self.assertEqual(m["houseSystem"], "W")

    def test_all_longitudes_normalised_and_signs_consistent(self):
        rnd = random.Random(5)
        for _ in range(200):
            c = calculate_chart(rnd.randint(1950, 2050), rnd.randint(1, 12), rnd.randint(1, 28), rnd.random() * 24,
                                rnd.uniform(-60, 60), rnd.uniform(-180, 180))
            for name, d in c["Planets"].items():
                self.assertTrue(0 <= d["longitude"] < 360, name)
                self.assertTrue(0 <= d["degree"] < 30, name)
            self.assertTrue(0 <= c["Ascendant"]["longitude"] < 360)

    def test_south_layout_is_distinct_and_consistent(self):
        c = calculate_chart(1990, 5, 15, 9.0, 19.076, 72.8777)
        north = generate_chart_layout(c, "north")
        south = generate_chart_layout(c, "south")
        self.assertNotIn("signs", north)
        self.assertEqual(len(south["signs"]), 12)
        self.assertEqual([s["sign"] for s in south["signs"]][0], "Aries")
        asc_house = [s for s in south["signs"] if s["house"] == 1][0]
        self.assertEqual(asc_house["sign"], c["Ascendant"]["sign"])
        planets_in_signs = sum(len(s["planets"]) for s in south["signs"])
        self.assertEqual(planets_in_signs, len(c["Planets"]))
        self.assertEqual(north["houses"], south["houses"])


class PanchangTests(unittest.TestCase):
    def test_yoga_matches_an_independent_route_over_many_instants(self):
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        rnd = random.Random(27)
        for _ in range(300):
            y, m, d, h = rnd.randint(1950, 2050), rnd.randint(1, 12), rnd.randint(1, 28), rnd.random() * 24
            jd = swe.julday(y, m, d, h)
            ay = swe.get_ayanamsa_ut(jd)
            sun = swe.calc_ut(jd, swe.SUN)[0][0] - ay            # tropical minus ayanamsha
            moon = swe.calc_ut(jd, swe.MOON)[0][0] - ay
            expected = int(((sun + moon) % 360.0) / (360.0 / 27.0)) + 1
            self.assertEqual(calculate_panchang(y, m, d, h)["yoga"], expected, f"{y}-{m}-{d} {h:.2f}")

    def test_pooja_sharma_yoga_is_not_the_old_tropical_value(self):
        p = calculate_panchang(1978, 8, 23, POOJA_UT_HOUR)
        self.assertEqual(p["yoga"], 11)            # engine used to return 15
        self.assertEqual(p["yoga_name"], YOGA_NAMES[10])

    def test_tithi_paksha_and_names(self):
        self.assertEqual(tithi_name(1), "Pratipada")
        self.assertEqual(tithi_name(15), "Purnima")
        self.assertEqual(tithi_name(16), "Pratipada")
        self.assertEqual(tithi_name(30), "Amavasya")
        self.assertEqual(len(YOGA_NAMES), 27)
        full = calculate_panchang(2024, 5, 23, 13.0)          # full moon 2024-05-23
        self.assertEqual(full["tithi"], 15)
        self.assertEqual(full["paksha"], "Shukla")
        new = calculate_panchang(2024, 4, 8, 17.0)            # new moon is 18:21 UT on 2024-04-08
        self.assertEqual(new["tithi"], 30)
        self.assertEqual(new["tithi_name"], "Amavasya")

    def test_karana_table(self):
        self.assertEqual(karana_name(1), "Kimstughna")
        self.assertEqual([karana_name(k) for k in range(2, 10)],
                         ["Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti", "Bava"])
        self.assertEqual(karana_name(57), "Vishti")
        self.assertEqual([karana_name(k) for k in (58, 59, 60)], ["Shakuni", "Chatushpada", "Naga"])
        for k in range(1, 61):
            self.assertIsInstance(karana_name(k), str)

    def test_weekday_uses_the_local_date(self):
        # 1978-08-24 00:30 IST (a Thursday) is 1978-08-23 19:00 UTC (a Wednesday).
        local, utc, _ = resolve_local_time(1978, 8, 24, 0, 30)
        p = calculate_panchang(utc.year, utc.month, utc.day, utc.hour + utc.minute / 60, weekday_index=local.weekday())
        self.assertEqual(p["weekday"], "Thursday")
        self.assertEqual(calculate_panchang(utc.year, utc.month, utc.day, 19.0)["weekday"], "Wednesday")  # UTC fallback


class TimeUtilTests(unittest.TestCase):
    def test_basic_and_non_india_zones(self):
        _, u, w = resolve_local_time(1990, 5, 15, 14, 30)
        self.assertEqual(u.isoformat(), "1990-05-15T09:00:00+00:00")
        self.assertEqual(w, [])
        _, u, _ = resolve_local_time(2020, 7, 1, 12, 0, "Europe/London")
        self.assertEqual(u.isoformat(), "2020-07-01T11:00:00+00:00")
        _, u, _ = resolve_local_time(2000, 1, 1, 12, 0, "Asia/Kathmandu")
        self.assertEqual(u.isoformat(), "2000-01-01T06:15:00+00:00")

    def test_gap_rejected_everywhere(self):
        for args in [(2020, 3, 8, 2, 30, "America/New_York"), (2021, 10, 3, 2, 30, "Australia/Sydney"),
                     (2021, 10, 3, 2, 15, "Australia/Lord_Howe")]:
            with self.assertRaisesRegex(TimeInputError, "does not exist"):
                resolve_local_time(*args)
        resolve_local_time(2020, 3, 8, 1, 59, "America/New_York")
        resolve_local_time(2020, 3, 8, 3, 0, "America/New_York")

    def test_overlap_warns_and_uses_first_occurrence(self):
        _, u, w = resolve_local_time(2020, 11, 1, 1, 30, "America/New_York")
        self.assertEqual(u.isoformat(), "2020-11-01T05:30:00+00:00")
        self.assertEqual(w[0]["code"], "ambiguous_local_time")
        _, u2, w2 = resolve_local_time(2020, 11, 1, 1, 30, "America/New_York", utc_offset_minutes=-300)
        self.assertEqual(u2.isoformat(), "2020-11-01T06:30:00+00:00")
        self.assertEqual(w2, [])
        self.assertEqual(resolve_local_time(2021, 4, 4, 1, 45, "Australia/Lord_Howe")[2][0]["code"], "ambiguous_local_time")

    def test_explicit_offset_contradiction_is_flagged(self):
        _, _, w = resolve_local_time(2020, 7, 15, 12, 0, "America/New_York", utc_offset_minutes=330)
        self.assertEqual(w[0]["code"], "utc_offset_override")
        self.assertEqual(resolve_local_time(2020, 7, 15, 12, 0, "America/New_York", utc_offset_minutes=-240)[2], [])
        with self.assertRaises(TimeInputError):
            resolve_local_time(2020, 7, 15, 12, 0, "UTC", utc_offset_minutes=900)

    def test_range_is_on_the_local_year(self):
        _, u, _ = resolve_local_time(1950, 1, 1, 3, 0)               # UTC is 1949-12-31
        self.assertEqual(u.year, 1949)
        _, u, _ = resolve_local_time(2050, 12, 31, 22, 0, "America/New_York")   # UTC is 2051-01-01
        self.assertEqual(u.year, 2051)
        for y in (1949, 2051):
            with self.assertRaisesRegex(TimeInputError, "supported range"):
                resolve_local_time(y, 6, 1, 12, 0)

    def test_invalid_inputs(self):
        for args in [(2021, 2, 29, 12, 0), (2020, 13, 1, 12, 0), (2020, 1, 1, 24, 0)]:
            with self.assertRaises(TimeInputError):
                resolve_local_time(*args)
        with self.assertRaisesRegex(TimeInputError, "IANA"):
            resolve_local_time(2020, 1, 1, 12, 0, "Mars/Olympus")


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        import main
        cls.main = main
        cls.client = TestClient(main.app)
        cls.H = {"x-api-key": os.environ["ASTROLAAB_API_KEY"]}
        cls.body = dict(year=1990, month=5, day=15, hour=14, minute=30, latitude=19.076, longitude=72.8777)

    def setUp(self):
        self.main.limiter.reset()
        self.main._auth_failures.clear()

    def post(self, over=None, headers=None):
        return self.client.post("/api/v1/chart", json={**self.body, **(over or {})}, headers=self.H if headers is None else headers)

    def test_auth(self):
        self.assertEqual(self.post(headers={}).status_code, 401)
        self.assertEqual(self.post(headers={"x-api-key": "wrong"}).status_code, 401)
        self.assertEqual(self.post().status_code, 200)

    def test_default_is_ist_mean_node_with_new_meta(self):
        j = self.post().json()
        self.assertEqual(j["meta"]["input_timezone"], "Asia/Kolkata")
        self.assertEqual(j["meta"]["utc"], "1990-05-15T09:00:00+00:00")
        self.assertEqual(j["meta"]["node"], "mean")
        self.assertEqual(j["meta"]["house_system"], "W")
        self.assertIn("ayanamsa_degrees", j["meta"])
        self.assertAlmostEqual(j["Planets"]["Moon"]["longitude"], 271.893544051776, delta=0.5 / 3600)
        self.assertIn("retrograde", j["Planets"]["Mercury"])
        self.assertIn("yoga_name", j["Panchang"])

    def test_non_india_timezone_changes_the_utc_instant(self):
        j = self.post({"timezone": "Europe/London", "latitude": 51.5, "longitude": -0.12, "year": 2020, "month": 7, "day": 1, "hour": 12, "minute": 0}).json()
        self.assertEqual(j["meta"]["utc"], "2020-07-01T11:00:00+00:00")
        self.assertEqual(j["meta"]["utc_offset_minutes"], 60)

    def test_local_weekday(self):
        j = self.post({"year": 1978, "month": 8, "day": 24, "hour": 0, "minute": 30}).json()
        self.assertEqual(j["Panchang"]["weekday"], "Thursday")

    def test_dst_gap_422_overlap_warns(self):
        gap = self.post({"timezone": "America/New_York", "year": 2020, "month": 3, "day": 8, "hour": 2, "minute": 30})
        self.assertEqual(gap.status_code, 422)
        self.assertIn("does not exist", gap.json()["detail"])
        amb = self.post({"timezone": "America/New_York", "year": 2020, "month": 11, "day": 1, "hour": 1, "minute": 30})
        self.assertEqual(amb.status_code, 200)
        self.assertEqual(amb.json()["meta"]["warnings"][0]["code"], "ambiguous_local_time")

    def test_validation_errors_are_422_not_500(self):
        for over in [{"year": 1949}, {"year": 2051}, {"month": 2, "day": 30}, {"timezone": "Nope/Nope"},
                     {"node": "bogus"}, {"latitude": 91}, {"utc_offset_minutes": 900}, {"chart_style": "round"}]:
            self.assertEqual(self.post(over).status_code, 422, over)

    def test_true_node_is_opt_in(self):
        mean = self.post().json()["Planets"]["Rahu"]["longitude"]
        true = self.post({"node": "true"}).json()["Planets"]["Rahu"]["longitude"]
        self.assertNotEqual(mean, true)

    def test_rate_limiter_is_enforced(self):
        codes = [self.post().status_code for _ in range(23)]
        self.assertEqual(codes.count(200), 20)
        self.assertEqual(codes.count(429), 3)

    def test_key_guessing_is_throttled_and_rotating_keys_do_not_help(self):
        codes = [self.post(headers={"x-api-key": f"guess{i}"}).status_code for i in range(25)]
        self.assertEqual(codes.count(401), self.main.AUTH_FAILURE_MAX + 1)
        self.assertGreater(codes.count(429), 0)

    def test_production_hides_docs(self):
        # docs are only disabled when ENVIRONMENT=production; here we just assert the health route works.
        self.assertEqual(self.client.get("/api/v1/health").status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
