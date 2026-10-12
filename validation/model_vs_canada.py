"""Run the calibrated model under Canada's arrangement and apply the same tests as the data.

    python3 validation/model_vs_canada.py [--productivity]

Without --productivity the model has no regional productivity or fiscal
capacity (the version that failed validation); with it, the current model.
Each test is computed on the model's simulated regions exactly as
validation/redistribution.py and validation/migration_and_capacity.py compute
it on the ten provinces, and printed beside the Canadian value.

Only the migration drivers and the redistribution pattern are genuine
out-of-sample checks. Fiscal capacity is calibrated from the data, so
reproducing it only confirms the calibration was wired in correctly.
"""

import json
import math
import sys
from dataclasses import replace
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD, ENVIRONMENT, REDISTRIBUTION, SCHOOLS, TRANSIT  # noqa: E402
from tiebout.model import Policy, _Run, _median  # noqa: E402

SEEDS = range(12)


def calibrated_world(productivity: bool):
    """Midpoints of the Canada ranges in tiebout/uncertainty.py."""
    domains = (
        replace(SCHOOLS, heterogeneity=0.031, within=0.28, capacity_elasticity=0.20 if productivity else 0.0),
        replace(ENVIRONMENT, heterogeneity=0.075, within=0.28, capacity_elasticity=0.16 if productivity else 0.0),
        replace(TRANSIT, heterogeneity=0.075, within=0.28, capacity_elasticity=0.026 if productivity else 0.0),
        REDISTRIBUTION,
    )
    return replace(
        DEFAULT_WORLD, domains=domains, income_sigma=0.81, national_overhead=0.6, local_overhead=0.6,
        deadweight=0.65, move_share=0.06, moving_cost=0.065, productivity_sd=0.05 if productivity else 0.0,
        steps=40,
    )


# Canada today, roughly: provinces run the public goods; redistribution is a
# national floor (federal transfers and taxes) that provinces top up.
CANADA = {"redistribution": Policy("floor", 0.2)}


def simulate_panel(world, seed):
    """Per region, per step: income, services, redistribution, inequality, and next-step net migration."""
    run = _Run(world, CANADA, seed)
    rows = []
    for step in range(world.steps):
        residents = [[i for i, r in enumerate(run.region) if r == k] for k in range(run.R)]
        pops = [len(res) for res in residents]
        state = run.region_state(residents)
        services = [sum(e[-1][r] for e in state if e[0] == "pg") for r in range(run.R)]
        red = next(e for e in state if e[0] == "red")
        transfers, rates = red[4], red[5]
        before = list(run.region)
        if world.move_share > 0:
            run.move(state, pops)
        after = run.region
        for r in range(run.R):
            if not residents[r]:
                continue
            incomes = [run.income(i, r) for i in residents[r]]
            inflow = sum(1 for a, b in zip(before, after) if b == r and a != r)
            outflow = sum(1 for a, b in zip(before, after) if a == r and b != r)
            rows.append({
                "seed": seed, "step": step, "region": r,
                "log_income": math.log(run.regional_income[r]),
                "log_services": math.log(max(services[r], 1e-6)),
                "transfer": transfers[r], "rate": rates[r],
                "inequality": 1 - _median(incomes) / mean(incomes),
                "net_migration": (inflow - outflow) / pops[r],
            })
    return rows


def standardize(xs):
    m, s = mean(xs), pstdev(xs)
    return [(x - m) / s for x in xs] if s else [0.0] * len(xs)


def two_regressor_ols(y, a, b):
    saa, sbb, sab = sum(x * x for x in a), sum(x * x for x in b), sum(x * z for x, z in zip(a, b))
    say, sby = sum(x * t for x, t in zip(a, y)), sum(x * t for x, t in zip(b, y))
    det = saa * sbb - sab * sab
    return (sbb * say - sab * sby) / det, (saa * sby - sab * say) / det


def demean(rows, key, by):
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r[k] for k in by), []).append(r[key])
    means = {g: mean(v) for g, v in groups.items()}
    return [r[key] - means[tuple(r[k] for k in by)] for r in rows]


def spearman(a, b):
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        r = [0] * len(xs)
        for k, i in enumerate(order):
            r[i] = k
        return r
    ra, rb, n = ranks(a), ranks(b), len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def tests(productivity: bool):
    world = calibrated_world(productivity)
    panel = [row for seed in SEEDS for row in simulate_panel(world, seed)]
    # Use the settled part of each run, and pair this step's conditions with this step's moves
    # (moves happen after policies are seen, the analogue of next year's migration).
    panel = [r for r in panel if r["step"] >= 10]

    # Migration drivers, within regions over time (remove each region's own mean and each step's mean).
    for r in panel:
        r["unit"] = (r["seed"], r["region"])
        r["time"] = (r["seed"], r["step"])
    y = standardize([a - b for a, b in zip(demean(panel, "net_migration", ["unit"]), [0] * len(panel))])
    inc = standardize(demean(panel, "log_income", ["unit"]))
    srv = standardize(demean(panel, "log_services", ["unit"]))
    b_inc, b_srv = two_regressor_ols(y, inc, srv)

    # Redistribution across regions: inequality vs. what regions spend on it (settled averages).
    regions = {}
    for r in panel:
        regions.setdefault(r["unit"], []).append(r)
    ineq = [mean(x["inequality"] for x in v) for v in regions.values()]
    spend = [mean(x["transfer"] for x in v) for v in regions.values()]
    want = [mean(x["rate"] for x in v) for v in regions.values()]

    return {
        "migration_effect_income": round(b_inc, 3),
        "migration_effect_services": round(b_srv, 3),
        "inequality_to_wanting": round(spearman(ineq, want), 3),
        "inequality_to_spending": round(spearman(ineq, spend), 3),
    }


def main():
    canada = {
        "migration_effect_income": 0.319,
        "migration_effect_services": -0.224,
        "inequality_to_wanting": 0.576,
        "inequality_to_spending": -0.188,
    }
    out = {"canada": canada, "model_without_productivity": tests(False), "model_with_productivity": tests(True)}
    (ROOT / "validation" / "model_vs_canada.json").write_text(json.dumps(out, indent=2))
    print(f"{'test':<28}{'Canada':>9}{'old model':>11}{'new model':>11}")
    for k in canada:
        print(f"{k:<28}{canada[k]:>9.2f}{out['model_without_productivity'][k]:>11.2f}{out['model_with_productivity'][k]:>11.2f}")


if __name__ == "__main__":
    main()
