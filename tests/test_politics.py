import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "validation"))
import political_realities as pr  # noqa: E402
from politics import amending, support  # noqa: E402
from tiebout.model import Policy  # noqa: E402

SHARES = [0.1] * 10
ATT = [0.0] * 10
X = {"loss_aversion": 2.0, "rebate_seen": 0.0, "abated": 0.2, "identity_scale": 0.0,
     "crisis_chance": 0.0, "crisis_cut": 0.3}


def case(*rules):
    return {"base": [0.0] * 10, "rules": [{"u": list(u), "pay": list(p), "crisis": list(c)} for u, p, c in rules]}


class PoliticalRealities(unittest.TestCase):
    def test_votes(self):
        self.assertAlmostEqual(support([1, -1, 1], [0.5, 0.2, 0.3]), 0.8)
        self.assertTrue(amending([1] * 7 + [-1] * 3, SHARES))
        self.assertFalse(amending([1] * 6 + [-1] * 4, SHARES))

    def test_crisis_cuts_only_federal_money(self):
        self.assertIsNone(pr.crisis_policy(Policy("floor", 0.5), 0.3))
        self.assertIsNone(pr.crisis_policy(Policy("price", 1.0), 0.3))
        self.assertAlmostEqual(pr.crisis_policy(Policy("matched", 0.5), 0.2).level, 0.4)
        self.assertAlmostEqual(pr.crisis_policy(Policy("foundation", 0.5), 0.36).level, 0.4)

    def test_loss_aversion_blocks_a_narrow_net_gain(self):
        # Six provinces gain 1, four lose 1.2: a net gain, and a majority of people gain.
        u = [1.0] * 6 + [-1.2] * 4
        c = case(([0] * 10, [0] * 10, [0] * 10), (u, [0] * 10, u))
        modes = ["local", "matched"]
        labels = ["local", "matched 50%"]
        self.assertEqual(pr.decide(c, labels, modes, 0, "schools", X, SHARES, ATT, off=("loss_aversion",))[0], "matched 50%")
        self.assertEqual(pr.decide(c, labels, modes, 0, "schools", X, SHARES, ATT)[0], "keep today's arrangement")
        # Loss aversion doesn't change who gains, so the Commons vote still passes...
        ok, amend, *_ = pr.judge(c, 1, 0, modes, "schools", X, SHARES, ATT)
        self.assertTrue(ok and not amend)
        # ...but the perceived national gain turns negative, so Ottawa doesn't bother.
        _, v = pr.perceived(c, 1, 0, modes, X, 0.0, SHARES, ATT)
        self.assertLess(sum(w * y for w, y in zip(SHARES, v)), 0)

    def test_mandate_in_provincial_field_needs_amendment(self):
        u = [1.0] * 6 + [-0.1] * 4   # six provinces gain: a Commons majority, not seven provinces
        c = case(([0] * 10, [0] * 10, [0] * 10), (u, [0] * 10, u))
        ok, amend, *_ = pr.judge(c, 1, 0, ["local", "central"], "schools", X, SHARES, ATT)
        self.assertTrue(amend)
        self.assertFalse(ok)
        ok, amend, *_ = pr.judge(c, 1, 0, ["local", "central"], "schools", X, SHARES, ATT, off=("constitution",))
        self.assertTrue(ok)

    def test_unseen_rebate_and_repeal(self):
        # Real gain 0.2 everywhere, visible payment 0.5: passes only if most of the rebate is seen.
        c = case(([0] * 10, [0] * 10, [0] * 10), ([0.2] * 10, [0.5] * 10, [0.2] * 10))
        modes = ["local", "price_floor"]
        ok, *_ = pr.judge(c, 1, 0, modes, "climate", X, SHARES, ATT)
        self.assertFalse(ok)
        ok, _, survive, *_ = pr.judge(c, 1, 0, modes, "climate", X, SHARES, ATT, off=("visible_payments",))
        self.assertTrue(ok)
        self.assertEqual(survive, 1.0)

    def test_attachment_counts_against_central_rules(self):
        att = [1.0] * 10
        c = case(([0] * 10, [0] * 10, [0] * 10), ([0.1] * 10, [0] * 10, [0.1] * 10))
        x = {**X, "identity_scale": 1.0}
        _, v = pr.perceived(c, 1, 0, ["local", "central"], x, 0.0, SHARES, att)
        self.assertTrue(all(y < 0 for y in v))
        _, v = pr.perceived(c, 1, 0, ["local", "central"], x, 0.0, SHARES, att, off=("attachment",))
        self.assertTrue(all(y > 0 for y in v))


if __name__ == "__main__":
    unittest.main()
