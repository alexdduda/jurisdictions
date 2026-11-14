"""Australia's inputs in the shape of data/targets.json, for the cross-country test.

Same measures as tiebout/canada.py and data/scripts/us_targets.py, on the six
states (the two territories are left out, as Canada's are), financial years
2015-16 to 2024-25:

  disagreement   state plus local general government expenses by purpose
                 (COFOG-A), ABS Government Finance Statistics, Annual, 2024-25
                 (5512.0, workbooks 55120DO003-010 state, 012-018 local, table 4):
                   schools      pre-primary, primary and secondary education (state;
                                local councils don't split education, and spend little)
                   environment  environmental protection (state + local)
                   transit      transport (state + local)
                   health       health (state + local)
                 Spread across states as levels per person, shares of total
                 expenses, and residual of log spending per person on log GSP per
                 person; heterogeneity = cv / 4 as for Canada. Like Canada's figures
                 these include spending paid for by Commonwealth grants.
  inequality     market-income Gini, OECD Income Distribution Database (AUS)
  migration      interstate departures from the six states over their population,
                 ABS National, state and territory population (3101.0, tables 16B, 4)
  regional_income  cv across states of household primary income (before
                 transfers) per person, ABS State Accounts (5220.0, household income
                 accounts)
  capacity       slope of log spending per person on log GSP per person (5220.0 table 1)
  emissions      log sd across the five mainland states of 2023-24 emissions per
                 person including land use (DCCEEW State and Territory Greenhouse Gas
                 Inventories 2024). Tasmania is left out: its forests make its net
                 emissions negative, so it has no log.

    python3 data/scripts/au_targets.py    # writes data/au/targets.json
"""

import csv
import datetime
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean, pstdev
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw" / "au"
STATES = {"NSW": "New South Wales", "VIC": "Victoria", "QLD": "Queensland", "SA": "South Australia",
          "WA": "Western Australia", "TAS": "Tasmania"}
STATE_BOOK = {"NSW": 3, "VIC": 4, "QLD": 5, "SA": 6, "WA": 7, "TAS": 8}
LOCAL_BOOK = {"NSW": 12, "VIC": 13, "QLD": 14, "SA": 15, "WA": 16, "TAS": 17}
YEARS = [f"{y}-{(y + 1) % 100:02d}" for y in range(2015, 2025)]
STATE_LINES = {"schools": ["Pre-primary, primary and secondary education"], "environment": ["Environmental protection"],
               "transit": ["Total transport"], "health": ["Total health"], "total": ["Total Expenses"]}
LOCAL_LINES = {"environment": ["Environmental Protection"], "transit": ["Transport"], "health": ["Health"],
               "total": ["Total Expenses"]}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xlsx_rows(path, sheet=1):
    z = zipfile.ZipFile(path)
    strings = [''.join(t.text or '' for t in si.iter(f"{{{NS['m']}}}t"))
               for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)] \
        if "xl/sharedStrings.xml" in z.namelist() else []
    rows = []
    for r in ET.fromstring(z.read(f"xl/worksheets/sheet{sheet}.xml")).iter(f"{{{NS['m']}}}row"):
        vals = {}
        for c in r.findall("m:c", NS):
            n = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group():
                n = n * 26 + ord(ch) - 64
            v = c.find("m:v", NS)
            if v is not None:
                vals[n - 1] = strings[int(v.text)] if c.get("t") == "s" else v.text
        if vals:
            rows.append([vals.get(i) for i in range(max(vals) + 1)])
    return rows


def gfs(book: int, lines: dict) -> dict:
    """{(key, year): $m} from table 4 (sheet 5) of one GFS workbook."""
    rows = xlsx_rows(RAW / "gfs" / f"55120DO{book:03d}_202425.xlsx", 5)
    head = next(r for r in rows if r and any(str(x).strip() == "2015-16" for x in r if x))
    cols = {str(x).strip(): i for i, x in enumerate(head) if x}
    want = {line: key for key, ls in lines.items() for line in ls}
    out = {}
    for r in rows:
        if not r or r[0] is None:
            continue
        label = str(r[0]).strip()
        if label in want:
            for y in YEARS:
                out[(want[label], y)] = float(r[cols[y]]) * 1e6
    return out


def fy(serial: str) -> str:
    """Excel date serial -> financial year label for a June observation."""
    d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(serial)))
    return f"{d.year - 1}-{d.year % 100:02d}" if d.month <= 6 else f"{d.year}-{(d.year + 1) % 100:02d}"


def series(path, match, sheet=2, months=(6,)) -> dict:
    """{(state code, financial year): value} for columns whose header contains `match` and a state name.
    With several months (quarterly data summed over a year) give months=(9, 12, 3, 6)."""
    rows = xlsx_rows(path, sheet)
    head = rows[0]
    cols = {}
    for i, h in enumerate(head):
        h = str(h or "")
        if match in h:
            for code, name in STATES.items():
                if f"; {name} ;" in h.replace("  ", " ") or h.startswith(f"{name} ;"):
                    cols[code] = i
    out = defaultdict(float)
    for r in rows[10:]:
        if not r or not r[0] or not re.match(r"^\d+(\.\d+)?$", str(r[0])):
            continue
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(float(r[0])))
        if d.month not in months:
            continue
        year = fy(r[0])
        for code, i in cols.items():
            if i < len(r) and r[i] not in (None, ""):
                out[(code, year)] += float(r[i])
    return dict(out)


def cv(xs):
    return pstdev(xs) / mean(xs)


def ols_residual_sd(y, x):
    mx, my = mean(x), mean(y)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    resid = [c - (my + b * (a - mx)) for a, c in zip(x, y)]
    return math.sqrt(sum(e * e for e in resid) / (len(resid) - 2))


def main() -> dict:
    spend = defaultdict(float)
    for s in STATES:
        for (k, y), v in gfs(STATE_BOOK[s], STATE_LINES).items():
            spend[(s, y, k)] += v
        for (k, y), v in gfs(LOCAL_BOOK[s], LOCAL_LINES).items():
            spend[(s, y, k)] += v
    pop = series(RAW / "pop" / "310104.xlsx", "Estimated Resident Population ;  Persons")
    gsp = series(RAW / "accounts" / "5220001.xlsx", "Gross state product: Current prices ;")
    gsp_pc = {k: v * 1e6 / pop[k] for k, v in gsp.items() if k in pop}
    years = [y for y in YEARS if all((s, y) in pop and (s, y) in gsp_pc for s in STATES)]
    out = {"source": "ABS 5512.0 (GFS 2024-25), 3101.0, 5220.0; OECD IDD; DCCEEW state inventories 2024; "
                     "six states, " + f"{years[0]} to {years[-1]}", "disagreement": {}, "fiscal_capacity": {}}
    for key in ("schools", "environment", "transit", "health"):
        per, slopes = defaultdict(list), []
        for y in years:
            pc = [spend[(s, y, key)] / pop[(s, y)] for s in STATES]
            sh = [spend[(s, y, key)] / spend[(s, y, "total")] for s in STATES]
            lg = [math.log(v) for v in pc]
            lx = [math.log(gsp_pc[(s, y)]) for s in STATES]
            per["levels"].append(cv(pc))
            per["shares"].append(cv(sh))
            per["residual"].append(ols_residual_sd(lg, lx))
            mx, my = mean(lx), mean(lg)
            slopes.append(sum((a - mx) * (b - my) for a, b in zip(lx, lg)) / sum((a - mx) ** 2 for a in lx))
            per["per_capita"].append(mean(pc))
        cvs = {m: mean(v) for m, v in per.items() if m != "per_capita"}
        out["disagreement"][key] = {"years": len(years), "mean_per_capita": round(mean(per["per_capita"])),
                                    "cv": {m: round(v, 4) for m, v in cvs.items()},
                                    "heterogeneity_range": [round(min(cvs.values()) / 4, 4), round(max(cvs.values()) / 4, 4)]}
        out["fiscal_capacity"][key] = {"income_elasticity": round(mean(slopes), 3), "years": len(slopes)}
    gini = [float(r["OBS_VALUE"]) for r in csv.DictReader(open(RAW / "oecd" / "idd.csv"))
            if r["MEASURE"] == "INC_MRKT_GINI" and r["AGE"] == "_T" and int(r["TIME_PERIOD"]) >= 2014]
    g = mean(gini)
    out["inequality"] = {"market_gini": round(g, 4), "income_sigma": round(math.sqrt(2) * NormalDist().inv_cdf((g + 1) / 2), 4),
                         "years": len(gini)}
    dep = series(RAW / "pop" / "3101016B.xlsx", "Interstate Departures", months=(9, 12, 3, 6))
    rates = [sum(dep[(s, y)] for s in STATES) / sum(pop[(s, y)] for s in STATES) for y in years if all((s, y) in dep for s in STATES)]
    out["migration"] = {"annual_rate": round(mean(rates), 5), "min": round(min(rates), 5), "max": round(max(rates), 5),
                        "years": len(rates)}
    primary = {}
    for s in STATES:
        rows = xlsx_rows(RAW / "accounts" / f"household_{s}.xlsx", 2)
        col = next(i for i, h in enumerate(rows[0]) if h and "Total primary income receivable" in str(h))
        for r in rows[10:]:
            if r and r[0] and re.match(r"^\d+(\.\d+)?$", str(r[0])) and col < len(r) and r[col]:
                y = fy(r[0])
                if (s, y) in pop:
                    primary[(s, y)] = float(r[col]) * 1e6 / pop[(s, y)]
    mcv = [cv([primary[(s, y)] for s in STATES]) for y in years if all((s, y) in primary for s in STATES)]
    out["regional_income"] = {"market_income_cv": round(mean(mcv), 4),
                              "market_income_cv_range": [round(min(mcv), 4), round(max(mcv), 4)],
                              "gdp_per_capita_cv": round(mean(cv([gsp_pc[(s, y)] for s in STATES]) for y in years), 4),
                              "years": len(mcv)}
    with (RAW / "emissions" / "per_capita_2021_2024.csv").open() as f:
        rows = [r for r in csv.DictReader(line for line in f if not line.startswith("#"))]
    last = next(r for r in rows if r["year"] == "2023-24")
    logs = [math.log(float(last[s])) for s in ("NSW", "VIC", "QLD", "SA", "WA")]
    out["emissions_spread"] = {"year": "2023-24", "log_sd": round(pstdev(logs), 3),
                               "measure": "emissions per person including land use, five mainland states"}
    (ROOT / "data" / "au").mkdir(exist_ok=True)
    (ROOT / "data" / "au" / "targets.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
