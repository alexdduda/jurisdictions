"""The cost of raising a dollar, federal and provincial, on one basis.

The model's verdicts for schools and the environment turn on the ratio of the
provincial to the federal excess cost of raising a dollar (marginal cost of
public funds minus one). The published estimates (Dahlby and Ferede) are for
different years and methods, and the provincial ones are from the province's
own point of view, so the range they imply (0.24 to 1.51) straddles both flip
points. This computes both levels for the same year (2025), the same tax
(personal income tax) and the same formula.

Same base, same formula. In each province, Ottawa and the province tax the
same income at a combined marginal rate T. Raising either rate by a point
costs taxpayers the same, and taxable income falls by the same amount, so the
revenue lost to all of Canada's governments together is the same whichever
level raised the rate:

    MCF(T) = 1 / (1 - e * T / (1 - T))

with e the elasticity of taxable income to the net-of-tax rate (1 - T). A
federal increase applies in every province, so its MCF averages the
provinces' (weighted by taxable income); a provincial increase applies at its
own T. Socially, then, the two differ only because combined rates differ
across provinces.

From a province's own point of view, income that moves or is reported in
another province is lost too, and the fall in federal revenue isn't its
problem. That "own view" uses Milligan and Smart's provincial elasticity for
top earners (0.664, which includes shifting between provinces) on the
province's rate alone. The model's welfare should use the social cost; the
own view is reported as an upper bound for what provinces act on.

Inputs:
  * 2025 rates: CRA "Tax rates and income brackets" (federal 14.5% blended for
    2025, provinces except Quebec); Revenu Quebec 2025 rates; Quebec
    abatement 16.5% of basic federal tax (Department of Finance); Ontario
    surtax 20% over $5,710 and 36% over $7,307 of basic Ontario tax (EY,
    TaxTips). Credits other than the basic personal amount are ignored.
  * Elasticity e: 0.1 to 0.4 (assumption, see VERIFICATION.md).
  * Weights: provincial taxable income approximated by population times
    average market income, 2024 (tables 17-10-0009, 11-10-0190).

    python3 validation/cost_of_funds.py      # writes validation/cost_of_funds.json
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tiebout.canada as ca  # noqa: E402

INF = float("inf")
FEDERAL = [(57_375, 0.145), (114_750, 0.205), (177_882, 0.26), (253_414, 0.29), (INF, 0.33)]
PROVINCIAL = {
    "Newfoundland and Labrador": [(44_192, .087), (88_382, .145), (157_792, .158), (220_910, .178), (282_214, .198),
                                  (564_429, .208), (1_128_858, .213), (INF, .218)],
    "Prince Edward Island": [(33_328, .095), (64_656, .1347), (105_000, .166), (140_000, .1762), (INF, .19)],
    "Nova Scotia": [(30_507, .0879), (61_015, .1495), (95_883, .1667), (154_650, .175), (INF, .21)],
    "New Brunswick": [(51_306, .094), (102_614, .14), (190_060, .16), (INF, .195)],
    "Quebec": [(53_255, .14), (106_495, .19), (129_590, .24), (INF, .2575)],
    "Ontario": [(52_886, .0505), (105_775, .0915), (150_000, .1116), (220_000, .1216), (INF, .1316)],
    "Manitoba": [(47_564, .108), (101_200, .1275), (INF, .174)],
    "Saskatchewan": [(53_463, .105), (152_750, .125), (INF, .145)],
    "Alberta": [(60_000, .08), (151_234, .10), (181_481, .12), (241_974, .13), (362_961, .14), (INF, .15)],
    "British Columbia": [(49_279, .0506), (98_560, .077), (113_158, .105), (137_407, .1229), (186_306, .147),
                         (259_829, .168), (INF, .205)],
}
QUEBEC_ABATEMENT = 0.165
ONTARIO_SURTAX = ((5_710, 0.20), (7_307, 0.36))
ONTARIO_BASIC_CREDIT = 12_747 * 0.0505  # basic personal amount 2025 at the lowest rate
INCOMES = (60_000, 100_000, 150_000)  # where most of the marginal revenue comes from
ELASTICITY = (0.1, 0.25, 0.4)
OWN_VIEW_ELASTICITY = 0.664  # Milligan and Smart (2015), top 1%, includes interprovincial shifting


def marginal(schedule, y):
    return next(rate for top, rate in schedule if y <= top)


def tax(schedule, y):
    out, low = 0.0, 0.0
    for top, rate in schedule:
        out += rate * max(0.0, min(y, top) - low)
        low = top
        if y <= top:
            break
    return out


def rates(p, y):
    """(federal marginal rate as applied in p, provincial marginal rate) at income y."""
    fed = marginal(FEDERAL, y) * (1 - QUEBEC_ABATEMENT if p == "Quebec" else 1)
    prov = marginal(PROVINCIAL[p], y)
    if p == "Ontario":
        basic = tax(PROVINCIAL[p], y) - ONTARIO_BASIC_CREDIT
        prov *= 1 + sum(s for threshold, s in ONTARIO_SURTAX if basic > threshold)
    return fed, prov


def mcf(e, t):
    return 1 / (1 - e * t / (1 - t))


def weights():
    ca.YEARS = ["2024"]
    pop = ca.population()
    income = {}
    for r in ca.rows("11100190.csv"):
        if (r["GEO"] in ca.PROVINCES and r["REF_DATE"] == "2024"
                and r["Economic family type"] == "Economic families and persons not in an economic family"
                and r["Income concept"] == "Average market income"):
            income[r["GEO"]] = ca.value(r)
    w = {p: pop[(p, "2024")] * income[p] for p in ca.PROVINCES}
    total = sum(w.values())
    return {p: v / total for p, v in w.items()}


def main() -> dict:
    w = weights()
    out = {"incomes": INCOMES, "elasticities": ELASTICITY, "combined_rates": {}, "by_elasticity": {}}
    for y in INCOMES:
        out["combined_rates"][str(y)] = {p: round(sum(rates(p, y)), 4) for p in ca.PROVINCES}
    ratios_all = []
    for e in ELASTICITY:
        rows = {}
        for y in INCOMES:
            combined = {p: sum(rates(p, y)) for p in ca.PROVINCES}
            # A federal point raises taxpayers' cost by the federal share actually paid (abated in Quebec).
            fed_weight = {p: w[p] * (1 - QUEBEC_ABATEMENT if p == "Quebec" else 1) for p in ca.PROVINCES}
            fed_cost = sum(fed_weight.values())
            fed_revenue = sum(fed_weight[p] * (1 - e * combined[p] / (1 - combined[p])) for p in ca.PROVINCES)
            fed_mcf = fed_cost / fed_revenue
            excess_fed = fed_mcf - 1
            prov = {p: mcf(e, combined[p]) for p in ca.PROVINCES}
            ratio = {p: (prov[p] - 1) / excess_fed for p in ca.PROVINCES}
            own = {p: 1 / (1 - OWN_VIEW_ELASTICITY * rates(p, y)[1] / (1 - combined[p])) for p in ca.PROVINCES}
            rows[str(y)] = {
                "federal_mcf": round(fed_mcf, 3),
                "provincial_mcf": {p: round(v, 3) for p, v in prov.items()},
                "ratio": {p: round(v, 3) for p, v in ratio.items()},
                "own_view_mcf": {p: round(v, 3) for p, v in own.items()},
            }
            ratios_all += list(ratio.values())
        out["by_elasticity"][str(e)] = rows
    # Population-weighted ratio (what a Canadian on average faces) and the full spread.
    weighted = [sum(w[p] * out["by_elasticity"][str(e)][str(y)]["ratio"][p] for p in ca.PROVINCES)
                for e in ELASTICITY for y in INCOMES]
    out["social_ratio"] = {"min": round(min(ratios_all), 3), "max": round(max(ratios_all), 3),
                           "weighted_min": round(min(weighted), 3), "weighted_max": round(max(weighted), 3)}
    own_excess = [out["by_elasticity"]["0.25"][str(y)]["own_view_mcf"][p] - 1 for y in INCOMES for p in ca.PROVINCES]
    out["own_view_ratio_at_e_0.25"] = {
        "min": round(min(own_excess) / max(out["by_elasticity"]["0.25"][str(y)]["federal_mcf"] - 1 for y in INCOMES), 3),
        "max": round(max(own_excess) / min(out["by_elasticity"]["0.25"][str(y)]["federal_mcf"] - 1 for y in INCOMES), 3),
    }
    out["weights"] = {p: round(v, 4) for p, v in w.items()}
    (ROOT / "validation" / "cost_of_funds.json").write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("social_ratio", "own_view_ratio_at_e_0.25")}, indent=1))
    for y in INCOMES:
        print(y, out["combined_rates"][str(y)])
        print("   ratio e=0.25", out["by_elasticity"]["0.25"][str(y)]["ratio"], "fed", out["by_elasticity"]["0.25"][str(y)]["federal_mcf"])
    return out


if __name__ == "__main__":
    main()
