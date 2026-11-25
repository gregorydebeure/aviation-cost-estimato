"""Aircraft-for-sale marketplace — rules, storage and billing (no Streamlit import: everything here is testable on its own).

Commercial rules (Greg):
  * A Menkor Pro subscriber can list an aircraft with no extra fee (PRO_INCLUDED_LISTINGS active listing(s) — adjustable, NOT specified by Greg: flagged).
  * Anyone else lists an aircraft for 15 EUR / month per listing (Stripe subscription, cancellable at the end of the period).
  * Every listing is reviewed by the admin before it can go live. Payment is asked only AFTER approval.
  * A listing is visible only while it is paid (or included in an active Pro plan). The owner can mark it sold: it then stays visible with a red SOLD
    ribbon for SOLD_VISIBLE_DAYS days (adjustable, flagged).
  * Sample listings are clearly labelled SAMPLE; they are fictional and are never presented as real.
Billing is verified against Stripe (no webhook): paid_until is stored from the subscription's current period end at each sync.
"""
import datetime as _dt
import uuid as _uuid

LISTING_PRICE_EUR = 15
PRO_INCLUDED_LISTINGS = 1          # commercial rule not given by Greg: adjustable
SOLD_VISIBLE_DAYS = 30             # idem
STATUSES = ("draft", "pending", "published", "rejected", "sold", "withdrawn")
STATUS_LABEL = {"draft": "Draft", "pending": "Waiting for review", "published": "Approved", "rejected": "Rejected", "sold": "Sold", "withdrawn": "Withdrawn"}
CURRENCIES = ("EUR", "USD", "GBP", "AED", "CHF")
MAX_DESC = 2000
TABLES = ("market_listings", "market_leads")
LEAD_MAX_PER_DAY = 5               # per sender, anti-abuse


def _now(): return _dt.datetime.now(_dt.timezone.utc)
def _iso(d): return d.astimezone(_dt.timezone.utc).isoformat()


def _parse(ts):
    if ts is None or ts == "": return None
    if isinstance(ts, _dt.datetime): return ts if ts.tzinfo else ts.replace(tzinfo=_dt.timezone.utc)
    return _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(_dt.timezone.utc)


# ── validation ──────────────────────────────────────────────────────────────
def _num(v, kind=float):
    if v is None or str(v).strip() == "": return None
    try: return kind(str(v).replace(",", "").strip())
    except ValueError: return "bad"


def validate_listing(d, now=None):
    """Raw form dict -> (ok, errors, cleaned). Nothing is invented: optional fields stay None."""
    now = now or _now(); err = []; c = {}
    for k, lab in (("manufacturer", "Manufacturer"), ("model", "Model"), ("category", "Type"), ("country", "Country")):
        v = str(d.get(k) or "").strip()
        if not v: err.append(f"{lab} is required.")
        c[k] = v[:80]
    y = _num(d.get("year"), int)
    if y is None or y == "bad" or not (1960 <= y <= now.year + 1): err.append(f"Year must be between 1960 and {now.year + 1}.")
    c["year"] = y if isinstance(y, int) else None
    h = _num(d.get("total_hours"), float)
    if h == "bad" or (h is not None and not (0 <= h <= 100000)): err.append("Total hours must be between 0 and 100,000.")
    c["total_hours"] = h if isinstance(h, float) else None
    c["serial_number"] = (str(d.get("serial_number") or "").strip()[:40]) or None
    c["city"] = (str(d.get("city") or "").strip()[:80]) or None
    c["aircraft_id"] = (str(d.get("aircraft_id") or "").strip()) or None
    on_req = bool(d.get("price_on_request"))
    p = _num(d.get("price_amount"), float)
    if on_req: c["price_amount"] = None
    else:
        if p is None or p == "bad" or p <= 0: err.append("Enter a price, or tick “Price on request”.")
        c["price_amount"] = p if isinstance(p, float) else None
    c["price_on_request"] = on_req
    cur = str(d.get("price_currency") or "EUR").upper()
    if cur not in CURRENCIES: err.append("Unsupported currency.")
    c["price_currency"] = cur
    desc = str(d.get("description") or "").strip()
    if len(desc) < 20: err.append("Add a short description (at least 20 characters).")
    if len(desc) > MAX_DESC: err.append(f"Description is limited to {MAX_DESC} characters.")
    c["description"] = desc[:MAX_DESC]
    return (not err), err, c


# ── visibility & billing rules ──────────────────────────────────────────────
def new_listing(owner_email, cleaned, now=None):
    now = now or _now()
    r = dict(cleaned); r.update(id=_uuid.uuid4().hex[:16], owner_email=owner_email.strip().lower(), status="draft", billing=None, paid_until=None,
                                stripe_session_id=None, stripe_subscription_id=None, reject_reason=None, cancel_at_period_end=False,
                                created_at=_iso(now), updated_at=_iso(now), published_at=None, sold_at=None)
    return r


def pro_slots_used(listings, owner_email):
    """Active Pro-included listings of this owner (approved, billing=pro)."""
    o = owner_email.strip().lower()
    return sum(1 for l in listings if l.get("owner_email") == o and l.get("billing") == "pro" and l.get("status") == "published")


def billing_for(listings, owner_email, owner_plan, listing_id=None):
    """'pro' when the owner is a Pro subscriber and has a free included slot, else 'paid' (15 EUR / month)."""
    if owner_plan == "pro":
        others = [l for l in listings if l.get("id") != listing_id]
        if pro_slots_used(others, owner_email) < PRO_INCLUDED_LISTINGS: return "pro"
    return "paid"


def is_live(l, owner_plan, now=None):
    """Visible to the public? Sold listings stay visible SOLD_VISIBLE_DAYS days; approved ones only while paid / included in an active Pro plan."""
    now = now or _now(); st = l.get("status")
    if l.get("is_sample"): return True
    if st == "sold":
        sa = _parse(l.get("sold_at")); return bool(sa) and now - sa <= _dt.timedelta(days=SOLD_VISIBLE_DAYS)
    if st != "published": return False
    if l.get("billing") == "pro": return owner_plan == "pro"
    if l.get("billing") == "paid":
        pu = _parse(l.get("paid_until")); return bool(pu) and pu > now
    return False


def owner_state(l, owner_plan, now=None):
    """Human state for the owner's dashboard: (label, next_action) — next_action in {None,'submit','pay','relist'}."""
    now = now or _now(); st = l.get("status")
    if st == "draft": return "Draft — not submitted", "submit"
    if st == "pending": return "Waiting for review", None
    if st == "rejected": return "Rejected" + (f": {l['reject_reason']}" if l.get("reject_reason") else ""), "submit"
    if st == "sold": return "Marked as sold", None
    if st == "withdrawn": return "Withdrawn", None
    if st == "published":
        if is_live(l, owner_plan, now):
            if l.get("billing") == "pro": return "Live — included in your Pro plan", None
            pu = _parse(l.get("paid_until")); return f"Live until {pu:%d %b %Y}" + (" (will not renew)" if l.get("cancel_at_period_end") else ""), None
        if l.get("billing") == "pro": return "Approved — needs an active Pro plan to be visible", None
        return f"Approved — activate for € {LISTING_PRICE_EUR}/month to publish", "pay"
    return st, None


# ── search ──────────────────────────────────────────────────────────────────
def filter_listings(ls, category=None, manufacturer=None, country=None, year_min=None, hours_max=None, text=None, sort="newest"):
    out = []
    t = (text or "").strip().lower()
    for l in ls:
        if category and category != "All" and l.get("category") != category: continue
        if manufacturer and manufacturer != "All" and l.get("manufacturer") != manufacturer: continue
        if country and country != "All" and l.get("country") != country: continue
        if year_min and (l.get("year") or 0) < year_min: continue
        if hours_max is not None and hours_max != "" and l.get("total_hours") is not None and l["total_hours"] > hours_max: continue
        if t and t not in " ".join(str(l.get(k) or "") for k in ("manufacturer", "model", "city", "country", "category", "serial_number")).lower(): continue
        out.append(l)
    key = {"newest": lambda x: x.get("published_at") or x.get("created_at") or "", "year": lambda x: x.get("year") or 0,
           "hours": lambda x: -(x.get("total_hours") if x.get("total_hours") is not None else 10**9)}.get(sort, lambda x: "")
    out.sort(key=key, reverse=True)
    return out


def price_label(l):
    if l.get("price_on_request") or l.get("price_amount") is None: return "Price on request"
    sym = {"EUR": "€", "USD": "$", "GBP": "£", "AED": "AED ", "CHF": "CHF "}.get(l.get("price_currency"), "")
    return f"{sym}{l['price_amount']:,.0f}"


# ── samples: fictional, labelled SAMPLE, never real ─────────────────────────
def sample_listings():
    """Fictional demo listings (is_sample). The 'aircraft_id' only links to the cost engine; every figure here is a placeholder, not a real aircraft."""
    base = [
        ("dassault_falcon_7x", "Dassault", "Falcon 7X", "Ultra-long-range jets", 2012, 4200, "France", "Paris", 31500000, "EUR"),
        ("challenger_350", "Bombardier", "Challenger 350", "Super midsize jets", 2016, 2800, "United Arab Emirates", "Dubai", 14900000, "USD"),
        ("gulfstream_g550", "Gulfstream", "G550", "Ultra-long-range jets", 2010, 5100, "United States", "Teterboro", None, "USD"),
        ("cessna_citation_cj3_plus", "Cessna", "Citation CJ3+", "Light jets", 2014, 2300, "Germany", "Munich", 5200000, "EUR"),
        ("embraer_phenom_300", "Embraer", "Phenom 300", "Light jets", 2015, 3100, "United Kingdom", "Farnborough", 6900000, "GBP"),
        ("honda_hondajet", "Honda", "HondaJet", "Very light jets", 2018, 900, "Switzerland", "Geneva", 4800000, "CHF"),
    ]
    out = []
    for i, (aid, man, mod, cat, yr, hrs, ctry, city, price, cur) in enumerate(base, 1):
        out.append(dict(id=f"sample-{i}", is_sample=True, status="published", aircraft_id=aid, manufacturer=man, model=mod, category=cat, year=yr,
                        total_hours=float(hrs), country=ctry, city=city, price_amount=float(price) if price else None, price_on_request=price is None,
                        price_currency=cur, serial_number=None, owner_email="", billing="sample", paid_until=None,
                        description="SAMPLE LISTING — fictional demonstration entry shown to illustrate the marketplace. Not a real aircraft for sale; "
                                    "figures are placeholders. Real listings appear here once brokers publish them.",
                        created_at=_iso(_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc)), published_at=_iso(_dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc))))
    return out


# ── Stripe side ─────────────────────────────────────────────────────────────
def checkout_params(listing, success_url, cancel_url):
    """Stripe Checkout subscription for one listing (15 EUR / month). Metadata ties the session to the listing."""
    name = f"Aviation Cost Estimator — Aircraft listing: {listing.get('manufacturer','')} {listing.get('model','')}".strip()[:120]
    md = {"product": "listing", "listing_id": listing["id"]}
    return dict(mode="subscription", customer_email=listing["owner_email"],
                line_items=[{"price_data": {"currency": "eur", "unit_amount": LISTING_PRICE_EUR * 100, "recurring": {"interval": "month"},
                                            "product_data": {"name": name}}, "quantity": 1}],
                metadata=md, subscription_data={"metadata": md}, success_url=success_url, cancel_url=cancel_url)


def _get(o, k, default=None):
    try:
        v = o.get(k, default) if hasattr(o, "get") else getattr(o, k, default)
    except Exception: v = default
    return default if v is None else v


def _period_end(sub):
    """current_period_end moved onto the subscription items in recent Stripe API versions: accept both."""
    pe = _get(sub, "current_period_end")
    if pe: return int(pe)
    items = _get(_get(sub, "items", {}), "data", [])
    ends = [int(_get(i, "current_period_end")) for i in items if _get(i, "current_period_end")]
    return max(ends) if ends else None


def billing_update_from_subscription(sub, listing):
    """Pure: Stripe subscription -> fields to store. Only an active/trialing subscription created for THIS listing (metadata) counts."""
    if _get(_get(sub, "metadata", {}), "listing_id") != listing["id"]: return None
    items = _get(_get(sub, "items", {}), "data", [])
    price = _get(items[0], "price", {}) if items else {}
    if items and (_get(price, "unit_amount") != LISTING_PRICE_EUR * 100 or _get(price, "currency") != "eur"): return None
    if _get(sub, "status") not in ("active", "trialing"): return dict(cancel_at_period_end=bool(_get(sub, "cancel_at_period_end", False)))
    pe = _period_end(sub)
    if not pe: return None
    return dict(paid_until=_iso(_dt.datetime.fromtimestamp(pe, _dt.timezone.utc)), stripe_subscription_id=_get(sub, "id"),
                cancel_at_period_end=bool(_get(sub, "cancel_at_period_end", False)))


LAST_SYNC = {}


def sync_listing_billing(stripe_mod, store, listing, allowed_order_ids=None):
    """Reads Stripe for one listing (checkout session, then subscription) and stores paid_until. Returns the updated listing. Never raises; details in LAST_SYNC."""
    LAST_SYNC.clear(); LAST_SYNC.update(listing=listing.get("id"), error=None, note=None)
    try:
        sub_id = listing.get("stripe_subscription_id")
        if not sub_id and listing.get("stripe_session_id"):
            s = stripe_mod.checkout.Session.retrieve(listing["stripe_session_id"])
            if _get(s, "status") != "complete" or _get(s, "mode") != "subscription": LAST_SYNC["note"] = "checkout not completed"; return listing
            if _get(_get(s, "metadata", {}), "listing_id") != listing["id"]: LAST_SYNC["note"] = "session belongs to another listing"; return listing
            if allowed_order_ids is not None and _get(_get(s, "metadata", {}), "order_id") not in allowed_order_ids:      # legal order flow on: a listing is billed only through an accepted, paid order
                LAST_SYNC["note"] = "no paid and accepted order for this checkout"; return listing
            if str(_get(s, "customer_email") or _get(_get(s, "customer_details", {}), "email") or "").lower() != listing["owner_email"]:
                LAST_SYNC["note"] = "different e-mail"; return listing
            sub_id = _get(s, "subscription")
            sub_id = _get(sub_id, "id") if not isinstance(sub_id, str) and sub_id else sub_id
        if not sub_id: LAST_SYNC["note"] = "no subscription yet"; return listing
        sub = stripe_mod.Subscription.retrieve(sub_id)
        upd = billing_update_from_subscription(sub, listing)
        if not upd: LAST_SYNC["note"] = "subscription not valid for this listing"; return listing
        listing = dict(listing); listing.update(upd); listing["updated_at"] = _iso(_now())
        store.update(listing["id"], upd | {"updated_at": listing["updated_at"]})
        return listing
    except Exception as e:
        LAST_SYNC["error"] = f"{type(e).__name__}: {str(e)[:160]}"; return listing


def cancel_at_period_end(stripe_mod, store, listing):
    """Owner stops the subscription: stays visible until the end of the paid period."""
    sub_id = listing.get("stripe_subscription_id")
    if not sub_id: return False, "No active subscription for this listing."
    try:
        stripe_mod.Subscription.modify(sub_id, cancel_at_period_end=True)
        store.update(listing["id"], {"cancel_at_period_end": True}); return True, "The listing stays visible until the end of the paid period and will not renew."
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:120]}"


# ── leads ───────────────────────────────────────────────────────────────────
def lead_allowed(leads, from_email, now=None):
    now = now or _now(); n = 0
    for l in leads:
        ts = _parse(l.get("created_at"))
        if l.get("from_email") == from_email.strip().lower() and ts and now - ts <= _dt.timedelta(days=1): n += 1
    return n < LEAD_MAX_PER_DAY


def new_lead(listing, from_email, from_name, message, now=None):
    return dict(id=_uuid.uuid4().hex[:16], listing_id=listing["id"], owner_email=listing["owner_email"], from_email=from_email.strip().lower(),
                from_name=(from_name or "").strip()[:80], message=(message or "").strip()[:1500], created_at=_iso(now or _now()))


# ── stores ──────────────────────────────────────────────────────────────────
class MemoryStore:
    def __init__(self): self.rows, self.leads = {}, []
    def list_all(self): return [dict(r) for r in self.rows.values()]
    def list_owner(self, email): return [dict(r) for r in self.rows.values() if r["owner_email"] == email.strip().lower()]
    def list_status(self, *sts): return [dict(r) for r in self.rows.values() if r["status"] in sts]
    def get(self, lid): return dict(self.rows[lid]) if lid in self.rows else None
    def insert(self, rec): self.rows[rec["id"]] = dict(rec); return True
    def update(self, lid, fields):
        if lid in self.rows: self.rows[lid].update(fields); return True
        return False
    def list_leads_from(self, email): return [l for l in self.leads if l["from_email"] == email.strip().lower()]
    def insert_lead(self, rec): self.leads.append(dict(rec)); return True


class SupabaseStore:
    """rest(method, table, params=None, json=None, prefer=None) -> (status, data): the app's `_sb_rest` (service key, server side)."""
    def __init__(self, rest): self.rest = rest
    def _list(self, params):
        st, data = self.rest("GET", "market_listings", dict(params, select="*", limit="500")); return data if (st == 200 and isinstance(data, list)) else []
    def list_all(self): return self._list({})
    def list_owner(self, email): return self._list({"owner_email": f"eq.{email.strip().lower()}"})
    def list_status(self, *sts): return self._list({"status": "in.(" + ",".join(sts) + ")"})
    def get(self, lid):
        r = self._list({"id": f"eq.{lid}"}); return r[0] if r else None
    def insert(self, rec): return self.rest("POST", "market_listings", None, rec, "return=minimal")[0] in (200, 201, 204)
    def update(self, lid, fields): return self.rest("PATCH", "market_listings", {"id": f"eq.{lid}"}, fields, "return=minimal")[0] in (200, 204)
    def list_leads_from(self, email):
        st, data = self.rest("GET", "market_leads", {"from_email": f"eq.{email.strip().lower()}", "select": "*", "limit": "50"})
        return data if (st == 200 and isinstance(data, list)) else []
    def insert_lead(self, rec): return self.rest("POST", "market_leads", None, rec, "return=minimal")[0] in (200, 201, 204)
    def tables_ready(self):
        return all(self.rest("GET", t, {"select": "id", "limit": "1"})[0] == 200 for t in TABLES)
