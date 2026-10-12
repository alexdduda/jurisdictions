"""The full study: optimise the default world, then map where the answer changes."""

import json
import time
from dataclasses import replace
from pathlib import Path

from .bridge import arrangement_to_jur
from .config import DEFAULT_WORLD
from .model import LOCAL, Domain, World
from .optimize import Evaluator, Score, best_single, coordinate_descent, make_pool, single_domain_world

MODE_ORDER = ("local", "central", "floor", "ceiling", "matched")


def _margin(winner: Score, table: dict[str, Score], mode: str) -> tuple[float, float]:
    """How far the winner beats the best *other* mode, and the noise on that gap."""
    rivals = [s for m, s in table.items() if m != mode]
    runner = max(rivals, key=lambda s: s.welfare)
    paired = [a.welfare - b.welfare for a, b in zip(winner.outcomes, runner.outcomes)]
    n = len(paired)
    mu = sum(paired) / n
    se = (sum((p - mu) ** 2 for p in paired) / (n - 1) / n) ** 0.5 if n > 1 else 0.0
    return mu, se


def _cell(winner: Score, table: dict[str, Score], name: str) -> str:
    policy = winner.arrangement[name]
    gap, se = _margin(winner, table, policy.mode)
    tie = " ≈" if gap < 2 * se else ""
    return f"{policy.label()}{tie}"


def phase_map(pool, base: World, seeds, rows, cols, make_domain, row_label, col_label, log) -> dict:
    grid = []
    for r in rows:
        line = []
        for c in cols:
            d = make_domain(r, c)
            ev = Evaluator(single_domain_world(base, d), seeds, pool)
            winner, table = best_single(ev, d)
            line.append(_cell(winner, table, d.name))
        grid.append(line)
        log(f"    {row_label}={r}: " + " | ".join(line))
    return {"rows": list(rows), "cols": list(cols), "row_label": row_label, "col_label": col_label, "cells": grid}


def run_study(seeds: list[int], out_dir: Path, workers: int | None = None, quick: bool = False, log=print) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = DEFAULT_WORLD
    if quick:
        base = replace(base, agents_per_region=40, steps=16, measure_steps=4)
    started = time.time()
    results: dict = {"seeds": seeds, "quick": quick}

    with make_pool(workers) as pool:
        log("1. optimising the default world")
        ev = Evaluator(base, seeds, pool)
        search = coordinate_descent(ev, log=log)
        best = search.best
        results["best"] = {k: p.label() for k, p in best.arrangement.items()}
        results["best_welfare"] = [best.welfare, best.se]

        log("2. baselines")
        all_local = ev.score([{d.name: LOCAL for d in base.domains}])[0]
        all_central = ev.score([{
            d.name: search.by_mode[d.name]["central"].arrangement[d.name] for d in base.domains
        }])[0]
        # Best you can do if every domain must be purely local or purely central:
        binary = {}
        for d in base.domains:
            loc, cen = search.by_mode[d.name]["local"], search.by_mode[d.name]["central"]
            binary[d.name] = (loc if loc.welfare >= cen.welfare else cen).arrangement[d.name]
        best_binary = ev.score([binary])[0]

        log("3. phase map: spillover x heterogeneity (no scale economies)")
        spill = phase_map(
            pool, base, seeds,
            rows=[0.0, 0.1, 0.2, 0.4, 0.6, 0.8] if not quick else [0.0, 0.4, 0.8],
            cols=[0.0, 0.1, 0.2, 0.3] if not quick else [0.0, 0.3],
            make_domain=lambda s, h: Domain("good", heterogeneity=h, within=0.1, spillover=s),
            row_label="spillover", col_label="heterogeneity", log=log,
        )

        log("4. phase map: scale economies x heterogeneity (no spillovers)")
        scale = phase_map(
            pool, base, seeds,
            rows=[0.0, 0.1, 0.2, 0.3, 0.5] if not quick else [0.0, 0.5],
            cols=[0.0, 0.1, 0.2, 0.3] if not quick else [0.0, 0.3],
            make_domain=lambda sc, h: Domain("good", heterogeneity=h, within=0.1, scale=sc),
            row_label="scale", col_label="heterogeneity", log=log,
        )

        log("5. redistribution under rising mobility")
        mobility = []
        red = Domain("redistribution", kind="redistribution")
        for share in ([0.0, 0.05, 0.1, 0.25, 0.5] if not quick else [0.0, 0.5]):
            world = single_domain_world(base, red, move_share=share)
            evm = Evaluator(world, seeds, pool)
            winner, table = best_single(evm, red)
            row = {
                "move_share": share,
                "winner": _cell(winner, table, red.name),
                "welfare": {m: table[m].welfare for m in ("local", "floor", "central")},
                "local_tax": table["local"].mean("policy_mean", red.name),
                "local_sorting": table["local"].mean("income_sorting"),
            }
            mobility.append(row)
            log(f"    move_share={share}: {row['winner']}, local tax {row['local_tax']:.3f}, sorting {row['local_sorting']:.3f}")

        log("6. robustness: re-optimise under different assumptions")
        variants = {
            "baseline": {},
            "no national overhead": {"national_overhead": 0.0},
            "heavy national overhead (0.3)": {"national_overhead": 0.3},
            "no mobility": {"move_share": 0.0},
            "high mobility (0.5)": {"move_share": 0.5},
            "more income inequality": {"income_sigma": 0.9},
        }
        robustness = {}
        for label, changes in variants.items():
            if label == "baseline":
                robustness[label] = results["best"]
                continue
            evr = Evaluator(replace(base, **changes), seeds, pool)
            sr = coordinate_descent(evr, max_passes=3, log=lambda *_: None)
            robustness[label] = {k: p.label() for k, p in sr.best.arrangement.items()}
            log(f"    {label}: " + ", ".join(f"{k}={v}" for k, v in robustness[label].items()))

    results.update({
        "baselines": {
            "all local": [all_local.welfare, all_local.se],
            "all central (best levels)": [all_central.welfare, all_central.se],
            "best local-or-central per domain": [best_binary.welfare, best_binary.se],
            "optimum": [best.welfare, best.se],
        },
        "binary": {k: p.label() for k, p in binary.items()},
        "by_mode": {
            d: {m: {"policy": s.arrangement[d].label(), "welfare": s.welfare} for m, s in table.items()}
            for d, table in search.by_mode.items()
        },
        "trace": search.trace,
        "phase_spillover": spill,
        "phase_scale": scale,
        "mobility": mobility,
        "robustness": robustness,
        "outcome": {
            "policy_mean": {k: best.mean("policy_mean", k) for k in best.arrangement},
            "policy_sd": {k: best.mean("policy_sd", k) for k in best.arrangement},
            "income_sorting": best.mean("income_sorting"),
            "local_policy_mean": {k: all_local.mean("policy_mean", k) for k in best.arrangement},
            "local_income_sorting": all_local.mean("income_sorting"),
        },
        "runs": ev.runs,
        "seconds": round(time.time() - started, 1),
    })

    (out_dir / "results.json").write_text(json.dumps(results, indent=2))
    (out_dir / "best_arrangement.jur").write_text(arrangement_to_jur(best, search, base))
    (out_dir / "REPORT.md").write_text(render_report(results, base))
    return results


def render_report(r: dict, world: World) -> str:
    def welfare_gap(name: str) -> str:
        w, se = r["baselines"][name]
        lo = r["baselines"]["all local"][0]
        top = r["baselines"]["optimum"][0]
        share = (w - lo) / (top - lo) if top != lo else 0.0
        return f"| {name} | {w:.4f} ± {se:.4f} | {share:.0%} |"

    lines = [
        "# The best balance between local and central power (in this model)",
        "",
        f"Seeds: {len(r['seeds'])} · simulations for the main search: {r['runs']} · runtime {r['seconds']}s"
        + (" · **quick mode: low resolution**" if r["quick"] else ""),
        "",
        "## The optimum",
        "",
        "| domain | best arrangement | spillover | heterogeneity | scale |",
        "|---|---|---|---|---|",
    ]
    for d in world.domains:
        if d.kind == "public_good":
            lines.append(f"| {d.name} | **{r['best'][d.name]}** | {d.spillover} | {d.heterogeneity} | {d.scale} |")
        else:
            lines.append(f"| {d.name} | **{r['best'][d.name]}** | – | – | – |")

    lines += [
        "",
        "Welfare is average utility per person. The last column shows how much of the gap between "
        "*everything local* and the optimum each option closes.",
        "",
        "| arrangement | welfare | gap closed |",
        "|---|---|---|",
        *(welfare_gap(k) for k in r["baselines"]),
        "",
        f"Best purely local-or-central choice per domain: "
        + ", ".join(f"{k} = {v}" for k, v in r["binary"].items()) + ".",
        "",
        "### What each mode can do for each domain (others held at the optimum)",
        "",
        "| domain | " + " | ".join(MODE_ORDER) + " |",
        "|---|" + "---|" * len(MODE_ORDER),
    ]
    for d, table in r["by_mode"].items():
        top = max(v["welfare"] for v in table.values())
        cells = []
        for m in MODE_ORDER:
            if m not in table:
                cells.append("–")
                continue
            loss = top - table[m]["welfare"]
            cells.append(f"**{table[m]['policy']}**" if loss == 0 else f"{table[m]['policy']} (−{loss * 1000:.1f})")
        lines.append(f"| {d} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Numbers in brackets: welfare lost versus the best mode, in thousandths of a util.",
        "",
        "### What changes on the ground",
        "",
        "| domain | mean level, all local | mean level, optimum | spread across regions at optimum |",
        "|---|---|---|---|",
    ]
    o = r["outcome"]
    for k in o["policy_mean"]:
        lines.append(f"| {k} | {o['local_policy_mean'][k]:.3f} | {o['policy_mean'][k]:.3f} | {o['policy_sd'][k]:.3f} |")
    lines += [
        "",
        f"Income sorting (spread of regional mean incomes): {o['local_income_sorting']:.3f} with everything "
        f"local, {o['income_sorting']:.3f} at the optimum.",
        "",
        "## Where the answer flips",
        "",
        "Each cell is the best arrangement for a single public good with those properties. "
        "`≈` means the winner beats the runner-up mode by less than two standard errors.",
    ]
    for key, title in (("phase_spillover", "Spillovers vs. regional differences (no scale economies)"),
                       ("phase_scale", "Scale economies vs. regional differences (no spillovers)")):
        ph = r[key]
        lines += [
            "",
            f"### {title}",
            "",
            f"| {ph['row_label']} ↓ / {ph['col_label']} → | " + " | ".join(str(c) for c in ph["cols"]) + " |",
            "|---|" + "---|" * len(ph["cols"]),
            *(f"| {row} | " + " | ".join(cells) + " |" for row, cells in zip(ph["rows"], ph["cells"])),
        ]
    lines += [
        "",
        "### Redistribution as people become more mobile",
        "",
        "| share considering a move each step | winner | welfare: local | floor | central | local tax rate | income sorting under local |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in r["mobility"]:
        w = row["welfare"]
        lines.append(
            f"| {row['move_share']} | {row['winner']} | {w['local']:.4f} | {w['floor']:.4f} | {w['central']:.4f} "
            f"| {row['local_tax']:.3f} | {row['local_sorting']:.3f} |"
        )
    lines += [
        "",
        "## How robust is the optimum?",
        "",
        "| assumptions | " + " | ".join(d.name for d in world.domains) + " |",
        "|---|" + "---|" * len(world.domains),
    ]
    for label, arr in r["robustness"].items():
        lines.append(f"| {label} | " + " | ".join(arr[d.name] for d in world.domains) + " |")
    lines += [
        "",
        "## What this model leaves out",
        "",
        "- **Floors are unfunded mandates.** A floor that binds everywhere is a central policy paid "
        "for locally. It beats `central` here only because national money carries overhead and local "
        "money doesn't. Real unfunded mandates have their own costs (poor regions pay as much as rich "
        "ones, and there's resentment and evasion) that this model doesn't charge for. With zero "
        "overhead, environment flips to central.",
        "- Modes that never bind (`floor 0`, `ceiling 1`) tie with `local` because they *are* local.",
        "- `±` on welfare levels is spread across random worlds. Comparisons between arrangements "
        "are paired on the same worlds, so they are much more precise than those intervals suggest.",
        "- Governments here are honest median voters. No capture, no lobbying, no corruption at either level.",
        "- The centre knows the spillover rate exactly when it sets a match rate. In reality it has to guess.",
        "- There is no policy experimentation: regions cannot learn from each other's results, which is one "
        "of the strongest real arguments for decentralisation.",
        "- Central policy must be uniform. A centre that could tailor policy region by region would always win, "
        "but it would also need information it rarely has.",
        "- All parameters are assumptions. The phase maps matter more than the headline optimum: they say "
        "*which features of a policy area* push it up or down a level.",
        "",
        "Re-score any arrangement with `python -m tiebout evaluate <file.jur>`. "
        "The optimum is saved as `best_arrangement.jur`.",
    ]
    return "\n".join(lines) + "\n"
