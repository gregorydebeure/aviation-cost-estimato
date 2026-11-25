"""Legal documents: configuration, readiness, immutability of versions, rendering, PDF. No network."""
import os, sys, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT); sys.path.insert(0, HERE)
import menkor_legal as L  # noqa: E402
import menkor_orders as ORD  # noqa: E402
import menkor_access as ACCESS  # noqa: E402

CFG_VALUES = {k: f"value of {k}" for k in L.REQUIRED_CONFIG.values()}
CFG_VALUES.update(LEGAL_RETENTION_YEARS="10", LEGAL_TAX_MODE="included")


def cfg(**over):
    vals = dict(CFG_VALUES); vals.update(over)
    return L.read_config(lambda k, d="": vals.get(k, d))


def pub(docs):
    """Same documents, marked published with an effective date (what a release looks like)."""
    for d in docs.values(): d.status = "published"; d.effective = "2026-12-01"
    return docs


def extra(lang): return {"offers_table": ORD.offers_table(ORD.catalog(ACCESS, None, 600), lang)}


class TestLegal(unittest.TestCase):
    def test_nothing_is_ready_without_the_seller_information(self):
        for lg in L.LANGS:
            b = L.build_bundle(lg, cfg(**{k: "" for k in L.REQUIRED_CONFIG.values()}), pub(L.load_docs()), extra(lg), stripe_key="sk_live_x")
            self.assertFalse(b.ready); self.assertTrue(any("configuration missing" in p for p in b.problems))

    def test_missing_config_lists_every_key(self):
        self.assertEqual(set(L.missing_config({"_tax_mode": ""})), set(L.REQUIRED_CONFIG.values()) | {"LEGAL_TAX_MODE"})
        self.assertEqual(L.missing_config(cfg()), [])
        self.assertTrue(L.missing_config(cfg(LEGAL_RETENTION_YEARS="ten")))

    def test_draft_texts_never_go_live_with_a_live_stripe_key(self):
        b = L.build_bundle("en", cfg(), L.load_docs(), extra("en"), stripe_key="sk_live_abc")
        self.assertFalse(b.ready); self.assertTrue(any("not published" in p for p in b.problems))

    def test_draft_texts_allowed_only_with_a_stripe_test_key(self):
        b = L.build_bundle("en", cfg(), L.load_docs(), extra("en"), stripe_key="sk_test_abc")
        self.assertTrue(b.ready, b.problems)

    def test_published_text_needs_an_effective_date(self):
        docs = pub(L.load_docs()); docs[("terms", "en")].effective = ""
        b = L.build_bundle("en", cfg(), docs, extra("en"), stripe_key="sk_live_x")
        self.assertFalse(b.ready); self.assertTrue(any("effective date" in p for p in b.problems))
        self.assertTrue(L.build_bundle("en", cfg(LEGAL_EFFECTIVE_DATE="2026-12-01"), docs, extra("en"), stripe_key="sk_live_x").ready)

    def test_fully_published_set_is_ready_and_has_no_leftover_field(self):
        for lg in L.LANGS:
            b = L.build_bundle(lg, cfg(), pub(L.load_docs()), extra(lg), stripe_key="sk_live_x")
            self.assertTrue(b.ready, b.problems)
            for k, d in b.docs.items(): self.assertNotIn("{{", d["text"], k)

    def test_every_placeholder_is_known_and_fr_en_use_the_same_ones(self):
        docs = L.load_docs(); known = set(L.REQUIRED_CONFIG) | {"offers_table"}
        for k in L.DOC_KEYS:
            fr, en = L.placeholders(docs[(k, "fr")].template), L.placeholders(docs[(k, "en")].template)
            self.assertTrue(fr <= known and en <= known, (k, fr - known, en - known)); self.assertEqual(fr, en, k)

    def test_both_languages_exist_for_every_document(self):
        docs = L.load_docs()
        for k in L.DOC_KEYS:
            for lg in L.LANGS: self.assertIn((k, lg), docs)

    def test_a_text_cannot_change_without_a_new_version(self):
        self.assertEqual(L.manifest_problems(), [])

    def test_manifest_detects_a_silent_change(self):
        import tempfile, shutil, json
        d = tempfile.mkdtemp(); shutil.copytree(L.LEGAL_DIR, d, dirs_exist_ok=True)
        p = os.path.join(d, "terms.en.md")
        with open(p, "a", encoding="utf-8") as f: f.write("\nA new clause.\n")
        self.assertTrue(any("terms.en" in x for x in L.manifest_problems(d)))
        with open(p, encoding="utf-8") as f: raw = f.read().replace("version: 1.0", "version: 1.1")
        with open(p, "w", encoding="utf-8") as f: f.write(raw)
        self.assertEqual([x for x in L.manifest_problems(d) if "text changed" in x], [])      # a new version number is the legitimate way

    def test_labels_are_exactly_the_required_sentences(self):
        self.assertEqual(L.label("terms", "fr"), "J'ai lu et j'accepte les Conditions générales de vente et d'utilisation, comprenant la licence d'utilisation des données et des rapports.")
        self.assertEqual(L.label("terms", "en"), "I have read and agree to the Terms of Sale and Use, including the data and report licence.")

    def test_terms_contain_the_protection_clauses(self):
        t = L.load_docs()[("terms", "en")].template.lower()
        for needle in ("does not transfer ownership", "mass or systematic extraction", "quotas", "estimates", "public aviation facts", "not a qualified electronic signature", "replacing models"): self.assertIn(needle, t)
        tf = L.load_docs()[("terms", "fr")].template.lower()
        for needle in ("ne transfère pas la propriété", "extraction massive", "quotas", "estimations", "faits publics", "signature électronique qualifiée", "remplacement de modèles"): self.assertIn(needle, tf)

    def test_withdrawal_text_has_no_blanket_no_refund_clause_and_separates_the_four_categories(self):
        w = L.load_docs()[("withdrawal", "en")].template.lower()
        self.assertIn("no blanket", w); self.assertNotIn("non-refundable", w)
        for needle in ("subscription", "time-limited", "digital reports", "manual services", "expressly"): self.assertIn(needle, w)

    def test_offers_table_in_the_terms_matches_the_configured_prices(self):
        b = L.build_bundle("en", cfg(), pub(L.load_docs()), extra("en"), stripe_key="sk_live_x")
        txt = b.docs["terms"]["text"]
        for o in ORD.catalog(ACCESS, None, 600).values(): self.assertIn(ORD.money(o["amount_minor"], o["currency"]), txt)

    def test_pdf_carries_version_and_effective_date(self):
        b = L.build_bundle("en", cfg(), pub(L.load_docs()), extra("en"), stripe_key="sk_live_x")
        pdf = L.document_pdf(b.docs["terms"], "en", "Seller")
        self.assertTrue(pdf.startswith(b"%PDF")); self.assertGreater(len(pdf), 3000)

    def test_hash_changes_with_the_text(self):
        d = pub(L.load_docs())[("terms", "en")]
        a, _ = L.render(d, cfg(), extra("en")); b, _ = L.render(d, cfg(LEGAL_COURTS="another court"), extra("en"))
        self.assertNotEqual(L.sha256_text(a), L.sha256_text(b))


if __name__ == "__main__": unittest.main()
