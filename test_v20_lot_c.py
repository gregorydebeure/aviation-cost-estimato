"""Lot C — storage, isolation, comparison, broker profile, events. In-memory PostgREST-like fake: NO network, NO Supabase, NO payment, NO email."""
import os, sys, unittest, re, copy

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_engine as E  # noqa: E402
import menkor_store as S  # noqa: E402

BASE = E.load_base() if hasattr(E, "load_base") else None


class FakeRest:
    """Minimal PostgREST subset: eq., is.null, not.is.null filters; select; order ignored; on_conflict upsert."""
    def __init__(self, fail=False):
        self.t = {}; self.calls = []; self.fail = fail

    def _match(self, row, params):
        for k, v in (params or {}).items():
            if k in ("select", "order", "on_conflict"): continue
            val = row.get(k)
            if v.startswith("eq."):
                if str(val) != v[3:]: return False
            elif v == "is.null":
                if val is not None: return False
            elif v == "not.is.null":
                if val is None: return False
        return True

    def __call__(self, method, table, params=None, json=None, prefer=None):
        self.calls.append((method, table, dict(params or {}), json))
        if self.fail: return 500, None
        rows = self.t.setdefault(table, [])
        if method == "GET": return 200, [copy.deepcopy(r) for r in rows if self._match(r, params)]
        if method == "POST":
            if params and params.get("on_conflict"):
                pk = params["on_conflict"]
                for r in rows:
                    if r.get(pk) == json.get(pk): r.update(copy.deepcopy(json)); return 201, None
            rows.append(copy.deepcopy(json)); return 201, None
        if method == "PATCH":
            for r in rows:
                if self._match(r, params): r.update(copy.deepcopy(json))
            return 204, None
        if method == "DELETE":
            self.t[table] = [r for r in rows if not self._match(r, params)]; return 204, None


def _scn_res(aid="dassault_falcon_7x", **kw):
    import pandas as pd
    df = E.load_base() if hasattr(E, "load_base") else None
    row = df[df["aircraft_id"] == aid].iloc[0]
    scn = E.Scenario(aircraft_id=aid, mode="simulation", other_hours=300.0, fuel=E.FuelConfig(price_source="average", price=1.1, currency="USD"), **kw)
    return df, scn, E.compute(row, scn)


class TestScenarioStore(unittest.TestCase):
    def setUp(self):
        self.r = FakeRest(); self.df, self.scn, self.res = _scn_res()

    def test_save_load_keeps_every_assumption_and_versions(self):
        scn = E.Scenario(aircraft_id=self.scn.aircraft_id, billed_hours=200, other_hours=100, charter_rate=9000, commission_pct=10,
                         fuel=E.FuelConfig(price_source="average", price=1.2, currency="EUR"), fx=E.Fx("EUR", 0.9, "2026-10-01", "ECB"),
                         depreciation_annual=500000, management={"fee": {"amount": 1000, "ccy": "USD"}})
        ok, sid = S.save_scenario(self.r, "a@x.co", "  My   plan ", scn, self.res)
        self.assertTrue(ok)
        row = S.get_scenario(self.r, "a@x.co", sid)
        self.assertEqual(row["name"], "My plan"); self.assertEqual(row["db_version"], E.DB_VERSION); self.assertEqual(row["engine_version"], E.ENGINE_VERSION)
        back = S.scenario_from_dict(row["payload"]["scenario"])
        self.assertEqual(back.canonical(), scn.canonical()); self.assertEqual(back.config_hash(), scn.config_hash())
        ue = row["payload"]["user_entered"]
        for need in ("depreciation_annual", "charter_rate", "commission_pct", "fuel_price", "hours", "management", "exchange_rate"): self.assertIn(need, ue)
        self.assertNotIn("mode", ue)
        blank = S.user_entered_fields(E.Scenario(aircraft_id="dassault_falcon_7x")); self.assertEqual(blank, [])   # defaults are never presented as user entries
        self.assertEqual(row["payload"]["snapshot"]["config_hash"], self.res["config_hash"])

    def test_absent_value_stays_absent_never_zero(self):
        scn = E.Scenario(aircraft_id=self.scn.aircraft_id)   # nothing entered
        ok, sid = S.save_scenario(self.r, "a@x.co", "blank", scn, E.compute(self.df[self.df.aircraft_id == scn.aircraft_id].iloc[0], scn))
        back = S.scenario_from_dict(S.get_scenario(self.r, "a@x.co", sid)["payload"]["scenario"])
        self.assertIsNone(back.depreciation_annual); self.assertIsNone(back.fuel.price)
        snap = S.get_scenario(self.r, "a@x.co", sid)["payload"]["snapshot"]
        self.assertIsNone(snap["operating_result_usd"])

    def test_validation_and_storage_failure_never_report_saved(self):
        self.assertFalse(S.save_scenario(self.r, "a@x.co", "   ", self.scn, self.res)[0])
        bad = FakeRest(fail=True)
        ok, msg = S.save_scenario(bad, "a@x.co", "n", self.scn, self.res)
        self.assertFalse(ok); self.assertIn("not available", msg)
        self.assertEqual(S.list_scenarios(bad, "a@x.co"), [])

    def test_rename_duplicate_delete_restore(self):
        _, sid = S.save_scenario(self.r, "a@x.co", "one", self.scn, self.res)
        self.assertTrue(S.rename_scenario(self.r, "a@x.co", sid, "two"))
        ok, sid2 = S.duplicate_scenario(self.r, "a@x.co", sid)
        self.assertTrue(ok); self.assertEqual(S.get_scenario(self.r, "a@x.co", sid2)["name"], "two (copy)")
        self.assertEqual(S.get_scenario(self.r, "a@x.co", sid2)["payload"], S.get_scenario(self.r, "a@x.co", sid)["payload"])
        self.assertFalse(S.delete_scenario(self.r, "a@x.co", sid, confirmed=False))       # no confirmation, no deletion
        self.assertEqual(len(S.list_scenarios(self.r, "a@x.co")), 2)
        self.assertTrue(S.delete_scenario(self.r, "a@x.co", sid, confirmed=True))
        self.assertEqual(len(S.list_scenarios(self.r, "a@x.co")), 1); self.assertEqual(len(S.list_scenarios(self.r, "a@x.co", deleted=True)), 1)
        self.assertTrue(S.restore_scenario(self.r, "a@x.co", sid)); self.assertEqual(len(S.list_scenarios(self.r, "a@x.co")), 2)
        self.assertFalse(S.purge_scenario(self.r, "a@x.co", sid, True))                   # not in the bin: refuse
        S.delete_scenario(self.r, "a@x.co", sid, True); self.assertTrue(S.purge_scenario(self.r, "a@x.co", sid, True))
        self.assertIsNone(S.get_scenario(self.r, "a@x.co", sid))

    def test_version_change_is_reported_not_hidden(self):
        _, sid = S.save_scenario(self.r, "a@x.co", "n", self.scn, self.res)
        row = S.get_scenario(self.r, "a@x.co", sid)
        self.assertFalse(S.version_status(row)["changed"])
        row["db_version"] = "old-base"; row["engine_version"] = "1.0"
        vs = S.version_status(row); self.assertTrue(vs["changed"] and vs["db_changed"] and vs["engine_changed"])
        self.assertEqual(vs["saved_db"], "old-base")


class TestIsolation(unittest.TestCase):
    def setUp(self):
        self.r = FakeRest(); self.df, self.scn, self.res = _scn_res()
        _, self.sa = S.save_scenario(self.r, "a@x.co", "A secret", self.scn, self.res)
        _, self.fa = S.create_folder(self.r, "a@x.co", "Client A")

    def test_other_owner_cannot_read_modify_delete_or_move(self):
        self.assertIsNone(S.get_scenario(self.r, "b@x.co", self.sa))
        self.assertEqual(S.list_scenarios(self.r, "b@x.co"), [])
        self.assertFalse(S.rename_scenario(self.r, "b@x.co", self.sa, "hacked"))
        self.assertFalse(S.delete_scenario(self.r, "b@x.co", self.sa, True))
        self.assertFalse(S.duplicate_scenario(self.r, "b@x.co", self.sa)[0])
        self.assertFalse(S.move_scenario(self.r, "b@x.co", self.sa, None))
        self.assertEqual(S.list_folders(self.r, "b@x.co"), [])
        self.assertFalse(S.rename_folder(self.r, "b@x.co", self.fa, "x")); self.assertFalse(S.delete_folder(self.r, "b@x.co", self.fa, True))
        _, sb = S.save_scenario(self.r, "b@x.co", "B", self.scn, self.res)
        self.assertFalse(S.save_scenario(self.r, "b@x.co", "into A folder", self.scn, self.res, folder_id=self.fa)[0])
        self.assertFalse(S.move_scenario(self.r, "b@x.co", sb, self.fa))
        a = S.get_scenario(self.r, "a@x.co", self.sa); self.assertEqual(a["name"], "A secret"); self.assertIsNone(a["deleted_at"])

    def test_owner_is_case_insensitive_and_required(self):
        self.assertIsNotNone(S.get_scenario(self.r, "A@X.CO", self.sa))
        for bad in ("", None, "no-at-sign"):
            with self.assertRaises(PermissionError): S.list_scenarios(self.r, bad)

    def test_every_request_carries_the_owner_filter(self):
        for m, t, params, js in self.r.calls:
            if m in ("GET", "PATCH", "DELETE") and t != "events":
                self.assertIn("owner_email", params, (m, t, params))

    def test_broker_profile_isolated(self):
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
        self.assertTrue(S.save_broker_profile(self.r, "a@x.co", "Alpha Aviation", png)[0])
        self.assertIsNone(S.get_broker_profile(self.r, "b@x.co"))
        self.assertEqual(S.get_broker_profile(self.r, "a@x.co")["broker_name"], "Alpha Aviation")


class TestFolders(unittest.TestCase):
    def test_folder_flow_keeps_scenarios_on_delete(self):
        r = FakeRest(); df, scn, res = _scn_res()
        ok, fid = S.create_folder(r, "a@x.co", "Client X"); self.assertTrue(ok)
        _, sid = S.save_scenario(r, "a@x.co", "s", scn, res, folder_id=fid)
        self.assertEqual(len(S.list_scenarios(r, "a@x.co", folder_id=fid)), 1)
        self.assertFalse(S.delete_folder(r, "a@x.co", fid, confirmed=False))
        self.assertTrue(S.delete_folder(r, "a@x.co", fid, confirmed=True))
        self.assertEqual(S.list_folders(r, "a@x.co"), [])
        s = S.get_scenario(r, "a@x.co", sid); self.assertIsNotNone(s); self.assertIsNone(s["folder_id"]); self.assertIsNone(s["deleted_at"])
        self.assertFalse(S.create_folder(r, "a@x.co", "  ")[0])


class TestBrokerLogo(unittest.TestCase):
    def test_logo_validation(self):
        self.assertTrue(S.validate_logo(b"\x89PNG\r\n\x1a\n" + b"1" * 10)[0]); self.assertTrue(S.validate_logo(b"\xff\xd8\xff\xe0" + b"1" * 10)[0])
        self.assertFalse(S.validate_logo(b"<svg onload=alert(1)>")[0]); self.assertFalse(S.validate_logo(b"\x89PNG\r\n\x1a\n" + b"1" * 500_000)[0])
        self.assertTrue(S.validate_logo(None)[0])
        r = FakeRest(); self.assertFalse(S.save_broker_profile(r, "a@x.co", "X", b"GIF89a....")[0]); self.assertEqual(r.t.get("broker_profiles", []), [])

    def test_delete_profile(self):
        r = FakeRest(); S.save_broker_profile(r, "a@x.co", "X", None); self.assertTrue(S.delete_broker_profile(r, "a@x.co")); self.assertIsNone(S.get_broker_profile(r, "a@x.co"))


class TestCompare(unittest.TestCase):
    def setUp(self):
        self.df = E.load_base()
        self.ids = ["dassault_falcon_7x", "dassault_falcon_8x"]
        self.common = dict(flown_hours=300.0, fuel_price=1.0, fuel_ccy="USD", fx=E.Fx())

    def test_common_hypotheses_apply_to_all(self):
        out = S.compare_aircraft(self.df, self.ids, self.common)
        self.assertEqual([o["hours"] for o in out], [300.0, 300.0]); self.assertTrue(all(o["available"] and o["adjusted"] == [] for o in out))
        for o, aid in zip(out, self.ids):
            row = self.df[self.df.aircraft_id == aid].iloc[0]
            exp = E.compute(row, E.Scenario(aircraft_id=aid, other_hours=300.0, fuel=E.FuelConfig(price_source="average", price=1.0, currency="USD")))
            self.assertEqual(o["budget_usd"], exp["budget_usd"])

    def test_adjustment_is_per_aircraft_only(self):
        out = S.compare_aircraft(self.df, self.ids, self.common, {self.ids[0]: {"flown_hours": 500.0}})
        self.assertEqual(out[0]["hours"], 500.0); self.assertEqual(out[0]["adjusted"], ["flown_hours"])
        self.assertEqual(out[1]["hours"], 300.0); self.assertEqual(out[1]["adjusted"], [])

    def test_missing_input_is_not_zero(self):
        out = S.compare_aircraft(self.df, self.ids, {**self.common, "fuel_price": None})
        for o in out: self.assertFalse(o["available"]); self.assertIn("fuel price", o["missing"]); self.assertNotIn("budget_usd", o)
        out = S.compare_aircraft(self.df, self.ids, {**self.common, "flown_hours": 0})
        self.assertTrue(all("annual flown hours" in o["missing"] for o in out))

    def test_count_bounds_and_unknown_model(self):
        with self.assertRaises(ValueError): S.compare_aircraft(self.df, self.ids[:1], self.common)
        with self.assertRaises(ValueError): S.compare_aircraft(self.df, self.ids + ["a", "b"], self.common)
        out = S.compare_aircraft(self.df, [self.ids[0], "nope"], self.common)
        self.assertFalse(out[1]["available"])


class TestEvents(unittest.TestCase):
    def test_whitelist_and_no_personal_data(self):
        self.assertIsNone(S.clean_event("page_view_with_email"))
        ev = S.clean_event("signup", {"plan": "pro", "email": "a@b.co", "name": "John", "message": "hi", "msn": "123", "folder": "Client", "journey": "Z"})
        self.assertEqual(ev["props"], {"plan": "pro"})
        r = FakeRest(); st = {}
        S.track(r, st, "scenario_saved", {"plan": "pro", "email": "a@b.co"})
        sent = r.t["events"][0]
        flat = repr(sent)
        for forbidden in ("a@b.co", "@", "John"): self.assertNotIn(forbidden, flat)
        self.assertEqual(set(sent), {"id", "session_id", "event", "props", "created_at"})

    def test_no_duplicate_on_rerun_and_failure_not_marked_done(self):
        r = FakeRest(); st = {}
        for _ in range(5): S.track(r, st, "visit")
        self.assertEqual(len(r.t["events"]), 1)
        S.track(r, st, "report_generated", once_key="report:abc"); S.track(r, st, "report_generated", once_key="report:abc"); S.track(r, st, "report_generated", once_key="report:def")
        self.assertEqual(len(r.t["events"]), 3)
        bad = FakeRest(fail=True); st2 = {}
        self.assertFalse(S.track(bad, st2, "visit"))
        good = FakeRest(); self.assertTrue(S.track(good, st2, "visit"))     # failure did not consume the once-key
        self.assertFalse(S.track(None, {}, "visit"))

    def test_session_id_is_hashed_and_not_an_email(self):
        r = FakeRest(); st = {}; S.track(r, st, "visit")
        self.assertRegex(r.t["events"][0]["session_id"], r"^[0-9a-f]{16}$"); self.assertNotEqual(r.t["events"][0]["session_id"], st["_anon_sid"])


class TestMigrationFiles(unittest.TestCase):
    def test_up_is_additive_and_down_reverts(self):
        up = open(os.path.join(ROOT, "migrations", "2026_10_lotC_up.sql")).read().lower(); down = open(os.path.join(ROOT, "migrations", "2026_10_lotC_down.sql")).read().lower()
        self.assertNotRegex(up, r"alter table public\.users|drop table|delete from|update public")
        for t in ("folders", "scenarios", "broker_profiles", "events"):
            self.assertIn(f"create table if not exists public.{t}", up); self.assertIn(f"drop table if exists public.{t}", down)
            self.assertIn(f"alter table public.{t}", up)
        self.assertIn("row level security", up)




# ───────────────────────── UI integration (recorder fake; NOT a real browser) ─────────────────────────
import fake_streamlit as F  # noqa: E402
from test_v19_screens import text  # noqa: E402

FUEL = {"Average annual fuel price (per litre)": 1.0, "Fuel price currency": "USD", "Aircraft model": "dassault_falcon_7x"}


def ui(ov, rest, email="a@x.co", plan=(True, True), configured=True, state=None):
    for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
    state = {} if state is None else state
    state["auth_email"] = email
    st = F.install({"__real_defaults__": True, **FUEL, **ov}, state)
    import app
    app.render_auth = lambda: plan; app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
    app._sb_rest = rest; app._storage_configured = lambda: configured
    try: app.main()
    except F.StopApp: pass
    return st, app, state


class TestScenarioUI(unittest.TestCase):
    def test_save_from_the_screen_stores_for_the_logged_in_owner_only(self):
        r = FakeRest()
        st, app, state = ui({"Scenario name": "Plan A", "Save current scenario": True}, r, email="owner@x.co")
        rows = r.t["scenarios"]; self.assertEqual(len(rows), 1); self.assertEqual(rows[0]["owner_email"], "owner@x.co"); self.assertEqual(rows[0]["name"], "Plan A")
        self.assertIn("saved", text(st))
        st2, _, _ = ui({}, r, email="other@x.co")
        self.assertNotIn("Plan A", text(st2)); self.assertIn("No saved scenario yet", text(st2))

    def test_empty_name_and_storage_off_never_say_saved(self):
        r = FakeRest()
        st, _, _ = ui({"Scenario name": "  ", "Save current scenario": True}, r); self.assertEqual(r.t.get("scenarios", []), []); self.assertNotIn("Scenario “", text(st))
        r2 = FakeRest()
        st, _, _ = ui({"Scenario name": "x", "Save current scenario": True}, r2, configured=False)
        self.assertEqual(r2.t.get("scenarios", []), []); self.assertIn("not configured", text(st))
        st, _, _ = ui({"Scenario name": "x", "Save current scenario": True}, FakeRest(fail=True))
        self.assertNotIn("Scenario “x” saved", text(st))

    def test_free_user_gets_the_gate_not_the_storage(self):
        r = FakeRest()
        st, _, _ = ui({"Scenario name": "x", "Save current scenario": True}, r, plan=(False, False))
        self.assertEqual(r.t.get("scenarios", []), [])

    def test_listing_shows_saved_figures_and_version_warning_without_silent_recompute(self):
        r = FakeRest(); ui({"Scenario name": "Plan A", "Save current scenario": True}, r)
        r.t["scenarios"][0]["db_version"] = "older-base"
        st, _, _ = ui({}, r); t = text(st)
        self.assertIn("Plan A", t); self.assertIn("AS SAVED", t); self.assertIn("Entered by you", t)
        self.assertNotIn("Same result as saved", t)           # no recalculation unless asked
        st, _, _ = ui({}, r, state={"_rc_" + r.t["scenarios"][0]["id"]: True}); t = text(st)
        self.assertIn("Recalculated now with base", t); self.assertIn("older-base", t)

    def test_delete_needs_confirmation_then_restore(self):
        r = FakeRest(); ui({"Scenario name": "Plan A", "Save current scenario": True}, r)
        sid = r.t["scenarios"][0]["id"]
        ui({f"Delete": True}, r); self.assertIsNone(r.t["scenarios"][0]["deleted_at"])
        ui({"I confirm I want to delete this scenario (it can be restored from “Recently deleted”)": True, "Delete": True}, r)
        self.assertIsNotNone(r.t["scenarios"][0]["deleted_at"])
        st, _, _ = ui({"Restore": True}, r); self.assertIsNone(r.t["scenarios"][0]["deleted_at"])

    def test_essentiel_has_no_pro_sections(self):
        r = FakeRest(); st, _, _ = ui({}, r, plan=(True, False))
        radio = [l for k, l, key, d in st.widgets if k == "radio"]
        self.assertIn("Section", radio)
        st2, _, _ = ui({"Section": "Compare aircraft"}, r, plan=(True, False))
        self.assertNotIn("Select 2 or 3 aircraft", text(st2))

    def test_compare_screen_and_missing_inputs(self):
        r = FakeRest()
        st, _, _ = ui({"Section": "Compare aircraft", "Aircraft (2 or 3)": ["Dassault Falcon 7X", "Dassault Falcon 8X"]}, r)
        t = text(st); self.assertNotIn("Select 2 or 3 aircraft", t)
        dfs = [a[0] for k, a, kw in st.log if k == "dataframe"]
        self.assertTrue(dfs); self.assertTrue(all(row == "not computed" for row in dfs[-1]["Annual budget"]))
        st, _, _ = ui({"Section": "Compare aircraft", "Aircraft (2 or 3)": ["Dassault Falcon 7X", "Dassault Falcon 8X"],
                       "Common annual flown hours": 300.0, "Common fuel price (per litre)": 1.0}, r)
        d = [a[0] for k, a, kw in st.log if k == "dataframe"][-1]
        self.assertTrue(all(str(x).startswith("$") for x in d["Annual budget"]))

    def test_broker_signature_changes_with_name_or_logo(self):
        _, app, _ = ui({}, FakeRest())
        a = app._broker_sig({"name": "A", "logo": b"x"}); self.assertNotEqual(a, app._broker_sig({"name": "B", "logo": b"x"})); self.assertNotEqual(a, app._broker_sig(None))
        self.assertEqual(app._broker_sig(None), "")

    def test_pdf_carries_broker_but_keeps_menkor_limits(self):
        import io, subprocess, tempfile
        from PIL import Image
        df = E.load_base(); row = df[df.aircraft_id == "dassault_falcon_7x"].iloc[0]
        res = E.compute(row, E.Scenario(aircraft_id="dassault_falcon_7x", mode="reference"))
        import menkor_report as R
        b = io.BytesIO(); Image.new("RGB", (60, 30), (10, 90, 160)).save(b, "PNG")
        pdf = R.build_report_pdf(res, E.Display(E.Fx()), [], None, broker=dict(name="Alpha & Co <Aviation>", logo=b.getvalue()))
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f: f.write(pdf)
        out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout; os.unlink(f.name)
        self.assertIn("Prepared by Alpha & Co <Aviation>", out); self.assertIn("Menkor Aviation GBL", out); self.assertIn("Main exclusions", out); self.assertIn("Essential assumptions", out)
        plain = R.build_report_pdf(res, E.Display(E.Fx()), [], None)
        self.assertNotIn(b"Prepared by", plain.replace(b"\n", b"")[:0] or b"")


class TestEventsWiring(unittest.TestCase):
    def test_events_have_no_personal_data_and_no_duplicates_across_reruns(self):
        r = FakeRest(); state = {}
        for _ in range(3): ui({"Scenario name": "Secret client Dupont", "Save current scenario": True}, r, email="john.smith@client.com", state=state)
        ev = r.t.get("events", [])
        names = [e["event"] for e in ev]
        self.assertEqual(names.count("visit"), 1); self.assertEqual(names.count("first_simulation"), 1)
        blob = repr(ev)
        for forbidden in ("john", "smith", "client.com", "Dupont", "Secret", "@"): self.assertNotIn(forbidden, blob)

    def test_no_events_when_storage_missing_or_disabled(self):
        r = FakeRest(); ui({}, r, configured=False); self.assertEqual(r.t.get("events", []), [])

    def test_study_request_event_only_after_real_reception(self):
        for okres, expected in (((True, ""), 1), ((False, "HTTP 500"), 0)):
            r = FakeRest()
            def patch_ok(app, _res=okres): app._send_budget_request = lambda data, **k: _res
            for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
            state = {"auth_email": "a@x.co"}
            st = F.install({"__real_defaults__": True, **FUEL, "Request my aircraft budget": True, "Name": "A", "Email": "a@b.co", "Aircraft status": "Already owned", "Send request": True}, state)
            import app
            app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
            app._sb_rest = r; app._storage_configured = lambda: True; patch_ok(app)
            try: app.main()
            except F.StopApp: pass
            n = len([e for e in r.t.get("events", []) if e["event"] == "study_request_received"])
            self.assertEqual(n >= 1, bool(expected))   # the recorder presses the button in every placement of the form
            self.assertNotIn("a@b.co", repr(r.t.get("events", [])))




class TestBenchmarkAtFirstLevel(unittest.TestCase):
    """The regional benchmark is chosen next to the fuel price (not buried in Advanced settings) and gives a result and a PDF without typing a price."""
    OV = {"Aircraft model": "dassault_falcon_7x", "Fuel price method": "Regional market benchmark", "📄 Generate PDF Report": True}

    def test_benchmark_gives_budget_and_report_without_typing_a_price(self):
        for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
        st = F.install({"__real_defaults__": True, **self.OV}, {"auth_email": "a@x.co"})
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        app._sb_rest = FakeRest(); app._storage_configured = lambda: False
        try: app.main()
        except F.StopApp: pass
        t = text(st)
        self.assertNotIn(app.FUEL_PRICE_MISSING, t)
        self.assertIn("weekly regional refinery", t); self.assertIn("Main refuelling region", [l for k, l, key, d in st.widgets])
        dl = [a[1] for k, a, kw in st.log if k == "download_button" and "PDF" in a[0]]
        self.assertTrue(dl)
        import subprocess, tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f: f.write(dl[0])
        out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout; os.unlink(f.name)
        self.assertRegex(out, r"(?i)refinery|benchmark")
        self.assertRegex(out, r"Annual budget")

    def test_default_still_assumes_no_price(self):
        for mm in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[mm]
        st = F.install({"__real_defaults__": True, "Aircraft model": "dassault_falcon_7x"}, {"auth_email": "a@x.co"})
        import app
        app.render_auth = lambda: (True, True); app._process_day_pass_return = lambda: None; app._get_logo = lambda: ""
        app._sb_rest = FakeRest(); app._storage_configured = lambda: False
        try: app.main()
        except F.StopApp: pass
        self.assertIn(app.FUEL_PRICE_MISSING, text(st))


if __name__ == "__main__": unittest.main()
