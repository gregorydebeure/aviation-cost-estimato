"""
Tests for Aviation Cost Estimator v15 (spec §9).  Run from the project folder:

    python3 -m unittest discover -s tests -v

Needs only pandas (+ reportlab for the PDF test, pdftotext optional).  The screen tests use
tests/fake_streamlit.py, a recorder that stands in for Streamlit — real browser rendering is not covered.
"""
import copy
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import pandas as pd  # noqa: E402
import menkor_engine as E  # noqa: E402

def raw_base():
    """The base with the ORIGINAL published values (original__ columns written back): the v15/v16 formula tests were written against it."""
    b = E.load_base().copy()
    for c in [c for c in b.columns if c.startswith(E.ORIGINAL_PREFIX)]:
        f = c[len(E.ORIGINAL_PREFIX):]
        b[f] = b[c].where(b[c].notna(), b[f])
    return b


ADJ = E.load_base()          # Menkor cost base as shipped (selected costs +15 %, originals in original__ columns)
BASE = raw_base()
CHECKS = E.load_checks()
CONFLICTS = E.load_conflicts()
CONVS = E.load_conversions()
INV = E.load_inventory()
PROV = E.load_provenance()


def read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
        return fh.read()


def row(aid):
    return BASE[BASE["aircraft_id"] == aid].iloc[0]


def sim(aid, **kw):
    r = row(aid)
    hours = kw.pop("billed_hours", E.num(r, "reference_annual_hours"))
    return E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=hours, **kw))


def ref(aid):
    return E.compute(row(aid), E.Scenario(aid, mode="reference"))


class TestDataIntegration(unittest.TestCase):
    def test_counts_and_identifiers(self):
        self.assertEqual(len(BASE), 167)
        sk = BASE["source_kind"].value_counts().to_dict()
        self.assertEqual(sk, {"pdf_acc": 144, "web_estimate": 2, "historical": 21})
        self.assertEqual(int(BASE["has_detail"].sum()), 146)
        self.assertEqual((~BASE["has_detail"]).sum(), 21)
        self.assertEqual(BASE["aircraft_id"].nunique(), 167)       # aircraft_id is the stable key
        self.assertEqual(BASE["model"].nunique(), 167)

    def test_provenance_classes_exist_and_are_kept(self):
        self.assertEqual(len(PROV), 12789)
        classes = set(PROV["status"].map(E.data_class))
        for c in ("Extracted", "Calculated", "Converted (calculated)", "Missing", "Invalid source value (left empty)"):
            self.assertIn(c, classes)
        r = row("dassault_falcon_7x")
        self.assertEqual(r["currency"], "USD")
        self.assertEqual(r["source_file"], "Dassault Falcon 7X.pdf")
        # extraction date is processing metadata, report/price date is not provided
        self.assertEqual(r["source_date_status"], "not_provided")
        pr = PROV[(PROV.aircraft_id == "dassault_falcon_7x") & (PROV.field == "report_date")].iloc[0]
        self.assertEqual(pr["status"], "missing")

    def test_missing_is_none_never_zero(self):
        r = row("challenger_870c")
        for f in ("maximum_takeoff_weight_kg", "maximum_landing_weight_kg", "basic_operating_weight_kg", "usable_fuel_weight_kg"):
            self.assertIsNone(E.num(r, f), f)
        self.assertIsNone(E.num(row("embraer_erj_170lr"), "average_preowned_price_usd") if (BASE.aircraft_id == "embraer_erj_170lr").any() else None)
        pm = BASE[BASE["average_preowned_price_usd"].isna() & (BASE["source_kind"] == "pdf_acc")]
        self.assertEqual(len(pm), 2)                                  # ERJ-170LR and Jetstar II/731
        # the printed zeros stay visible in provenance with their specific status
        z = PROV[PROV["status"] == "invalid_source_placeholder"]
        self.assertEqual(len(z), 6)

    def test_legacy_rows_have_no_invented_detail(self):
        leg = BASE[~BASE["has_detail"]]
        for f in ("annual_fuel_cost_usd", "fuel_burn_l_per_h", "annual_budget_usd", "reference_fuel_price_usd_per_l"):
            self.assertTrue(leg[f].isna().all(), f)
        self.assertTrue(leg["record_status"].eq(E.LEGACY_STATUS).all())

    def test_archive_checks_and_tolerances_kept(self):
        self.assertEqual(len(CHECKS), 2340)
        self.assertEqual(int((CHECKS["status"] == "REVIEW").sum()), 376)
        self.assertIn("tolerance", CHECKS.columns)
        k = CHECKS[(CHECKS.aircraft_id == "challenger_870c") & CHECKS["check"].str.startswith("positive_physical_value")]
        self.assertEqual(len(k), 4)
        self.assertTrue((k["status"] == "REVIEW").all())
        # alerts surface the REVIEW checks of the model and the invalid masses of the 870C
        al = E.alerts_for(row("challenger_870c"), CHECKS, CONFLICTS, CONVS, admin=True)      # internal traceability: admin only
        txt = " ".join(a["text"] for a in al)
        self.assertIn("numeric check(s) to review", txt)
        self.assertIn("invalid (0)", txt)
        self.assertIn("maximum_takeoff_weight_kg", txt)
        cl = " ".join(a["text"] for a in E.alerts_for(row("challenger_870c"), CHECKS, CONFLICTS, CONVS))      # client wording: no field names, no tolerances
        self.assertIn("invalid (0)", cl)
        for hidden in ("numeric check", "maximum_takeoff_weight_kg", "tol.", "observed"):
            self.assertNotIn(hidden, cl)

    def test_extraction_date_not_presented_as_price_validity(self):
        t = " ".join(a["text"] for a in E.alerts_for(row("dassault_falcon_7x"), CHECKS, CONFLICTS, CONVS, admin=True))
        self.assertIn("processing date, not a market date", t)
        c = " ".join(a["text"] for a in E.alerts_for(row("dassault_falcon_7x"), CHECKS, CONFLICTS, CONVS))
        self.assertIn("Economic reference date not documented", c); self.assertNotIn("extraction", c)


class TestDoubleCounting(unittest.TestCase):
    def test_falcon_7x_crew_not_added_twice(self):
        r = ref("dassault_falcon_7x")
        self.assertEqual(r["fixed"]["annual_total"], 588918)          # NOT 588,918 + 377,505 = 966,423
        self.assertNotEqual(r["fixed"]["annual_total"], 588918 + 377505)
        self.assertEqual(r["budget_usd"], 1637042)
        self.assertAlmostEqual(r["budget_usd"], 588918 + 1048124, delta=1)
        s = sim("dassault_falcon_7x")
        self.assertEqual(s["fixed"]["annual_total"], 588918)
        crew = [c for c in s["components"] if c["key"] == "crew_expense"][0]
        self.assertEqual(crew["annual_usd"], 377505)                  # shown as a component OF the 588,918
        fixed_rows = [c for c in s["components"] if c["category"] == "Fixed"]
        self.assertAlmostEqual(sum(c["annual_usd"] for c in fixed_rows), 588918, places=6)   # breakdown == total, no extra

    def test_all_models_fixed_total_is_source_total(self):
        for _, r in BASE[BASE.has_detail].iterrows():
            x = ref(r.aircraft_id)
            self.assertEqual(x["fixed"]["annual_total"], r["annual_fixed_cost_usd"], r.aircraft_id)
            self.assertLessEqual(abs(x["budget_usd"] - (x["fixed"]["annual_total"] + x["variable"]["annual"])), 1.0, r.aircraft_id)  # archive tolerance
            s = sim(r.aircraft_id)
            self.assertEqual(s["fixed"]["annual_total"], r["annual_fixed_cost_usd"])

    def test_component_edit_replaces_not_adds(self):
        base = sim("dassault_falcon_7x")["fixed"]["annual_total"]
        e = sim("dassault_falcon_7x", fixed_overrides={"crew_expense": 400000.0})
        self.assertAlmostEqual(e["fixed"]["annual_total"], base + (400000 - 377505), places=6)
        # editing back to the source value changes nothing
        e0 = sim("dassault_falcon_7x", fixed_overrides={"crew_expense": 377505.0})
        self.assertAlmostEqual(e0["fixed"]["annual_total"], base, places=6)
        # variable: replacing airframe maintenance hourly 471 -> 600 adds exactly 129 per flown hour
        v0 = sim("dassault_falcon_7x")["variable"]["per_h"]
        v1 = sim("dassault_falcon_7x", var_overrides_h={"airframe_maint": 600.0})["variable"]["per_h"]
        self.assertAlmostEqual(v1 - v0, 600 - 471, places=6)

    def test_variable_components_are_a_breakdown_not_an_addition(self):
        s = sim("dassault_falcon_7x")
        var_rows = [c for c in s["components"] if c["category"] == "Variable"]
        self.assertAlmostEqual(sum(c["annual_usd"] for c in var_rows), s["variable"]["annual"], places=4)
        # crew travel + catering + airport + other are components of crew misc, not extra
        r = row("dassault_falcon_7x")
        self.assertAlmostEqual(sum(E.num(r, f) for f in ("hourly_crew_travel_usd", "hourly_catering_usd", "hourly_airport_fees_usd", "hourly_other_usd")),
                               E.num(r, "hourly_crew_misc_usd"), delta=2)

    def test_old_double_count_would_have_been_visible(self):
        r = row("dassault_falcon_7x")
        old_fixed = r["annual_fixed_cost_usd"] + r["annual_crew_expense_fixed_usd"]
        self.assertEqual(old_fixed, 966423)                           # the figure seen in the old Dashboard
        self.assertNotEqual(sim("dassault_falcon_7x")["fixed"]["annual_total"], old_fixed)


class TestSimulationFormulas(unittest.TestCase):
    def test_formulas_match_spec_exactly(self):
        r = row("dassault_falcon_7x")
        var, fuel, ref_h = r["annual_variable_cost_usd"], r["annual_fuel_cost_usd"], r["reference_annual_hours"]
        nonfuel = (var - fuel) / ref_h
        burn, price = r["fuel_burn_l_per_h"], r["reference_fuel_price_usd_per_l"]
        H = 420.0
        s = sim("dassault_falcon_7x", billed_hours=H)
        self.assertAlmostEqual(s["variable"]["nonfuel_per_h"], nonfuel, places=9)
        self.assertAlmostEqual(s["variable"]["fuel_per_h"], burn * price, places=9)
        self.assertAlmostEqual(s["variable"]["annual"], H * (nonfuel + burn * price), places=6)
        self.assertAlmostEqual(s["budget_usd"], r["annual_fixed_cost_usd"] + H * (nonfuel + burn * price), places=6)
        self.assertAlmostEqual(s["cost_per_h_usd"], s["budget_usd"] / H, places=9)

    def test_fuel_price_change(self):
        a = sim("dassault_falcon_7x")
        fc = E.FuelConfig(price_source="manual", price=2 * 0.99, unit="L", currency="USD")
        b = sim("dassault_falcon_7x", fuel=fc)
        self.assertAlmostEqual(b["variable"]["fuel_per_h"], 2 * a["variable"]["fuel_per_h"], places=9)
        self.assertAlmostEqual(b["variable"]["nonfuel_per_h"], a["variable"]["nonfuel_per_h"], places=9)   # only fuel moves
        self.assertEqual(b["fixed"]["annual_total"], a["fixed"]["annual_total"])
        self.assertNotEqual(a["config_hash"], b["config_hash"])

    def test_annual_hours_change(self):
        a, b = sim("dassault_falcon_7x", billed_hours=350), sim("dassault_falcon_7x", billed_hours=700)
        self.assertAlmostEqual(b["variable"]["annual"], 2 * a["variable"]["annual"], places=6)
        self.assertEqual(a["fixed"]["annual_total"], b["fixed"]["annual_total"])
        self.assertLess(b["cost_per_h_usd"], a["cost_per_h_usd"])             # fixed cost spread over more hours

    def test_burn_methods(self):
        r = row("dassault_falcon_7x")
        pub = sim("dassault_falcon_7x", fuel=E.FuelConfig(burn_method="published"))
        der = sim("dassault_falcon_7x", fuel=E.FuelConfig(burn_method="derived"))
        cus = sim("dassault_falcon_7x", fuel=E.FuelConfig(burn_method="custom", custom_burn_l_h=1500.0))
        self.assertEqual(pub["fuel"]["burn_l_h"], r["fuel_burn_l_per_h"])
        self.assertEqual(der["fuel"]["burn_l_h"], r["fuel_burn_from_annual_l_per_h"])
        self.assertEqual(cus["fuel"]["burn_l_h"], 1500.0)
        self.assertIn("average economic assumption", pub["fuel"]["note"].lower())

    def test_report_vs_simulation_not_forced_equal_but_close(self):
        worst = 0.0
        for _, r in BASE[BASE.has_detail].iterrows():
            a, s = ref(r.aircraft_id), sim(r.aircraft_id)
            gap = abs(s["budget_usd"] - a["budget_usd"]) / a["budget_usd"]
            worst = max(worst, gap)
            self.assertIsNotNone(s["reconciliation"])
            self.assertAlmostEqual(s["reconciliation"]["difference"], s["budget_usd"] - a["budget_usd"], places=4)
        self.assertLess(worst, 0.005)                                  # < 0.5% (measured max 0.29%): rounding of printed burn/price
        # source data untouched
        self.assertEqual(row("dassault_falcon_7x")["annual_fuel_cost_usd"], 494252)

    def test_reference_mode_returns_published_totals(self):
        for _, r in BASE[BASE.has_detail].iterrows():
            x = ref(r.aircraft_id)
            self.assertEqual(x["budget_usd"], r["annual_budget_usd"])
            self.assertAlmostEqual(x["cost_per_h_usd"], r["total_cost_per_h_from_annual_usd"], places=4)
            self.assertEqual(x["variable"]["annual"], r["annual_variable_cost_usd"])


class TestUnitsAndCurrency(unittest.TestCase):
    def test_gallon_litre_conversions_documented(self):
        r = row("challenger_300")
        self.assertAlmostEqual(r["reference_fuel_price_usd_per_l"], 4.25 / 3.785411784, places=6)
        self.assertAlmostEqual(r["fuel_burn_l_per_h"], 286 * 3.785411784, delta=0.5)
        self.assertAlmostEqual(r["annual_fuel_volume_l"], 100100 * 3.785411784, delta=1)
        for _, c in CONVS[CONVS.source_unit == "GAL/h"].iterrows():
            self.assertAlmostEqual(float(c.converted_value), float(c.source_value) * E.USG_TO_L, delta=1e-6)
        for _, c in CONVS[CONVS.source_unit == "USD/GAL"].iterrows():
            self.assertAlmostEqual(float(c.converted_value), float(c.source_value) / E.USG_TO_L, delta=1e-6)
        self.assertEqual(E.USG_TO_L, 3.785411784)

    def test_manual_price_unit_and_currency_conversion(self):
        fx = E.Fx("EUR", 0.9, "2026-10-17")
        p, err = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual", price=4.25, unit="USG", currency="USD"), fx)
        self.assertIsNone(err); self.assertAlmostEqual(p, 4.25 / 3.785411784, places=9)
        p, _ = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual", price=1.0, unit="L", currency="USD", taxes_pct=10), fx)
        self.assertAlmostEqual(p, 1.1, places=9)
        p, _ = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual", price=0.9, unit="L", currency="EUR"), fx)
        self.assertAlmostEqual(p, 1.0, places=9)                                   # 0.9 EUR at 0.9 EUR/USD = 1 USD
        p, err = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual", price=0.9, unit="L", currency="EUR"), E.Fx())
        self.assertIsNone(p); self.assertIn("EUR", err)                            # no silent conversion without a rate
        p, err = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual"), fx)
        self.assertIsNone(p)                                                        # no default price invented

    def test_eur_display_needs_dated_rate(self):
        d = E.Display(E.Fx("EUR"))
        self.assertTrue(d.eur_blocked); self.assertEqual(d.ccy, "USD"); self.assertTrue(d.money(1000).startswith("$"))
        d = E.Display(E.Fx("EUR", 0.9))                                            # rate without date
        self.assertTrue(d.eur_blocked)
        d = E.Display(E.Fx("EUR", 0.9, "17/10/2026"))                              # bad date format
        self.assertTrue(d.eur_blocked)
        d = E.Display(E.Fx("EUR", 0.9, "2026-10-17", "ECB"))
        self.assertEqual(d.ccy, "EUR"); self.assertEqual(d.money(1000), "€ 900"); self.assertIn("2026-10-17", d.note())
        self.assertAlmostEqual(d.to_usd(d.conv(1234.5)), 1234.5, places=9)
        self.assertEqual(E.Display(E.Fx("USD")).money(1000), "$ 1,000")

    def test_charter_rate_in_eur_requires_rate(self):
        s = sim("dassault_falcon_7x", charter_rate=9000.0, charter_rate_ccy="EUR")
        self.assertFalse(s["profit"]["available"]); self.assertIn("EUR", " ".join(s["profit"]["messages"]))
        s = sim("dassault_falcon_7x", charter_rate=9000.0, charter_rate_ccy="EUR", fx=E.Fx("USD", 0.9, "2026-10-17"))
        self.assertTrue(s["profit"]["available"]); self.assertAlmostEqual(s["profit"]["rate_usd"], 10000.0, places=6)

    def test_fx_is_kept_in_results_and_hash(self):
        a = sim("dassault_falcon_7x", fx=E.Fx("EUR", 0.9, "2026-10-17"))
        b = sim("dassault_falcon_7x", fx=E.Fx("EUR", 0.95, "2026-10-17"))
        self.assertEqual(a["scenario"]["fx"]["usd_to_eur"], 0.9)
        self.assertEqual(a["scenario"]["fx"]["rate_date"], "2026-10-17")
        self.assertNotEqual(a["config_hash"], b["config_hash"])
        self.assertEqual(a["budget_usd"], b["budget_usd"])                          # the engine keeps USD; only display changes

    def test_stopover_consumed_vs_purchased(self):
        r = E.stopover_purchase(1000, "USG", 5.0, "USD", 10, 100, 3000, E.Fx())
        self.assertAlmostEqual(r["purchased_l"], 3785.411784, places=6)
        self.assertAlmostEqual(r["balance_l"], 785.411784, places=6)
        self.assertAlmostEqual(r["purchase_cost"], 1000 * 5.5 + 100, places=6)
        r = E.stopover_purchase(1000, "L", 1.0, "EUR", 0, 0, 800, E.Fx())
        self.assertIsNone(r["usd"])                                                  # EUR with no rate: not converted


class TestZeroHoursAndMissingData(unittest.TestCase):
    def test_zero_hours(self):
        s = sim("dassault_falcon_7x", billed_hours=0)
        self.assertTrue(s["available"])
        self.assertIsNone(s["cost_per_h_usd"])                                      # "not applicable", not 0 and not a crash
        self.assertEqual(s["budget_usd"], s["fixed"]["annual_total"])
        self.assertEqual(s["variable"]["annual"], 0)
        self.assertIn("zero_hours", [f["code"] for f in s["flags"]])
        s = sim("dassault_falcon_7x", billed_hours=0, charter_rate=9000.0)
        self.assertTrue(s["profit"]["available"]); self.assertAlmostEqual(s["profit"]["operating_result"], -s["fixed"]["annual_total"])

    def test_missing_core_value_is_not_zero(self):
        r = row("dassault_falcon_7x").copy()
        r["annual_fuel_cost_usd"] = float("nan")
        x = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350))
        self.assertFalse(x["available"]); self.assertIsNone(x["budget_usd"])
        self.assertIn("missing_core", [f["code"] for f in x["flags"]])
        r2 = row("dassault_falcon_7x").copy(); r2["fuel_burn_l_per_h"] = float("nan"); r2["fuel_burn_from_annual_l_per_h"] = float("nan")
        x = E.compute(r2, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350))
        self.assertFalse(x["available"]); self.assertIn("no_burn", [f["code"] for f in x["flags"]])
        r3 = row("dassault_falcon_7x").copy(); r3["reference_fuel_price_usd_per_l"] = float("nan")
        x = E.compute(r3, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350))
        self.assertFalse(x["available"])

    def test_missing_component_override_ignored_and_flagged(self):
        r = row("dassault_falcon_7x").copy(); r["annual_hangar_fixed_usd"] = float("nan")
        x = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350, fixed_overrides={"hangar": 99999.0}))
        self.assertIn("override_ignored", [f["code"] for f in x["flags"]])
        self.assertEqual(x["fixed"]["annual_total"], r["annual_fixed_cost_usd"])
        self.assertNotIn("hangar", [c["key"] for c in x["components"]])             # no zero line invented

    def test_missing_rate_gives_unavailable_profit(self):
        s = sim("dassault_falcon_7x")
        self.assertFalse(s["profit"]["available"]); self.assertIn("Enter your expected charter revenue per billed hour", " ".join(s["profit"]["messages"]))

    def test_manual_price_missing_is_error_not_zero(self):
        s = sim("dassault_falcon_7x", fuel=E.FuelConfig(price_source="manual"))
        self.assertFalse(s["available"]); self.assertIn("price_manual", [f["code"] for f in s["flags"]])

    def test_zero_source_values_kept_and_flagged(self):
        a = E.alerts_for(row("flaris_lar01"), CHECKS, CONFLICTS, CONVS)
        self.assertIn("Insurance is recorded as 0", " ".join(x["text"] for x in a))
        self.assertEqual(E.num(row("flaris_lar01"), "annual_insurance_fixed_usd"), 0.0)

    def test_negative_hours_rejected(self):
        r = row("dassault_falcon_7x")
        x = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=-10.0))
        self.assertFalse(x["available"])

    def test_historical_fixed_split_validated_on_old_base_models(self):
        """Old-base rule: Couts_Fixes (excl. crew) + Couts_Equipe (crew + training) == report fixed total, on every model that has both."""
        both = BASE[BASE["has_detail"] & BASE["legacy_Couts_Fixes_Annuels"].notna()]
        self.assertEqual(len(both), 10)
        for _, r in both.iterrows():
            tot = E.num(r, "legacy_Couts_Fixes_Annuels") + E.num(r, "legacy_Couts_Equipe_Annuels")
            self.assertLessEqual(abs(tot - r["annual_fixed_cost_usd"]), 1.0, r["model"])               # archive tolerance 1 USD
            crew_plus_training = r["annual_crew_expense_fixed_usd"] + r["annual_crew_training_fixed_usd"]
            self.assertLessEqual(abs(E.num(r, "legacy_Couts_Equipe_Annuels") - crew_plus_training), 1.0, r["model"])
        x = E.compute(row("airbus_340"), E.Scenario("airbus_340", mode="reference"))
        self.assertEqual(x["fixed"]["annual_total"], 360066 + 471643)                                # crew counted once
        self.assertTrue(any(f["code"] == "legacy_fixed_split" for f in x["flags"]))

    def test_historical_sheet_limits(self):
        s = E.compute(row("airbus_340"), E.Scenario("airbus_340", mode="simulation", billed_hours=100.0, fuel=E.FuelConfig(price_source="manual", price=5)))
        self.assertTrue(s["historical"]); self.assertEqual(s["fuel"], {})
        self.assertTrue(any(f["code"] == "legacy" for f in s["flags"]))
        self.assertIsNone(s["variable"]["fuel_per_h"])                               # fuel not separable: n/a, not 0


class TestCharterProfitability(unittest.TestCase):
    RATE = 9500.0

    def base(self, **kw):
        return sim("dassault_falcon_7x", billed_hours=kw.pop("billed", 300.0), charter_rate=self.RATE, commission_pct=kw.pop("comm", 10.0), **kw)

    def test_formula(self):
        s = self.base(positioning_hours=40.0, other_hours=60.0, other_commercial_fees=20000.0)
        p, v = s["profit"], s["variable"]["per_h"]
        H = 300 + 40 + 60
        self.assertEqual(p["flown_hours"], H)
        self.assertAlmostEqual(p["revenue"], 300 * self.RATE)
        self.assertAlmostEqual(p["variable_cost_all_flown"], H * v, places=6)       # variable cost of ALL flown hours
        expected = 300 * self.RATE - 0.10 * 300 * self.RATE - 20000 - H * v - s["fixed"]["annual_total"]
        self.assertAlmostEqual(p["operating_result"], expected, places=6)

    def test_positioning_costs_but_earns_nothing(self):
        a, b = self.base(), self.base(positioning_hours=50.0)
        self.assertEqual(a["profit"]["revenue"], b["profit"]["revenue"])
        self.assertAlmostEqual(a["profit"]["operating_result"] - b["profit"]["operating_result"], 50 * a["variable"]["per_h"], places=6)

    def test_private_hours_use_same_cost_no_082_coefficient(self):
        a, b = self.base(), self.base(other_hours=100.0)
        self.assertAlmostEqual(a["profit"]["operating_result"] - b["profit"]["operating_result"], 100 * a["variable"]["per_h"], places=6)
        src = read("menkor_engine.py")
        self.assertNotIn("0.82", src)                                                # no arbitrary private coefficient in the engine
        self.assertNotIn("0.82", read("menkor_report.py"))

    CONF = dict(positioning_confirmed=True, private_hours_confirmed=True, other_fees_confirmed=True, limits_reviewed=True)

    def test_threshold_is_where_result_is_zero(self):
        s = self.base(positioning_hours=30.0, other_hours=20.0, **self.CONF)
        th = s["profit"]["threshold"]; be = th["billed_hours_exact"]
        self.assertEqual(th["status"], "ok"); self.assertEqual(th["billed_hours"], math.ceil(be - 1e-9))     # whole hours are rounded UP
        rho = 30.0 / 300.0
        z = E.compute(row("dassault_falcon_7x"), E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=be, positioning_hours=rho * be,
                                                            other_hours=20.0, charter_rate=self.RATE, commission_pct=10.0))
        self.assertAlmostEqual(z["profit"]["operating_result"], 0.0, delta=0.01)
        self.assertIn("positioning 0.10", th["assumptions"]); self.assertIn("private/other hours 20 h", th["assumptions"])

    def test_no_threshold_when_contribution_not_positive(self):
        s = sim("dassault_falcon_7x", charter_rate=2000.0, commission_pct=10.0, billed_hours=300.0, **self.CONF)     # cost/h ~ 2,988 variable alone
        p = s["profit"]
        self.assertLessEqual(p["contribution_per_billed_hour"], 0)
        self.assertEqual(p["threshold"]["status"], "unattainable"); self.assertIsNone(p["threshold"]["billed_hours"])
        self.assertEqual(p["threshold"]["message"], "No attainable threshold under these assumptions.")
        s = self.base(positioning_hours=600.0, **self.CONF)                       # heavy positioning can also remove the threshold
        self.assertLessEqual(s["profit"]["contribution_per_billed_hour"], 0)
        self.assertEqual(s["profit"]["threshold"]["status"], "unattainable")

    def test_sensitivity_is_the_same_engine(self):
        r = row("dassault_falcon_7x")
        sc = E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0, positioning_hours=30.0, charter_rate=self.RATE, commission_pct=10.0)
        here = E.compute(r, sc)["profit"]["operating_result"]
        pts = dict(E.sensitivity_billed_hours(r, sc, [300]))
        self.assertAlmostEqual(pts[300], here, places=6)

    def test_required_rate_gives_target_margin(self):
        s = self.base(positioning_hours=20.0)
        rr = E.required_rate(s["profit"], 15.0)
        t = sim("dassault_falcon_7x", billed_hours=300.0, positioning_hours=20.0, charter_rate=rr, commission_pct=10.0)
        self.assertAlmostEqual(t["profit"]["operating_result"] / t["profit"]["revenue"], 0.15, places=6)
        self.assertIsNone(E.required_rate(s["profit"], 95.0))                        # impossible margin: not attainable

    def test_label_is_operating_result_not_net_profit(self):
        app = read("app.py")
        self.assertNotIn("Net Result", app)
        self.assertNotIn("PROFITABLE</span>", app.replace("POSITIVE OPERATING RESULT", ""))
        self.assertIn("Estimated operating result", app)
        self.assertIn("before depreciation, interest and tax", read("menkor_report.py"))
        self.assertIn("not a net profit", app)


class TestVariantsAndG450(unittest.TestCase):
    PAIRS = [("cessna_citation_cj2", "cessna_citation_cj2_plus"), ("cessna_citation_cj3", "cessna_citation_cj3_plus"),
             ("challenger_601_3a", "challenger_601_1a"), ("challenger_850", "challenger_850_cs"),
             ("cessna_citation_xls", "cessna_citation_xls_plus"), ("embraer_phenom_100", "embraer_phenom_100ev"),
             ("embraer_lineage_1000", "embraer_lineage_1000e"), ("eclipse_500", "eclipse_550"),
             ("nextant_400xt", "nextant_400xti"), ("hawker_800xp", "hawker_800xpi"), ("hawker_800a", "hawker_800sp"),
             ("learjet_45", "learjet_45xr"), ("learjet_40", "learjet_40xr"), ("learjet_60", "learjet_60xr"),
             ("learjet_31", "learjet_31a"), ("learjet_31a", "learjet_31aer"), ("dornier_328", "dornier_328_business")]

    def test_variants_distinct_ids_and_not_copied(self):
        ids = set(BASE["aircraft_id"])
        miss = []
        for a, b in self.PAIRS:
            for x in (a, b):
                if x not in ids:
                    miss.append(x)
        # identifiers are looked up by prefix when the exact slug differs slightly
        for x in miss:
            self.assertTrue(any(i.startswith(x[:12]) for i in ids), x)
        found = [(a, b) for a, b in self.PAIRS if a in ids and b in ids]
        self.assertGreaterEqual(len(found), 12)
        num_cols = ["annual_budget_usd", "annual_fixed_cost_usd", "annual_variable_cost_usd", "fuel_burn_l_per_h", "seats_full_range_nm", "normal_cruise_kts"]
        for a, b in found:
            ra, rb = row(a), row(b)
            self.assertTrue(any(E.num(ra, c) != E.num(rb, c) for c in num_cols), f"{a} vs {b} must not be copies of each other")

    def test_plus_signs_and_generations_preserved(self):
        ids = set(BASE["aircraft_id"])
        for must in ("cessna_citation_cj2_plus", "cessna_citation_cj3_plus", "cessna_citation_xls_plus"):
            self.assertIn(must, ids)
        self.assertTrue(any("hushkit" in i for i in ids))
        self.assertGreaterEqual(sum(1 for i in ids if i.startswith("gulfstream_g500")), 2)     # two G500 generations, distinct
        self.assertTrue(any("xpi" in i for i in ids)); self.assertTrue(any(i.endswith("xr") for i in ids))
        self.assertTrue(any("400xt" in i for i in ids))

    def test_g450_single_model_with_conflict_kept(self):
        g = BASE[BASE["aircraft_id"].str.contains("g450")]
        self.assertEqual(len(g), 1)
        r = g.iloc[0]
        self.assertEqual(r["source_file"], "Gulfstream G450.Pdf")                  # main source indicated in the base
        self.assertEqual(r["record_status"], "source_conflict_review_required")
        self.assertEqual(r["annual_budget_usd"], 1759142)
        c = CONFLICTS[CONFLICTS["field"] == "annual_budget_usd"].iloc[0]
        self.assertEqual((float(c.primary_value), float(c.alternate_value)), (1759142.0, 2013162.0))
        self.assertEqual(len(CONFLICTS), 29)
        inv = INV[INV["aircraft_id"] == "gulfstream_g450"]
        self.assertEqual(sorted(inv["source_role"]), ["alternate", "primary"])
        for f in inv["file"]:
            self.assertGreater(len(CHECKS[(CHECKS.aircraft_id == "gulfstream_g450") & (CHECKS.source_file == f)]), 0)   # checks kept per source
            self.assertGreater(len(PROV[(PROV.aircraft_id == "gulfstream_g450") & (PROV.source_file == f)]), 0)       # provenance kept per source
        x = ref("gulfstream_g450")
        self.assertEqual(x["budget_usd"], 1759142)                                  # engine uses the primary source only, not an average
        al = " ".join(a["text"] for a in E.alerts_for(r, CHECKS, CONFLICTS, CONVS))
        self.assertIn("Source conflict", al); self.assertIn("29", al)
        # the two reports are not two aircraft in the app
        self.assertEqual(int((BASE["model"].str.contains("G450")).sum()), 1)

    def test_870c_name_not_merged_or_renamed(self):
        r = row("challenger_870c")
        self.assertEqual(r["record_status"], "model_name_and_source_values_review_required")
        self.assertIn("870CS", str(r["source_model_report"]))
        self.assertIn("870C", r["model"])

    def test_seats_range_semantics(self):
        p = E.performance_summary(row("dassault_falcon_7x"))
        self.assertEqual(p["seats_range_nm"], 5353); self.assertEqual(p["ferry_range_nm"], 5723)
        self.assertIn("all passenger seats occupied", p["range_definition"])
        app = read("app.py")
        self.assertNotIn("Max Range", app)
        self.assertIn("Range — seats occupied", app)
        # a model without that value stays empty (nothing borrowed from a neighbour)
        miss = BASE[BASE["has_detail"] & BASE["seats_full_range_nm"].isna()]
        for _, m in miss.iterrows():
            self.assertIsNone(E.performance_summary(m)["seats_range_nm"])


class TestSingleEngineAcrossScreensAndPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import smoke_support
        cls.S = smoke_support

    def metrics(self, st):
        return [(a[0], a[1]) for k, a, kw in st.log if k == "metric"]

    def test_dashboard_costmaster_quotation_match_engine(self):
        ov = {"Calculation mode": "Custom simulation", "Expected charter revenue per billed hour": 9500.0, "Rate currency": "USD",
              "This rate represents": "Operator revenue before commission (gross)", "Commission (%) on gross revenue": 10.0,
              "Billed charter hours / year": 300, "Positioning hours (flown, not billed)": 40,
              "Owner / private / other hours (not billed)": 60}
        st, app = self.S.run(ov)
        res = E.compute(ADJ[ADJ.aircraft_id == "dassault_falcon_7x"].iloc[0], E.Scenario(
            "dassault_falcon_7x", mode="simulation", billed_hours=300.0, positioning_hours=40.0, other_hours=60.0,
            charter_rate=9500.0, commission_pct=10.0))
        D = E.Display(E.Fx()).money
        m = self.metrics(st)
        budget = [v for k, v in m if k in ("💶 Total Annual Budget", "💶 Annual budget")]
        self.assertGreaterEqual(len(budget), 2); self.assertTrue(all(v == D(res["budget_usd"]) for v in budget))
        fixed = [v for k, v in m if k in ("🔒 Annual Fixed Costs", "🔒 Annual fixed")]
        self.assertTrue(all(v == D(res["fixed"]["annual_total"]) for v in fixed))
        cph = [v for k, v in m if k in ("⌛ Cost / flown hour",)]
        self.assertTrue(all(v == D(res["cost_per_h_usd"]) for v in cph) and len(cph) == 2)
        op = [v for k, v in m if k == "📊 Estimated operating result"]
        self.assertTrue(all(v == D(res["profit"]["operating_result"]) for v in op) and len(op) == 2)      # Profitability == Cost Master
        self.assertIn(D(E.required_rate(res["profit"], 0)), [v for k, v in m if k.startswith("Rate covering the entered costs")])
        self.assertEqual(sum(1 for k, _ in m if k == "Cost per flown hour"), 1)

    def test_eur_display_consistent_everywhere(self):
        ov = {"Calculation mode": "Custom simulation", "Display currency": "EUR", "EUR for 1 USD": 0.92,
              "Rate date (YYYY-MM-DD)": "2026-10-17", "Expected charter revenue per billed hour": 9500.0}
        st, app = self.S.run(ov)
        fx = E.Fx("EUR", 0.92, "2026-10-17")
        res = E.compute(ADJ[ADJ.aircraft_id == "dassault_falcon_7x"].iloc[0], E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350.0, charter_rate=9500.0, commission_pct=10.0, fx=fx))
        d = E.Display(fx)
        vals = [v for k, a, kw in st.log if k == "metric" for v in [a[1]] if isinstance(v, str) and v[:1] in "€$"]
        self.assertTrue(vals); self.assertTrue(all(v.startswith("€") for v in vals), "no USD amount may appear under a EUR label")
        self.assertIn(d.money(res["budget_usd"]), vals)

    def test_pdf_matches_screen_and_engine(self):
        import menkor_report as R
        fx = E.Fx("EUR", 0.92, "2026-10-17", "test rate")
        sc = E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0, positioning_hours=40.0, other_hours=60.0,
                        charter_rate=9500.0, commission_pct=10.0, fx=fx, fuel=E.FuelConfig(price_source="manual", price=4.0, unit="USG", currency="USD",
                                                                                       airport_icao="LFPB", supplier="TestFuel", validity_date="2026-10-20"))
        r = row("dassault_falcon_7x"); res = E.compute(r, sc); d = E.Display(fx)
        pdf = R.build_report_pdf(res, d, E.alerts_for(r, CHECKS, CONFLICTS, CONVS))
        self.assertTrue(pdf.startswith(b"%PDF"))
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not available")
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "r.pdf"); open(p, "wb").write(pdf)
            txt = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout
        flat = re.sub(r"\s+", " ", txt)
        for needle in (res["config_hash"], d.money(res["budget_usd"]), d.money(res["fixed"]["annual_total"]), d.money(res["variable"]["per_h"]),
                       d.money(res["cost_per_h_usd"]), d.money(res["profit"]["operating_result"]), d.money(res["profit"]["revenue"]),
                       "0.9200 EUR", "2026-10-17", "LFPB", "TestFuel", "2026-10-20", "L/h", "US gal", "before depreciation, interest and tax",
                       "not the manufacturer's maximum range", "not a flight-planning"):
            self.assertIn(needle, flat, needle)

    def test_pdf_obsolete_after_assumption_change(self):
        state = {}
        ov = {"Calculation mode": "Custom simulation", "📄 Generate PDF Report": True}
        st, app = self.S.run(ov, state=state)
        self.assertIn("pdf_report", state)
        h1 = state["pdf_report"]["hash"]
        st2, _ = self.S.run({"Calculation mode": "Custom simulation"}, state=state)           # same assumptions: download offered
        self.assertTrue(any(k == "download_button" and "PDF" in a[0] for k, a, kw in st2.log))
        st3, _ = self.S.run({"Calculation mode": "Custom simulation", "Billed charter hours / year": 500}, state=state)   # hours changed
        self.assertFalse(any(k == "download_button" and "PDF" in a[0] for k, a, kw in st3.log))
        self.assertTrue(any(k == "warning" and "obsolete" in a[0] for k, a, kw in st3.log))

    def test_config_hash_covers_every_assumption(self):
        base = E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0)
        h0 = base.config_hash()
        variants = [dict(billed_hours=310.0), dict(positioning_hours=5.0), dict(other_hours=5.0), dict(charter_rate=1000.0), dict(commission_pct=5.0),
                    dict(other_commercial_fees=1.0), dict(fixed_overrides={"hangar": 1.0}), dict(var_overrides_h={"catering": 1.0}),
                    dict(extra_fixed=1.0), dict(extra_var_h=1.0), dict(fx=E.Fx("EUR", 0.9, "2026-10-17")), dict(fuel=E.FuelConfig(burn_method="derived")),
                    dict(fuel=E.FuelConfig(price_source="manual", price=1.0)), dict(mode="reference")]
        hashes = {E.Scenario(**{**base.__dict__, **v}).config_hash() for v in variants}
        self.assertEqual(len(hashes), len(variants)); self.assertNotIn(h0, hashes)
        self.assertEqual(h0, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0).config_hash())    # same config -> same id

    def test_fleet_comparison_equals_single_compute(self):
        sc = E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0, other_hours=20.0)
        comp = E.fleet_comparison(BASE, sc).set_index("aircraft_id")
        self.assertEqual(len(comp), 146)
        for aid in ("dassault_falcon_7x", "gulfstream_g450", "challenger_300", "pilatus_pc_24"):
            if aid in comp.index:
                x = E.compute(row(aid), E.Scenario(aid, mode="simulation", billed_hours=300.0, other_hours=20.0))
                self.assertAlmostEqual(comp.loc[aid, "budget_usd"], x["budget_usd"], places=6)

    def test_csv_export_carries_assumptions(self):
        import app  # noqa: F401  (already imported by smoke_support)
        fx = E.Fx("EUR", 0.92, "2026-10-17")
        res = E.compute(ADJ[ADJ.aircraft_id == "dassault_falcon_7x"].iloc[0], E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=350.0, fx=fx))
        csv = sys.modules["app"]._results_csv(res, E.Display(fx)).decode("utf-8-sig")
        for needle in ("scenario_reference", res["config_hash"], "usd_to_eur_rate,0.92", "rate_date,2026-10-17", "source_currency,USD"):
            self.assertIn(needle, csv)

    def test_all_screens_run_for_every_aircraft_without_error(self):
        # smoke: all 167 models, both modes, Pro and free — no exception
        ids = list(BASE["aircraft_id"])
        for aid in ids:
            for mode in ("Report reference", "Custom simulation"):
                st, app = self.S.run({"Aircraft model": aid, "Calculation mode": mode, "Charter rate to use": "Custom rate", "Rate per billed hour": 5000.0})
                errs = [a[0] for k, a, kw in st.log if k == "error"]
                self.assertFalse([e for e in errs if "Traceback" in str(e)], aid)
                leak = [" ".join(str(x) for x in a_)[:100] for k, a_, kw in st.log if re.search(r"\bACC\b|aircraftcostcalculator|Aircraft Cost Calculator", " ".join(str(x) for x in a_))]
                self.assertFalse(leak, (aid, mode, leak[:1]))     # the third-party calculator name never reaches the screens
        st, app = self.S.run({}, plan=(False, False))
        own = [a for k, a, kw in st.log if k == "metric" and not str(a[0]).startswith("Demo")]
        self.assertFalse(own)   # free users only see the clearly labelled demo metrics, never their own selection


class TestV16(unittest.TestCase):
    """Integration v16: three Challengers, two partial web Globals, alias, per-source breakdown."""
    S = None

    @classmethod
    def setUpClass(cls):
        import smoke_support
        cls.S = smoke_support

    def test_three_challengers_present_once_and_match_verification_file(self):
        ver = pd.read_csv(os.path.join(ROOT, "data", "challenger_verification.csv"))
        for aid in ("challenger_604", "challenger_605", "challenger_650"):
            self.assertEqual(int((BASE.aircraft_id == aid).sum()), 1, aid)
            self.assertEqual(row(aid)["source_kind"], "pdf_acc")
        self.assertEqual(int(BASE.model.str.contains("Challenger 60[45]|Challenger 650", regex=True).sum()), 3)
        self.assertEqual(BASE["aircraft_id"].duplicated().sum(), 0)
        self.assertGreaterEqual(len(ver), 3)

    def test_challengers_selectable_in_app(self):
        for aid in ("challenger_604", "challenger_605", "challenger_650"):
            st, app = self.S.run({"Aircraft model": aid})
            self.assertTrue([1 for k, a, kw in st.log if k == "metric"], aid)

    def test_alias_global_7000_points_to_7500_without_extra_aircraft(self):
        al = E.load_aliases()
        for q in ("Global 7000", "global 7000", "Global 7500", "bombardier_global_7500"):
            self.assertEqual(E.resolve_alias(q, BASE, al), "bombardier_global_7500", q)
        self.assertEqual(E.resolve_alias("Global 6000", BASE, al), "bombardier_global_6000")
        self.assertEqual(int(BASE.model.str.contains("7000").sum()), 0)
        self.assertEqual(len(BASE), 167)

    def test_two_web_globals_are_flagged_and_separate_from_acc(self):
        for aid in ("bombardier_global_6000", "bombardier_global_7500"):
            r = row(aid)
            self.assertEqual(r["source_kind"], "web_estimate")
            res = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0))
            codes = [f["code"] for f in res["flags"]]
            self.assertIn("web_source", codes)
            self.assertEqual(res["web_source"]["access_date"], "2026-10-18")
            self.assertIn("guardianjet", res["web_source"]["url"].lower())
            al = " ".join(a["text"] for a in E.alerts_for(r, CHECKS, CONFLICTS, CONVS, admin=True))
            for needle in ("US gallon", "USD", "2026-10-18", "training"):
                self.assertIn(needle, al, (aid, needle))
            cl = " ".join(a["text"] for a in E.alerts_for(r, CHECKS, CONFLICTS, CONVS))
            for needle in ("US gallon", "USD", "training"):
                self.assertIn(needle, cl, (aid, needle))
            for hidden in ("Guardian", "guardianjet", "2026-10-18", "http"):
                self.assertNotIn(hidden, cl, (aid, hidden))

    def test_web_totals_modes_and_no_invented_components(self):
        for aid in ("bombardier_global_6000", "bombardier_global_7500"):
            r = row(aid)
            pub = E.num(r, "annual_budget_usd")
            ref_ = E.compute(r, E.Scenario(aid, mode="reference"))
            sim_ = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=E.num(r, "reference_annual_hours")))
            self.assertAlmostEqual(ref_["budget_usd"], pub, delta=1.5)
            self.assertAlmostEqual(sim_["budget_usd"], pub, delta=1.5)
            for res in (ref_, sim_):
                self.assertAlmostEqual(sum(c["annual_usd"] for c in res["components"]), res["budget_usd"], delta=1.0)
                labels = " ".join(c["label"] for c in res["components"]).lower()
                self.assertNotIn("training", labels.replace("training not isolated", ""))
                self.assertNotIn("airframe", labels.replace("airframe/engine split unknown", ""))
            # absent ACC fields stay absent (never zero)
            for f in ("annual_crew_training_fixed_usd", "annual_airframe_maintenance_usd", "annual_engine_apu_maintenance_usd"):
                self.assertIsNone(E.num(r, f), f)

    def test_web_component_edit_replaces_without_double_count(self):
        aid = "bombardier_global_7500"; r = row(aid)
        base = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0))
        h = E.num(r, "hourly_maintenance_total_usd")
        ed = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0, var_overrides_h={"maintenance_total": h + 100}))
        self.assertAlmostEqual(ed["budget_usd"] - base["budget_usd"], 100 * 300, delta=0.01)
        same = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0, var_overrides_h={"maintenance_total": h}))
        self.assertAlmostEqual(same["budget_usd"], base["budget_usd"], delta=0.01)
        # unknown-scope components cannot be edited: ignored with a message, never added
        bad = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0,
                                      fixed_overrides={"crew_training": 5000.0}, var_overrides_h={"airframe_maintenance": 5.0}))
        self.assertAlmostEqual(bad["budget_usd"], base["budget_usd"], delta=0.01)
        self.assertTrue([f for f in bad["flags"] if "ignored" in f["text"]])

    def test_web_fuel_in_litres(self):
        for aid, gal_h in (("bombardier_global_6000", 512.0), ("bombardier_global_7500", 528.0)):
            res = E.compute(row(aid), E.Scenario(aid, mode="simulation", billed_hours=300.0))
            self.assertAlmostEqual(res["fuel"]["burn_l_h"], gal_h * E.USG_TO_L, delta=1.0)
            self.assertAlmostEqual(res["fuel"]["price_usd_l"], 7.54 / E.USG_TO_L, places=4)
            self.assertAlmostEqual(res["fuel"]["fuel_per_h_usd"], res["fuel"]["burn_l_h"] * res["fuel"]["price_usd_l"], delta=0.5)

    def test_web_provenance_and_controls(self):
        pv = PROV[PROV.aircraft_id.isin(["bombardier_global_6000", "bombardier_global_7500"])]
        st_ = set(pv["status"])
        self.assertIn("web_extracted", st_); self.assertIn("assumed", st_)
        self.assertEqual(E.data_class("web_extracted"), "Web estimate (extracted)")
        self.assertEqual(E.data_class("assumed"), "Assumed — to confirm")

    def test_web_globals_screens_pdf_csv(self):
        import app  # noqa: F401
        for aid in ("bombardier_global_6000", "bombardier_global_7500"):
            for mode in ("Report reference", "Custom simulation"):
                st, app_ = self.S.run({"Aircraft model": aid, "Calculation mode": mode})
                self.assertTrue([1 for k, a, kw in st.log if k == "metric"], (aid, mode))
                self.assertFalse([1 for k, a, kw in st.log if k == "error" and "Traceback" in str(a)])
            res = E.compute(row(aid), E.Scenario(aid, mode="simulation", billed_hours=300.0))
            disp = E.Display(E.Fx("USD", None, None))
            csv = sys.modules["app"]._results_csv(res, disp).decode("utf-8-sig")
            for hidden in ("web_source", "guardianjet", "record_type", "2026-10-18"):
                self.assertNotIn(hidden, csv.lower())
            import menkor_report
            pdf = menkor_report.build_report_pdf(res, disp, E.alerts_for(row(aid), CHECKS, CONFLICTS, CONVS))
            self.assertTrue(pdf.startswith(b"%PDF"))
            if shutil.which("pdftotext"):
                with tempfile.TemporaryDirectory() as d:
                    pth = os.path.join(d, "r.pdf"); open(pth, "wb").write(pdf)
                    txt = subprocess.run(["pdftotext", "-layout", pth, "-"], capture_output=True, text=True).stdout
                for needle in ("artial web estimate", "US gallon"):
                    self.assertIn(needle, txt, (aid, needle))
                for hidden in ("Guardian", "guardianjet", "2026-10-18"):
                    self.assertNotIn(hidden, txt, (aid, hidden))

    def test_alias_quick_find_in_app(self):
        st, app_ = self.S.run({"Quick find (model or alias, e.g. Global 7000)": ""})
        app_.st.session_state["ac_search"] = "Global 7000"
        app_._on_search()
        self.assertEqual(app_.st.session_state["ac_sel"], "bombardier_global_7500")
        self.assertIn("former program name", app_.st.session_state["ac_search_note"])

    def test_fleet_table_lists_web_but_flags_source(self):
        comp = E.fleet_comparison(BASE, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=300.0))
        self.assertEqual(int((comp.source_kind == "web_estimate").sum()), 2)
        self.assertEqual(int((comp.source_kind == "pdf_acc").sum()), 144)


class TestMenkorBase(unittest.TestCase):
    """Menkor cost base: the +15 % on maintenance & programs, airport fees, crew training and hangar is stored IN THE DATA (Global recurrent training
    120 000 USD = 2 pilots x 60 000). The engine adjusts nothing; Report reference reads the original__ values."""

    def comp(self, res, key):
        return next(c for c in res["components"] if c["key"] == key)

    def arow(self, aid): return ADJ[ADJ.aircraft_id == aid].iloc[0]

    def test_no_adjustment_machinery_left_in_the_engine_or_the_screens(self):
        for name in ("adjust_row", "adjustment_text", "ACTUALISE_DEFAULT", "INFLATION_PCT_DEFAULT", "recurrent_training_override"):
            self.assertFalse(hasattr(E, name), name)
        self.assertFalse(hasattr(E.Scenario("dassault_falcon_7x"), "actualise")); self.assertFalse(hasattr(E.Scenario("dassault_falcon_7x"), "inflation_pct"))
        src = read("app.py")
        for gone in ("Update base costs", "Adjustment (%)", "act_on", "infl_pct", "Menkor base update"):
            self.assertNotIn(gone, src, gone)

    def test_totals_components_add_up_and_reference_is_original(self):
        for aid in ("dassault_falcon_7x", "gulfstream_g450", "challenger_300", "bombardier_global_7500", "bombardier_global_6000"):
            r = self.arow(aid); h = E.num(r, "reference_annual_hours")
            sim_ = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=h))
            ref = E.compute(r, E.Scenario(aid, mode="reference"))
            self.assertAlmostEqual(sum(c["annual_usd"] for c in sim_["components"]), sim_["budget_usd"], delta=1.0)
            self.assertAlmostEqual(sum(c["annual_usd"] for c in ref["components"]), ref["budget_usd"], delta=1.0)
            self.assertEqual(ref["budget_usd"], E.num(r, "original__annual_budget_usd"), aid)
            self.assertEqual(sim_["menkor_base"]["published_budget_adjusted"], E.num(r, "annual_budget_usd"))
            self.assertGreater(sim_["budget_usd"], ref["budget_usd"] - 1.0)
            raw = E.compute(BASE[BASE.aircraft_id == aid].iloc[0], E.Scenario(aid, mode="simulation", billed_hours=h))
            for k in ("insurance", "crew_expense", "aircraft_misc", "fuel"):          # lines outside the adjustment are identical to the original ones
                if any(c["key"] == k for c in raw["components"]):
                    self.assertEqual(self.comp(sim_, k)["annual_usd"], self.comp(raw, k)["annual_usd"], (aid, k))

    def test_falcon_7x_listed_lines_are_stored_plus_15_percent(self):
        r = self.arow("dassault_falcon_7x"); h = E.num(r, "reference_annual_hours")
        sim_ = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=h))
        ref = E.compute(r, E.Scenario("dassault_falcon_7x", mode="reference"))
        for k in ("hangar", "crew_training", "airframe_maint", "engine_apu_maint", "airport_fees"):
            self.assertAlmostEqual(self.comp(sim_, k)["annual_usd"], self.comp(ref, k)["annual_usd"] * 1.15, delta=0.5, msg=k)
        mb = sim_["menkor_base"]; self.assertTrue(mb["applied"]); self.assertEqual(mb["pct"], 15.0); self.assertEqual(mb["status"], "adjusted_documented")
        self.assertFalse(ref["menkor_base"]["applied"])

    def test_global_recurrent_training_is_120k_in_the_base_and_original_in_reference(self):
        for aid in ("bombardier_global_5000", "bombardier_global_express", "bombardier_global_express_xrs"):
            r = self.arow(aid); h = E.num(r, "reference_annual_hours")
            sim_ = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=h))
            self.assertEqual(self.comp(sim_, "crew_training")["annual_usd"], 2 * 60000.0, aid)
            self.assertEqual(E.num(r, "menkor_training_override_usd"), 120000.0)
            ref = E.compute(r, E.Scenario(aid, mode="reference"))
            self.assertEqual(self.comp(ref, "crew_training")["annual_usd"], E.num(r, "original__annual_crew_training_fixed_usd"), aid)
        self.assertTrue(pd.isna(self.arow("dassault_falcon_7x")["menkor_training_override_usd"]))

    def test_web_globals_missing_lines_stay_missing(self):
        r = self.arow("bombardier_global_7500"); h = E.num(r, "reference_annual_hours")
        upd = E.compute(r, E.Scenario("bombardier_global_7500", mode="simulation", billed_hours=h))
        its = {i["item"]: i for i in upd["menkor_base"]["items"]}
        self.assertIsNone(its["Crew training"]["before"]); self.assertIsNone(its["Handling & en-route / airport fees"]["before"])
        self.assertIn("not available", its["Crew training"]["note"])
        self.assertFalse([c for c in upd["components"] if c["key"] == "crew_training"])        # no invented training line
        raw = E.compute(BASE[BASE.aircraft_id == "bombardier_global_7500"].iloc[0], E.Scenario("bombardier_global_7500", mode="simulation", billed_hours=h))
        self.assertAlmostEqual(self.comp(upd, "maintenance_total")["annual_usd"], self.comp(raw, "maintenance_total")["annual_usd"] * 1.15, delta=0.5)
        self.assertEqual(r["menkor_adjustment_status"], "adjusted_partial_web")

    def test_user_edit_replaces_base_value(self):
        r = self.arow("dassault_falcon_7x"); h = E.num(r, "reference_annual_hours")
        base = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=h))
        hg = self.comp(base, "hangar")["annual_usd"]
        ed = E.compute(r, E.Scenario("dassault_falcon_7x", mode="simulation", billed_hours=h, fixed_overrides={"hangar": 100000.0}))
        self.assertAlmostEqual(self.comp(ed, "hangar")["annual_usd"], 100000.0, delta=0.01)
        self.assertAlmostEqual(ed["budget_usd"] - base["budget_usd"], 100000.0 - hg, delta=0.01)

    def test_historical_sheets_have_no_adjustment_and_no_original_values(self):
        leg = ADJ[~ADJ.has_detail].iloc[0]
        x = E.compute(leg, E.Scenario(leg["aircraft_id"], mode="simulation", billed_hours=300.0))
        self.assertFalse(x["menkor_base"]["applied"]); self.assertEqual(str(leg["menkor_adjustment_status"]), "unchanged_historical_no_breakdown")
        self.assertEqual(int(ADJ[~ADJ.has_detail]["menkor_adjustment_applied"].astype(str).str.lower().eq("true").sum()), 0)

    def test_no_acc_wording_for_users_and_menkor_source_shown(self):
        import smoke_support
        smoke_support.run({})
        import menkor_report
        for aid in ("dassault_falcon_7x", "bombardier_global_7500"):
            r = ADJ[ADJ.aircraft_id == aid].iloc[0]
            res = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0))
            texts = [f["text"] for f in res["flags"]] + [a["text"] for a in E.alerts_for(r, CHECKS, CONFLICTS, CONVS)] + [E.STATUS_TEXT.get(str(r["record_status"]), "")]
            csv = sys.modules["app"]._results_csv(res, E.Display(E.Fx("USD", None, None))).decode("utf-8-sig")
            pdf = menkor_report.build_report_pdf(res, E.Display(E.Fx("USD", None, None)), E.alerts_for(r, CHECKS, CONFLICTS, CONVS))
            with tempfile.TemporaryDirectory() as d:
                pth = os.path.join(d, "r.pdf"); open(pth, "wb").write(pdf)
                txt = subprocess.run(["pdftotext", "-layout", pth, "-"], capture_output=True, text=True).stdout if shutil.which("pdftotext") else ""
            prov_src = " ".join(str(x) for x in sys.modules["app"]._prov_table(r, PROV)["Source"])
            for blob in texts + [csv, txt, prov_src]:
                self.assertNotRegex(blob, r"\bACC\b|Aircraft Cost Calculator", aid)
            for hidden in ("extraction_date", "source_file", "aircraft_id"):
                self.assertNotIn(hidden, csv)
            if txt:
                self.assertIn("Menkor cost base", txt)

    def test_screens_run_with_toggle_on_and_off(self):
        import smoke_support
        for aid in ("dassault_falcon_7x", "bombardier_global_5000", "bombardier_global_6000"):
            for on in (True, False):
                st, app_ = smoke_support.run({"Aircraft model": aid, "Update base costs (adjustment scenario)": on})
                self.assertTrue([1 for k, a, kw in st.log if k == "metric"], (aid, on))


class TestCharterEstimate(unittest.TestCase):
    """Historical per-model indicative price file: kept as DATA only (never injected into the calculations, the screens, the PDF or the CSV)."""

    @classmethod
    def setUpClass(cls):
        cls.P = E.load_charter_prices()

    def test_file_complete_and_consistent(self):
        P = self.P
        self.assertEqual(len(P), 167); self.assertEqual(set(P.aircraft_id), set(BASE.aircraft_id)); self.assertEqual(P.aircraft_id.duplicated().sum(), 0)
        for aid in P.aircraft_id:
            e = E.charter_estimate(aid, P)
            if e["available"]:
                self.assertGreater(e["reference"], 0, aid)
                if e["low"] and e["high"]: self.assertTrue(e["low"] <= e["reference"] <= e["high"], aid)
                self.assertIn(e["currency"], ("USD", "EUR"))

    def test_unavailable_models_never_zero_nor_other_model(self):
        un = [a for a in self.P.aircraft_id if not E.charter_estimate(a, self.P)["available"]]
        self.assertEqual(len(un), 19)
        for a in un:
            e = E.charter_estimate(a, self.P)
            self.assertFalse(e["auto_prefill"]); self.assertIsNone(e["reference"] or None); self.assertEqual(e["action"], "manual_quote_required")
        self.assertIsNone(E.charter_estimate("unknown_model", self.P))

    def test_auto_prefill_follows_the_file(self):
        n = sum(E.charter_estimate(a, self.P)["auto_prefill"] for a in self.P.aircraft_id)
        self.assertEqual(n, 117)
        for aid in ("airbus_acj319neo", "learjet_36a"): self.assertFalse(E.charter_estimate(aid, self.P)["auto_prefill"])
        e = E.charter_estimate("dassault_falcon_7x", self.P)
        self.assertEqual((e["reference"], e["currency"], e["scope"], e["auto_prefill"]), (13000.0, "USD", "exact_model", True))
        self.assertEqual(E.charter_estimate("iai_astra_sp", self.P)["alt_reference"], 3500.0)

    def test_eur_rate_entered_by_the_user_needs_a_dated_rate(self):
        aid = "airbus_340"; r = row(aid)
        sc = dict(aircraft_id=aid, mode="simulation", billed_hours=300.0, charter_rate=19000.0, charter_rate_ccy="EUR")
        no_fx = E.compute(r, E.Scenario(**sc))
        self.assertFalse(no_fx["profit"]["available"]); self.assertIn("EUR", " ".join(no_fx["profit"]["messages"]))
        with_fx = E.compute(r, E.Scenario(**sc, fx=E.Fx("USD", 0.92, "2026-10-18")))
        self.assertTrue(with_fx["profit"]["available"]); self.assertAlmostEqual(with_fx["rate_usd"], 19000.0 / 0.92, places=6)

    def test_disclaimers_say_estimate(self):
        txt = " ".join(E.charter_disclaimers(E.charter_estimate("airbus_319", self.P))).lower()
        for w in ("estimate", "not a menkor quotation", "operator", "billable flight hour"): self.assertIn(w, txt)
        px = " ".join(E.charter_disclaimers(E.charter_estimate("learjet_36a", self.P))).lower()
        self.assertIn("confidence", px)

    def test_hash_differs_by_rate_basis(self):
        a = E.Scenario("airbus_319", charter_rate=13143.0, rate_basis="gross").config_hash()
        b = E.Scenario("airbus_319", charter_rate=13143.0, rate_basis="net").config_hash()
        self.assertNotEqual(a, b)

    def _txt(self, st):
        return " ".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "info"))

    def test_no_automatic_charter_price_anywhere(self):
        """The historical estimate file stays on disk but is never injected: empty rate field, no suggestion, no revenue, no threshold."""
        import smoke_support
        for aid in ("airbus_319", "dassault_falcon_7x", "learjet_36a", "airbus_318"):
            st, _ = smoke_support.run({"Aircraft model": aid, "Calculation mode": "Custom simulation"})
            t = self._txt(st); labels = [l for _, l, _, _ in st.widgets]
            self.assertNotIn("Menkor estimate", t); self.assertNotIn("Charter rate to use", labels); self.assertNotIn("Use historical rate", labels)
            self.assertNotIn("Charter price estimate", t)
            self.assertIn("Enter your expected charter revenue per billed hour to run this simulation.", t)
            self.assertFalse([1 for k, a, kw in st.log if k == "metric" and a[0] in ("💵 Charter revenue", "📊 Estimated operating result")])
        src = read("app.py")
        for gone in ("charter_estimate(", "_RS_REF", "estimate_ref", "Menkor estimate", "legacy_Taux_Charter_EUR_h"): self.assertNotIn(gone, src)

    def test_pdf_and_csv_never_carry_an_estimate(self):
        import smoke_support, menkor_report
        smoke_support.run({})
        aid = "airbus_319"; r = row(aid)
        res = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=300.0, charter_rate=13143.0, charter_rate_ccy="USD", positioning_confirmed=True, private_hours_confirmed=True, other_fees_confirmed=True, limits_reviewed=True))
        disp = E.Display(E.Fx("USD"))
        csv = sys.modules["app"]._results_csv(res, disp).decode("utf-8-sig")
        self.assertNotIn("charter_rate_source", csv); self.assertNotIn("estimate_ref", csv); self.assertIn("charter_rate_basis,before commission (gross)", csv)
        pdf = menkor_report.build_report_pdf(res, disp, [])
        with tempfile.TemporaryDirectory() as d:
            pth = os.path.join(d, "r.pdf"); open(pth, "wb").write(pdf)
            txt = subprocess.run(["pdftotext", "-layout", pth, "-"], capture_output=True, text=True).stdout
        self.assertNotIn("ESTIMATE from", txt); self.assertNotIn("indicative charter price file", " ".join(txt.split()))

    def test_no_acc_leak_in_charter_data(self):
        blob = " ".join(map(str, self.P.values.ravel())).lower()
        for w in ("aircraftcostcalculator", "acc cost", "pdf_acc"): self.assertNotIn(w, blob)

    def test_listing_never_shows_raw_source_codes(self):
        import smoke_support
        st, app_ = smoke_support.run({"Aircraft model": "dassault_falcon_7x", "Calculation mode": "Custom simulation"})
        frames = [a[0] for k, a, kw in st.log if k == "dataframe" and hasattr(a[0], "columns")]
        for f in frames:
            blob = " ".join(map(str, f.columns)) + " " + " ".join(map(str, f.astype(str).values.ravel()))
            self.assertNotIn("pdf_acc", blob); self.assertNotIn("web_estimate", blob); self.assertNotIn("source_kind", blob)


if __name__ == "__main__":
    unittest.main(verbosity=2)
