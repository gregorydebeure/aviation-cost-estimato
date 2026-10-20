"""
Menkor cost base: the +15 % lives in the DATA (data/menkor_base_couts_ajustes_15pct.csv), the original published values are preserved in
original__* columns, the engine adjusts nothing and Report reference reads the originals.
"""
import io, os, sys, contextlib, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "tools"))
import pandas as pd  # noqa: E402
import menkor_engine as E  # noqa: E402
import audit_adjustment as AUD  # noqa: E402

BASE = E.load_base(); FAL = "dassault_falcon_7x"
ORIGINAL_PDF_FALCON = {  # printed in "Dassault Falcon 7X.pdf", pages 2-3 (checked against the extracted page text)
    "annual_airframe_maintenance_usd": 164983.0, "annual_engine_apu_maintenance_usd": 221115.0, "annual_hangar_fixed_usd": 64846.0,
    "annual_crew_training_fixed_usd": 83729.0, "hourly_airframe_maintenance_usd": 471.0, "hourly_engine_apu_maintenance_usd": 632.0,
    "hourly_maintenance_total_usd": 1103.0, "hourly_airport_fees_usd": 81.0}
V16_SHA256 = "315a7fbf7e100eb93b54400eded83f72ac1cf5328981beb0b4e51b3f98223878"   # the v16 file the originals come from


def row(aid): return BASE[BASE.aircraft_id == aid].iloc[0]


class TestCostBaseData(unittest.TestCase):
    def test_new_base_is_loaded_and_has_the_expected_shape(self):
        self.assertEqual(len(BASE), 167); self.assertEqual(int(BASE.has_detail.sum()), 146)
        self.assertEqual(set(BASE["menkor_base_version"]), {"MENKOR_ADJUSTED_15PCT_2026-10-18"})
        self.assertEqual(set(BASE["menkor_original_csv_sha256"]), {V16_SHA256})
        self.assertEqual(int(BASE.menkor_adjustment_applied.astype(str).str.lower().eq("true").sum()), 146)
        self.assertEqual(BASE.menkor_adjustment_status.value_counts().to_dict(), {"adjusted_documented": 144, "unchanged_historical_no_breakdown": 21, "adjusted_partial_web": 2})
        self.assertEqual(os.path.basename(str(E.DATA_DIR / E.BASE_FILE)), "menkor_base_couts_ajustes_15pct.csv")

    def test_falcon_7x_original_stored_and_computed(self):
        r = row(FAL)
        for f, v in ORIGINAL_PDF_FALCON.items():
            self.assertEqual(E.num(r, E.ORIGINAL_PREFIX + f), v, f)              # preserved original = printed in the report
            self.assertAlmostEqual(E.num(r, f), v * 1.15, places=6, msg=f)        # stored Menkor base = original x 1.15
        ref = E.compute(r, E.Scenario(FAL, mode="reference")); sim = E.compute(r, E.Scenario(FAL, mode="simulation", billed_hours=350.0))
        comp = lambda res, k: next(c["annual_usd"] for c in res["components"] if c["key"] == k)
        for key, f in (("airframe_maint", "annual_airframe_maintenance_usd"), ("engine_apu_maint", "annual_engine_apu_maintenance_usd"), ("hangar", "annual_hangar_fixed_usd")):
            self.assertEqual(comp(ref, key), ORIGINAL_PDF_FALCON[f]); self.assertAlmostEqual(comp(sim, key), ORIGINAL_PDF_FALCON[f] * 1.15, places=6)
        self.assertAlmostEqual(comp(sim, "airframe_maint"), 189730.45, places=2); self.assertAlmostEqual(comp(sim, "hangar"), 74572.90, places=2)

    def test_whole_base_is_internally_consistent(self):
        prov = pd.read_csv(E.DATA_DIR / "provenance.csv", low_memory=False)
        self.assertEqual(AUD.problems_for_base(BASE, prov), [])
        with contextlib.redirect_stdout(io.StringIO()): self.assertEqual(AUD.main(FAL), [])

    def test_originals_are_preserved_separately_and_never_touched_by_the_engine(self):
        r = row(FAL); snap = r.copy()
        for mode in ("reference", "simulation"): E.compute(r, E.Scenario(FAL, mode=mode, billed_hours=350.0))
        self.assertTrue(r.equals(snap))
        o = E.original_view(r)
        self.assertEqual(E.num(o, "annual_budget_usd"), 1637042.0); self.assertEqual(E.num(r, "annual_budget_usd"), 1721495.45)
        self.assertEqual(E.num(E.original_view(o), "annual_budget_usd"), 1637042.0)                  # idempotent
        self.assertEqual(E.num(o, "annual_insurance_fixed_usd"), E.num(r, "annual_insurance_fixed_usd"))   # lines without an original__ column are unchanged

    def test_metadata_deltas_equal_the_original_vs_base_difference(self):
        for _, r in BASE[BASE.has_detail].iterrows():
            d = E.num(r, "menkor_delta_budget_usd"); self.assertIsNotNone(d, r["aircraft_id"])
            self.assertAlmostEqual(E.num(r, "annual_budget_usd") - E.num(r, E.ORIGINAL_PREFIX + "annual_budget_usd"), d, delta=0.01, msg=r["aircraft_id"])
            self.assertAlmostEqual(E.num(r, "annual_fixed_cost_usd") - E.num(r, E.ORIGINAL_PREFIX + "annual_fixed_cost_usd"), E.num(r, "menkor_delta_fixed_usd"), delta=0.01)
            self.assertAlmostEqual(E.num(r, "annual_variable_cost_usd") - E.num(r, E.ORIGINAL_PREFIX + "annual_variable_cost_usd"), E.num(r, "menkor_delta_variable_usd"), delta=0.01)

    def test_fuel_is_never_adjusted_in_the_base(self):
        for _, r in BASE[BASE.has_detail].iterrows():
            for f in ("annual_fuel_cost_usd", "annual_fuel_volume_l", "hourly_fuel_usd", "fuel_burn_l_per_h", "reference_fuel_price_usd_per_l",
                      "annual_insurance_fixed_usd", "annual_crew_expense_fixed_usd", "hourly_catering_usd"):
                self.assertNotIn(E.ORIGINAL_PREFIX + f, BASE.columns, f)


class TestReferenceAndSingleApplication(unittest.TestCase):
    def test_reference_reads_originals_for_every_documented_aircraft(self):
        for _, r in BASE[BASE.has_detail].iterrows():
            res = E.compute(r, E.Scenario(r["aircraft_id"], mode="reference"))
            self.assertTrue(res["available"], r["aircraft_id"])
            self.assertEqual(res["budget_usd"], E.num(r, E.ORIGINAL_PREFIX + "annual_budget_usd"), r["aircraft_id"])
            self.assertFalse(res["menkor_base"]["applied"])

    def test_simulation_reads_the_stored_base_once_no_second_adjustment(self):
        for aid in ("dassault_falcon_7x", "gulfstream_g450", "challenger_300", "airbus_a340" if False else "bombardier_global_5000"):
            r = row(aid); h = E.num(r, "reference_annual_hours")
            sim = E.compute(r, E.Scenario(aid, mode="simulation", billed_hours=h))
            self.assertEqual(sim["menkor_base"]["published_budget_adjusted"], E.num(r, "annual_budget_usd"))
            self.assertAlmostEqual(sim["reconciliation"]["published_budget"], E.num(r, "annual_budget_usd"), places=6)
            self.assertAlmostEqual(sim["menkor_base"]["delta_total"], E.num(r, "menkor_delta_budget_usd"), delta=0.01)       # exactly the stored +15 %, not more

    def test_repeated_calls_and_fleet_comparison_do_not_compound(self):
        r = row(FAL); snap = r.copy(); kw = dict(mode="simulation", billed_hours=350.0)
        a = E.compute(r, E.Scenario(FAL, **kw)); b = E.compute(r, E.Scenario(FAL, **kw))
        self.assertTrue(r.equals(snap)); self.assertEqual(a["budget_usd"], b["budget_usd"])
        fc = E.fleet_comparison(BASE[BASE.aircraft_id == FAL], E.Scenario(FAL, **kw))
        self.assertAlmostEqual(float(fc.iloc[0]["budget_usd"]), a["budget_usd"], places=6)

    def test_total_difference_is_15_percent_of_the_four_lines_only(self):
        on = E.compute(row(FAL), E.Scenario(FAL, mode="simulation", billed_hours=350.0))["menkor_base"]
        self.assertAlmostEqual(on["delta_total"], 0.15 * (164983.0 + 221115.0 + 81.0 * 350.0 + 83729.0 + 64846.0), places=6)
        self.assertEqual(round(on["delta_total"]), 84453); self.assertEqual(round(on["published_budget_original"]), 1637042)

    def test_hash_depends_on_the_base_version(self):
        self.assertIn("adj15", E.DB_VERSION)


class TestNoAdjustmentControl(unittest.TestCase):
    def test_screens_have_no_adjustment_button_nor_percentage(self):
        import smoke_support
        for mode in ("Custom simulation", "Report reference"):
            st, _ = smoke_support.run({"Aircraft model": FAL, "Calculation mode": mode})
            labels = [l for _, l, _, _ in st.widgets]
            self.assertFalse([l for l in labels if "adjust" in l.lower() or "update base" in l.lower() or "(%)" in l and "ommission" not in l and "margin" not in l.lower() and "taxes" not in l.lower()], labels)
            txt = " ".join(str(a[0]) for k, a, kw in st.log if k in ("caption", "markdown", "info"))
            self.assertNotIn("Update base costs", txt)

    def test_simulation_screen_documents_the_base_and_keeps_originals_visible(self):
        import smoke_support
        st, _ = smoke_support.run({"Aircraft model": FAL, "Calculation mode": "Custom simulation"})
        txt = " ".join(str(a[0]) for k, a, kw in st.log if k in ("caption", "markdown", "info", "expander"))
        self.assertIn("Menkor cost base", txt); self.assertIn("kept separately", txt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
