"""Politics the welfare model leaves out, and whether it explains what Canada does.

The model scores rules by real welfare and lets a benevolent planner pick.
validation/politics.py added visible payments and a vote. This adds the rest of
what the comparison with real politics turned up, on the ten real provinces
(sized by population, with their measured tastes), starting from what Canada
does today rather than from a blank slate:

1. Status quo. A reform is judged against today's arrangement, not against
   provinces deciding (STATUS_QUO below, in model terms).
2. Loss aversion. A province that loses weighs the loss `loss_aversion` times
   a gain of the same size: 1.8 to 2.1, the 95% interval of the mean across 607
   estimates (Brown, Imai, Vieider and Camerer, Journal of Economic Literature
   62(2), 2024: 1.955).
3. Visible payments. As in politics.py: carbon-price payments are seen, the
   rebate only partly (rebate_seen 0 to 0.6).
4. Attachment to the province. People who want their province, not Ottawa, to
   decide count a central rule as a cost whatever it does for services. The
   pattern across provinces is measured (data/regional_attachment.json: CES
   questions on federal vs provincial power, fair treatment and which
   government looks after you; Quebec, Saskatchewan, Alberta and Newfoundland
   highest, Ontario slightly pro-Ottawa). How much Ottawa intrudes is set per
   kind of rule (INTRUSION, an assumption). The size is not measured: the cost
   is attachment x intrusion x identity_scale x the area's largest gain, with
   identity_scale sampled from 0 to 1.
5. The constitution and the courts. Ottawa can enact some rules alone: its own
   powers, its spending power (grants with conditions), and what the courts
   have upheld. Those need a majority in the Commons, taken as provinces
   holding more than half the people. The rest intrude on provincial powers
   and need the general amending formula: seven provinces with half the people
   (LEGAL below, with the clauses and cases).
6. Repeal. A rule passed by Parliament can be undone by the next one. A rule
   with visible payments survives an election only if a majority still sees a
   gain, judged at a fresh draw of rebate_seen; the chance it survives
   ELECTIONS elections (about a decade: Canada held nine general elections
   from 2000 to 2025) discounts its value. A constitutional change can't be
   undone by an election.
7. Fiscal crises. In a federal budget crisis Ottawa cuts its own money: grants
   and federal programmes fall by `crisis_cut`, while mandates, standards and
   prices, which cost Ottawa nothing, are untouched. It may do so unilaterally:
   the Supreme Court upheld the 1990 cap on Canada Assistance Plan payments
   (Reference re Canada Assistance Plan (B.C.), [1991] 2 SCR 525). 15% to 40% is
   the range of the 1995 budget's cut to provincial transfers (about 15% of
   total CAP and EPF transfers including tax points, 40% of projected cash, by
   1997-98). `crisis_chance`, the chance of such a cut in a decade, is 0.3 to
   0.6: two confirmed episodes from 1990 to 2025 (the 1990 cap, the 1995
   budget) give about 0.43 for at least one in a decade (Poisson); counting the
   2017 slowdown of Canada Health Transfer growth as a third gives 0.58.

Ottawa then adopts, among the rules it can pass, the one with the largest
expected perceived gain (population-weighted, discounted for repeal), or keeps
today's arrangement. For each area the output gives how often that choice is
today's arrangement, against how often a planner who sees only real welfare
would keep it, and which mechanism does the work (each switched off in turn).

Not modelled: parties and the seat system, interest groups, credit claiming,
courts' future rulings, and opting out (Quebec's practice of taking the money
without the programme).

    python3 validation/political_realities.py   # writes validation/political_realities.json
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
from calibrate_mobility import provinces_ranges  # noqa: E402
from politics import _shares, amending, support  # noqa: E402
from tiebout.config import DEFAULT_WORLD  # noqa: E402
from tiebout.geography import PROVINCES, layout  # noqa: E402
from tiebout.model import Policy, _clamp, _Run  # noqa: E402
from tiebout.optimize import make_pool  # noqa: E402
from tiebout.uncertainty import build, latin_hypercube, world_ranges  # noqa: E402

DRAWS, SEEDS = 40, 3
ELECTIONS = 3
OUT = ROOT / "validation" / "political_realities.json"
RANGES = {"loss_aversion": (1.8, 2.1), "rebate_seen": (0.0, 0.6), "abated": (0.05, 0.30),
          "identity_scale": (0.0, 1.0), "crisis_chance": (0.3, 0.6), "crisis_cut": (0.15, 0.40)}
SEEN_GRID = (0.0, 0.15, 0.3, 0.45, 0.6)

# Today's arrangement in model terms, at the level the uncertainty analysis found best for that kind of rule.
STATUS_QUO = {
    "schools": ("local", "provinces run schools; no federal school grant"),
    "environment": ("floor", "federal minimum standards (Canadian Environmental Protection Act) that provinces implement and may exceed"),
    "transit": ("city", "cities run transit, with federal capital grants (Canada Public Transit Fund)"),
    "health": ("foundation", "provinces run health care; the Canada Health Transfer pays a per-person amount on condition of the Canada Health Act's standards"),
    "redistribution": ("central", "mostly federal: income tax, Old Age Security, Employment Insurance, the Canada Child Benefit"),
    "climate": ("floor", "the consumer fuel charge was set to zero in April 2025 and repealed in March 2026 (Bill C-4); industrial output-based pricing and regulations remain, treated as a quantity floor"),
}

# How far a kind of rule puts Ottawa in charge (an assumption, 0 to 1).
INTRUSION = {"local": 0.0, "city": 0.25, "equalized": 0.25, "matched": 0.5, "foundation": 0.5, "equalized_both": 0.5,
             "floor": 0.75, "ceiling": 0.75, "price_floor": 0.75, "central": 1.0, "price": 1.0}

# Rules Ottawa can enact alone; anything else needs the general amending formula.
_SPENDING = {"local", "matched", "equalized", "foundation", "city"}
LEGAL = {
    "schools": (_SPENDING, "education is provincial (s. 93); Ottawa may only attach conditions to money it spends"),
    "health": (_SPENDING, "hospitals are provincial (s. 92(7)); federal role through the spending power, as in the Canada Health Act"),
    "transit": (_SPENDING, "municipal institutions and local works are provincial (s. 92(8), 92(10))"),
    "environment": (_SPENDING | {"central", "floor", "ceiling"},
                    "shared; federal standards upheld under the criminal law power (R. v. Hydro-Quebec, [1997] 3 SCR 213)"),
    "climate": ({"local", "floor", "price_floor"},
                "minimum national standards of carbon-price stringency upheld under peace, order and good government "
                "(Reference re Greenhouse Gas Pollution Pricing Act, 2021 SCC 11); a uniform federal price or standard "
                "displacing stricter provincial ones goes beyond what was upheld, so is treated as needing amendment"),
    "redistribution": ({"local", "central"},
                       "federal taxing and spending (s. 91(3)), unemployment insurance (s. 91(2A), 1940) and pensions "
                       "(s. 94A, 1951); a mandate on provincial welfare levels would need amendment"),
}
NO_MONEY = {"local", "floor", "ceiling", "price", "price_floor", "equalized_both"}
MECHANISMS = ("status_quo", "loss_aversion", "visible_payments", "attachment", "constitution", "repeal", "fiscal_crisis")


def attachment() -> list[float]:
    names = {"NL": "Newfoundland and Labrador", "PE": "Prince Edward Island", "NS": "Nova Scotia",
             "NB": "New Brunswick", "QC": "Quebec", "ON": "Ontario", "MB": "Manitoba", "SK": "Saskatchewan",
             "AB": "Alberta", "BC": "British Columbia"}
    a = json.loads((ROOT / "data" / "regional_attachment.json").read_text())["provinces"]
    return [a[names[c]]["attachment"] for c in PROVINCES]


def crisis_policy(p: Policy, cut: float, regulation: bool = False) -> Policy | None:
    """The rule after Ottawa cuts its own money by `cut`, or None if it spends none.

    In an area paid for by emitters (`regulation`, climate) every rule is a
    regulation or a price, so none costs Ottawa money; a national quantity
    standard there is not federal spending.
    """
    if regulation or p.mode in NO_MONEY:
        return None
    if p.mode == "foundation":
        return Policy(p.mode, p.level * (1 - cut) ** 0.5)   # Ottawa pays f^2 per person
    return Policy(p.mode, p.level * (1 - cut))


def _case(args):
    world, name, policies, seed, extra = args
    d = world.domain(name)
    base = _Run(world, {}, seed).run().by_origin
    out = []
    for policy in policies:
        run = _Run(world, {name: policy}, seed)
        o = run.run()
        pay = [0.0] * run.R
        if d.private_costs and policy.mode in ("price", "price_floor"):
            a = run.abatement.get(name, [1.0] * run.R)
            cut = [_clamp(policy.level / (2 * a[r]), 0, world.max_level) for r in range(run.R)]
            scale = sum(cut) / (extra["abated"] * sum(a))
            pay = [d.weight * policy.level * max(a[r] * scale - cut[r], 0.0) for r in range(run.R)]
        cp = crisis_policy(policy, extra["crisis_cut"], d.private_costs)
        crisis = _Run(world, {name: cp}, seed).run().by_origin if cp else o.by_origin
        out.append({"u": o.by_origin, "pay": pay, "crisis": crisis})
    return {"base": base, "rules": out}


def _nat(shares, v):
    return sum(w * y for w, y in zip(shares, v))


def perceived(case, i, ref, modes, x, seen, shares, att, off=()):
    """Province by province, how rule i looks against `ref` (an index, or None for provinces deciding)."""
    on = lambda m: m not in off
    rules, R = case["rules"], len(shares)
    pc = x["crisis_chance"] if on("fiscal_crisis") else 0.0
    eu = lambda r: [(1 - pc) * a + pc * b for a, b in zip(r["u"], r["crisis"])]
    base_u = eu(rules[ref]) if ref is not None else case["base"]
    base_pay = rules[ref]["pay"] if ref is not None else [0.0] * R
    base_int = INTRUSION[modes[ref]] if ref is not None else 0.0
    real = [a - b for a, b in zip(eu(rules[i]), base_u)]
    v = list(real)
    if on("visible_payments"):
        v = [v[p] - (1 - seen) * (rules[i]["pay"][p] - base_pay[p]) for p in range(R)]
    if on("attachment"):
        G = max([_nat(shares, r["u"]) - _nat(shares, case["base"]) for r in rules] + [1e-9])
        v = [v[p] - x["identity_scale"] * G * att[p] * (INTRUSION[modes[i]] - base_int) for p in range(R)]
    if on("loss_aversion"):
        v = [y if y >= 0 else x["loss_aversion"] * y for y in v]
    return real, v


def judge(case, i, ref, modes, area, x, shares, att, off=(), legal=None, elections=ELECTIONS):
    """(passes, needs amendment, chance of surviving the next elections, real change, perceived change).

    `legal` is the set of modes the centre can enact alone (default: Canada's, LEGAL[area][0])."""
    on = lambda m: m not in off
    legal = LEGAL[area][0] if legal is None else legal
    real, v = perceived(case, i, ref, modes, x, x["rebate_seen"], shares, att, off)
    amend = on("constitution") and modes[i] not in legal
    ok = amending(v, shares) if amend else support(v, shares) > 0.5
    survive = 1.0
    if ok and on("repeal") and on("visible_payments") and not amend and any(case["rules"][i]["pay"]):
        q = mean(support(perceived(case, i, ref, modes, x, s, shares, att, off)[1], shares) > 0.5 for s in SEEN_GRID)
        survive = q ** elections
    return ok, amend, survive, real, v


def decide(case, labels, modes, sq, area, x, shares, att, off=(), legal=None):
    """Ottawa's choice in one world, with the mechanisms in `off` switched off. Returns (label, real gain vs today)."""
    ref = sq if "status_quo" not in off else None
    best = (0.0, "keep today's arrangement" if ref is not None else "provinces decide", 0.0)
    for i, lab in enumerate(labels):
        if i == ref:
            continue
        ok, _, survive, real, v = judge(case, i, ref, modes, area, x, shares, att, off, legal)
        if ok and _nat(shares, v) * survive > best[0]:
            best = (_nat(shares, v) * survive, lab, _nat(shares, real) * survive)
    return best[1], best[2]


def main() -> dict:
    base_world = replace(DEFAULT_WORLD, province_profile="canada", geography="provinces")
    saved = json.loads((ROOT / "results" / "uncertainty_canada.json").read_text())["domains"]
    ranges = provinces_ranges()
    att = attachment()
    shares = _shares(base_world)
    out = {"draws": DRAWS, "seeds": SEEDS, "elections": ELECTIONS, "ranges": RANGES, "intrusion": INTRUSION,
           "attachment": dict(zip(PROVINCES, att)), "areas": {}}
    with make_pool() as pool:
        for d in DEFAULT_WORLD.domains:
            best = {m: f for m, f in saved[d.name]["best_per_mode"].items() if m != "legislature"}
            modes = list(best)
            labels = [best[m]["policy"] for m in modes]
            policies = [Policy(best[m]["mode"], best[m]["level"]) for m in modes]
            sq = modes.index(STATUS_QUO[d.name][0])
            rng = random.Random(f"realities:{d.name}")
            samples = latin_hypercube({**world_ranges(d.name, ranges), **RANGES}, DRAWS, rng)
            tasks, xs = [], []
            for j, params in enumerate(samples):
                x = {k: params.pop(k) for k in RANGES}
                world, _ = build(base_world, d, params)
                for k in range(SEEDS):
                    tasks.append((world, d.name, policies, 10_000 * j + k, x))
                    xs.append(x)
            cases = list(pool.map(_case, tasks, chunksize=1))
            area = {"status_quo": labels[sq], "status_quo_meaning": STATUS_QUO[d.name][1],
                    "legal": {"alone": sorted(m for m in modes if m in LEGAL[d.name][0]),
                              "needs_amendment": sorted(m for m in modes if m not in LEGAL[d.name][0]),
                              "basis": LEGAL[d.name][1]},
                    "choices": {}}

            def tally(off):
                picks, gains = {}, []
                for c, x in zip(cases, xs):
                    lab, g = decide(c, labels, modes, sq, d.name, x, shares, att, off)
                    picks[lab] = picks.get(lab, 0) + 1
                    gains.append(g)
                return {"picks": {k: round(v / len(cases), 3) for k, v in sorted(picks.items(), key=lambda t: -t[1])},
                        "keeps_today": round(picks.get("keep today's arrangement", 0) / len(cases), 3),
                        "mean_real_gain_vs_today": round(mean(gains), 5)}

            # A planner who sees real welfare only, starting from today's arrangement.
            area["choices"]["planner"] = tally(tuple(m for m in MECHANISMS if m != "status_quo"))
            area["choices"]["all_politics"] = tally(())
            area["choices"]["without"] = {m: tally((m,)) for m in MECHANISMS if m != "status_quo"}
            area["choices"]["only"] = {m: tally(tuple(k for k in MECHANISMS if k not in ("status_quo", m)))
                                       for m in MECHANISMS if m != "status_quo"}
            # Per rule: how often it could pass at all, and who opposes it (full politics).
            rule_rows = {}
            for i, lab in enumerate(labels):
                if i == sq:
                    continue
                passes, surv, opp = [], [], [0.0] * len(shares)
                for c, x in zip(cases, xs):
                    ok, amend, survive, _, v = judge(c, i, sq, modes, d.name, x, shares, att)
                    passes.append(ok)
                    for p in range(len(v)):
                        opp[p] += v[p] < 0
                    if any(c["rules"][i]["pay"]) and not amend:
                        # Had Parliament adopted it anyway (as in 2019): the chance it outlasts the next elections.
                        surv.append(mean(support(perceived(c, i, sq, modes, x, s, shares, att)[1], shares) > 0.5
                                         for s in SEEN_GRID) ** ELECTIONS)
                rule_rows[lab] = {"route": "amendment" if modes[i] not in LEGAL[d.name][0] else "Parliament",
                                  "passes": round(mean(passes), 3),
                                  **({"survives_elections_if_adopted": round(mean(surv), 3)} if surv else {}),
                                  "opposed_by": {p: round(n / len(cases), 3) for p, n in zip(PROVINCES, opp)}}
            area["rules"] = rule_rows
            out["areas"][d.name] = area
            print(d.name, json.dumps({k: area["choices"][k] for k in ("planner", "all_politics")}), flush=True)
            OUT.write_text(json.dumps(out, indent=2))
    OUT.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    main()
