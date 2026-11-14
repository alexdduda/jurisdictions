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

    # Ratio of provincial to federal excess cost of raising a dollar (MCF - 1), on
    # one basis: 2025 personal income tax, same formula, social cost
    # (validation/cost_of_funds.py). The published estimates (Dahlby and Ferede:
    # federal 2021, provincial 2006, the provinces' own view) implied 0.24 to 1.51.
    cof = json.loads((ROOT / "validation" / "cost_of_funds.json").read_text())["social_ratio"]
    ratio_lo, ratio_hi = cof["min"], cof["max"]
    canada_lo, canada_hi = cof["weighted_min"], cof["weighted_max"]

    env = maps["environment"]
    sch = maps["schools"]
    env_mid = env["held_at"].get("spillover")
    sch_mid = sch["held_at"].get("spillover", 0.05)
    # Environment spillover is now measured (data/environment_spillover.json): read the map at its midpoint.
    env_sp = json.loads((ROOT / "data" / "environment_spillover.json").read_text())["spillover_range"]
    env_mid = env_mid if env_mid is not None else round(sum(env_sp) / 2, 2)
    env_nat = flip(env, "central", "cols", at=env_mid)[0]
    health = maps.get("health")
    health_nat = flip(health, "central", "cols", at=0.0)[0] if health else None
    # Along spillover, at an excess-burden ratio near Canada's, where does a national standard start?
    env_by_spill = flip(env, "central", "rows", at=1.0)[0]
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
            "current": f"{canada_lo} to {canada_hi} for Canada as a whole; {ratio_lo} to {ratio_hi} province by province (2025 income tax, one method)",
            "status": (f"schools: below the threshold everywhere, so provinces with equalization; "
                       f"environment: at the threshold for Canada as a whole, so a near-tie: a national standard wins most sampled worlds, "
                       f"but a 20% matching grant loses least across them"),
            "watch": "Combined federal-provincial marginal rates (each budget) and new estimates of how taxable income responds to rates; sales and corporate taxes are not yet included.",
        },
        {
            "area": "environment",
            "number": "Share of provincial environmental spending's benefit felt in other provinces (spillover)",
            "flips": (f"at an excess-burden ratio of 1, a national standard wins from a spillover of {env_by_spill}; "
                      f"below a ratio of 1, provinces (with grants) win across the measured range"),
            "threshold": env_by_spill,
            "current": (f"{env_sp[0]} to {env_sp[1]}: waste and wastewater, whose benefits mostly stay home, are about "
                        "two thirds of the spending (table 10-10-0005); per-part spillovers are assumed"),
            "status": "the measured range is well below the 30% to 80% once assumed, so the case for a national standard now rests on the excess-burden ratio, not on spillover",
            "watch": "Studies of how far provincial water and air pollution crosses provincial lines; table 10-10-0005 each year for the spending mix.",
        },
        {
            "area": "health",
            "number": "Provincial cost of raising a dollar relative to federal (excess burden ratio), with no scale saving",
            "flips": f"national provision from a ratio of {health_nat}; matching grants or a floor below",
            "threshold": health_nat,
            "current": f"{canada_lo} to {canada_hi} for Canada as a whole",
            "status": "well below the threshold, so provinces with a small matching grant; the threshold falls as scale savings rise (national from a ratio of 1 with a 5% saving), which is why health has no clear winner",
            "watch": "The same tax-rate data as for schools; a Canadian estimate of administrative scale economies in health insurance.",
        },
        {
            "area": "transit",
            "number": "Saving from one national transit system over separate city or provincial systems",
            "flips": f"national from about {scale_nat:.0%}; below that, provinces (or cities)",
            "threshold": scale_nat,
            "current": "-10% to +5%: US bus operators' cost per vehicle-hour rises with size (elasticity +0.08 to +0.14, NTD 2023-2024, data/scripts/transit_scale.py); European studies find savings only for small operators (Abrate et al. 2016)",
            "status": "below the threshold, so provinces and their cities; no Canadian estimate yet",
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
