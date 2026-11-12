"""The uncertainty analysis with each region set to its real province.

Same sampled worlds and seeds as results/uncertainty_canada.json, but each
region's average taste (schools, environment, climate), abatement cost
(climate) and productivity are its province's measured values instead of
random draws (tiebout/provinces.py). What stays uncertain is what was never
measured: spillovers, scale, cost of funds, mobility, transit's city
parameters. Compares the verdicts.

    python3 validation/provinces_run.py      # writes validation/provinces_run.json
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

OUT = ROOT / "validation" / "provinces_run.json"


def brief(r: dict) -> dict:
    return {"win_share": r["win_share"], "robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
            "gain_captured": round(r["robust"]["gain_captured"], 3),
            "best_per_mode": {m: round(f["gain_captured"], 3) for m, f in r["best_per_mode"].items()}}


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    out = json.loads(OUT.read_text()) if OUT.exists() else {"provinces": {}}
    out["sampled"] = {k: brief(v) for k, v in saved["domains"].items()}
    base = replace(DEFAULT_WORLD, province_profile="canada")
    rs = range_set("canada")
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            if d.name in out["provinces"]:
                continue
            r = analyse_domain(pool, base, d, saved["draws"], saved["seeds"], random.Random(f"20261008:{d.name}"), print, rs)
            out["provinces"][d.name] = brief(r)
            OUT.write_text(json.dumps(out, indent=2))
            print(d.name, out["provinces"][d.name]["robust"], out["provinces"][d.name]["gain_captured"], flush=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
