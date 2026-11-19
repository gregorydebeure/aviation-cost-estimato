"""Model access rules (v26): packs 14 days, swaps, additive packs, Pro quota, extra model, Stripe verification. In-memory store + fake Stripe: no network, no payment."""
import datetime as dt, unittest
import menkor_access as A

UTC = dt.timezone.utc
T0 = dt.datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
ALL = [f"m{i}" for i in range(30)]


def sess(sid, kind, email="a@b.com", paid=True, amount=None, cur="eur", ctx="pack", created=T0, mode="payment"):
    return dict(id=sid, mode=mode, payment_status="paid" if paid else "unpaid", currency=cur, amount_total=A.PRODUCTS[kind]["price_eur"] * 100 if amount is None else amount,
                customer_details={"email": email}, metadata={"product": kind, "ctx": ctx}, created=int(created.timestamp()))


class TestStripeVerification(unittest.TestCase):
    def test_paid_exact_amount_grants(self):
        g = A.grants_from_sessions([sess("s1", "comparison")], "a@b.com", set())
        self.assertEqual(len(g), 1); self.assertEqual(g[0]["slots"], 3); self.assertEqual(A._parse(g[0]["expires_at"]), T0 + dt.timedelta(days=14))

    def test_refuses_unpaid_wrong_amount_wrong_email_unknown_product_known_session(self):
        bad = [sess("u", "single", paid=False), sess("w", "single", amount=100), sess("e", "single", email="x@y.com"), sess("c", "single", cur="usd"),
               dict(sess("k", "single"), metadata={"product": "pro"}), sess("sub", "single", mode="subscription")]
        self.assertEqual(A.grants_from_sessions(bad, "a@b.com", set()), [])
        self.assertEqual(A.grants_from_sessions([sess("s1", "single")], "a@b.com", {"s1"}), [])

    def test_sync_is_idempotent_and_never_raises(self):
        class Sess:
            @staticmethod
            def list(**kw): return {"data": [sess("s1", "single")]}
        class Stripe: checkout = type("C", (), {"Session": Sess})
        store = A.MemoryStore()
        self.assertEqual(A.sync_from_stripe(Stripe, store, "a@b.com"), 1); self.assertEqual(A.sync_from_stripe(Stripe, store, "a@b.com"), 0)
        self.assertEqual(A.sync_from_stripe(object(), store, "a@b.com"), 0)

    def test_checkout_params(self):
        p = A.checkout_params("comparison", "a@b.com", "pack", "ok", "no")
        self.assertEqual(p["mode"], "payment"); self.assertEqual(p["line_items"][0]["price_data"]["unit_amount"], 5900)
        self.assertEqual(A.checkout_params("extra_model", "a@b.com", "pro", "ok", "no")["metadata"]["ctx"], "pro")
        self.assertEqual(A.checkout_params("extra_model", "a@b.com", "free", "ok", "no")["metadata"]["ctx"], "pack")
        self.assertEqual(A.checkout_params("single", "a@b.com", "pro", "ok", "no")["metadata"]["ctx"], "pack")


class TestPacks(unittest.TestCase):
    def state(self, grants, sel=None, plan=None, now=T0 + dt.timedelta(days=1)):
        return A.AccessState("a@b.com", plan, grants, sel, [], now)

    def test_three_models_for_14_days_then_nothing(self):
        g = A.grants_from_sessions([sess("s1", "comparison")], "a@b.com", set())
        sel = dict(aircraft_ids=["m1", "m2", "m3"], changes=[])
        self.assertEqual(self.state(g, sel).entitled_ids(ALL), {"m1", "m2", "m3"})
        self.assertEqual(self.state(g, sel, now=T0 + dt.timedelta(days=14, seconds=1)).entitled_ids(ALL), set())

    def test_second_pack_adds_slots_without_extending(self):
        g = A.grants_from_sessions([sess("s1", "comparison"), sess("s2", "single", created=T0 + dt.timedelta(days=5))], "a@b.com", set())
        st = self.state(g, dict(aircraft_ids=["m1", "m2", "m3", "m4"], changes=[]), now=T0 + dt.timedelta(days=6))
        self.assertEqual(st.pack_slots(), 4); self.assertEqual(len(st.pack_models()), 4)
        st = self.state(g, dict(aircraft_ids=["m1", "m2", "m3", "m4"], changes=[]), now=T0 + dt.timedelta(days=15))     # first expired, second still valid (adds, not extends)
        self.assertEqual(st.pack_slots(), 1); self.assertEqual(st.pack_models(), ["m1"])

    def test_choose_validates_and_swaps_within_limit(self):
        g = A.grants_from_sessions([sess("s1", "comparison")], "a@b.com", set()); st = self.state(g)
        ok, _, rec = st.choose_pack_models(["m1", "m2", "m3"], ALL); self.assertTrue(ok); self.assertEqual(rec["changes"], [])   # first fill is not a change
        st = self.state(g, rec)
        self.assertFalse(st.choose_pack_models(["m1", "m2", "m3", "m4"], ALL)[0]); self.assertFalse(st.choose_pack_models(["zzz"], ALL)[0])
        ok, _, rec2 = st.choose_pack_models(["m1", "m2", "m9"], ALL); self.assertTrue(ok); self.assertEqual(len(rec2["changes"]), 1)
        ok, _, _ = self.state(g, dict(rec2, changes=rec2["changes"] * 3)).choose_pack_models(["m1", "m2", "m8"], ALL); self.assertFalse(ok)   # 24 h limit reached
        later = self.state(g, dict(rec2, changes=rec2["changes"] * 3), now=T0 + dt.timedelta(days=3)); self.assertTrue(later.choose_pack_models(["m1", "m2", "m8"], ALL)[0])

    def test_no_pack_no_choice(self): self.assertFalse(self.state([]).choose_pack_models(["m1"], ALL)[0])


class TestPro(unittest.TestCase):
    def st(self, unl=(), grants=(), now=T0):
        return A.AccessState("a@b.com", "pro", list(grants), None, list(unl), now)

    def test_ten_new_models_per_month_no_carry_over(self):
        unl = [dict(email="a@b.com", aircraft_id=f"m{i}", month="2026-11") for i in range(10)]
        s = self.st(unl); self.assertEqual(s.pro_quota_left(), 0)
        ok, msg, _ = s.unlock_pro_model("m20", ALL); self.assertFalse(ok); self.assertIn("15", msg)
        self.assertTrue(s.unlock_pro_model("m3", ALL)[0])                                      # already unlocked: free
        dec = self.st(unl, now=dt.datetime(2026, 12, 2, tzinfo=UTC)); self.assertEqual(dec.pro_quota_left(), 10)   # new month: 10 again, not 20
        self.assertEqual(len(dec.entitled_ids(ALL)), 10)                                      # old models stay accessible while Pro is active

    def test_extra_model_adds_one_in_its_month_only(self):
        g = A.grants_from_sessions([sess("x", "extra_model", ctx="pro")], "a@b.com", set())
        unl = [dict(email="a@b.com", aircraft_id=f"m{i}", month="2026-11") for i in range(10)]
        self.assertEqual(self.st(unl, g).pro_quota_left(), 1)
        self.assertEqual(self.st(unl, g, now=dt.datetime(2026, 12, 2, tzinfo=UTC)).pro_quota_left(), 10)

    def test_not_pro_cannot_unlock_and_loses_models_when_pro_ends(self):
        unl = [dict(email="a@b.com", aircraft_id="m1", month="2026-11")]
        gone = A.AccessState("a@b.com", None, [], None, unl, T0); self.assertEqual(gone.entitled_ids(ALL), set()); self.assertFalse(gone.unlock_pro_model("m2", ALL)[0])

    def test_free_has_no_models_and_essentiel_no_longer_exists(self):
        self.assertEqual(A.AccessState("a@b.com", "essentiel", [], None, [], T0).entitled_ids(ALL), set())   # removed plan: no special access
        self.assertFalse(A.AccessState("a@b.com", "essentiel", [], None, [], T0).has_paid_access())
        self.assertEqual(A.AccessState("a@b.com", None, [], None, [], T0).entitled_ids(ALL), set())


class TestStores(unittest.TestCase):
    def test_supabase_adapter_uses_conflict_safe_inserts(self):
        calls = []
        def rest(m, t, params=None, json=None, prefer=None): calls.append((m, t, params, prefer)); return 200, []
        s = A.SupabaseStore(rest); s.insert_grant({"session_id": "s"}); s.insert_pro_unlock({"email": "a", "aircraft_id": "m"}); s.set_selection({"email": "a"})
        self.assertTrue(all("duplicates" in c[3] for c in calls)); self.assertEqual(calls[0][2], {"on_conflict": "session_id"})
        self.assertEqual(A.load_state(s, "a@b.com", None).pack_slots(), 0)

    def test_memory_store_deduplicates(self):
        m = A.MemoryStore(); g = A.grants_from_sessions([sess("s1", "single")], "a@b.com", set())[0]; m.insert_grant(g); m.insert_grant(g)
        self.assertEqual(len(m.list_grants("a@b.com")), 1)


class TestSyncRobustness(unittest.TestCase):
    class _Obj:                                   # Stripe-like object that is NOT a dict (recent stripe-python)
        def __init__(self, d): self._d = d
        def to_dict(self): return self._d
    def _sess(self, **kw):
        d = dict(id="cs_test_abc123", mode="payment", payment_status="paid", currency="eur", amount_total=5900, created=1763000000,
                 metadata={"product": "comparison", "ctx": "pack"}, customer_details={"email": "a@b.com"}, customer_email="a@b.com"); d.update(kw); return d
    def _stripe(self, data, fail_filtered=False):
        outer = self
        class L:
            def __init__(s, d): s.data = d
        class Sess:
            @staticmethod
            def list(**kw):
                if fail_filtered and "customer_details" in kw: raise RuntimeError("bad filter")
                return L(data)
        class Co: Session = Sess
        class M: checkout = Co
        return M
    def test_non_dict_stripe_objects_and_filter_fallback(self):
        store = A.MemoryStore(); n = A.sync_from_stripe(self._stripe([self._Obj(self._sess())], fail_filtered=True), store, "a@b.com")
        self.assertEqual(n, 1); self.assertEqual(len(store.grants), 1); self.assertEqual(A.LAST_SYNC["stored"], 1)
    def test_skip_reasons_are_reported(self):
        store = A.MemoryStore()
        A.sync_from_stripe(self._stripe([self._sess(amount_total=1000), self._sess(id="cs_x2", customer_details={"email": "z@z.com"}, customer_email="z@z.com")]), store, "a@b.com")
        self.assertEqual(len(store.grants), 0); txt = " ".join(A.LAST_SYNC["skipped"]); self.assertIn("amount/currency mismatch", txt); self.assertIn("different e-mail", txt)


if __name__ == "__main__":
    unittest.main()
