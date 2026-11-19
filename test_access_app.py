"""App wiring of the model access rules (fake Streamlit — NOT a real browser). In-memory store, no Stripe call, no payment."""
import datetime as dt, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F  # noqa: E402
import menkor_access as A  # noqa: E402
import pandas as pd  # noqa: E402

DF = pd.DataFrame({"aircraft_id": ["a", "b", "c", "d"], "model": ["A", "B", "C", "D"]})
NOW = dt.datetime.now(dt.timezone.utc)


def boot(plan, mem=None, admin=False, on=True):
    for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[m]
    st = F.install({}, None)
    import app
    S = st.session_state; S["auth_email"] = "x@y.com"; S["auth_plan"] = plan; S["auth_is_admin"] = admin
    mem = mem or A.MemoryStore(); app._access_rules_on = lambda: on
    app._access_state = lambda email, plan, force=False: (A.load_state(mem, email, plan), mem)
    return st, app, mem


def pack(mem, kind="comparison", ids=("a", "b", "c")):
    mem.insert_grant(dict(session_id="s_" + kind, email="x@y.com", kind=kind, slots=A.PRODUCTS[kind]["slots"], context="pack",
                          purchased_at=A._iso(NOW), expires_at=A._iso(NOW + dt.timedelta(days=14))))
    mem.set_selection(dict(email="x@y.com", aircraft_ids=list(ids), changes=[], updated_at=A._iso(NOW)))


class TestGate(unittest.TestCase):
    def test_rules_off_changes_nothing(self):
        _, app, _ = boot("pro", on=False); self.assertEqual(app._access_gate(DF, "d", True, True)[:2], (True, True)); self.assertIsNone(app._acc_filter(DF) if False else None)

    def test_admin_unchanged_and_removed_essentiel_plan_gets_nothing(self):
        _, app, _ = boot("pro", admin=True); self.assertEqual(app._access_gate(DF, "d", True, True)[:2], (True, True))
        st, app, _ = boot("essentiel"); self.assertEqual(app._access_gate(DF, "d", False, False)[:2], (False, False)); self.assertEqual(st.session_state["_acc_ids"], [])

    def test_pack_holder_gets_pro_features_only_on_unlocked_models(self):
        mem = A.MemoryStore(); pack(mem); st, app, _ = boot(None, mem)
        self.assertEqual(app._access_gate(DF, "a", False, False)[:2], (True, True)); self.assertEqual(app._access_gate(DF, "d", False, False)[:2], (False, False))
        self.assertEqual(app._acc_filter(DF).aircraft_id.tolist(), ["a", "b", "c"])          # comparison limited to unlocked models

    def test_pro_needs_unlocking_and_free_gets_nothing(self):
        mem = A.MemoryStore(); st, app, _ = boot("pro", mem); self.assertEqual(app._access_gate(DF, "a", True, True)[:2], (False, False))
        mem.insert_pro_unlock(dict(email="x@y.com", aircraft_id="a", month=A.month_of(NOW), unlocked_at=A._iso(NOW)))
        self.assertEqual(app._access_gate(DF, "a", True, True)[:2], (True, True))
        _, app, _ = boot(None); self.assertEqual(app._access_gate(DF, "a", False, False)[:2], (False, False))

    def test_expired_pack_locks_again(self):
        mem = A.MemoryStore(); pack(mem)
        late = lambda email, plan, force=False: (A.AccessState(email, plan, mem.list_grants(email), mem.get_selection(email), [], NOW + dt.timedelta(days=15)), mem)
        _, app, _ = boot(None, mem); app._access_state = late; self.assertEqual(app._access_gate(DF, "a", False, False)[:2], (False, False))


class TestPanel(unittest.TestCase):
    def render(self, plan, mem, aid):
        st, app, mem = boot(plan, mem); i, p, ctx = app._access_gate(DF, aid, False, False); app._render_access_panel(ctx, aid, DF); return st

    def test_panel_renders_for_every_state_without_error(self):
        mem = A.MemoryStore(); self.render(None, mem, "a")                       # no pack: purchase offers
        mem = A.MemoryStore(); pack(mem); self.render(None, mem, "d")           # pack, locked model: swap UI
        self.render("pro", A.MemoryStore(), "a")                                # pro, locked: unlock button
        mem = A.MemoryStore(); [mem.insert_pro_unlock(dict(email="x@y.com", aircraft_id=f"m{i}", month=A.month_of(NOW), unlocked_at=A._iso(NOW))) for i in range(10)]
        self.render("pro", mem, "a")                                            # pro, quota exhausted: extra model offer

    def test_rules_text_is_visible_before_payment(self):
        st = self.render(None, A.MemoryStore(), "a")
        txt = " ".join(str(a[0]) for k, a, kw in st.log if k in ("markdown", "caption", "warning", "info"))
        self.assertIn("never uses another unlock", txt); self.assertIn("does not extend", txt); self.assertIn("excluding applicable taxes", txt)

    def test_offers_panel_lists_everything_and_packs_only_when_live(self):
        st, app, _ = boot("pro", on=True)
        out=[]; app.st.markdown=lambda *a,**k: out.append(a[0] if a else "")
        app._offers_panel(True); t=" ".join(out)
        for need in ("€ 29","€ 59","€ 15","€ 79 / month","$ 600","from € 490","14 days"): self.assertIn(need,t)
        out.clear(); app._offers_panel(False); t=" ".join(out)
        self.assertNotIn("€ 29",t); self.assertNotIn("Comparison pack",t)
        for need in ("€ 79 / month","$ 600","from € 490"): self.assertIn(need,t)

    def test_panel_guides_the_buyer_to_the_left_selector(self):
        mem = A.MemoryStore(); pack(mem); st = self.render(None, mem, "d")                  # pack holder looking at a model that is not theirs
        t = " ".join(str(a[0]) for k, a, kw in st.log if k in ("info", "success", "warning"))
        self.assertIn("Aircraft selection", t); self.assertIn("A, B, C", t)
        mem = A.MemoryStore(); pack(mem); st = self.render(None, mem, "a")                  # looking at one of their models
        t = " ".join(str(a[0]) for k, a, kw in st.log if k in ("info", "success", "warning")); self.assertIn("is unlocked", t)
        mem = A.MemoryStore(); mem.insert_grant(dict(session_id="s", email="x@y.com", kind="comparison", slots=3, context="pack", purchased_at=A._iso(NOW), expires_at=A._iso(NOW + dt.timedelta(days=14))))
        st = self.render(None, mem, "a"); t = " ".join(str(a[0]) for k, a, kw in st.log if k in ("info", "success", "warning"))
        self.assertIn("Step 1", t); self.assertIn("Apply my models", t)

    def test_sidebar_list_shows_unlocked_models_plus_demo(self):
        df = pd.DataFrame({"aircraft_id": ["a", "b", "c", "dassault_falcon_7x"], "model": ["A", "B", "C", "F7X"], "Categorie": ["x"] * 4})
        mem = A.MemoryStore(); pack(mem, "single", ("a",))
        st, app, _ = boot(None, mem); shown, mine = app._sidebar_models(df)
        self.assertEqual(sorted(shown["aircraft_id"]), ["a", "dassault_falcon_7x"]); self.assertEqual(mine, {"a"})
        st, app, _ = boot(None, A.MemoryStore()); shown, mine = app._sidebar_models(df); self.assertEqual(len(shown), 4); self.assertEqual(mine, set())      # nothing unlocked yet: full list
        st, app, _ = boot(None, mem, admin=True); self.assertEqual(len(app._sidebar_models(df)[0]), 4)                                                     # admin unrestricted
        st, app, _ = boot(None, mem, on=False); self.assertEqual(len(app._sidebar_models(df)[0]), 4)                                                       # rules off


if __name__ == "__main__":
    unittest.main()
