"""Measured values for each province, for the model's "canada" province profile.

    python3 data/scripts/province_profile.py   # writes data/provinces/profile.json

  taste_z       province mean on the latent scale of the 2019 Canadian Election
                Study item (data/ces_disagreement.json), in units of the
                within-province spread, centred on the population-weighted mean
  emissions     2024 tonnes CO2e per person (ECCC regional table, Statistics
                Canada population), relative to the population-weighted mean
  income        average market income 2015-2024 (table 11-10-0190), relative
                to the population-weighted mean
  population    2024
"""

import csv
import json
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import tiebout.canada as ca  # noqa: E402

AREAS = {"schools": "schools", "environment": "environment", "redistribution": "redistribution", "climate": "climate"}


def main():
    ca.YEARS = [str(y) for y in range(2015, 2025)]
    pop = ca.population()
    p24 = {p: pop[(p, "2024")] for p in ca.PROVINCES}
    tot = sum(p24.values())
    wmean = lambda d: sum(p24[p] * d[p] for p in ca.PROVINCES) / tot
    ces = json.loads((ROOT / "data" / "ces_disagreement.json").read_text())
    taste = {}
    for area, key in AREAS.items():
        m = ces[key]["province_means"]
        c = wmean(m)
        taste[area] = {p: round(m[p] - c, 4) for p in ca.PROVINCES}
    with (ROOT / "data" / "historical" / "ghg_by_province_1990_2005_2024.csv").open() as f:
        per = {r["province"]: float(r["mt_2024"]) * 1e6 / p24[r["province"]] for r in csv.DictReader(f)}
    em = {p: round(per[p] / wmean(per), 4) for p in ca.PROVINCES}
    inc = {}
    for r in ca.rows("11100190.csv"):
        if (r["GEO"] in ca.PROVINCES and r["REF_DATE"] in ca.YEARS
                and r["Economic family type"] == "Economic families and persons not in an economic family"
                and r["Income concept"] == "Average market income"):
            v = ca.value(r)
            if v is not None:
                inc.setdefault(r["GEO"], []).append(v)
    inc = {p: mean(v) for p, v in inc.items()}
    inc = {p: round(inc[p] / wmean(inc), 4) for p in ca.PROVINCES}
    out = {"taste_z": taste, "emissions": em, "income": inc, "population": p24}
    (ROOT / "data" / "provinces" / "profile.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("emissions", "income")}, indent=1))


if __name__ == "__main__":
    main()
