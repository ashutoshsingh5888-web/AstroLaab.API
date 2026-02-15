from datetime import timedelta

DASHA_SEQUENCE = [
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17),
]

NAKSHATRA_LORDS = [
    "Ketu", "Venus", "Sun", "Moon", "Mars",
    "Rahu", "Jupiter", "Saturn", "Mercury"
] * 3  # 27 Nakshatras


def calculate_vimshottari_dasha(moon_longitude, birth_date):
    """
    Calculates Mahadasha timeline.
    Returns timeline + current running dasha.
    """

    nakshatra_size = 360 / 27
    nakshatra_index = int(moon_longitude // nakshatra_size)

    starting_lord = NAKSHATRA_LORDS[nakshatra_index]

    # Find where this lord is in dasha sequence
    start_index = next(
        i for i, d in enumerate(DASHA_SEQUENCE) if d[0] == starting_lord
    )

    timeline = []
    current_date = birth_date

    # Remaining portion of first dasha
    degrees_into_nakshatra = moon_longitude % nakshatra_size
    remaining_fraction = 1 - (degrees_into_nakshatra / nakshatra_size)

    first_dasha_years = DASHA_SEQUENCE[start_index][1]
    remaining_years = first_dasha_years * remaining_fraction

    end_date = current_date + timedelta(days=remaining_years * 365.25)

    timeline.append({
        "planet": starting_lord,
        "start": str(current_date.date()),
        "end": str(end_date.date())
    })

    current_date = end_date

    # Remaining 8 dashas
    for i in range(1, 9):
        idx = (start_index + i) % 9
        planet, years = DASHA_SEQUENCE[idx]

        end_date = current_date + timedelta(days=years * 365.25)

        timeline.append({
            "planet": planet,
            "start": str(current_date.date()),
            "end": str(end_date.date())
        })

        current_date = end_date

    # Find current running dasha
    today = birth_date
    current_running = timeline[0]["planet"]

    for period in timeline:
        if str(today.date()) >= period["start"] and str(today.date()) <= period["end"]:
            current_running = period["planet"]
            break

    return {
        "timeline": timeline,
        "current": current_running
    }
