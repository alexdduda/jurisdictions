"""Agent-based model of how policy authority is split between a nation and its regions.

The world is a torus of regions. Agents have a taste for each public good and
an income. Every step:

  1. Each region's government picks the policy its median resident wants,
     within whatever the national arrangement allows.
  2. Some agents compare their region with a few others and move if the gain
     beats a moving cost (Tiebout's "voting with your feet").

An *arrangement* says, per policy domain, who decides (the same five modes as
scopelang):

    local     regions decide alone
    central   the nation sets one uniform level everywhere
    floor     regions decide, but not below a national minimum
    ceiling   regions decide, but not above a national maximum
    matched   regions decide, and the nation pays a share of their costs

The trade-offs that make the choice non-trivial (Oates' decentralisation
theorem plus the classic objections to it):

  * Tastes differ between regions, so one uniform level fits nobody exactly.
  * Spillovers: part of a region's provision benefits its neighbours, which a
    region ignores, so it under-provides.
  * Scale: central provision can be cheaper per unit.
  * National budgets have overhead (deadweight loss, administration), so moving
    money through the centre is not free.
  * Mobility: agents sort into regions that suit them (good for fit), but
    richer agents also escape redistribution, which hollows out local tax bases.

Public-good utility for agent i in region r:
    2 * taste_i * e_r - (cost share) * unit_cost * p_r**2 - (national tax)
where e_r = (1 - s) * p_r + s * mean(p of neighbours) is the level actually
experienced. A region ignoring spillovers wants p = taste * (1 - s); the social
optimum is p = taste / unit_cost, so local choice under-provides by (1 - s).

Redistribution utility: log(income * (1 - t) + transfer), with
transfer = t * mean income of the pool * (1 - deadweight * t). The pool is the
region, or the whole nation when redistribution is central.
"""

import math
import random
from dataclasses import dataclass, field

MODES = ("local", "central", "floor", "ceiling", "matched", "equalized", "city", "price", "price_floor")


@dataclass(frozen=True)
class Domain:
    name: str
    kind: str = "public_good"   # or "redistribution"
    heterogeneity: float = 0.1  # sd of regional taste centres
    within: float = 0.1         # sd of tastes inside a region
    spillover: float = 0.0      # share of provision felt by neighbours
    scale: float = 0.0          # unit-cost saving under central provision
    weight: float = 1.0
    # How much harder a poorer region finds it to pay for this good: its local
    # cost is scaled by (national mean income / regional mean income) ** this.
    # Elasticity of the provided level with respect to regional income.
    capacity_elasticity: float = 0.0
    # City level (two tiers inside each region). Off when both are 0.
    # urban_premium: how much more city residents value the good than the
    #   countryside (taste shifted by +/- half of it), e.g. transit and density.
    # metro_spillover: share of a place's provision felt by the other part of the
    #   same region (commuting between city and suburbs), which a province
    #   internalises and a city does not.
    urban_premium: float = 0.0
    metro_spillover: float = 0.0
    # Regulatory goods (climate): abatement is paid by emitters, not budgets, so
    # no cost of public funds applies, and costs differ by region. abatement_sd is
    # the log-sd of each region's cost multiplier (0 = equal costs);
    # abatement_taste_corr links high-cost regions to lower taste for the good.
    private_costs: bool = False
    abatement_sd: float = 0.0
    abatement_taste_corr: float = 0.0

    @property
    def two_tier(self) -> bool:
        return self.urban_premium > 0 or self.metro_spillover > 0


@dataclass(frozen=True)
class Policy:
    mode: str = "local"
    level: float = 0.0  # central level, floor, ceiling, match rate, equalization rate, city grant rate, or carbon price

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")

    def label(self) -> str:
        if self.mode == "local":
            return "local"
        if self.mode == "matched":
            return f"matched {self.level:.0%}"
        if self.mode == "equalized":
            return f"equalized {self.level:.0%}"
        if self.mode == "city":
            return "city" if not self.level else f"city + {self.level:.0%} grant"
        if self.mode == "price":
            return f"price {self.level:.3g}"
        if self.mode == "price_floor":
            return f"price floor {self.level:.3g}"
        return f"{self.mode} {self.level:.3g}"


LOCAL = Policy()


@dataclass(frozen=True)
class World:
    domains: tuple[Domain, ...]
    grid: int = 4                  # grid x grid regions on a torus
    agents_per_region: int = 100
    steps: int = 30
    measure_steps: int = 6         # welfare is averaged over the last few steps
    move_share: float = 0.25       # share of agents who consider moving each step
    candidates: int = 4            # other regions each mover looks at
    moving_cost: float = 0.01
    congestion: float = 0.1        # utility cost per unit of (population / average)
    income_sigma: float = 0.6      # log-normal income spread
    deadweight: float = 0.5        # efficiency loss of redistributive taxes
    national_overhead: float = 0.1 # extra cost per unit of money run through the centre
    local_overhead: float = 0.0    # extra cost per unit of money raised and spent locally
    max_level: float = 1.5
    max_tax: float = 0.9
    # Inequality aversion in redistribution: utility of consumption is
    # (c^(1-a) - 1) / (1-a); a = 1 is log utility (the default).
    inequality_aversion: float = 1.0
    # Regional productivity: an agent's income is skill * productivity of the
    # region they live in, so moving changes income. 0 means every region is
    # equally productive (the original model).
    productivity_sd: float = 0.0
    # Share of each region's residents living in its city (used only by two-tier goods).
    # Statistics Canada: 71.8% of Canadians lived in a census metropolitan area, July 2021.
    urban_share: float = 0.72

    def domain(self, name: str) -> Domain:
        for d in self.domains:
            if d.name == name:
                return d
        raise KeyError(name)


@dataclass
class Outcome:
    welfare: float
    components: dict[str, float] = field(default_factory=dict)
    policy_mean: dict[str, float] = field(default_factory=dict)
    policy_sd: dict[str, float] = field(default_factory=dict)
    income_sorting: float = 0.0    # sd of regional mean income / national mean (regional income spread)
    crowding: float = 0.0          # largest region / average region
    migration: float = 0.0         # share of agents who changed region per round


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    m = n // 2
    return s[m] if n % 2 else 0.5 * (s[m - 1] + s[m])


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _sd(values) -> float:
    values = list(values)
    if len(values) < 2:
        return 0.0
    mu = _mean(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / len(values))


def torus_neighbors(grid: int) -> list[list[int]]:
    out = []
    for r in range(grid * grid):
        x, y = r % grid, r // grid
        out.append(sorted({
            ((x + dx) % grid) + ((y + dy) % grid) * grid
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
        } - {r}))
    return out


def _bound(local: list[float], policy: Policy) -> list[float]:
    if policy.mode == "floor":
        return [max(v, policy.level) for v in local]
    if policy.mode == "ceiling":
        return [min(v, policy.level) for v in local]
    return local


class _Run:
    """One simulation of one arrangement with one seed."""

    def __init__(self, world: World, arrangement: dict[str, Policy], seed: int):
        self.world = world
        self.arrangement = arrangement
        rng = random.Random(seed)
        self.move_rng = random.Random(seed * 7919 + 17)

        self.R = world.grid ** 2
        self.nbrs = torus_neighbors(world.grid)
        self.N = self.R * world.agents_per_region
        self.region = [i // world.agents_per_region for i in range(self.N)]
        # Skill is portable; income also depends on the region's productivity.
        self.skill = [math.exp(rng.gauss(0, world.income_sigma)) for _ in range(self.N)]
        self.tastes: dict[str, list[float]] = {}
        self.abatement: dict[str, list[float]] = {}
        for d in world.domains:
            if d.kind == "public_good":
                draws = [rng.gauss(0, d.heterogeneity) for _ in range(self.R)]
                if d.abatement_sd > 0:
                    # Separate stream, so goods without regional cost differences are unchanged.
                    cost_rng = random.Random(f"{seed}:abatement:{d.name}")
                    z = [cost_rng.gauss(0, 1) for _ in range(self.R)]
                    sd = d.abatement_sd
                    self.abatement[d.name] = [math.exp(sd * zr - sd * sd / 2) for zr in z]
                    c = _clamp(d.abatement_taste_corr, -1.0, 1.0)
                    # High-cost regions want less of the good (corr > 0 means that).
                    draws = [-c * d.heterogeneity * z[r] + math.sqrt(1 - c * c) * draws[r] for r in range(self.R)]
                centres = [_clamp(0.5 + g, 0, 1) for g in draws]
                self.tastes[d.name] = [
                    _clamp(centres[self.region[i]] + rng.gauss(0, d.within), 0, 1)
                    for i in range(self.N)
                ]
        # City or countryside, fixed per person and kept when moving region.
        urban_rng = random.Random(seed * 31337 + 5)  # separate stream: one-tier worlds are unchanged
        self.urban = [1 if urban_rng.random() < world.urban_share else 0 for _ in range(self.N)]
        self.place_tastes: dict[str, list[float]] = {}
        for d in world.domains:
            if d.kind == "public_good" and d.two_tier:
                half = d.urban_premium / 2
                self.place_tastes[d.name] = [
                    _clamp(self.tastes[d.name][i] + (half if self.urban[i] else -half), 0, 1) for i in range(self.N)
                ]
        sd = world.productivity_sd
        prod_rng = random.Random(seed * 104729 + 3)  # separate stream: sd = 0 reproduces the original draws
        self.productivity = (
            [math.exp(prod_rng.gauss(0, sd) - sd * sd / 2) for _ in range(self.R)] if sd > 0 else [1.0] * self.R
        )
        # With no redistribution domain, income would never enter utility; add it so
        # agents can move for higher incomes. (Redistribution's log consumption covers it otherwise.)
        self.private_consumption = sd > 0 and not any(d.kind == "redistribution" for d in world.domains)
        self.national_income = _mean(self.skill[i] * self.productivity[self.region[i]] for i in range(self.N))

    def income(self, i: int, r: int) -> float:
        return self.skill[i] * self.productivity[r]

    # --- government ---

    def region_state(self, residents: list[list[int]]) -> list[tuple]:
        """Per-domain, per-region quantities agents need to evaluate a region."""
        w = self.world
        pops = [len(res) for res in residents]
        self.national_income = _mean(self.income(i, self.region[i]) for i in range(self.N))
        self.regional_income = [
            _mean(self.income(i, r) for i in res) if res else self.national_income
            for r, res in enumerate(residents)
        ]
        state = []
        for d in w.domains:
            policy = self.arrangement.get(d.name, LOCAL)
            if d.kind == "public_good" and d.two_tier:
                state.append(self._public_good_two_tier(d, policy, residents, pops))
            elif d.kind == "public_good":
                state.append(self._public_good(d, policy, residents, pops))
            elif d.kind == "redistribution":
                state.append(self._redistribution(d, policy, residents))
            else:
                raise ValueError(f"unknown domain kind {d.kind!r}")
        return state

    def _public_good(self, d: Domain, policy: Policy, residents, pops) -> tuple:
        w, s = self.world, d.spillover
        theta = self.tastes[d.name]
        # Fiscal capacity: local money is dearer, in utility, where incomes are lower.
        # National taxes are paid in proportion to income, so they carry no such penalty.
        k = d.capacity_elasticity
        burden = [
            (self.national_income / self.regional_income[r]) ** k if k and self.regional_income[r] > 0 else 1.0
            for r in range(self.R)
        ]
        # Regional cost multipliers (1 everywhere unless the good has abatement_sd).
        a = self.abatement.get(d.name, [1.0] * self.R)
        if d.private_costs:
            # Emitters pay; no budget, so no cost of public funds at either level.
            unit, local_share = 1.0, 1.0
            local = [
                _clamp(_median([theta[i] for i in res]) * (1 - s) / (burden[r] * a[r]), 0, w.max_level) if res else 0.0
                for r, res in enumerate(residents)
            ]
            if policy.mode == "central":
                p = [_clamp(policy.level, 0, w.max_level)] * self.R       # one quantity everywhere
            elif policy.mode == "price":
                # Every region abates until marginal cost 2 * a * p equals the price.
                p = [_clamp(policy.level / (2 * a[r]), 0, w.max_level) for r in range(self.R)]
            elif policy.mode == "price_floor":
                p = [max(local[r], _clamp(policy.level / (2 * a[r]), 0, w.max_level)) for r in range(self.R)]
            else:
                p = _bound(local, policy)
            experienced = [(1 - s) * p[r] + s * _mean(p[n] for n in self.nbrs[r]) for r in range(self.R)]
            gain = [d.weight * 2 * experienced[r] for r in range(self.R)]
            cost = [d.weight * a[r] * burden[r] * p[r] ** 2 for r in range(self.R)]
            return ("pg", d.name, theta, gain, cost, p)
        if policy.mode == "central":
            p = [_clamp(policy.level, 0, w.max_level)] * self.R
            unit, local_share = 1.0 - d.scale, 0.0
        else:
            match = policy.level if policy.mode == "matched" else 0.0
            local_share = 1.0 - match
            unit = 1.0
            price = max(local_share, 0.05) * (1 + w.local_overhead)
            local = [
                _clamp(_median([theta[i] for i in res]) * (1 - s) / (price * burden[r]), 0, w.max_level) if res else 0.0
                for r, res in enumerate(residents)
            ]
            p = _bound(local, policy)

        # Equalization: regions decide, but the nation tops up each poorer region's
        # ability to pay by a share q of its gap to the national mean, and pays the
        # difference in cost at the national cost of funds. With no fiscal-capacity
        # effect (k = 0) it is identical to letting regions decide.
        equalization_spend = 0.0
        if policy.mode == "equalized" and k:
            q = _clamp(policy.level, 0.0, 1.0)
            topped = [
                self.regional_income[r] + q * max(0.0, self.national_income - self.regional_income[r])
                for r in range(self.R)
            ]
            eq_burden = [(self.national_income / topped[r]) ** k if topped[r] > 0 else 1.0 for r in range(self.R)]
            local = [
                _clamp(_median([theta[i] for i in res]) * (1 - s) / (price * eq_burden[r]), 0, w.max_level) if res else 0.0
                for r, res in enumerate(residents)
            ]
            p = local
            equalization_spend = sum(
                pops[r] * unit * local_share * (burden[r] - eq_burden[r]) * p[r] ** 2 for r in range(self.R)
            ) / self.N
            burden = eq_burden

        experienced = [
            (1 - s) * p[r] + s * _mean(p[n] for n in self.nbrs[r]) for r in range(self.R)
        ]
        national_spend = sum(pops[r] * unit * (1 - local_share) * p[r] ** 2 for r in range(self.R)) / self.N
        national_tax = (national_spend + equalization_spend) * (1 + w.national_overhead)
        gain = [d.weight * 2 * experienced[r] for r in range(self.R)]
        local_cost = unit * local_share * (1 + w.local_overhead)
        cost = [d.weight * (local_cost * burden[r] * p[r] ** 2 + national_tax) for r in range(self.R)]
        return ("pg", d.name, theta, gain, cost, p)

    def _public_good_two_tier(self, d: Domain, policy: Policy, residents, pops) -> tuple:
        """A good provided separately in each region's city (place 1) and countryside (place 0).

        "city" lets each place decide for itself: tailored to its own residents, but
        blind to the commuting spillover onto the other place. Every other rule is
        decided by the province (or nation) at one level across both places, which
        internalises that spillover but cannot tailor to density.
        """
        w, s, sm = self.world, d.spillover, d.metro_spillover
        theta = self.place_tastes[d.name]
        k = d.capacity_elasticity
        R = self.R
        places = [[] for _ in range(2 * R)]
        for r, res in enumerate(residents):
            for i in res:
                places[2 * r + self.urban[i]].append(i)
        place_pops = [len(x) for x in places]
        burden = [
            (self.national_income / self.regional_income[r]) ** k if k and self.regional_income[r] > 0 else 1.0
            for r in range(R)
        ]
        equalization_spend = 0.0
        if policy.mode == "central":
            p = [_clamp(policy.level, 0, w.max_level)] * (2 * R)
            unit, local_share = 1.0 - d.scale, 0.0
            place_burden = [burden[j // 2] for j in range(2 * R)]
        elif policy.mode == "city":
            local_share = 1.0 - _clamp(policy.level, 0.0, 0.95)
            unit = 1.0
            price = max(local_share, 0.05) * (1 + w.local_overhead)
            # Each place ignores what it gives the other place and neighbouring regions.
            p = [
                _clamp(_median([theta[i] for i in places[j]]) * (1 - s - sm) / (price * burden[j // 2]), 0, w.max_level)
                if places[j] else 0.0
                for j in range(2 * R)
            ]
            place_burden = [burden[j // 2] for j in range(2 * R)]
        else:
            match = policy.level if policy.mode == "matched" else 0.0
            local_share = 1.0 - match
            unit = 1.0
            price = max(local_share, 0.05) * (1 + w.local_overhead)
            eff_burden = burden
            if policy.mode == "equalized" and k:
                q = _clamp(policy.level, 0.0, 1.0)
                topped = [
                    self.regional_income[r] + q * max(0.0, self.national_income - self.regional_income[r])
                    for r in range(R)
                ]
                eff_burden = [(self.national_income / topped[r]) ** k if topped[r] > 0 else 1.0 for r in range(R)]
            # One level per province: it internalises the city-suburb spillover
            # (a uniform level gives each place (1 - s) of its own provision).
            regional = [
                _clamp(_median([theta[i] for i in res]) * (1 - s) / (price * eff_burden[r]), 0, w.max_level)
                if res else 0.0
                for r, res in enumerate(residents)
            ]
            regional = _bound(regional, policy)
            p = [regional[j // 2] for j in range(2 * R)]
            if eff_burden is not burden:
                equalization_spend = sum(
                    place_pops[j] * unit * local_share * (burden[j // 2] - eff_burden[j // 2]) * p[j] ** 2
                    for j in range(2 * R)
                ) / self.N
            place_burden = [eff_burden[j // 2] for j in range(2 * R)]

        regional_level = [
            (p[2 * r] * place_pops[2 * r] + p[2 * r + 1] * place_pops[2 * r + 1]) / pops[r] if pops[r] else 0.0
            for r in range(R)
        ]
        experienced = []
        for j in range(2 * R):
            r, other = j // 2, j ^ 1
            nbr = _mean(regional_level[n] for n in self.nbrs[r])
            experienced.append((1 - s - sm) * p[j] + sm * p[other] + s * nbr)
        national_spend = sum(place_pops[j] * unit * (1 - local_share) * p[j] ** 2 for j in range(2 * R)) / self.N
        national_tax = (national_spend + equalization_spend) * (1 + w.national_overhead)
        local_cost = unit * local_share * (1 + w.local_overhead)
        gain = [d.weight * 2 * experienced[j] for j in range(2 * R)]
        cost = [d.weight * (local_cost * place_burden[j] * p[j] ** 2 + national_tax) for j in range(2 * R)]
        return ("pg2", d.name, theta, gain, cost, regional_level)

    def _redistribution(self, d: Domain, policy: Policy, residents) -> tuple:
        w, eta = self.world, self.world.deadweight
        if policy.mode == "central":
            t = [_clamp(policy.level, 0, w.max_tax)] * self.R
            pool = [self.national_income] * self.R
        else:
            pool = [_mean(self.income(i, r) for i in res) if res else 0.0 for r, res in enumerate(residents)]
            local = []
            for r, res in enumerate(residents):
                if not res or pool[r] <= 0:
                    local.append(0.0)
                    continue
                # Ideal rate of the median earner (Meltzer and Richard 1981, Journal of
                # Political Economy 89: 914-927; empirical support is mixed, e.g. Dao
                # 2001): falls to 0 as the region becomes homogeneous in income.
                median_income = _median([self.income(i, r) for i in res])
                local.append(_clamp((1 - median_income / pool[r]) / (2 * eta), 0, w.max_tax))
            t = _bound(local, policy)
        transfer = [t[r] * pool[r] * (1 - eta * t[r]) for r in range(self.R)]
        keep = [1 - t[r] for r in range(self.R)]
        return ("red", d.name, d.weight, keep, transfer, t)

    # --- agents ---

    def utility(self, i: int, r: int, state: list[tuple], pops: list[int], parts: dict | None = None) -> float:
        avg = self.N / self.R
        u = -self.world.congestion * pops[r] / avg
        if self.private_consumption:
            v = math.log(self.income(i, r))
            u += v
            if parts is not None:
                parts["consumption"] = parts.get("consumption", 0.0) + v
        for entry in state:
            if entry[0] == "pg":
                _, name, theta, gain, cost, _ = entry
                v = gain[r] * theta[i] - cost[r]
            elif entry[0] == "pg2":
                _, name, theta, gain, cost, _ = entry
                j = 2 * r + self.urban[i]
                v = gain[j] * theta[i] - cost[j]
            else:
                _, name, weight, keep, transfer, _ = entry
                c = self.income(i, r) * keep[r] + transfer[r]
                a = self.world.inequality_aversion
                v = weight * (math.log(c) if a == 1.0 else (c ** (1 - a) - 1) / (1 - a))
            u += v
            if parts is not None:
                parts[name] = parts.get(name, 0.0) + v
        if parts is not None:
            parts["congestion"] = parts.get("congestion", 0.0) - self.world.congestion * pops[r] / avg
        return u

    def move(self, state: list[tuple], pops: list[int]) -> int:
        """Let a sample of agents relocate; return how many did."""
        w = self.world
        moved = 0
        movers = self.move_rng.sample(range(self.N), int(w.move_share * self.N))
        k = min(w.candidates, self.R - 1)
        for i in movers:
            here = self.region[i]
            options = [r for r in self.move_rng.sample(range(self.R), k + 1) if r != here][:k]
            best, best_u = here, self.utility(i, here, state, pops) + w.moving_cost
            for r in options:
                pops[r] += 1  # an agent evaluates a region as it would be with them in it
                u = self.utility(i, r, state, pops)
                pops[r] -= 1
                if u > best_u:
                    best, best_u = r, u
            if best != here:
                pops[here] -= 1
                pops[best] += 1
                self.region[i] = best
                moved += 1
        return moved

    def measure(self, state: list[tuple], pops: list[int], residents) -> Outcome:
        parts: dict[str, float] = {}
        total = sum(self.utility(i, self.region[i], state, pops, parts) for i in range(self.N))
        out = Outcome(welfare=total / self.N, components={k: v / self.N for k, v in parts.items()})
        populated = [r for r in range(self.R) if pops[r]]
        for entry in state:
            levels = entry[-1]
            out.policy_mean[entry[1]] = sum(levels[r] * pops[r] for r in range(self.R)) / self.N
            out.policy_sd[entry[1]] = _sd(levels[r] for r in populated)
        regional_income = [_mean(self.income(i, r) for i in residents[r]) for r in populated]
        out.income_sorting = _sd(regional_income) / self.national_income
        out.crowding = max(pops) / (self.N / self.R)
        return out

    def run(self) -> Outcome:
        w = self.world
        samples = []
        for step in range(w.steps):
            residents = [[] for _ in range(self.R)]
            for i, r in enumerate(self.region):
                residents[r].append(i)
            pops = [len(res) for res in residents]
            state = self.region_state(residents)
            measuring = step >= w.steps - w.measure_steps
            if measuring:
                samples.append(self.measure(state, pops, residents))
            if w.move_share > 0:
                moved = self.move(state, pops)
                if measuring:
                    samples[-1].migration = moved / self.N
        return _average(samples)


def _average(samples: list[Outcome]) -> Outcome:
    n = len(samples)
    out = Outcome(
        welfare=sum(s.welfare for s in samples) / n,
        income_sorting=sum(s.income_sorting for s in samples) / n,
        crowding=sum(s.crowding for s in samples) / n,
        migration=sum(s.migration for s in samples) / n,
    )
    for attr in ("components", "policy_mean", "policy_sd"):
        keys = getattr(samples[0], attr).keys()
        setattr(out, attr, {k: sum(getattr(s, attr)[k] for s in samples) / n for k in keys})
    return out


def simulate(world: World, arrangement: dict[str, Policy], seed: int = 0) -> Outcome:
    unknown = set(arrangement) - {d.name for d in world.domains}
    if unknown:
        raise KeyError(f"arrangement names unknown domains: {', '.join(sorted(unknown))}")
    return _Run(world, arrangement, seed).run()
