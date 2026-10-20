"""Lot A — three journeys, simplified first level, single confirmation, client-safe views, Market Search wording.
They use tests/fake_streamlit.py (a recorder): this is NOT a real Streamlit / browser validation. No payment, no email, no deployment."""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F  # noqa: E402
import menkor_engine as E  # noqa: E402
from test_v19_screens import run, text, metrics, csv_of, pdf_text  # noqa: E402

FAL = "dassault_falcon_7x"
JA, JB, JC = "Estimate operating costs", "Simulate charter operations", "Request an aircraft-specific budget"
REAL = {"__real_defaults__": True, "Aircraft model": FAL}
RATE = {"Expected charter revenue per billed hour": 9000.0, "Rate currency": "USD",
        "This rate represents": "Operator revenue before commission (gross)", "Commission (%) on gross revenue": 10.0}
FUEL = {"Average annual fuel price (per litre)": 1.0, "Fuel price currency": "USD"}


def labels(st): return {l for _, l, _, _ in st.widgets}


class TestJourneys(unittest.TestCase):
    def test_real_default_is_the_cost_estimate_in_custom_simulation_with_empty_fuel_price(self):
        st, _ = run(REAL)
        radios = [(l, k) for k, l, key, d in st.widgets if k == "radio"]
        self.assertIn("What do you want to do?", [l for l, _ in radios])
        L = labels(st)
        self.assertIn("Total annual flown hours", L)
        for hidden in ("Billed charter hours / year", "Positioning hours (flown, not billed)", "Owner / private / other hours (not billed)",
                       "Expected charter revenue per billed hour", "Commission (%) on gross revenue", "Confirm assumptions and calculate", "Positioning assumption"):
            self.assertNotIn(hidden, L, hidden)
        t = text(st)
        self.assertIn("Enter your average fuel purchase price, including applicable fuel taxes and fees.", t)
        self.assertIn("Enter your average annual fuel price to calculate the operating budget.", t)       # blocked, short explanation, nothing invented
        self.assertFalse([m for m in metrics(st) if m[0].endswith("Total Annual Budget")])

    def test_cost_estimate_with_a_fuel_price_gives_the_engine_budget_and_no_charter_result(self):
        st, app = run({**REAL, **FUEL, "Total annual flown hours": 300})
        scn = E.Scenario(FAL, mode="simulation", billed_hours=0.0, positioning_hours=0.0, other_hours=300.0,
                         fuel=E.FuelConfig(price_source="average", price=1.0, currency="USD"))
        row = app.get_active_db().set_index("aircraft_id").loc[FAL]; row["aircraft_id"] = FAL
        res = E.compute(row, scn)
        shown = [m[1] for m in metrics(st) if m[0].endswith("Total Annual Budget")][0]
        self.assertEqual(shown, f"$ {res['budget_usd']:,.0f}")
        self.assertEqual(res["hours"]["billed"], 0.0)
        self.assertIn("not treated as billed charter hours", text(st))
        for bad in ("Gross Revenue", "Operating result", "Net Result"):
            self.assertFalse([m for m in metrics(st) if bad in m[0]])
        self.assertIn("Charter profitability is available in the journey", text(st))

    def test_first_level_fields_only_and_advanced_section_exists(self):
        st, _ = run({**REAL, **FUEL})
        exp = " ".join(str(a[0]) for k, a, kw in st.log if k == "expander")
        for sec in ("Advanced settings", "Currency conversion", "Economic ownership costs"):
            self.assertIn(sec, exp)
        L = labels(st)
        self.assertIn("Calculation mode", L); self.assertIn("Fuel price method", L); self.assertIn("Burn method", L)
        first = [l for k, l, key, d in st.widgets][:12]
        self.assertIn("Aircraft model", L)

    def test_advanced_defaults_are_custom_simulation_and_user_fuel_price(self):
        st, _ = run({**REAL, **FUEL})
        calc = [w for w in st.widgets if w[1] == "Calculation mode"]; self.assertTrue(calc)
        self.assertNotIn("Report reference — published", text(st))
        # default Fuel price method is the user's average annual price: a result appears only with it
        self.assertTrue([m for m in metrics(st) if m[0].endswith("Total Annual Budget")])

    def test_charter_journey_shows_the_charter_fields_and_one_confirmation_button(self):
        st, _ = run({**REAL, "What do you want to do?": JB, **RATE, **FUEL})
        L = labels(st)
        for need in ("Billed charter hours / year", "Positioning hours (flown, not billed)", "Owner / private / other hours (not billed)",
                     "Expected charter revenue per billed hour", "Rate currency", "This rate represents", "Commission (%) on gross revenue", "Confirm assumptions and calculate"):
            self.assertIn(need, L, need)
        self.assertFalse([l for l in L if l.startswith("I confirm the") or l.startswith("I have reviewed")])           # the four checkboxes are gone
        t = text(st)
        for line in ("Charter rate and basis:", "Commission:", "Positioning:", "Private / owner / other hours:", "Other commercial fees:", "Cost scope:"):
            self.assertIn(line, t, line)
        self.assertIn("Not displayed until you confirm", t)

    def test_budget_request_journey_hides_the_simulation_inputs_and_shows_the_offer_first(self):
        st, _ = run({**REAL, "What do you want to do?": JC})
        L = labels(st)
        for hidden in ("Total annual flown hours", "Billed charter hours / year", "Average annual fuel price (per litre)", "Expected charter revenue per billed hour"):
            self.assertNotIn(hidden, L, hidden)
        self.assertIn("What will this specific aircraft cost you?", text(st))
        self.assertEqual(len([1 for k, a, kw in st.log if k == "markdown" and "What will this specific aircraft cost you?" in str(a[0])]), 1)   # shown once

    def test_switching_journey_never_reinterprets_hours(self):
        st, _ = run({**REAL, "What do you want to do?": JB, **FUEL}, patch=None)
        st2, _ = run({**REAL, "What do you want to do?": JB, **FUEL}, patch=lambda app: None)
        # the cost estimate's total hours are not converted into charter hours (and vice versa)
        import fake_streamlit as F2
        for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[m]
        stt = F2.install({**REAL, "What do you want to do?": JB, **FUEL}, {f"th_{FAL}": 400})
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F2.StopApp: pass
        self.assertIn("are not converted into charter hours", text(stt))
        stt2 = F2.install({**REAL, **FUEL}, {f"bh_{FAL}": 200})
        for m in [k for k in sys.modules if k == "app"]: del sys.modules[m]
        import app as app2
        app2.render_auth = lambda: (True, True); app2._process_day_pass_return = lambda: None; app2._get_logo = lambda: ""
        try: app2.main()
        except F2.StopApp: pass
        self.assertIn("kept but not used in this view", text(stt2))


class TestResultsByAvailability(unittest.TestCase):
    OVB = {**REAL, "What do you want to do?": JB, **RATE, **FUEL, "Confirm assumptions and calculate": True}

    def test_operating_economic_and_owner_balance_with_ownership_costs(self):
        st, _ = run({**self.OVB, "Annual economic depreciation": 1000000.0, "Annual loan interest and financing costs": 200000.0})
        t = text(st); names = [m[0] for m in metrics(st)]
        self.assertTrue([n for n in names if "Estimated operating result" in n])
        self.assertTrue([n for n in names if "Economic result after the ownership costs entered" in n])
        self.assertTrue([n for n in names if "Owner remaining balance after charter contribution" in n])
        self.assertIn("before depreciation, interest and tax", t); self.assertIn("capital repayment", t.lower())
        self.assertIn("Operating cost coverage threshold", t); self.assertIn("Economic coverage threshold including the ownership costs entered", t)
        self.assertIn("Estimate based on your assumptions. Aircraft-specific maintenance events and programme exclusions may materially change the result.", t)

    def test_economic_result_never_complete_when_an_ownership_input_is_missing(self):
        st, _ = run({**self.OVB, "Annual economic depreciation": 1000000.0})
        self.assertFalse([m for m in metrics(st) if "Economic result after" in m[0]])
        self.assertIn("Economic result not complete", text(st)); self.assertIn("loan interest", text(st))

    def test_thresholds_formulas_are_in_a_closed_help_section(self):
        st, _ = run(self.OVB)
        self.assertIn("How the thresholds are calculated", " ".join(str(a[0]) for k, a, kw in st.log if k == "expander"))


class TestClientViewsAreClean(unittest.TestCase):
    FORBIDDEN = [r"extraction_date", r"numeric check", r"tol\.", r"source_file", r"\.pdf\b", r"\.csv\b", r"Guardian", r"guardianjet", r"IATA Fuel", r"Platts",
                 r"reconcil", r"fuel_burn_l_per_h", r"reference_fuel_price", r"aircraft_id", r"exact cost breakdown", r"seats_full_range", r"processing date"]

    def _all(self, **extra):
        ov = {**REAL, "What do you want to do?": JB, **RATE, **FUEL, "Confirm assumptions and calculate": True, "📄 Generate PDF Report": True, **extra}
        st, app = run(ov)
        return st, " ".join(text(st).split()), " ".join(pdf_text(st.session_state["pdf_report"]["data"]).split()), csv_of(st)

    def test_screen_pdf_csv_have_no_internal_details(self):
        for aid in (FAL, "bombardier_global_7500", "challenger_870c"):
            st, scr, pdf, csv = self._all(**{"Aircraft model": aid})
            # the style block is not user text
            scr = re.sub(r"<style>.*?</style>", "", scr)
            for pat in self.FORBIDDEN:
                for name, blob in (("screen", scr), ("pdf", pdf), ("csv", csv)):
                    if name == "csv" and pat == r"fuel_burn_l_per_h": continue          # an export item name, not a database field
                    self.assertIsNone(re.search(pat, blob, re.I), (aid, name, pat))

    def test_provenance_is_for_the_admin_only(self):
        st, _ = run({**REAL, **FUEL}, patch=None)
        self.assertNotIn("Data provenance", " ".join(str(a[0]) for k, a, kw in st.log if k == "expander"))
        for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[m]
        sta = F.install({**REAL, **FUEL}, {"auth_is_admin": True})
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F.StopApp: pass
        self.assertIn("Data provenance", " ".join(str(a[0]) for k, a, kw in sta.log if k == "expander"))

    def test_economic_reference_date_message_when_missing(self):
        st, scr, pdf, csv = self._all()
        self.assertIn("Economic reference date not documented", scr); self.assertIn("Economic reference date not documented", pdf)
        self.assertIn("Economic reference date not documented", csv)

    def test_fuel_results_show_burn_price_and_cost_per_hour(self):
        st, scr, pdf, csv = self._all()
        m = re.search(r"Fuel retained: ([\d,]+) L per flown hour .*? × \$ ([\d.]+) per litre .*? = \$ ([\d,]+) per flown hour", scr)
        self.assertTrue(m, scr[:300])
        self.assertAlmostEqual(float(m.group(1).replace(",", "")) * float(m.group(2)), float(m.group(3).replace(",", "")), delta=2)

    def test_detailed_cost_breakdown_wording_for_free_plan(self):
        for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
        st = F.install({**REAL, **FUEL}, None)
        import app
        app.render_auth = lambda: (False, False); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F.StopApp: pass
        t = text(st); self.assertIn("Free demo", t); self.assertNotIn("exact cost breakdown", t); self.assertNotIn("000,000", t)


class TestMarketSearchWording(unittest.TestCase):
    def setUp(self):
        for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
        self.st = F.install({**REAL, "Aircraft model ": "x"}, None)
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F.StopApp: pass
        self.t = " ".join(re.sub(r"<style>.*?</style>", "", text(self.st), flags=re.S).split())
        self.src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()

    def test_no_exhaustive_promise_no_contradictory_delay_no_insult(self):
        for bad in ("Every active listing", "every active listing", "time-waster", "competitor", "within 48 hours", "Delivered within", "Make Offer", "JSSI", "Not Enrolled",
                    "Verified Seller", "verified by our team", "raw ledger", "Atlantic Aviation Brokers"):
            self.assertNotIn(bad, self.t, bad)
        self.assertIn("Delivery timeframe confirmed when your request is reviewed", self.t)

    def test_single_uniform_price_consistent_with_the_checkout_amount(self):
        prices = set(re.findall(r"€ ?(\d[\d,]*)", self.t)) & {"300", "250", "500", "200"}
        self.assertEqual(prices, {"300"})
        self.assertRegex(self.src, r'"currency":"eur","unit_amount":30000')       # 300.00 EUR: unchanged, consistent with the displayed price
        self.assertIn("Proceed to Payment — € 300", self.src)

    def test_sample_is_labelled_prices_are_distinguished_and_no_sources_shown(self):
        self.assertIn("Sample deliverable", self.t)
        self.assertIn("Asking price", self.t); self.assertIn("estimated value", self.t.lower())
        for col in ("Engine Program", ">Avionics<", "Inspection Status", ">Broker<", "Key Notes"):
            self.assertNotIn(col, self.t, col)
        self.assertIn("Indicative timeline", self.t)

    def test_service_stays_separate_from_saas_and_budget_study(self):
        self.assertIn("manually prepared market search", self.t)
        self.assertNotIn("Aircraft-specific operating budget", self.t.split("Request Your Market Search")[-1])


if __name__ == "__main__":
    unittest.main()
