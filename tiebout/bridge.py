"""Translate between tiebout arrangements and scopelang programs.

    tiebout   scopelang
    local     shadow
    central   preempt
    floor     floor
    ceiling   ceiling
    matched   matched
    equalized equalized
    city      devolved
"""

from scopelang import run

from .model import LOCAL, Policy, World

TO_LAW = {"local": "shadow", "central": "preempt", "floor": "floor", "ceiling": "ceiling", "matched": "matched",
          "equalized": "equalized", "city": "devolved"}
FROM_LAW = {v: k for k, v in TO_LAW.items()}

COMMENTS = {
    "local": "regions decide",
    "central": "one national level everywhere",
    "floor": "regions decide, never below this",
    "ceiling": "regions decide, never above this",
    "matched": "regions decide; the nation pays this share of the cost",
    "equalized": "regions decide; the nation closes this share of poorer regions' capacity gap",
    "city": "cities decide, skipping the provinces; the nation pays this share of their cost",
    "price": "one national carbon price; provinces may not change it",
    "price_floor": "a national minimum carbon price; provinces may go higher",
}


def law_line(name: str, p: Policy) -> str:
    """A policy as a scopelang law. Carbon prices are laws on `<name>_price`:
    a uniform national price preempts, a price floor is a floor."""
    if p.mode == "price":
        return f"law {name}_price: preempt = {p.level:g}"
    if p.mode == "price_floor":
        return f"law {name}_price: floor = {p.level:g}"
    return f"law {name}: {TO_LAW[p.mode]}" + ("" if p.mode == "local" else f" = {p.level:g}")


def arrangement_to_jur(best, search, world: World) -> str:
    lines = [
        "# Best arrangement found by tiebout.",
        f"# Welfare {best.welfare:.4f} ± {best.se:.4f} over {len(best.outcomes)} seeds.",
        "# Re-score after editing: python -m tiebout evaluate results/best_arrangement.jur",
        "",
        "scope nation {",
    ]
    for d in world.domains:
        p = best.arrangement[d.name]
        decl = "  " + law_line(d.name, p)
        table = search.by_mode.get(d.name, {})
        rivals = sorted(
            ((m, s) for m, s in table.items() if m != p.mode),
            key=lambda item: -item[1].welfare,
        )
        note = COMMENTS[p.mode]
        if rivals:
            m, s = rivals[0]
            note += f"; next best: {s.arrangement[d.name].label()} ({(s.welfare - best.welfare) * 1000:+.1f} milli-utils)"
        lines.append(f"{decl:<40}# {note}")
    lines += [
        "",
        "  # A region trying to undercut a floor is struck down, e.g.:",
        "  # scope region_7 { environment = 0 }",
        "}",
    ]
    return "\n".join(lines) + "\n"


def jur_to_arrangement(source: str, world: World, scope: str = "nation") -> tuple[dict[str, Policy], list[str]]:
    """Read the laws a scope declares as an arrangement. Returns (arrangement, warnings)."""
    result = run(source)
    warnings = [str(d).strip() for d in result.diagnostics]
    if scope not in result.interp.scopes:
        raise ValueError(f"program has no scope named {scope!r}")
    known = {d.name for d in world.domains}
    arrangement = {d.name: LOCAL for d in world.domains}
    for name, (law, value) in result.laws(scope).items():
        if name.endswith("_price") and name[: -len("_price")] in known:
            area = name[: -len("_price")]
            if law not in ("preempt", "floor") or value is None:
                raise ValueError(f"law {name}: a carbon price is preempt or floor, with a value")
            arrangement[area] = Policy("price" if law == "preempt" else "price_floor", float(value))
            continue
        if name not in known:
            warnings.append(f"ignoring law {name}: not a domain in this world ({', '.join(sorted(known))})")
            continue
        mode = FROM_LAW[law]
        if mode == "local":
            arrangement[name] = LOCAL
            continue
        if value is None or isinstance(value, (bool, str)):
            raise ValueError(f"law {name}: {law} needs a numeric value")
        arrangement[name] = Policy(mode, float(value))
    return arrangement, warnings
