"""Validation: what drives migration, and does income drive provincial spending?

Two predictions of the model, neither fitted during calibration:

1. Migration. Agents in the model move only for public services and to avoid
   crowding; there are no wages. So net migration into a province should
   track its public spending, not its income.
2. Fiscal capacity. Every region starts equally rich and sets spending from
   tastes alone. So richer provinces should not spend more per person.

    python3 validation/migration_and_capacity.py

Data: Statistics Canada 17-10-0022 (interprovincial migration), 17-10-0009
(population), 36-10-0222 (GDP), 10-10-0005 (spending by function), ten
provinces, 2008-2024.
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tiebout.canada as ca  # noqa: E402

YEARS = [str(y) for y in range(2008, 2025)]
ca.YEARS = YEARS  # the loaders read the module-level year list
P = ca.PROVINCES
FUNCTIONS = {
    "schools": "Primary and secondary education [7092]",
    "environment": "Environmental protection [705]",
    "transit": "Transport [7045]",
    "social protection": "Social protection [710]",
    "health": "Health [707]",
}


def net_migration(pop):
    """Net interprovincial migration rate by (province, year); the July-June year keyed on its start."""
    inflow, outflow = defaultdict(float), defaultdict(float)
    for r in ca.rows("17100022.csv"):
        o = r["GEO"].replace(", province of origin", "")
        d = r["Geography, province of destination"].replace(", province of destination", "")
        y = r["REF_DATE"][:4]
        if o in P and d in P and o != d and y in YEARS:
            v = ca.value(r) or 0.0
            outflow[(o, y)] += v
            inflow[(d, y)] += v
    return {(p, y): (inflow[(p, y)] - outflow[(p, y)]) / pop[(p, y)]
            for p in P for y in YEARS if (p, y) in pop and ((p, y) in inflow or (p, y) in outflow)}


def demean_by_year(d):
    """Remove each year's cross-province mean, so common shocks don't masquerade as effects."""
    out = {}
    for y in YEARS:
        vals = [d[(p, y)] for p in P if (p, y) in d]
        if len(vals) == len(P):
            m = mean(vals)
            out.update({(p, y): d[(p, y)] - m for p in P})
    return out


def demean_by_province(d):
    """Remove each province's own average, leaving only its changes over time."""
    out = {}
    for p in P:
        keys = [k for k in d if k[0] == p]
        if keys:
            m = mean(d[k] for k in keys)
            out.update({k: d[k] - m for k in keys})
    return out


def standardize(xs):
    m, s = mean(xs), pstdev(xs)
    return [(x - m) / s for x in xs]


def ols(y, xs):
    """OLS of y on standardized regressors xs (list of columns). Returns coefficients and R^2."""
    k = len(xs)
    n = len(y)
    # Normal equations, small k: solve with Gaussian elimination.
    a = [[sum(xs[i][t] * xs[j][t] for t in range(n)) for j in range(k)] for i in range(k)]
    b = [sum(xs[i][t] * y[t] for t in range(n)) for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(a[r][c]))
        a[c], a[piv], b[c], b[piv] = a[piv], a[c], b[piv], b[c]
        for r in range(k):
            if r != c:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * z for x, z in zip(a[r], a[c])]
                b[r] -= f * b[c]
    beta = [b[i] / a[i][i] for i in range(k)]
    fit = [sum(beta[i] * xs[i][t] for i in range(k)) for t in range(n)]
    my = mean(y)
    r2 = 1 - sum((yt - ft) ** 2 for yt, ft in zip(y, fit)) / sum((yt - my) ** 2 for yt in y)
    return beta, r2


def migration_test(pop, gdp, spend):
    mig = net_migration(pop)
    log_gdp = {k: math.log(v) for k, v in gdp.items()}
    services = {}
    for p in P:
        for y in YEARS:
            parts = [spend.get((p, y, f)) for f in ("Primary and secondary education [7092]", "Health [707]", "Social protection [710]")]
            if all(v is not None for v in parts) and (p, y) in pop:
                services[(p, y)] = math.log(sum(parts) / pop[(p, y)])
    # Next year's migration on this year's conditions: people respond to what they see.
    keys = [(p, y) for p in P for y in YEARS[:-1]
            if (p, y) in log_gdp and (p, y) in services and (p, str(int(y) + 1)) in mig]
    def fit(g, s, m):
        ks = [k for k in keys if k in g and k in s and (k[0], str(int(k[1]) + 1)) in m]
        y = standardize([m[(p, str(int(yr) + 1))] for p, yr in ks])
        xg = standardize([g[k] for k in ks])
        xs = standardize([s[k] for k in ks])
        (bg, bs), r2 = ols(y, [xg, xs])
        return {
            "observations": len(ks),
            "standardized_effect_income": round(bg, 3),
            "standardized_effect_services": round(bs, 3),
            "r2_both": round(r2, 3),
            "r2_income_only": round(ols(y, [xg])[1], 3),
            "r2_services_only": round(ols(y, [xs])[1], 3),
        }

    # Between provinces: which kinds of province gain people (confounded by age, language, taxes).
    between = fit(demean_by_year(log_gdp), demean_by_year(services), demean_by_year(mig))
    # Within provinces: does a province gain people in years its own income or services rise?
    two_way = lambda d: demean_by_province(demean_by_year(d))
    within = fit(two_way(log_gdp), two_way(services), two_way(mig))
    return {
        "between_provinces": between,
        "within_provinces_over_time": within,
        "model_predicts": "services matter, income does not (the model has no wages)",
    }


def capacity_test(pop, gdp, spend):
    """Across provinces, slope of log spending per person on log GDP per person (an income elasticity)."""
    out = {}
    for key, fn in FUNCTIONS.items():
        slopes = []
        for y in YEARS:
            pts = [(math.log(gdp[(p, y)]), math.log(spend[(p, y, fn)] / pop[(p, y)]))
                   for p in P if (p, y) in gdp and (p, y, fn) in spend and spend[(p, y, fn)] > 0]
            if len(pts) == len(P):
                mx, my = mean(x for x, _ in pts), mean(v for _, v in pts)
                slopes.append(sum((x - mx) * (v - my) for x, v in pts) / sum((x - mx) ** 2 for x, _ in pts))
        out[key] = {"income_elasticity": round(mean(slopes), 3), "years": len(slopes),
                    "share_of_years_positive": round(sum(s > 0 for s in slopes) / len(slopes), 2)}
    out["model_predicts"] = "0 for every function (regions start equally rich)"
    return out


def main():
    pop = ca.population()
    gdp = ca.gdp_per_capita(pop)
    spend = ca.spending()
    result = {"migration": migration_test(pop, gdp, spend), "fiscal_capacity": capacity_test(pop, gdp, spend)}
    (ROOT / "validation" / "migration_and_capacity.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
