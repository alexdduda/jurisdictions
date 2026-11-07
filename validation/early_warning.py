"""What would change each verdict, and how close are we?

For every policy area, the numbers that decide it, the value at which the
verdict flips (read from the threshold maps in results/thresholds.json, so it
stays in sync with them), the best current estimate, and the data release that
would move it. Where an official projection exists, the projected value is
given too (data/projections/).

    python3 validation/early_warning.py      # writes results/watchlist.json
"""

import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def flip(m: dict, mode: str, along: str, at=None):
    """Smallest value along `along` ("rows" or "cols") where the winner is `mode`,
    on the row/column nearest `at` (or on every row/column if at is None)."""
    rows, cols, cells = m["rows"], m["cols"], m["cells"]
    if along == "cols":
        lines = [cells[rows.index(min(rows, key=lambda r: abs(r - at)))]] if at is not None else cells
        axis = cols
    else:
        idx = [cols.index(min(cols, key=lambda c: abs(c - at)))] if at is not None else range(len(cols))
        lines = [[cells[i][j] for i in range(len(rows))] for j in idx]
        axis = rows
    out = []
    for line in lines:
        hit = [axis[k] for k, c in enumerate(line) if c["mode"] == mode]
        out.append(min(hit) if hit else None)
    return out


def log_spread(rows, key):
    v = [math.log(float(r[key])) for r in rows]
    mu = sum(v) / len(v)
    return math.sqrt(sum((x - mu) ** 2 for x in v) / len(v))


def main() -> dict:
    maps = json.loads((ROOT / "results" / "thresholds.json").read_text())["maps"]
    emis = list(csv.DictReader((ROOT / "data" / "projections" / "eccc_2025_per_capita.csv").open()))
    spread = {k: round(log_spread(emis, k), 2) for k in ("2023", "2030_wm", "2035_wm", "2030_wam", "2035_wam")}

    # Ratio of provincial to federal excess cost of raising a dollar (MCF - 1).
    # Dahlby and Ferede: federal personal income tax MCF 2.86 (2021); provincial
    # 1.44 to 3.81 (2006). Not the same year or method, hence a range.
    fed = 2.86 - 1
    ratio_lo, ratio_hi = round((1.44 - 1) / fed, 2), round((3.81 - 1) / fed, 2)

    env = maps["environment"]
    sch = maps["schools"]
    env_mid = env["held_at"].get("spillover")
    sch_mid = sch["held_at"].get("spillover", 0.05)
    env_nat = flip(env, "central", "cols", at=0.6 if env_mid is None else env_mid)[0]
    sch_nat = flip(sch, "central", "cols", at=sch_mid)[0]
    scale_nat = flip(maps["transit_scale"], "central", "rows", at=0.1)[0]
    city_zero = flip(maps["transit"], "city", "cols", at=0.3)[0]
    price_any = min(r for r, row in zip(maps["climate"]["rows"], maps["climate"]["cells"])
                    if all(c["mode"] in ("price", "price_floor") for c in row))
    red = maps["redistribution_inequality"]
    red_floor = [r for r, row in zip(red["rows"], red["cells"]) if any(c["mode"] == "floor" for c in row)]

    items = [
        {
            "area": "schools, environment",
            "number": "Provincial cost of raising a dollar relative to federal (excess burden ratio)",
            "flips": f"national standard for the environment from {env_nat}; for schools from {sch_nat}; provinces below that",
            "threshold": {"environment": env_nat, "schools": sch_nat},
            "current": f"{ratio_lo} to {ratio_hi} (Dahlby and Ferede: federal 2021, provincial 2006)",
            "status": "unknown: the published range spans both sides of both thresholds",
            "watch": "A matched-year, same-method estimate of the marginal cost of public funds for federal and provincial income taxes. No scheduled release.",
        },
        {
            "area": "transit",
            "number": "Saving from one national transit system over separate city or provincial systems",
            "flips": f"national from about {scale_nat:.0%}; below that, provinces (or cities)",
            "threshold": scale_nat,
            "current": "not measured for Canada",
            "status": "unknown",
            "watch": "Cost benchmarking of Canadian transit agencies by network size (for example the Canadian Urban Transit Association's annual fact book).",
        },
        {
            "area": "transit",
            "number": "Share of transit benefit carried by commuters across the metro boundary",
            "flips": "cities beat provinces only near zero; by 10% provinces win",
            "threshold": 0.1,
            "current": "below 50% by construction of metro boundaries; not measured",
            "status": "unknown, but the census can measure it",
            "watch": "2026 Census commuting-flow tables (place of residence by place of work), not yet scheduled.",
            "city_wins_at_zero_spillover_from_taste_gap": city_zero,
        },
        {
            "area": "climate",
            "number": "Spread of emissions per person across provinces (log standard deviation)",
            "flips": f"a carbon price beats a uniform quantity standard at any spread from {price_any}",
            "threshold": price_any,
            "current": f"{spread['2023']} (2023)",
            "projected": {
                "2030": f"{spread['2030_wm']} with current measures, {spread['2030_wam']} with additional measures",
                "2035": f"{spread['2035_wm']} with current measures, {spread['2035_wam']} with additional measures",
            },
            "status": f"safe through 2035: projected spread stays about {round(spread['2035_wm'] / price_any, 1)} times the threshold",
            "watch": "ECCC's annual emissions projections and National Inventory Report.",
        },
        {
            "area": "redistribution",
            "number": "Weight on inequality (elasticity of marginal utility of income)",
            "flips": f"a national floor provinces can top up starts to win from {min(red_floor) if red_floor else 'never'} (with low tax distortion)",
            "threshold": min(red_floor) if red_floor else None,
            "current": "1.26 (1.19 to 1.34; Layard, Mayraz and Nickell 2008)",
            "status": "safe",
            "watch": "New estimates from happiness or willingness-to-pay studies.",
        },
    ]
    out = {"items": items, "emissions_spread": spread}
    (ROOT / "results" / "watchlist.json").write_text(json.dumps(out, indent=2))
    for it in items:
        print(f"- {it['area']}: {it['number']}\n    flips: {it['flips']}\n    now: {it['current']} -> {it['status']}")
    return out


if __name__ == "__main__":
    main()
