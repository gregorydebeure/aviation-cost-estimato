"""Order flow screens and the payment gate in app.py with the fake Streamlit (NOT a real browser), fake Supabase, fake Stripe: no network, no real e-mail, no real payment."""
import ast, datetime as dt, os, re, sys, types, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import fake_streamlit as F  # noqa: E402
from fake_rest import FakeRest, Obj  # noqa: E402
from test_legal import CFG_VALUES  # noqa: E402

STARTED = "2026-12-01T00:00:00+00:00"
T_STARTED = dt.datetime.fromisoformat(STARTED).timestamp()


class FakeStripe(types.ModuleType):
    def __init__(self):
        super().__init__("stripe"); self.api_key = None; self.created = []; self.sessions = []; self.subs = []; self.customers = []; self.modified = []; self.price = Obj(unit_amount=7900, currency="eur", recurring=Obj(interval="month"))
        o = self
        class Session:
            @staticmethod
            def create(**p): o.created.append(p); return Obj(id=f"cs_{len(o.created)}", url="https://stripe.test/pay")
            @staticmethod
            def list(limit=100, **kw): return Obj(data=o.sessions)
        class Price:
            @staticmethod
            def retrieve(pid): return o.price
        class Customer:
            @staticmethod
            def create(**kw): return Obj(id="cus_new")
            @staticmethod
            def modify(cid, **kw): o.modified.append(("customer", cid))
            @staticmethod
            def list(email, limit): return Obj(data=o.customers)
        class Subscription:
            @staticmethod
            def list(customer, status, limit): return Obj(data=o.subs)
            @staticmethod
            def retrieve(sid): return Obj(id=sid, status="active", cancel_at_period_end=False, current_period_end=1800000000)
            @staticmethod
            def modify(sid, **kw): o.modified.append(("sub", sid, kw))
        class Invoice:
            @staticmethod
            def list(customer, limit): return Obj(data=[])
            @staticmethod
            def retrieve(i): return Obj(hosted_invoice_url="https://stripe.test/inv")
        class Refund:
            @staticmethod
            def list(payment_intent, limit): return Obj(data=[])
        class CreditNote:
            @staticmethod
            def list(customer, limit): return Obj(data=[])
        self.checkout = types.SimpleNamespace(Session=Session); self.Price, self.Customer, self.Subscription, self.Invoice, self.Refund, self.CreditNote = Price, Customer, Subscription, Invoice, Refund, CreditNote


def boot(email="a@x.com", flow=True, ready=True, overrides=None, secrets=None, query=None, admin=False):
    for m in [k for k in sys.modules if k == "app" or k.startswith("streamlit") or k.startswith("plotly")]: del sys.modules[m]
    st = F.install(dict(overrides or {}), None); stripe = FakeStripe(); sys.modules["stripe"] = stripe
    import app
    S = st.session_state; S["auth_email"] = email; S["auth_plan"] = None; S["auth_is_admin"] = admin
    st.query_params.update(query or {})
    sec = {"STRIPE_SECRET_KEY": "sk_test_fake", "STRIPE_PRICE_PRO": "price_pro", "LEGAL_FLOW_ENABLED": "1" if flow else "0", "LEGAL_FLOW_STARTED_AT": STARTED, "ACCESS_RULES_ENABLED": "1"}
    if ready: sec.update(CFG_VALUES)
    sec.update(secrets or {})
    app._secret = lambda k, d="": sec.get(k, d); rest = FakeRest(); app._sb_rest = rest
    app._storage_configured = lambda: True; app._legal_tables_ok = lambda: True; app._track = lambda *a, **k: False
    app._mail_secrets = lambda: {"RESEND_API_KEY": "re_fake", "EMAIL_FROM": "from@x.com"}
    sent = []; app._mail_post = lambda url, **kw: (sent.append(kw["json"]), types.SimpleNamespace(status_code=200))[1]
    return st, app, rest, stripe, sent


def run(fn, *a):
    try: return fn(*a)
    except F.StopApp: return None


def text(st):
    return " ".join(str(x) for k, a, kw in st.log for x in a if isinstance(x, str)) + " " + " ".join(w[1] for w in st.widgets)


FORM = {"You are": "individual", "First name": "Ada", "Last name": "Martin", "Billing country": "FR", "Address": "1 rue X", "Postal code": "75001", "City": "Paris"}
EN_TERMS = "I have read and agree to the Terms of Sale and Use, including the data and report licence."
IMM = "I request immediate performance of the service and digital access before any right of withdrawal I may have has expired."
ACK = "I acknowledge that I have been informed of the conditions, time limit and consequences of exercising any right of withdrawal I may have, as described in the “Withdrawal, refunds and cancellation” information."


class TestGate(unittest.TestCase):
    def test_flow_is_off_by_default_and_the_legacy_payment_still_works(self):
        st, app, rest, stripe, _ = boot(flow=False); self.assertFalse(app._legal_on())
        app._stripe_checkout(dict(mode="payment")); self.assertEqual(len(stripe.created), 1)

    def test_with_the_flow_on_no_session_without_an_order(self):
        st, app, rest, stripe, _ = boot(); self.assertTrue(app._legal_on())
        with self.assertRaises(PermissionError): app._stripe_checkout(dict(mode="payment"))
        self.assertEqual(stripe.created, [])

    def test_direct_links_cannot_bypass_the_acceptance(self):
        st, app, rest, stripe, _ = boot()
        url, err = app._checkout_url("a@x.com", "pro"); self.assertIsNone(url); self.assertIn("PermissionError", err)
        url, err = app._access_checkout_url("comparison", "a@x.com", None); self.assertIsNone(url); self.assertIn("PermissionError", err)
        st2, app2, *_ = boot(); app2.st.warning = lambda *a, **k: None
        self.assertIsNone(app2._market_search_checkout_url("a@x.com", {"budget": "1"})); self.assertEqual(stripe.created, [])

    def test_only_one_function_creates_stripe_sessions(self):
        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as f: tree = ast.parse(f.read())
        found = []
        class V(ast.NodeVisitor):
            fn = None
            def visit_FunctionDef(self, n):
                old, V.fn = V.fn, n.name; self.generic_visit(n); V.fn = old
            def visit_Call(self, n):
                f = n.func
                if isinstance(f, ast.Attribute) and f.attr == "create" and isinstance(f.value, ast.Attribute) and f.value.attr == "Session": found.append(V.fn)
                self.generic_visit(n)
        V().visit(tree); self.assertTrue(found); self.assertEqual(set(found), {"_stripe_checkout"})
        for mod in ("menkor_market.py", "menkor_access.py", "menkor_orders.py", "menkor_legal.py"):
            with open(os.path.join(ROOT, mod), encoding="utf-8") as f: t = ast.parse(f.read())
            calls = [n for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "create" and isinstance(n.func.value, ast.Attribute) and n.func.value.attr == "Session"]
            self.assertEqual(calls, [], mod)

    def test_an_order_without_its_acceptance_cannot_be_paid(self):
        st, app, rest, stripe, _ = boot(); import menkor_orders as ORD
        rest.t["orders"].append(dict(id="ORD-X", email="a@x.com", status="pending_payment", amount_minor=5900, currency="EUR", terms_sha256="h", mode="payment"))
        with self.assertRaises(ORD.OrderError): app._stripe_checkout(dict(mode="payment"), dict(id="ORD-X", email="a@x.com", lang="en"))
        self.assertEqual(stripe.created, [])

    def test_no_checkbox_is_ticked_by_default(self):
        with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as f: src = f.read()
        for m in re.finditer(r"st\.checkbox\(([^\n]*)\)", src):
            if "ord_" in m.group(1) or "rg_terms" in m.group(1): self.assertNotIn("value=True", m.group(1), m.group(1))

    def test_ordering_is_blocked_while_the_documents_are_not_ready(self):
        st, app, rest, stripe, _ = boot(ready=False, overrides=dict(FORM, **{"Confirm and pay": True})); app._order_start("single")
        run(app._render_order_panel); self.assertIn("temporarily unavailable", text(st)); self.assertEqual(rest.t["orders"], []); self.assertEqual(stripe.created, [])
        self.assertNotIn(EN_TERMS, text(st))

    def test_live_key_with_draft_texts_is_blocked_test_key_allowed(self):
        st, app, *_ = boot(secrets={"STRIPE_SECRET_KEY": "sk_live_fake"}); self.assertFalse(app._legal_gate("en")[0])
        st, app, *_ = boot(); self.assertTrue(app._legal_gate("en")[0], app._legal_gate("en")[1])
        st, app, *_ = boot(secrets={"LEGAL_FLOW_STARTED_AT": ""}); self.assertIn("LEGAL_FLOW_STARTED_AT is missing", app._legal_gate("en")[1])


class TestOrderScreens(unittest.TestCase):
    def test_pay_button_without_acceptance_creates_nothing(self):
        st, app, rest, stripe, _ = boot(overrides=dict(FORM, **{"Confirm and pay": True})); app._order_start("comparison"); run(app._render_order_panel)
        self.assertEqual(rest.t["orders"], []); self.assertEqual(stripe.created, []); self.assertIn("must be accepted", " ".join(str(a[0]) for k, a, kw in st.log if k == "error"))

    def test_consumer_without_the_immediate_request_is_refused(self):
        st, app, rest, stripe, _ = boot(overrides=dict(FORM, **{"Confirm and pay": True, EN_TERMS: True})); app._order_start("comparison"); run(app._render_order_panel)
        self.assertEqual(stripe.created, []); self.assertIn("immediate performance", " ".join(str(a[0]) for k, a, kw in st.log if k == "error"))
        self.assertIn(IMM, text(st)); self.assertIn(ACK, text(st))

    def test_consumer_happy_path_creates_order_proof_and_one_checkout(self):
        st, app, rest, stripe, _ = boot(overrides=dict(FORM, **{"Confirm and pay": True, EN_TERMS: True, IMM: True, ACK: True})); app._order_start("comparison"); run(app._render_order_panel)
        self.assertEqual(len(rest.t["orders"]), 1); self.assertEqual(len(rest.t["order_acceptances"]), 1); self.assertEqual(len(stripe.created), 1)
        p = stripe.created[0]; o = rest.t["orders"][0]
        self.assertEqual(p["client_reference_id"], o["id"]); self.assertEqual(p["metadata"]["order_id"], o["id"]); self.assertEqual(p["line_items"][0]["price_data"]["unit_amount"], 5900)
        self.assertEqual(o["stripe_session_id"], "cs_1"); self.assertEqual(o["stripe_customer_id"], "cus_new"); self.assertEqual(p["customer"], "cus_new"); self.assertEqual(o["customer_type"], "individual")
        self.assertEqual(st.session_state["_order"]["url"], "https://stripe.test/pay")

    def test_business_path_has_company_optional_vat_and_no_consumer_boxes(self):
        ov = dict(FORM, **{"You are": "business", "Company name": "Roe Aviation Ltd", "Confirm and pay": True, EN_TERMS: True})
        st, app, rest, stripe, _ = boot(overrides=ov); app._order_start("pro"); run(app._render_order_panel)
        self.assertNotIn(IMM, text(st)); self.assertIn("VAT / tax ID (optional)", text(st))
        self.assertEqual(len(stripe.created), 1); p = stripe.created[0]; self.assertEqual(p["tax_id_collection"], {"enabled": True}); self.assertEqual(rest.t["orders"][0]["billing"]["tax_id"], "")
        self.assertEqual(rest.t["orders"][0]["billing"]["company_name"], "Roe Aviation Ltd"); self.assertEqual(p["mode"], "subscription"); self.assertEqual(p["subscription_data"]["metadata"]["order_id"], rest.t["orders"][0]["id"])

    def test_pro_price_mismatch_on_the_stripe_side_blocks_the_payment(self):
        ov = dict(FORM, **{"You are": "business", "Company name": "R", "Confirm and pay": True, EN_TERMS: True})
        st, app, rest, stripe, _ = boot(overrides=ov); stripe.price = Obj(unit_amount=5000, currency="eur", recurring=Obj(interval="month")); app._order_start("pro"); run(app._render_order_panel)
        self.assertEqual(stripe.created, []); self.assertEqual(rest.t["orders"][0]["status"], "cancelled")

    def test_every_product_goes_through_the_same_gate_with_matching_amounts(self):
        import menkor_orders as ORD
        for key in ("single", "comparison", "extra_model", "pro", "market_search"):
            ov = dict(FORM, **{"You are": "business", "Company name": "R", "Confirm and pay": True, EN_TERMS: True})
            st, app, rest, stripe, _ = boot(overrides=ov); app._order_start(key, extra={"meta": {"budget": "x"}} if key == "market_search" else None); run(app._render_order_panel)
            self.assertEqual(len(stripe.created), 1, key); o = rest.t["orders"][0]; p = stripe.created[0]
            amt = ORD.params_amount(p); self.assertTrue(amt is None or amt == o["amount_minor"], key); self.assertEqual(p["metadata"]["order_id"], o["id"], key)
            if key == "market_search": self.assertEqual(o["currency"], "EUR"); self.assertEqual(amt, 60000)

    def test_listing_order_is_bound_to_its_owner(self):
        import menkor_market as M
        st, app, rest, stripe, _ = boot(overrides=dict(FORM, **{"You are": "business", "Company name": "R", "Confirm and pay": True, EN_TERMS: True})); mem = M.MemoryStore(); app.MKT.SupabaseStore = lambda r: mem
        ok, err, c = M.validate_listing(dict(manufacturer="Dassault", model="Falcon 7X", category="Ultra-long-range jets", country="France", year="2012", total_hours="4200", price_amount="31500000", price_currency="EUR", description="Well maintained aircraft, programme up to date."), M._now())
        l = M.new_listing("someone@else.com", c, M._now()); mem.insert(l)
        app._order_start("listing", extra={"listing_id": l["id"]}); run(app._render_order_panel); self.assertEqual(stripe.created, [])           # not the owner: no payment
        l2 = M.new_listing("a@x.com", c, M._now()); mem.insert(l2); st.session_state["_order"] = None
        app._order_start("listing", extra={"listing_id": l2["id"]}); run(app._render_order_panel); self.assertEqual(len(stripe.created), 1)
        self.assertEqual(stripe.created[0]["metadata"]["listing_id"], l2["id"]); self.assertEqual(stripe.created[0]["mode"], "subscription")

    def test_french_order_screen(self):
        st, app, rest, stripe, _ = boot(); st.session_state["_legal_lang"] = "fr"; app._order_start("single"); run(app._render_order_panel); t = text(st)
        for needle in ("Récapitulatif", "Particulier", "Confirmer et payer", "J'ai lu et j'accepte les Conditions générales de vente et d'utilisation, comprenant la licence d'utilisation des données et des rapports.", "Total à payer"): self.assertIn(needle, t)
        self.assertIn("pas une signature électronique qualifiée", t)

    def test_english_screen_shows_recap_with_everything_required(self):
        st, app, *_ = boot(); app._order_start("pro"); run(app._render_order_panel); t = text(st)
        for needle in ("Recap", "Price", "Currency", "Taxes", "Total to pay", "Recurring", "Renewal", "Cancellation", "Credit consumption rules", "Access period", "Confirm and pay", EN_TERMS, "not a qualified electronic signature", "open in a new tab"): self.assertIn(needle, t)

    def test_acceptance_boxes_are_unticked_again_for_every_new_order(self):
        st, app, rest, stripe, _ = boot(); st.session_state.update({"ord_terms": True, "ord_imm": True, "ord_ack": True, "ord_mkt": True})
        app._order_start("single"); self.assertFalse(any(k in st.session_state for k in ("ord_terms", "ord_imm", "ord_ack", "ord_mkt")))
        st.session_state.update({"ord_terms": True}); app._order_cancel(); self.assertNotIn("ord_terms", st.session_state)

    def test_login_required_to_order(self):
        st, app, rest, stripe, _ = boot(email=None); app._order_start("pro"); run(app._render_order_panel); self.assertIn("Log in", text(st)); self.assertEqual(rest.t["orders"], [])

    def test_the_order_panel_and_purchases_do_not_exist_with_the_flow_off(self):
        st, app, *_ = boot(flow=False); app._order_start("pro"); run(app._render_order_panel); self.assertNotIn("Confirm and pay", text(st))


class TestPublicPagesAndSignup(unittest.TestCase):
    def test_public_page_before_publication_shows_no_text(self):
        st, app, *_ = boot(email=None, ready=False, query={"legal": "terms", "lang": "en"}); self.assertTrue(run(app._render_legal_page)); t = text(st)
        self.assertIn("being finalised", t); self.assertNotIn("Seller and contact", t)

    def test_public_page_with_a_complete_set_up_shows_text_version_and_pdf(self):
        st, app, *_ = boot(email=None, query={"legal": "terms", "lang": "en"}); self.assertTrue(run(app._render_legal_page)); t = text(st)
        self.assertIn("Seller and contact", t); self.assertIn("Version 1.0", t); self.assertIn("Withdrawal, refunds and cancellation", t)
        self.assertIn("download_button", {k for k, a, kw in st.log})

    def test_public_pages_in_both_languages_and_every_document(self):
        for k in ("terms", "withdrawal", "notice", "privacy", "cookies"):
            for lg in ("en", "fr"):
                st, app, *_ = boot(email=None, query={"legal": k, "lang": lg}); self.assertTrue(run(app._render_legal_page), (k, lg)); self.assertNotIn("being finalised", text(st))

    def test_unknown_page_is_ignored(self):
        st, app, *_ = boot(email=None, query={"legal": "../../etc"}); self.assertFalse(run(app._render_legal_page))

    def test_footer_links_only_when_published(self):
        st, app, *_ = boot(ready=False); app._legal_footer(); self.assertNotIn("legal=terms", text(st))
        st, app, *_ = boot(); app._legal_footer(); self.assertIn("legal=terms&lang=en", text(st)); self.assertIn("legal=privacy&lang=fr", text(st))

    def test_signup_needs_the_acceptance_and_stores_the_proof_before_the_account(self):
        st, app, rest, *_ = boot(email=None); order = []
        app._hash = lambda p: "h"; app._sb_get_user = lambda e: None; app._sb_insert_user = lambda e, h: (order.append(("user", len(rest.t["signup_acceptances"]))) or (True, "")); app.ACC.notify_signup = lambda *a, **k: {"welcome": (False, "")}
        ok, msg = app._register("new@x.com", "secret1", False, "en"); self.assertFalse(ok); self.assertEqual(order, []); self.assertEqual(rest.t["signup_acceptances"], [])
        ok, msg = app._register("new@x.com", "secret1", None, "en"); self.assertFalse(ok)
        ok, msg = app._register("new@x.com", "secret1", True, "en"); self.assertTrue(ok); self.assertEqual(order, [("user", 1)]); self.assertEqual(rest.t["signup_acceptances"][0]["email"], "new@x.com")

    def test_signup_is_unchanged_with_the_flow_off(self):
        st, app, rest, *_ = boot(email=None, flow=False); app._hash = lambda p: "h"; app._sb_get_user = lambda e: None; app._sb_insert_user = lambda e, h: (True, ""); app.ACC.notify_signup = lambda *a, **k: {"welcome": (False, "")}
        self.assertTrue(app._register("new@x.com", "secret1")[0]); self.assertEqual(rest.t["signup_acceptances"], [])

    def test_signup_blocked_while_documents_not_ready(self):
        st, app, rest, *_ = boot(email=None, ready=False); app._sb_get_user = lambda e: None; called = []; app._sb_insert_user = lambda e, h: (called.append(1) or (True, ""))
        self.assertFalse(app._register("new@x.com", "secret1", True, "en")[0]); self.assertEqual(called, [])


class TestPaymentConfirmation(unittest.TestCase):
    def _paid(self, app, rest, stripe, key="comparison", email="a@x.com"):
        import menkor_orders as ORD, menkor_legal as L
        from test_orders import place, session, accept, BIZ
        o = place(rest, key=key, email=email); s = session(o); s["created"] = 1796000000; stripe.sessions.append(s); return o, s

    def test_return_from_stripe_is_not_proof_payment_is_read_server_side(self):
        st, app, rest, stripe, sent = boot(query={"access": "paid"}); import test_orders as T
        o = T.place(rest); self.assertEqual(rest.t["orders"][0]["status"], "pending_payment")
        app._sync_orders("a@x.com", force=True); self.assertEqual(rest.t["orders"][0]["status"], "pending_payment"); self.assertEqual(sent, [])      # URL says "paid", Stripe says nothing: nothing happens

    def test_sync_marks_paid_sends_one_email_with_the_terms_attached_and_is_idempotent(self):
        st, app, rest, stripe, sent = boot(); o, s = self._paid(app, rest, stripe)
        new = app._sync_orders("a@x.com", force=True); self.assertEqual(len(new), 1); self.assertEqual(rest.t["orders"][0]["status"], "paid")
        self.assertEqual(len(sent), 1); self.assertEqual(sent[0]["to"], ["a@x.com"]); self.assertEqual(sent[0]["attachments"][0]["filename"], f"terms-{o['id']}.pdf")
        for _ in range(3): app._sync_orders("a@x.com", force=True)
        self.assertEqual(len(sent), 1); self.assertEqual(rest.t["orders"][0]["status"], "paid")

    def test_failed_email_is_retried_without_duplicates(self):
        st, app, rest, stripe, sent = boot(); self._paid(app, rest, stripe); calls = []
        app._mail_post = lambda url, **kw: (calls.append(1), types.SimpleNamespace(status_code=500))[1]
        app._sync_orders("a@x.com", force=True); self.assertIsNone(rest.t["orders"][0]["confirmation_sent_at"])
        app._mail_post = lambda url, **kw: (sent.append(kw["json"]), types.SimpleNamespace(status_code=200))[1]
        app._sync_orders("a@x.com", force=True); app._sync_orders("a@x.com", force=True); self.assertEqual(len(sent), 1); self.assertIsNotNone(rest.t["orders"][0]["confirmation_sent_at"])

    def test_access_is_granted_only_through_a_paid_accepted_order(self):
        import menkor_access as ACCESS
        st, app, rest, stripe, sent = boot(); o, s = self._paid(app, rest, stripe); store = ACCESS.MemoryStore() if hasattr(ACCESS, "MemoryStore") else None
        self.assertEqual(ACCESS.grants_from_sessions([s], "a@x.com", set(), None, app.ORD.paid_order_ids(rest, "a@x.com")), [])
        app._sync_orders("a@x.com", force=True); self.assertEqual(len(ACCESS.grants_from_sessions([s], "a@x.com", set(), None, app.ORD.paid_order_ids(rest, "a@x.com"))), 1)

    def test_pro_subscription_outside_the_flow_does_not_count_but_existing_ones_do(self):
        st, app, rest, stripe, sent = boot(); app._sb_update_user = lambda e, f: True; app._sb_get_user = lambda e: {}
        mk = lambda created, md=None: Obj(id="sub_x", created=created, metadata=Obj(**(md or {})), **{"items": Obj(data=[Obj(price=Obj(id="price_pro"))])})
        stripe.customers = [Obj(id="cus_1")]
        stripe.subs = [mk(T_STARTED + 3600)]; self.assertIsNone(app._check_sub("a@x.com"))               # bought after the start, no accepted order: not Pro
        stripe.subs = [mk(T_STARTED - 86400)]; self.assertEqual(app._check_sub("a@x.com"), "pro")         # existing customer before the start date: keeps access
        o, s = self._paid(app, rest, stripe, key="pro"); s["customer"] = "cus_1"
        stripe.subs = [mk(T_STARTED + 3600, {"order_id": o["id"]})]; self.assertEqual(app._check_sub("a@x.com"), "pro")      # bought through the flow and paid

    def test_flow_off_keeps_the_old_subscription_check(self):
        st, app, rest, stripe, sent = boot(flow=False); app._sb_update_user = lambda e, f: True; app._sb_get_user = lambda e: {}
        stripe.customers = [Obj(id="cus_1")]; stripe.subs = [Obj(id="s", created=T_STARTED + 1, metadata=Obj(), **{"items": Obj(data=[Obj(price=Obj(id="price_pro"))])})]
        self.assertEqual(app._check_sub("a@x.com"), "pro")


class TestPurchasesPage(unittest.TestCase):
    def test_a_customer_sees_own_order_documents_and_nobody_elses(self):
        import test_orders as T
        st, app, rest, stripe, sent = boot(email="a@x.com"); a = T.place(rest, email="a@x.com", key="single"); b = T.place(rest, email="b@x.com", key="comparison")
        run(app._render_purchases); t = text(st)
        self.assertIn(a["id"], t); self.assertNotIn(b["id"], t); self.assertIn("Accepted terms and proof (PDF)", t)
        downloads = [(a_, kw) for k, a_, kw in st.log if k == "download_button"]
        st2, app2, rest2, *_ = boot(email="b@x.com"); rest2.t = rest.t; run(app2._render_purchases); self.assertNotIn(a["id"], text(st2)); self.assertIn(b["id"], text(st2))

    def test_needs_login_and_flow(self):
        st, app, *_ = boot(email=None); run(app._render_purchases); self.assertIn("Log in", text(st))
        st, app, *_ = boot(flow=False); run(app._render_purchases); self.assertIn("not available", text(st))

    def test_cancel_subscription_only_for_an_own_paid_order(self):
        import test_orders as T
        st, app, rest, stripe, sent = boot(email="a@x.com", overrides={"I want to cancel this subscription at the end of the paid period": True, "Cancel subscription": True})
        o = T.place(rest, email="a@x.com", key="pro"); s = T.session(o); stripe.sessions.append(s); s["created"] = 1796000000; app._sync_orders("a@x.com", force=True)
        run(app._render_purchases); self.assertIn(("sub", "sub_1", {"cancel_at_period_end": True}), stripe.modified)
        st2, app2, rest2, stripe2, _ = boot(email="evil@x.com", overrides={"I want to cancel this subscription at the end of the paid period": True, "Cancel subscription": True}); rest2.t = rest.t
        run(app2._render_purchases); self.assertEqual(stripe2.modified, [])

    def test_admin_status_panel_lists_what_is_missing(self):
        st, app, *_ = boot(ready=False, admin=True); app._legal_admin_panel(); t = text(st)
        self.assertIn("LEGAL_SELLER_NAME", t); self.assertIn("not ready", t); self.assertIn("blocked", t)


if __name__ == "__main__": unittest.main()


class MarketSearchEurAndTimelineTests(unittest.TestCase):
    """v30: Market Search is sold in EUR, can be requested by e-mail without paying, and the acquisition timeline shows no prices."""
    def _src(self):
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py"), encoding="utf-8") as f: return f.read()
    def test_no_usd_left_in_market_search(self):
        s = self._src()
        self.assertNotIn("MARKET_SEARCH_PRICE_USD", s); self.assertNotIn('"currency":"usd"', s)
        for bad in ("$ 600", "$600"): self.assertNotIn(bad, s)
        self.assertIn('"currency":"eur","unit_amount":MARKET_SEARCH_PRICE_EUR*100', s)
    def test_timeline_has_no_prices(self):
        s = self._src(); i = s.index("_tl_steps=["); j = s.index("for num,title,desc,delay in _tl_steps:")
        blk = s[i:j]; self.assertNotIn("$", blk); self.assertNotIn("€", blk); self.assertNotIn("💰", s[j:j + 600])
    def test_free_email_request_does_not_create_order_or_payment(self):
        sent = []
        class R:  status_code = 200
        def post(url, headers=None, json=None, timeout=None): sent.append(json); return R()
        st, app, rest, stripe, _ = boot(); ok, d = app._send_budget_request({"Name": "A", "Email": "a@x.com", "Aircraft model": "G650"}, secrets={"RESEND_API_KEY": "k", "ADMIN_EMAIL": "me@x.com"}, post=post,
                                               subject="Market Search request (no payment) — G650", intro="x")
        self.assertTrue(ok); self.assertEqual(sent[0]["subject"], "Market Search request (no payment) — G650"); self.assertEqual(sent[0]["to"], ["me@x.com"])
