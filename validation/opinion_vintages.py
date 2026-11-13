"""Do the verdicts survive opinion data from other years?

The taste calibration uses one survey, the 2019 Canadian Election Study: how far
provinces' average wishes sit apart in units of disagreement within a province
(rho). data/scripts/ces_vintages.py measures the same thing in the 1993 to 2015
studies (data/ces_vintages.json). Where it feeds the model:

  schools      within-province disagreement = spending spread / rho, capped at
               the model's 0.25 to 0.30. With 2019's rho (0.08) the cap binds;
               with 2004's (0.25) within falls to about 0.10. The range now runs
               from the highest same-question rho (2004-2019) to the cap.
  environment  same-question rho 0.12 to 0.20 (2015's is lost in sampling noise)
               keeps within above the cap in every year: unchanged.
  climate      heterogeneity = rho x within. The 2008 carbon-tax item gives 0.18
               against 2019's 0.235, so the lower bound moves from 0.05 to 0.045.

Reruns those two areas on the same sampled worlds and seeds as today's.

    python3 validation/opinion_vintages.py     # writes validation/opinion_vintages.json
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

OUT = ROOT / "validation" / "opinion_vintages.json"
CAP = 0.30


def same_question(area: str) -> list[float]:
    years = json.loads((ROOT / "data" / "ces_vintages.json").read_text())["years"]
    return [v[area]["rho"] for y, v in years.items() if area in v and not v[area]["proxy"] and v[area]["rho"] > 0]


def dated_ranges() -> tuple[dict, dict]:
    targets = json.loads((ROOT / "data" / "targets.json").read_text())
    rs = canada_ranges()
    info = {}
    lo_h, hi_h = targets["disagreement"]["schools"]["heterogeneity_range"]
    rho = same_question("schools")
    within = (round(min(lo_h / max(rho), CAP), 3), CAP)
    rs["domains"]["schools"]["within"] = within
    info["schools"] = {"rho_range": [min(rho), max(rho)], "within": within, "was": [0.25, 0.30]}
    env = same_question("environment")
    lo_e = targets["disagreement"]["environment"]["heterogeneity_range"][0]
    info["environment"] = {"rho_range": [min(env), max(env)], "lowest_within": round(lo_e / max(env), 3),
                           "unchanged": lo_e / max(env) >= CAP}
    clim = same_question("climate")
    het = (round(min(clim) * 0.25, 3), rs["domains"]["climate"]["heterogeneity"][1])
    rs["domains"]["climate"]["heterogeneity"] = het
    info["climate"] = {"rho_range": [min(clim), max(clim)], "heterogeneity": het, "was": [0.05, 0.08]}
    return rs, info


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    rs, info = dated_ranges()
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    out["inputs"] = info
    res = out.setdefault("results", {})
    out["now"] = {k: {"robust": saved["domains"][k]["robust"]["policy"],
                      "gain_captured": round(saved["domains"][k]["robust"]["gain_captured"], 3),
                      "win_share": saved["domains"][k]["win_share"]} for k in ("schools", "climate")}
    with make_pool() as pool:
        for name in ("schools", "climate"):
            if name in res:
                continue
            r = analyse_domain(pool, DEFAULT_WORLD, DEFAULT_WORLD.domain(name), saved["draws"], saved["seeds"],
                               random.Random(f"20261008:{name}"), print, rs)
            res[name] = {"robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
                         "gain_captured": round(r["robust"]["gain_captured"], 3), "win_share": r["win_share"]}
            OUT.write_text(json.dumps(out, indent=2))
            print(name, res[name], flush=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
