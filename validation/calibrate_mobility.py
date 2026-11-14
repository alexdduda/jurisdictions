"""Fit the model's mobility settings to a country's migration and income spread.

The model has three mobility settings nobody measures directly: the share of
people who consider moving each round (move_share), what moving costs
(moving_cost), and how much regions differ in productivity (productivity_sd).
Two things are measured: the share of people who move between regions each
year, and how far apart regional average incomes are. This searches a grid of
the three settings, at the midpoints of each country's other ranges, and keeps
the grid points whose simulated migration and income spread both fall in the
country's target range. The fitted range is the box around the points kept;
if none is kept, the nearest point (in relative distance to the targets).

Public goods and redistribution are fitted separately: with redistribution,
richer people also move to escape taxes, so the same settings give more sorting.

  canada_provinces  ten provinces (tiebout/geography.py); targets 0.3-0.75% a year,
                    income spread 12-19% (data/targets.json, as for the 16-region model)
  us_states         fifty states; 1.3-1.7% a year (CPS), 15-20% (BEA)
  au_states         six states; 1.26-1.75% a year (ABS interstate departures),
                    10-15% (ABS household primary income)

    python3 validation/calibrate_mobility.py [country ...]   # writes validation/mobility.json
"""

import itertools
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.model import simulate  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import build, canada_ranges, world_ranges  # noqa: E402

OUT = ROOT / "validation" / "mobility.json"
COUNTRIES = {
    "canada_provinces": {"targets": None, "geography": "provinces",
                         "migration": (0.003, 0.0075), "income_spread": (0.12, 0.19)},
    "us_states": {"targets": "data/us/targets.json", "geography": "us_states",
                  "migration": (0.013, 0.017), "income_spread": (0.15, 0.20)},
    "au_states": {"targets": "data/au/targets.json", "geography": "au_states",
                  "migration": (0.0126, 0.0175), "income_spread": (0.10, 0.15)},
}
GRID = {
    "move_share": [0.02, 0.03, 0.05, 0.08, 0.12],
    "moving_cost": [0.005, 0.01, 0.02, 0.035, 0.05, 0.07],
    "public_good_productivity_sd": [0.05, 0.10, 0.15, 0.20],
    "redistribution_productivity_sd": [0.0, 0.02, 0.04, 0.07],
}
SEEDS = 2


def country_ranges(name: str) -> dict:
    c = COUNTRIES[name]
    if not c["targets"]:
        return canada_ranges()
    t = json.loads((ROOT / c["targets"]).read_text())
    capacity = {k: {"income_elasticity": v["income_elasticity"]} for k, v in t["fiscal_capacity"].items()}
    return canada_ranges(targets=t, capacity=capacity, emissions_spread=t["emissions_spread"]["log_sd"])


def base_world(name: str):
    g = COUNTRIES[name]["geography"]
    if g == "provinces":
        return replace(DEFAULT_WORLD, geography=g)
    return replace(DEFAULT_WORLD, geography=g, language_profile="", city_profile="")


def _task(args):
    world, seed = args
    o = simulate(world, {}, seed)
    return o.migration, o.income_sorting


def fit(pool, name: str) -> dict:
    c = COUNTRIES[name]
    rs, base = country_ranges(name), base_world(name)
    out = {}
    for kind, area, sd_key in (("public_goods", "schools", "public_good_productivity_sd"),
                               ("redistribution", "redistribution", "redistribution_productivity_sd")):
        mid = {k: (lo + hi) / 2 for k, (lo, hi) in world_ranges(area, rs).items()}
        points = list(itertools.product(GRID["move_share"], GRID["moving_cost"], GRID[sd_key]))
        tasks = []
        for ms, mc, ps in points:
            world, _ = build(base, DEFAULT_WORLD.domain(area), {**mid, "move_share": ms, "moving_cost": mc, "productivity_sd": ps})
            tasks += [(world, s) for s in range(SEEDS)]
        res = list(pool.map(_task, tasks, chunksize=2))
        rows = []
        for j, (ms, mc, ps) in enumerate(points):
            m = sum(r[0] for r in res[j * SEEDS:(j + 1) * SEEDS]) / SEEDS
            inc = sum(r[1] for r in res[j * SEEDS:(j + 1) * SEEDS]) / SEEDS
            rows.append({"move_share": ms, "moving_cost": mc, "productivity_sd": ps,
                         "migration": round(m, 5), "income_spread": round(inc, 4)})
        lo_m, hi_m = c["migration"]
        lo_i, hi_i = c["income_spread"]
        kept = [r for r in rows if lo_m <= r["migration"] <= hi_m and lo_i <= r["income_spread"] <= hi_i]
        miss = lambda r: (max(0, lo_m - r["migration"], r["migration"] - hi_m) / hi_m
                          + max(0, lo_i - r["income_spread"], r["income_spread"] - hi_i) / hi_i)
        best = sorted(rows, key=miss)
        use = kept or best[:1]
        out[kind] = {
            "fits": len(kept),
            "ranges": {k: (min(r[k] for r in use), max(r[k] for r in use)) for k in ("move_share", "moving_cost", "productivity_sd")},
            "nearest": best[0] if not kept else None,
            "kept": kept,
        }
        print(name, kind, "fits", len(kept), out[kind]["ranges"], "nearest" if not kept else "", best[0] if not kept else "", flush=True)
    return out


def ranges_for(name: str) -> dict:
    """Fitted mobility ranges, as {public_good_world: {...}, redistribution_world: {...}}."""
    fitted = json.loads(OUT.read_text())[name]
    widen = lambda r: (r[0], r[1]) if r[1] > r[0] else (r[0], r[0] * 1.0001 + 1e-6)
    return {"public_good_world": {k: widen(v) for k, v in fitted["public_goods"]["ranges"].items()},
            "redistribution_world": {k: widen(v) for k, v in fitted["redistribution"]["ranges"].items()}}


def provinces_ranges() -> dict:
    """Canada's ranges with mobility refitted for the ten-province geography."""
    rs = canada_ranges()
    mob = ranges_for("canada_provinces")
    rs["public_good_world"].update(mob["public_good_world"])
    rs["redistribution_world"].update(mob["redistribution_world"])
    return rs


def main(names) -> dict:
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    with make_pool() as pool:
        for name in names:
            out[name] = {"targets": {k: COUNTRIES[name][k] for k in ("migration", "income_spread")}, **fit(pool, name)}
            OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main(sys.argv[1:] or list(COUNTRIES))
