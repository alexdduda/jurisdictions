# Validation

Calibration fits the model to Canadian inputs. Validation asks whether it then
reproduces Canadian *outcomes* it was never fitted to. Each script reruns on
the data in `data/raw/` (see the main README for downloads).

## The tests

| script | question |
|---|---|
| `redistribution.py` | Across provinces, does market-income inequality predict wanting redistribution (survey) and spending on it (budgets)? |
| `migration_and_capacity.py` | Do people move toward higher incomes or better services? Do richer provinces spend more per person? |
| `model_vs_canada.py` | Run the calibrated model under Canada's arrangement and apply the same tests to its output |

## Results

**In the data** (ten provinces, 2008 to 2024):

| pattern | value | strength |
|---|---|---|
| inequality → wanting redistribution | +0.58 (rank correlation) | suggestive, p = 0.09, n = 10 |
| inequality → spending on redistribution | −0.19 | none, p = 0.60 |
| next year's net migration, within a province over time: income | +0.32 (standardized) | 160 province-years |
| the same: spending on services | −0.22 | 160 province-years |
| income elasticity of provincial spending | schools 0.41, environment 0.32, social protection 0.67, transit 0.05, health 0.01 | positive in 94%, 76%, 100%, 59%, 71% of years |

**The model against the data** (`model_vs_canada.py`, 12 seeds):

| test | Canada | before regional productivity | after |
|---|---|---|---|
| migration follows income | +0.32 | +0.36 | +0.30 |
| migration follows services | −0.22 | +0.01 | −0.04 |
| inequality → wanting | +0.58 | +0.98 | +0.97 |
| inequality → spending | −0.19 | +0.40 | +0.39 |

## What we concluded, including where we were wrong

1. **Fiscal capacity was missing.** Richer provinces spend more on schools,
   the environment and social protection; the original model, with equally
   rich regions, could not. The model now has regional productivity and a
   per-service capacity elasticity, calibrated from the elasticities above
   (halved, because spending is the model's cost, which grows with the level
   squared). This fixes the gap by construction, so it is calibration, not an
   independent confirmation.
2. **Migration did not discriminate between versions.** We first read the
   migration data as contradicting the model ("people move for income, the
   model says services"). Running the same test on the model showed that the
   original already moved people toward richer regions, through income sorting
   and richer redistribution pools. Both versions match. That first reading
   was wrong.
3. **Regional redistribution still fails, in a known direction.** In the
   model, more unequal regions want and get more redistribution. In Canada the
   most unequal provinces are poorer and lean on federal programs, so they
   spend less. The model therefore makes regional redistribution look more
   effective than it is. That bias works against the conclusion that
   redistribution should be national, so the conclusion survives it. The
   mechanism behind the gap (poverty and inequality occurring together,
   federal programs concentrated in poorer provinces) is not modelled.
4. **The model is too tidy.** Inequality predicts wanting redistribution at
   +0.97 in the model and +0.58 in the data: real preferences depend on much
   more than income.

## A calibration error this process caught

Provincial spending measures the model's cost, which grows with the square of
the service level, so the spread of spending is twice the spread of levels.
The first calibration converted spending spread straight into taste spread
and overstated regional disagreement by a factor of two. Fixed in
`tiebout/canada.py`; every result after commit 5a867ce uses the corrected
values.

## A calibration that didn't transfer

Mobility and regional productivity were first calibrated in a world with all
four policy areas, then reused in the uncertainty analysis, which studies each
area in its own world. Each sampled world records its realised income spread
and migration, and that check showed almost none of the public-goods worlds
(0 to 1%) landed on the Canadian targets: their regional income spread was
about 8% against Canada's 12 to 19%. Without a redistribution domain, high
earners have no reason to sort, so the same productivity gap produces less
regional inequality. Public-goods worlds now have their own productivity range
(0.09 to 0.17), chosen to hit the same targets; the four-area cross-check keeps
the original one. The earlier error understated fiscal-capacity differences,
which favour national financing, so it had made national verdicts harder to
reach, not easier.

## A bug caught before publishing

The first run with a city level offered "cities decide" in the threshold maps
but never in the uncertainty analysis: the list of candidate rules was built
from the base transit settings, which have no city level, instead of from the
sampled worlds. Cities therefore won 0 of 200 worlds by construction. Fixed
in `tiebout/uncertainty.py`, with a regression test
(`test_uncertainty_offers_city_rules_for_transit`). Each policy area also now
draws from its own random stream, so re-running one area can't change another.
