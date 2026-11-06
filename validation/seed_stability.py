"""Are 3 random seeds per world enough?

The uncertainty analysis scores every rule in every sampled world on 3 shared
seeds. Simulation noise could still pick the wrong winner where two rules are
close. For a sample of the saved worlds in each policy area, this re-scores
the best fixed policy of each rule on the original 3 seeds and on 12 fresh
ones, and reports how often the winning rule agrees.

    python3 validation/seed_stability.py [WORLDS_PER_AREA]
"""

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.model import Policy, simulate  # noqa: E402
from tiebout.uncertainty import build  # noqa: E402

ORIGINAL = [0, 1, 2]
FRESH = list(range(100, 112))


def score(args):
    world, name, policy, seeds = args
    return sum(simulate(world, {name: policy}, s).welfare for s in seeds) / len(seeds)


def main(per_area: int = 30) -> dict:
    run = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    domains = {d.name: d for d in DEFAULT_WORLD.domains}
    out = {}
    with ProcessPoolExecutor() as pool:
        for name, d in run["domains"].items():
            rules = [Policy(f["mode"], f["level"]) for f in d["best_per_mode"].values()]
            params_keys = list(d["ranges"])
            worlds = []
            for j, point in enumerate(d["points"][:per_area]):
                params = {k: point[k] for k in params_keys}
                worlds.append(build(DEFAULT_WORLD, domains[name], params)[0])
            agree, flips = 0, []
            for wi, world in enumerate(worlds):
                orig = list(pool.map(score, [(world, name, r, [10_000 * wi + s for s in ORIGINAL]) for r in rules]))
                fresh = list(pool.map(score, [(world, name, r, [10_000 * wi + s for s in FRESH]) for r in rules]))
                a = max(range(len(rules)), key=lambda i: orig[i])
                b = max(range(len(rules)), key=lambda i: fresh[i])
                if rules[a].mode == rules[b].mode:
                    agree += 1
                else:
                    flips.append((rules[a].label(), rules[b].label(), round(abs(fresh[a] - fresh[b]), 5)))
            out[name] = {"worlds": len(worlds), "agreement": round(agree / len(worlds), 3), "flips": flips}
            print(f"{name:<15} winner agrees on {agree}/{len(worlds)} worlds" + (f"; flips: {flips}" if flips else ""), flush=True)
    (ROOT / "validation" / "seed_stability.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30)
