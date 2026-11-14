"""Do the verdicts survive a housing market?

The model has no housing by default: moving costs a fixed amount and crowding
costs every resident alike. With World.housing on, each resident pays rent of
housing x the region's mean income x (population / average), and the rent goes
to the region's original residents as owners. Rents are sampled at 10% to 30%
of income (an assumption, not fitted to data).

Housing turns out to raise sorting by income, not damp it: rent is the same
amount for everyone in a region, so it weighs most on low incomes, and poorer
people are priced out of richer regions (tests/test_tiebout.py). So it doesn't
fix the US misfit (validation/country_run.py), where the model already sorts too much.

Reruns every area on the same sampled worlds with housing added and reports the
robust rule, the share of worlds matching Canada's migration and income spread,
and the typical migration and income spread.

    python3 validation/housing.py     # writes validation/housing.json
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

OUT = ROOT / "validation" / "housing.json"
HOUSING = (0.10, 0.30)


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    rs = canada_ranges()
    rs["public_good_world"]["housing"] = HOUSING
    rs["redistribution_world"]["housing"] = HOUSING
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    out["housing_range"] = HOUSING
    out["now"] = {k: {"robust": v["robust"]["policy"], "robust_mode": v["robust"]["mode"],
                      "gain_captured": round(v["robust"]["gain_captured"], 3), "win_share": v["win_share"],
                      "share_on_canadian_targets": v.get("share_on_canadian_targets")}
                  for k, v in saved["domains"].items()}
    res = out.setdefault("results", {})
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            if d.name in res:
                continue
            r = analyse_domain(pool, DEFAULT_WORLD, d, saved["draws"], saved["seeds"],
                               random.Random(f"20261008:{d.name}"), print, rs)
            res[d.name] = {"robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
                           "gain_captured": round(r["robust"]["gain_captured"], 3), "win_share": r["win_share"],
                           "share_on_canadian_targets": r["share_on_canadian_targets"],
                           "median_income_spread": sorted(p["realised_income_spread"] for p in r["points"])[len(r["points"]) // 2],
                           "median_migration": sorted(p["realised_migration"] for p in r["points"])[len(r["points"]) // 2]}
            OUT.write_text(json.dumps(out, indent=2))
            print(d.name, json.dumps(res[d.name]), flush=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
