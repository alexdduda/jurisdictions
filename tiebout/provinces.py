"""The "canada" province profile: each region takes its province's measured values.

Without a profile, each region's average taste, abatement cost and
productivity are random draws whose spread is calibrated to Canada. With it,
they are the measured values of the province the region stands for
(data/provinces/profile.json, built by data/scripts/province_profile.py), so
results can name provinces:

  taste       2019 Canadian Election Study province mean, in units of
              within-province spread, times the area's `within` (schools,
              environment, climate; redistribution has no regional taste in
              the model). Transit has no survey item and keeps random draws.
  abatement   2024 emissions per person relative to the mean (climate)
  income      average market income 2015-2024 relative to the mean (the
              region's productivity)

Regions follow tiebout/cities.py REGION_GROUPS: 4 Quebec, 6 Ontario, 2 British
Columbia, 2 Alberta, 1 Manitoba and Saskatchewan, 1 Atlantic. Grouped
provinces are averaged by population, which hides Saskatchewan's emissions
inside Manitoba's. Each multiplier is normalised to mean 1 over the 16 regions.
"""

import json
from functools import lru_cache
from pathlib import Path

from .cities import GROUPS, REGION_GROUPS

DATA = Path(__file__).resolve().parent.parent / "data" / "provinces" / "profile.json"
FULL = {"NL": "Newfoundland and Labrador", "PE": "Prince Edward Island", "NS": "Nova Scotia", "NB": "New Brunswick",
        "QC": "Quebec", "ON": "Ontario", "MB": "Manitoba", "SK": "Saskatchewan", "AB": "Alberta",
        "BC": "British Columbia"}
GROUP_NAMES = {"QC": "Quebec", "ON": "Ontario", "BC": "British Columbia", "AB": "Alberta",
               "PR": "Manitoba and Saskatchewan", "ATL": "Atlantic provinces"}


@lru_cache(maxsize=None)
def profile(name: str = "canada") -> dict:
    if name != "canada":
        raise KeyError(f"unknown province profile {name!r}")
    raw = json.loads(DATA.read_text())
    pop = raw["population"]

    def by_group(values: dict) -> dict:
        out = {}
        for g, provs in GROUPS.items():
            names = [FULL[p] for p in provs]
            out[g] = sum(pop[n] * values[n] for n in names) / sum(pop[n] for n in names)
        return out

    def per_region(values: dict, normalise: bool) -> tuple:
        g = by_group(values)
        r = [g[x] for x in REGION_GROUPS]
        if normalise:
            m = sum(r) / len(r)
            r = [v / m for v in r]
        return tuple(r)

    return {
        "taste_z": {area: per_region(z, False) for area, z in raw["taste_z"].items()},
        "abatement": per_region(raw["emissions"], True),
        "income": per_region(raw["income"], True),
        "names": tuple(GROUP_NAMES[x] for x in REGION_GROUPS),
    }
