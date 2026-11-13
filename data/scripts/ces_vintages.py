"""Between- vs within-province disagreement in older Canadian Election Studies.

The model's taste inputs come from the 2019 study (data/scripts/ces_disagreement.py):
how far provinces' average wishes sit apart, in units of disagreement within a
province (rho), and each province's average (the province profile). This applies
the same method to the 1993, 1997, 2004, 2008, 2011 and 2015 studies, to see
whether those numbers were stable, so the backtest no longer has to assume
they were.

Same questions where they exist: "should the federal government spend more,
less or about the same on education / the environment" (2004 to 2019) and "how
much should be done to reduce the gap between the rich and the poor" (2004 to
2019). Earlier studies didn't ask them, so the nearest items stand in, flagged
`proxy`: cutting education spending "a lot / some / not at all" (1993, 1997),
"protecting the environment is more important than creating jobs" (1993 to
2011, also run where the spending item exists so the two can be compared), and
"the government must do more to reduce the income gap" (1993, 1997). For
climate, "the Liberal Party's Green Shift/Carbon Tax would really hurt the
Canadian economy" (2008), reversed so that disagreeing counts as support.

Each answer is read as a latent wish, normal within a province with sd 1, cut
at thresholds shared by all provinces; a province's mean follows from its
answer shares. Sampling noise is removed by bootstrap, as for 2019. Standard
library only; reads the tab-delimited files from Borealis (Canadian Dataverse,
CC BY-NC 4.0) in data/raw/ces/<year>/ces<year>.tab.

    python3 data/scripts/ces_vintages.py     # writes data/ces_vintages.json
"""

import csv
import json
import random
from math import sqrt
from pathlib import Path
from statistics import NormalDist, mean, pstdev

ROOT = Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "raw" / "ces"
PROVINCES = ["Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia", "New Brunswick", "Quebec",
             "Ontario", "Manitoba", "Saskatchewan", "Alberta", "British Columbia"]
SGC = dict(zip(["10", "11", "12", "13", "24", "35", "46", "47", "48", "59"], PROVINCES))
# 2015 codes provinces alphabetically (with the territories); 1993 numbers them 0-9 east to west.
ALPHA_2015 = {"1": "Alberta", "2": "British Columbia", "3": "Manitoba", "4": "New Brunswick",
              "5": "Newfoundland and Labrador", "7": "Nova Scotia", "9": "Ontario", "10": "Prince Edward Island",
              "11": "Quebec", "12": "Saskatchewan"}
EAST_WEST_1993 = {str(i): p for i, p in enumerate(PROVINCES)}

SPEND_3 = {"1": "high", "5": "mid", "3": "low"}            # 2004-2011: more / same / less
SPEND_2015 = {"1": "high", "3": "mid", "2": "low"}
GAP_5 = {"1": "high", "2": "high", "3": "mid", "4": "low", "5": "low"}
AGREE_4 = {"1": "high", "2": "high", "3": "low", "4": "low"}
CUT_3 = {"1": "low", "3": "mid", "5": "high"}              # cut spending a lot / some / not at all
HURTS_7 = {"1": "low", "3": "low", "5": "high", "7": "high"}  # agreeing the tax "would really hurt the economy" = against

# year: (province variable, province codes, weight, {area: (variable, coding, proxy?)})
SURVEYS = {
    "1993": ("CPSPROV", EAST_WEST_1993, "CPSPWGT1", {
        "schools": ("CPSL7F", CUT_3, True), "environment_jobs": ("MBSA12", AGREE_4, True),
        "redistribution": ("MBSA8", AGREE_4, True)}),
    "1997": ("province", SGC, "cpspwgt1", {
        "schools": ("pese6f", CUT_3, True), "environment_jobs": ("mbsa6", AGREE_4, True),
        "redistribution": ("mbsa4", AGREE_4, True)}),
    "2004": ("province", SGC, "cespwgt", {
        "schools": ("pes_d1d", SPEND_3, False), "environment": ("pes_d1f", SPEND_3, False),
        "environment_jobs": ("mbs_a6", AGREE_4, True), "redistribution": ("cps_f6", GAP_5, False)}),
    "2008": ("ces08_PROVINCE", SGC, "ces08_PROVWGT", {
        "schools": ("ces08_PES_D1D", SPEND_3, False), "environment": ("ces08_PES_D1F", SPEND_3, False),
        "environment_jobs": ("ces08_MBS_A15", AGREE_4, True), "redistribution": ("ces08_PES_F6", GAP_5, False),
        "climate": ("ces08_CPS_J0", HURTS_7, False)}),
    "2011": ("PROVINCE11", SGC, "PROVINCIAL_WEIGHT", {
        "schools": ("CPS11_34", SPEND_3, False), "environment": ("CPS11_35", SPEND_3, False),
        "environment_jobs": ("MBS11_C14", AGREE_4, True), "redistribution": ("PES11_41", GAP_5, False)}),
    "2015": ("province", ALPHA_2015, "ProvWgt", {
        "schools": ("spnd_educ", SPEND_2015, False), "environment": ("spnd_envi", SPEND_2015, False),
        "redistribution": ("p_gap", GAP_5, False)}),
}
inv = NormalDist().inv_cdf
BOOT = 200


def province_means(rows):
    """rows: list of (province, answer class, weight)."""
    out = []
    for p in PROVINCES:
        tot = {"low": 0.0, "mid": 0.0, "high": 0.0}
        for q, a, w in rows:
            if q == p:
                tot[a] += w
        n = sum(tot.values())
        pl = min(max(tot["low"] / n, 0.005), 0.995)
        ph = min(max(tot["high"] / n, 0.005), 0.995)
        out.append(-(inv(pl) + inv(1 - ph)) / 2)
    return out


def measure(rows, rng):
    mus = province_means(rows)
    by = {p: [r for r in rows if r[0] == p] for p in PROVINCES}
    noise = []
    for _ in range(BOOT):
        take = [r for p in PROVINCES for r in rng.choices(by[p], k=len(by[p]))]
        b = province_means(take)
        noise.append(pstdev([x - y for x, y in zip(b, mus)]) ** 2)
    raw = pstdev(mus)
    return mus, raw, sqrt(max(raw ** 2 - mean(noise), 0.0))


def corr(x, y):
    mx, my = mean(x), mean(y)
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))


def main() -> dict:
    csv.field_size_limit(10 ** 9)
    out = {"method": "as data/scripts/ces_disagreement.py (2019), standard library", "years": {}}
    ref = json.loads((ROOT / "data" / "ces_disagreement.json").read_text())
    for year, (pvar, codes, wvar, items) in SURVEYS.items():
        with open(RAW / year / f"ces{year}.tab", encoding="latin1") as f:
            data = list(csv.DictReader(f, delimiter="\t"))
        out["years"][year] = {}
        for area, (var, coding, proxy) in items.items():
            rows = []
            for r in data:
                p, a, w = codes.get(r[pvar]), coding.get(r[var].strip()), r[wvar].strip()
                if p and a and w not in ("", "NA"):
                    rows.append((p, a, float(w) if float(w) > 0 else 1.0))
            mus, raw, rho = measure(rows, random.Random(f"ces{year}:{area}"))
            res = {"question": var, "proxy": proxy, "respondents": len(rows),
                   "province_means": {p: round(m, 3) for p, m in zip(PROVINCES, mus)},
                   "rho_raw": round(raw, 4), "rho": round(rho, 4)}
            key = "environment" if area == "environment_jobs" else area
            if key in ref:
                res["corr_with_2019_province_means"] = round(corr(mus, [ref[key]["province_means"][p] for p in PROVINCES]), 2)
            out["years"][year][area] = res
            print(year, area, var, f"n={len(rows)} rho={rho:.3f} raw={raw:.3f}",
                  res.get("corr_with_2019_province_means"), flush=True)
    out["years"]["2019"] = {k: {"question": v["question"], "proxy": False, "respondents": v["respondents"],
                                "province_means": v["province_means"], "rho_raw": v["rho_raw"], "rho": v["rho"]}
                            for k, v in ref.items()}
    (ROOT / "data" / "ces_vintages.json").write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
