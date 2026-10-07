#!/usr/bin/env python3
"""Smoke-check the DEPLOYED Python chart API for the thread-local ayanamsha bug.

Before the fix, requests served by worker threads used Fagan-Bradley instead of
Lahiri, shifting every sidereal longitude by about 0.883 deg. For Mumbai
1990-05-15 14:30 IST the Moon must be 271.8935 (Lahiri); 271.0103 means the bug.

  ASTROLAAB_API_URL=https://<your-render-app>/api/v1/chart ASTROLAAB_API_KEY=... python tests/validate_deployed_api.py
"""
import json, os, sys, urllib.request

URL = os.environ.get("ASTROLAAB_API_URL")
KEY = os.environ.get("ASTROLAAB_API_KEY")
if not URL or not KEY:
    sys.exit("set ASTROLAAB_API_URL and ASTROLAAB_API_KEY")
body = dict(year=1990, month=5, day=15, hour=14, minute=30, latitude=19.076, longitude=72.8777)
req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-api-key": KEY})
j = json.load(urllib.request.urlopen(req, timeout=30))
moon = j["Planets"]["Moon"]["longitude"]
err = abs(moon - 271.893544051776) * 3600
print(f"Moon {moon:.6f}  error vs Lahiri reference {err:.3f} arcsec")
ay = j["meta"].get("ayanamsa_degrees")
if ay is not None:
    print(f"ayanamsa {ay:.4f} (Lahiri 1990 = 23.7225, Fagan-Bradley = 24.6058)")
if err > 0.5:
    print("FAIL: deployed API is not using Lahiri (likely the thread-local sidereal-mode bug)")
    sys.exit(1)
print("PASS")
