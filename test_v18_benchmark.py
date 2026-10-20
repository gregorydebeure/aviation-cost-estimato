"""
Regional fuel benchmark (IATA/Platts, week ending 2026-10-09): separate table, USD/L conversion, replacement of the fuel line (no double count),
no +15 % on fuel, user adjustment, hours, missing data, screen/PDF/CSV coherence, PDF invalidation, independent Report reference.
Screens use tests/fake_streamlit.py (a recorder, NOT Streamlit).
"""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_engine as E  # noqa: E402
import menkor_report as RPT  # noqa: E402
from test_v17_fixes import row, raw_row, sim, pdf_text, FAL, TODAY, CHECKS, CONFLICTS, CONVS  # noqa: E402

G = 3.785411784
EXPECTED = {"europe_cis": 482.41, "north_america": 458.67, "asia_oceania": 417.70, "middle_east": 392.90, "africa": 467.95, "latin_america_caribbean": 449.49}
DISC = "Refinery market benchmark — not an into-wing price. Adjust the average price to reflect your fuel contracts, delivery charges and applicable non-recoverable taxes."
METHOD = "Regional market benchmark"


def bench(region="middle_east", price=None): return E.FuelConfig(price_source="benchmark", benchmark_region=region, price=price)
def codes(r): return [f["code"] for f in r["flags"]]
def flat(t): return re.sub(r"\s+", " ", t)


class TestTable(unittest.TestCase):
    def test_table_is_separate_and_complete(self):
        d = E.load_fuel_benchmarks(); self.assertEqual(len(d), 6)
        self.assertNotIn("price_us_cents_per_us_gallon", E.load_base().columns)
        for _, r in d.iterrows():
            self.assertEqual(r["price_us_cents_per_us_gallon"], EXPECTED[r["region_id"]])
            self.assertEqual((r["period_start"], r["period_end"]), ("2026-10-03", "2026-10-09"))
            self.assertTrue(r["source_url_1"].startswith("https://www.iata.org/en/publications/economics/fuel-monitor"))
            self.assertIn("fuel_price_analysis.jpg", r["source_url_2"]); self.assertIn("not an into-wing", r["price_nature"])
            self.assertIn("NOT cleared", r["licence_note"])

    def test_six_gallon_to_litre_conversions(self):
        d = E.load_fuel_benchmarks().set_index("region_id")
        for rid, cents in EXPECTED.items():
            self.assertAlmostEqual(d.loc[rid, "price_usd_per_l"], cents / 100 / G, places=12, msg=rid)
            self.assertAlmostEqual(E.usd_per_l_from_us_cents_per_usg(cents), cents / 100 / 3.785411784, places=12)
        self.assertEqual(f"{d.loc['middle_east','price_usd_per_l']:.3f}", "1.038")
        self.assertEqual(f"{d.loc['europe_cis','price_usd_per_l']:.3f}", "1.274")


class TestEngine(unittest.TestCase):
    def test_fuel_cost_is_burn_times_exact_benchmark_times_all_flown_hours(self):
        r = sim(billed_hours=300.0, positioning_hours=40.0, other_hours=60.0, fuel=bench("north_america"))
        self.assertTrue(r["available"]); f = r["fuel"]; p = 458.67 / 100 / G
        self.assertAlmostEqual(f["price_usd_l"], p, places=12)
        self.assertAlmostEqual(f["annual_cost_usd"], 400.0 * f["burn_l_h"] * p, places=6)
        self.assertEqual(f["price_source"], "benchmark"); self.assertFalse(r["fuel_benchmark"]["user_adjusted"])
        self.assertIn("fuel_benchmark", codes(r)); self.assertNotIn("fuel_benchmark_adjusted", codes(r))

    def test_replaces_the_fuel_line_without_double_counting(self):
        rep = sim(billed_hours=350.0); b = sim(billed_hours=350.0, fuel=bench("europe_cis"))
        burn = b["fuel"]["burn_l_h"]; p = 482.41 / 100 / G
        self.assertAlmostEqual(b["budget_usd"] - rep["budget_usd"], 350 * burn * (p - rep["fuel"]["price_usd_l"]), places=4)
        self.assertAlmostEqual(b["variable"]["nonfuel_per_h"], rep["variable"]["nonfuel_per_h"], places=9)       # only the fuel line moved
        self.assertAlmostEqual(b["fixed"]["annual_total"], rep["fixed"]["annual_total"], places=9)
        self.assertEqual(len([c for c in b["components"] if c["key"] == "fuel"]), 1)
        self.assertAlmostEqual(sum(c["annual_usd"] for c in b["components"] if c["category"] == "Variable"), b["variable"]["annual"], places=4)
        self.assertAlmostEqual(b["budget_usd"], b["fixed"]["annual_total"] + b["variable"]["annual"], places=6)

    def test_no_15_percent_on_fuel_and_burn_untouched(self):
        b = sim(billed_hours=350.0, fuel=bench("middle_east")); r = row(FAL)
        self.assertAlmostEqual(b["fuel"]["burn_l_h"], E.num(r, "fuel_burn_l_per_h"))
        self.assertAlmostEqual(b["fuel"]["price_usd_l"], 392.90 / 100 / G, places=12)                           # no x1.15 anywhere
        self.assertEqual(E.num(r, "annual_fuel_cost_usd"), E.num(raw_row(FAL), "annual_fuel_cost_usd"))
        self.assertEqual(E.num(r, "fuel_burn_l_per_h"), E.num(raw_row(FAL), "fuel_burn_l_per_h"))
        self.assertFalse([k for k in raw_row(FAL).index if "bench" in k.lower()])                                # no regional mark-up stored in the base

    def test_manual_edit_is_flagged_and_used(self):
        b = sim(fuel=bench("middle_east", 1.25)); bi = b["fuel_benchmark"]
        self.assertTrue(bi["user_adjusted"]); self.assertEqual(bi["nature"], "user hypothesis"); self.assertAlmostEqual(b["fuel"]["price_usd_l"], 1.25)
        self.assertAlmostEqual(bi["benchmark_usd_l"], 392.90 / 100 / G, places=12); self.assertIn("fuel_benchmark_adjusted", codes(b))
        self.assertEqual(bi["adjusted_text"], "User-adjusted annual fuel price assumption.")
        same = sim(fuel=bench("middle_east", round(392.90 / 100 / G, 3)))                                       # the displayed (3-decimal) value = untouched
        self.assertFalse(same["fuel_benchmark"]["user_adjusted"]); self.assertAlmostEqual(same["fuel"]["price_usd_l"], 392.90 / 100 / G, places=12)

    def test_unbilled_and_zero_hours(self):
        a = sim(billed_hours=0.0, positioning_hours=100.0, other_hours=50.0, fuel=bench("africa"))
        self.assertTrue(a["available"]); self.assertAlmostEqual(a["fuel"]["annual_litres"], 150.0 * a["fuel"]["burn_l_h"])
        z = sim(billed_hours=0.0, fuel=bench("africa"))
        self.assertTrue(z["available"]); self.assertEqual(z["fuel"]["annual_cost_usd"], 0.0); self.assertIsNone(z["cost_per_h_usd"]); self.assertIn("zero_hours", codes(z))

    def test_missing_region_or_price_is_an_error_not_zero(self):
        for fc in (bench(""), bench("atlantis"), bench("africa", -1.0), bench("africa", 0.0)):
            r = sim(fuel=fc)
            if fc.price == 0.0:                       # 0 typed by the user: refused, never a free fuel
                self.assertFalse(r["available"]); self.assertIn("price_benchmark", codes(r)); continue
            self.assertFalse(r["available"]); self.assertIn("price_benchmark", codes(r)); self.assertIsNone(r["budget_usd"])

    def test_missing_fuel_data_gives_no_invented_replacement(self):
        base = E.load_base(); hist = base[~base.has_detail.astype(bool)].iloc[0]
        r = E.compute(hist, E.Scenario(hist["aircraft_id"], mode="simulation", billed_hours=100.0, fuel=bench()), today=TODAY)
        base_r = E.compute(hist, E.Scenario(hist["aircraft_id"], mode="simulation", billed_hours=100.0), today=TODAY)
        self.assertTrue(r["historical"]); self.assertEqual(r["fuel"], {}); self.assertIn("legacy_fuel", codes(r)); self.assertIsNone(r["fuel_benchmark"])
        self.assertEqual(r["budget_usd"], base_r["budget_usd"])             # the benchmark replaces nothing: fuel is not separable in a historical sheet
        r2 = row(FAL).copy(); r2["fuel_burn_l_per_h"] = None; r2["fuel_burn_from_annual_l_per_h"] = None
        r2 = E.compute(r2, E.Scenario(FAL, mode="simulation", billed_hours=100.0, fuel=bench()), today=TODAY)
        self.assertFalse(r2["available"]); self.assertIn("no_burn", codes(r2))
        r3 = row(FAL).copy(); r3["annual_fuel_cost_usd"] = None
        r3 = E.compute(r3, E.Scenario(FAL, mode="simulation", billed_hours=100.0, fuel=bench()), today=TODAY)
        self.assertFalse(r3["available"])

    def test_reference_mode_is_independent(self):
        a = E.compute(row(FAL), E.Scenario(FAL, mode="reference"), today=TODAY)
        b = E.compute(row(FAL), E.Scenario(FAL, mode="reference", fuel=bench("europe_cis", 2.0), billed_hours=900.0), today=TODAY)
        self.assertEqual(a["budget_usd"], b["budget_usd"]); self.assertEqual(b["budget_usd"], 1637042.0); self.assertEqual(a["config_hash"], b["config_hash"])
        self.assertIsNone(b["fuel_benchmark"]); self.assertNotEqual(b["fuel"].get("price_source"), "benchmark")

    def test_hash_changes_with_method_region_price_and_data(self):
        h = lambda fc: sim(fuel=fc)["config_hash"]
        self.assertEqual(h(bench("africa")), h(bench("africa")))
        self.assertEqual(len({h(bench("africa")), h(bench("europe_cis")), h(bench("africa", 1.5)), h(E.FuelConfig()), h(E.FuelConfig(price_source="average", price=1.2))}), 5)
        r = row(FAL); old = E.load_fuel_benchmarks; before = h(bench("africa"))
        try:
            d = old().copy(); d.loc[d.region_id == "africa", "price_us_cents_per_us_gallon"] = 470.0
            d["price_usd_per_l"] = d["price_us_cents_per_us_gallon"].map(E.usd_per_l_from_us_cents_per_usg); E.load_fuel_benchmarks = lambda: d
            self.assertNotEqual(E.compute(r, E.Scenario(FAL, billed_hours=350.0, fuel=bench("africa")), today=TODAY)["config_hash"], before)
        finally: E.load_fuel_benchmarks = old

    def test_eur_display_uses_dated_rate_only(self):
        fx = E.Fx("EUR", 0.92, "2026-10-18", "test"); r = sim(fuel=bench("middle_east"), fx=fx)
        self.assertEqual(r["fuel"]["price_usd_l"], sim(fuel=bench("middle_east"))["fuel"]["price_usd_l"])        # USD source price, EUR is display only
        self.assertAlmostEqual(E.Display(fx).conv(1.0), 0.92)

    def test_sensitivity_and_fleet_share_the_engine_price(self):
        s = E.Scenario(FAL, billed_hours=350.0, fuel=bench("middle_east")); p = 392.90 / 100 / G
        out = E.sensitivity_fuel_price(row(FAL), s, [p])
        self.assertAlmostEqual(out[0][2], E.compute(row(FAL), s, today=TODAY)["budget_usd"], places=4)
        fc = E.fleet_comparison(E.load_base()[E.load_base().aircraft_id == FAL], s)
        self.assertAlmostEqual(float(fc.iloc[0]["budget_usd"]), E.compute(row(FAL), s, today=TODAY)["budget_usd"], places=4)


class TestScreensPdfCsv(unittest.TestCase):
    OV = {"Aircraft model": FAL, "Calculation mode": "Custom simulation", "Fuel price method": METHOD, "Main refuelling region": "middle_east"}

    def run_app(self, ov=None):
        import smoke_support
        return smoke_support.run(ov or {})

    def text(self, st): return " ".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "error", "info", "success", "expander"))
    def metric(self, st, label): return next(v for k, a, kw in st.log if k == "metric" and a[0].endswith(label) for v in [a[1]])
    def csv(self, st): return next(a[1] for k, a, kw in st.log if k == "download_button" and "CSV" in a[0]).decode("utf-8-sig")

    def test_ui_labels_disclaimer_and_no_airport_fields_in_the_annual_path(self):
        st, _ = self.run_app(self.OV); L = {l for _, l, _, _ in st.widgets}; t = self.text(st)
        self.assertTrue({"Fuel price method", "Main refuelling region", "Average fuel price used (USD/L)"} <= L)
        self.assertIn(DISC, t); self.assertIn("2026-10-09", t); self.assertIn("not a real-time feed", t)
        self.assertNotIn(E.BENCHMARK_USER_ADJUSTED, t)
        self.assertFalse({"Airport ICAO", "Supplier", "Fees per uplift (fixed)", "Quote valid until (YYYY-MM-DD)"} & L)

    def test_adjusting_the_prefilled_price_shows_the_user_mention(self):
        st, _ = self.run_app({**self.OV, "Average fuel price used (USD/L)": 1.25}); self.assertIn(E.BENCHMARK_USER_ADJUSTED, self.text(st))

    def test_screen_pdf_csv_agree_and_pdf_invalidation(self):
        ov = {**self.OV, "Average fuel price used (USD/L)": 1.25, "📄 Generate PDF Report": True}
        st, _ = self.run_app(ov); screen = self.metric(st, "Total Annual Budget"); csv = self.csv(st); txt = flat(pdf_text(st.session_state["pdf_report"]["data"]))
        n = float(re.search(r"annual_budget_usd,([\d.]+)", csv).group(1)); self.assertEqual(f"$ {round(n):,}", screen); self.assertIn(screen, txt)
        for needle in ("fuel_price_method,Regional market benchmark", "fuel_benchmark_region,Middle East", "fuel_benchmark_period,week ending 2026-10-09",
                       "fuel_benchmark_price_us_cents_per_us_gallon,392.9", "fuel_price_used_usd_per_l,1.25", "fuel_price_currency_unit,USD per litre",
                       "fuel_price_user_adjusted,True", "fuel_price_qualification,user hypothesis", "fuel_price_adjusted_text,User-adjusted annual fuel price assumption."):
            self.assertIn(needle, csv)
        for needle in ("Regional market benchmark", "Middle East", "week ending 2026-10-09", "392.90 US cents per US gallon", "1.038 USD/L", "1.250 USD/L",
                       "User-adjusted annual fuel price assumption.", "user hypothesis", "not an into-wing price"):
            self.assertIn(needle, txt)
        h1 = st.session_state["pdf_report"]["hash"]
        # a relevant change gives another scenario id: the stored PDF (old hash) is then reported obsolete
        self.assertNotEqual(h1, sim(fuel=bench("middle_east", 1.30))["config_hash"])
        self.assertNotEqual(h1, sim(fuel=bench("africa", 1.25))["config_hash"])

    def test_unadjusted_pdf_says_refinery_reference(self):
        st, _ = self.run_app({**self.OV, "📄 Generate PDF Report": True}); csv = self.csv(st); txt = flat(pdf_text(st.session_state["pdf_report"]["data"]))
        self.assertIn("fuel_price_qualification,refinery reference", csv); self.assertIn("fuel_price_user_adjusted,False", csv)
        self.assertIn("refinery reference", txt); self.assertNotIn("User-adjusted", txt); self.assertIn("not an into-wing price", txt)

    def test_report_reference_disables_controls_and_keeps_original(self):
        st, _ = self.run_app({**self.OV, "Calculation mode": "Report reference"})
        self.assertEqual(self.metric(st, "Total Annual Budget"), "$ 1,637,042")

    def test_pdf_does_not_call_the_benchmark_real_time_or_annual_average(self):
        r = row(FAL); res = E.compute(r, E.Scenario(FAL, mode="simulation", billed_hours=350.0, fuel=bench("asia_oceania")), today=TODAY)
        t = flat(pdf_text(RPT.build_report_pdf(res, E.Display(E.Fx("USD")), E.alerts_for(r, CHECKS, CONFLICTS, CONVS), generated_on=TODAY)))
        self.assertIn(DISC, t); self.assertNotRegex(t, r"(?i)real-time price (?!is used)"); self.assertNotIn("annual average benchmark", t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
