ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def generate_chart_layout(chart_data, chart_style="north"):
    """
    Generates North or South Indian whole-sign house layout.
    """
    asc_sign = chart_data["Ascendant"]["sign"]
    asc_index = ZODIAC_SIGNS.index(asc_sign)

    houses = {}
    for i in range(12):
        house_number = i + 1
        sign_index = (asc_index + i) % 12
        houses[house_number] = {
            "sign": ZODIAC_SIGNS[sign_index],
            "planets": []
        }

    for planet, data in chart_data["Planets"].items():
        planet_sign = data["sign"]
        sign_index = ZODIAC_SIGNS.index(planet_sign)
        house_number = (sign_index - asc_index) % 12 + 1
        houses[house_number]["planets"].append(planet)

    return {
        "chart_style": chart_style,
        "houses": houses
    }
