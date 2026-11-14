"""Real geographies: regions sized by population, neighbours by shared borders.

By default the model has grid x grid equal regions on a torus, an abstract
stand-in for a federation. With World.geography set, regions are real
provinces or states: each starts with agents in proportion to its population
(at least MIN_AGENTS, so small ones still have a median voter), and spillovers
reach the regions it borders. Agents in small regions that had to be rounded up
carry a weight below 1 in welfare (and big regions' agents above 1), so welfare
is still population-weighted.

  provinces   the ten provinces, 2024 population (Statistics Canada 17-10-0009,
              as in data/provinces/profile.json). Neighbours share a land border,
              plus Prince Edward Island with New Brunswick (Confederation Bridge)
              and Nova Scotia, and Newfoundland and Labrador with Nova Scotia
              (ferry).
  us_states   the 50 states, 2024 population (BEA SAINC4). Neighbours share a
              land border; Alaska is linked to Washington and Hawaii to
              California so every state has one.
"""

from functools import lru_cache

MIN_AGENTS = 10

PROVINCES = ("NL", "PE", "NS", "NB", "QC", "ON", "MB", "SK", "AB", "BC")
PROVINCE_POP = {"NL": 545_080, "PE": 178_869, "NS": 1_080_310, "NB": 857_114, "QC": 8_982_312,
                "ON": 16_090_358, "MB": 1_487_953, "SK": 1_245_196, "AB": 4_901_795, "BC": 5_659_205}
PROVINCE_BORDERS = {"NL": ("QC", "NS"), "PE": ("NB", "NS"), "NS": ("NB", "PE", "NL"), "NB": ("QC", "NS", "PE"),
                    "QC": ("ON", "NB", "NL"), "ON": ("QC", "MB"), "MB": ("ON", "SK"), "SK": ("MB", "AB"),
                    "AB": ("SK", "BC"), "BC": ("AB",)}

STATE_POP = {
    "AL": 5_163_055, "AK": 736_537, "AZ": 7_556_424, "AR": 3_096_080, "CA": 39_364_774, "CO": 5_988_502,
    "CT": 3_674_449, "DE": 1_050_123, "FL": 23_265_838, "GA": 11_204_208, "HI": 1_434_952, "ID": 2_000_872,
    "IL": 12_703_033, "IN": 6_934_754, "IA": 3_230_454, "KS": 2_965_252, "KY": 4_584_046, "LA": 4_614_878,
    "ME": 1_408_438, "MD": 6_245_314, "MA": 7_138_560, "MI": 10_099_962, "MN": 5_797_405, "MS": 2_950_172,
    "MO": 6_243_544, "MT": 1_137_557, "NE": 2_005_591, "NV": 3_253_543, "NH": 1_408_518, "NJ": 9_506_354,
    "NM": 2_126_774, "NY": 20_001_419, "NC": 11_052_061, "ND": 793_387, "OH": 11_860_621, "OK": 4_097_758,
    "OR": 4_265_324, "PA": 13_045_848, "RI": 1_110_415, "SC": 5_490_316, "SD": 927_110, "TN": 7_251_291,
    "TX": 31_318_578, "UT": 3_502_983, "VT": 646_521, "VA": 8_819_642, "WA": 7_927_958, "WV": 1_767_402,
    "WI": 5_957_168, "WY": 586_722,
}
STATE_BORDERS = {
    "AL": "FL GA MS TN", "AK": "WA", "AZ": "CA CO NV NM UT", "AR": "LA MS MO OK TN TX", "CA": "AZ NV OR HI",
    "CO": "AZ KS NE NM OK UT WY", "CT": "MA NY RI", "DE": "MD NJ PA", "FL": "AL GA", "GA": "AL FL NC SC TN",
    "HI": "CA", "ID": "MT NV OR UT WA WY", "IL": "IN IA KY MO WI", "IN": "IL KY MI OH",
    "IA": "IL MN MO NE SD WI", "KS": "CO MO NE OK", "KY": "IL IN MO OH TN VA WV", "LA": "AR MS TX",
    "ME": "NH", "MD": "DE PA VA WV", "MA": "CT NH NY RI VT", "MI": "IN OH WI", "MN": "IA ND SD WI",
    "MS": "AL AR LA TN", "MO": "AR IL IA KS KY NE OK TN", "MT": "ID ND SD WY", "NE": "CO IA KS MO SD WY",
    "NV": "AZ CA ID OR UT", "NH": "ME MA VT", "NJ": "DE NY PA", "NM": "AZ CO OK TX", "NY": "CT MA NJ PA VT",
    "NC": "GA SC TN VA", "ND": "MN MT SD", "OH": "IN KY MI PA WV", "OK": "AR CO KS MO NM TX",
    "OR": "CA ID NV WA", "PA": "DE MD NJ NY OH WV", "RI": "CT MA", "SC": "GA NC", "SD": "IA MN MT NE ND WY",
    "TN": "AL AR GA KY MS MO NC VA", "TX": "AR LA NM OK", "UT": "AZ CO ID NV WY", "VT": "MA NH NY",
    "VA": "KY MD NC TN WV", "WA": "ID OR AK", "WV": "KY MD OH PA VA", "WI": "IL IA MI MN",
    "WY": "CO ID MT NE SD UT",
}

# Australia's six states, June 2025 estimated resident population (ABS 3101.0
# table 4). Neighbours share a land border, plus Tasmania with Victoria (Bass Strait).
AU_STATES = ("NSW", "VIC", "QLD", "SA", "WA", "TAS")
AU_POP = {"NSW": 8_587_369, "VIC": 7_064_041, "QLD": 5_670_203, "SA": 1_901_652, "WA": 3_044_966, "TAS": 577_827}
AU_BORDERS = {"NSW": ("VIC", "QLD", "SA"), "VIC": ("NSW", "SA", "TAS"), "QLD": ("NSW", "SA"),
              "SA": ("NSW", "VIC", "QLD", "WA"), "WA": ("SA",), "TAS": ("VIC",)}

GEOGRAPHIES = {
    "au_states": (AU_STATES, AU_POP, AU_BORDERS),
    "provinces": (PROVINCES, PROVINCE_POP, PROVINCE_BORDERS),
    "us_states": (tuple(STATE_POP), STATE_POP, {k: tuple(v.split()) for k, v in STATE_BORDERS.items()}),
}


@lru_cache(maxsize=None)
def layout(name: str, total: int) -> tuple:
    """(region codes, agents per region, neighbour indices, population shares)."""
    codes, pop, borders = GEOGRAPHIES[name]
    tot = sum(pop[c] for c in codes)
    shares = [pop[c] / tot for c in codes]
    # Largest remainder, after giving every region its minimum.
    ideal = [s * total for s in shares]
    counts = [max(MIN_AGENTS, int(x)) for x in ideal]
    left = total - sum(counts)
    order = sorted(range(len(codes)), key=lambda i: -(ideal[i] - int(ideal[i])))
    k = 0
    while left > 0:
        i = order[k % len(order)]
        if ideal[i] >= MIN_AGENTS:
            counts[i] += 1
            left -= 1
        k += 1
    index = {c: i for i, c in enumerate(codes)}
    nbrs = tuple(tuple(index[b] for b in borders[c]) for c in codes)
    return tuple(codes), tuple(counts), nbrs, tuple(shares)


# Official-language minority (French as first official language spoken, 2021
# Census) for the provinces, as in model.LANGUAGE_PROFILES: Quebec 82.2%, New
# Brunswick 30.0%, Ontario 3.4%, the rest about 2.5%.
LANGUAGE = {
    "provinces": {"QC": 0.822, "NB": 0.300, "ON": 0.034, "NL": 0.025, "PE": 0.025, "NS": 0.025,
                  "MB": 0.025, "SK": 0.025, "AB": 0.025, "BC": 0.025},
    "us_states": {},
    "au_states": {},
}
