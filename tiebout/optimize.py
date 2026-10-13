"""Search for the arrangement that maximises average welfare.

Coordinate descent: hold every domain fixed except one, try every
(mode, level) for it, keep the best, move on; repeat until a full pass changes
nothing. Each candidate is scored on the same seeds (common random numbers),
so differences between candidates are not just different luck.
"""

import math
import os
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field, replace

from .model import LOCAL, MODES, Domain, Outcome, Policy, World, simulate

Arrangement = dict[str, Policy]


def candidates(domain: Domain) -> list[Policy]:
    out = [LOCAL]
    if domain.private_costs:
        # Regulation, not spending: quantity standards and floors, or a carbon price,
        # uniform or as a floor provinces may exceed. Grants don't apply.
        levels = [round(0.1 * k, 3) for k in range(1, 13)]
        prices = [round(0.2 * k, 3) for k in range(1, 13)]
        out += [Policy("central", lv) for lv in levels] + [Policy("floor", lv) for lv in levels]
        out += [Policy("price", t) for t in prices] + [Policy("price_floor", t) for t in prices]
        return out
    if domain.kind == "public_good":
        levels = [round(0.1 * k, 3) for k in range(13)]  # 0.0 .. 1.2
        for mode in ("central", "floor", "ceiling"):
            out += [Policy(mode, lv) for lv in levels]
        out += [Policy("matched", round(0.1 * k, 3)) for k in range(1, 10)]
        out += [Policy("equalized", q) for q in (0.25, 0.5, 0.75, 1.0)]
        if domain.two_tier:
            # Cities decide, optionally with a federal grant covering a share of their cost.
            out += [Policy("city", m) for m in (0.0, 0.1, 0.2, 0.3, 0.5)]
    else:
        levels = [round(0.05 * k, 3) for k in range(17)]  # 0.0 .. 0.8
        for mode in ("central", "floor", "ceiling"):
            out += [Policy(mode, lv) for lv in levels]
    return out


def refinements(domain: Domain, best: Policy) -> list[Policy]:
    if best.mode == "local":
        return []
    step = 0.025
    top = 0.95 if best.mode in ("matched", "city") else 1.0 if best.mode == "equalized" else 3.0 if best.mode.startswith("price") else (1.5 if domain.kind == "public_good" else 0.9)
    levels = {round(min(max(best.level + k * step, 0.0), top), 4) for k in (-2, -1, 1, 2)}
    return [Policy(best.mode, lv) for lv in sorted(levels - {best.level})]


def _key(arrangement: Arrangement) -> tuple:
    return tuple(sorted((k, p.mode, p.level) for k, p in arrangement.items() if p != LOCAL))


def _task(args) -> Outcome:
    world, items, seed = args
    return simulate(world, dict(items), seed)


@dataclass
class Score:
    arrangement: Arrangement
    welfare: float
    se: float
    outcomes: list[Outcome] = field(repr=False, default_factory=list)

    def mean(self, attr: str, key: str | None = None) -> float:
        if key is None:
            return sum(getattr(o, attr) for o in self.outcomes) / len(self.outcomes)
        return sum(getattr(o, attr).get(key, 0.0) for o in self.outcomes) / len(self.outcomes)


class Evaluator:
    """Scores arrangements over a fixed set of seeds, in parallel, with a cache."""

    def __init__(self, world: World, seeds: list[int], pool: ProcessPoolExecutor):
        self.world = world
        self.seeds = seeds
        self.pool = pool
        self.cache: dict[tuple, Score] = {}
        self.runs = 0

    def score(self, arrangements: list[Arrangement]) -> list[Score]:
        todo = []
        for arr in arrangements:
            k = _key(arr)
            if k not in self.cache and k not in [t[0] for t in todo]:
                todo.append((k, arr))
        tasks = [
            (self.world, tuple(sorted(arr.items())), seed)
            for _, arr in todo for seed in self.seeds
        ]
        if tasks:
            chunk = max(1, len(tasks) // (8 * (os.cpu_count() or 1)))
            results = list(self.pool.map(_task, tasks, chunksize=chunk))
            self.runs += len(tasks)
            n = len(self.seeds)
            for j, (k, arr) in enumerate(todo):
                outs = results[j * n:(j + 1) * n]
                ws = [o.welfare for o in outs]
                mu = sum(ws) / n
                se = math.sqrt(sum((w - mu) ** 2 for w in ws) / (n - 1) / n) if n > 1 else 0.0
                self.cache[k] = Score(dict(arr), mu, se, outs)
        return [self.cache[_key(arr)] for arr in arrangements]


@dataclass
class SearchResult:
    best: Score
    passes: int
    # For each domain, the best score reachable with each mode while every
    # other domain stays at the optimum: how much getting it wrong costs.
    by_mode: dict[str, dict[str, Score]]
    trace: list[str]


def coordinate_descent(ev: Evaluator, max_passes: int = 4, log=print) -> SearchResult:
    world = ev.world
    current: Arrangement = {d.name: LOCAL for d in world.domains}
    trace = []
    by_mode: dict[str, dict[str, Score]] = {}
    passes = 0

    for passes in range(1, max_passes + 1):
        changed = False
        for d in world.domains:
            options = candidates(d)
            if current[d.name] not in options:
                options.append(current[d.name])
            scores = ev.score([{**current, d.name: p} for p in options])
            best = max(scores, key=lambda s: s.welfare)
            extra = ev.score([{**current, d.name: p} for p in refinements(d, best.arrangement[d.name])])
            scores += extra
            best = max(scores, key=lambda s: s.welfare)

            table: dict[str, Score] = {}
            for s in scores:
                mode = s.arrangement[d.name].mode
                if mode not in table or s.welfare > table[mode].welfare:
                    table[mode] = s
            by_mode[d.name] = table

            chosen = best.arrangement[d.name]
            if chosen != current[d.name]:
                msg = f"pass {passes}: {d.name}: {current[d.name].label()} -> {chosen.label()} (welfare {best.welfare:.4f})"
                trace.append(msg)
                log("  " + msg)
                current = {**current, d.name: chosen}
                changed = True
        if not changed:
            break

    # by_mode tables from the last pass were built while later domains could still
    # change; rebuild each against the final optimum so they are comparable.
    for d in world.domains:
        options = candidates(d) + [current[d.name]]
        scores = ev.score([{**current, d.name: p} for p in options])
        table = {}
        for s in scores:
            mode = s.arrangement[d.name].mode
            if mode not in table or s.welfare > table[mode].welfare:
                table[mode] = s
        by_mode[d.name] = table

    best = ev.score([current])[0]
    return SearchResult(best, passes, by_mode, trace)


def best_single(ev: Evaluator, domain: Domain) -> tuple[Score, dict[str, Score]]:
    """Grid-search one domain in a one-domain world; return the winner and per-mode bests."""
    scores = ev.score([{domain.name: p} for p in candidates(domain)])
    table: dict[str, Score] = {}
    for s in scores:
        mode = s.arrangement[domain.name].mode
        if mode not in table or s.welfare > table[mode].welfare:
            table[mode] = s
    winner = max(scores, key=lambda s: s.welfare)
    return winner, table


def single_domain_world(base: World, domain: Domain, **world_changes) -> World:
    return replace(base, domains=(domain,), **world_changes)


def make_pool(workers: int | None = None) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=workers or os.cpu_count())


__all__ = [
    "Arrangement", "Evaluator", "MODES", "Score", "SearchResult", "best_single",
    "candidates", "coordinate_descent", "make_pool", "single_domain_world",
]
