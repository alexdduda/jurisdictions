"""Backtest: give the model only the data that existed before a reform.

For each of three reform dates, every measured input is recomputed from the
ten years before it, the uncertainty analysis is rerun with those inputs (same
sampled worlds, same seeds, so only the data differ), and the verdict is set
next to what Canada actually did:

  1996  The Canada Health and Social Transfer replaces the Canada Assistance
        Plan: Ottawa stops matching provincial welfare spending dollar for
        dollar and pays a block grant instead (redistribution moves down).
  2006  Ontario creates the Greater Toronto Transportation Authority (Metrolinx)
        over the municipal transit systems of the Toronto and Hamilton area
        (transit moves up, from cities to a provincial body).
  2016  The Pan-Canadian Framework sets a national minimum carbon price that
        provinces may meet with their own systems, backed by a federal charge
        from 2019 (climate moves up, as a price floor).

A model that says what *should* happen is not proven right because governments
did it, or wrong because they didn't; governments decide for many reasons. So
the backtest asks three narrower questions:

  1. Stability: with only the data of the time, does the model reach the
     verdict it reaches today?
  2. Direction: does that verdict point the way Canada moved?
  3. Where they disagree, what happened afterwards, in data the model never saw?

Inputs that could not be dated (no older source on hand) are held at today's
values and listed in the output: the survey measure of disagreement within
provinces (2019 Canadian Election Study), the carbon-tax opinion data (2019),
and the 2016 Census city map. Spending by function before 2008 comes from an
older Statistics Canada classification (FMS, table 10-10-0039); the two are
compared on their one overlapping year and the range is widened to cover both.

    python3 data/scripts/fetch_fms_1989_2009.py   # once
    python3 validation/backtest.py                # writes validation/backtest.json
"""

import csv
import json
import math
import random
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))
import migration_and_capacity as mc  # noqa: E402
import tiebout.canada as ca  # noqa: E402
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import analyse_domain, canada_ranges  # noqa: E402

OUT = ROOT / "validation" / "backtest.json"
FMS = ROOT / "data" / "historical" / "fms_1989_2009.csv"
GHG = ROOT / "data" / "historical" / "ghg_by_province_1990_2005_2024.csv"

# Old (FMS) items standing in for the CCOFOG functions used today.
FMS_ITEMS = {
    "Primary and secondary education [7092]": "Elementary and secondary education",
    "Environmental protection [705]": "Environment",
    "Transport [7045]": "Transportation and communication",
    "Social protection [710]": "Social services",
}
TOTAL = "Total expenditures"

VINTAGES = {
    1996: {"spending": "fms", "spend_years": range(1988, 1996), "years": range(1986, 1996),
           "emissions_year": "1990",
           "domains": ("schools", "environment", "transit", "redistribution")},
    2006: {"spending": "fms", "spend_years": range(1996, 2006), "years": range(1996, 2006),
           "emissions_year": "2005",
           "domains": ("schools", "environment", "transit", "redistribution")},
    2016: {"spending": "ccofog", "spend_years": range(2008, 2016), "years": range(2006, 2016),
           "emissions_year": "2005",
           "domains": ("schools", "environment", "transit", "redistribution", "climate")},
}

REFORMS = [
    {
        "year": 1996, "area": "redistribution",
        "what": "Canada Health and Social Transfer replaces the Canada Assistance Plan's 50-50 cost sharing of provincial welfare with a block grant",
        "direction": "down (national matching to provincial choice)",
        "verdict": "No: the model says national, in 98% of worlds",
    },
    {
        "year": 2006, "area": "transit",
        "what": "Ontario creates the Greater Toronto Transportation Authority (Metrolinx from 2007) over municipal transit in the Toronto and Hamilton area",
        "direction": "up (cities to a provincial body)",
        "verdict": "Yes in direction: with the data of the time, cities deciding alone does worse than provinces deciding, and the best fixed rule is provinces with a small national floor (no clear winner: it keeps 2% of the attainable gain)",
    },
    {
        "year": 2016, "area": "climate",
        "what": "Pan-Canadian Framework: a national minimum carbon price provinces may meet with their own systems; federal backstop from 2019",
        "direction": "up (provincial choice to a national price floor)",
        "verdict": "Yes: a carbon price, in 99% of worlds; a floor provinces may exceed does almost as well. It did not foresee the 2025 repeal of the consumer charge",
    },
]
NOT_DATED = [
    "within-province disagreement (2019 Canadian Election Study)",
    "carbon-tax opinion and its link to emissions (2019 Canadian Election Study)",
    "city map for transit (2016 Census)",
    "cost of public funds, spillovers, scale economies (never measured; same ranges as today)",
]


def fms_spending() -> dict:
    """(province, fiscal year start, CCOFOG function name or TOTAL) -> dollars."""
    old_to_new = {v: k for k, v in FMS_ITEMS.items()}
    out = {}
    with FMS.open() as f:
        for r in csv.DictReader(f):
            year = str(int(r["fiscal_year_end"][:4]) - 1)  # FY ending March 1996 is 1995-96
            key = old_to_new.get(r["item"], TOTAL if r["item"] == TOTAL else None)
            if key:
                out[(r["province"], year, key)] = float(r["dollars_millions"]) * 1e6
    return out


def with_years(years):
    ys = [str(y) for y in years]
    ca.YEARS = ys
    mc.YEARS = ys


def measure(spend_years, years, spending: str) -> dict:
    """The measured calibration inputs, from the given years only."""
    with_years(range(min(min(spend_years), min(years)) - 1, max(max(spend_years), max(years)) + 2))
    pop = ca.population()
    gdp = ca.gdp_per_capita(pop)
    kids = ca.school_age(pop)
    top_level = ca.TOP_LEVEL
    if spending == "fms":
        spend = fms_spending()
        ca.TOP_LEVEL = [TOTAL]
    else:
        spend = ca.spending()
    try:
        with_years(spend_years)
        dis = ca.disagreement(pop, gdp, spend, kids)
        mc.FUNCTIONS = {k: v for k, v in ca.FUNCTIONS.items() if k != "social protection"}
        capacity = mc.capacity_test(pop, gdp, spend)
    finally:
        ca.TOP_LEVEL = top_level
    with_years(years)
    return {
        "disagreement": dis,
        "inequality": ca.inequality(),
        "migration": ca.migration(pop),
        "regional_income": ca.regional_income(gdp),
        "capacity": capacity,
    }


def bridge() -> dict:
    """Old against new classification on their one overlapping year (2008-09):
    the ratio new/old of each dispersion measure, per function."""
    old = measure(range(2008, 2009), range(2008, 2009), "fms")["disagreement"]
    new = measure(range(2008, 2009), range(2008, 2009), "ccofog")["disagreement"]
    return {k: {m: round(new[k]["cv"][m] / old[k]["cv"][m], 3) for m in old[k]["cv"]} for k in old}


def bridged(dis: dict, ratios: dict) -> dict:
    """Widen each heterogeneity range to cover both the raw old-classification
    value and the value rescaled to the new classification."""
    out = {}
    for k, v in dis.items():
        raw = list(v["heterogeneity"].values())
        scaled = [v["heterogeneity"][m] * ratios[k][m] for m in v["heterogeneity"]]
        out[k] = {**v, "heterogeneity_raw_range": v["heterogeneity_range"],
                  "heterogeneity_range": [round(min(raw + scaled), 4), round(max(raw + scaled), 4)]}
    return out


def emissions_spread(year: str) -> float:
    with_years([year])
    pop = ca.population()
    with GHG.open() as f:
        logs = [math.log(float(r[f"mt_{year}"]) * 1e6 / pop[(r["province"], year)]) for r in csv.DictReader(f)]
    m = mean(logs)
    return round(math.sqrt(sum((x - m) ** 2 for x in logs) / len(logs)), 3)


def brief(r: dict, migration: float | None = None) -> dict:
    extra = {}
    if migration:
        # Worlds about as mobile as the period (realised migration within 30% of it).
        pts = [p for p in r["points"] if 0.7 * migration <= p["realised_migration"] <= 1.3 * migration]
        if pts:
            modes = [p["mode"] for p in pts]
            extra["as_mobile_as_period"] = {"worlds": len(pts),
                                            "win_share": {m: round(modes.count(m) / len(pts), 3) for m in sorted(set(modes))}}
    return {**extra,
        "win_share": r["win_share"], "robust": r["robust"]["policy"],
        "robust_mode": r["robust"]["mode"], "gain_captured": round(r["robust"]["gain_captured"], 3),
        "best_per_mode": {m: round(f["gain_captured"], 3) for m, f in r["best_per_mode"].items()},
        "share_on_canadian_targets": r["share_on_canadian_targets"],
    }


def afterwards() -> dict:
    """What happened to provincial welfare spending after the 1996 block grant,
    in data the 1996 model never saw (FMS, ten provinces)."""
    spend = fms_spending()
    with_years(range(1987, 2010))
    pop = ca.population()
    gdp = ca.gdp_per_capita(pop)
    fn = "Social protection [710]"

    def stats(years):
        cvs, shares = [], []
        for y in map(str, years):
            pc = [spend[(p, y, fn)] / pop[(p, y)] for p in ca.PROVINCES]
            cvs.append(ca.cv(pc))
            shares.append(mean(spend[(p, y, fn)] / (gdp[(p, y)] * pop[(p, y)]) for p in ca.PROVINCES))
        return {"spread_cv": round(mean(cvs), 3), "share_of_gdp": round(mean(shares), 4)}

    before, after = stats(range(1988, 1996)), stats(range(1997, 2009))
    return {
        "measure": "provincial and local social services spending per person (FMS 'Social services')",
        "before_FY1988_to_1995": before, "after_FY1997_to_2008": after,
    }


def main() -> dict:
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    ratios = bridge()
    out["bridge_2008"] = ratios
    out["today"] = {k: v["heterogeneity_range"] for k, v in json.loads((ROOT / "data" / "targets.json").read_text())["disagreement"].items()}
    out["reforms"], out["not_dated"], out["afterwards"] = REFORMS, NOT_DATED, afterwards()
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    draws, seeds = saved["draws"], saved["seeds"]
    out["now"] = {k: brief(v) for k, v in saved["domains"].items()}
    vint = out.setdefault("vintages", {})
    with make_pool() as pool:
        for year, spec in VINTAGES.items():
            m = measure(spec["spend_years"], spec["years"], spec["spending"])
            if spec["spending"] == "fms":
                m["disagreement"] = bridged(m["disagreement"], ratios)
            spread = emissions_spread(spec["emissions_year"])
            v = vint.setdefault(str(year), {"results": {}})
            v["inputs"] = {
                "spending_years": f"FY{min(spec['spend_years'])}-{max(spec['spend_years'])} ({spec['spending'].upper()})",
                "other_years": f"{min(spec['years'])}-{max(spec['years'])}",
                "heterogeneity": {k: d["heterogeneity_range"] for k, d in m["disagreement"].items()},
                "income_sigma": m["inequality"]["income_sigma"],
                "market_gini": m["inequality"]["market_gini"],
                "migration_rate": m["migration"]["annual_rate"],
                "market_income_cv": m["regional_income"]["market_income_cv"],
                "capacity_elasticity": {k: d["income_elasticity"] for k, d in m["capacity"].items() if isinstance(d, dict)},
                "emissions_spread": {"year": spec["emissions_year"], "log_sd": spread},
                "inside_mobility_targets": (0.12 <= m["regional_income"]["market_income_cv"] <= 0.19
                                            and 0.003 <= m["migration"]["annual_rate"] <= 0.0075),
            }
            capacity = m["capacity"]
            if spec["spending"] == "fms":
                # Single-year elasticities differ a lot between the two classifications
                # (2008-09: transit 0.62 old against -0.08 new), so for old-classification
                # years the sampled range covers both the period's value and today's.
                today = json.loads((ROOT / "validation" / "migration_and_capacity.json").read_text())["fiscal_capacity"]
                capacity = {k: {"income_elasticity": (d["income_elasticity"], today[k]["income_elasticity"])}
                            for k, d in capacity.items() if isinstance(d, dict)}
            ranges = canada_ranges(targets=m, capacity=capacity, emissions_spread=spread)
            print(f"{year}: inputs {json.dumps(v['inputs'])}", flush=True)
            for name in spec["domains"]:
                if name in v["results"]:
                    continue
                started = time.time()
                r = analyse_domain(pool, DEFAULT_WORLD, DEFAULT_WORLD.domain(name), draws, seeds,
                                   random.Random(f"20261008:{name}"), print, ranges)
                v["results"][name] = brief(r, m["migration"]["annual_rate"])
                print(f"  {year} {name}: {v['results'][name]['robust']} ({time.time() - started:.0f}s)", flush=True)
                OUT.write_text(json.dumps(out, indent=2))
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
