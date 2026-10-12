"""Build site/index.html from the study results.

    python3 site/build.py [RESULTS_DIR]
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "results"


def trim_points(points, keep):
    return [{k: p[k] for k in keep if k in p} for p in points]


def main() -> None:
    study = json.loads(((RESULTS / "results.json") if (RESULTS / "results.json").exists() else ROOT / "results" / "results.json").read_text())
    wide = json.loads((RESULTS / "uncertainty.json").read_text())
    canada_path = RESULTS / "uncertainty_canada.json"
    canada = json.loads(canada_path.read_text()) if canada_path.exists() else None
    # The page leads with the calibrated run when it exists.
    unc = canada or wide

    def domains_of(run):
        out = {}
        for name, d in run["domains"].items():
            params = [dr["parameter"] for dr in d["drivers"]]
            out[name] = {
                "win_share": d["win_share"],
                "robust": d["robust"],
                "cautious": d["cautious"],
                "best_per_mode": d["best_per_mode"],
                "drivers": d["drivers"],
                "stakes": d["mean_gain_over_local"],
                "ranges": d["ranges"],
                "points": trim_points(d["points"], params + ["mode", "winner", "gain"]),
            }
        return out

    domains = domains_of(unc)

    data = {
        "study": {k: study[k] for k in ("best", "baselines", "phase_spillover", "phase_scale", "mobility", "robustness", "by_mode")},
        "unc": {
            "draws": unc["draws"],
            "seeds": unc["seeds"],
            "domains": domains,
            "separability": unc["separability"],
        },
        "jur": {
            "robust": (RESULTS / ("robust_arrangement_canada.jur" if canada else "robust_arrangement.jur")).read_text(),
        },
        "calibrated": bool(canada),
        "wide": {name: {"win_share": d["win_share"], "robust": d["robust"], "stakes": d["mean_gain_over_local"]}
                 for name, d in wide["domains"].items()},
        "targets": json.loads((ROOT / "data" / "targets.json").read_text()) if (ROOT / "data" / "targets.json").exists() else None,
        "survey": json.loads((ROOT / "data" / "ces_disagreement.json").read_text()) if (ROOT / "data" / "ces_disagreement.json").exists() else None,
    }
    template = (ROOT / "site" / "template.html").read_text()
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    out = template.replace("/*__DATA__*/null", payload)
    (ROOT / "site" / "index.html").write_text(out)
    print(f"wrote site/index.html ({len(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
