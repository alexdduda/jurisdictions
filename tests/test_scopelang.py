import unittest

from scopelang import ParseError, run


def kinds(result):
    return [d.kind for d in result.diagnostics]


class Shadowing(unittest.TestCase):
    def test_nearest_value_wins_without_a_law(self):
        r = run("x = 1  scope a { x = 2  scope b { } }")
        self.assertEqual(r.value("b", "x"), 2)
        self.assertEqual(r.value("root", "x"), 1)
        self.assertEqual(r.diagnostics, [])

    def test_undefined_is_an_error_not_a_crash(self):
        r = run("scope a { show missing }")
        self.assertEqual(kinds(r), ["error"])


class Preempt(unittest.TestCase):
    def test_lower_write_is_struck_down_and_not_applied(self):
        r = run("scope fed { law age: preempt = 18  scope prov { age = 21 } }")
        self.assertEqual(kinds(r), ["struck_down"])
        self.assertEqual(r.value("prov", "age"), 18)

    def test_declaring_scope_can_change_its_own_law(self):
        r = run("scope fed { law age: preempt = 18  age = 19 }")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.value("fed", "age"), 19)

    def test_cannot_weaken_by_redeclaring_lower_down(self):
        r = run("scope fed { law age: preempt = 18  scope prov { law age: shadow = 16 } }")
        self.assertEqual(kinds(r), ["struck_down"])


class FloorAndCeiling(unittest.TestCase):
    def test_floor_allows_raising_and_blocks_lowering(self):
        r = run("""
            scope ca { law wage: floor = 15
              scope qc { wage = 16  scope mtl { wage = 15.5 } }
              scope ab { wage = 15 }
            }""")
        self.assertEqual(kinds(r), ["struck_down"])  # mtl is below qc's 16
        self.assertEqual(r.value("mtl", "wage"), 16)
        self.assertEqual(r.value("ab", "wage"), 15)

    def test_ceiling(self):
        r = run("scope ca { law rent_increase: ceiling = 3  scope qc { rent_increase = 5 } }")
        self.assertEqual(kinds(r), ["struck_down"])

    def test_raising_floor_later_invalidates_lower_values(self):
        r = run("scope ca { law wage: floor = 15  scope qc { wage = 16 }  wage = 17 }")
        self.assertEqual(kinds(r), ["now_invalid"])

    def test_compound_assignment_is_checked(self):
        r = run("scope ca { law wage: floor = 15  scope qc { wage = 16  wage -= 2 } }")
        self.assertEqual(kinds(r), ["struck_down"])
        self.assertEqual(r.value("qc", "wage"), 16)

    def test_lower_level_may_add_its_own_floor_under_a_shadow_law(self):
        r = run("""
            scope ca { law tax: shadow = 5
              scope qc { law tax: floor = 9  scope mtl { tax = 8 } }
            }""")
        self.assertEqual(kinds(r), ["struck_down"])


class Matched(unittest.TestCase):
    def test_match_rate_is_not_an_inherited_level(self):
        r = run("scope ca { law env: matched = 0.6  scope qc { env = 0.2 } scope on { } }")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.laws("ca"), {"env": ("matched", 0.6)})
        self.assertEqual(r.value("qc", "env"), 0.2)
        self.assertEqual(kinds(run("scope ca { law env: matched = 0.6  scope on { show env } }")), ["error"])

    def test_equalized_carries_a_rate(self):
        r = run("scope ca { law schools: equalized = 0.5  scope qc { schools = 0.3 } }")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.laws("ca"), {"schools": ("equalized", 0.5)})

    def test_rate_must_be_a_share(self):
        self.assertEqual(kinds(run("law env: matched = 2")), ["error"])


class MultipleParents(unittest.TestCase):
    SRC = """
        scope qc { law fare: shadow = 3.75  scope cmm { fare = 3.5 } }
        scope mtl in qc, cmm { }
    """

    def test_conflicting_parents_is_a_dispute(self):
        r = run(self.SRC + "scope mtl in qc, cmm { show fare }")
        self.assertEqual(kinds(r), ["dispute"])

    def test_defer_settles_it(self):
        r = run(self.SRC + "scope mtl in qc, cmm { defer fare to cmm }")
        self.assertEqual(r.value("mtl", "fare"), 3.5)

    def test_defer_does_not_escape_the_other_parents_rules(self):
        r = run("""
            scope qc { law wage: floor = 16  scope cmm { } }
            scope mtl in qc, cmm { defer wage to cmm  wage = 15 }
        """)
        self.assertEqual(kinds(r), ["struck_down"])

    def test_can_only_defer_to_a_parent(self):
        r = run(self.SRC + "scope other { }  scope mtl in qc, cmm { defer fare to other }")
        self.assertEqual(kinds(r), ["error"])


class Commons(unittest.TestCase):
    def test_writes_are_tracked_as_externalities(self):
        r = run("""
            scope qc { shared river = 10
              scope mtl { river += 4 }
              scope tr  { show river }
              scope qcc { }
            }""")
        self.assertEqual(r.value("qc", "river"), 14)
        report = "\n".join(r.interp.externalities())
        self.assertIn("changed by mtl (+4", report)
        self.assertIn("tr", report)
        self.assertIn("read (and so affected) by: tr", report)

    def test_shared_cannot_become_a_law(self):
        self.assertEqual(kinds(run("shared river = 1  law river: floor = 2")), ["error"])


class Scopes(unittest.TestCase):
    def test_reopening_a_scope(self):
        r = run("scope ca { scope qc { x = 1 } }  scope ca { scope qc { y = 2 } }")
        self.assertEqual(r.diagnostics, [])
        self.assertEqual(r.value("qc", "x"), 1)

    def test_same_name_elsewhere_is_rejected(self):
        r = run("scope ca { scope qc { } }  scope qc { }")
        self.assertEqual(kinds(r), ["error"])

    def test_if_and_expressions(self):
        r = run("x = 3  if x * 2 >= 6 and not false { y = max(x, 10) - 1 } else { y = 0 }")
        self.assertEqual(r.value("root", "y"), 9)

    def test_tree_renders(self):
        r = run("scope ca { law w: floor = 15  scope qc { w = 16 } }")
        tree = "\n".join(r.interp.tree())
        self.assertIn("law w: floor = 15", tree)
        self.assertIn("└── qc", tree)


class Syntax(unittest.TestCase):
    def test_unknown_mode(self):
        with self.assertRaises(ParseError):
            run("law x: sometimes = 1")

    def test_unclosed_block(self):
        with self.assertRaises(ParseError):
            run("scope a { x = 1")


if __name__ == "__main__":
    unittest.main()
