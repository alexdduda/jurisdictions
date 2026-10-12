# The best balance between local and central power (in this model)

Seeds: 6 · simulations for the main search: 2154 · runtime 400.8s

## The optimum

| domain | best arrangement | spillover | heterogeneity | scale |
|---|---|---|---|---|
| schools | **local** | 0.05 | 0.2 | 0.0 |
| environment | **floor 0.5** | 0.6 | 0.06 | 0.0 |
| transit | **central 0.65** | 0.2 | 0.1 | 0.3 |
| redistribution | **central 0.225** | – | – | – |

Welfare is average utility per person. The last column shows how much of the gap between *everything local* and the optimum each option closes.

| arrangement | welfare | gap closed |
|---|---|---|
| all local | 0.6180 ± 0.0272 | 0% |
| all central (best levels) | 0.7216 ± 0.0279 | 53% |
| best local-or-central per domain | 0.7873 ± 0.0292 | 87% |
| optimum | 0.8123 ± 0.0292 | 100% |

Best purely local-or-central choice per domain: schools = local, environment = central 0.5, transit = central 0.65, redistribution = central 0.225.

### What each mode can do for each domain (others held at the optimum)

| domain | local | central | floor | ceiling | matched |
|---|---|---|---|---|---|
| schools | **local** | central 0.5 (−65.8) | **floor 0** | **ceiling 1** | matched 10% (−3.7) |
| environment | local (−90.3) | central 0.5 (−25.0) | **floor 0.5** | ceiling 0.3 (−90.3) | matched 50% (−20.7) |
| transit | local (−75.3) | **central 0.65** | floor 0.4 (−72.5) | ceiling 0.6 (−75.3) | matched 10% (−70.4) |
| redistribution | local (−30.3) | **central 0.225** | floor 0.25 (−0.7) | ceiling 0.1 (−14.0) | – |

Numbers in brackets: welfare lost versus the best mode, in thousandths of a util.

### What changes on the ground

| domain | mean level, all local | mean level, optimum | spread across regions at optimum |
|---|---|---|---|
| schools | 0.479 | 0.478 | 0.195 |
| environment | 0.201 | 0.500 | 0.000 |
| transit | 0.397 | 0.650 | 0.000 |
| redistribution | 0.154 | 0.225 | 0.000 |

Income sorting (spread of regional mean incomes): 0.213 with everything local, 0.069 at the optimum.

## Where the answer flips

Each cell is the best arrangement for a single public good with those properties. `≈` means the winner beats the runner-up mode by less than two standard errors.

### Spillovers vs. regional differences (no scale economies)

| spillover ↓ / heterogeneity → | 0.0 | 0.1 | 0.2 | 0.3 |
|---|---|---|---|---|
| 0.0 | local | local | local | local |
| 0.1 | matched 10% | floor 0.3 ≈ | floor 0.1 ≈ | floor 0.1 |
| 0.2 | floor 0.5 | matched 10% | matched 10% | matched 10% |
| 0.4 | floor 0.5 | floor 0.5 | matched 30% ≈ | matched 30% |
| 0.6 | floor 0.5 | floor 0.5 | floor 0.5 | floor 0.5 |
| 0.8 | floor 0.5 | floor 0.5 | floor 0.5 | floor 0.5 |

### Scale economies vs. regional differences (no spillovers)

| scale ↓ / heterogeneity → | 0.0 | 0.1 | 0.2 | 0.3 |
|---|---|---|---|---|
| 0.0 | local | local | local | local |
| 0.1 | local | local | local | local |
| 0.2 | central 0.6 | central 0.6 | local | local |
| 0.3 | central 0.6 | central 0.7 | central 0.7 | local |
| 0.5 | central 0.9 | central 0.9 | central 0.9 | central 0.9 |

### Redistribution as people become more mobile

| share considering a move each step | winner | welfare: local | floor | central | local tax rate | income sorting under local |
|---|---|---|---|---|---|---|
| 0.0 | central 0.25 | -0.0600 | -0.0561 | -0.0554 | 0.158 | 0.065 |
| 0.05 | central 0.25 | -0.0784 | -0.0563 | -0.0554 | 0.169 | 0.233 |
| 0.1 | central 0.25 ≈ | -0.0947 | -0.0561 | -0.0554 | 0.162 | 0.276 |
| 0.25 | central 0.25 ≈ | -0.0852 | -0.0574 | -0.0554 | 0.152 | 0.263 |
| 0.5 | central 0.25 | -0.0901 | -0.0736 | -0.0554 | 0.137 | 0.289 |

## How robust is the optimum?

| assumptions | schools | environment | transit | redistribution |
|---|---|---|---|---|
| baseline | local | floor 0.5 | central 0.65 | central 0.225 |
| no national overhead | local | central 0.5 | central 0.7 | central 0.225 |
| heavy national overhead (0.3) | local | floor 0.5 | central 0.55 | central 0.225 |
| no mobility | floor 0.075 | floor 0.5 | central 0.65 | central 0.225 |
| high mobility (0.5) | local | floor 0.5 | central 0.65 | central 0.225 |
| more income inequality | local | floor 0.5 | central 0.65 | central 0.375 |

## What this model leaves out

- **Floors are unfunded mandates.** A floor that binds everywhere is a central policy paid for locally. It beats `central` here only because national money carries overhead and local money doesn't. Real unfunded mandates have their own costs (poor regions pay as much as rich ones, and there's resentment and evasion) that this model doesn't charge for. With zero overhead, environment flips to central.
- Modes that never bind (`floor 0`, `ceiling 1`) tie with `local` because they *are* local.
- `±` on welfare levels is spread across random worlds. Comparisons between arrangements are paired on the same worlds, so they are much more precise than those intervals suggest.
- Governments here are honest median voters. No capture, no lobbying, no corruption at either level.
- The centre knows the spillover rate exactly when it sets a match rate. In reality it has to guess.
- There is no policy experimentation: regions cannot learn from each other's results, which is one of the strongest real arguments for decentralisation.
- Central policy must be uniform. A centre that could tailor policy region by region would always win, but it would also need information it rarely has.
- All parameters are assumptions. The phase maps matter more than the headline optimum: they say *which features of a policy area* push it up or down a level.

Re-score any arrangement with `python -m tiebout evaluate <file.jur>`. The optimum is saved as `best_arrangement.jur`.
