ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def generate_chart_layout(chart_data, chart_style="north"):
    """
    Whole-sign house layout.

    `houses` (house number -> sign + planets) is returned for both styles.
    For the South Indian style the signs are fixed on the page, so an extra
    `signs` list is returned in zodiac order with the house each sign holds.
    """
    asc_index = ZODIAC_SIGNS.index(chart_data["Ascendant"]["sign"])

    houses = {}
    for i in range(12):
        houses[i + 1] = {"sign": ZODIAC_SIGNS[(asc_index + i) % 12], "planets": []}

    for planet, data in chart_data["Planets"].items():
        house_number = (ZODIAC_SIGNS.index(data["sign"]) - asc_index) % 12 + 1
        houses[house_number]["planets"].append(planet)

    layout = {"chart_style": chart_style, "houses": houses}
    if chart_style == "south":
        layout["ascendant_sign"] = ZODIAC_SIGNS[asc_index]
        layout["signs"] = [
            {
                "sign": sign,
                "house": (i - asc_index) % 12 + 1,
                "planets": list(houses[(i - asc_index) % 12 + 1]["planets"]),
            }
            for i, sign in enumerate(ZODIAC_SIGNS)
        ]
    return layout
