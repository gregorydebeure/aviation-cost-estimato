"""
Simplified fuel path: ONE average price per litre + currency ("Average fuel price — annual planning assumption").
The dated local quote (airport, supplier, taxes, fees, validity, expired-price confirmation) lives in a separate ADVANCED module.
Screens are exercised with tests/fake_streamlit.py (a recorder, NOT Streamlit).
"""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_engine as E  # noqa: E402
import menkor_report as RPT  # noqa: E402
from test_v17_fixes import row, sim, fuel, pdf_text, FAL, TODAY, CHECKS, CONFLICTS, CONVS  # noqa: E402

AVG_SRC = "My average annual fuel price"
ADV = "Use a detailed local quote instead of the fuel price source above"
FX = E.Fx("EUR", 0.92, "2026-10-18", "test")


def avg(price=2.0, ccy="USD", **k):
    return E.FuelConfig(price_source="average", price=price, currency=ccy, **k)


def codes(r): return [f["code"] for f in r["flags"]]


class TestAverageEngine(unittest.TestCase):
    def test_average_price_is_used_without_any_validity_logic(self):
        r = sim(fuel=avg(2.0))
        self.assertTrue(r["available"]); self.assertIsNone(r["fuel_validity"])
        self.assertAlmostEqual(r["fuel"]["price_usd_l"], 2.0); self.assertEqual(r["fuel"]["price_source"], "average")
        self.assertIn("fuel_average_assumption", codes(r))
        self.assertFalse([c for c in codes(r) if c.startswith("fuel_validity") or c.startswith("fuel_price_expired") or c == "fuel_date_invalid"])
        self.assertIsNone(r["fuel"]["local"]); self.assertEqual(r["fuel"]["average"]["currency"], "USD")

    def test_stale_advanced_fields_never_interfere_with_the_average_path(self):
        # an old date / confirmation left in the config must not block or change an average-price simulation
        a = sim(fuel=avg(2.0))
        b = sim(fuel=avg(2.0, validity_date="2001-01-01", taxes_pct=25.0, fees_per_uplift=900.0, airport_icao="LFPB", supplier="X", expired_confirmation="zz"))
        self.assertTrue(b["available"]); self.assertEqual(a["budget_usd"], b["budget_usd"]); self.assertIsNone(b["fuel_validity"])

    def test_same_budget_as_an_equivalent_advanced_quote(self):
        m = sim(fuel=fuel(price=2.0, d="2026-12-31"))
        self.assertEqual(sim(fuel=avg(2.0))["budget_usd"], m["budget_usd"])

    def test_fuel_cost_follows_burn_times_average_price_in_litres(self):
        r = sim(fuel=avg(2.5)); f = r["fuel"]
        self.assertAlmostEqual(f["fuel_per_h_usd"], f["burn_l_h"] * 2.5); self.assertAlmostEqual(f["annual_cost_usd"], r["hours"]["flown"] * f["burn_l_h"] * 2.5)
        self.assertAlmostEqual(f["annual_usg"], f["annual_litres"] / E.USG_TO_L)

    def test_eur_average_needs_a_dated_rate_and_converts(self):
        r = sim(fuel=avg(1.84, "EUR"), fx=FX); self.assertTrue(r["available"])
        self.assertAlmostEqual(r["fuel"]["price_usd_l"], 1.84 / 0.92); self.assertEqual(r["fuel"]["average"]["fx_date"], "2026-10-18")
        r = sim(fuel=avg(1.84, "EUR"))                       # no rate: error, never an invented rate or a zero
        self.assertFalse(r["available"]); self.assertIn("price_average", codes(r))
        r = sim(fuel=avg(1.84, "EUR"), fx=E.Fx("EUR", 0.92, "31/12/2026"))
        self.assertFalse(r["available"])

    def test_missing_or_zero_price_is_an_error_not_zero(self):
        for p in (None, 0.0, -1.0):
            r = sim(fuel=avg(p)); self.assertFalse(r["available"]); self.assertIn("price_average", codes(r)); self.assertIsNone(r["budget_usd"])

    def test_currency_conversions_helpers_are_preserved(self):
        fx = E.Fx("EUR", 0.9, "2026-01-01")
        p, _ = E.manual_price_usd_per_l(E.FuelConfig(price_source="manual", price=4.25, unit="USG", currency="USD"), fx)
        self.assertAlmostEqual(p, 4.25 / E.USG_TO_L)
        p, _ = E.average_price_usd_per_l(avg(0.9, "EUR"), fx); self.assertAlmostEqual(p, 1.0)
        p, err = E.average_price_usd_per_l(avg(0.9, "EUR"), E.Fx()); self.assertIsNone(p); self.assertTrue(err)

    def test_report_reference_is_untouched_by_any_fuel_configuration(self):
        base = E.compute(row(FAL), E.Scenario(FAL, mode="reference"), today=TODAY)
        for fc in (avg(9.0), avg(1.0, "EUR"), fuel(price=9.0, d="2000-01-01")):
            r = E.compute(row(FAL), E.Scenario(FAL, mode="reference", fuel=fc), today=TODAY)
            self.assertEqual((r["budget_usd"], r["fixed"]["annual_total"], r["config_hash"]), (base["budget_usd"], base["fixed"]["annual_total"], base["config_hash"]))
        self.assertEqual(round(base["budget_usd"]), 1637042); self.assertEqual(round(base["fixed"]["annual_total"]), 588918)

    def test_sensitivity_uses_the_average_path_and_cannot_be_blocked_by_an_expired_quote(self):
        scn = E.Scenario(FAL, mode="simulation", billed_hours=350.0, fuel=fuel(price=2.0, d="2000-01-01"))
        pts = E.sensitivity_fuel_price(row(FAL), scn, [1.0, 2.0, 3.0])
        self.assertTrue(all(c is not None for _, c, _ in pts)); self.assertLess(pts[0][1], pts[2][1])

    def test_hash_changes_with_average_price_and_currency(self):
        h = lambda f, fx=None: sim(fuel=f, **({"fx": fx} if fx else {}))["config_hash"]
        self.assertEqual(h(avg(2.0)), h(avg(2.0)))
        self.assertNotEqual(h(avg(2.0)), h(avg(2.1))); self.assertNotEqual(h(avg(2.0, "EUR"), FX), h(avg(2.0), FX))


class TestAverageScreens(unittest.TestCase):
    def run_app(self, ov=None, **kw):
        import smoke_support
        return smoke_support.run(ov or {}, **kw)

    def text(self, st):
        return " ".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "error", "info", "success", "expander"))

    def metric(self, st, label):
        return next(v for k, a, kw in st.log if k == "metric" and a[0].endswith(label) for v in [a[1]])

    OV = {"Aircraft model": FAL, "Calculation mode": "Custom simulation", "Fuel price method": AVG_SRC, "Average annual fuel price (per litre)": 2.0}

    def labels(self, st): return {l for _, l, _, _ in st.widgets}

    def test_new_title_and_wording_replace_the_old_section(self):
        st, _ = self.run_app(self.OV); t = self.text(st)
        self.assertIn("Enter your average fuel purchase price, including applicable fuel taxes and fees.", t)
        self.assertIn("Average annual fuel price (per litre)", self.labels(st))
        self.assertNotIn("Local fuel price", t); self.assertNotIn("Local fuel price — manual entry", open(os.path.join(ROOT, "app.py"), encoding="utf-8").read())

    def test_default_path_has_only_price_and_currency(self):
        st, _ = self.run_app(self.OV); L = self.labels(st)
        self.assertTrue({"Average annual fuel price (per litre)", "Fuel price currency"} <= L)
        for gone in ("Airport ICAO", "Airport IATA", "Supplier", "Fees per uplift (fixed)", "Quote valid until (YYYY-MM-DD)", "Price",
                     "I confirm: use this expired price as a HISTORICAL assumption"):
            self.assertNotIn(gone, L, gone)
        self.assertTrue(self.metric(st, "Total Annual Budget"))

    def test_advanced_module_is_separate_and_keeps_the_old_functions(self):
        st, _ = self.run_app(self.OV); self.assertIn(ADV, self.labels(st))
        st, _ = self.run_app({**self.OV, ADV: True, "Price": 2.0, "Quote valid until (YYYY-MM-DD)": "2020-01-01"}); L = self.labels(st)
        for there in ("Airport ICAO", "Airport IATA", "Supplier", "Fees per uplift (fixed)", "Quote valid until (YYYY-MM-DD)", "Price",
                      "I confirm: use this expired price as a HISTORICAL assumption"):
            self.assertIn(there, L, there)
        self.assertIn("EXPIRED", self.text(st))

    def test_expired_quote_logic_never_shows_in_the_average_path(self):
        st, _ = self.run_app({**self.OV, "Quote valid until (YYYY-MM-DD)": "2000-01-01"})
        self.assertNotIn("EXPIRED", self.text(st)); self.assertNotIn("HISTORICAL", self.text(st))

    def test_missing_average_price_warns_and_blocks(self):
        st, _ = self.run_app({**self.OV, "Average annual fuel price (per litre)": 0.0})
        self.assertIn("Enter your average annual fuel price", self.text(st))
        self.assertFalse([1 for k, a, kw in st.log if k == "metric" and "Total Annual Budget" in a[0]])

    def test_report_reference_disables_the_average_controls_and_shows_original(self):
        st, _ = self.run_app({**self.OV, "Calculation mode": "Report reference", "Average annual fuel price (per litre)": 9.0})
        self.assertEqual(self.metric(st, "Total Annual Budget"), "$ 1,637,042")
        dis = {l: d for _, l, _, d in st.widgets}
        self.assertTrue(dis["Average annual fuel price (per litre)"] and dis["Fuel price currency"] and dis["Fuel price method"] and dis[ADV])

    def test_eur_currency_and_display_conversion(self):
        ov = {**self.OV, "Fuel price currency": "EUR", "Average annual fuel price (per litre)": 1.84, "Display currency": "EUR",
              "EUR for 1 USD": 0.92, "Rate date (YYYY-MM-DD)": "2026-10-18"}
        st, _ = self.run_app(ov); self.assertTrue(self.metric(st, "Total Annual Budget").startswith("€"))
        st, _ = self.run_app({**ov, "EUR for 1 USD": 0.0})
        self.assertIn("exchange rate", self.text(st).lower())

    def test_screen_pdf_csv_agree_and_describe_a_user_average(self):
        st, _ = self.run_app({**self.OV, "📄 Generate PDF Report": True})
        screen = self.metric(st, "Total Annual Budget")
        csv = next(a[1] for k, a, kw in st.log if k == "download_button" and "CSV" in a[0]).decode("utf-8-sig")
        txt = pdf_text(st.session_state["pdf_report"]["data"])
        n = float(re.search(r"annual_budget_usd,([\d.]+)", csv).group(1)); self.assertEqual(f"$ {round(n):,}", screen); self.assertIn(screen, txt)
        for needle in ("fuel_price_source,average", "fuel_average_price_per_litre,2.0", "fuel_average_price_currency,USD", "fuel_price_nature,"):
            self.assertIn(needle, csv)
        self.assertNotIn("fuel_validity_status", csv)


class TestAveragePdf(unittest.TestCase):
    def build(self, fc, **kw):
        r = row(FAL); fx = kw.pop("fx", E.Fx("USD"))
        res = E.compute(r, E.Scenario(FAL, mode="simulation", billed_hours=350.0, fuel=fc, fx=fx, **kw), today=TODAY)
        return pdf_text(RPT.build_report_pdf(res, E.Display(fx), E.alerts_for(r, CHECKS, CONFLICTS, CONVS), generated_on=TODAY))

    def flat(self, t): return re.sub(r"\s+", " ", t)

    def test_pdf_presents_the_price_as_a_user_average_hypothesis(self):
        t = self.flat(self.build(avg(2.0)))
        for needle in ("average annual price of USD 2.000 per litre", "annual planning assumption", "includes the fuel taxes and fees that normally apply",
                       "user hypothesis, not a verified or real-time price", "Average price entered"):
            self.assertIn(needle, t, needle)
        low = t.lower()
        for bad in ("local fuel entry", "fuel price validity", "expired", "icao", "supplier", "live price", "real-time price is"):
            self.assertNotIn(bad, low, bad)
        # the only mention of "verified"/"real-time" is the explicit negation
        for m in re.finditer(r"verified local price|real-time price", t): self.assertIn("not a " + m.group(0), t)
        self.assertNotRegex(t, r"(?<!not a )(?<!not an )verified local price")

    def test_pdf_eur_average_shows_the_conversion(self):
        t = self.flat(self.build(avg(1.84, "EUR"), fx=FX))
        self.assertIn("EUR 1.840 per litre", t); self.assertIn("converted at", t); self.assertIn("0.92 EUR per 1 USD (rate dated 2026-10-18)", t)

    def test_reference_pdf_has_no_average_wording(self):
        r = row(FAL); res = E.compute(r, E.Scenario(FAL, mode="reference"), today=TODAY)
        t = self.flat(pdf_text(RPT.build_report_pdf(res, E.Display(E.Fx("USD")), [], generated_on=TODAY)))
        self.assertNotIn("average price of", t); self.assertIn("1,637,042", t)

    def test_advanced_quote_pdf_still_documents_its_validity(self):
        t = self.flat(self.build(fuel(price=2.0, d="2020-01-01", confirm=True)))
        self.assertIn("EXPIRED", t); self.assertIn("Local fuel entry", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
