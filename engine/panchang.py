import swisseph as swe

from engine.astronomy import ensure_lahiri

SIDEREAL = swe.FLG_SIDEREAL

TITHI_NAMES = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi", "Saptami",
    "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi", "Trayodashi", "Chaturdashi",
]
YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda", "Sukarma",
    "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata", "Harshana", "Vajra",
    "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva", "Siddha", "Sadhya", "Shubha",
    "Shukla", "Brahma", "Indra", "Vaidhriti",
]
REPEATING_KARANAS = ["Bava", "Balava", "Kaulava", "Taitila", "Garaja", "Vanija", "Vishti"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def tithi_name(tithi: int) -> str:
    if tithi == 15:
        return "Purnima"
    if tithi == 30:
        return "Amavasya"
    return TITHI_NAMES[(tithi - 1) % 15]


def karana_name(karana: int) -> str:
    """karana is the 1..60 half-tithi index."""
    if karana == 1:
        return "Kimstughna"
    if karana >= 58:
        return ["Shakuni", "Chatushpada", "Naga"][karana - 58]
    return REPEATING_KARANAS[(karana - 2) % 7]


def calculate_panchang(year, month, day, hour, weekday_index=None):
    """
    Panchang for a UTC instant.

    Yoga needs the SIDEREAL Sun + Moon (the ayanamsha does not cancel in a sum,
    unlike in Tithi/Karana, which use the Moon - Sun difference). Pass
    weekday_index (Monday=0) for the LOCAL civil date; the UTC date is only a
    fallback and is wrong for births that cross midnight in UTC.
    """
    ensure_lahiri()  # thread-local in Swiss Ephemeris; see engine/astronomy.py
    jd = swe.julday(year, month, day, hour)
    sun = swe.calc_ut(jd, swe.SUN, SIDEREAL)[0][0]
    moon = swe.calc_ut(jd, swe.MOON, SIDEREAL)[0][0]

    diff = (moon - sun) % 360.0
    tithi = int(diff / 12.0) + 1
    yoga = int(((sun + moon) % 360.0) / (360.0 / 27.0)) + 1
    karana = int(diff / 6.0) + 1
    if weekday_index is None:
        weekday_index = swe.day_of_week(jd)

    return {
        "tithi": tithi,
        "tithi_name": tithi_name(tithi),
        "paksha": "Shukla" if tithi <= 15 else "Krishna",
        "yoga": yoga,
        "yoga_name": YOGA_NAMES[yoga - 1],
        "karana": karana,
        "karana_name": karana_name(karana),
        "weekday": WEEKDAYS[weekday_index],
    }
