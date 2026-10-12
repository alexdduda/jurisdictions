"""Turn verdicts into thresholds on the numbers nobody has measured.

Spillovers and scale savings have no Canadian data, so a verdict that depends
on them is only as good as the guess. Instead of a verdict, this maps the
best rule across those axes, holding every calibrated parameter at the
midpoint of its Canadian range, and reports where the answer changes. Anyone
who knows the real number can then read off the answer.

    python3 -m tiebout.thresholds            # writes results/thresholds.json
"""

import json
import time
from dataclasses import replace
from pathlib import Path

from .config import DEFAULT_WORLD
from .optimize import Evaluator, best_single, make_pool
from .uncertainty import build, canada_ranges, world_ranges

# For each policy area, the two axes that decide it and that data can't pin down
# (or, for redistribution, that the uncertainty analysis found most influential).
MAPS = {
    "transit": {
        "rows": ("scale", [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]),
        "cols": ("spillover", [0.0, 0.1, 0.2, 0.3, 0.4]),
    },
    "environment": {
        "rows": ("spillover", [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]),
        "cols": ("overhead_ratio", [0.6, 0.9, 1.2, 1.5]),
    },
    "schools": {
        "rows": ("spillover", [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]),
        "cols": ("overhead_ratio", [0.6, 0.9, 1.2, 1.5]),
    },
    "redistribution": {
        "rows": ("move_share", [0.0, 0.02, 0.05, 0.1, 0.2, 0.3]),
        "cols": ("deadweight", [0.3, 0.5, 0.7, 0.9]),
    },
}
SEEDS = [0, 1, 2]


def midpoints(domain_name: str, ranges: dict) -> dict[str, float]:
    return {k: (lo + hi) / 2 for k, (lo, hi) in world_ranges(domain_name, ranges).items()}


def run_thresholds(out_dir: Path, log=print) -> dict:
    ranges = canada_ranges()
    started = time.time()
    out = {"seeds": len(SEEDS), "maps": {}}
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            spec = MAPS[d.name]
            (rname, rvals), (cname, cvals) = spec["rows"], spec["cols"]
            base = midpoints(d.name, ranges)
            cells = []
            for rv in rvals:
                row = []
                for cv in cvals:
                    world, dom = build(DEFAULT_WORLD, d, {**base, rname: rv, cname: cv})
                    winner, table = best_single(Evaluator(world, SEEDS, pool), dom)
                    policy = winner.arrangement[dom.name]
                    rivals = sorted((s.welfare for m, s in table.items() if m != policy.mode), reverse=True)
                    row.append({
                        "mode": policy.mode, "label": policy.label(),
                        "margin": round(winner.welfare - rivals[0], 5) if rivals else None,
                    })
                cells.append(row)
                log(f"  {d.name} {rname}={rv}: " + " | ".join(c["label"] for c in row))
            out["maps"][d.name] = {
                "row_param": rname, "rows": rvals, "col_param": cname, "cols": cvals,
                "held_at": {k: round(v, 4) for k, v in base.items() if k not in (rname, cname)},
                "cells": cells,
            }
    out["seconds"] = round(time.time() - started, 1)
    (out_dir / "thresholds.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(line_buffering=True)
    run_thresholds(Path(__file__).resolve().parent.parent / "results")
