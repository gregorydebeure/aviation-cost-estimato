"""Screen / PDF / CSV / budget-request tests for the 'indicative simulation vs aircraft-specific budget' change.
They use tests/fake_streamlit.py (a recorder). This is NOT a real Streamlit/browser validation. No real email is ever sent: the HTTP call is injected."""
import os, re, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F  # noqa: E402
import menkor_engine as E  # noqa: E402

FAL = "dassault_falcon_7x"
RATE = {"Expected charter revenue per billed hour": 9000.0, "Rate currency": "USD",
        "This rate represents": "Operator revenue before commission (gross)", "Commission (%) on gross revenue": 10.0}
BASEOV = {"Aircraft model": FAL, "Calculation mode": "Custom simulation"}
OFFER = "A manually prepared budget based on serial number, programme coverage, upcoming maintenance and your intended operation."


def run(ov, patch=None):
    for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[m]
    st = F.install(ov, None)
    import app
    app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
    if patch: patch(app)
    try: app.main()
    except F.StopApp: pass
    return st, app


def confirmations(ov):
    """The single recap button replaces the four former checkboxes: pressing it confirms the assumptions currently displayed."""
    return {"Confirm assumptions and calculate": True}


def text(st):
    return "\n".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "error", "info", "success"))


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f: f.write(data)
    try: return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout
    finally: os.unlink(f.name)


def metrics(st): return [(a[0], a[1]) for k, a, kw in st.log if k == "metric"]


def csv_of(st):
    return next(a[1] for k, a, kw in st.log if k == "download_button" and "CSV" in a[0]).decode("utf-8-sig")


class TestNoRate(unittest.TestCase):
    def test_costs_visible_no_revenue_no_threshold_no_obsolete_estimate(self):
        st, _ = run({**BASEOV, "📄 Generate PDF Report": True})
        t = text(st)
        self.assertIn("Enter your expected charter revenue per billed hour to run this simulation.", t)
        labels = [m[0] for m in metrics(st)]
        self.assertTrue([l for l in labels if "Annual Budget" in l])
        for bad in ("Gross Revenue", "Operating result", "operating result", "Net Result"):
            self.assertFalse([l for l in labels if bad in l], bad)
        self.assertNotIn("Menkor estimate", t); self.assertNotIn("Operating cost coverage threshold:", t)
        st_w = [w for w in st.widgets if w[1] == "Expected charter revenue per billed hour"]
        self.assertTrue(st_w)                                                     # an (empty) field exists
        csv = csv_of(st); self.assertNotRegex(csv, r"threshold_billed_hours,\d")
        pdf = st.session_state["pdf_report"]["data"]; p = " ".join(pdf_text(pdf).split())     # cost-only report is not broken
        self.assertIn("not entered", p); self.assertNotIn("Menkor estimate", p)

    def test_rate_field_is_empty_and_has_explicit_currency_and_basis_choice(self):
        st, app = run(BASEOV)
        kinds = {l: k for k, l, key, d in st.widgets}
        self.assertEqual(kinds.get("Rate currency"), "selectbox"); self.assertEqual(kinds.get("This rate represents"), "radio")


class TestThresholdOnScreen(unittest.TestCase):
    def test_withheld_then_shown_after_confirmations_with_note_and_hours(self):
        ov = {**BASEOV, **RATE}
        st, _ = run(ov)
        t = text(st)
        self.assertIn("Not displayed until you confirm", t); self.assertNotRegex(t, r"Operating cost coverage threshold: [\d,]+ billed")
        self.assertFalse([m for m in metrics(st) if m[0] == "Billed hours (rounded up)"])
        st2, _ = run({**ov, **confirmations(ov)})
        t2 = text(st2)
        self.assertRegex(t2, r"Operating cost coverage threshold: [\d,]+ billed hours \([\d,]+ flown hours in total")
        self.assertIn(E.THRESHOLD_NOTE, t2); self.assertIn("Seuil de couverture des coûts d'exploitation renseignés", t2)
        self.assertTrue([m for m in metrics(st2) if m[0] == "Billed hours (rounded up)"]); self.assertTrue([m for m in metrics(st2) if m[0] == "Total flown hours"])
        self.assertIn("Costs included & limitations", " ".join(str(a[0]) for k, a, kw in st2.log if k == "expander"))
        self.assertNotRegex(t2, r"(?i)break-?even")

    def test_incomplete_ownership_lists_what_is_missing_then_complete(self):
        ov = {**BASEOV, **RATE}; ov.update(confirmations(ov))
        t = text(run(ov)[0]); self.assertIn("economic depreciation", t); self.assertIn("Not complete", t)
        ov2 = {**ov, "Annual economic depreciation": 1500000.0, "Annual loan interest and financing costs": 0.0}
        st2, _ = run(ov2); t2 = text(st2)
        self.assertRegex(t2, r"Economic coverage threshold including the ownership costs entered: [\d,]+ billed hours"); self.assertNotIn("Not complete", t2)

    def test_changing_a_confirmed_assumption_requires_a_new_confirmation(self):
        ov = {**BASEOV, **RATE}
        state = {}
        for k in list(sys.modules):
            if k == "app" or k.startswith("streamlit") or k.startswith("plotly"): del sys.modules[k]
        def go(o):
            for k in list(sys.modules):
                if k == "app" or k.startswith("streamlit") or k.startswith("plotly"): del sys.modules[k]
            st = F.install(o, state)
            import app
            app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
            try: app.main()
            except F.StopApp: pass
            return st
        st1 = go({**ov, **confirmations(ov)})                    # button pressed
        self.assertRegex(text(st1), r"Operating cost coverage threshold: [\d,]+ billed")
        st2 = go(ov)                                             # next rerun, nothing changed: still confirmed
        self.assertRegex(text(st2), r"Operating cost coverage threshold: [\d,]+ billed")
        st3 = go({**ov, "Commission (%) on gross revenue": 12.0})   # a concerned assumption changed: confirmation is obsolete
        self.assertNotRegex(text(st3), r"Operating cost coverage threshold: [\d,]+ billed")
        self.assertIn("Not displayed until you confirm", text(st3))
        st4 = go({**ov, "Commission (%) on gross revenue": 12.0, **confirmations(ov)})
        self.assertRegex(text(st4), r"Operating cost coverage threshold: [\d,]+ billed")
        st5 = go({**ov, "Commission (%) on gross revenue": 12.0, "Other commercial fees / year (USD) — not already in the report": 5000.0})
        self.assertNotRegex(text(st5), r"Operating cost coverage threshold: [\d,]+ billed")


class TestScreenPdfCsvAgree(unittest.TestCase):
    def setUp(self):
        self.ov = {**BASEOV, **RATE, "📄 Generate PDF Report": True}; self.ov.update(confirmations({**BASEOV, **RATE}))
        self.st, self.app = run(self.ov)

    def test_threshold_identical_on_screen_csv_pdf(self):
        t = text(self.st); m = re.search(r"Operating cost coverage threshold: ([\d,]+) billed hours \(([\d,]+) flown hours", t)
        self.assertTrue(m); billed = int(m.group(1).replace(",", ""))
        csv = csv_of(self.st); self.assertRegex(csv, rf"threshold_billed_hours,{billed}\b")
        pdf = " ".join(pdf_text(self.st.session_state["pdf_report"]["data"]).split())
        self.assertIn(f"{billed:,d} billed hours", pdf); self.assertIn("Operating cost coverage threshold", pdf)
        self.assertIn(" ".join(E.THRESHOLD_NOTE.split()), pdf)
        for need in ("Seuil de couverture des coûts d'exploitation renseignés", "Costs included", "before commission", "positioning", "private"):
            self.assertIn(need, pdf, need)
        self.assertNotRegex(pdf, r"(?i)break-?even")

    def test_csv_carries_assumptions_and_scope(self):
        csv = csv_of(self.st)
        for need in ("charter_rate_basis", "charter_rate_usd_per_billed_hour", "commission_pct_applied", "positioning_hours", "positioning_ratio_used", "operating_cost_coverage_threshold_note",
                     "confirmations", "costs_not_confirmed", "cost_known_exclusions", "cost_limitations", "economic_coverage_threshold_status"):
            self.assertIn(need, csv, need)
        self.assertNotRegex(csv, r"(?i)break-?even|acc_")

    def test_pdf_goes_stale_when_an_assumption_changes_and_download_is_blocked(self):
        st1, _ = run(self.ov)
        state = {"pdf_report": st1.session_state["pdf_report"]}
        for k in list(sys.modules):
            if k == "app" or k.startswith("streamlit") or k.startswith("plotly"): del sys.modules[k]
        st2 = F.install({**BASEOV, **RATE, "Commission (%) on gross revenue": 15.0}, state)
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F.StopApp: pass
        self.assertIn("is obsolete", text(st2))
        self.assertFalse([1 for k, a, kw in st2.log if k == "download_button" and "PDF" in a[0]])

    def test_external_charter_separated_from_owner_payments(self):
        pdf = " ".join(pdf_text(self.st.session_state["pdf_report"]["data"]).split())
        self.assertRegex(pdf, r"(?i)external charter")
        self.assertRegex(pdf, r"(?i)owner")


class TestBudgetOffer(unittest.TestCase):
    def test_block_button_text_and_limits(self):
        st, _ = run({**BASEOV, **RATE})
        t = text(st)
        self.assertIn("What will this specific aircraft cost you?", t); self.assertIn(OFFER, t)
        self.assertTrue([1 for k, l, key, d in st.widgets if k == "button" and l == "Request my aircraft budget"])
        for need in ("Detailed operating budget", "three years", "First-year cash flow", "Private and charter scenarios", "remaining to the owner after the charter contribution", "CAMO / MRO"):
            self.assertIn(need, t, need)
        self.assertRegex(t, r"not a pre-purchase inspection \(PPI\)"); self.assertNotRegex(t, r"(?i)\b(€|\$|usd|eur)\s?\d+[^\n]*budget request")

    def test_budget_offer_has_no_price_and_no_payment(self):
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        i = src.index("BUDGET_OFFER_TITLE="); j = src.index("# ─── MAIN")
        block = src[i:j]
        self.assertNotRegex(block, r"(?i)stripe|checkout|€\s?\d|\$\s?\d|per month|/month")

    def form_ov(self, **kw):
        base = {**BASEOV, **RATE, "Request my aircraft budget": True, "Name": "A B", "Email": "a@b.co", "Aircraft status": "Already owned", "Send request": True}
        return {**base, **kw}

    def go(self, ov, fake_send):
        def patch(app): app._send_budget_request = fake_send
        st, _ = run(ov, patch)
        return st

    def test_form_success_shows_transmitted_only_after_success(self):
        calls = []
        st = self.go(self.form_ov(), lambda data, **k: (calls.append(data) or (True, "")))
        t = text(st)
        self.assertTrue(calls); self.assertEqual(calls[0]["Email"], "a@b.co")
        self.assertIn("has been transmitted", t)

    def test_form_failure_and_not_configured_never_say_sent(self):
        for res, needle in (((False, "HTTP 500"), "could not be sent (HTTP 500)"), ((False, "not_configured"), "reception is not configured")):
            st = self.go(self.form_ov(), lambda data, _r=res, **k: _r)
            t = text(st); self.assertIn(needle, t); self.assertNotIn("has been transmitted", t); self.assertNotRegex(t, r"(?i)\brequest (was )?sent\b")
            self.assertIn("No request has been recorded", t)
        st = self.go(self.form_ov(), lambda data, **k: (False, "not_configured")); self.assertIn("RESEND_API_KEY", text(st))

    def test_form_is_short_and_status_has_no_preselected_answer(self):
        st, _ = run(self.form_ov())
        labels = [l for k, l, key, d in st.widgets]
        for need in ("Name", "Email", "Aircraft model", "Aircraft status"): self.assertIn(need, labels)
        for gone in ("MSN (optional at first contact)", "Year (optional)", "Known programmes (if available)", "Intended region / base"): self.assertNotIn(gone, labels)
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertRegex(src, r'st\.radio\("Aircraft status",\[[^\]]*\],index=None')

    def test_status_required_before_sending(self):
        calls = []
        st = self.go(self.form_ov(**{"Aircraft status": None}), lambda data, **k: (calls.append(1) or (True, "")))
        self.assertFalse(calls)

    def test_validation_blocks_sending(self):
        calls = []
        st = self.go(self.form_ov(Email="not-an-email"), lambda data, **k: (calls.append(1) or (True, "")))
        self.assertFalse(calls); self.assertIn("valid email", text(st))
        st = self.go(self.form_ov(Name=""), lambda data, **k: (calls.append(1) or (True, ""))); self.assertFalse(calls)

    def test_transport_is_injected_and_not_configured_without_secrets(self):
        _, app = run(BASEOV)
        sent = []
        class R:  # fake response
            def __init__(s, c): s.status_code = c
        ok, d = app._send_budget_request({"Name": "x", "Email": "a@b.co", "Aircraft model": "m"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "me@x.co"}, post=lambda *a, **k: (sent.append((a, k)) or R(200)))
        self.assertTrue(ok); self.assertEqual(sent[0][1]["json"]["to"], ["me@x.co"]); self.assertEqual(sent[0][0][0], "https://api.resend.com/emails")
        ok, d = app._send_budget_request({"Email": "a@b.co"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "me@x.co", "BUDGET_REQUEST_TO": "bud@x.co"}, post=lambda *a, **k: (sent.append(k) or R(201)))
        self.assertTrue(ok); self.assertEqual(sent[-1]["json"]["to"], ["bud@x.co"])
        ok, d = app._send_budget_request({"Email": "a@b.co"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "me@x.co"}, post=lambda *a, **k: R(403))
        self.assertFalse(ok); self.assertEqual(d, "HTTP 403")
        def boom(*a, **k): raise ConnectionError("x")
        ok, d = app._send_budget_request({"Email": "a@b.co"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "me@x.co"}, post=boom)
        self.assertFalse(ok); self.assertEqual(d, "ConnectionError")
        for sec in ({}, {"RESEND_API_KEY": "k"}, {"ADMIN_EMAIL": "me@x.co"}):
            n = len(sent); ok, d = app._send_budget_request({"Email": "a@b.co"}, secrets=sec, post=lambda *a, **k: (sent.append(1) or R(200)))
            self.assertEqual((ok, d), (False, "not_configured")); self.assertEqual(len(sent), n)          # nothing transmitted, no invented address
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertNotRegex(src, r"BUDGET_REQUEST_TO\"\)\s*or\s*\"[^\"]+@")                                  # no hard-coded fallback address

    def test_html_in_form_values_is_escaped(self):
        _, app = run(BASEOV); sent = []
        class R: status_code = 200
        app._send_budget_request({"Name": "<script>x</script>", "Email": "a@b.co"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "m@x.co"}, post=lambda *a, **k: (sent.append(k) or R()))
        self.assertNotIn("<script>", sent[0]["json"]["html"])


class TestManagementAndLandingUI(unittest.TestCase):
    BASE = {**BASEOV, **RATE}

    def labels(self, st): return {(k, l) for k, l, key, d in st.widgets}

    def test_simplified_blocks_and_old_choices_removed(self):
        st, _ = run(self.BASE); w = self.labels(st); t = text(st)
        self.assertIn(("number_input", "Annual management fee"), w); self.assertIn(("selectbox", "Management fee currency"), w)
        self.assertIn("Management fees are not included in the reference costs.", t); self.assertIn("Management fees excluded.", t)
        self.assertIn(("checkbox", "Add additional costs per landing"), w)
        self.assertIn("Enter only costs not already covered by the reference costs or your programmes.", t)
        for old in ("Inclusion not confirmed", "Already included in the hourly costs", "Add separately", "(not in the base)", "Per-cycle costs", "None specified"):
            self.assertNotIn(old, t); self.assertFalse([1 for k, l in w if old in l], old)
        self.assertFalse([1 for k, l in w if l == "Management fee" or l.startswith("Management fee —")])         # no inclusion selector any more
        for lab in ("Additional cost per landing", "Average flight duration (hours)"): self.assertNotIn(("number_input", lab), w)   # hidden until ticked
        src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
        self.assertRegex(src, r'st\.expander\("⚙ Advanced adjustments",expanded=False\)')                         # closed by default
        i = src.index("⚙ Advanced adjustments"); j = src.index("Add additional costs per landing", i); self.assertLess(j, i + 3000)
        self.assertGreater(src.index("CAMO", i), i)                                                                    # CAMO / dispatch live inside the advanced section

    def test_per_landing_fields_appear_only_when_ticked(self):
        st, _ = run({**self.BASE, "Add additional costs per landing": True}); w = self.labels(st)
        for lab in ("Additional cost per landing", "Average flight duration (hours)"): self.assertIn(("number_input", lab), w)
        self.assertIn(("selectbox", "Currency per landing"), w)
        self.assertIn("untick the option", text(st))                                                               # unavailable until filled
        self.assertFalse([1 for k, a, kw in st.log if k == "metric" and "Total Annual Budget" in a[0]])

    def test_screen_budget_matches_engine_and_management_added_once(self):
        ov = {**self.BASE, "Annual management fee": 60000.0}
        st, _ = run(ov); st0, _ = run(self.BASE)
        v = lambda s_: float(next(m[1] for m in metrics(s_) if "Total Annual Budget" in m[0]).replace("$", "").replace(",", ""))
        self.assertAlmostEqual(v(st) - v(st0), 60000.0, delta=1.0)
        ov2 = {**ov, "Add additional costs per landing": True, "Additional cost per landing": 3000.0, "Average flight duration (hours)": 2.0}
        st2, _ = run(ov2); self.assertAlmostEqual(v(st2) - v(st), 3000.0 * 350.0 / 2.0, delta=1.0)               # 350 billed + 0 other (sidebar defaults)

    def test_camo_dispatch_checkbox_only_with_a_fee_and_no_double_count(self):
        w0 = self.labels(run(self.BASE)[0]); self.assertFalse([1 for k, l in w0 if "already covers CAMO" in l])
        ov = {**self.BASE, "Annual management fee": 60000.0, "CAMO — annual cost": 20000.0, "Dispatch / flight support — annual cost": 10000.0}
        w1 = self.labels(run(ov)[0]); self.assertIn(("checkbox", "My management fee already covers CAMO and dispatch"), w1)
        v = lambda s_: float(next(m[1] for m in metrics(s_) if "Total Annual Budget" in m[0]).replace("$", "").replace(",", ""))
        a = v(run({**self.BASE, "Annual management fee": 60000.0})[0]); b = v(run(ov)[0]); c = v(run({**ov, "My management fee already covers CAMO and dispatch": True})[0])
        self.assertAlmostEqual(b - a, 30000.0, delta=1.0); self.assertAlmostEqual(c - a, 0.0, delta=1.0)

    def test_exports_consistent_and_main_report_shows_only_active_adjustments(self):
        base = {**self.BASE, "📄 Generate PDF Report": True}
        off, _ = run(base)
        pdf0 = pdf_text(off.session_state["pdf_report"]["data"]); main0 = pdf0.split("Annex — assumptions and adjustments")[0]
        self.assertIn("Management fees excluded.", main0); self.assertNotIn("Advanced adjustments active", main0)
        self.assertNotIn("CAMO", main0); self.assertNotIn("per landing", main0)
        csv0 = csv_of(off); self.assertIn("additional_cost_per_landing,not enabled: nothing added", csv0)
        ov = {**base, "Annual management fee": 60000.0, "CAMO — annual cost": 20000.0, "Add additional costs per landing": True, "Additional cost per landing": 3000.0, "Average flight duration (hours)": 2.0}
        on, _ = run(ov)
        pdf1 = " ".join(pdf_text(on.session_state["pdf_report"]["data"]).split()); main1 = pdf1.split("Annex — assumptions and adjustments")[0]
        self.assertIn("Management fee entered: $ 60,000 per year, added once", main1)
        self.assertIn("Advanced adjustments active", main1); self.assertIn("CAMO", main1); self.assertIn("additional cost per landing", main1)
        annex = pdf1.split("Annex — assumptions and adjustments")[1]
        self.assertIn("Management fee: Added once", annex); self.assertIn("CAMO: Added", annex); self.assertIn("Dispatch / flight support: Not entered", annex); self.assertIn("not a confirmed zero", annex); self.assertIn("Additional cost per landing", annex)
        csv1 = csv_of(on)
        for need in ("management_management,Added once to the fixed costs", "management_camo,Added once to the fixed costs", "management_dispatch,Not entered", "management_note,Management fees are not included in the reference costs.",
                     "additional_cost_per_landing,added:"):
            k_, v_ = need.split(",", 1); self.assertRegex(csv1, re.escape(k_) + r',"?' + re.escape(v_), need)       # the CSV may quote a value that contains a comma
        self.assertNotEqual(on.session_state["pdf_report"]["hash"], off.session_state["pdf_report"]["hash"])

    def test_switching_an_adjustment_off_invalidates_the_old_pdf(self):
        ov = {**self.BASE, "Annual management fee": 60000.0, "📄 Generate PDF Report": True}
        st1, _ = run(ov); state = {"pdf_report": st1.session_state["pdf_report"]}
        for k in list(sys.modules):
            if k == "app" or k.startswith("streamlit") or k.startswith("plotly"): del sys.modules[k]
        st2 = F.install({**self.BASE}, state)                                    # fee removed
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        try: app.main()
        except F.StopApp: pass
        self.assertIn("is obsolete", text(st2)); self.assertFalse([1 for k, a, kw in st2.log if k == "download_button" and "PDF" in a[0]])


if __name__ == "__main__":
    unittest.main()
