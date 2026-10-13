# Claims to audit: which level of government should decide each policy area in Canada

These claims come from an agent-based simulation of fiscal federalism,
calibrated and partly validated against Canadian data. Audit the conclusions,
whether the model supports them, and whether the calibration and validation
are sound. An earlier automated review of this study raised five challenges;
what was done about each is listed at the end.

## The model

- 16 regions on a 4x4 torus, 100 agents each. Agents have a portable skill
  (log-normal) and a taste in [0, 1] for each public good. Income is skill
  times the productivity of the region the agent lives in, so moving changes
  income.
- Each round, each region's government sets the level its median resident
  prefers, within the national rule. Then some agents compare their region
  with 4 others and move if the utility gain beats a moving cost. Crowding
  imposes a cost proportional to population.
- Public good utility: 2 * taste * e - cost * burden * p^2, where
  e = (1 - s) * p_own + s * mean(p_neighbours) and s is the spillover share.
  burden = (national mean income / regional mean income) ^ k, so local money
  is dearer where incomes are lower (fiscal capacity). National taxes are
  paid in proportion to income and carry no such penalty. A region ignoring
  spillovers chooses p = taste * (1 - s) / (price * burden).
- Central provision can be cheaper per unit (scale economies). Money raised
  nationally and locally each carry an overhead (marginal cost of public
  funds minus one).
- Redistribution: utility log(income * (1 - t) + transfer), with
  transfer = t * mean income of the pool * (1 - deadweight * t). The pool is
  the region, or the nation when redistribution is national. Regional rates
  are set by the median earner. With no redistribution domain, utility
  includes log(income) so agents still move for jobs.
- Five rules per policy area: regions decide; one uniform national standard;
  a national floor; a national cap; a matching grant. National policy is
  uniform across regions. Welfare is the unweighted mean of agent utility.

## Calibration to Canada

| parameter | value | source |
|---|---|---|
| between-province disagreement about each service | schools 0.025 to 0.036, environment 0.073 to 0.076, transit 0.069 to 0.082 (sd of regional taste centres on a 0-1 scale) | Statistics Canada 10-10-0005 spending by function, 2015-2024, measured per person, as a budget share, net of provincial GDP, and per child aged 5-17. Spending is the model's cost (p squared), so taste spread = CV(spending) / 4 |
| within-province disagreement | 0.25 to 0.30, the model's ceiling | 2019 Canadian Election Study (about 37,000 respondents): between-province spread is 8% (education) and 20% (environment) of within-province spread, from an ordered-probit reading of "spend less / same / more" with bootstrap noise correction |
| fiscal capacity elasticity k | schools 0.15 to 0.25, environment 0.12 to 0.20, transit about 0.03 | Income elasticity of provincial spending across provinces, 2008-2024 (0.41, 0.32, 0.05), halved because spending is p squared |
| income inequality | log-sd 0.78 to 0.84 | market-income Gini 0.43, Statistics Canada 11-10-0134 |
| regional productivity and mobility | calibrated jointly | provincial average market-income spread 12-19% (11-10-0190) and interprovincial migration 0.75% a year (17-10-0022). 52-67% of sampled worlds land on both targets |
| cost of raising a dollar | national overhead 0.2 to 1.0; provincial = national times 0.6 to 1.5 | Dahlby and Ferede (2012, 2022): federal personal income tax marginal cost of funds about 2.86 (2021); provincial 1.44 to 3.81 (2006); no systematic ordering |
| tax deadweight (redistribution) | 0.4 to 0.9 | implies a marginal cost of funds of about 1.3 to 2.2 at a 30% rate |
| spillovers, scale savings, crowding | not calibrated | no Canadian measurement found |

## Method

200 worlds per policy area sampled across the remaining ranges (Latin
hypercube), every candidate rule and level scored in every world on 3 shared
seeds. The recommended rule is the single fixed rule with the lowest expected
regret. Areas are analysed separately; a joint optimisation over 8 worlds
agreed on the rule in 94% of cases and kept at least 96% of the joint gain.

## Validation (outcomes the model was not fitted to)

| pattern across provinces | Canada | model |
|---|---|---|
| next-year net migration on provincial income, within provinces over time | +0.32 | +0.30 |
| the same on spending for services | -0.22 | -0.04 |
| market-income inequality and wanting redistribution (rank correlation, survey) | +0.58 (p = 0.09, n = 10) | +0.97 |
| market-income inequality and spending on redistribution | -0.19 (p = 0.60) | +0.39 |

The last row fails. We argue the failure biases against our redistribution
conclusion: the model makes regional redistribution look more effective than
it is in Canada.

## Conclusions

1. **Redistribution should be national.** A national scheme wins 98% of
   worlds and keeps 87% of the gain perfect knowledge would achieve. It wins
   even with no mobility at all, because pooling across provinces with
   different average incomes helps.
2. **Transit should be national**, but only conditionally: it wins 97% of
   sampled worlds, and the threshold map says a national standard wins once
   one system saves more than 5 to 10%. Below that, provinces should run it.
3. **Environmental protection should have a national standard** (wins 75%,
   keeps 90%). If provinces raise money about 40% more cheaply than Ottawa, a
   national floor wins instead.
4. **Schools: a national standard is the lowest-regret rule** (wins 62%,
   keeps only 21%), with the smallest stakes of the four. Which level raises
   money more cheaply decides it.
5. **General lesson:** in Canada, people within a province disagree five to
   twelve times more than provinces disagree with each other, so the main
   argument for provincial control (provinces wanting different things) is
   weak. Fiscal capacity differences and spillovers push toward national
   rules.

## Challenges from the earlier review, and responses

- "The verdicts restate the guessed ranges": ranges replaced by Canadian
  measurements where any exist; unmeasured parameters reported as thresholds.
- "Transit belongs to metropolitan areas": not addressed. The model has no
  metropolitan level. We consider this the most serious open gap.
- "National redistribution partly reflects the log-utility welfare measure":
  not addressed; no sensitivity analysis on inequality aversion yet.
- "Provinces differ in taste for redistribution": confirmed by the survey
  (between/within spread 0.21) but not modelled.
- "Environmental policy can use prices": not modelled.

## Errors found and corrected during the study

- Spending spread was first converted to taste spread as CV / 2 instead of
  CV / 4, overstating disagreement by a factor of two.
- Productivity was calibrated in a four-area world and reused in single-area
  worlds, where no redistribution means no income sorting; almost no
  single-area world matched the Canadian targets until recalibrated.
- A first reading of the migration data concluded the original model got
  migration wrong; testing the model showed it did not.
