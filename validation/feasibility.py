"""Who loses? Each recommended rule, region by region, against provinces deciding.

The robustness analysis picks the rule with the most total welfare. A rule can
win on totals and still not last if its losses fall on a few places. For each
policy area this samples worlds from the Canadian ranges, runs the robust rule
(results/uncertainty_canada.json) and the provincial default on the same
seeds, and measures, for the people who started in each of the 16 regions,
the change in average welfare. It reports:

  share losing        share of regions (each starts with 1/16 of the people)
                      worse off under the rule
  worst loss          the hardest-hit region's loss, in units of the average
                      gain (2 means it loses twice what the average person gains)
  concentrated        cases where under a quarter of regions lose, but the
                      worst loses more than the average gain: few losers who
                      lose a lot, the pattern that tends to organise opposition
  who                 correlation of a region's change with its productivity
                      (income), its average taste for the good, and for
                      climate its abatement cost (emissions per person)

For climate, the two regions with the highest abatement cost stand in for
Alberta and Saskatchewan (2 of 16 regions is 12.5% of people; the two
provinces held 14.7% of Canadians in 2016 and 51% of the ten provinces'
emissions in 2024).

    python3 validation/feasibility.py              # writes validation/feasibility.json
    python3 validation/feasibility.py --provinces  # regions take their province's measured
                                                   # values; adds the change by province group
"""

import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.model import LOCAL, Policy, _Run  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import build, canada_ranges, latin_hypercube, world_ranges  # noqa: E402

DRAWS, SEEDS = 40, 3
OUT = ROOT / "validation" / "feasibility.json"


def corr(x, y):
    mx, my = mean(x), mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy) if sx and sy else 0.0


def _case(args):
    world, name, policy, seed = args
    rule = _Run(world, {name: policy}, seed)
    a = rule.run()
    b = _Run(world, {}, seed).run()
    n = world.agents_per_region
    taste = [mean(rule.tastes[name][r * n:(r + 1) * n]) for r in range(rule.R)] if name in rule.tastes else None
    return {
        "delta": [x - y for x, y in zip(a.by_origin, b.by_origin)],
        "productivity": rule.productivity,
        "taste": taste,
        "abatement": rule.abatement.get(name),
    }


def by_province(cases: list[dict]) -> dict:
    """Median change for each province group, in units of the average gain."""
    from tiebout.provinces import profile
    names = profile("canada")["names"]
    out = {}
    for g in dict.fromkeys(names):
        idx = [r for r, n in enumerate(names) if n == g]
        vals = sorted(mean(c["delta"][r] for r in idx) / mean(c["delta"]) for c in cases if mean(c["delta"]) > 0)
        out[g] = {"median_change_over_mean_gain": round(vals[len(vals) // 2], 2),
                  "share_of_worlds_losing": round(sum(v < 0 for v in vals) / len(vals), 3)}
    return out


def summarise(cases: list[dict]) -> dict:
    rows = []
    for c in cases:
        d = c["delta"]
        gain = mean(d)
        if gain <= 0:
            continue  # the rule doesn't help in this world; nothing to distribute
        losing = sum(x < 0 for x in d) / len(d)
        worst = -min(d) / gain if min(d) < 0 else 0.0
        row = {"losing": losing, "worst": worst, "concentrated": losing < 0.25 and worst > 1.0,
               "corr_productivity": corr(d, c["productivity"])}
        if c["taste"]:
            row["corr_taste"] = corr(d, c["taste"])
        if c["abatement"]:
            row["corr_abatement"] = corr(d, c["abatement"])
            top = sorted(range(len(d)), key=lambda r: -c["abatement"][r])[:2]
            row["top_cost_regions"] = mean(d[r] for r in top) / gain
            row["top_cost_regions_lose"] = all(d[r] < 0 for r in top)
        rows.append(row)
    med = lambda xs: sorted(xs)[len(xs) // 2]
    out = {
        "cases": len(rows),
        "median_share_losing": round(med([r["losing"] for r in rows]), 3),
        "median_worst_loss_over_mean_gain": round(med([r["worst"] for r in rows]), 2),
        "share_concentrated": round(mean(r["concentrated"] for r in rows), 3),
        "share_with_any_loser": round(mean(r["losing"] > 0 for r in rows), 3),
        "corr_with_productivity": round(mean(r["corr_productivity"] for r in rows), 2),
    }
    if "corr_taste" in rows[0]:
        out["corr_with_taste"] = round(mean(r["corr_taste"] for r in rows), 2)
    if "corr_abatement" in rows[0]:
        out["corr_with_abatement_cost"] = round(mean(r["corr_abatement"] for r in rows), 2)
        out["top_two_cost_regions_change_over_mean_gain"] = round(med([r["top_cost_regions"] for r in rows]), 2)
        out["share_where_both_top_cost_regions_lose"] = round(mean(r["top_cost_regions_lose"] for r in rows), 3)
    return out


def main(provinces: bool = False) -> dict:
    base_world = replace(DEFAULT_WORLD, province_profile="canada") if provinces else DEFAULT_WORLD
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())["domains"]
    ranges = canada_ranges()
    out = {"draws": DRAWS, "seeds": SEEDS, "against": "provinces decide (local)", "areas": {},
           "province_profile": provinces}
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            rb = saved[d.name]["robust"]
            policy = Policy(rb["mode"], rb["level"])
            samples = latin_hypercube(world_ranges(d.name, ranges), DRAWS, random.Random(f"feasibility:{d.name}"))
            tasks = []
            for j, params in enumerate(samples):
                world, _ = build(base_world, d, params)
                tasks += [(world, d.name, policy, 10_000 * j + k) for k in range(SEEDS)]
            cases = list(pool.map(_case, tasks, chunksize=4))
            res = summarise(cases)
            out["areas"][d.name] = {"rule": rb["policy"], **res}
            if provinces:
                out["areas"][d.name]["by_province"] = by_province(cases)
            print(d.name, json.dumps(out["areas"][d.name]), flush=True)
    (OUT.with_name("feasibility_provinces.json") if provinces else OUT).write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main("--provinces" in sys.argv)
