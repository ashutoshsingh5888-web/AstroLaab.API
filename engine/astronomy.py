import swisseph as swe

def ensure_lahiri():
    """Select the Lahiri ayanamsha for the CURRENT thread.

    Swiss Ephemeris keeps the sidereal mode in thread-local storage. Setting it
    once at import only affects the importing thread: FastAPI runs sync routes
    in worker threads that silently fall back to Fagan-Bradley (about 0.88 deg
    off Lahiri). It is cheap, so every calculation sets it itself.
    """
    swe.set_sid_mode(swe.SIDM_LAHIRI)


ensure_lahiri()

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
ZODIAC_SIGNS = SIGNS

BODIES = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
}
# AstroSage and the Worker both use the MEAN node by default.
NODE_IDS = {"mean": swe.MEAN_NODE, "true": swe.TRUE_NODE}
CALC_FLAGS = swe.FLG_SIDEREAL | swe.FLG_SPEED


def normalize_longitude(longitude: float) -> float:
    return longitude % 360.0


def zodiac_from_longitude(longitude: float):
    longitude = normalize_longitude(longitude)
    sign_index = min(11, int(longitude // 30))
    degree = longitude - sign_index * 30.0
    return SIGNS[sign_index], round(degree, 8)


def _entry(longitude_value: float, speed: float):
    sign, degree = zodiac_from_longitude(longitude_value)
    return {
        "sign": sign,
        "degree": degree,
        "longitude": round(longitude_value, 8),
        "speed": round(speed, 8),
        "retrograde": speed < 0,
    }


def calculate_chart(year, month, day, hour, latitude, longitude, node="mean"):
    """
    Calculate a Lahiri sidereal birth chart (Whole Sign houses).

    `hour` is UTC decimal hours; the API layer converts local time first.
    swe.calc_ut takes UT and applies Delta-T internally.
    `node` is "mean" (default, matches AstroSage) or "true".
    """
    if node not in NODE_IDS:
        raise ValueError("node must be 'mean' or 'true'")
    ensure_lahiri()
    jd_ut = swe.julday(year, month, day, hour)

    planets_data = {}
    for name, body_id in BODIES.items():
        position, _flags = swe.calc_ut(jd_ut, body_id, CALC_FLAGS)
        planets_data[name] = _entry(normalize_longitude(float(position[0])), float(position[3]))

    node_position, _flags = swe.calc_ut(jd_ut, NODE_IDS[node], CALC_FLAGS)
    rahu_long = normalize_longitude(float(node_position[0]))
    rahu_speed = float(node_position[3])
    planets_data["Rahu"] = _entry(rahu_long, rahu_speed)
    # Ketu is exactly opposite Rahu and shares its motion.
    planets_data["Ketu"] = _entry(normalize_longitude(rahu_long + 180.0), rahu_speed)

    houses = swe.houses_ex(jd_ut, latitude, longitude, b"W", swe.FLG_SIDEREAL)
    ascendant_longitude = normalize_longitude(float(houses[1][0]))
    asc_sign, asc_degree = zodiac_from_longitude(ascendant_longitude)

    return {
        "Ascendant": {
            "sign": asc_sign,
            "degree": asc_degree,
            "longitude": round(ascendant_longitude, 8),
        },
        "Planets": planets_data,
        "meta": {
            "julianDayUT": jd_ut,
            "ayanamsa": "Lahiri",
            "ayanamsaDegrees": swe.get_ayanamsa_ut(jd_ut),
            "deltaTSeconds": swe.deltat(jd_ut) * 86400.0,
            "node": node,
            "houseSystem": "W",
            "timeScale": "UT",
        },
    }
