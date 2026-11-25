"""In-memory stand-in for the Supabase REST transport used by menkor_orders (PostgREST filters eq / is.null / in / lt, unique keys, immutability triggers). Tests only."""
import copy


class FakeRest:
    UNIQUE = {"orders": ["id", "stripe_session_id"], "order_acceptances": ["id", "order_id"], "legal_document_versions": ["sha256"], "signup_acceptances": ["id"]}
    IMMUTABLE = {"order_acceptances", "legal_document_versions", "signup_acceptances"}      # the SQL triggers refuse UPDATE

    def __init__(self):
        self.t = {n: [] for n in ("orders", "order_acceptances", "legal_document_versions", "signup_acceptances", "market_listings")}
        self.fail_posts = set(); self.calls = []

    def _match(self, row, params):
        for k, cond in (params or {}).items():
            if k in ("select", "limit", "order", "on_conflict"): continue
            v = row.get(k)
            if cond.startswith("eq."):
                if str(v) != cond[3:]: return False
            elif cond == "is.null":
                if v is not None: return False
            elif cond.startswith("in.("):
                if str(v) not in cond[4:-1].split(","): return False
            elif cond.startswith("lt."):
                if not (v is not None and str(v) < cond[3:]): return False
        return True

    def __call__(self, method, table, params=None, json=None, prefer=None):
        name, _, q = table.partition("?"); params = dict(params or {}); self.calls.append((method, name))
        if name not in self.t: return 404, None
        rows = self.t[name]; prefer = prefer or ""
        if method == "GET":
            out = [copy.deepcopy(r) for r in rows if self._match(r, params)]
            if params.get("limit"): out = out[: int(params["limit"])]
            return 200, out
        if method == "POST":
            if name in self.fail_posts: return 500, None
            rec = copy.deepcopy(json)
            for col in self.UNIQUE.get(name, []):
                if rec.get(col) is not None and any(r.get(col) == rec[col] for r in rows):
                    return (201, None) if "ignore-duplicates" in prefer else (409, None)
            if name == "order_acceptances" and not any(r["id"] == rec["order_id"] for r in self.t["orders"]): return 409, None
            rows.append(rec); return 201, None
        if method == "PATCH":
            if name in self.IMMUTABLE: return 400, None          # trigger: evidence rows are immutable
            hit = [r for r in rows if self._match(r, params)]
            for r in hit: r.update(copy.deepcopy(json))
            return 200, ([copy.deepcopy(r) for r in hit] if "representation" in prefer else None)
        return 405, None


class Obj(dict):
    """Stripe-like object: dict with attribute access."""
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
