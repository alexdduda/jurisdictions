"""The model on the United States: does it predict how the US divides powers?

Same analysis as `python -m tiebout uncertainty --ranges canada`, with every
measured input replaced by its US value (data/us/targets.json, built by
data/scripts/us_targets.py): spending disagreement across the 50 states,
market-income inequality, how strongly state spending rises with state income
(no equalization), and the spread of CO2 per person. Mobility is refitted so the
model reproduces US migration between states (1.3% to 1.7% a year, against
Canada's 0.75%) and the spread of state market incomes (17.5% to 18%):

  public goods     move_share 0.03-0.08, moving_cost 0.005-0.015,
                   productivity_sd 0.15-0.20 (grid search: migration 1.2-1.7%,
                   income spread 0.15-0.20)
  redistribution   move_share 0.03-0.05, moving_cost 0.035-0.045,
                   productivity_sd 0-0.03. The model can't hit both targets here:
                   with US inequality, the migration rate that matches pushes the
                   income spread to about 0.23, and the spread that matches comes
                   with about 1% migration. The range straddles the two.

Kept from Canada, flagged: the cost-of-funds ratio (computed for Canada's
taxes, about 1), the city map for transit, the language map for schools, and
every unmeasured range. The model still has 16 regions; the US has 50 states.

Reports, per area, the robust rule, and how the US actually assigns it, for
comparison. Uses the same sampled worlds (random streams) as the Canadian run.

    python3 validation/us_run.py      # writes validation/us_run.json
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import analyse_domain, canada_ranges  # noqa: E402

OUT = ROOT / "validation" / "us_run.json"
PUBLIC_GOOD_MOBILITY = {"move_share": (0.03, 0.08), "moving_cost": (0.005, 0.015), "productivity_sd": (0.15, 0.20)}
REDISTRIBUTION_MOBILITY = {"move_share": (0.03, 0.05), "moving_cost": (0.035, 0.045), "productivity_sd": (0.0, 0.03)}
TARGETS = {"migration": (0.013, 0.017), "income_spread": (0.15, 0.20)}

# How the US assigns each area, in the model's terms (sources in README.md).
ACTUAL = {
    "schools": ("States and districts decide; federal money is under a tenth of school spending, much of it "
                "Title I grants aimed at poor districts", "local, with a small targeted grant"),
    "environment": ("Federal minimum standards (Clean Air Act, Clean Water Act) that states implement and may exceed",
                    "floor"),
    "transit": ("Cities, transit agencies and states run it; federal capital grants pay a fixed share "
                "(typically 80% for highways, up to 80% for transit projects)", "local, with matching grants"),
    "redistribution": ("Mostly federal (Social Security, SNAP, SSI, the earned income tax credit), with Medicaid "
                       "cost-shared and cash welfare a block grant", "central, with some matching"),
    "climate": ("No national carbon price; some states price carbon (California cap and trade, the Regional "
                "Greenhouse Gas Initiative); federal vehicle and power standards", "states decide, with some standards"),
}


def us_ranges() -> dict:
    us = json.loads((ROOT / "data" / "us" / "targets.json").read_text())
    capacity = {k: {"income_elasticity": v["income_elasticity"]} for k, v in us["fiscal_capacity"].items()}
    rs = canada_ranges(targets=us, capacity=capacity, emissions_spread=us["emissions_spread"]["log_sd"])
    rs["public_good_world"].update(PUBLIC_GOOD_MOBILITY)
    rs["redistribution_world"].update(REDISTRIBUTION_MOBILITY)
    return rs


def on_target(points: list[dict]) -> float:
    return sum(TARGETS["migration"][0] <= p["realised_migration"] <= TARGETS["migration"][1]
               and TARGETS["income_spread"][0] <= p["realised_income_spread"] <= TARGETS["income_spread"][1]
               for p in points) / len(points)


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    rs = us_ranges()
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    out["inputs"] = {k: v for k, v in json.loads((ROOT / "data" / "us" / "targets.json").read_text()).items()
                     if k != "source"}
    out["mobility"] = {"public_goods": PUBLIC_GOOD_MOBILITY, "redistribution": REDISTRIBUTION_MOBILITY,
                       "targets": TARGETS}
    out["canada"] = {k: {"robust": v["robust"]["policy"], "gain_captured": round(v["robust"]["gain_captured"], 3),
                         "win_share": v["win_share"]} for k, v in saved["domains"].items()}
    res = out.setdefault("results", {})
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            if d.name in res:
                continue
            r = analyse_domain(pool, DEFAULT_WORLD, d, saved["draws"], saved["seeds"],
                               random.Random(f"20261008:{d.name}"), print, rs)
            pts = r["points"]
            res[d.name] = {
                "robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
                "gain_captured": round(r["robust"]["gain_captured"], 3), "win_share": r["win_share"],
                "best_per_mode": {m: round(f["gain_captured"], 3) for m, f in r["best_per_mode"].items()},
                "share_on_us_targets": round(on_target(pts), 3),
                "median_migration": sorted(p["realised_migration"] for p in pts)[len(pts) // 2],
                "median_income_spread": sorted(p["realised_income_spread"] for p in pts)[len(pts) // 2],
                "actual": ACTUAL[d.name][0], "actual_in_model_terms": ACTUAL[d.name][1],
            }
            OUT.write_text(json.dumps(out, indent=2))
            print(d.name, json.dumps(res[d.name]), flush=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
