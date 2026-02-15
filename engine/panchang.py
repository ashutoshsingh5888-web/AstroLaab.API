import swisseph as swe

def calculate_panchang(year, month, day, hour):
    """
    Basic Panchang calculations.
    """

    jd = swe.julday(year, month, day, hour)

    sun = swe.calc_ut(jd, swe.SUN)[0][0]
    moon = swe.calc_ut(jd, swe.MOON)[0][0]

    # Tithi
    tithi = int(((moon - sun) % 360) / 12) + 1

    # Yoga
    yoga = int(((sun + moon) % 360) / (360 / 27)) + 1

    # Karana (simple formula)
    karana = int(((moon - sun) % 360) / 6) + 1

    weekday = swe.day_of_week(jd)

    weekdays = [
        "Monday", "Tuesday", "Wednesday",
        "Thursday", "Friday", "Saturday", "Sunday"
    ]

    return {
        "tithi": tithi,
        "yoga": yoga,
        "karana": karana,
        "weekday": weekdays[weekday]
    }
