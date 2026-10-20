"""
Targeted tests for the four corrections (strict Report reference, dated assumptions, PDF, wording).
Screens are exercised with tests/fake_streamlit.py (a recorder, NOT Streamlit): no browser rendering is covered here.
"""
import os, re, shutil, subprocess, sys, tempfile, unittest
from datetime import date, datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_engine as E  # noqa: E402
import menkor_report as RPT  # noqa: E402

BASE = E.load_base(); CHECKS, CONFLICTS, CONVS = E.load_checks(), E.load_conflicts(), E.load_conversions()
TODAY = date(2026, 10, 18)
FAL = "dassault_falcon_7x"


def row(aid): return BASE[BASE.aircraft_id == aid].iloc[0]          # Menkor cost base as shipped (selected costs +15 %, originals in original__ columns)


def raw_row(aid): return E.original_view(row(aid))                  # strictly original published values


def pdf_text(data, first=None, last=None):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "r.pdf")
        with open(p, "wb") as fh: fh.write(data)
        cmd = ["pdftotext", "-layout"] + (["-f", str(first), "-l", str(last)] if first else []) + [p, "-"]
        return subprocess.run(cmd, capture_output=True, text=True).stdout


def sim(aid=FAL, **kw):
    kw.setdefault("billed_hours", 350.0)
    return E.compute(row(aid), E.Scenario(aid, mode="simulation", **kw), today=TODAY)


def fuel(price=2.0, d="2020-01-01", confirm=False, **k):
    f = E.FuelConfig(price_source="manual", price=price, unit="L", currency="USD", validity_date=d, **k)
    if confirm: f.expired_confirmation = E.fuel_confirmation_token(f)
    return f


class TestStrictReference(unittest.TestCase):
    ORIG = dict(fixed=588918.0, variable=1048124.0, budget=1637042.0)

    def test_reference_equals_original_published_values_whatever_the_scenario(self):
        r = row(FAL); before = r.copy()
        scenarios = [dict(), dict(billed_hours=900.0, positioning_hours=80.0),
                     dict(fixed_overrides={"hangar": 1.0}, var_overrides_h={"catering": 9.0}, extra_fixed=5000.0, extra_var_h=50.0),
                     dict(fuel=fuel(price=2.0, d="2020-01-01"))]
        hashes = set()
        for kw in scenarios:
            res = E.compute(r, E.Scenario(FAL, mode="reference", **kw), today=TODAY)
            self.assertEqual((res["fixed"]["annual_total"], res["variable"]["annual"], res["budget_usd"]), (self.ORIG["fixed"], self.ORIG["variable"], self.ORIG["budget"]), kw)
            self.assertFalse(res["menkor_base"]["applied"]); self.assertEqual(res["hours"]["flown"], E.num(r, "reference_annual_hours"))
            self.assertFalse([c for c in res["components"] if c["edited"]])
            hashes.add(res["config_hash"])
        self.assertEqual(len(hashes), 1, "stored custom parameters must not change the identity of Report reference")
        self.assertTrue(r.equals(before), "the original base row must never be modified")
        self.assertEqual(E.num(BASE.loc[BASE.aircraft_id == FAL].iloc[0], "original__annual_budget_usd"), self.ORIG["budget"])
        self.assertEqual(E.num(BASE.loc[BASE.aircraft_id == FAL].iloc[0], "annual_budget_usd"), 1721495.45)     # the base itself holds the Menkor values

    def test_menkor_base_values_only_in_custom_simulation_with_amounts(self):
        raw = E.compute(raw_row(FAL), E.Scenario(FAL, mode="simulation", billed_hours=350.0), today=TODAY); adj = sim()
        a = adj["menkor_base"]
        self.assertTrue(a["applied"]); self.assertGreater(adj["budget_usd"], raw["budget_usd"])
        self.assertAlmostEqual(a["published_budget_original"], 1637042.0, delta=0.01)
        self.assertAlmostEqual(a["published_budget_adjusted"], 1721495.45, delta=0.01)     # Menkor cost base (~1,721,495 USD)
        self.assertAlmostEqual(a["delta_total"], 84453.45, delta=0.01)
        self.assertAlmostEqual(sum(i["delta"] for i in a["items"]), a["delta_total"], delta=0.01)
        self.assertTrue(all(abs(i["pct"] - 15.0) < 1e-6 for i in a["items"] if i["pct"] is not None))
        self.assertIn("The economic reference date is unknown", a["text"].replace("the economic", "The economic")); self.assertIn("not verified market inflation", a["text"])

    def test_adjusted_published_basis_vs_fuel_recalculation_difference_is_explained(self):
        adj = sim()            # at reference hours: 350 h
        rc = adj["reconciliation"]
        self.assertAlmostEqual(rc["published_budget"], 1721495.45, delta=0.01)
        self.assertAlmostEqual(rc["simulated_at_report_conditions"], 1719273.45, delta=0.01)   # burn x price recomputed
        self.assertAlmostEqual(rc["difference"], -2222.0, delta=0.01)                           # same -2,222 as on the ORIGINAL values: rounding, not the Menkor base
        raw = E.compute(raw_row(FAL), E.Scenario(FAL, mode="simulation", billed_hours=350.0), today=TODAY)
        self.assertAlmostEqual(rc["difference"], raw["reconciliation"]["difference"], delta=0.01)
        self.assertIn("rounded", rc["note"]); self.assertAlmostEqual(rc["adjustment_delta"], 84453.45, delta=0.01)

    def test_no_double_counting_user_edit_replaces_base_value(self):
        base = sim(); hg = next(c for c in base["components"] if c["key"] == "hangar")["annual_usd"]
        ed = sim(fixed_overrides={"hangar": 100000.0})
        self.assertAlmostEqual(ed["budget_usd"] - base["budget_usd"], 100000.0 - hg, delta=0.01)
        self.assertAlmostEqual(sum(c["annual_usd"] for c in ed["components"]), ed["budget_usd"], delta=1.0)


class TestScreens(unittest.TestCase):
    def run_app(self, ov=None, **kw):
        import smoke_support
        return smoke_support.run(ov or {}, **kw)

    def metric(self, st, label):
        return next(v for k, a, kw in st.log if k == "metric" and a[0].endswith(label) for v in [a[1]])

    def text(self, st):
        return " ".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "error", "info", "success"))

    def test_reference_screen_shows_original_values_and_disables_controls(self):
        st, _ = self.run_app({"Aircraft model": FAL, "Calculation mode": "Report reference"})
        self.assertEqual(self.metric(st, "Total Annual Budget"), "$ 1,637,042"); self.assertEqual(self.metric(st, "Annual Fixed Costs"), "$ 588,918")
        self.assertIn("Switch to Custom simulation to adjust costs.", self.text(st))
        dis = {(k, l): d for k, l, key, d in st.widgets}
        for w in [("slider", "Billed charter hours / year"),
                  ("radio", "Fuel price method"), ("selectbox", "Burn method"), ("number_input", "Hangar (USD/yr)"), ("number_input", "Extra fixed cost (USD/yr)")]:
            self.assertIn(w, dis, w); self.assertTrue(dis[w], w)
        self.assertFalse([1 for k, a, kw in st.log if k == "expander" and "Menkor cost base" in str(a[0])])
        self.assertFalse([l for _, l, _, _ in st.widgets if "adjust" in l.lower()], "no adjustment control exists any more")

    def test_simulation_screen_shows_menkor_base_items_pct_and_money_difference(self):
        st, _ = self.run_app({"Aircraft model": FAL, "Calculation mode": "Custom simulation"})
        dis = {(k, l): d for k, l, key, d in st.widgets}
        self.assertFalse(dis[("number_input", "Hangar (USD/yr)")])
        self.assertFalse([l for _, l, _, _ in st.widgets if "adjust" in l.lower() or "Update base" in l], "no adjustment toggle / percentage input")
        frames = [a[0] for k, a, kw in st.log if k == "dataframe" and hasattr(a[0], "columns") and "Menkor base (USD)" in list(a[0].columns)]
        self.assertTrue(frames); f = frames[0]
        self.assertIn("Difference (USD)", f.columns); self.assertIn("Original published (USD)", f.columns); self.assertIn("+15.0%", set(f["Change"]))
        self.assertIn("economic reference date is unknown", self.text(st))
        self.assertGreater(float(self.metric(st, "Total Annual Budget").replace("$", "").replace(",", "")), 1637042.0 - 5000)

    def test_roundtrip_modes_keeps_custom_parameters_and_widgets(self):
        ov = {"Aircraft model": FAL, "Hangar (USD/yr)": 100000.0,
              "Billed charter hours / year": 200.0}
        st1, app_mod = self.run_app({**ov, "Calculation mode": "Custom simulation"})
        st2, _ = self.run_app({**ov, "Calculation mode": "Report reference"})
        st3, _ = self.run_app({**ov, "Calculation mode": "Custom simulation"})
        self.assertEqual(self.metric(st1, "Total Annual Budget"), self.metric(st3, "Total Annual Budget"))
        self.assertEqual(self.metric(st2, "Total Annual Budget"), "$ 1,637,042")
        self.assertNotEqual(self.metric(st1, "Total Annual Budget"), "$ 1,637,042")
        k1 = {key for kd, _, key, _ in st1.widgets if key and kd != "button"}; k2 = {key for kd, _, key, _ in st2.widgets if key and kd != "button"}   # buttons hold no value
        self.assertFalse(k1 - k2 - set(app_mod._KEEP_KEYS), f"widgets removed in Report reference lose their stored value in Streamlit: {sorted(k1 - k2)}")

    def _fuel_ov(self, **extra):
        return {"Aircraft model": FAL, "Calculation mode": "Custom simulation", "Use a detailed local quote instead of the fuel price source above": True, "Price": 2.0,
                "Quote valid until (YYYY-MM-DD)": "2020-01-01", **extra}

    def test_expired_price_warns_blocks_then_confirmation_allows_and_resets(self):
        st, _ = self.run_app(self._fuel_ov())
        t = self.text(st); self.assertIn("EXPIRED", t); self.assertIn("not used until you explicitly confirm", t)
        self.assertFalse([1 for k, a, kw in st.log if k == "metric" and "Total Annual Budget" in a[0]])
        lab = "I confirm: use this expired price as a HISTORICAL assumption"
        st2, _ = self.run_app(self._fuel_ov(**{lab: True}))
        self.assertIn("HISTORICAL assumption after explicit user confirmation", self.text(st2))
        self.assertTrue([1 for k, a, kw in st2.log if k == "metric" and "Total Annual Budget" in a[0]])
        key = lambda s: [key_ for kind, l, key_, d in s.widgets if kind == "checkbox" and l == lab][0]
        st3, _ = self.run_app(self._fuel_ov(**{lab: True, "Price": 2.5}))
        st4, _ = self.run_app(self._fuel_ov(**{lab: True, "Quote valid until (YYYY-MM-DD)": "2020-01-02"}))
        self.assertEqual(len({key(st2), key(st3), key(st4)}), 3, "price or date change must produce a new (unchecked) confirmation widget")

    def test_invalid_and_unknown_dates_on_screen(self):
        st, _ = self.run_app(self._fuel_ov(**{"Quote valid until (YYYY-MM-DD)": "31/12/2026"}))
        self.assertIn("Invalid validity date", self.text(st))
        st, _ = self.run_app(self._fuel_ov(**{"Quote valid until (YYYY-MM-DD)": ""}))
        self.assertIn("Validity unknown", self.text(st)); self.assertTrue([1 for k, a, kw in st.log if k == "metric" and "Total Annual Budget" in a[0]])

    def test_screen_pdf_csv_consistency(self):
        lab = "I confirm: use this expired price as a HISTORICAL assumption"
        st, app_ = self.run_app(self._fuel_ov(**{lab: True, "📄 Generate PDF Report": True}))
        screen = self.metric(st, "Total Annual Budget")
        csv = next(a[1] for k, a, kw in st.log if k == "download_button" and "CSV" in a[0]).decode("utf-8-sig")
        pdf = st.session_state["pdf_report"]["data"]; txt = pdf_text(pdf)
        n = float(re.search(r"annual_budget_usd,([\d.]+)", csv).group(1))
        self.assertEqual(f"$ {round(n):,}", screen); self.assertIn(screen, txt)
        for needle in ("fuel_validity_status,expired", "fuel_expired_price_confirmed_as_historical,True", "fuel_validity_checked_on,", "fuel_validity_timezone,\"Asia/Dubai"):
            self.assertIn(needle, csv)
        self.assertIn("fuel price EXPIRED".lower(), txt.lower()); self.assertIn("HISTORICAL", txt)
        self.assertIn("EXPIRED", self.text(st))                                  # same warning on screen
        self.assertIn(st.session_state["pdf_report"]["hash"], txt)               # config id printed in the PDF
        self.assertRegex(txt, r"Generated \d{1,2} \w+ \d{4}")

    def test_pdf_obsolete_after_relevant_assumption_change(self):
        lab = "I confirm: use this expired price as a HISTORICAL assumption"
        st, _ = self.run_app(self._fuel_ov(**{lab: True, "📄 Generate PDF Report": True}))
        h = st.session_state["pdf_report"]["hash"]
        same, _ = self.run_app(self._fuel_ov(**{lab: True}), state=st.session_state)
        self.assertTrue([1 for k, a, kw in same.log if k == "download_button" and "PDF" in a[0]])
        for change in ({"Hangar (USD/yr)": 120000.0}, {"Price": 2.2}, {"Billed charter hours / year": 300.0}, {"Quote valid until (YYYY-MM-DD)": "2020-01-05"}):
            chg, _ = self.run_app(self._fuel_ov(**{lab: True, **change}), state={"pdf_report": dict(st.session_state["pdf_report"])})
            self.assertIn("obsolete", self.text(chg), change)
            self.assertFalse([1 for k, a, kw in chg.log if k == "download_button" and "PDF" in a[0]], change)

    def test_no_three_four_year_claim_anywhere(self):
        for fn in ("app.py", "menkor_engine.py", "menkor_report.py"):
            with open(os.path.join(ROOT, fn), encoding="utf-8") as fh: src = fh.read()
            self.assertNotRegex(src, r"3[-–]4 year|3 to 4 year|3-4 ans|Values 3|3–4 years", fn)
        t = E.menkor_base_text(E.menkor_base_info(row(FAL)))
        for needle in ("Menkor cost base", "+15%", "Menkor assumption, not verified market inflation", "economic reference date is unknown", "kept separately"):
            self.assertIn(needle, t)


class TestFuelDates(unittest.TestCase):
    def status(self, d, today=TODAY): return E.validity_status(d, today)["status"]

    def test_statuses(self):
        self.assertEqual(self.status(""), "unknown"); self.assertEqual(self.status(None), "unknown"); self.assertEqual(self.status("  "), "unknown")
        self.assertEqual(self.status("2026-10-18"), "valid")        # today: valid ("on or after today")
        self.assertEqual(self.status("2026-10-19"), "valid"); self.assertEqual(self.status("2030-01-01"), "valid")
        self.assertEqual(self.status("2026-10-17"), "expired"); self.assertEqual(self.status("2020-01-01"), "expired")
        for bad in ("2026-13-01", "2026-02-30", "31/12/2026", "2026-1-1", "tomorrow", "20261018", "2026-10-18T00:00"):
            v = E.validity_status(bad, TODAY); self.assertEqual(v["status"], "invalid", bad); self.assertIn("YYYY-MM-DD", v["message"])

    def test_today_is_computed_in_documented_timezone_never_hardcoded(self):
        self.assertEqual(E.current_date(datetime(2026, 10, 17, 21, 0, tzinfo=timezone.utc)), date(2026, 10, 18))   # 01:00 next day in Dubai
        self.assertEqual(E.current_date(datetime(2026, 10, 17, 19, 59, tzinfo=timezone.utc)), date(2026, 10, 17))
        self.assertEqual(E.current_date(), datetime.now(timezone(timedelta(hours=4))).date())
        self.assertIn("Dubai", E.BUSINESS_TZ_NAME)
        with open(os.path.join(ROOT, "menkor_engine.py"), encoding="utf-8") as fh: src = fh.read()
        self.assertNotRegex(src, r"date\(20\d\d,|fromisoformat\(['\"]20\d\d")

    def test_engine_flags_per_status(self):
        r = sim(fuel=fuel(d="")); self.assertTrue(r["available"]); self.assertIn("fuel_validity_unknown", [f["code"] for f in r["flags"]])
        r = sim(fuel=fuel(d="2026-10-18")); self.assertTrue(r["available"]); self.assertEqual(r["fuel_validity"]["status"], "valid")
        self.assertFalse([f for f in r["flags"] if f["code"].startswith("fuel_")])
        r = sim(fuel=fuel(d="2027-06-30")); self.assertTrue(r["available"])
        r = sim(fuel=fuel(d="2026-02-30")); self.assertFalse(r["available"]); self.assertIn("fuel_date_invalid", [f["code"] for f in r["flags"]])
        r = sim(fuel=fuel(d="2026-10-17")); self.assertFalse(r["available"]); self.assertIn("fuel_price_expired", [f["code"] for f in r["flags"]])
        self.assertEqual(r["fuel_validity"]["status"], "expired")

    def test_confirmation_and_reset_on_price_or_date_change(self):
        ok = sim(fuel=fuel(confirm=True)); self.assertTrue(ok["available"]); self.assertTrue(ok["fuel_validity"]["confirmed"])
        self.assertIn("fuel_price_expired_confirmed", [f["code"] for f in ok["flags"]])
        for mod in (dict(price=2.1), dict(d="2020-01-02"), dict(taxes_pct=5.0), dict(unit="USG"), dict(currency="USD", unit="L", price=2.0)):
            base = dict(price=2.0, d="2020-01-01"); base.update(mod)
            f = fuel(**{k: v for k, v in base.items() if k in ("price", "d")})
            f.expired_confirmation = E.fuel_confirmation_token(fuel(confirm=False))     # token of the ORIGINAL price/date
            for k_, v_ in mod.items():
                if k_ in ("taxes_pct", "unit", "currency"): setattr(f, k_, v_)
            r = sim(fuel=f)
            same_as_original = (mod == dict(currency="USD", unit="L", price=2.0))
            self.assertEqual(r["available"], same_as_original, mod)
        self.assertNotEqual(sim(fuel=fuel(confirm=True))["config_hash"], sim(fuel=fuel(confirm=False))["config_hash"])

    def test_status_travels_with_hash_so_pdf_expires(self):
        a = E.compute(row(FAL), E.Scenario(FAL, mode="simulation", billed_hours=350.0, fuel=fuel(d="2026-10-18", confirm=False)), today=date(2026, 10, 18))
        b = E.compute(row(FAL), E.Scenario(FAL, mode="simulation", billed_hours=350.0, fuel=fuel(d="2026-10-18", confirm=False)), today=date(2026, 10, 19))
        self.assertNotEqual(a["config_hash"], b["config_hash"])      # same inputs, but the price expired in between

    def test_dates_are_never_mixed_or_invented(self):
        d = E.dates_for(row(FAL)); self.assertEqual(d["economic_reference_date"], "unknown"); self.assertIsNone(d["consultation_date"]); self.assertTrue(d["extraction_date"])
        w = E.dates_for(row("bombardier_global_7500")); self.assertEqual(w["economic_reference_date"], "unknown"); self.assertTrue(w["consultation_date"])


class TestPdf(unittest.TestCase):
    @staticmethod
    def build(aid=FAL, mode="simulation", fx=None, **kw):
        r = row(aid); fx = fx or E.Fx("USD")
        res = E.compute(r, E.Scenario(aid, mode=mode, fx=fx, **kw), today=TODAY)
        return res, RPT.build_report_pdf(res, E.Display(fx), E.alerts_for(r, CHECKS, CONFLICTS, CONVS), generated_on=TODAY)

    CASES = [dict(aid=FAL, mode="simulation", billed_hours=350.0, positioning_hours=40.0, charter_rate=13000.0, commission_pct=10.0,
                  fuel=fuel(confirm=True), positioning_confirmed=True, private_hours_confirmed=True, other_fees_confirmed=True, limits_reviewed=True),
             dict(aid=FAL, mode="reference"),
             dict(aid="bombardier_global_7500", mode="simulation", billed_hours=300.0),
             dict(aid="airbus_340", mode="simulation", billed_hours=100.0, charter_rate=19000.0, charter_rate_ccy="EUR", fx=E.Fx("EUR", 0.92, "2026-10-18"))]

    def test_logo_on_every_page_and_bundled_file_is_found(self):
        from pathlib import Path
        logo = (Path(__file__).resolve().parent.parent / "menkor_logo.png").read_bytes()
        self.assertTrue(logo.startswith(b"\x89PNG"))
        r = row(FAL); fx = E.Fx("USD")
        res = E.compute(r, E.Scenario(FAL, mode="simulation", fx=fx, billed_hours=350.0), today=TODAY)
        pdf = RPT.build_report_pdf(res, E.Display(fx), E.alerts_for(r, CHECKS, CONFLICTS, CONVS), logo_bytes=logo, generated_on=TODAY)
        try:
            import pypdf
        except ImportError:
            self.skipTest("pypdf not installed")
        rd = pypdf.PdfReader(__import__("io").BytesIO(pdf))
        for pg in rd.pages:
            self.assertTrue(any(v.get_object().get("/Subtype") == "/Image" for v in pg["/Resources"].get("/XObject", {}).values()), "logo missing on a page")
        src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
        ns = {"base64": __import__("base64")}
        exec(src[src.index("def _get_logo():"):src.index("# ─── DATABASE & ENGINE")].replace("__file__", repr(str(Path(__file__).resolve().parent.parent / "app.py"))), ns)
        self.assertEqual(__import__("base64").b64decode(ns["_get_logo"]()), logo, "bundled logo is loaded first")

    def test_fonts_embedded_and_no_character_spacing(self):
        res, pdf = self.build(**self.CASES[0])
        fonts = subprocess.run(["pdffonts", "-"], input=pdf, capture_output=True).stdout.decode()
        lib = [l for l in fonts.splitlines() if "Liberation" in l]
        self.assertTrue(lib and all(" yes yes yes " in l for l in lib), fonts)
        try:
            import pypdf
        except ImportError:
            self.skipTest("pypdf not installed")
        rd = pypdf.PdfReader(__import__("io").BytesIO(pdf))
        for pg in rd.pages:
            c = pg.get_contents().get_data().decode("latin1")
            self.assertEqual([m for m in re.findall(r"(-?[\d.]+) Tc\b", c) if float(m) != 0.0], [], "no character spacing anywhere")
            used = set(re.findall(r"/(F[\d+]+) [\d.]+ Tf", c)); res_f = {k.lstrip("/"): v.get_object().get("/BaseFont") for k, v in pg["/Resources"]["/Font"].items()}
            for u in used:
                self.assertIn("Liberation", str(res_f.get(u)), f"unembedded font used: {res_f.get(u)}")

    def test_summary_first_and_technical_details_in_annex(self):
        for case in self.CASES:
            res, pdf = self.build(**case); txt = pdf_text(pdf)
            head, annex = txt.split("Annex — assumptions and adjustments")
            p1 = pdf_text(pdf, 1, 1)
            for needle in ("AVIATION COST REPORT", res["model"], "Annual budget", "Cost per flown hour", "Essential assumptions", "Currency", "Mode", "Hours"):
                self.assertIn(needle, p1, (case["aid"], needle))
            for tech in ("aircraft_id", "tol.", "fuel_burn_l_per_h", "reference_fuel_price_usd_per_l", "Rounding vs", "observed"):
                self.assertNotIn(tech, txt, (case["aid"], tech))          # nowhere in the client report, annex included
            self.assertIn("economic reference date", p1.lower())
            self.assertIn("Scenario reference", annex)
            self.assertIn(res["config_hash"], txt); self.assertIn("Generated 18 October 2026", txt)

    def test_material_warnings_visible_on_first_page(self):
        p1 = pdf_text(self.build(**self.CASES[0])[1], 1, 1)
        for n in ("EXPIRED", "HISTORICAL", "not a net profit", "Menkor cost base"):
            self.assertIn(n, p1)
        p1w = pdf_text(self.build(**self.CASES[2])[1], 1, 1); self.assertIn("Partial data", p1w)
        self.assertIn("original published values", " ".join(pdf_text(self.build(**self.CASES[1])[1], 1, 1).split()))

    def test_amounts_formatted_no_raw_floats_no_negative_zero(self):
        self.assertEqual(RPT.fmt_pct(-0.0001), "0.0%"); self.assertEqual(RPT.fmt_pct(-0.04, 1), "0.0%"); self.assertEqual(RPT.fmt_pct(-0.13, 2), "-0.13%")
        for case in self.CASES:
            txt = pdf_text(self.build(**case)[1]); main = txt.split("Annex — assumptions and adjustments")[0]
            self.assertNotRegex(txt, r"[-−]\s?0\.0%"); self.assertNotRegex(main, r"\d\.\d{5,}")
            self.assertNotRegex(txt, r"[$€] [-−]\d"); self.assertNotRegex(main.lower(), r"\bnan\b")

    def test_tables_not_split_with_single_row_and_headings_not_orphaned(self):
        for case in self.CASES:
            pdf = self.build(**case)[1]
            n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", "-"], input=pdf, capture_output=True).stdout.decode()).group(1))
            for p in range(1, n + 1):
                lines = [l for l in pdf_text(pdf, p, p).splitlines() if l.strip() and "Menkor Aviation GBL — Confidential" not in l]
                for i, l in enumerate(lines):
                    if re.match(r"\s*(\d\.\s|[A-C]\.\s)", l) and not l.strip().startswith("1 further"):
                        self.assertGreaterEqual(len(lines) - i - 1, 1, f"orphan heading on page {p}: {l.strip()}")
            full = pdf_text(pdf)
            for head_, last_ in (("1. Cost summary", "Total cost per flown hour"), ("3. Charter profitability", "ESTIMATED OPERATING RESULT")):
                if head_ in full and last_ in full:
                    pg = [q for q in range(1, n + 1) if head_ in pdf_text(pdf, q, q)]
                    self.assertTrue(last_ in pdf_text(pdf, pg[0], pg[0]) or head_.startswith("3.") and "Not calculated" in full, f"table split after its heading: {head_}")

    def test_pdf_obsolete_hash_changes_with_each_relevant_assumption(self):
        base = dict(aircraft_id=FAL, mode="simulation", billed_hours=350.0)
        h0 = E.Scenario(**base).config_hash()
        for ch in (dict(billed_hours=360.0), dict(positioning_hours=10.0), dict(fixed_overrides={"hangar": 5.0}),
                   dict(charter_rate=9000.0), dict(commission_pct=5.0), dict(fuel=fuel()), dict(rate_basis="net"), dict(positioning_confirmed=True), dict(limits_reviewed=True), dict(depreciation_annual=0.0),
                   dict(management={"camo": {"status": "added", "amount": 1.0, "ccy": "USD"}}), dict(cycle_status="added"), dict(positioning_ratio=0.1),
                   dict(supplements_retained_usd=1000.0), dict(supplements_cost_usd=500.0)):
            self.assertNotEqual(E.Scenario(**{**base, **ch}).config_hash(), h0, ch)


class TestCss(unittest.TestCase):
    """Static checks of the CSS/theme; the contrast measurement in a real Chromium is tools/check_css_contrast.py (run below when available)."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh: src = fh.read()
        cls.css = re.search(r'st\.markdown\("""<style>(.*?)</style>""", unsafe_allow_html=True\)', src, re.S).group(1)

    def test_no_generated_class_selectors(self):
        code = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)          # comments may mention the word
        self.assertNotRegex(code, r"emotion|\.css-[0-9a-z]+|st-[a-z]{2}\b")
        selectors = re.findall(r"([^{}]+)\{", code)
        for sel in selectors:
            for part in sel.split(","):
                self.assertFalse(re.search(r"\.(st[A-Z]\w*|css-\w+)", part.replace(".stApp", "").replace(".stButton", "")), part)

    def test_theme_file_and_palette(self):
        with open(os.path.join(ROOT, ".streamlit", "config.toml"), encoding="utf-8") as fh: t = fh.read()
        for needle in ('base = "dark"', 'primaryColor = "#C9A84C"', 'backgroundColor = "#0B1629"', "enableStaticServing = true"):
            self.assertIn(needle, t)

    def test_every_widget_family_and_state_is_covered(self):
        for needle in ('[data-baseweb="select"]', '[data-baseweb="popover"]', '[role="option"]', '[data-testid="stExpander"] details > summary', "input:disabled",
                       "::placeholder", ":hover", ":focus-within", 'aria-selected="true"', "aria-disabled", "@media (max-width: 640px)", "-webkit-text-fill-color"):
            self.assertIn(needle, self.css, needle)

    def test_contrast_in_real_chromium_when_available(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            self.skipTest("playwright not installed")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_css_contrast.py"), tempfile.mkdtemp()], capture_output=True, text=True, timeout=240)
        if "Executable doesn't exist" in r.stderr or "BrowserType.launch" in r.stderr:
            self.skipTest("no Chromium available")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("failures: []", r.stdout)
        self.assertRegex(r.stdout, r"OLD css failures.*select value")


if __name__ == "__main__":
    unittest.main(verbosity=2)
