import swisseph as swe

swe.set_sid_mode(swe.SIDM_LAHIRI)

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]
ZODIAC_SIGNS = SIGNS

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE,
}

def normalize_longitude(longitude: float) -> float:
    return longitude % 360.0

def zodiac_from_longitude(longitude: float):
    longitude = normalize_longitude(longitude)
    sign_index = min(11, int(longitude // 30))
    degree = longitude - sign_index * 30.0
    return SIGNS[sign_index], round(degree, 8)

def calculate_chart(year, month, day, hour, latitude, longitude):
    """
    Calculate a Lahiri sidereal birth chart.
    The hour argument is UTC decimal hours; the API layer converts local IST.
    """
    swe.set_topo(longitude, latitude, 0)
    jd_ut = swe.julday(year, month, day, hour)

    planets_data = {}
    rahu_long = None

    for name, planet_id in PLANETS.items():
        position, _retflags = swe.calc_ut(jd_ut, planet_id, swe.FLG_SIDEREAL)
        longitude_value = normalize_longitude(float(position[0]))

        if name == "Rahu":
            rahu_long = longitude_value

        sign, degree = zodiac_from_longitude(longitude_value)
        planets_data[name] = {
            "sign": sign,
            "degree": degree,
            "longitude": round(longitude_value, 8),
        }

    if rahu_long is None:
        raise RuntimeError("Rahu position unavailable")

    ketu_long = normalize_longitude(rahu_long + 180.0)
    ketu_sign, ketu_degree = zodiac_from_longitude(ketu_long)
    planets_data["Ketu"] = {
        "sign": ketu_sign,
        "degree": ketu_degree,
        "longitude": round(ketu_long, 8),
    }

    houses = swe.houses_ex(
        jd_ut,
        latitude,
        longitude,
        b"W",
        swe.FLG_SIDEREAL,
    )
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
            "timeScale": "UT",
        },
    }
