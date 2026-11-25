"""Orders, proof of acceptance, consistency of amounts, reconciliation, customer documents. Fake Supabase, fake Stripe objects: no network, no e-mail."""
import copy, datetime as dt, os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_legal as L  # noqa: E402
import menkor_orders as ORD  # noqa: E402
import menkor_access as ACCESS  # noqa: E402
from fake_rest import FakeRest, Obj  # noqa: E402
from test_legal import cfg, pub, extra  # noqa: E402

NOW = dt.datetime(2026, 12, 2, 10, 0, tzinfo=dt.timezone.utc)
CFG = cfg()
CAT = ORD.catalog(ACCESS, None, 600)


def bundle(lang="en", mutate=None):
    docs = pub(L.load_docs())
    if mutate: mutate(docs)
    return L.build_bundle(lang, CFG, docs, extra(lang), stripe_key="sk_live_x")


PROFILE = dict(customer_type="individual", first_name="Ada", last_name="Martin", country="FR", address_line1="1 rue X", postal_code="75001", city="Paris")
BIZ = dict(customer_type="business", first_name="Bob", last_name="Roe", company_name="Roe Aviation Ltd", country="GB", address_line1="2 High St", postal_code="N1 1AA", city="London")


def accept(lang="en", **kw):
    a = dict(terms=True, label=L.label("terms", lang), immediate=True, immediate_ack=True, marketing=False); a.update(kw); return a


def place(rest, key="comparison", email="a@x.com", profile=None, acc=None, lang="en", **kw):
    return ORD.place_order(rest, email=email, offer=CAT[key], profile=profile or PROFILE, accept=acc or accept(lang), bundle=bundle(lang), cfg=CFG, now=NOW, **kw)


def session(order, **kw):
    s = Obj(id="cs_1", status="complete", payment_status="paid", mode=order["mode"], amount_total=order["amount_minor"], amount_subtotal=order["amount_minor"], currency=order["currency"].lower(),
            metadata=Obj(order_id=order["id"], product=order["offer_key"]), client_reference_id=order["id"], customer="cus_1", payment_intent="pi_1", subscription=("sub_1" if order["mode"] == "subscription" else None),
            invoice="in_1", created=1796000000, customer_details=Obj(email=order["email"])); s.update(kw); return s


class TestAcceptance(unittest.TestCase):
    def test_no_payment_without_acceptance(self):
        r = FakeRest()
        with self.assertRaises(ORD.OrderError) as c: place(r, acc=accept(terms=False))
        self.assertEqual(c.exception.code, "terms_not_accepted"); self.assertEqual(r.t["orders"], []); self.assertEqual(r.t["order_acceptances"], [])

    def test_only_a_literal_true_counts(self):
        for v in (None, "on", 1, "true"):
            with self.assertRaises(ORD.OrderError): place(FakeRest(), acc=accept(terms=v))

    def test_label_must_be_the_exact_statement_in_the_order_language(self):
        with self.assertRaises(ORD.OrderError) as c: place(FakeRest(), acc=accept(label="I agree"))
        self.assertEqual(c.exception.code, "label_mismatch")
        with self.assertRaises(ORD.OrderError): place(FakeRest(), acc=accept(label=L.label("terms", "fr")), lang="en")
        place(FakeRest(), lang="fr", acc=accept("fr"))            # the French statement is valid for a French order

    def test_unpublished_legal_documents_block_the_order(self):
        b = L.build_bundle("en", CFG, L.load_docs(), extra("en"), stripe_key="sk_live_x")
        with self.assertRaises(ORD.OrderError) as c: ORD.place_order(FakeRest(), email="a@x.com", offer=CAT["single"], profile=PROFILE, accept=accept(), bundle=b, cfg=CFG, now=NOW)
        self.assertEqual(c.exception.code, "legal_not_ready")

    def test_proof_contents(self):
        r = FakeRest(); o = place(r); a = r.t["order_acceptances"][0]
        self.assertEqual(o["status"], "pending_payment"); self.assertEqual(a["order_id"], o["id"]); self.assertEqual(a["email"], "a@x.com")
        self.assertEqual(a["accepted_at"], "2026-12-02T10:00:00+00:00"); self.assertEqual(a["lang"], "en"); self.assertEqual(a["terms_version"], "1.0")
        self.assertEqual(a["checkbox_label"], L.label("terms", "en")); self.assertEqual(a["amount_minor"], 5900); self.assertEqual(a["currency"], "EUR"); self.assertEqual(a["mode"], "payment")
        self.assertEqual(a["terms_sha256"], bundle().docs["terms"]["sha256"])
        self.assertEqual({d["key"] for d in a["documents"]}, set(L.DOC_KEYS)); self.assertTrue(a["offer_snapshot"]["recap"]); self.assertEqual(len(a["offer_fingerprint"]), 64)
        self.assertGreater(a["retain_until"], a["accepted_at"]); self.assertIs(a["marketing_opt_in"], False)
        self.assertIn(a["terms_sha256"], {x["sha256"] for x in r.t["legal_document_versions"]})

    def test_later_change_of_the_terms_never_touches_an_old_order(self):
        r = FakeRest(); o1 = place(r)
        def new_text(docs): docs[("terms", "en")].template += "\n## 18. New clause\nSomething new.\n"; docs[("terms", "en")].version = "1.1"
        o2 = ORD.place_order(r, email="a@x.com", offer=CAT["single"], profile=PROFILE, accept=accept(), bundle=bundle(mutate=new_text), cfg=CFG, now=NOW)
        self.assertNotEqual(o1["terms_sha256"], o2["terms_sha256"]); self.assertEqual((o1["terms_version"], o2["terms_version"]), ("1.0", "1.1"))
        a1, docs1 = ORD.accepted_documents(r, "a@x.com", o1["id"]); body = [d for d in docs1 if d["key"] == "terms"][0]
        self.assertEqual(body["version"], "1.0"); self.assertNotIn("New clause", body["body"]); self.assertEqual(L.sha256_text(body["body"]), o1["terms_sha256"])
        a2, docs2 = ORD.accepted_documents(r, "a@x.com", o2["id"]); self.assertIn("New clause", [d for d in docs2 if d["key"] == "terms"][0]["body"])

    def test_evidence_cannot_be_updated(self):
        r = FakeRest(); o = place(r)
        self.assertEqual(r("PATCH", "order_acceptances", {"order_id": f"eq.{o['id']}"}, {"checkbox_label": "x"}, "return=minimal")[0], 400)
        self.assertEqual(r("PATCH", "legal_document_versions", {"sha256": f"eq.{o['terms_sha256']}"}, {"body": "x"}, "return=minimal")[0], 400)
        with open(os.path.join(ROOT, "legal_migration.sql"), encoding="utf-8") as f: sql = f.read()
        for t in ("legal_document_versions", "order_acceptances", "signup_acceptances"): self.assertIn(f"create trigger {t}_guard before update or delete", sql); self.assertIn(f"alter table {t}", sql)

    def test_proof_storage_failure_stops_the_payment(self):
        r = FakeRest(); r.fail_posts = {"order_acceptances"}
        with self.assertRaises(ORD.OrderError) as c: place(r)
        self.assertEqual(c.exception.code, "proof_storage_failed"); self.assertTrue(all(o["status"] == "cancelled" for o in r.t["orders"]))
        r2 = FakeRest(); r2.fail_posts = {"orders"}
        with self.assertRaises(ORD.OrderError): place(r2)
        r3 = FakeRest(); r3.fail_posts = {"legal_document_versions"}
        with self.assertRaises(ORD.OrderError): place(r3)

    def test_assert_payable_is_the_gate(self):
        r = FakeRest(); o = place(r)
        self.assertEqual(ORD.assert_payable(r, "a@x.com", o["id"])["id"], o["id"])
        for email, oid in (("b@x.com", o["id"]), ("a@x.com", "ORD-NOPE")):
            with self.assertRaises(ORD.OrderError): ORD.assert_payable(r, email, oid)
        r.t["order_acceptances"].clear()                          # an order without its acceptance can never be paid
        with self.assertRaises(ORD.OrderError) as c: ORD.assert_payable(r, "a@x.com", o["id"])
        self.assertEqual(c.exception.code, "no_acceptance")
        o2 = place(FakeRest()); r4 = FakeRest(); r4.t["orders"].append(dict(o2, status="draft"))
        with self.assertRaises(ORD.OrderError): ORD.assert_payable(r4, "a@x.com", o2["id"])

    def test_signup_acceptance(self):
        r = FakeRest(); b = bundle()
        with self.assertRaises(ORD.OrderError): ORD.record_signup_acceptance(r, "n@x.com", b, False, L.label("signup", "en"), CFG, NOW)
        with self.assertRaises(ORD.OrderError): ORD.record_signup_acceptance(r, "n@x.com", b, True, "wrong", CFG, NOW)
        self.assertEqual(r.t["signup_acceptances"], [])
        ORD.record_signup_acceptance(r, "n@x.com", b, True, L.label("signup", "en"), CFG, NOW); self.assertEqual(r.t["signup_acceptances"][0]["terms_version"], "1.0")

    def test_marketing_is_separate_and_optional(self):
        r = FakeRest(); place(r, acc=accept(marketing=False)); place(r, acc=accept(marketing=True))
        self.assertEqual([a["marketing_opt_in"] for a in r.t["order_acceptances"]], [False, True])


class TestProfiles(unittest.TestCase):
    def test_individual_and_business_both_work_and_vat_is_optional(self):
        r = FakeRest(); self.assertEqual(place(r, profile=PROFILE)["customer_type"], "individual")
        o = place(r, profile=BIZ, acc=accept(immediate=False, immediate_ack=False)); self.assertEqual(o["customer_type"], "business"); self.assertEqual(o["billing"]["tax_id"], "")
        o = place(r, profile=dict(BIZ, tax_id="GB123456789")); self.assertEqual(o["billing"]["tax_id"], "GB123456789")

    def test_business_needs_a_company_name_individual_does_not(self):
        with self.assertRaises(ORD.OrderError) as c: place(FakeRest(), profile=dict(BIZ, company_name=""))
        self.assertTrue(any("company" in p.lower() for p in c.exception.problems))
        o = place(FakeRest(), profile=dict(PROFILE, company_name="Ignored", tax_id="X123456")); self.assertEqual(o["billing"]["company_name"], "")

    def test_required_billing_fields_and_country_of_the_customer(self):
        for bad in (dict(first_name=""), dict(last_name=""), dict(country=""), dict(country="ZZ"), dict(address_line1=""), dict(city=""), dict(postal_code=""), dict(customer_type="")):
            with self.assertRaises(ORD.OrderError): place(FakeRest(), profile=dict(PROFILE, **bad))
        with self.assertRaises(ORD.OrderError): place(FakeRest(), email="not-an-email")
        with self.assertRaises(ORD.OrderError): place(FakeRest(), profile=dict(BIZ, tax_id="!!"))

    def test_the_customer_country_is_never_the_sellers(self):
        o = place(FakeRest(), profile=dict(PROFILE, country="BR")); self.assertEqual(o["billing"]["country"], "BR")
        self.assertNotIn("seller_country", o["billing"])

    def test_consumer_must_make_the_immediate_performance_request_business_not(self):
        for acc in (accept(immediate=False), accept(immediate_ack=False)):
            with self.assertRaises(ORD.OrderError) as c: place(FakeRest(), acc=acc)
            self.assertEqual(c.exception.code, "immediate_request_missing")
        r = FakeRest(); place(r, profile=BIZ, acc=accept(immediate=False, immediate_ack=False))
        a = r.t["order_acceptances"][0]; self.assertFalse(a["immediate_requested"]); self.assertIsNone(a["immediate_label"])
        r = FakeRest(); place(r); a = r.t["order_acceptances"][0]
        self.assertTrue(a["immediate_requested"] and a["immediate_ack"]); self.assertEqual(a["immediate_label"], L.label("immediate", "en"))

    def test_every_sold_category_has_a_defined_consumer_rule(self):
        for k, o in CAT.items(): self.assertTrue(ORD.needs_immediate_request(dict(customer_type="individual"), o), k); self.assertFalse(ORD.needs_immediate_request(dict(customer_type="business"), o), k)


class TestConsistency(unittest.TestCase):
    def test_catalog_amounts_come_from_the_code_that_grants_access(self):
        for k, p in ACCESS.PRODUCTS.items(): self.assertEqual(CAT[k]["amount_minor"], p["price_eur"] * 100)
        self.assertEqual(CAT["pro"]["amount_minor"], 7900); self.assertEqual(CAT["pro"]["interval"], "month"); self.assertEqual(CAT["market_search"]["currency"], "USD")

    def test_recap_states_price_currency_taxes_total_and_nature(self):
        rows = dict(ORD.recap(CAT["pro"], {}, "en", CFG)); self.assertIn("79", rows["Price"]); self.assertEqual(rows["Currency"], "EUR")
        self.assertEqual(rows["Taxes"], CFG["tax_note"]); self.assertIn("79", rows["Total to pay"]); self.assertIn("Recurring", rows["Type of payment"])
        for k in ("Billing", "Renewal", "Cancellation", "Credit consumption rules", "Access period"): self.assertIn(k, rows)
        one = dict(ORD.recap(CAT["comparison"], {}, "en", CFG)); self.assertIn("One-off", one["Type of payment"]); self.assertNotIn("Renewal", one); self.assertIn("14 days", one["Access period"])
        self.assertIn("3 model", one["What is included"])
        fr = dict(ORD.recap(CAT["pro"], {}, "fr", CFG)); self.assertIn("Total à payer", fr)

    def test_stripe_tax_mode_is_stated_in_the_recap_and_requested_from_stripe(self):
        c2 = cfg(LEGAL_TAX_MODE="stripe_tax"); rows = dict(ORD.recap(CAT["single"], {}, "en", c2)); self.assertIn("applicable taxes", rows["Total to pay"]); self.assertIn("Stripe", rows["Taxes"])
        r = FakeRest(); o = place(r, key="single"); p = ORD.decorate_params(ACCESS.checkout_params("single", "a@x.com", "pack", "u1", "u2"), o, c2)
        self.assertEqual(p["automatic_tax"], {"enabled": True}); self.assertNotIn("automatic_tax", ORD.decorate_params(ACCESS.checkout_params("single", "a@x.com", "pack", "u1", "u2"), o, CFG))

    def test_stripe_parameters_carry_the_order_the_same_amount_and_native_invoicing(self):
        r = FakeRest(); o = place(r); base = ACCESS.checkout_params("comparison", "a@x.com", "pack", "ok", "ko"); p = ORD.decorate_params(base, o, CFG)
        self.assertEqual(ORD.params_amount(p), o["amount_minor"]); self.assertEqual(p["client_reference_id"], o["id"]); self.assertEqual(p["metadata"]["order_id"], o["id"])
        self.assertEqual(p["metadata"]["product"], "comparison"); self.assertEqual(p["metadata"]["terms_version"], "1.0"); self.assertTrue(p["invoice_creation"]["enabled"])
        self.assertEqual(p["billing_address_collection"], "required"); self.assertNotIn("tax_id_collection", p); self.assertIn(o["id"], p["custom_text"]["submit"]["message"])
        ob = place(r, profile=BIZ, acc=accept(immediate=False, immediate_ack=False)); pb = ORD.decorate_params(base, ob, CFG, "cus_9")
        self.assertEqual(pb["tax_id_collection"], {"enabled": True}); self.assertEqual(pb["customer"], "cus_9"); self.assertNotIn("customer_email", pb); self.assertEqual(pb["customer_update"]["name"], "auto")

    def test_a_tampered_amount_or_mode_never_reaches_stripe(self):
        r = FakeRest(); o = place(r); base = ACCESS.checkout_params("comparison", "a@x.com", "pack", "ok", "ko")
        bad = copy.deepcopy(base); bad["line_items"][0]["price_data"]["unit_amount"] = 100
        with self.assertRaises(ORD.OrderError): ORD.decorate_params(bad, o, CFG)
        bad = copy.deepcopy(base); bad["line_items"][0]["price_data"]["currency"] = "usd"
        with self.assertRaises(ORD.OrderError): ORD.decorate_params(bad, o, CFG)
        bad = dict(base, mode="subscription")
        with self.assertRaises(ORD.OrderError): ORD.decorate_params(bad, o, CFG)

    def test_the_configured_stripe_price_must_be_the_displayed_offer(self):
        r = FakeRest(); o = place(r, key="pro")
        ORD.verify_price(Obj(unit_amount=7900, currency="eur", recurring=Obj(interval="month")), o)
        for bad in (Obj(unit_amount=5000, currency="eur", recurring=Obj(interval="month")), Obj(unit_amount=7900, currency="usd", recurring=Obj(interval="month")),
                    Obj(unit_amount=7900, currency="eur", recurring=Obj(interval="year")), Obj(unit_amount=7900, currency="eur", recurring=None)):
            with self.assertRaises(ORD.OrderError) as c: ORD.verify_price(bad, o)
            self.assertEqual(c.exception.code, "price_mismatch")

    def test_the_paid_amount_must_equal_the_ordered_amount(self):
        r = FakeRest(); o = place(r)
        res = ORD.reconcile(r, [session(o, amount_total=100)], "a@x.com", CFG, NOW); self.assertEqual(res["paid"], [])
        self.assertEqual(r.t["orders"][0]["status"], "mismatch")
        for kw in (dict(currency="usd"), dict(mode="subscription")):
            r = FakeRest(); o = place(r); self.assertEqual(ORD.reconcile(r, [session(o, **kw)], "a@x.com", CFG, NOW)["paid"], [])


class TestReconcile(unittest.TestCase):
    def test_paid_session_activates_once_and_records_everything(self):
        r = FakeRest(); o = place(r); res = ORD.reconcile(r, [session(o)], "a@x.com", CFG, NOW); self.assertEqual(len(res["paid"]), 1)
        row = r.t["orders"][0]; self.assertEqual((row["status"], row["stripe_session_id"], row["stripe_payment_intent"], row["stripe_invoice_id"], row["stripe_customer_id"]), ("paid", "cs_1", "pi_1", "in_1", "cus_1"))
        self.assertEqual(row["access_end"], "2026-12-16T10:00:00+00:00")             # 14 days
        o2 = place(r, key="pro"); ORD.reconcile(r, [session(o2, id="cs_2")], "a@x.com", CFG, NOW); self.assertEqual(r.t["orders"][1]["stripe_subscription_id"], "sub_1"); self.assertIsNone(r.t["orders"][1]["access_end"])

    def test_replayed_events_change_nothing(self):
        r = FakeRest(); o = place(r); s = session(o)
        self.assertEqual(len(ORD.reconcile(r, [s], "a@x.com", CFG, NOW)["paid"]), 1)
        snap = copy.deepcopy(r.t)
        for _ in range(3): self.assertEqual(ORD.reconcile(r, [s, s], "a@x.com", CFG, NOW)["paid"], [])
        self.assertEqual(r.t, snap)
        self.assertTrue(ORD.claim_confirmation(r, "a@x.com", o["id"], NOW)); self.assertFalse(ORD.claim_confirmation(r, "a@x.com", o["id"], NOW))
        ORD.release_confirmation(r, "a@x.com", o["id"]); self.assertTrue(ORD.claim_confirmation(r, "a@x.com", o["id"], NOW))

    def test_credits_are_not_granted_twice(self):
        r = FakeRest(); o = place(r); s = session(o)
        ids = lambda: ORD.paid_order_ids(r, "a@x.com")
        self.assertEqual(ACCESS.grants_from_sessions([s], "a@x.com", set(), None, ids()), [])             # not paid in our records yet: nothing
        ORD.reconcile(r, [s], "a@x.com", CFG, NOW); ORD.reconcile(r, [s], "a@x.com", CFG, NOW)
        g = ACCESS.grants_from_sessions([s], "a@x.com", set(), None, ids()); self.assertEqual(len(g), 1)
        self.assertEqual(ACCESS.grants_from_sessions([s], "a@x.com", {g[0]["session_id"]}, None, ids()), [])

    def test_failed_or_unfinished_payment_activates_nothing(self):
        for kw in (dict(payment_status="unpaid"), dict(status="open"), dict(status="open", payment_status="unpaid")):
            r = FakeRest(); o = place(r); res = ORD.reconcile(r, [session(o, **kw)], "a@x.com", CFG, NOW)
            self.assertEqual(res["paid"], []); self.assertEqual(r.t["orders"][0]["status"], "pending_payment")
            self.assertEqual(ACCESS.grants_from_sessions([session(o, **kw)], "a@x.com", set(), None, ORD.paid_order_ids(r, "a@x.com")), [])

    def test_expired_session_closes_the_order(self):
        r = FakeRest(); o = place(r); ORD.reconcile(r, [session(o, status="expired", payment_status="unpaid")], "a@x.com", CFG, NOW); self.assertEqual(r.t["orders"][0]["status"], "expired")
        r = FakeRest(); o = place(r); ORD.expire_stale(r, "a@x.com", now=NOW + dt.timedelta(hours=30)); self.assertEqual(r.t["orders"][0]["status"], "expired")
        r = FakeRest(); o = place(r); ORD.expire_stale(r, "a@x.com", now=NOW + dt.timedelta(hours=2)); self.assertEqual(r.t["orders"][0]["status"], "pending_payment")

    def test_a_session_created_outside_the_flow_never_grants_access(self):
        s = session(Obj(id="x", email="a@x.com", mode="payment", offer_key="comparison", amount_minor=5900, currency="EUR"), metadata=Obj(product="comparison"), client_reference_id=None)
        self.assertEqual(ACCESS.grants_from_sessions([s], "a@x.com", set(), None, set()), [])
        self.assertEqual(len(ACCESS.grants_from_sessions([s], "a@x.com", set(), None, None)), 1)        # legacy behaviour, flow off
        r = FakeRest(); self.assertEqual(ORD.reconcile(r, [s], "a@x.com", CFG, NOW)["paid"], [])

    def test_a_session_of_another_customer_or_order_is_ignored(self):
        r = FakeRest(); o = place(r)
        self.assertEqual(ORD.reconcile(r, [session(o)], "b@x.com", CFG, NOW)["paid"], [])
        self.assertEqual(ORD.reconcile(r, [session(o, customer_details=Obj(email="evil@x.com"))], "a@x.com", CFG, NOW)["paid"], [])
        link = ORD.link_session(r, "a@x.com", o["id"], "cs_real"); self.assertTrue(link)
        self.assertEqual(ORD.reconcile(r, [session(o, id="cs_other")], "a@x.com", CFG, NOW)["paid"], [])
        self.assertEqual(len(ORD.reconcile(r, [session(o, id="cs_real")], "a@x.com", CFG, NOW)["paid"]), 1)

    def test_stripe_tax_compares_the_price_before_tax(self):
        c2 = cfg(LEGAL_TAX_MODE="stripe_tax"); r = FakeRest(); o = place(r)
        self.assertEqual(len(ORD.reconcile(r, [session(o, amount_total=7080)], "a@x.com", c2, NOW)["paid"]), 1)


class TestCustomerArea(unittest.TestCase):
    def test_each_customer_only_sees_own_orders_proofs_and_documents(self):
        r = FakeRest(); a = place(r, email="a@x.com"); b = place(r, email="b@x.com", profile=BIZ, acc=accept(immediate=False, immediate_ack=False))
        self.assertEqual([o["id"] for o in ORD.list_orders(r, "a@x.com")], [a["id"]])
        self.assertIsNone(ORD.get_order(r, "b@x.com", a["id"])); self.assertIsNone(ORD.get_acceptance(r, "b@x.com", a["id"]))
        self.assertEqual(ORD.accepted_documents(r, "b@x.com", a["id"]), (None, []))
        self.assertIsNotNone(ORD.accepted_documents(r, "a@x.com", a["id"])[0])
        self.assertEqual(ORD.accepted_documents(r, "", a["id"]), (None, []))
        ORD.cancel_pending(r, "b@x.com", a["id"]); self.assertEqual(r.t["orders"][0]["status"], "pending_payment")      # another customer cannot touch it

    def test_invoices_are_listed_only_for_the_customers_own_stripe_customers(self):
        class S:
            class Invoice:
                @staticmethod
                def list(customer, limit): return Obj(data=[Obj(id=f"in_{customer}", number="N-1", status="paid", total=5900, currency="eur", created=1, hosted_invoice_url="https://x/h", invoice_pdf="https://x/p", customer=customer, subscription=None),
                                                           Obj(id="in_leak", number="N-2", status="paid", total=1, currency="eur", created=1, customer="cus_OTHER", subscription=None)])
            class CreditNote:
                @staticmethod
                def list(customer, limit): return Obj(data=[Obj(id="cn_1", number="C-1", total=100, currency="eur", pdf="https://x/c", customer=customer, invoice="in_1")])
        orders = [dict(stripe_customer_id="cus_1"), dict(stripe_customer_id=None)]
        d = ORD.stripe_documents(S, orders); self.assertEqual([i["id"] for i in d["invoices"]], ["in_cus_1"]); self.assertEqual(len(d["credit_notes"]), 1)
        self.assertEqual(ORD.stripe_documents(S, []), dict(invoices=[], credit_notes=[]))

    def test_only_the_owner_can_cancel_a_subscription(self):
        mine = [dict(stripe_subscription_id="sub_1", status="paid")]
        self.assertTrue(ORD.can_cancel(mine, "sub_1")); self.assertFalse(ORD.can_cancel(mine, "sub_2")); self.assertFalse(ORD.can_cancel([dict(stripe_subscription_id="sub_1", status="pending_payment")], "sub_1"))

    def test_refund_is_traced_and_partial_refunds_are_distinguished(self):
        r = FakeRest(); o = place(r); ORD.reconcile(r, [session(o)], "a@x.com", CFG, NOW); row = ORD.list_orders(r, "a@x.com")[0]
        class S:
            class Refund:
                amount = 5900
                @classmethod
                def list(cls, payment_intent, limit): return Obj(data=[Obj(amount=cls.amount, status="succeeded")])
        tot, stt = ORD.refund_state(S, row); self.assertEqual((tot, stt), (5900, "refunded")); self.assertTrue(ORD.apply_refund(r, row, tot, stt))
        self.assertEqual((r.t["orders"][0]["status"], r.t["orders"][0]["refunded_minor"]), ("refunded", 5900))
        self.assertFalse(ORD.apply_refund(r, ORD.list_orders(r, "a@x.com")[0], tot, stt))          # no silent re-write
        S.Refund.amount = 1000; self.assertEqual(ORD.refund_state(S, row), (1000, "partially_refunded"))
        S.Refund.amount = 0; self.assertEqual(ORD.refund_state(S, row), (0, None))

    def test_renewal_shows_the_next_due_date(self):
        self.assertEqual(ORD.period_end(Obj(current_period_end=1800000000)), "2027-01-15")
        self.assertEqual(ORD.period_end(Obj(items=Obj(data=[Obj(current_period_end=1800000000)]))), "2027-01-15"); self.assertEqual(ORD.period_end(Obj()), "—")

    def test_confirmation_email_content_and_attachment(self):
        r = FakeRest(); o = place(r, key="pro"); ORD.reconcile(r, [session(o)], "a@x.com", CFG, NOW); row = ORD.list_orders(r, "a@x.com")[0]
        a, docs = ORD.accepted_documents(r, "a@x.com", o["id"]); pdf = ORD.acceptance_pdf(a, docs, row, "Seller")
        subj, html, att = ORD.confirmation_email(row, a, "en", CFG, "https://app/?view=purchases", "https://stripe/inv", pdf)
        for needle in ("Menkor Pro", "79", "EUR", "monthly", "1.0", "https://stripe/inv", "My purchases and documents", "Cancellation", "Withdrawal", "attached"): self.assertIn(needle.lower(), html.lower(), needle)
        self.assertEqual(att[0][1][:4], b"%PDF"); self.assertGreater(len(att[0][1]), 5000)
        sent = []
        class P:
            status_code = 200
        ok, _ = ORD.send_email(lambda url, **kw: (sent.append(kw["json"]), P)[1], "key", "from@x", "a@x.com", subj, html, att); self.assertTrue(ok)
        self.assertEqual(sent[0]["attachments"][0]["filename"], f"terms-{o['id']}.pdf"); self.assertFalse(ORD.send_email(lambda *a, **k: P, "", "f", "t", "s", "h")[0])

    def test_french_confirmation_and_order(self):
        r = FakeRest(); o = place(r, lang="fr", acc=accept("fr")); row = r.t["orders"][0]; a, docs = ORD.accepted_documents(r, "a@x.com", o["id"])
        subj, html, att = ORD.confirmation_email(row, a, "fr", CFG, "https://app", None, None); self.assertIn("Confirmation", subj); self.assertIn("Mes achats et documents", html); self.assertEqual(att, [])
        self.assertEqual(a["checkbox_label"], L.label("terms", "fr"))


if __name__ == "__main__": unittest.main()
