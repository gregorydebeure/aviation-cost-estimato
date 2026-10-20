"""Lot B — free demo, plan table, study offer, PDF template. Recorder-based (tests/fake_streamlit.py): NOT a real browser. No payment, no email."""
import os, re, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F  # noqa: E402
import menkor_engine as E  # noqa: E402
import menkor_report as RPT  # noqa: E402
from test_v19_screens import run, text, metrics  # noqa: E402

FAL = "dassault_falcon_7x"


def free_run(aid):
    for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
    st = F.install({"__real_defaults__": True, "Aircraft model": aid}, None)
    import app
    app.render_auth = lambda: (False, False); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
    try: app.main()
    except F.StopApp: pass
    return st


class TestFreeDemo(unittest.TestCase):
    def test_demo_is_labelled_and_has_no_placeholder(self):
        t = text(free_run(FAL))
        self.assertIn("Free demo", t); self.assertIn("not your aircraft", t)
        self.assertNotIn("000,000", t); self.assertIn("report preview", t.lower())

    def test_other_aircraft_do_not_get_a_computation(self):
        st = free_run("gulfstream_g650")
        t = text(st)
        self.assertIn("Dassault Falcon 7X", t); self.assertIn("available with an Essentiel or Pro plan", t)
        self.assertTrue(all(str(a[0]).startswith("Demo") for k, a, kw in st.log if k == "metric"))

    def test_free_has_no_pdf_button(self):
        st = free_run(FAL)
        self.assertFalse([1 for k, l, key, d in st.widgets if k in ("button", "download_button") and "PDF" in str(l)])

    def test_plan_table_prices_unchanged_and_no_future_features(self):
        t = text(free_run(FAL))
        self.assertIn("15€/mo", t); self.assertIn("50€/mo", t)
        for forbidden in ("Scenario saving", "broker logo", "client folders", "Compare 2"): self.assertNotIn(forbidden, t)


class TestStudyOffer(unittest.TestCase):
    def test_text_and_single_button(self):
        import app
        self.assertEqual(app.BUDGET_OFFER_TITLE, "What will this specific aircraft cost you?")
        self.assertEqual(app.BUDGET_BUTTON, "Request my aircraft budget")

    def test_no_new_price_in_offer(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        block = src[src.index("BUDGET_OFFER_TITLE="):src.index("# ─── MAIN")]
        self.assertNotRegex(block, r"(?i)stripe|checkout|€\s?\d|\$\s?\d|/month")


class TestReportTemplate(unittest.TestCase):
    def test_template_version_in_session_guard(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertIn('_p.get("tpl")==RPT.TEMPLATE_VERSION', src)
        self.assertTrue(RPT.TEMPLATE_VERSION)


if __name__ == "__main__": unittest.main()
