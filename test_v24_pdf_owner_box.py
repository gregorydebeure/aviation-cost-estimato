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


class TestPilotCrew(unittest.TestCase):
    R_ = BASE[BASE.aircraft_id == AID].iloc[0]

    def comp(self, **kw):
        base = dict(mode="simulation", fuel=E.FuelConfig(price_source="average", price=1.274, currency="USD"), billed_hours=250.0)
        base.update(kw)
        return E.compute(self.R_, E.Scenario(AID, **base), today=TODAY)

    def test_pilot_crew_replaces_the_reference_crew_expense(self):
        ref = self.comp(); ref_crew = float(self.R_["annual_crew_expense_fixed_usd"])
        pc = {"pilot_in_command": dict(count=2, salary=150000.0, ccy="USD"), "first_officer": dict(count=1, salary=90000.0, ccy="USD")}
        r = self.comp(pilot_crew=pc)
        self.assertAlmostEqual(r["fixed"]["annual_total"] - ref["fixed"]["annual_total"], 390000.0 - ref_crew, places=2)   # replaced, not added
        self.assertEqual(r["variable"]["annual"], ref["variable"]["annual"])
        self.assertIn("2 pilot in command + 1 first officer", " ".join(r["scope"]["exclusions"]))

    def test_partial_pilot_entry_is_an_error_not_a_guess(self):
        r = self.comp(pilot_crew={"pilot_in_command": dict(count=1, salary=150000.0, ccy="USD")})
        self.assertFalse(r["available"]); self.assertIn("pilot_crew_incomplete", [f["code"] for f in r["flags"]])

    def test_empty_keeps_the_reference(self):
        self.assertEqual(self.comp()["fixed"]["annual_total"], self.comp(pilot_crew={})["fixed"]["annual_total"])
        self.assertFalse(self.comp()["pilot_crew"]["entered"])

    def test_pdf_annex_states_the_pilot_crew(self):
        _, t = pdf_text(billed_hours=250.0, pilot_crew={"pilot_in_command": dict(count=2, salary=150000.0, ccy="USD"), "first_officer": dict(count=1, salary=90000.0, ccy="USD")})
        self.assertIn("Pilot crew entered by the user", t)

    def test_page_one_holds_everything_and_no_split_exclusion_box(self):
        res, _ = pdf_text(billed_hours=250.0, other_hours=60.0)
        r = BASE[BASE.aircraft_id == AID].iloc[0]
        pdf = R.build_report_pdf(res, E.Display(E.Fx("USD")), E.alerts_for(r, CH, CF, CV), generated_on=TODAY)
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(pdf)
        try:
            p1 = subprocess.run(["pdftotext", "-f", "1", "-l", "1", f.name, "-"], capture_output=True, text=True).stdout
            self.assertIn("see the annex", p1); self.assertIn("Essential assumptions", p1)
            p2 = subprocess.run(["pdftotext", "-f", "2", "-l", "2", f.name, "-"], capture_output=True, text=True).stdout
            self.assertNotIn("Essential assumptions", p2); self.assertNotIn("Main exclusions", p2)
        finally:
            os.unlink(f.name)
