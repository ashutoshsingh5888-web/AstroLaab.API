# -----------------------------------
# NAVAMSA (D9) CALCULATION
# -----------------------------------

from engine.charts import ZODIAC_SIGNS

MOVABLE_SIGNS = [0, 3, 6, 9]     # Aries, Cancer, Libra, Capricorn
FIXED_SIGNS = [1, 4, 7, 10]      # Taurus, Leo, Scorpio, Aquarius
DUAL_SIGNS = [2, 5, 8, 11]       # Gemini, Virgo, Sagittarius, Pisces


def get_navamsa_sign(longitude):
    """
    Returns Navamsa (D9) sign name.
    """

    sign_index = int(longitude // 30)
    degree_in_sign = longitude % 30

    navamsa_part = int(degree_in_sign // (30 / 9))

    if sign_index in MOVABLE_SIGNS:
        start_index = sign_index
    elif sign_index in FIXED_SIGNS:
        start_index = (sign_index + 8) % 12
    else:  # DUAL_SIGNS
        start_index = (sign_index + 4) % 12

    navamsa_sign_index = (start_index + navamsa_part) % 12

    return ZODIAC_SIGNS[navamsa_sign_index]
