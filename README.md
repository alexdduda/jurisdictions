# jurisdictions

Two linked experiments built on one analogy: **variable scope in code is like
jurisdiction in politics.** Both ask who gets to set a value, and whose
setting wins.

Programming languages answer with one fixed rule: the innermost scope
*shadows* the outer one. Federations argue about it. Sometimes the centre
preempts, sometimes it sets a floor and lets lower levels go higher, and
sometimes it pays part of the bill and lets them choose. This repo turns that
argument into code twice:

1. **`scopelang`**: a small language where each variable can carry its own
   precedence rule.
2. **`tiebout`**: an agent-based simulation that searches for the split of
   power between a nation and its regions that makes people best off, and maps
   when that answer changes.

The two connect: the simulation reads and writes its arrangements as
scopelang programs.

Pure Python 3.10+ standard library. Nothing to install.

```bash
python3 -m scopelang examples/min_wage.jur --tree
python3 -m tiebout study            # one hand-picked world + phase maps (~7 min on 8 cores)
python3 -m tiebout uncertainty      # 200 sampled worlds per policy area (~25 min)
python3 -m tiebout evaluate results/robust_arrangement.jur
python3 -m tiebout uncertainty --ranges canada   # the same, calibrated to Canadian data
python3 -m tiebout.thresholds       # where each verdict flips on the unmeasured numbers
python3 validation/model_vs_canada.py   # does the model reproduce Canadian patterns?
python3 site/build.py               # rebuild the results page from results/
python3 -m unittest discover -s tests -t .
```

---

## 1. scopelang

```
scope canada {
  law min_wage: floor = 15

  scope quebec {
    min_wage = 16
    scope montreal { min_wage = 14 }   # below Quebec's 16
  }
}
```

```
  ✗ line 6 STRUCK DOWN: montreal cannot set min_wage = 14: below the floor of 16 from quebec (floor law of canada, line 2)
```

### Laws

A `law NAME: MODE [= value]` declared in a scope binds every scope beneath it:

| mode | rule for lower scopes | real-world example |
|---|---|---|
| `shadow` | set your own; nearest value wins (ordinary scoping) | municipal parking rules |
| `preempt` | you may not set it at all | criminal law in Canada |
| `floor` | you may raise it, never go below what you inherit | cannabis age: federal 18, Quebec 21 |
| `ceiling` | you may lower it, never go above what you inherit | caps on rent increases |
| `matched` | set it freely; the declaring scope pays this share of the cost | federal health transfers |

Illegal writes are **struck down**: they're reported but not applied, and the
program keeps running, the way a court voids one statute without stopping the
government. At the end, every surviving value is checked again. If Ottawa
raises the floor *after* Quebec set its wage, Quebec's value is reported as
**now invalid**.

A lower level can't weaken a binding law by redeclaring it. It *can* add its own
floor under a `shadow` law, as a province would for its cities.

### Two parents, and disputes

```
scope montreal in quebec, cmm { show transit_fare }      # DISPUTE: quebec says 3.75, cmm says 3.5
scope montreal in quebec, cmm { defer transit_fare to cmm }
```

`defer` settles which value you *read*. It doesn't free you from the other
parent's floors, ceilings or preemptions.

### Commons and externalities

```
scope quebec {
  shared river_pollution = 10
  scope montreal { river_pollution += 4 }
  scope trois_rivieres { show river_pollution }
}
```

The run ends with an externality report: who changed the commons, by how much,
and who else lives with it.

```
river_pollution (commons of quebec) is now 14
  changed by montreal (+4, line 3)
  also lived with by: quebec, trois_rivieres
  read (and so affected) by: trois_rivieres
```

Also available: `show`, `explain NAME` (prints the value, the governing law in
plain English, and the chain of scopes), `if`/`else`, arithmetic, comparisons,
`min`/`max`/`abs`/`round`, and `--tree` to print the jurisdiction tree.

---

## 2. tiebout: what's the best balance?

A 4×4 grid of regions holds 1,600 agents. Each agent has an income and a taste
for each public good. Every step, each region's government picks what its
median resident wants, within the national rules. Then a quarter of the agents
look at a few other regions and move if it's worth the moving cost
(Tiebout, "A Pure Theory of Local Expenditures", *Journal of Political
Economy* 64(5), 1956: "voting with your feet").

The optimizer chooses, for every policy domain, one of the same five modes as
scopelang (local, central, floor, ceiling, matched) plus its level. It uses
coordinate descent, with every candidate scored on the same seeds.

### The trade-offs it's balancing

| pushes power **down** | pushes power **up** |
|---|---|
| regions want different things, and one uniform policy fits nobody | **spillovers**: a region ignores the benefit to its neighbours, so it under-provides |
| mobility lets people sort into regions that suit them | **scale**: one network is cheaper than sixteen |
| running money through the national budget has overhead | **mobility** lets the rich escape redistribution, which hollows out local tax bases |

These are the ingredients of Oates' decentralisation theorem and the standard
objections to it. The tests check that the model reproduces the textbook
results: local under-provision equals `taste × (1 − spillover)`, and a matching
grant at the spillover rate restores the social optimum.

### Default domains

| domain | regional disagreement | spillover | scale economies |
|---|---|---|---|
| schools | high (0.20) | low (0.05) | none |
| environment | low (0.06) | high (0.60) | none |
| transit | medium (0.10) | some (0.20) | 30% cheaper centrally |
| redistribution | n/a | n/a (mobility is the issue) | n/a |

These numbers are **assumptions**, chosen so each domain sits in a different
corner. The report's phase maps vary them to show which properties of a policy
area push it up or down a level. That generalises better than the headline
optimum does.

### Output

`python -m tiebout study` writes to `results/`:

- `REPORT.md`: the optimum, baselines, per-mode losses, phase maps, the
  mobility experiment, robustness checks and the model's limits
- `best_arrangement.jur`: the optimum as a scopelang program. Edit it and
  re-score with `python -m tiebout evaluate`
- `results.json`: every number in the report

### Handling uncertain assumptions

`python -m tiebout uncertainty` replaces every guessed number with a wide range
and samples 200 worlds per policy area (Latin hypercube). Every candidate policy
is scored in every world on the same seeds. It reports:

- how often each rule wins
- the single fixed rule with the lowest expected regret, which is what a
  government has to pick when it doesn't know the true parameters
- which parameters actually change the answer
- a check that solving one policy area at a time matches joint optimisation
  (it kept at least 96% of the joint gain in 8 test worlds)

Results go to `results/uncertainty.json` and `results/robust_arrangement.jur`.
This run overturned one result of the single-world study. That study charged
overhead on national money but not local money, which made national floors look
better than they are. With both overheads sampled, environment goes to a
national standard.

### Calibrated to Canada

`python -m tiebout uncertainty --ranges canada` replaces guesses with
measurements wherever Canadian evidence exists:

| parameter | source |
|---|---|
| regional disagreement (schools, environment, transit) | Statistics Canada 10-10-0005 spending by function, measured per person, as a budget share, net of provincial income, and (schools) per child aged 5 to 17 (17-10-0005) |
| disagreement within vs. between provinces | 2019 Canadian Election Study, 37,000 respondents (`data/scripts/ces_disagreement.py`) |
| income inequality | 11-10-0134 market-income Gini |
| mobility | 17-10-0022 interprovincial migration, 0.75% a year, used as an upper bound |
| cost of raising money, national vs. provincial | Computed on one basis from 2025 income tax rates (`validation/cost_of_funds.py`): provincial/federal ratio 0.68 to 1.36 by province, 1.01 to 1.02 for Canada; federal level from Dahlby and Ferede |

Spillovers, scale savings and crowding have no Canadian data and stay as wide
guesses. Rebuild the targets with `python3 -m tiebout.canada` after
downloading the raw tables into `data/raw/` (not committed; table numbers
above, CSVs from statcan.gc.ca, the survey from Harvard Dataverse
doi:10.7910/DVN/DUS88V). The survey script needs pandas and pyreadstat; the
simulation itself does not.

### A city level for transit

Transit gets two tiers inside each region: its metropolitan areas and the
countryside. With `World.city_profile = "canada"` (the default) every census
metropolitan area is in the model: all 35 from the 2016 Census, Ottawa-Gatineau
split by province, sized by population and given a transit taste from the
share of its commuters using transit (2.3% in Saguenay and Trois-Rivieres to
24.3% in Toronto). Each region holds its province's metro areas in proportion;
small ones are pooled with others of similar transit use, leaving 25 city
places plus a countryside in each region (`tiebout/cities.py`,
`data/cities/cma_2016.csv`). With an empty profile it is one city and one
countryside, and a one-city profile reproduces that model exactly (tested).

"Cities decide" lets each place set its own level, tailored to its residents
but blind to commuting across the metro boundary; every other rule is set by
the province or nation at one level for all its places, which counts that
commuting but can't tailor. scopelang's `devolved`
rule expresses the same thing: the level two below decides, and the province
in between is struck down if it tries.

Cities win only when almost no commuting crosses the metro boundary
(Statistics Canada draws metro areas so that most of it doesn't). National
transit wins only if one national system saves about 10% or more over city or
provincial systems (5% in the one-city model), a number nobody has measured;
the transit verdict rests on it. `validation/city_sensitivity.py` reruns the
analysis with the gap between metro areas halved and with Toronto, Montreal and
Vancouver at post-pandemic (May 2023) transit use: the robust rule is the same
in every case. Re-run one area with `python -m tiebout uncertainty --ranges canada --only
transit`.

### Climate and carbon pricing

Climate is a fifth area, separate from public environmental spending, because
it works through regulation: emitters pay, so no cost of public funds applies,
and abatement costs differ by province. Rules: provinces decide, a uniform
national quantity standard, a quantity floor, a national carbon price, or a
price floor provinces may exceed. Calibration: provincial disagreement from
the 2019 Canadian Election Study carbon-tax question; abatement-cost spread
informed by 2024 emissions per person (ECCC, log spread 0.66); and the link
between high emissions and low support (r = -0.82 across provinces).

A carbon price wins 99% of sampled worlds and keeps 99% of the attainable
gain; a uniform quantity standard keeps 44%. With equal costs the two are
identical; any cost difference favours the price. The model leaves out trade
exposure, emissions leaking abroad, revenue use and the politics that ended
Canada's consumer carbon charge in April 2025.

### Schools and language

Regions carry Canada's official-language profile (2021 Census, French as first
official language spoken: Quebec 82.2%, New Brunswick 30.0%, Ontario 3.4%; 19.5%
across the model's 16 regions against 21.4% nationally). A national standard sets
one curriculum, which costs minority-language residents unless a national system
accommodates them; provincial rules leave content with the provinces, as Charter
section 23 boards do now. Minority-language residents also face a higher moving
cost, informed by Quebec having the lowest interprovincial out-migration (0.35% a
year). The curriculum cost barely moves a national welfare total because the
minority is a fifth of the country: a limit of utilitarian aggregation, and the
reason constitutional protections exist.

### Looking ahead

The model describes long-run structure, not a forecast. Two measured inputs
have projections, so those verdicts are dated: climate (ECCC's 2025
projections of emissions per person by province keep the spread at 0.64 to
0.68 through 2035, far above the 0.2 where a carbon price stops beating a
uniform standard) and transit (metro areas' shares projected to 2041 by
continuing 2011-2016 growth; `validation/city_sensitivity.py
canada_2041_trend`). `validation/early_warning.py` writes
`results/watchlist.json`: for each verdict, the number that decides it, the
flip point read from the threshold maps, the best current estimate and what
would measure it.

### Backtest and who loses

`validation/backtest.py` gives the model only the data that existed before
three reforms (1996 block grant for welfare, 2006 Metrolinx, 2016 national
carbon price floor): spending by function from the older FMS classification
(`data/scripts/fetch_fms_1989_2009.py`, table 10-10-0039, bridged to today's
classification on their overlap year), and inequality, migration, regional
incomes and emissions from the ten years before each date. All 13 verdicts
pick the same rule as today. Two of the three reforms moved the way the model
recommends; the 1996 block grant did not, and afterwards provincial
social-services spending fell from 4.4% to 3.4% of GDP and spread out
between provinces. Survey opinion (2019) and the city map (2016) could not be
dated and are held at today's values.

`validation/feasibility.py` runs each recommended rule against provinces
deciding and measures the change for the people starting in each region.
Equalization has concentrated losers (about a third of regions, the worst
losing 2.5 times the average gain); a carbon price has almost none, so the
model can't explain the 2025 repeal of the consumer charge through lost
welfare.

### Real provinces

By default each region's average taste, abatement cost and productivity are
random draws with Canada's measured spread. `World.province_profile="canada"`
(`tiebout/provinces.py`, data from `data/scripts/province_profile.py`) gives
each region its province's measured values instead: 2019 Canadian Election
Study means, 2024 emissions per person, 2015-2024 market income.
`validation/provinces_run.py` reruns the analysis that way (same verdicts,
except schools moves to a small matching grant, still no clear winner), and
`feasibility.py --provinces` / `politics.py --provinces` name who loses and who
opposes: mostly Alberta.

### Politics: which rules would pass

`validation/politics.py` adds, after each simulation, what voters see and a
vote: under a carbon price households see the charge on all remaining
emissions but only part of the rebate (Mildenberger et al. 2022 found low
awareness and underestimation in Canada), and a rule passes when regions
holding a majority (or two thirds) of people perceive a gain over provinces
deciding. A carbon price passes in every sampled world on real welfare and in
none as voters see it: payments are about 19 times the real gain, so most
regions gain only if voters see about 94% of the rebate. The best rule that
passes is a quantity floor, keeping about half the gain. Other areas lose
little to politics.

### Accuracy checks

- `validation/seed_stability.py`: re-scores 30 worlds per area with 12 fresh
  seeds. The winning rule agrees in 142 of 150; every flip is between
  near-equivalent rules.
- The one-area-at-a-time shortcut is checked against joint optimisation of all
  five areas on 16 worlds: 91% agreement, at least 97% of the joint gain kept.

See [VERIFICATION.md](VERIFICATION.md) for every factual claim and its sources,
and [COMPARISONS.md](COMPARISONS.md) for how each finding compares with
published work.

### What it leaves out

Governments are honest median voters, the centre knows the spillover rates,
central policy has to be uniform, and regions can't learn from each other's
experiments. Each of these would shift the answer; see the end of the report.

## Layout

```
scopelang/   lexer.py, parser.py, interpreter.py (the precedence rules live here)
tiebout/     model.py (simulation), optimize.py (search), experiments.py (study + report),
             bridge.py (scopelang <-> arrangements), config.py (default world),
             cities.py (metropolitan areas per region)
examples/    cannabis.jur, min_wage.jur, river.jur, dispute.jur
tests/
```

## Data sources and licences

- **Statistics Canada** tables 10-10-0005, 11-10-0134, 11-10-0190,
  17-10-0005, 17-10-0009, 17-10-0022 and 36-10-0222, reference years 2008 to
  2024. Adapted from Statistics Canada, under the Statistics Canada Open
  Licence. This does not constitute an endorsement by Statistics Canada of
  this product. Raw tables are not committed; `data/targets.json` holds the
  derived values.
- **Statistics Canada, 2016 Census**: population of every census metropolitan
  area and province (The Daily, 8 February 2017, Tables 2 and 3) and transit
  share of commuters by metropolitan area (The Daily, 29 November 2017, Table
  1), transcribed into `data/cities/cma_2016.csv`. Adapted from Statistics
  Canada, under the same licence. Ottawa-Gatineau split by province from the
  City of Ottawa's 2016 Census page.
- **Environment and Climate Change Canada**, greenhouse gas emissions by
  province, 2024 (Canadian Environmental Sustainability Indicators).
- **2019 Canadian Election Study, online survey.** Stephenson, Laura B.;
  Harell, Allison; Rubenson, Daniel; Loewen, Peter John, 2020, Harvard
  Dataverse, [doi:10.7910/DVN/DUS88V](https://doi.org/10.7910/DVN/DUS88V),
  licensed CC BY-NC 4.0. Only derived provincial aggregates are committed
  (`data/ces_disagreement.json`); the survey file is not.
- **Marginal cost of public funds:** Dahlby, B. and Ferede, E. (2012), "The
  Effects of Tax Rate Changes on Tax Bases and the Marginal Cost of Public
  Funds for Canadian Provincial Governments", *International Tax and Public
  Finance* 19(6): 844-883; Dahlby, B. and Ferede, E. (2022), "What Are the
  Economic Costs of Raising Revenue by the Canadian Federal Government?",
  Fraser Institute.
- **Inequality aversion:** Layard, R., Mayraz, G. and Nickell, S. (2008), "The
  Marginal Utility of Income", *Journal of Public Economics* 92(8-9):
  1846-1857 (combined estimate 1.26).
- **Industrial carbon price path** ($95 per tonne in 2026 to $140 in 2040): as
  reported by the International Carbon Action Partnership and EY, May 2026.
- `audit/` holds automated reviews by [ai-auditor](https://github.com/alexdduda/ai-auditor)
  (model-generated; challenges to check, not verified findings).
