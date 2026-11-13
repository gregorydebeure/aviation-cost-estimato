"""PDF 2.1: owner cost-per-hour box, management-fee scope wording, 'Not confirmed' link. Fake-free (engine + ReportLab only)."""
import subprocess, unittest, tempfile, os
from datetime import date
import menkor_engine as E
import menkor_report as R

BASE = E.load_base(); CH, CF, CV = E.load_checks(), E.load_conflicts(), E.load_conversions()
AID = "dassault_falcon_7x"; TODAY = date(2026, 11, 13)


def pdf_text(**kw):
    r = BASE[BASE.aircraft_id == AID].iloc[0]
    base = dict(mode="simulation", fuel=E.FuelConfig(price_source="average", price=1.274, currency="USD"), charter_rate=9000.0, commission_pct=10.0,
                positioning_confirmed=True, private_hours_confirmed=True, other_fees_confirmed=True, limits_reviewed=True)
    base.update(kw)
    res = E.compute(r, E.Scenario(AID, **base), today=TODAY)
    pdf = R.build_report_pdf(res, E.Display(E.Fx("USD")), E.alerts_for(r, CH, CF, CV), generated_on=TODAY)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf)
    try:
        return res, " ".join(subprocess.run(["pdftotext", f.name, "-"], capture_output=True, text=True).stdout.split())
    finally:
        os.unlink(f.name)


class TestPdf21(unittest.TestCase):
    def test_template_version(self): self.assertEqual(R.TEMPLATE_VERSION, "2.1")

    def test_owner_box_with_hours(self):
        res, t = pdf_text(billed_hours=250.0, other_hours=60.0)
        of = res["profitability"]["owner_flight"] if "profitability" in res else None
        self.assertIn("YOUR COST PER FLIGHT HOUR", t); self.assertIn("WITHOUT CHARTER", t); self.assertIn("CHARTER SAVES YOU", t)
        self.assertIn("Based on 60 owner flight hours", t)

    def test_owner_box_without_hours_shows_annual_not_zero(self):
        _, t = pdf_text(billed_hours=250.0, other_hours=0.0)
        self.assertIn("/ year", t); self.assertIn("No owner flight hours entered", t)

    def test_not_confirmed_heading_links_to_budget_page(self):
        _, t = pdf_text(billed_hours=250.0, other_hours=60.0)
        self.assertNotIn("unknown is never shown as zero", t)
        self.assertIn("Not confirmed (for a more accurate budget: " + R.BUDGET_URL, t.replace("- ", "-"))

    def test_management_scope_declared_or_not(self):
        m = {"management": dict(amount=120000, ccy="USD")}
        _, t = pdf_text(billed_hours=250.0, other_hours=60.0, management=m, management_covers_camo_dispatch=True)
        self.assertIn("Declared by the user as INCLUDING: CAMO", t); self.assertIn("not added again", t)
        _, t = pdf_text(billed_hours=250.0, other_hours=60.0, management=m)
        self.assertIn("did not declare CAMO or dispatch", t)


class TestOwnerFlightExtension(unittest.TestCase):
    def test_keys(self):
        o = E.owner_flight_indicator(500.0, 50.0, standalone_usd=800.0, contribution_usd=300.0, fixed_usd=600.0)
        self.assertAlmostEqual(o["per_hour_usd"], 10.0); self.assertAlmostEqual(o["standalone_per_hour_usd"], 16.0)
        self.assertAlmostEqual(o["saving_per_hour_usd"], 6.0); self.assertAlmostEqual(o["fixed_covered_pct"], 50.0)
    def test_covered_never_negative(self):
        o = E.owner_flight_indicator(-200.0, 50.0, standalone_usd=800.0, contribution_usd=1000.0, fixed_usd=600.0)
        self.assertEqual(o["status"], "surplus"); self.assertTrue(o["per_hour_usd"] in (None, 0.0)); self.assertGreater(o["surplus_usd"], 0)
