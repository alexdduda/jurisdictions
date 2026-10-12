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

MODES = ("local", "central", "floor", "ceiling", "matched")


@dataclass(frozen=True)
class Domain:
    name: str
    kind: str = "public_good"   # or "redistribution"
    heterogeneity: float = 0.1  # sd of regional taste centres
    within: float = 0.1         # sd of tastes inside a region
    spillover: float = 0.0      # share of provision felt by neighbours
    scale: float = 0.0          # unit-cost saving under central provision
    weight: float = 1.0


@dataclass(frozen=True)
class Policy:
    mode: str = "local"
    level: float = 0.0  # central level, floor, ceiling, or match rate

    def __post_init__(self):
        if self.mode not in MODES:
            raise ValueError(f"unknown mode {self.mode!r}")

    def label(self) -> str:
        if self.mode == "local":
            return "local"
        if self.mode == "matched":
            return f"matched {self.level:.0%}"
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
    income_sorting: float = 0.0    # sd of regional mean income / national mean
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
        self.income = [math.exp(rng.gauss(0, world.income_sigma)) for _ in range(self.N)]
        self.tastes: dict[str, list[float]] = {}
        for d in world.domains:
            if d.kind == "public_good":
                centres = [_clamp(0.5 + rng.gauss(0, d.heterogeneity), 0, 1) for _ in range(self.R)]
                self.tastes[d.name] = [
                    _clamp(centres[self.region[i]] + rng.gauss(0, d.within), 0, 1)
                    for i in range(self.N)
                ]
        self.national_income = _mean(self.income)

    # --- government ---

    def region_state(self, residents: list[list[int]]) -> list[tuple]:
        """Per-domain, per-region quantities agents need to evaluate a region."""
        w = self.world
        pops = [len(res) for res in residents]
        state = []
        for d in w.domains:
            policy = self.arrangement.get(d.name, LOCAL)
            if d.kind == "public_good":
                state.append(self._public_good(d, policy, residents, pops))
            elif d.kind == "redistribution":
                state.append(self._redistribution(d, policy, residents))
            else:
                raise ValueError(f"unknown domain kind {d.kind!r}")
        return state

    def _public_good(self, d: Domain, policy: Policy, residents, pops) -> tuple:
        w, s = self.world, d.spillover
        theta = self.tastes[d.name]
        if policy.mode == "central":
            p = [_clamp(policy.level, 0, w.max_level)] * self.R
            unit, local_share = 1.0 - d.scale, 0.0
        else:
            match = policy.level if policy.mode == "matched" else 0.0
            local_share = 1.0 - match
            unit = 1.0
            price = max(local_share, 0.05) * (1 + w.local_overhead)
            local = [
                _clamp(_median([theta[i] for i in res]) * (1 - s) / price, 0, w.max_level) if res else 0.0
                for res in residents
            ]
            p = _bound(local, policy)

        experienced = [
            (1 - s) * p[r] + s * _mean(p[n] for n in self.nbrs[r]) for r in range(self.R)
        ]
        national_spend = sum(pops[r] * unit * (1 - local_share) * p[r] ** 2 for r in range(self.R)) / self.N
        national_tax = national_spend * (1 + w.national_overhead)
        gain = [d.weight * 2 * experienced[r] for r in range(self.R)]
        local_cost = unit * local_share * (1 + w.local_overhead)
        cost = [d.weight * (local_cost * p[r] ** 2 + national_tax) for r in range(self.R)]
        return ("pg", d.name, theta, gain, cost, p)

    def _redistribution(self, d: Domain, policy: Policy, residents) -> tuple:
        w, eta = self.world, self.world.deadweight
        if policy.mode == "central":
            t = [_clamp(policy.level, 0, w.max_tax)] * self.R
            pool = [self.national_income] * self.R
        else:
            pool = [_mean(self.income[i] for i in res) for res in residents]
            local = []
            for r, res in enumerate(residents):
                if not res or pool[r] <= 0:
                    local.append(0.0)
                    continue
                # Ideal rate of the median earner (Meltzer-Richard): falls to 0 as
                # the region becomes homogeneous in income.
                median_income = _median([self.income[i] for i in res])
                local.append(_clamp((1 - median_income / pool[r]) / (2 * eta), 0, w.max_tax))
            t = _bound(local, policy)
        transfer = [t[r] * pool[r] * (1 - eta * t[r]) for r in range(self.R)]
        keep = [1 - t[r] for r in range(self.R)]
        return ("red", d.name, d.weight, keep, transfer, t)

    # --- agents ---

    def utility(self, i: int, r: int, state: list[tuple], pops: list[int], parts: dict | None = None) -> float:
        avg = self.N / self.R
        u = -self.world.congestion * pops[r] / avg
        for entry in state:
            if entry[0] == "pg":
                _, name, theta, gain, cost, _ = entry
                v = gain[r] * theta[i] - cost[r]
            else:
                _, name, weight, keep, transfer, _ = entry
                v = weight * math.log(self.income[i] * keep[r] + transfer[r])
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
        regional_income = [_mean(self.income[i] for i in residents[r]) for r in populated]
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
