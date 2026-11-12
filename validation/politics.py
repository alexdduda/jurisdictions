"""Which rules would pass? Perceived costs and a ratification vote.

The model scores rules by real welfare. Reforms are adopted, and kept, by
voters who see some costs more clearly than others. Two additions, applied
after each simulation so the model's welfare accounting is unchanged:

1. Visible payments. Under a carbon price, households pay the price on every
   tonne they still emit, and get the money back as a rebate. In real welfare
   the two cancel (federal rebates went back to the province of origin). In
   perception they don't: Canadians underestimated the rebate and many didn't
   know they received one (Mildenberger, Lachapelle, Harrison and
   Stadelmann-Steffen, Nature Climate Change 12, 2022). A region's perceived
   change is its real change minus (1 - rebate_seen) x the payment. Quantity
   standards and floors have no visible payment: their costs are buried in
   prices, which is the textbook reason regulation is easier to pass than a tax.

   Payments need emissions. A region's emissions per person are proportional
   to its abatement cost multiplier (the calibration already ties that
   multiplier's spread to emissions per person across provinces), scaled so
   that the price cuts a share `abated` of national emissions.

2. A vote. A rule passes when the regions holding a majority of people
   perceive themselves better off than under provinces deciding. (Each region
   starts with 1/16 of the people.) A two-thirds threshold stands in for the
   general amending formula (seven provinces with half the population).

For each policy area this samples worlds from the Canadian ranges, scores
each kind of rule (its best level from results/uncertainty_canada.json), and
reports how often it passes and, per world, the best rule that passes. The
gap between that and the best rule outright is the cost of politics.

Not measured, so sampled: rebate_seen 0 to 0.6 (low awareness, substantial
underestimation), abated 5% to 30%.

    python3 validation/politics.py              # writes validation/politics.json
    python3 validation/politics.py --provinces  # regions take their province's measured values;
                                                # adds who opposes each rule, by province group
"""

import json
import random
import sys
from dataclasses import replace
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.model import LOCAL, Policy, _clamp, _Run  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import build, canada_ranges, latin_hypercube, world_ranges  # noqa: E402

DRAWS, SEEDS = 40, 3
OUT = ROOT / "validation" / "politics.json"
SALIENCE = {"rebate_seen": (0.0, 0.6), "abated": (0.05, 0.30)}
THRESHOLDS = {"majority": 0.5, "two_thirds": 2 / 3}


def _case(args):
    world, name, policies, seed, salience = args
    d = world.domain(name)
    base = _Run(world, {}, seed).run().by_origin
    out = []
    for policy in policies:
        run = _Run(world, {name: policy}, seed)
        o = run.run()
        delta = [x - y for x, y in zip(o.by_origin, base)]
        perceived = list(delta)
        pay = [0.0] * len(delta)
        if d.private_costs and policy.mode in ("price", "price_floor"):
            a = run.abatement.get(name, [1.0] * run.R)
            cut = [_clamp(policy.level / (2 * a[r]), 0, world.max_level) for r in range(run.R)]
            # Baseline emissions proportional to a, scaled so the price cuts `abated` of the total.
            scale = sum(cut) / (salience["abated"] * sum(a))
            for r in range(run.R):
                residual = max(a[r] * scale - cut[r], 0.0)
                pay[r] = d.weight * policy.level * residual
                perceived[r] -= (1 - salience["rebate_seen"]) * pay[r]
        # Share of the rebate voters would need to see for a majority of regions to
        # perceive a gain: region r is for it once seen >= 1 - delta_r / pay_r.
        needed = None
        if any(pay):
            need = sorted(max(0.0, 1 - delta[r] / pay[r]) if pay[r] > 0 else (0.0 if delta[r] > 0 else 2.0)
                          for r in range(len(delta)))
            needed = need[len(need) // 2]
        out.append({"gain": mean(delta), "delta": delta, "perceived": perceived, "needed": needed,
                    "payment_over_gain": (mean(pay) / mean(delta)) if any(pay) and mean(delta) > 0 else None})
    return out


def main(provinces: bool = False, only: tuple = ()) -> dict:
    base_world = replace(DEFAULT_WORLD, province_profile="canada") if provinces else DEFAULT_WORLD
    names = None
    if provinces:
        from tiebout.provinces import profile
        names = profile("canada")["names"]
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())["domains"]
    ranges = canada_ranges()
    out = {"draws": DRAWS, "seeds": SEEDS, "salience_ranges": SALIENCE, "areas": {}, "province_profile": provinces}
    with make_pool() as pool:
        prev = json.loads(OUT.read_text()) if (only and OUT.exists() and not provinces) else None
        if prev:
            out["areas"] = prev["areas"]
        for d in DEFAULT_WORLD.domains:
            if only and d.name not in only:
                continue
            best = saved[d.name]["best_per_mode"]
            policies = [Policy(f["mode"], f["level"]) for m, f in best.items() if m != "local"]
            labels = [f["policy"] for m, f in best.items() if m != "local"]
            rng = random.Random(f"politics:{d.name}")
            samples = latin_hypercube({**world_ranges(d.name, ranges), **SALIENCE}, DRAWS, rng)
            tasks = []
            for j, params in enumerate(samples):
                sal = {k: params.pop(k) for k in SALIENCE}
                world, _ = build(base_world, d, params)
                tasks += [(world, d.name, policies, 10_000 * j + k, sal) for k in range(SEEDS)]
            cases = list(pool.map(_case, tasks, chunksize=2))
            area = {"rules": {}}
            for i, lab in enumerate(labels):
                rows = [c[i] for c in cases]
                need = sorted(r["needed"] for r in rows if r["needed"] is not None)
                extra = {}
                if need:
                    extra = {"rebate_seen_needed_for_majority": {"median": round(need[len(need) // 2], 3),
                                                                 "p10": round(need[len(need) // 10], 3),
                                                                 "p90": round(need[9 * len(need) // 10], 3)},
                             "payment_over_real_gain_median": round(sorted(r["payment_over_gain"] for r in rows if r["payment_over_gain"])[len(need) // 2], 1)}
                area["rules"][lab] = {**extra,
                    "mean_gain": round(mean(r["gain"] for r in rows), 5),
                    **{f"passes_{k}_real": round(mean(sum(x > 0 for x in r["delta"]) / len(r["delta"]) > t for r in rows), 3)
                       for k, t in THRESHOLDS.items()},
                    **{f"passes_{k}_perceived": round(mean(sum(x > 0 for x in r["perceived"]) / len(r["perceived"]) > t for r in rows), 3)
                       for k, t in THRESHOLDS.items()},
                }
            if names:
                # Share of worlds in which each province group perceives itself worse off.
                for i, lab in enumerate(labels):
                    opp = {}
                    for g in dict.fromkeys(names):
                        idx = [r for r, n in enumerate(names) if n == g]
                        opp[g] = round(mean(mean(c[i]["perceived"][r] for r in idx) < 0 for c in cases), 3)
                    area["rules"][lab]["opposed_by"] = opp
            # Per world: the best rule outright against the best rule that passes.
            for k, t in THRESHOLDS.items():
                kept, picks = [], {}
                for c in cases:
                    top = max(r["gain"] for r in c)
                    passing = [(r["gain"], labels[i]) for i, r in enumerate(c)
                               if sum(x > 0 for x in r["perceived"]) / len(r["perceived"]) > t and r["gain"] > 0]
                    g, lab = max(passing) if passing else (0.0, "nothing passes")
                    picks[lab] = picks.get(lab, 0) + 1
                    if top > 0:
                        kept.append(g / top)
                area[f"best_that_passes_{k}"] = {
                    "gain_kept": round(mean(kept), 3),
                    "picks": {lab: round(n / len(cases), 3) for lab, n in sorted(picks.items(), key=lambda x: -x[1])},
                }
            out["areas"][d.name] = area
            print(d.name, json.dumps(area), flush=True)
    (OUT.with_name("politics_provinces.json") if provinces else OUT).write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main("--provinces" in sys.argv, tuple(a for a in sys.argv[1:] if not a.startswith("--")))
