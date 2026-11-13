"""Verdicts dated further ahead, with uncertainty that grows with the horizon.

Measured inputs drift: across the backtest's vintages, provincial spending
disagreement moved up to 12-27% a decade, inequality 8%, the emissions spread
22% (DECADE_DRIFT in tiebout/uncertainty.py). For a verdict dated h years
ahead, each measured range is widened around its midpoint by that drift times
h/10, and the analysis rerun on the same sampled worlds and seeds.
Unmeasured ranges are already wide guesses and stay as they are.

    python3 validation/horizons.py      # writes validation/horizons.json
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

OUT = ROOT / "validation" / "horizons.json"
HORIZONS = {"2036": 10, "2046": 20}


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())
    out = json.loads(OUT.read_text()) if OUT.exists() else {"horizons": {}}
    out["now"] = {k: {"robust": v["robust"]["policy"], "robust_mode": v["robust"]["mode"],
                      "gain_captured": round(v["robust"]["gain_captured"], 3), "win_share": v["win_share"]}
                  for k, v in saved["domains"].items()}
    with make_pool() as pool:
        for label, h in HORIZONS.items():
            rs = canada_ranges(horizon_years=h)
            res = out["horizons"].setdefault(label, {})
            for d in DEFAULT_WORLD.domains:
                if d.name in res:
                    continue
                r = analyse_domain(pool, DEFAULT_WORLD, d, saved["draws"], saved["seeds"],
                                   random.Random(f"20261008:{d.name}"), print, rs)
                res[d.name] = {"robust": r["robust"]["policy"], "robust_mode": r["robust"]["mode"],
                               "gain_captured": round(r["robust"]["gain_captured"], 3), "win_share": r["win_share"]}
                OUT.write_text(json.dumps(out, indent=2))
                print(label, d.name, res[d.name]["robust"], res[d.name]["gain_captured"], flush=True)
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
