import unittest
from dataclasses import replace

from tiebout.bridge import jur_to_arrangement
from tiebout.config import DEFAULT_WORLD
from tiebout.model import Domain, Policy, World, simulate, torus_neighbors

SMALL = dict(grid=3, agents_per_region=30, steps=6, measure_steps=2)


def world(*domains, **changes):
    return World(domains=tuple(domains), **{**SMALL, **changes})


class Mechanics(unittest.TestCase):
    def test_deterministic_for_a_seed(self):
        w = replace(DEFAULT_WORLD, **SMALL)
        self.assertEqual(simulate(w, {}, 3).welfare, simulate(w, {}, 3).welfare)

    def test_torus_has_four_neighbours(self):
        self.assertTrue(all(len(n) == 4 for n in torus_neighbors(4)))

    def test_unknown_domain_rejected(self):
        with self.assertRaises(KeyError):
            simulate(world(Domain("a")), {"b": Policy("central", 0.5)})

    def test_population_is_conserved(self):
        w = world(Domain("a", heterogeneity=0.3), move_share=0.5)
        o = simulate(w, {}, 1)
        self.assertGreaterEqual(o.crowding, 1.0)


class Economics(unittest.TestCase):
    """The model should reproduce the textbook results it is built on."""

    def test_spillovers_cause_local_underprovision(self):
        s = 0.6
        w = world(Domain("env", heterogeneity=0.0, within=0.0, spillover=s), move_share=0.0)
        o = simulate(w, {}, 0)
        self.assertAlmostEqual(o.policy_mean["env"], 0.5 * (1 - s), places=6)

    def test_matching_at_the_spillover_rate_restores_the_optimum(self):
        s = 0.6
        w = world(Domain("env", heterogeneity=0.0, within=0.0, spillover=s), move_share=0.0, national_overhead=0.0)
        o = simulate(w, {"env": Policy("matched", s)}, 0)
        self.assertAlmostEqual(o.policy_mean["env"], 0.5, places=6)
        self.assertGreater(o.welfare, simulate(w, {}, 0).welfare)

    def test_uniform_policy_costs_fit_when_regions_differ(self):
        w = world(Domain("schools", heterogeneity=0.3, within=0.0), move_share=0.0)
        self.assertGreater(simulate(w, {}, 0).welfare, simulate(w, {"schools": Policy("central", 0.5)}, 0).welfare)

    def test_scale_economies_favour_the_centre_when_tastes_agree(self):
        w = world(Domain("transit", heterogeneity=0.0, within=0.05, scale=0.4), move_share=0.0)
        self.assertGreater(simulate(w, {"transit": Policy("central", 0.8)}, 0).welfare, simulate(w, {}, 0).welfare)

    def test_mobility_sorts_people_by_income_under_local_redistribution(self):
        red = Domain("redistribution", kind="redistribution")
        still = simulate(world(red, move_share=0.0, steps=12), {}, 0)
        mobile = simulate(world(red, move_share=0.5, steps=12), {}, 0)
        self.assertGreater(mobile.income_sorting, still.income_sorting)

    def test_floor_is_binding(self):
        w = world(Domain("env", spillover=0.6), move_share=0.0)
        o = simulate(w, {"env": Policy("floor", 0.45)}, 0)
        self.assertGreaterEqual(o.policy_mean["env"], 0.45 - 1e-9)


class Bridge(unittest.TestCase):
    def test_reads_laws_from_scopelang(self):
        src = """
            scope nation {
              law schools: shadow
              law environment: floor = 0.5
              law transit: preempt = 0.6
              law redistribution: matched = 0.2
            }"""
        arr, warnings = jur_to_arrangement(src, DEFAULT_WORLD)
        self.assertEqual(warnings, [])
        self.assertEqual(arr["schools"], Policy())
        self.assertEqual(arr["environment"], Policy("floor", 0.5))
        self.assertEqual(arr["transit"], Policy("central", 0.6))
        self.assertEqual(arr["redistribution"], Policy("matched", 0.2))

    def test_unknown_law_is_a_warning(self):
        _, warnings = jur_to_arrangement("scope nation { law defence: preempt = 1 }", DEFAULT_WORLD)
        self.assertTrue(any("defence" in w for w in warnings))

    def test_preempt_needs_a_level(self):
        with self.assertRaises(ValueError):
            jur_to_arrangement("scope nation { law transit: preempt }", DEFAULT_WORLD)


class RegionalProductivity(unittest.TestCase):
    """Validation tests 2 and 3 found Canadians move for income and richer provinces spend more."""

    def _run(self, world, arrangement=None, seed=0):
        from tiebout.model import _Run
        run = _Run(world, arrangement or {}, seed)
        run.run()
        return run

    def test_off_by_default(self):
        w = world(Domain("a"))
        self.assertEqual(w.productivity_sd, 0.0)
        self.assertEqual(Domain("a").capacity_elasticity, 0.0)

    def test_richer_regions_provide_more_when_capacity_matters(self):
        w = world(Domain("a", heterogeneity=0.0, within=0.0, capacity_elasticity=1.0),
                  productivity_sd=0.3, move_share=0.0)
        from tiebout.model import _Run
        run = _Run(w, {}, 0)
        residents = [[i for i, r in enumerate(run.region) if r == k] for k in range(run.R)]
        p = run.region_state(residents)[0][-1]
        rich = max(range(run.R), key=lambda r: run.regional_income[r])
        poor = min(range(run.R), key=lambda r: run.regional_income[r])
        self.assertGreater(p[rich], p[poor])

    def test_without_capacity_income_does_not_change_provision(self):
        w = world(Domain("a", heterogeneity=0.0, within=0.0), productivity_sd=0.3, move_share=0.0)
        from tiebout.model import _Run
        run = _Run(w, {}, 0)
        residents = [[i for i, r in enumerate(run.region) if r == k] for k in range(run.R)]
        p = run.region_state(residents)[0][-1]
        self.assertAlmostEqual(max(p), min(p))

    def test_people_move_toward_productive_regions(self):
        w = world(Domain("a", heterogeneity=0.0), productivity_sd=0.3, move_share=0.5, moving_cost=0.0, steps=12)
        run = self._run(w)
        pops = [run.region.count(r) for r in range(run.R)]
        best = max(range(run.R), key=lambda r: run.productivity[r])
        worst = min(range(run.R), key=lambda r: run.productivity[r])
        self.assertGreater(pops[best], pops[worst])


if __name__ == "__main__":
    unittest.main()
