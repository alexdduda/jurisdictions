"""How strongly each province's people side with their province against Ottawa.

The model treats a province as a bundle of preferences over services. Real
politics also has attachment: people who want their province, not Ottawa, to
decide, whatever the service. The Canadian Election Study asked three questions
that measure it, in the same respondents' province, with provincial weights:

  power      "Which do you prefer: a strong federal government or more power to
             the provincial governments?" (2008 PES_G13, 2011 PES11_55)
  treated    "In general, does the federal government treat your province better,
             worse, or about the same as other provinces?" (1997 cpsj12,
             2004 cps_p5, 2008 PES_P12, 2011 PES11_38)
  looks_after "Which government looks after your interests better, the federal
             government or the provincial government?" (2004 pes_d2, 2008 PES_F9)

For each, the share of answers on the provincial side minus the share on the
federal side, among those who chose a side or "the same/balanced" (don't know
and refused dropped), averaged over the years asked. `attachment` is the mean of
the three, a number from -1 (all side with Ottawa) to 1 (all with the province).

Also kept: who Canadians blamed for longer health waiting lists in 2004
(cps_f5b), the one question that asks about blame directly.

    python3 data/scripts/regional_attachment.py   # writes data/regional_attachment.json
"""

import csv
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw" / "ces"
PROVINCES = ["Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick", "Quebec",
             "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]
SGC = dict(zip(["10", "11", "12", "13", "24", "35", "46", "47", "48", "59"], PROVINCES))
# answer code -> +1 provincial side, -1 federal side, 0 middle
TREATED = {"1": -1, "5": 0, "3": 1}            # better / same / worse
POWER = {"1": -1, "3": 0, "6": 0, "5": 1}      # strong federal / both or balanced / more to provinces
LOOKS = {"1": -1, "5": 0, "3": 1}              # federal / not much difference / provincial
QUESTIONS = {
    "power": [("2008", "ces08_PROVINCE", "ces08_PROVWGT", "ces08_PES_G13", POWER),
              ("2011", "PROVINCE11", "PROVINCIAL_WEIGHT", "PES11_55", POWER)],
    "treated": [("1997", "province", "cpspwgt1", "cpsj12", TREATED),
                ("2004", "province", "cespwgt", "cps_p5", TREATED),
                ("2008", "ces08_PROVINCE", "ces08_PROVWGT", "ces08_PES_P12", TREATED),
                ("2011", "PROVINCE11", "PROVINCIAL_WEIGHT", "PES11_38", TREATED)],
    "looks_after": [("2004", "province", "cespwgt", "pes_d2", LOOKS),
                    ("2008", "ces08_PROVINCE", "ces08_PROVWGT", "ces08_PES_F9", LOOKS)],
}
BLAME = {"1": "federal", "3": "provincial", "6": "both", "5": "neither"}

_cache = {}


def load(year):
    if year not in _cache:
        csv.field_size_limit(10 ** 9)
        with open(RAW / year / f"ces{year}.tab", encoding="latin1") as f:
            _cache[year] = list(csv.DictReader(f, delimiter="\t"))
    return _cache[year]


def weight(r, wvar):
    w = (r.get(wvar) or "").strip()
    try:
        return float(w) if float(w) > 0 else 1.0
    except ValueError:
        return None


def main() -> dict:
    out = {"source": "Canadian Election Study 1997, 2004, 2008, 2011 (Borealis, CC BY-NC 4.0), provincial weights",
           "questions": {}, "provinces": {}}
    net = {q: {p: [] for p in PROVINCES} for q in QUESTIONS}
    for q, items in QUESTIONS.items():
        out["questions"][q] = {}
        for year, pvar, wvar, var, coding in items:
            tot = {p: {-1: 0.0, 0: 0.0, 1: 0.0} for p in PROVINCES}
            n = 0
            for r in load(year):
                p, a, w = SGC.get((r.get(pvar) or "").strip()), coding.get((r.get(var) or "").strip()), weight(r, wvar)
                if p and a is not None and w:
                    tot[p][a] += w
                    n += 1
            res = {}
            for p in PROVINCES:
                s = sum(tot[p].values())
                res[p] = round((tot[p][1] - tot[p][-1]) / s, 3)
                net[q][p].append(res[p])
            out["questions"][q][year] = {"variable": var, "respondents": n, "net_provincial": res}
            print(q, year, var, n, res, flush=True)
    for p in PROVINCES:
        each = {q: round(mean(net[q][p]), 3) for q in QUESTIONS}
        out["provinces"][p] = {**each, "attachment": round(mean(each.values()), 3)}
    blame = {}
    for r in load("2004"):
        a, w = BLAME.get((r.get("cps_f5b") or "").strip()), weight(r, "cespwgt")
        if a and w:
            blame[a] = blame.get(a, 0.0) + w
    s = sum(blame.values())
    out["health_waits_blame_2004"] = {k: round(v / s, 3) for k, v in blame.items()}
    (ROOT / "data" / "regional_attachment.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out["provinces"], indent=1), out["health_waits_blame_2004"])
    return out


if __name__ == "__main__":
    main()
