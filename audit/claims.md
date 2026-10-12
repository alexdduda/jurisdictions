# Claims to audit: which level of government should decide each policy area

These claims come from an agent-based simulation ("tiebout") of fiscal
federalism. Audit both the conclusions and whether the model supports them.

## The model

- 16 regions on a 4x4 torus, 100 agents each. Agents have a log-normal income
  and a taste in [0, 1] for each public good.
- Each round, each region's government sets the level its median resident
  prefers, within the national rule. Then up to half the agents compare their
  region with 4 others and move if the utility gain beats a moving cost.
  Crowding imposes a cost proportional to population.
- Public good utility: 2 * taste * e - cost * p^2, where
  e = (1 - s) * p_own + s * mean(p_neighbours) and s is the spillover share.
  A region ignoring spillovers chooses p = taste * (1 - s); the social optimum
  is p = taste / unit_cost.
- Central provision can be cheaper per unit (scale economies). Money run
  through the national budget carries an overhead; money raised locally carries
  its own overhead.
- Redistribution: utility log(income * (1 - t) + transfer), with
  transfer = t * mean income of the pool * (1 - deadweight * t). The pool is the
  region, or the nation when redistribution is national. Regional rates are set
  by the median earner.
- Five rules per policy area: regions decide; one national standard; a national
  floor; a national cap; a matching grant (the nation pays a share of regional
  costs). National policy must be uniform across regions.
- Welfare is the unweighted mean of agent utility.

## Method

Every uncertain parameter got a wide range. 200 worlds per policy area were
sampled (Latin hypercube) and every candidate rule and level was scored in every
world on 3 shared random seeds. The recommended rule is the single fixed rule
with the lowest expected regret across all worlds. A check against joint
optimisation of all four areas (8 worlds) agreed on the rule in 94% of cases
and kept at least 96% of the jointly optimal gain.

Ranges: spillover 0 to 0.15 (schools), 0.3 to 0.8 (environment), 0.05 to 0.35
(transit). Regional taste disagreement 0.1 to 0.3 (schools), 0.02 to 0.15
(environment), 0.05 to 0.2 (transit). Scale savings 0 to 0.1 (schools,
environment), 0.1 to 0.45 (transit). National and local overhead 0 to 0.35
each. Mobility 0 to 0.5. Income log-sd 0.4 to 1.0. Tax deadweight 0.25 to 0.8.

## Conclusions

1. **Transit should be national.** A national standard wins in 94% of worlds
   and keeps 89% of the gain that perfect knowledge would achieve over regional
   control. Scale economies drive it.
2. **Environmental protection should be national.** A national standard wins in
   67% of worlds, a national floor in 31%. The standard keeps 88% of the
   possible gain. Which of the two wins depends mainly on whether national or
   local money is costlier to raise.
3. **Redistribution should be national.** A national scheme wins in 100% of
   worlds. With regional redistribution, mobile high earners sort into low-tax
   regions and regional tax bases diverge. A national floor is nearly as good
   only when nobody moves.
4. **Schools should stay regional.** No fixed national rule clearly beats
   regional control: the best (a 10% matching grant) keeps 4% of a gain that
   is itself small (8% of the stakes in transit). A national standard is the
   one clearly harmful choice.
5. **General lesson:** split power by policy area. Spillovers push authority
   up (toward floors, grants or standards), regional disagreement pushes it
   down, and scale economies justify centralising only when they outweigh
   disagreement.

## Limits the study already acknowledges

Governments are honest median voters (no capture or lobbying). Regions cannot
learn from each other's policy experiments. National policy cannot vary by
region. Public good costs are not tied to regional income, so poor regions'
difficulty paying for a national floor is missing. 16 equal regions do not
resemble any real federation.
