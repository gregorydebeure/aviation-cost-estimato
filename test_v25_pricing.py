"""Pricing of 18 Nov 2026: Menkor Pro 79 EUR/month, Market Search 600 EUR (changed to EUR on 25 Nov 2026), precise budget from 490 EUR. Source-level checks (no real Stripe, no payment)."""
import os, re, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()


class TestPricing(unittest.TestCase):
    def test_market_search_is_charged_in_eur_cents(self):
        self.assertIn("MARKET_SEARCH_PRICE_EUR = 600", SRC)
        self.assertIn('"currency":"eur","unit_amount":MARKET_SEARCH_PRICE_EUR*100', SRC)
        self.assertIsNone(re.search(r"€ ?300(?![\d,])", SRC))

    def test_pro_is_79_everywhere_and_no_50_left(self):
        self.assertIsNone(re.search(r"50 ?€|€ ?50\b", SRC)); self.assertIn("79€/mo", SRC); self.assertIn("79€/month", SRC)

    def test_former_pro_price_still_grants_pro(self):
        self.assertIn("STRIPE_PRICE_PRO_LEGACY", SRC); self.assertIn("pid==pro_price or pid in pro_legacy", SRC)

    def test_precise_budget_from_490_is_shown(self):
        self.assertIn("PRECISE_BUDGET_FROM_EUR = 490", SRC); self.assertIn("from € {PRECISE_BUDGET_FROM_EUR}", SRC)

    def test_packs_are_sold_only_behind_the_access_rules_flag(self):
        self.assertIn('_secret("ACCESS_RULES_ENABLED","0"))!="1"', SRC)               # off by default: the app behaves as before until the SQL migration is run and the flag set
        self.assertIn("_render_access_panel(_acc_ctx", SRC)
