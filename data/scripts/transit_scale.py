"""Savings from size in bus operations, from the US National Transit Database.

The transit verdict turns on how much one national system would save over
separate city or provincial ones. Earlier versions took 0 to 10% from cost
studies (Abrate et al. 2016; Berechman and Giuliano's review). This measures it
directly: across US agencies, how operating cost per vehicle revenue hour of bus
service changes with how many hours an agency runs.

Data: NTD Annual Data - Metrics (data.transportation.gov dataset ekg5-frzt),
mode MB (bus), report years 2023 and 2024, full reporters, directly operated (DO)
or purchased transportation (PT) separately and pooled. Saved to
data/raw/us/ntd/metrics_bus_2023_2024.csv.

Regression, per year and type of service:

    log(cost per hour) = a + b log(vehicle revenue hours) + c log(urban area population)

The urban-area term holds local wages and congestion roughly fixed, since large
agencies sit in large, expensive cities. b < 0 means bigger operators run an
hour of bus service more cheaply. Merging k equal systems into one then saves
1 - k**b of operating cost. Canada's transit is run by dozens of agencies per
province; a national system would merge roughly the provinces' systems (k about
5 to 10 for systems of similar size). Firm size only: a national body would not
change the density of any city's network, which is what network-economy
studies find matters.

    python3 data/scripts/transit_scale.py      # writes data/transit_scale.json
"""

import csv
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw" / "us" / "ntd" / "metrics_bus_2023_2024.csv"


def ols(y, xs):
    """Coefficients (with intercept first) and standard errors, for a few regressors."""
    n, k = len(y), len(xs) + 1
    X = [[1.0] + [x[t] for x in xs] for t in range(n)]
    xtx = [[sum(X[t][i] * X[t][j] for t in range(n)) for j in range(k)] for i in range(k)]
    xty = [sum(X[t][i] * y[t] for t in range(n)) for i in range(k)]
    # Invert xtx (Gauss-Jordan).
    a = [row[:] + [1.0 if i == j else 0.0 for j in range(k)] for i, row in enumerate(xtx)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        f = a[c][c]
        a[c] = [v / f for v in a[c]]
        for r in range(k):
            if r != c:
                g = a[r][c]
                a[r] = [v - g * w for v, w in zip(a[r], a[c])]
    inv = [row[k:] for row in a]
    beta = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    resid = [y[t] - sum(beta[i] * X[t][i] for i in range(k)) for t in range(n)]
    s2 = sum(e * e for e in resid) / (n - k)
    se = [math.sqrt(s2 * inv[i][i]) for i in range(k)]
    return beta, se


def main() -> dict:
    rows = []
    with RAW.open() as f:
        for r in csv.DictReader(f):
            try:
                cost, hours, pop = float(r["total_operating_expenses"]), float(r["vehicle_revenue_hours"]), float(r["primary_uza_population"])
            except (ValueError, KeyError):
                continue
            if r["reporter_type"] != "Full Reporter" or cost <= 0 or hours < 1000 or pop <= 0:
                continue
            rows.append({"year": r["report_year"], "tos": r["type_of_service"], "cost_hour": cost / hours,
                         "hours": hours, "pop": pop})
    out = {"source": "NTD Annual Data - Metrics (ekg5-frzt), bus, full reporters, at least 1,000 revenue hours",
           "fits": {}}
    for year in ("2023", "2024"):
        for tos in ("DO", "PT", "all"):
            sub = [r for r in rows if r["year"] == year and (tos == "all" or r["tos"] == tos)]
            y = [math.log(r["cost_hour"]) for r in sub]
            beta, se = ols(y, [[math.log(r["hours"]) for r in sub], [math.log(r["pop"]) for r in sub]])
            out["fits"][f"{year} {tos}"] = {"n": len(sub), "b_size": round(beta[1], 4), "se_size": round(se[1], 4),
                                           "c_urban_pop": round(beta[2], 4), "se_urban_pop": round(se[2], 4)}
    bs = [v["b_size"] for k, v in out["fits"].items() if k.endswith("DO")]
    lo_b, hi_b = min(v["b_size"] - 2 * v["se_size"] for k, v in out["fits"].items() if k.endswith("DO")), \
        max(v["b_size"] + 2 * v["se_size"] for k, v in out["fits"].items() if k.endswith("DO"))
    out["directly_operated_b"] = {"mean": round(mean(bs), 4), "two_se_range": [round(lo_b, 4), round(hi_b, 4)]}
    # Saving from merging k similar systems: 1 - k**b (b < 0 saves, b > 0 costs).
    out["saving_from_merging"] = {str(k): {"central": round(1 - k ** mean(bs), 3),
                                           "range": [round(1 - k ** hi_b, 3), round(1 - k ** lo_b, 3)]}
                                  for k in (5, 10)}
    (ROOT / "data" / "transit_scale.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
