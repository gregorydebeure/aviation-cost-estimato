"""
Model-level access rules (v26) — packs, Pro quota, additional models.  Pure logic + two storage adapters; no Streamlit import.

Rules (validated by Greg, 19 Nov 2026):
  * Budget individuel 29 EUR  -> 1 model, 14 days.      Pack Comparaison 59 EUR -> 3 models, 14 days.
  * The buyer may CHANGE the unlocked models during the period (safeguard: MAX_MODEL_CHANGES_PER_24H replaced models per rolling 24 h).
  * Reports already downloaded stay with the buyer; the folders (access to the models) end with the period.
  * A second pack bought during the period ADDS its slots (it does not extend the dates).
  * Menkor Pro 79 EUR/month -> 10 NEW models per calendar month (UTC). Models unlocked stay accessible while Pro is active. Unused quota is NOT carried over.
  * Additional model: 15 EUR. Pro: +1 new model in the month of purchase (permanent while Pro). Pack holder: +1 slot for 14 days.
  * Regenerating / changing assumptions on an unlocked model never consumes anything. Comparative PDF only among unlocked models.
Everything here is server side: the app asks `AccessState.can_access(aircraft_id)` before computing, displaying or exporting a model.
Payments are verified against Stripe (no webhook): a grant exists only for a PAID Checkout Session created by this app (metadata) with the exact expected amount.
"""
from __future__ import annotations
import datetime as _dt

PACK_DAYS = 14
MAX_MODEL_CHANGES_PER_24H = 3          # anti-extraction safeguard (not a commercial rule): replaced models per rolling 24 h; adjustable
PRO_MODELS_PER_MONTH = 10
PRODUCTS = {
    "single":      dict(label="Budget individuel",  price_eur=29, slots=1, name="Aviation Cost Estimator — Budget individuel (1 model, 14 days)"),
    "comparison":  dict(label="Pack Comparaison",   price_eur=59, slots=3, name="Aviation Cost Estimator — Pack Comparaison (3 models, 14 days)"),
    "extra_model": dict(label="Additional model",   price_eur=15, slots=1, name="Aviation Cost Estimator — Additional model"),
}
TABLES = ("access_grants", "access_selection", "access_pro_unlocks")


def _parse(ts):
    if ts is None: return None
    if isinstance(ts, _dt.datetime): return ts if ts.tzinfo else ts.replace(tzinfo=_dt.timezone.utc)
    return _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(_dt.timezone.utc)


def _iso(d): return d.astimezone(_dt.timezone.utc).isoformat()
def month_of(d): d = _parse(d); return f"{d.year:04d}-{d.month:02d}"


# ── Stripe side ──────────────────────────────────────────────────────────────
def checkout_params(kind, email, ctx, success_url, cancel_url):
    """Parameters for stripe.checkout.Session.create (one-off payment). ctx = 'pro' when the buyer has an active Pro plan, else 'pack'."""
    p = PRODUCTS[kind]
    return dict(mode="payment", customer_email=email,
                line_items=[{"price_data": {"currency": "eur", "unit_amount": p["price_eur"] * 100, "product_data": {"name": p["name"]}}, "quantity": 1}],
                metadata={"product": kind, "ctx": "pro" if (ctx == "pro" and kind == "extra_model") else "pack"},
                success_url=success_url, cancel_url=cancel_url)


def grants_from_sessions(sessions, email, known_session_ids, report=None):
    """Pure: Stripe Checkout Sessions (dicts) -> new grant records. Only PAID one-off sessions of this app, exact amount, same e-mail, not already stored."""
    email = (email or "").strip().lower(); out = []
    for s in sessions or []:
        try:
            sid = s.get("id")
            def _skip(why):
                if report is not None: report.append(f"…{str(sid)[-6:]}: {why}")
            if not sid: continue
            if sid in known_session_ids: _skip("already stored"); continue
            md = s.get("metadata") or {}; kind = md.get("product")
            if kind not in PRODUCTS: _skip("not an access purchase (no product metadata)"); continue
            if s.get("mode") != "payment" or s.get("payment_status") != "paid": _skip(f"not paid (mode={s.get('mode')}, status={s.get('payment_status')})"); continue
            pr = PRODUCTS[kind]
            if s.get("currency") != "eur" or s.get("amount_total") != pr["price_eur"] * 100: _skip(f"amount/currency mismatch ({s.get('amount_total')} {s.get('currency')})"); continue
            who = ((s.get("customer_details") or {}).get("email") or s.get("customer_email") or "").strip().lower()
            if who != email: _skip("different e-mail"); continue
            bought = _dt.datetime.fromtimestamp(int(s["created"]), _dt.timezone.utc)
            ctx = md.get("ctx") or "pack"
            out.append(dict(session_id=sid, email=email, kind=kind, slots=pr["slots"], context=ctx, purchased_at=_iso(bought),
                            expires_at=_iso(bought + _dt.timedelta(days=PACK_DAYS)) if ctx == "pack" else None))
        except Exception:
            continue          # a malformed session never grants anything
    return out


LAST_SYNC = {}          # diagnostics of the last sync (read by the admin panel; contains no secret)


def _as_dict(x):
    """Stripe objects -> plain nested dicts, whatever the stripe-python version."""
    for m in ("to_dict_recursive", "to_dict"):
        f = getattr(x, m, None)
        if callable(f):
            try: return f()
            except Exception: pass
    return dict(x) if not isinstance(x, dict) else x


def sync_from_stripe(stripe_mod, store, email):
    """Reads the paid Checkout Sessions of this e-mail from Stripe and stores the missing grants. Returns the number of new grants. Never raises;
    what happened is left in LAST_SYNC (counts, skip reasons, error type)."""
    info = LAST_SYNC; info.clear(); info.update(email=email, sessions=0, new=0, stored=0, skipped=[], error=None)
    try:
        data = []
        try:
            resp = stripe_mod.checkout.Session.list(limit=100, status="complete", customer_details={"email": email})
            data = list(getattr(resp, "data", None) or (resp.get("data", []) if hasattr(resp, "get") else []))
        except Exception as e:
            info["filtered_error"] = f"{type(e).__name__}: {str(e)[:160]}"
        if not data:                                   # fallback: recent completed sessions, filtered by e-mail in code
            resp = stripe_mod.checkout.Session.list(limit=100, status="complete")
            data = list(getattr(resp, "data", None) or (resp.get("data", []) if hasattr(resp, "get") else []))
        sessions = [_as_dict(x) for x in data]
        info["sessions"] = len(sessions)
        known = {g["session_id"] for g in store.list_grants(email)}
        new = grants_from_sessions(sessions, email, known, info["skipped"])
        info["new"] = len(new)
        for g in new:
            if store.insert_grant(g) is not False: info["stored"] += 1
        return len(new)
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        return 0


# ── State & rules ────────────────────────────────────────────────────────────
class AccessState:
    def __init__(self, email, plan, grants, selection, pro_unlocks, now=None):
        self.email = (email or "").strip().lower(); self.plan = plan
        self.grants = list(grants or []); self.now = _parse(now) if now else _dt.datetime.now(_dt.timezone.utc)
        self.selection = list((selection or {}).get("aircraft_ids") or [])
        self.changes = [c for c in ((selection or {}).get("changes") or [])]
        self.pro_unlocks = list(pro_unlocks or [])

    # packs
    def pack_slots(self):
        return sum(int(g["slots"]) for g in self.grants if g.get("context") == "pack" and g.get("expires_at") and _parse(g["expires_at"]) > self.now)

    def pack_expiry(self):
        ex = [_parse(g["expires_at"]) for g in self.grants if g.get("context") == "pack" and g.get("expires_at") and _parse(g["expires_at"]) > self.now]
        return max(ex) if ex else None

    def pack_models(self):
        return self.selection[: self.pack_slots()]            # slots that expired drop the last selected models

    # Pro
    def pro_unlocked_ids(self):
        return [u["aircraft_id"] for u in self.pro_unlocks] if self.plan == "pro" else []

    def pro_quota_left(self):
        if self.plan != "pro": return 0
        m = month_of(self.now)
        extra = sum(int(g["slots"]) for g in self.grants if g.get("context") == "pro" and month_of(g["purchased_at"]) == m)
        used = sum(1 for u in self.pro_unlocks if u.get("month") == m)
        return max(0, PRO_MODELS_PER_MONTH + extra - used)

    # access
    def entitled_ids(self, all_ids):
        ids = set(self.pack_models()) | set(self.pro_unlocked_ids())
        return ids & set(all_ids)

    def can_access(self, aircraft_id, all_ids):
        return aircraft_id in self.entitled_ids(all_ids)

    def has_paid_access(self):
        return self.plan == "pro" or self.pack_slots() > 0

    # actions (return (ok, message, payload)); the caller persists payload
    def choose_pack_models(self, aircraft_ids, all_ids):
        ids = list(dict.fromkeys(aircraft_ids)); slots = self.pack_slots()
        if slots <= 0: return False, "No active pack.", None
        if len(ids) > slots: return False, f"Your pack unlocks {slots} model(s).", None
        if any(i not in set(all_ids) for i in ids): return False, "Unknown model.", None
        old = self.pack_models(); removed = [i for i in old if i not in ids]
        recent = [c for c in self.changes if (self.now - _parse(c)).total_seconds() < 86400]
        if len(recent) + len(removed) > MAX_MODEL_CHANGES_PER_24H:
            return False, f"Model changes are limited to {MAX_MODEL_CHANGES_PER_24H} per 24 hours.", None
        changes = recent + [_iso(self.now)] * len(removed)
        return True, "Models updated.", dict(email=self.email, aircraft_ids=ids, changes=changes, updated_at=_iso(self.now))

    def unlock_pro_model(self, aircraft_id, all_ids):
        if self.plan != "pro": return False, "Menkor Pro is required.", None
        if aircraft_id not in set(all_ids): return False, "Unknown model.", None
        if aircraft_id in self.pro_unlocked_ids(): return True, "Already unlocked.", None
        if self.pro_quota_left() <= 0: return False, f"Monthly quota reached ({PRO_MODELS_PER_MONTH} new models). You can add a model for € {PRODUCTS['extra_model']['price_eur']}.", None
        return True, "Model unlocked.", dict(email=self.email, aircraft_id=aircraft_id, month=month_of(self.now), unlocked_at=_iso(self.now))

    def summary(self):
        return dict(plan=self.plan, pack_slots=self.pack_slots(), pack_models=self.pack_models(), pack_expires_at=self.pack_expiry(),
                    pro_unlocked=self.pro_unlocked_ids(), pro_quota_left=self.pro_quota_left())


def load_state(store, email, plan, now=None):
    return AccessState(email, plan, store.list_grants(email), store.get_selection(email), store.list_pro_unlocks(email), now)


# ── Storage adapters ─────────────────────────────────────────────────────────
class MemoryStore:
    def __init__(self): self.grants, self.sel, self.unl = [], {}, []
    def list_grants(self, email): return [g for g in self.grants if g["email"] == email.lower()]
    def insert_grant(self, g):
        if not any(x["session_id"] == g["session_id"] for x in self.grants): self.grants.append(dict(g))
    def get_selection(self, email): return self.sel.get(email.lower())
    def set_selection(self, rec): self.sel[rec["email"]] = dict(rec)
    def list_pro_unlocks(self, email): return [u for u in self.unl if u["email"] == email.lower()]
    def insert_pro_unlock(self, rec):
        if not any(u["email"] == rec["email"] and u["aircraft_id"] == rec["aircraft_id"] for u in self.unl): self.unl.append(dict(rec))


class SupabaseStore:
    """rest(method, table, params=None, json=None, prefer=None) -> (status, data) — the app's existing `_sb_rest` transport (service key, server side)."""
    def __init__(self, rest): self.rest = rest
    def _get(self, table, email):
        st, data = self.rest("GET", table, {"email": f"eq.{email.lower()}", "select": "*"})
        return data if (st == 200 and isinstance(data, list)) else []
    def list_grants(self, email): return self._get("access_grants", email)
    def insert_grant(self, g):
        st, _ = self.rest("POST", "access_grants", {"on_conflict": "session_id"}, g, "resolution=ignore-duplicates,return=minimal")
        if st not in (200, 201, 204): LAST_SYNC["error"] = f"Supabase insert failed (HTTP {st})"; return False
        return True
    def get_selection(self, email):
        r = self._get("access_selection", email); return r[0] if r else None
    def set_selection(self, rec): self.rest("POST", "access_selection", {"on_conflict": "email"}, rec, "resolution=merge-duplicates,return=minimal")
    def list_pro_unlocks(self, email): return self._get("access_pro_unlocks", email)
    def insert_pro_unlock(self, rec): self.rest("POST", "access_pro_unlocks", {"on_conflict": "email,aircraft_id"}, rec, "resolution=ignore-duplicates,return=minimal")
    def tables_ready(self):
        return all(self.rest("GET", t, {"select": "email", "limit": "1"})[0] == 200 for t in TABLES if t != "access_grants") and self.rest("GET", "access_grants", {"select": "session_id", "limit": "1"})[0] == 200
