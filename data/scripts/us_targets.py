"""United States inputs in the shape of data/targets.json, for the cross-country test.

Same measures as tiebout/canada.py, on the 50 states (not DC, a city-state),
2017-2022:

  disagreement   state and local direct expenditure by function, Census Bureau
                 Annual Survey of State and Local Government Finances, table 1
                 (www2.census.gov/programs-surveys/gov-finances/tables/<year>/
                 <yy>slsstab1.xlsx). Spread across states as levels per person,
                 shares of direct general expenditure, and residual of log
                 spending per person on log GDP per person; heterogeneity = cv / 4
                 as for Canada. Functions matched to Canada's COFOG ones:
                   schools      elementary and secondary education
                   environment  sewerage + solid waste management (COFOG 705 is
                                waste, waste water, pollution and biodiversity;
                                the Census "natural resources" line is mostly
                                agriculture, forestry and fish and game)
                   transit      highways + air + parking + sea and inland port +
                                transit utility (COFOG 7045 is all transport)
                 Like Canada's consolidated provincial-local figures, these
                 include spending paid for by federal grants.
  inequality     market-income Gini, OECD Income Distribution Database (same
                 source gives Canada 0.43, matching Statistics Canada)
  migration      movers between states a year, Current Population Survey table
                 A-1 (Census Bureau), survey years 2017-2023
  regional_income  cv across states of market income per person: BEA SAINC4
                 net earnings by place of residence + dividends, interest and rent
                 (personal income less transfers), over population
  capacity       slope of log spending per person on log GDP per person (BEA
                 SAGDP1), as validation/migration_and_capacity.py
  emissions      log sd across states of energy CO2 per person, EIA table 4,
                 2022 (Canada's uses all greenhouse gases)

    python3 data/scripts/us_targets.py    # writes data/us/targets.json
"""

import csv
import json
import math
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean, pstdev
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw" / "us"
YEARS = [str(y) for y in range(2017, 2023)]
STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "Florida",
          "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine",
          "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska",
          "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
          "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas",
          "Utah", "Vermont", "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming"]
# Census line descriptions (matched after stripping) for each function.
FUNCTIONS = {
    "schools": ["Elementary & secondary"],
    "environment": ["Sewerage", "Solid waste management"],
    "transit": ["Highways", "Air transportation (airports)", "Parking facilities", "Sea and inland port facilities",
                "Transit"],
}
TOTAL = "Direct general expenditure"
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def cv(xs):
    return pstdev(xs) / mean(xs)


def xlsx_rows(path):
    """Rows of the first sheet as lists (stdlib only)."""
    z = zipfile.ZipFile(path)
    strings = [''.join(t.text or '' for t in si.iter(f"{{{NS['m']}}}t"))
               for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS)] \
        if "xl/sharedStrings.xml" in z.namelist() else []
    rows = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(f"{{{NS['m']}}}row"):
        vals = {}
        for c in r.findall("m:c", NS):
            n = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group():
                n = n * 26 + ord(ch) - 64
            v = c.find("m:v", NS)
            if v is not None:
                vals[n - 1] = strings[int(v.text)] if c.get("t") == "s" else v.text
            else:
                inline = c.find("m:is", NS)
                if inline is not None:
                    vals[n - 1] = ''.join(t.text or '' for t in inline.iter(f"{{{NS['m']}}}t"))
        if vals:
            rows.append([vals.get(i) for i in range(max(vals) + 1)])
    return rows


def spending():
    """$ by (state, year, function or TOTAL)."""
    out = {}
    for y in YEARS:
        rows = xlsx_rows(RAW / "census_finance" / f"{y[2:]}slsstab1.xlsx")
        header = next(r for r in rows if r and len(r) > 2 and r[2] and "United States" in str(r[2]))
        cols = {str(name).strip(): i for i, name in enumerate(header) if name and str(name).strip() in STATES}
        assert len(cols) == 50, (y, len(cols))
        wanted = {d: k for k, ds in FUNCTIONS.items() for d in ds}
        wanted[TOTAL] = TOTAL
        # Revenue lines repeat some names (sewerage, highways, transit charges); read
        # only from the expenditure-by-function block on. Transit is the utility line.
        on = False
        for r in rows:
            if len(r) < 2 or r[1] is None:
                continue
            desc = str(r[1]).strip()
            if desc.startswith("Direct expenditure by"):
                on = True
            if not on or desc not in wanted:
                continue
            key = wanted[desc]
            for s, i in cols.items():
                v = r[i] if i < len(r) else None
                if v not in (None, "", "-"):
                    out[(s, y, key)] = out.get((s, y, key), 0.0) + float(v) * 1000
    return out


def bea(name, line):
    path = next((RAW / "bea").glob(f"{name}__ALL_AREAS_*.csv"))
    out = {}
    with path.open(encoding="latin1") as f:
        for r in csv.DictReader(f):
            g = (r.get("GeoName") or "").strip().rstrip("*").strip()
            if g in STATES and r["LineCode"] == str(line):
                for y in YEARS:
                    try:
                        out[(g, y)] = float(r[y])
                    except (ValueError, KeyError):
                        pass
    return out


def ols_residual_sd(y, x):
    mx, my = mean(x), mean(y)
    b = sum((a - mx) * (c - my) for a, c in zip(x, y)) / sum((a - mx) ** 2 for a in x)
    resid = [c - (my + b * (a - mx)) for a, c in zip(x, y)]
    return math.sqrt(sum(e * e for e in resid) / (len(resid) - 2))


def main() -> dict:
    spend = spending()
    pop = bea("SAINC4", 20)
    gdp = {k: v * 1e6 / pop[k] for k, v in bea("SAGDP1", 3).items() if k in pop}
    market = {k: (bea("SAINC4", 45)[k] + bea("SAINC4", 46)[k]) * 1e6 / pop[k]
              for k in pop}
    out = {"source": "Census Bureau state and local finance table 1, BEA SAINC4 and SAGDP1, CPS A-1, OECD IDD, "
                     "EIA state CO2 table 4; 50 states, 2017-2022", "disagreement": {}}
    capacity = {}
    for key in FUNCTIONS:
        per = defaultdict(list)
        slopes = []
        for y in YEARS:
            pc = [spend[(s, y, key)] / pop[(s, y)] for s in STATES]
            sh = [spend[(s, y, key)] / spend[(s, y, TOTAL)] for s in STATES]
            lg = [math.log(v) for v in pc]
            lx = [math.log(gdp[(s, y)]) for s in STATES]
            per["levels"].append(cv(pc))
            per["shares"].append(cv(sh))
            per["residual"].append(ols_residual_sd(lg, lx))
            mx, my = mean(lx), mean(lg)
            slopes.append(sum((a - mx) * (b - my) for a, b in zip(lx, lg)) / sum((a - mx) ** 2 for a in lx))
            per["per_capita"].append(mean(pc))
        cvs = {m: mean(v) for m, v in per.items() if m != "per_capita"}
        out["disagreement"][key] = {
            "functions": FUNCTIONS[key], "years": len(YEARS), "mean_per_capita": round(mean(per["per_capita"])),
            "cv": {m: round(v, 4) for m, v in cvs.items()},
            "heterogeneity_range": [round(min(cvs.values()) / 4, 4), round(max(cvs.values()) / 4, 4)],
        }
        capacity[key] = {"income_elasticity": round(mean(slopes), 3), "years": len(slopes)}
    # Inequality (OECD, total population, market income).
    gini = [float(r["OBS_VALUE"]) for r in csv.DictReader(open(RAW / "oecd" / "idd.csv"))
            if r["REF_AREA"] == "USA" and r["MEASURE"] == "INC_MRKT_GINI" and r["AGE"] == "_T"
            and r["TIME_PERIOD"] in YEARS]
    g = mean(gini)
    out["inequality"] = {"market_gini": round(g, 4), "income_sigma": round(math.sqrt(2) * NormalDist().inv_cdf((g + 1) / 2), 4)}
    # Migration between states (CPS A-1: different state / total), survey years 2017-2023.
    rates = []
    for r in xlsx_rows(RAW / "cps" / "hst_mig_a_1.xlsx"):
        label = str(r[0] or "")
        m = re.match(r"(20\d\d)", label)
        if m and 2017 <= int(m.group(1)) <= 2023 and "2010 controls" not in label and len(r) > 8 and r[8]:
            rates.append(float(r[8]) / float(r[1]))
        if label.startswith("Percent"):
            break
    out["migration"] = {"annual_rate": round(mean(rates), 5), "min": round(min(rates), 5), "max": round(max(rates), 5),
                        "years": len(rates)}
    mcv = [cv([market[(s, y)] for s in STATES]) for y in YEARS]
    out["regional_income"] = {"market_income_cv": round(mean(mcv), 4),
                              "market_income_cv_range": [round(min(mcv), 4), round(max(mcv), 4)],
                              "gdp_per_capita_cv": round(mean(cv([gdp[(s, y)] for s in STATES]) for y in YEARS), 4)}
    out["fiscal_capacity"] = capacity
    rows = xlsx_rows(RAW / "eia" / "table4.xlsx")
    head = next(r for r in rows if r and r[0] == "State")
    col = head.index("2022")
    logs = [math.log(float(r[col])) for r in rows if r and r[0] in STATES]
    assert len(logs) == 50
    out["emissions_spread"] = {"year": "2022", "log_sd": round(pstdev(logs), 3), "measure": "energy CO2 per person"}
    (ROOT / "data" / "us").mkdir(exist_ok=True)
    (ROOT / "data" / "us" / "targets.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    main()
