"""The model on other federations: does it predict how they divide powers?

Same analysis as `python -m tiebout uncertainty --ranges canada`, with every
measured input replaced by the country's own (data/<country>/targets.json) and
the regions replaced by its real states, sized by population with real borders
(tiebout/geography.py). Mobility is refitted to the country's migration and
income spread (validation/calibrate_mobility.py). Kept from Canada, flagged:
the cost-of-funds ratio (computed for Canada's taxes, about 1), the opinion-based
ratio of within- to between-region disagreement, and every unmeasured range.
No city or language map outside Canada: transit uses the two-place model.

  us   50 states. data/scripts/us_targets.py (Census, BEA, CPS, OECD, EIA)
  au   6 states. data/scripts/au_targets.py (ABS, OECD, DCCEEW)

Each verdict is compared with how the country actually assigns the area
(the "actual" entries below; their figures are checked in VERIFICATION.md,
the summaries of programmes without a figure are not). Same sampled worlds as the Canadian run.

    python3 validation/country_run.py us au     # writes validation/country_<c>.json
"""

import json
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))
from calibrate_mobility import ranges_for  # noqa: E402
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import analyse_domain, canada_ranges  # noqa: E402

COUNTRIES = {
    "us": {"targets": "data/us/targets.json", "geography": "us_states", "mobility": "us_states",
           "migration": (0.013, 0.017), "income_spread": (0.15, 0.20), "actual": {
        "schools": ("States and districts decide; federal money is about an eighth of school revenue (11.7% in "
                    "fiscal 2024, 13.7% at the pandemic peak), much of it Title I grants aimed at poor districts", "local, with a small targeted grant"),
        "environment": ("Federal minimum standards (Clean Air Act, Clean Water Act) that states implement and may "
                        "exceed", "floor"),
        "transit": ("Cities, transit agencies and states run it; federal capital grants pay a share of projects "
                    "(at most 80% for transit capital investment grants)", "local, with matching grants"),
        "health": ("Mixed: federal Medicare for those 65 and over, Medicaid run by states with the federal "
                   "government paying 50% to 83% of the cost by state income, private insurance for most others", "matched, for the public part"),
        "redistribution": ("Mostly federal (Social Security, SSI, the earned income tax credit). SNAP food benefits were "
                           "fully federal for about 50 years until the 2025 budget law, which makes most states pay a share "
                           "set by their error rates; Medicaid is cost-shared and cash welfare has been a fixed block grant "
                           "($16.5 billion a year) since 1996", "central, with some matching"),
        "climate": ("No national carbon price; some states price carbon (California's cap-and-trade, extended to 2045 "
                    "and renamed cap-and-invest in 2025; the Regional Greenhouse Gas Initiative for power plants in north-eastern "
                    "states); federal vehicle and power standards", "states decide, with some standards"),
    }},
    "au": {"targets": "data/au/targets.json", "geography": "au_states", "mobility": "au_states",
           "migration": (0.0126, 0.0175), "income_spread": (0.10, 0.15), "actual": {
        "schools": ("States run schools; the Commonwealth pays at least 20% of a needs-based Schooling Resource "
                    "Standard per student in government schools (80% in non-government ones), with loadings for disadvantage", "foundation"),
        "environment": ("States regulate and spend; national law (the EPBC Act) covers nine matters of national "
                        "environmental significance, such as World Heritage properties, Ramsar wetlands and threatened species", "local, with a narrow national floor"),
        "transit": ("State governments run public transport; the Commonwealth co-funds some infrastructure",
                    "local, with grants"),
        "health": ("States run public hospitals; the Commonwealth pays 45% of the growth in their efficient cost, "
                   "priced by activity, under the National Health Reform Agreement, and runs Medicare", "matched"),
        "redistribution": ("Federal: pensions and allowances are paid by the Commonwealth", "central"),
        "climate": ("A national carbon price ran from 1 July 2012 and was repealed in July 2014; large emitters now "
                    "face the national Safeguard Mechanism, baselines declining 4.9% a year with tradable credits", "national standard"),
    }},
}


def country_ranges(code: str) -> dict:
    c = COUNTRIES[code]
    t = json.loads((ROOT / c["targets"]).read_text())
    capacity = {k: {"income_elasticity": v["income_elasticity"]} for k, v in t["fiscal_capacity"].items()}
    rs = canada_ranges(targets=t, capacity=capacity, emissions_spread=t["emissions_spread"]["log_sd"])
    mob = ranges_for(c["mobility"])
    rs["public_good_world"].update(mob["public_good_world"])
    rs["redistribution_world"].update(mob["redistribution_world"])
    return rs


def on_target(points: list[dict], c: dict) -> float:
    return sum(c["migration"][0] <= p["realised_migration"] <= c["migration"][1]
               and c["income_spread"][0] <= p["realised_income_spread"] <= c["income_spread"][1]
               for p in points) / len(points)


def run(code: str) -> dict:
    c = COUNTRIES[code]
    out_path = ROOT / "validation" / f"country_{code}.json"
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    rs = country_ranges(code)
    base = replace(DEFAULT_WORLD, geography=c["geography"], language_profile="", city_profile="")
    out = json.loads(out_path.read_text()) if out_path.exists() else {}
    out["inputs"] = {k: v for k, v in json.loads((ROOT / c["targets"]).read_text()).items() if k != "source"}
    out["mobility"] = {"public_goods": rs["public_good_world"], "redistribution": rs["redistribution_world"],
                       "targets": {"migration": c["migration"], "income_spread": c["income_spread"]}}
    out["canada"] = {k: {"robust": v["robust"]["policy"], "robust_mode": v["robust"]["mode"],
                         "gain_captured": round(v["robust"]["gain_captured"], 3), "win_share": v["win_share"]}
                     for k, v in saved["domains"].items()}
    res = out.setdefault("results", {})
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            if d.name in res:
                continue
            r = analyse_domain(pool, base, d, saved["draws"], saved["seeds"], random.Random(f"20261008:{d.name}"), print, rs)
            pts = r["points"]
            res[d.name] = {
                "robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
                "gain_captured": round(r["robust"]["gain_captured"], 3), "win_share": r["win_share"],
                "best_per_mode": {m: round(f["gain_captured"], 3) for m, f in r["best_per_mode"].items()},
                "share_on_targets": round(on_target(pts, c), 3),
                "median_migration": sorted(p["realised_migration"] for p in pts)[len(pts) // 2],
                "median_income_spread": sorted(p["realised_income_spread"] for p in pts)[len(pts) // 2],
                "actual": c["actual"][d.name][0], "actual_in_model_terms": c["actual"][d.name][1],
            }
            out_path.write_text(json.dumps(out, indent=2))
            print(code, d.name, json.dumps(res[d.name]), flush=True)
    out_path.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    for code in sys.argv[1:] or list(COUNTRIES):
        run(code)
