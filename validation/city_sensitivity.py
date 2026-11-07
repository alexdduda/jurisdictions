"""Does the transit verdict survive changes in commuting since 2016?

Re-runs the transit uncertainty analysis (same sampled worlds, same seeds) on
alternative city maps and compares the robust rule and how often each rule
wins:

  canada              2016 Census, every metropolitan area (the baseline)
  canada_2023_big3    Toronto, Montreal, Vancouver at May 2023 transit shares
  canada_half_spread  the gap between metropolitan areas halved
  (two-place)         every metropolitan area alike: the earlier model, read
                      from results/uncertainty_canada_two_place.json if present

    python3 validation/city_sensitivity.py
"""

import json
import random
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import analyse_domain, range_set  # noqa: E402


def brief(r: dict) -> dict:
    keep = {k: r[k] for k in ("win_share", "robust", "mean_gain_over_local")}
    keep["best_per_mode"] = {m: {"policy": f["policy"], "gain_captured": round(f["gain_captured"], 3)}
                             for m, f in r["best_per_mode"].items()}
    return keep


def main(scenarios=("canada_2023_big3", "canada_half_spread")):
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    draws, seeds = saved["draws"], saved["seeds"]
    out = {"canada": brief(saved["domains"]["transit"])}
    prev = ROOT / "results" / "uncertainty_canada_two_place.json"
    if prev.exists():
        out["two_place"] = brief(json.loads(prev.read_text())["domains"]["transit"])
    rs = range_set("canada")
    transit = DEFAULT_WORLD.domain("transit")
    with make_pool() as pool:
        for name in scenarios:
            base = replace(DEFAULT_WORLD, city_profile=name)
            print(f"{name}:", flush=True)
            r = analyse_domain(pool, base, transit, draws, seeds, random.Random("20261008:transit"), print, rs)
            out[name] = brief(r)
    for name, r in out.items():
        rb = r["robust"]
        print(f"{name:<20} robust {rb['policy']:<16} keeps {rb['gain_captured']:.0%}; "
              f"cities win {r['win_share'].get('city', 0):.0%}, central {r['win_share'].get('central', 0):.0%}; "
              f"best city rule keeps {r['best_per_mode']['city']['gain_captured']:.0%}")
    (ROOT / "validation" / "city_sensitivity.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
