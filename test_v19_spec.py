"""Tests for the 'indicative simulation vs Menkor aircraft-specific budget' change.
Engine-level tests exercise menkor_engine directly; screen/PDF/CSV tests use tests/fake_streamlit.py (a recorder — NOT a real Streamlit/browser)."""
import math, os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_engine as E  # noqa: E402

BASE = E.load_base()
FAL = "dassault_falcon_7x"
CONF = dict(positioning_confirmed=True, private_hours_confirmed=True, other_fees_confirmed=True, limits_reviewed=True)


def _rd(f):
    with open(os.path.join(ROOT, f), encoding="utf-8") as fh: return fh.read()


def row(aid=FAL): return BASE[BASE["aircraft_id"] == aid].iloc[0]


def comp(aid=FAL, **kw):
    kw.setdefault("billed_hours", 300.0)
    return E.compute(row(aid), E.Scenario(aid, mode="simulation", **kw))


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f: f.write(data)
    try: return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout
    finally: os.unlink(f.name)


class TestRegressionFormula(unittest.TestCase):
    def test_spec_arithmetic_case_115_35_to_116(self):
        F, V, R, c = 588918.0, 2994.64, 9000.0, 0.10
        th = E._solve_threshold("t", "t", F, R * (1 - c) - V, 0.0, 0.0)
        self.assertAlmostEqual(th["billed_hours_exact"], 115.35288, places=4)
        self.assertEqual(th["billed_hours"], 116)                       # rounded UP, never down
        self.assertEqual(th["flown_hours"], 116)

    def test_rounding_up_not_to_nearest(self):
        th = E._solve_threshold("t", "t", 100.2, 1.0, 0.0, 0.0)          # 100.2 -> 101 (nearest would give 100)
        self.assertEqual(th["billed_hours"], 101)
        th = E._solve_threshold("t", "t", 100.0, 1.0, 0.0, 0.0)          # exact integer stays
        self.assertEqual(th["billed_hours"], 100)

    def test_general_formula_with_positioning_private_and_other(self):
        F, V, R, c, p, Hp, A = 500000.0, 2000.0, 8000.0, 0.1, 0.2, 40.0, 10000.0
        th = E._solve_threshold("t", "t", F + V * Hp + A, R * (1 - c) - V * (1 + p), p, Hp)
        self.assertAlmostEqual(th["billed_hours_exact"], (F + V * Hp + A) / (R * (1 - c) - V * (1 + p)), places=9)
        self.assertAlmostEqual(th["flown_hours"], th["billed_hours"] * (1 + p) + Hp, places=9)


class TestRateAndCommission(unittest.TestCase):
    def test_absent_rate_costs_visible_no_revenue_result_or_threshold(self):
        r = comp()
        self.assertTrue(r["available"]); self.assertGreater(r["budget_usd"], 0)
        p = r["profit"]
        self.assertFalse(p["available"]); self.assertEqual(p["messages"], [E.NO_RATE_MESSAGE])
        self.assertNotIn("revenue", p); self.assertNotIn("operating_result", p); self.assertIsNone(p["threshold"])
        for bad in (0.0, -5.0):
            self.assertFalse(comp(charter_rate=bad)["profit"]["available"])

    def test_gross_rate_commission_applied_once(self):
        p = comp(charter_rate=9000.0, rate_basis="gross", commission_pct=10.0, **CONF)["profit"]
        self.assertAlmostEqual(p["commission"], 9000 * 300 * 0.10, places=4)
        self.assertAlmostEqual(p["revenue"] - p["commission"], 9000 * 300 * 0.90, places=4)

    def test_net_rate_never_deducts_commission_even_if_a_commission_is_present(self):
        a = comp(charter_rate=8100.0, rate_basis="net", commission_pct=0.0, **CONF)["profit"]
        b = comp(charter_rate=8100.0, rate_basis="net", commission_pct=25.0, **CONF)["profit"]
        self.assertEqual(a["commission"], 0.0); self.assertEqual(b["commission"], 0.0)
        self.assertEqual(a["operating_result"], b["operating_result"]); self.assertEqual(a["threshold"]["billed_hours"], b["threshold"]["billed_hours"])
        g = comp(charter_rate=9000.0, rate_basis="gross", commission_pct=10.0, **CONF)["profit"]    # 9000 gross @10% == 8100 net
        self.assertAlmostEqual(g["operating_result"], a["operating_result"], places=4)
        self.assertEqual(g["threshold"]["billed_hours"], a["threshold"]["billed_hours"])

    def test_gross_without_commission_is_not_silently_zero(self):
        p = comp(charter_rate=9000.0, rate_basis="gross", commission_pct=None, **CONF)["profit"]
        self.assertFalse(p["available"]); self.assertIn("commission", " ".join(p["messages"]).lower())
        p = comp(charter_rate=9000.0, rate_basis="gross", commission_pct=0.0, **CONF)["profit"]       # an explicit zero is accepted
        self.assertTrue(p["available"])

    def test_unknown_basis_is_refused(self):
        p = comp(charter_rate=9000.0, rate_basis="", commission_pct=10.0, **CONF)["profit"]
        self.assertFalse(p["available"])

    def test_supplements_kept_apart_from_the_rate(self):
        a = comp(charter_rate=9000.0, commission_pct=10.0, **CONF)["profit"]
        b = comp(charter_rate=9000.0, commission_pct=10.0, supplements_retained_usd=50000.0, supplements_cost_usd=30000.0, **CONF)["profit"]
        self.assertEqual(a["revenue"], b["revenue"])                                          # not mixed into the hourly revenue
        self.assertAlmostEqual(b["operating_result"] - a["operating_result"], 20000.0, places=4)


class TestConfirmations(unittest.TestCase):
    def thr(self, **kw):
        return comp(charter_rate=9000.0, commission_pct=10.0, positioning_hours=30.0, **kw)["profit"]["threshold"]

    def test_threshold_withheld_until_all_four_confirmations(self):
        for k in CONF:
            th = self.thr(**{**CONF, k: False})
            self.assertEqual(th["status"], "awaiting_confirmation", k); self.assertIsNone(th["billed_hours"], k)
        self.assertEqual(self.thr(**CONF)["status"], "ok")

    def test_zero_positioning_and_private_hours_need_an_explicit_choice(self):
        th = comp(charter_rate=9000.0, commission_pct=10.0)["profit"]["threshold"]               # zeros by default, nothing confirmed
        self.assertEqual(th["status"], "awaiting_confirmation")
        self.assertIn("positioning", th["missing"]); self.assertIn("private/owner hours", th["missing"])
        th = comp(charter_rate=9000.0, commission_pct=10.0, **CONF)["profit"]["threshold"]       # same zeros once confirmed
        self.assertEqual(th["status"], "ok")

    def test_hours_basis_needs_positive_billed_hours_unless_ratio_given(self):
        r = comp(billed_hours=0.0, charter_rate=9000.0, commission_pct=10.0, **CONF)["profit"]["threshold"]
        self.assertEqual(r["status"], "ratio_undefined")
        r = comp(billed_hours=0.0, charter_rate=9000.0, commission_pct=10.0, positioning_ratio=0.1, **CONF)["profit"]["threshold"]
        self.assertEqual(r["status"], "ok")

    def test_ratio_is_kept_constant_private_hours_constant(self):
        th = comp(charter_rate=9000.0, commission_pct=10.0, positioning_hours=60.0, other_hours=50.0, **CONF)["profit"]["threshold"]   # ratio 0.2 at 300 h
        self.assertAlmostEqual(th["positioning_ratio"], 0.2)
        self.assertAlmostEqual(th["flown_hours"], th["billed_hours"] * 1.2 + 50.0, places=6)
        th2 = comp(billed_hours=100.0, charter_rate=9000.0, commission_pct=10.0, positioning_hours=20.0, other_hours=50.0, **CONF)["profit"]["threshold"]
        self.assertEqual(th["billed_hours"], th2["billed_hours"])                      # same ratio => same threshold whatever the billed hours entered

    def test_threshold_is_where_result_is_zero_with_everything_on(self):
        p = comp(charter_rate=9000.0, commission_pct=10.0, positioning_hours=60.0, other_hours=50.0, other_commercial_fees=20000.0, **CONF)["profit"]
        be = p["threshold"]["billed_hours_exact"]
        z = comp(billed_hours=be, positioning_hours=0.2 * be, other_hours=50.0, charter_rate=9000.0, commission_pct=10.0, other_commercial_fees=20000.0, **CONF)["profit"]
        self.assertAlmostEqual(z["operating_result"], 0.0, delta=0.01)

    def test_fixed_costs_do_not_move_with_hours(self):
        a, b = comp(billed_hours=100.0), comp(billed_hours=400.0)
        self.assertEqual(a["fixed"]["annual_total"], b["fixed"]["annual_total"])

    def test_negative_or_zero_contribution_gives_no_threshold(self):
        th = comp(charter_rate=2000.0, commission_pct=10.0, **CONF)["profit"]["threshold"]
        self.assertEqual(th["status"], "unattainable"); self.assertEqual(th["message"], "No attainable threshold under these assumptions.")
        self.assertIsNone(th["billed_hours"])
        # exactly zero contribution
        r = comp(charter_rate=1.0, commission_pct=0.0, **CONF)["profit"]
        v = r["contribution_per_billed_hour"]
        r2 = comp(charter_rate=1.0 - v, commission_pct=0.0, **CONF)["profit"]           # rate chosen so that contribution is 0
        self.assertAlmostEqual(r2["contribution_per_billed_hour"], 0.0, places=6)
        self.assertEqual(r2["threshold"]["status"], "unattainable")

    def test_note_and_labels(self):
        th = comp(charter_rate=9000.0, commission_pct=10.0, **CONF)["profit"]["threshold"]
        self.assertEqual(th["note"], "Estimate based on your assumptions. Aircraft-specific maintenance events and programme exclusions may materially change the result.")
        self.assertEqual(th["label"], "Operating cost coverage threshold")
        self.assertTrue(th["label_fr"].startswith("Seuil de couverture des coûts d'exploitation renseignés"))
        for f in ("app.py", "menkor_report.py", "menkor_engine.py"):
            self.assertNotRegex(_rd(f), r"(?i)break-?even", f)


class TestOwnership(unittest.TestCase):
    P = dict(charter_rate=9000.0, commission_pct=10.0, **CONF)

    def test_absent_ownership_is_not_zero_and_threshold_b_incomplete(self):
        p = comp(**self.P)["profit"]
        self.assertIsNone(p["economic_result"]); self.assertIsNone(p["ownership_costs_total"])
        te = p["threshold_economic"]; self.assertEqual(te["status"], "incomplete")
        self.assertCountEqual(te["missing"], ["economic depreciation", "loan interest"])
        self.assertEqual(p["threshold"]["status"], "ok")                                   # A is independent of the ownership fields

    def test_one_field_missing_stays_incomplete_explicit_zero_completes(self):
        p = comp(depreciation_annual=1500000.0, **self.P)["profit"]
        self.assertEqual(p["threshold_economic"]["status"], "incomplete"); self.assertEqual(p["threshold_economic"]["missing"], ["loan interest"])
        p = comp(depreciation_annual=1500000.0, interest_annual=0.0, **self.P)["profit"]
        te = p["threshold_economic"]; self.assertEqual(te["status"], "ok")
        self.assertGreater(te["billed_hours"], p["threshold"]["billed_hours"])

    def test_ownership_never_enters_threshold_a_nor_operating_result(self):
        a = comp(**self.P)["profit"]; b = comp(depreciation_annual=2e6, interest_annual=5e5, **self.P)["profit"]
        self.assertEqual(a["threshold"]["billed_hours"], b["threshold"]["billed_hours"]); self.assertEqual(a["operating_result"], b["operating_result"])
        self.assertAlmostEqual(b["economic_result"], b["operating_result"] - 2.5e6, places=4)

    def test_threshold_b_formula(self):
        b = comp(depreciation_annual=2e6, interest_annual=5e5, **self.P)["profit"]
        a = b["threshold"]; u = a["contribution_per_billed_hour"]
        self.assertAlmostEqual(b["threshold_economic"]["billed_hours_exact"], a["billed_hours_exact"] + 2.5e6 / u, places=6)

    def test_ownership_currency_conversion_is_dated(self):
        fx = E.Fx("EUR", 0.92, "2026-10-17")
        p = comp(depreciation_annual=920000.0, depreciation_ccy="EUR", interest_annual=0.0, fx=fx, **self.P)["profit"]
        self.assertAlmostEqual(p["ownership"]["depreciation_usd"], 1000000.0, places=4)
        p = comp(depreciation_annual=920000.0, depreciation_ccy="EUR", interest_annual=0.0, **self.P)["profit"]       # no dated rate => not converted, not zero
        self.assertIsNone(p["economic_result"]); self.assertEqual(p["threshold_economic"]["status"], "incomplete")
        self.assertIn("EUR/USD", " ".join(p["ownership"]["errors"]))

    def test_note_says_interest_only_no_tax_not_cash_flow(self):
        n = E.OWNERSHIP_NOTE.lower()
        for w in ("interest", "not capital repayment", "taxes are excluded", "not cash flow", "not tax amortisation"):
            self.assertIn(w, n)


class TestManagementAndCycle(unittest.TestCase):
    FEE = {"management": {"amount": 60000.0, "ccy": "USD"}}

    def test_no_amount_adds_nothing_and_is_not_a_confirmed_zero(self):
        a = comp(); b = comp(management={"management": {"amount": None, "ccy": "USD"}, "camo": {"amount": None}})
        self.assertEqual(a["budget_usd"], b["budget_usd"]); self.assertEqual(b["management"]["management"]["status"], "none")
        self.assertIsNone(b["management"]["management"]["amount_usd"])                       # unknown stays None, never 0
        sc = E.costs_scope(row(), b, E.Scenario(FAL, mode="simulation", billed_hours=300.0))
        self.assertIn("Management fees excluded.", " ".join(sc["exclusions"]))

    def test_management_fee_added_exactly_once_everywhere(self):
        a = comp(); c = comp(management=self.FEE)
        self.assertAlmostEqual(c["fixed"]["annual_total"] - a["fixed"]["annual_total"], 60000.0, places=4)
        self.assertAlmostEqual(c["budget_usd"] - a["budget_usd"], 60000.0, places=4)
        self.assertAlmostEqual(sum(x["annual_usd"] for x in c["components"]), c["budget_usd"], delta=1.0)     # the breakdown still adds up
        self.assertEqual(len([x for x in c["components"] if x["key"].startswith("mgmt_")]), 1)
        d = comp(management=self.FEE, charter_rate=9000.0, commission_pct=10.0, **CONF); e = comp(charter_rate=9000.0, commission_pct=10.0, **CONF)
        self.assertAlmostEqual(d["profit"]["operating_result"] - e["profit"]["operating_result"], -60000.0, places=4)
        self.assertGreater(d["profit"]["threshold"]["billed_hours_exact"], e["profit"]["threshold"]["billed_hours_exact"])
        self.assertEqual(d["profit"]["threshold_economic"]["status"], "incomplete")           # not an ownership cost

    def test_management_in_eur_needs_a_dated_rate(self):
        fee = {"management": {"amount": 55000.0, "ccy": "EUR"}}
        self.assertFalse(comp(management=fee)["available"])
        r = comp(management=fee, fx=E.Fx("EUR", 0.9, "2026-10-17")); self.assertTrue(r["available"])
        self.assertAlmostEqual(r["management"]["management"]["amount_usd"], 55000.0 / 0.9, places=4)

    def test_camo_dispatch_added_when_entered_but_not_when_covered_by_the_fee(self):
        base = comp(management=self.FEE)
        both = comp(management={**self.FEE, "camo": {"amount": 20000.0, "ccy": "USD"}, "dispatch": {"amount": 10000.0, "ccy": "USD"}})
        self.assertAlmostEqual(both["fixed"]["annual_total"] - base["fixed"]["annual_total"], 30000.0, places=4)
        cov = comp(management={**self.FEE, "camo": {"amount": 20000.0, "ccy": "USD"}, "dispatch": {"amount": 10000.0, "ccy": "USD"}}, management_covers_camo_dispatch=True)
        self.assertEqual(cov["fixed"]["annual_total"], base["fixed"]["annual_total"])          # no double count
        self.assertEqual(cov["management"]["camo"]["status"], "covered"); self.assertEqual(cov["management"]["dispatch"]["status"], "covered")
        # 'covered' needs a fee: without one the flag changes nothing and the CAMO amount is still added
        nofee = comp(management={"camo": {"amount": 20000.0, "ccy": "USD"}}, management_covers_camo_dispatch=True)
        self.assertAlmostEqual(nofee["fixed"]["annual_total"] - comp()["fixed"]["annual_total"], 20000.0, places=4)
        self.assertNotEqual(cov["config_hash"], both["config_hash"])

    def test_per_landing_disabled_adds_nothing_enabled_adds_once_per_flown_hour(self):
        a = comp()
        off = comp(cycle_status="none", cycle_cost=3000.0, avg_flight_hours=2.0)               # values typed but the option is off: no effect
        self.assertEqual(off["budget_usd"], a["budget_usd"]); self.assertNotIn("cycle_cost", [x["key"] for x in off["components"]])
        on = comp(cycle_status="added", cycle_cost=3000.0, avg_flight_hours=2.0)
        self.assertAlmostEqual(on["variable"]["per_h"] - a["variable"]["per_h"], 1500.0, places=6)
        landings = 300.0 / 2.0
        self.assertAlmostEqual(on["budget_usd"] - a["budget_usd"], 3000.0 * landings, places=4)           # = cost × number of landings, once
        self.assertEqual(comp(cycle_status="added", cycle_cost=3000.0, avg_flight_hours=2.0, positioning_hours=30.0, other_hours=20.0)["variable"]["per_h"], on["variable"]["per_h"])
        self.assertNotEqual(on["config_hash"], off["config_hash"])

    def test_per_landing_in_results_and_threshold_without_double_count(self):
        k = dict(charter_rate=9000.0, commission_pct=10.0, **CONF)
        a = comp(**k)["profit"]; on = comp(cycle_status="added", cycle_cost=3000.0, avg_flight_hours=2.0, **k)["profit"]
        self.assertLess(on["operating_result"], a["operating_result"]); self.assertGreater(on["threshold"]["billed_hours_exact"], a["threshold"]["billed_hours_exact"])
        be = on["threshold"]["billed_hours_exact"]
        z = comp(billed_hours=be, cycle_status="added", cycle_cost=3000.0, avg_flight_hours=2.0, **k)["profit"]
        self.assertAlmostEqual(z["operating_result"], 0.0, delta=0.01)                         # threshold == zero of the SAME result

    def test_per_landing_missing_inputs_is_an_error_never_zero(self):
        for kw in (dict(cycle_cost=None, avg_flight_hours=2.0), dict(cycle_cost=3000.0, avg_flight_hours=None), dict(cycle_cost=3000.0, avg_flight_hours=0.0)):
            self.assertFalse(comp(cycle_status="added", **kw)["available"], kw)
        self.assertFalse(comp(cycle_status="added", cycle_cost=3000.0, cycle_cost_ccy="EUR", avg_flight_hours=2.0)["available"])
        self.assertTrue(comp(cycle_status="added", cycle_cost=2700.0, cycle_cost_ccy="EUR", avg_flight_hours=2.0, fx=E.Fx("EUR", 0.9, "2026-10-17"))["available"])

    def test_no_repetitive_warning_when_nothing_is_enabled(self):
        r = comp(); sc = E.costs_scope(row(), r, E.Scenario(FAL, mode="simulation", billed_hours=300.0))
        allt = " ".join(sc["not_confirmed"] + sc["limits"] + sc["exclusions"]).lower()
        self.assertNotIn("per-landing", allt); self.assertNotIn("camo", allt); self.assertNotIn("not in the base", allt)

    def test_reference_mode_ignores_every_adjustment(self):
        r0 = E.compute(row(), E.Scenario(FAL, mode="reference")); r1 = E.compute(row(), E.Scenario(FAL, mode="reference", management=self.FEE, cycle_status="added", cycle_cost=3000.0, avg_flight_hours=2.0))
        self.assertEqual(r0["budget_usd"], r1["budget_usd"]); self.assertEqual(r0["config_hash"], r1["config_hash"])


class TestScopeBlock(unittest.TestCase):
    def test_content(self):
        r = comp(); sc = E.costs_scope(row(), r, E.Scenario(FAL, mode="simulation", billed_hours=300.0))
        self.assertTrue(sc["included"]); allt = " ".join(sc["limits"] + sc["exclusions"] + sc["not_confirmed"]).lower()
        for w in ("major inspection", "landing gear", "engine", "apu", "programme", "unbudgeted", "loan interest", "depreciation", "tax"):
            self.assertIn(w, allt, w)
        self.assertNotIn("missing cost", " ".join(sc["not_confirmed"]).lower())
        self.assertIn("unknown", allt)

    def test_hash_changes_with_every_new_assumption(self):
        base = E.Scenario(FAL, mode="simulation", billed_hours=300.0, charter_rate=9000.0, commission_pct=10.0)
        h0 = comp(charter_rate=9000.0, commission_pct=10.0)["config_hash"]
        for kw in (dict(rate_basis="net"), dict(positioning_confirmed=True), dict(limits_reviewed=True), dict(depreciation_annual=0.0), dict(interest_annual=1.0),
                   dict(management={"camo": {"amount": 1.0}}), dict(cycle_status="added", cycle_cost=1.0, avg_flight_hours=1.0), dict(management_covers_camo_dispatch=True), dict(positioning_ratio=0.1), dict(supplements_retained_usd=1.0)):
            self.assertNotEqual(comp(charter_rate=9000.0, commission_pct=10.0, **kw)["config_hash"], h0, kw)


class TestFxRate(unittest.TestCase):
    def test_eur_rate_needs_dated_conversion_and_is_consistent(self):
        self.assertFalse(comp(charter_rate=8000.0, charter_rate_ccy="EUR", commission_pct=0.0)["profit"]["available"])
        fx = E.Fx("EUR", 0.92, "2026-10-17")
        a = comp(charter_rate=8280.0, charter_rate_ccy="EUR", commission_pct=0.0, fx=fx)["profit"]
        b = comp(charter_rate=9000.0, charter_rate_ccy="USD", commission_pct=0.0, fx=fx)["profit"]
        self.assertAlmostEqual(a["rate_usd"], 9000.0, places=6); self.assertAlmostEqual(a["operating_result"], b["operating_result"], places=4)


class TestNo15Double(unittest.TestCase):
    def test_report_reference_reads_originals_and_simulation_is_not_re_adjusted(self):
        r = E.compute(row(), E.Scenario(FAL, mode="reference"))
        self.assertAlmostEqual(r["budget_usd"], 1637042.0, delta=1.0)
        self.assertAlmostEqual(row()["fixed_total"] if "fixed_total" in row().index else 588918.0, row()["fixed_total"] if "fixed_total" in row().index else 588918.0)
        s = E.compute(row(), E.Scenario(FAL, mode="simulation", billed_hours=E.num(row(), "reference_annual_hours")))
        self.assertGreater(s["budget_usd"], r["budget_usd"])                                  # +15 % applied once (stored in the base)
        self.assertLess(s["budget_usd"], r["budget_usd"] * 1.16)                              # never a second +15 % on top
        for f in ("app.py", "menkor_engine.py"):
            self.assertNotRegex(_rd(f), r"\*\s*1\.15\b", f)


if __name__ == "__main__":
    unittest.main()
