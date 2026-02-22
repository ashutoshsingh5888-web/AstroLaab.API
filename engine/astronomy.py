import swisseph as swe

# ----------------------------------------------------
# Swiss Ephemeris Configuration
# ----------------------------------------------------

# Use Lahiri Ayanamsa (SIDEREAL)
swe.set_sid_mode(swe.SIDM_LAHIRI)

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

PLANETS = {
    "Sun": swe.SUN,
    "Moon": swe.MOON,
    "Mars": swe.MARS,
    "Mercury": swe.MERCURY,
    "Jupiter": swe.JUPITER,
    "Venus": swe.VENUS,
    "Saturn": swe.SATURN,
    "Rahu": swe.TRUE_NODE
}

# ----------------------------------------------------
# Helpers
# ----------------------------------------------------

def zodiac_from_longitude(longitude):
    sign_index = int(longitude // 30)
    degree = longitude % 30
    return SIGNS[sign_index], round(degree, 2)

# ----------------------------------------------------
# Main Chart Calculator
# ----------------------------------------------------

def calculate_chart(year, month, day, hour, latitude, longitude):
    """
    Main astrology engine function.
    All calculations are SIDEREAL (Lahiri).
    """

    # Set observer location
    swe.set_topo(longitude, latitude, 0)

    # Julian Day (UT)
    jd = swe.julday(year, month, day, hour)

    planets_data = {}

    # -----------------------------
    # Planetary Positions (Sidereal)
    # -----------------------------
    for name, planet_id in PLANETS.items():
        position = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL)
        longitude_value = position[0][0]

        # Store Rahu for Ketu calculation
        if name == "Rahu":
            rahu_long = longitude_value
            ketu_long = (rahu_long + 180) % 360

        sign, degree = zodiac_from_longitude(longitude_value)

        planets_data[name] = {
            "sign": sign,
            "degree": degree,
            "longitude": round(longitude_value, 4)
        }

    # -----------------------------
    # Ketu (Opposite Rahu)
    # -----------------------------
    ketu_sign, ketu_degree = zodiac_from_longitude(ketu_long)
    planets_data["Ketu"] = {
        "sign": ketu_sign,
        "degree": ketu_degree,
        "longitude": round(ketu_long, 4)
    }

    # -----------------------------
    # Ascendant (SIDEREAL — FINAL FIX)
houses = swe.houses_ex(
    jd,
    swe.FLG_SIDEREAL,
    latitude,
    longitude
)

ascendant_longitude = houses[1][0]   # <-- THIS IS ASC
asc_sign, asc_degree = zodiac_from_longitude(ascendant_longitude)

    return {
        "Ascendant": {
            "sign": asc_sign,
            "degree": asc_degree,
            "longitude": round(ascendant_longitude, 4)
        },
        "Planets": planets_data
    }