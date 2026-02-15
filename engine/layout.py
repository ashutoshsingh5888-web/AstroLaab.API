# -----------------------------------
# CHART LAYOUT ENGINE
# -----------------------------------

def build_house_map(planets_data, ascendant_longitude):
    """
    Builds house-wise mapping using Whole Sign logic.
    planets_data = {planet: longitude}
    """
    houses = {i: {"planets": []} for i in range(1, 13)}

    asc_sign = int(ascendant_longitude // 30)

    for planet, data in planets_data.items():
        longitude = data["longitude"]
        planet_sign = int(longitude // 30)
        house = (planet_sign - asc_sign) % 12 + 1
        houses[house]["planets"].append(planet)

    return houses


# -----------------------------------
# NORTH INDIAN FORMAT
# -----------------------------------

def format_north_chart(houses):
    """
    North Indian chart: fixed houses.
    """
    return {
        "chart_style": "north",
        "houses": houses
    }


# -----------------------------------
# SOUTH INDIAN FORMAT
# -----------------------------------

def format_south_chart(houses):
    """
    South Indian chart: fixed zodiac signs.
    """
    return {
        "chart_style": "south",
        "houses": houses
    }
