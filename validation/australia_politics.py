"""Out-of-sample test of the political layer: Australia's carbon price, 2012-2014.

validation/political_realities.py was built after Canada repealed its consumer
carbon charge (2025-2026), so its account of that repeal is an explanation, not
a prediction. Australia is a case it has never seen. The carbon pricing
mechanism started on 1 July 2012 (Clean Energy Act 2011, passed by the
Commonwealth Parliament alone) and was repealed from 1 July 2014, after the
first election held under it (September 2013). Large emitters have since faced
the Safeguard Mechanism, a national baseline on facility emissions (from 2016;
baselines declining 4.9% a year with tradable credits since 2023).

The climate area is rerun on Australia's six states (tiebout/geography.py),
with every measured input rebuilt from Australian data (validation/country_run.py),
and the political layer applied with Australia's own rules:

- Status quo: no national carbon policy (before July 2012, and again after the
  repeal). State schemes such as New South Wales's greenhouse gas abatement
  scheme are read as provinces deciding.
- Constitution: every climate rule here is something the Commonwealth
  Parliament can enact alone (it did enact a price, and later the Safeguard
  Mechanism); no rule needs a referendum.
- Attachment to the state: switched off. No Australian measure was found, and
  Canada's isn't transferable.
- Loss aversion, visible payments, repeal: as for Canada. How much of the
  household compensation voters noticed was not measured in anything found;
  Canada's range (0 to 60% of the rebate seen) is kept. The evidence found
  points to the low end: in 2013 most people surveyed (Per Capita, 1,400
  respondents) thought the tax cost them about $20 a week, against the
  government's figure of under $10.
- Rule levels: Canada's best level for each kind of rule (results/uncertainty_canada.json);
  Australia's own analysis also picks a price at 1.2.

Predictions, fixed before the first run (see the commit that adds this file):

  P1  Adopted from no national policy, a carbon price (uniform or as a floor)
      is more likely than not to be repealed at the first election: its mean
      chance of surviving one election is below 0.5.
  P2  Starting again from no national policy, the rule the Commonwealth
      adopts with full politics is most often a quantity standard (uniform or
      floor), matching the Safeguard Mechanism, not a price.

Either could fail: Australia's states differ from Canada's provinces in size,
emissions and income, and the planner's choice (a price) is the contrast.

A known limit, not tested here: if P1 holds wherever payments are visible, the
layer also predicts the repeal of carbon taxes that lasted, such as British
Columbia's (July 2008 to April 2025) and Sweden's (since 1991).

    python3 validation/australia_politics.py   # writes validation/australia_politics.json
"""

import json
import random
import sys
from dataclasses import replace
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))
from country_run import country_ranges  # noqa: E402
from political_realities import RANGES, SEEN_GRID, _case, decide, judge, perceived  # noqa: E402
from politics import _shares, support  # noqa: E402
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.geography import AU_STATES  # noqa: E402
from tiebout.model import Policy  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import build, latin_hypercube, world_ranges  # noqa: E402

DRAWS, SEEDS = 40, 3
AREA = "climate"
OUT = ROOT / "validation" / "australia_politics.json"
LEGAL = {"local", "central", "floor", "price", "price_floor"}
QUANTITY = {"central", "floor"}
PRICE = {"price", "price_floor"}
# No Australian measure of attachment to the state; climate rules cost the Commonwealth no money.
OFF = ("attachment",)
EVERYTHING_BUT_STATUS_QUO = ("loss_aversion", "visible_payments", "attachment", "constitution", "repeal", "fiscal_crisis")


def survival(case, i, ref, modes, x, shares, off=OFF) -> float:
    """Chance a rule, once adopted, keeps a majority through one election (a fresh draw of rebate_seen)."""
    att = [0.0] * len(shares)
    return mean(support(perceived(case, i, ref, modes, x, s, shares, att, off)[1], shares) > 0.5 for s in SEEN_GRID)


def main() -> dict:
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())["domains"][AREA]["best_per_mode"]
    modes = list(saved)
    labels = [saved[m]["policy"] for m in modes]
    policies = [Policy(saved[m]["mode"], saved[m]["level"]) for m in modes]
    sq = modes.index("local")
    base_world = replace(DEFAULT_WORLD, geography="au_states", language_profile="", city_profile="")
    shares = _shares(base_world)
    att = [0.0] * len(shares)
    rs = country_ranges("au")
    d = DEFAULT_WORLD.domain(AREA)
    rng = random.Random(f"australia_politics:{AREA}")
    samples = latin_hypercube({**world_ranges(AREA, rs), **RANGES}, DRAWS, rng)
    tasks, xs = [], []
    for j, params in enumerate(samples):
        x = {k: params.pop(k) for k in RANGES}
        world, _ = build(base_world, d, params)
        for k in range(SEEDS):
            tasks.append((world, AREA, policies, 10_000 * j + k, x))
            xs.append(x)
    with make_pool() as pool:
        cases = list(pool.map(_case, tasks, chunksize=1))

    def tally(off):
        picks = {}
        for c, x in zip(cases, xs):
            lab, _ = decide(c, labels, modes, sq, AREA, x, shares, att, off, LEGAL)
            picks[lab] = picks.get(lab, 0) + 1
        return {k: round(v / len(cases), 3) for k, v in sorted(picks.items(), key=lambda t: -t[1])}

    rules = {}
    for i, lab in enumerate(labels):
        if i == sq:
            continue
        passes, surv, surv_real, opp = [], [], [], [0.0] * len(shares)
        for c, x in zip(cases, xs):
            ok, _, _, _, v = judge(c, i, sq, modes, AREA, x, shares, att, OFF, LEGAL, elections=1)
            passes.append(ok)
            for p in range(len(v)):
                opp[p] += v[p] < 0
            surv.append(survival(c, i, sq, modes, x, shares))
            surv_real.append(survival(c, i, sq, modes, x, shares, OFF + ("visible_payments", "loss_aversion")))
        rules[lab] = {"passes_as_voters_see_it": round(mean(passes), 3),
                      "survives_one_election_if_adopted": round(mean(surv), 3),
                      "survives_one_election_on_real_welfare": round(mean(surv_real), 3),
                      "opposed_by": {s: round(n / len(cases), 3) for s, n in zip(AU_STATES, opp)}}

    # How much of the compensation voters would have to notice for a price to keep a majority.
    needed = []
    i_price = modes.index("price")
    for c, x in zip(cases, xs):
        grid = [k / 20 for k in range(21)]
        ok = [s for s in grid if support(perceived(c, i_price, sq, modes, x, s, shares, att, OFF)[1], shares) > 0.5]
        needed.append(min(ok) if ok else None)
    found = sorted(n for n in needed if n is not None)

    choice = tally(OFF)
    planner = tally(EVERYTHING_BUT_STATUS_QUO)
    price_surv = mean(rules[labels[m]]["survives_one_election_if_adopted"] for m in range(len(modes)) if modes[m] in PRICE)
    quantity_share = sum(v for k, v in choice.items() if k.split()[0] in QUANTITY)
    price_share = sum(v for k, v in choice.items() if k.split()[0] == "price")
    out = {
        "draws": DRAWS, "seeds": SEEDS, "states": AU_STATES, "ranges": RANGES, "legal_alone": sorted(LEGAL),
        "switched_off": list(OFF), "levels_from": "results/uncertainty_canada.json (climate best_per_mode)",
        "rules": rules,
        "rebate_seen_needed_for_majority": {
            "worlds_where_some_share_suffices": round(len(found) / len(needed), 3),
            "median": found[len(found) // 2] if found else None,
            "p10": found[len(found) // 10] if found else None,
            "p90": found[9 * len(found) // 10] if found else None},
        "choice_with_politics": choice,
        "planner_choice": planner,
        "predictions": {
            "P1_price_repealed_at_first_election": {
                "mean_survival": round(price_surv, 3), "holds": price_surv < 0.5,
                "actual": "repealed from 1 July 2014, after the September 2013 election"},
            "P2_quantity_standard_chosen": {
                "share_quantity_standard": round(quantity_share, 3), "share_price": round(price_share, 3),
                "holds": quantity_share > max(price_share, choice.get("keep today's arrangement", 0)),
                "actual": "Safeguard Mechanism: national baselines for large emitters (2016; declining with tradable credits from 2023)"},
        },
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: out[k] for k in ("rules", "rebate_seen_needed_for_majority", "choice_with_politics",
                                          "planner_choice", "predictions")}, indent=1))
    return out


if __name__ == "__main__":
    main()
