"""Measure calibration targets from Statistics Canada tables.

    python3 -m tiebout.canada            # reads data/raw/, writes data/targets.json

Every target is computed for the ten provinces (territories excluded: tiny
populations and very different costs) and averaged over 2015-2024.

Regional disagreement is the hard one. Differences in what provinces spend mix
what people want with what things cost and what a province can afford, so it is
measured three ways and the spread between them is reported:

  levels    coefficient of variation of per-capita spending
  shares    coefficient of variation of the function's share of the budget
            (a rich province spends more on everything; shares cancel that)
  residual  spread of log per-capita spending after removing the part
            explained by provincial GDP per capita
  per_child (schools only) spending per resident aged 5 to 17, so provinces
            with more children are not mistaken for provinces that care more

In the model, a region left alone provides p = taste * (1 - s) / price, so the
spread of provision across regions is the spread of tastes: CV(p) = sd / 0.5.
What a province *spends* is the model's cost, which grows with p squared, so
CV(spending) = 2 CV(p). Hence heterogeneity = CV(spending) / 4.
(An earlier version used CV / 2, overstating disagreement by a factor of two.)
"""

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean, pstdev

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
YEARS = [str(y) for y in range(2015, 2025)]
PROVINCES = [
    "Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick",
    "Quebec", "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia",
]
FUNCTIONS = {
    "schools": "Primary and secondary education [7092]",
    "environment": "Environmental protection [705]",
    "transit": "Transport [7045]",
    "social protection": "Social protection [710]",
}
TOP_LEVEL = [
    "General public services [701]", "Defence [702]", "Public order and safety [703]",
    "Economic affairs [704]", "Environmental protection [705]", "Housing and community amenities [706]",
    "Health [707]", "Recreation, culture and religion [708]", "Education [709]", "Social protection [710]",
]


def rows(name: str):
    with open(RAW / name, encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def value(r) -> float | None:
    try:
        return float(r["VALUE"])
    except (TypeError, ValueError):
        return None


def cv(xs: list[float]) -> float:
    return pstdev(xs) / mean(xs)


def population() -> dict[tuple[str, str], float]:
    """July 1 (Q3) population by (province, year)."""
    out = {}
    for r in rows("17100009.csv"):
        if r["GEO"] in PROVINCES and r["REF_DATE"][:4] in YEARS and r["REF_DATE"][5:7] == "07":
            out[(r["GEO"], r["REF_DATE"][:4])] = value(r)
    return out


def school_age(pop) -> dict[tuple[str, str], float]:
    """Population aged 5 to 17 (roughly K-12) by (province, year), July 1."""
    ages = {f"{a} years" for a in range(5, 18)}
    out: dict[tuple[str, str], float] = defaultdict(float)
    for r in rows("17100005.csv"):
        if (r["GEO"] in PROVINCES and r["REF_DATE"] in YEARS and r["Gender"] == "Total - gender"
                and r["Age group"] in ages):
            v = value(r)
            if v is not None:
                out[(r["GEO"], r["REF_DATE"])] += v
    return dict(out)


def gdp_per_capita(pop) -> dict[tuple[str, str], float]:
    out = {}
    for r in rows("36100222.csv"):
        if (r["GEO"] in PROVINCES and r["REF_DATE"] in YEARS and r["Prices"] == "Current prices"
                and r["Estimates"] == "Gross domestic product at market prices"):
            v = value(r)
            if v is not None:
                out[(r["GEO"], r["REF_DATE"])] = v * 1e6 / pop[(r["GEO"], r["REF_DATE"])]
    return out


def spending() -> dict[tuple[str, str, str], float]:
    """Consolidated provincial-territorial and local spending, $, by (province, year, function)."""
    out = {}
    wanted = set(FUNCTIONS.values()) | set(TOP_LEVEL)
    for r in rows("10100005.csv"):
        if (r["GEO"] in PROVINCES and r["REF_DATE"] in YEARS
                and r["Public sector components"] == "Consolidated provincial-territorial and local governments"
                and r["Canadian Classification of Functions of Government (CCOFOG)"] in wanted):
            v = value(r)
            if v is not None:
                out[(r["GEO"], r["REF_DATE"], r["Canadian Classification of Functions of Government (CCOFOG)"])] = v * 1e6
    return out


def ols_residual_sd(y: list[float], x: list[float]) -> float:
    mx, my = mean(x), mean(y)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    resid = [c - (my + b * (a - mx)) for a, c in zip(x, y)]
    return math.sqrt(sum(e * e for e in resid) / (len(resid) - 2))  # two fitted parameters


def disagreement(pop, gdp, spend, kids) -> dict:
    out = {}
    for key, fn in FUNCTIONS.items():
        per_year = defaultdict(list)
        for year in YEARS:
            per_cap, shares, logs, log_gdp, per_child = [], [], [], [], []
            for p in PROVINCES:
                total = sum(spend.get((p, year, t), 0.0) for t in TOP_LEVEL)
                s = spend.get((p, year, fn))
                if s is None or not total or (p, year) not in gdp:
                    break
                per_cap.append(s / pop[(p, year)])
                if (p, year) in kids:
                    per_child.append(s / kids[(p, year)])
                shares.append(s / total)
                logs.append(math.log(s / pop[(p, year)]))
                log_gdp.append(math.log(gdp[(p, year)]))
            else:
                per_year["levels"].append(cv(per_cap))
                per_year["shares"].append(cv(shares))
                per_year["residual"].append(ols_residual_sd(logs, log_gdp))
                if key == "schools" and len(per_child) == len(PROVINCES):
                    # Education need tracks the number of school-age children, not total population.
                    per_year["per_child"].append(cv(per_child))
                per_year["per_capita"].append(mean(per_cap))
        cvs = {m: mean(v) for m, v in per_year.items() if m != "per_capita"}
        out[key] = {
            "function": fn,
            "years": len(per_year["levels"]),
            "mean_per_capita": round(mean(per_year["per_capita"])),
            "cv": {m: round(v, 4) for m, v in cvs.items()},
            "heterogeneity": {m: round(v / 4, 4) for m, v in cvs.items()},
            "heterogeneity_range": [round(min(cvs.values()) / 4, 4), round(max(cvs.values()) / 4, 4)],
        }
    return out


def inequality() -> dict:
    """Gini of adjusted market income (before taxes and transfers), Canada, mapped to a log-normal sd."""
    ginis = {}
    for r in rows("11100134.csv"):
        if r["GEO"] == "Canada" and r["REF_DATE"] in YEARS and r["Income concept"] in (
                "Adjusted market income", "Adjusted after-tax income"):
            v = value(r)
            if v is not None:
                ginis.setdefault(r["Income concept"], []).append(v)
    market = mean(ginis["Adjusted market income"])
    after = mean(ginis["Adjusted after-tax income"])
    # For a log-normal, Gini = 2 * Phi(sigma / sqrt 2) - 1.
    sigma = math.sqrt(2) * NormalDist().inv_cdf((market + 1) / 2)
    return {"market_gini": round(market, 4), "after_tax_gini": round(after, 4), "income_sigma": round(sigma, 4)}


def migration(pop) -> dict:
    """Interprovincial migrants between the ten provinces as a share of their population, per year."""
    by_year = defaultdict(float)
    for r in rows("17100022.csv"):
        origin = r["GEO"].replace(", province of origin", "")
        dest = r["Geography, province of destination"].replace(", province of destination", "")
        year = r["REF_DATE"][:4]  # REF_DATE like 2019/2020 is the July-June year; key on its start
        if origin in PROVINCES and dest in PROVINCES and origin != dest and year in YEARS:
            v = value(r)
            if v:
                by_year[year] += v
    rates = [by_year[y] / sum(pop[(p, y)] for p in PROVINCES) for y in YEARS if by_year.get(y)]
    return {"annual_rate": round(mean(rates), 5), "min": round(min(rates), 5), "max": round(max(rates), 5), "years": len(rates)}


def regional_income(gdp) -> dict:
    """How far apart provincial incomes are.

    GDP per person overstates it (resource profits mostly don't reach residents),
    so the calibration target is household market income (table 11-10-0190):
    average market income of economic families and unattached individuals.
    """
    cvs = [cv([gdp[(p, y)] for p in PROVINCES]) for y in YEARS if all((p, y) in gdp for p in PROVINCES)]
    market = defaultdict(dict)
    for r in rows("11100190.csv"):
        if (r["GEO"] in PROVINCES and r["REF_DATE"] in YEARS
                and r["Economic family type"] == "Economic families and persons not in an economic family"
                and r["Income concept"] in ("Average market income", "Median market income")):
            v = value(r)
            if v is not None:
                market[(r["REF_DATE"], r["Income concept"])][r["GEO"]] = v
    avg_cvs = [cv(list(market[(y, "Average market income")].values())) for y in YEARS
               if len(market[(y, "Average market income")]) == len(PROVINCES)]
    median_to_mean = {
        p: round(mean(market[(y, "Median market income")][p] / market[(y, "Average market income")][p]
                      for y in YEARS if p in market[(y, "Median market income")] and p in market[(y, "Average market income")]), 4)
        for p in PROVINCES
    }
    return {
        "gdp_per_capita_cv": round(mean(cvs), 4),
        "market_income_cv": round(mean(avg_cvs), 4),
        "market_income_cv_range": [round(min(avg_cvs), 4), round(max(avg_cvs), 4)],
        "median_to_mean_market_income": median_to_mean,
        "years": len(avg_cvs),
    }


def main() -> None:
    pop = population()
    gdp = gdp_per_capita(pop)
    spend = spending()
    kids = school_age(pop)
    targets = {
        "source": "Statistics Canada tables 10-10-0005, 11-10-0134, 11-10-0190, 17-10-0005, 17-10-0009, 17-10-0022, 36-10-0222; ten provinces, 2015-2024",
        "disagreement": disagreement(pop, gdp, spend, kids),
        "inequality": inequality(),
        "migration": migration(pop),
        "regional_income": regional_income(gdp),
    }
    ces = ROOT / "data" / "ces_disagreement.json"
    if ces.exists():
        # Survey (2019 Canadian Election Study): between-province spread in units of
        # within-province spread, from data/scripts/ces_disagreement.py.
        targets["survey"] = {k: {"rho": v["rho"], "respondents": v["respondents"], "question": v["question"]}
                             for k, v in json.loads(ces.read_text()).items()}
    out = ROOT / "data" / "targets.json"
    out.write_text(json.dumps(targets, indent=2))
    print(json.dumps(targets, indent=2))


if __name__ == "__main__":
    main()
