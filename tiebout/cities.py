"""City profiles: the census metropolitan areas inside each modelled region.

Each of the 16 regions stands for a slice of one province (or group of
provinces) and contains that province's metropolitan areas in proportion to
their population, plus the population living outside any metropolitan area
("countryside"). How much a place wants transit is read from how much its
workers already use it: the share commuting by public transit in the 2016
Census, the last census before the pandemic changed commuting.

Sources (data/cities/cma_2016.csv, all read directly from the pages):
  * Population, 2016 Census: Statistics Canada, The Daily, 8 February 2017,
    Tables 2 and 3 (98-402-X2016001). Ottawa-Gatineau split by province:
    City of Ottawa, 2016 Census population and dwelling counts (991,726 and
    332,057, summing to the Statistics Canada total of 1,323,783).
  * Transit share of commuters, 2016 Census: Statistics Canada, The Daily,
    29 November 2017, Table 1 (every CMA, Ottawa-Gatineau split by province).

Outside the metropolitan areas no published 2016 figure was found; it is
implied from the national share (12.4%) less the metropolitan areas, weighting
by population rather than workers: 3.0%.

A place's taste offset is linear in transit share and scaled so that the
countryside sits at -urban_premium/2 and the average metropolitan resident at
+urban_premium/2. That is exactly the city/countryside gap of the two-place
model, so the urban premium keeps its calibrated meaning; what this adds is the
spread between metropolitan areas (Toronto 24.3% against St. Catharines-Niagara
2.7%).
"""

import csv
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "cities" / "cma_2016.csv"

# 2016 Census populations (The Daily, 8 February 2017, Table 2).
PROVINCE_POP = {
    "NL": 519_716, "PE": 142_907, "NS": 923_598, "NB": 747_101, "QC": 8_164_361,
    "ON": 13_448_494, "MB": 1_278_365, "SK": 1_098_352, "AB": 4_067_175, "BC": 4_648_055,
}
CANADA_POP = 35_151_728
# 2011 to 2016 growth, % (same table): used only for trend projections.
PROVINCE_GROWTH = {
    "NL": 1.0, "PE": 1.9, "NS": 0.2, "NB": -0.5, "QC": 3.3,
    "ON": 4.6, "MB": 5.8, "SK": 6.3, "AB": 11.6, "BC": 5.6,
}
NATIONAL_TRANSIT = 12.4

# Which province (group) each region stands for. Regions 0, 7, 11 are Quebec,
# 1, 3, 6, 9, 12, 14 Ontario and 4 New Brunswick in the official-language
# profile; the city profile follows that, makes region 4 the Atlantic
# provinces, and gives the six remaining regions to the West (2 BC, 2 AB, 1
# Manitoba and Saskatchewan) and, for one, Quebec's city structure, the
# province most under-weighted by 3 of 16 regions (23.2% of Canadians).
# Population shares: QC 4/16 = 25% (23.2%), ON 37.5% (38.3%), BC 12.5% (13.2%),
# AB 12.5% (11.6%), MB+SK 6.25% (6.8%), Atlantic 6.25% (6.6%).
REGION_GROUPS = ("QC", "ON", "BC", "ON", "ATL", "AB", "ON", "QC",
                 "BC", "ON", "AB", "QC", "ON", "PR", "ON", "QC")
GROUPS = {"QC": ("QC",), "ON": ("ON",), "BC": ("BC",), "AB": ("AB",),
          "PR": ("MB", "SK"), "ATL": ("NL", "PE", "NS", "NB")}

# A metropolitan area gets its own place if it holds at least this share of
# its group's population (with 100 agents per region, about 4 agents).
# Smaller ones are pooled with others of similar transit use.
MIN_SHARE = 0.04


def _rows(overrides: dict | None = None, year: int = 2016):
    """Metro areas. With a later `year`, each area's population is projected by
    continuing its 2011-2016 growth relative to its province's, so its share of
    the province follows the trend; province totals are kept at 2016 (only
    shares within a province enter the model). Transit shares stay at 2016."""
    periods = (year - 2016) / 5
    with DATA.open() as f:
        rows = [
            {"cma": r["cma"], "province": r["province"],
             "pop": int(r["population_2016"]) * ((1 + float(r["growth_2011_2016"]) / 100)
                                                 / (1 + PROVINCE_GROWTH[r["province"]] / 100)) ** periods,
             "transit": float(r["transit_share_2016"])}
            for r in csv.DictReader(f)
        ]
    for r in rows:
        if overrides and r["cma"] in overrides:
            r["transit"] = overrides[r["cma"]]
    return rows


def rural_transit(rows=None) -> float:
    """Implied from 2016 national and metropolitan figures (always the baseline data)."""
    rows = rows or _rows()
    cma_pop = sum(r["pop"] for r in rows)
    return (NATIONAL_TRANSIT * CANADA_POP - sum(r["pop"] * r["transit"] for r in rows)) / (CANADA_POP - cma_pop)


def _pool(rows):
    pop = sum(r["pop"] for r in rows)
    return {"cma": " + ".join(r["cma"] for r in rows), "pop": pop,
            "transit": sum(r["pop"] * r["transit"] for r in rows) / pop}


def group_places(group: str, rows=None) -> list[dict]:
    """Places of one region: (name, population share, transit share), largest first, countryside last."""
    rows = rows or _rows()
    provinces = GROUPS[group]
    total = sum(PROVINCE_POP[p] for p in provinces)
    cmas = sorted((r for r in rows if r["province"] in provinces), key=lambda r: -r["pop"])
    big = [r for r in cmas if r["pop"] / total >= MIN_SHARE]
    small = sorted((r for r in cmas if r["pop"] / total < MIN_SHARE), key=lambda r: -r["transit"])
    # Pool small metro areas in order of transit share until each pool reaches MIN_SHARE.
    pools, cur = [], []
    for r in small:
        cur.append(r)
        if sum(x["pop"] for x in cur) / total >= MIN_SHARE:
            pools.append(cur)
            cur = []
    if cur:
        if pools:
            pools[-1].extend(cur)
        else:
            pools.append(cur)
    places = big + [_pool(p) for p in pools]
    places.sort(key=lambda r: -r["pop"])
    out = [{"name": r["cma"], "share": r["pop"] / total, "transit": r["transit"]} for r in places]
    out.append({"name": "outside metropolitan areas", "share": 1 - sum(p["share"] for p in out),
                "transit": rural_transit()})
    return out


def offsets(places: list[dict], rows=None) -> list[tuple[float, float]]:
    """(population share, taste offset per unit of urban premium) for each place."""
    # The scale is always the 2016 baseline, so overriding some areas' shares
    # moves those areas only (and can shrink the average city-countryside gap).
    base = _rows()
    m_rural = rural_transit(base)
    m_cma = sum(r["pop"] * r["transit"] for r in base) / sum(r["pop"] for r in base)
    return [(p["share"], (p["transit"] - m_rural) / (m_cma - m_rural) - 0.5) for p in places]


def canada_profile(overrides: dict | None = None, spread: float = 1.0, year: int = 2016) -> tuple:
    """The 16 regions' places. `overrides` replaces some areas' transit shares;
    `spread` scales the gap between metropolitan areas around their average
    (0 makes every metropolitan area alike, as in the two-place model)."""
    rows = _rows(overrides, year)
    by_group = {}
    for g in GROUPS:
        offs = offsets(group_places(g, rows), rows)
        by_group[g] = tuple(offs[:-1] and [(sh, 0.5 + spread * (o - 0.5)) for sh, o in offs[:-1]]) + (offs[-1],)
    return tuple(by_group[g] for g in REGION_GROUPS)


# Sensitivity scenarios for how commuting has changed since 2016 (validation/city_sensitivity.py).
# May 2023 transit shares for the three largest areas are from the Labour Force
# Survey (Statistics Canada release of 22 August 2023, as reported; see
# VERIFICATION.md): a different survey from the census, so an illustration of
# post-pandemic change, not a like-for-like update.
LFS_2023 = {"Toronto": 20.6, "Montreal": 16.4, "Vancouver": 22.5}


def summary() -> dict:
    rows = _rows()
    out = {"rural_transit": round(rural_transit(rows), 2),
           "cma_share_of_population": round(sum(r["pop"] for r in rows) / CANADA_POP, 4),
           "cmas": len(rows), "groups": {}}
    for g in GROUPS:
        out["groups"][g] = [
            {"place": p["name"], "share": round(p["share"], 3), "transit": round(p["transit"], 1),
             "offset": round(o, 3)}
            for p, (_, o) in zip(group_places(g, rows), offsets(group_places(g, rows), rows))
        ]
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(summary(), indent=1))


CITY_PROFILES = {
    "canada": canada_profile,
    "canada_2023_big3": lambda: canada_profile(overrides=LFS_2023),
    "canada_half_spread": lambda: canada_profile(spread=0.5),
    "canada_2041_trend": lambda: canada_profile(year=2041),
}
