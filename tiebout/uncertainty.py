"""Make the conclusions survive not knowing the parameters.

The main study optimises one hand-picked world. Here every uncertain number
gets a plausible *range* instead, and we:

  1. Sample many worlds from those ranges (Latin hypercube, so each range is
     covered evenly).
  2. Score every candidate policy in every sampled world, on the same seeds.
  3. Report how often each mode wins, which single fixed policy does best
     across all worlds (expected regret and 95th-percentile regret), and how
     much is lost by having to commit to one policy without knowing the true
     parameters. That last point also models a centre that can't measure
     spillovers: its level has to work across the whole range.
  4. Rank the parameters by how much knowing them changes the answer.
  5. Check the shortcut of analysing each domain alone, by comparing it with
     joint optimisation of the full world.
"""

import json
import math
import random
import time
from dataclasses import replace
from pathlib import Path

from .config import DEFAULT_WORLD
from .model import LOCAL, Domain, Policy, World, simulate
from .optimize import Evaluator, candidates, coordinate_descent, make_pool

# "wide": every number guessed, ranges deliberately wide, from a clearly local
# reading of each policy area to a clearly national one.
WIDE = {
    "domains": {
        "schools": {"heterogeneity": (0.10, 0.30), "spillover": (0.00, 0.15), "scale": (0.00, 0.10), "within": (0.05, 0.15)},
        "environment": {"heterogeneity": (0.02, 0.15), "spillover": (0.30, 0.80), "scale": (0.00, 0.10), "within": (0.05, 0.15)},
        "transit": {"heterogeneity": (0.05, 0.20), "spillover": (0.05, 0.35), "scale": (0.10, 0.45), "within": (0.05, 0.15)},
        "redistribution": {},
    },
    "public_good_world": {
        "national_overhead": (0.00, 0.35),
        "local_overhead": (0.00, 0.35),
        "move_share": (0.00, 0.50),
        "moving_cost": (0.00, 0.05),
        "congestion": (0.03, 0.20),
    },
    "redistribution_world": {
        "income_sigma": (0.40, 1.00),
        "deadweight": (0.25, 0.80),
        "move_share": (0.00, 0.50),
        "moving_cost": (0.00, 0.05),
        "congestion": (0.03, 0.20),
    },
}


def canada_ranges() -> dict:
    """Ranges calibrated to Canada where evidence exists; WIDE elsewhere.

    Measured from Statistics Canada (see tiebout/canada.py, data/targets.json):
      heterogeneity  spread of provincial spending on each function, three ways
      income_sigma   market-income Gini, mapped to a log-normal
      mobility and   regions differ in productivity, so people move for jobs.
      productivity   productivity_sd, moving_cost and move_share are calibrated
                     jointly so the model matches two Canadian targets at once:
                     provincial market-income spread 12-19% (11-10-0190) and
                     interprovincial migration 0.3-0.75% a year (17-10-0022)
      within         the 2019 Canadian Election Study puts between-province
                     disagreement at only 8% (schools) to 20% (environment) of
                     within-province disagreement, so within = heterogeneity / rho
                     is about 0.35 to 0.45, more than a 0-1 taste scale can hold;
                     the model's ceiling (0.25 to 0.30, near a uniform spread) is used
    From published estimates (Dahlby and Ferede 2012, 2022):
      overheads      marginal cost of public funds minus one. Federal: 1.02
                     (corporate tax) to 1.86 (personal income tax), 2021.
                     Provincial personal income tax: 0.44 to 2.81 across
                     provinces, 2006. No systematic ordering between levels, so
                     national is sampled over its range (down to 0.2 to allow a
                     cheaper marginal tax mix; sales taxes cost least in these
                     studies but no federal figure is published) and the
                     provincial/federal ratio is log-uniform on 1/4 to 4:
                     symmetric, so neither level is cheaper on average, and wide
                     enough to cover the published 0.24 to 2.75.
                     Earlier versions excluded the cited federal estimate (found
                     by audit), then sampled the two independently over ranges of
                     different widths, which made provincial money 40% dearer on
                     average without evidence.
      fiscal capacity  richer provinces spend more per person (income elasticity
                     of spending 0.41 schools, 0.32 environment, 0.05 transit,
                     validation/migration_and_capacity.py); halved for p squared
      deadweight     0.4 to 0.9 gives a marginal cost of funds of about 1.3 to 2.2
                     at a 30% tax rate
    Not calibrated (no Canadian data): spillover, scale, congestion.
    """
    root = Path(__file__).resolve().parent.parent
    targets = json.loads((root / "data" / "targets.json").read_text())
    # Fiscal capacity: income elasticity of provincial spending (validation test 3),
    # halved because spending is the model's cost, p squared. Spread +/- 25% for
    # year-to-year variation in the estimate.
    capacity = json.loads((root / "validation" / "migration_and_capacity.json").read_text())["fiscal_capacity"]
    het = {k: tuple(v["heterogeneity_range"]) for k, v in targets["disagreement"].items()}
    sigma = targets["inequality"]["income_sigma"]
    domains = {name: dict(r) for name, r in WIDE["domains"].items()}
    for name in ("schools", "environment", "transit"):
        lo, hi = het[name]
        domains[name]["heterogeneity"] = (lo, hi)
        domains[name]["within"] = (0.25, 0.30)
        k = max(capacity[name]["income_elasticity"], 0.0) / 2
        domains[name]["capacity_elasticity"] = (round(0.75 * k, 4), round(1.25 * k, 4))
    # Jointly calibrated (validation/README): with people moving for jobs, these keep
    # provincial market-income spread at 12-19% and migration at 0.3-0.75% a year.
    mobility = {"move_share": (0.02, 0.10), "moving_cost": (0.05, 0.08), "productivity_sd": (0.035, 0.07)}
    # Worlds with only a public good have no redistribution, so high earners don't
    # sort and regional incomes spread less for the same productivity gap. They
    # need their own calibration to hit the same 12-19% income spread.
    public_good_mobility = {**mobility, "productivity_sd": (0.09, 0.17)}
    return {
        "domains": domains,
        "public_good_world": {
            "national_overhead": (0.20, 1.90),
            "overhead_log_ratio": (-math.log(4), math.log(4)),
            **public_good_mobility,
            "congestion": (0.03, 0.20),
        },
        "redistribution_world": {
            "income_sigma": (round(sigma - 0.03, 3), round(sigma + 0.03, 3)),
            "deadweight": (0.40, 0.90),
            **mobility,
            "congestion": (0.03, 0.20),
        },
    }


def range_set(name: str) -> dict:
    if name == "wide":
        return WIDE
    if name == "canada":
        return canada_ranges()
    raise ValueError(f"unknown range set {name!r}; use 'wide' or 'canada'")


WEAK_WINNER = 0.1  # a fixed rule keeping under 10% of the tailored gain is no clear winner
SIMPLICITY = {"local": 0, "central": 1, "floor": 2, "ceiling": 3, "matched": 4, "equalized": 5}


def latin_hypercube(ranges: dict[str, tuple[float, float]], n: int, rng: random.Random) -> list[dict[str, float]]:
    columns = {}
    for name, (lo, hi) in ranges.items():
        strata = list(range(n))
        rng.shuffle(strata)
        columns[name] = [lo + (hi - lo) * (k + rng.random()) / n for k in strata]
    return [{name: columns[name][i] for name in ranges} for i in range(n)]


def world_ranges(domain_name: str, ranges: dict) -> dict:
    if domain_name == "redistribution":
        return dict(ranges["redistribution_world"])
    return {**ranges["public_good_world"], **ranges["domains"][domain_name]}


def build(base: World, domain: Domain, params: dict[str, float]) -> tuple[World, Domain]:
    if "overhead_log_ratio" in params and "overhead_ratio" not in params:
        # An explicit ratio (a threshold-map axis) takes precedence over the sampled log ratio.
        params = {**params, "overhead_ratio": math.exp(params["overhead_log_ratio"])}
    if "overhead_ratio" in params:
        params = {**params, "local_overhead": params["national_overhead"] * params["overhead_ratio"]}
    domain_fields = {k: v for k, v in params.items() if k in Domain.__dataclass_fields__}
    world_fields = {k: v for k, v in params.items() if k in World.__dataclass_fields__}
    d = replace(domain, **domain_fields)
    return replace(base, domains=(d,), **world_fields), d


def _task(args) -> tuple[float, float, float]:
    world, items, seed = args
    o = simulate(world, dict(items), seed)
    return o.welfare, o.migration, o.income_sorting


def _winner(cands: list[Policy], welfare: list[float]) -> int:
    """Index of the best candidate; exact ties go to the simplest mode (floor 0 is just local)."""
    top = max(welfare)
    tied = [i for i, w in enumerate(welfare) if w >= top - 1e-12]
    return min(tied, key=lambda i: (SIMPLICITY[cands[i].mode], i))


def analyse_domain(pool, base: World, domain: Domain, draws: int, seeds: int, rng: random.Random, log,
                   range_set_: dict | None = None) -> dict:
    ranges = world_ranges(domain.name, range_set_ or WIDE)
    samples = latin_hypercube(ranges, draws, rng)
    cands = candidates(domain)
    tasks = []
    for j, params in enumerate(samples):
        world, d = build(base, domain, params)
        for c in cands:
            for k in range(seeds):
                tasks.append((world, ((d.name, c),), 10_000 * j + k))
    started = time.time()
    flat = list(pool.map(_task, tasks, chunksize=64))
    log(f"    {domain.name}: {len(tasks)} runs in {time.time() - started:.0f}s")

    # welfare[j][i] = mean over seeds for draw j, candidate i
    per = len(cands) * seeds
    welfare, realised = [], []
    local_index = cands.index(LOCAL)
    for j in range(draws):
        block = flat[j * per:(j + 1) * per]
        welfare.append([sum(b[0] for b in block[i * seeds:(i + 1) * seeds]) / seeds for i in range(len(cands))])
        loc = block[local_index * seeds:(local_index + 1) * seeds]
        realised.append({"migration": sum(b[1] for b in loc) / seeds, "income_spread": sum(b[2] for b in loc) / seeds})

    local_i = cands.index(LOCAL)
    winners = [_winner(cands, w) for w in welfare]
    best = [w[i] for w, i in zip(welfare, winners)]
    gain = [b - w[local_i] for b, w in zip(best, welfare)]
    mean_gain = sum(gain) / draws

    # Fixed policies: how much does committing to one, everywhere in the range, cost?
    fixed = []
    for i, c in enumerate(cands):
        regret = sorted(best[j] - welfare[j][i] for j in range(draws))
        fixed.append({
            "policy": c.label(), "mode": c.mode, "level": c.level,
            "mean_regret": sum(regret) / draws,
            "p95_regret": regret[int(0.95 * (draws - 1))],
            "gain_captured": 1 - (sum(regret) / draws) / mean_gain if mean_gain > 0 else 1.0,
        })
    robust = min(fixed, key=lambda f: (f["mean_regret"], SIMPLICITY[f["mode"]]))
    cautious = min(fixed, key=lambda f: (f["p95_regret"], SIMPLICITY[f["mode"]]))
    best_per_mode = {}
    for f in fixed:
        if f["mode"] not in best_per_mode or f["mean_regret"] < best_per_mode[f["mode"]]["mean_regret"]:
            best_per_mode[f["mode"]] = f

    modes = [cands[i].mode for i in winners]
    share = {m: modes.count(m) / draws for m in SIMPLICITY if modes.count(m)}

    drivers = []
    for name in ranges:
        values = sorted(s[name] for s in samples)
        cut = values[draws // 2]
        low = [modes[j] for j in range(draws) if samples[j][name] < cut]
        high = [modes[j] for j in range(draws) if samples[j][name] >= cut]
        dist = lambda xs: {m: xs.count(m) / len(xs) for m in SIMPLICITY} if xs else {}
        dl, dh = dist(low), dist(high)
        tv = 0.5 * sum(abs(dl.get(m, 0) - dh.get(m, 0)) for m in SIMPLICITY)
        drivers.append({
            "parameter": name, "range": ranges[name], "importance": tv,
            "low": {m: v for m, v in dl.items() if v}, "high": {m: v for m, v in dh.items() if v},
        })
    drivers.sort(key=lambda d: -d["importance"])

    points = [
        {**{k: round(v, 4) for k, v in samples[j].items()},
         "winner": cands[winners[j]].label(), "mode": modes[j], "gain": gain[j],
         "realised_migration": round(realised[j]["migration"], 5),
         "realised_income_spread": round(realised[j]["income_spread"], 4)}
        for j in range(draws)
    ]
    on_target = sum(0.12 <= r["income_spread"] <= 0.19 and r["migration"] <= 0.0075 for r in realised) / draws
    log(f"      wins: " + ", ".join(f"{m} {v:.0%}" for m, v in share.items())
        + f" | robust: {robust['policy']} (captures {robust['gain_captured']:.0%} of the tailored gain)")
    return {
        "domain": domain.name, "draws": draws, "seeds": seeds, "ranges": ranges,
        "win_share": share, "robust": robust, "cautious": cautious,
        "best_per_mode": best_per_mode, "mean_gain_over_local": mean_gain,
        "drivers": drivers, "points": points, "share_on_canadian_targets": on_target,
    }


def separability_check(pool, base: World, n: int, seeds: int, rng: random.Random, log,
                       range_set_: dict | None = None) -> dict:
    """Does optimising domains one at a time miss interactions between them?"""
    rs_ = range_set_ or WIDE
    red = rs_["redistribution_world"]
    ranges = {**rs_["public_good_world"], "income_sigma": red["income_sigma"], "deadweight": red["deadweight"]}
    if "productivity_sd" in red:
        # The joint world contains redistribution, so it uses that world's calibration.
        ranges["productivity_sd"] = red["productivity_sd"]
    for name, rs in rs_["domains"].items():
        for k, v in rs.items():
            ranges[f"{name}.{k}"] = v
    rows = []
    for j, params in enumerate(latin_hypercube(ranges, n, rng)):
        world_fields = {k: v for k, v in params.items() if "." not in k and k not in ("overhead_ratio", "overhead_log_ratio")}
        if "overhead_log_ratio" in params:
            world_fields["local_overhead"] = params["national_overhead"] * math.exp(params["overhead_log_ratio"])
        domains = []
        for d in base.domains:
            fields = {k.split(".", 1)[1]: v for k, v in params.items() if k.startswith(d.name + ".")}
            domains.append(replace(d, **fields))
        world = replace(base, domains=tuple(domains), **world_fields)
        seed_list = [50_000 + 100 * j + k for k in range(seeds)]

        separate = {}
        for d in domains:
            single = replace(world, domains=(d,))
            scores = Evaluator(single, seed_list, pool).score([{d.name: c} for c in candidates(d)])
            welfare = [s.welfare for s in scores]
            separate[d.name] = candidates(d)[_winner(candidates(d), welfare)]

        ev = Evaluator(world, seed_list, pool)
        joint = coordinate_descent(ev, max_passes=3, log=lambda *_: None).best
        assembled = ev.score([separate])[0]
        local = ev.score([{d.name: LOCAL for d in domains}])[0]
        stakes = joint.welfare - local.welfare
        row = {
            "same_modes": sum(separate[k].mode == joint.arrangement[k].mode for k in separate),
            "domains": len(separate),
            "gain_kept": (assembled.welfare - local.welfare) / stakes if stakes > 0 else 1.0,
            "separate": {k: p.label() for k, p in separate.items()},
            "joint": {k: p.label() for k, p in joint.arrangement.items()},
        }
        rows.append(row)
        log(f"    world {j + 1}/{n}: modes agree {row['same_modes']}/{row['domains']}, "
            f"one-at-a-time keeps {row['gain_kept']:.0%} of the joint gain")
    return {
        "worlds": n,
        "mode_agreement": sum(r["same_modes"] for r in rows) / sum(r["domains"] for r in rows),
        "min_gain_kept": min(r["gain_kept"] for r in rows),
        "mean_gain_kept": sum(r["gain_kept"] for r in rows) / n,
        "rows": rows,
    }


def run_uncertainty(out_dir: Path, draws: int = 200, seeds: int = 3, check_worlds: int = 8,
                    workers: int | None = None, log=print, ranges: str = "wide") -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rs = range_set(ranges)
    rng = random.Random(20261008)
    started = time.time()
    out = {"draws": draws, "seeds": seeds, "ranges": ranges, "domains": {}}
    with make_pool(workers) as pool:
        log(f"A. sampling worlds per policy area ({ranges} ranges)")
        for d in DEFAULT_WORLD.domains:
            out["domains"][d.name] = analyse_domain(pool, DEFAULT_WORLD, d, draws, seeds, rng, log, rs)
        log("B. checking one-domain-at-a-time against joint optimisation")
        out["separability"] = separability_check(pool, DEFAULT_WORLD, check_worlds, seeds, rng, log, rs)
    out["seconds"] = round(time.time() - started, 1)
    suffix = "" if ranges == "wide" else f"_{ranges}"
    (out_dir / f"uncertainty{suffix}.json").write_text(json.dumps(out, indent=2))
    (out_dir / f"robust_arrangement{suffix}.jur").write_text(robust_jur(out))
    return out


def robust_jur(out: dict) -> str:
    from .bridge import TO_LAW

    lines = [
        "# The policy per domain with the lowest expected regret across all sampled worlds.",
        f"# {out['draws']} sampled worlds per domain, {out['seeds']} seeds each.",
        "",
        "scope nation {",
    ]
    for name, r in out["domains"].items():
        f = r["robust"]
        if f["gain_captured"] < WEAK_WINNER:
            # No fixed national rule earns its keep here; say so rather than
            # dressing up a near-tie as a recommendation.
            lines.append(f"{'  law ' + name + ': shadow':<40}# no rule clearly wins; best ({f['policy']}) keeps {f['gain_captured']:.0%}")
            continue
        decl = f"  law {name}: {TO_LAW[f['mode']]}" + ("" if f["mode"] == "local" else f" = {f['level']:g}")
        lines.append(f"{decl:<40}# wins {r['win_share'].get(f['mode'], 0):.0%} of worlds; keeps {f['gain_captured']:.0%} of the tailored gain")
    lines.append("}")
    return "\n".join(lines) + "\n"
