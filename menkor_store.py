"""Menkor — personal scenarios, client folders, broker profile and anonymous product events (Lot C).

Design
- Pure logic with an INJECTED transport `rest(method, table, params=None, json=None, prefer=None) -> (status, data)`; the app plugs the existing Supabase
  REST access (service key, server side). Nothing here talks to the network by itself and nothing is sent anywhere in tests.
- Owner isolation is enforced SERVER-SIDE by the app code: the owner is always the authenticated session e-mail passed by the caller, never a
  value typed by the user, and EVERY read / update / delete adds `owner_email=eq.<owner>`. Row Level Security is also enabled in the migration
  (no policy for anon / authenticated roles, so only the server's service key can reach the tables).
- Deletion is a soft delete (`deleted_at`) so it can be recovered; a purge is a separate explicit action.
- A saved scenario keeps: every assumption (Scenario.canonical()), the base version and engine version at save time, the save date, which fields
  the user changed versus the defaults, and a snapshot of the main results AS SAVED. Reloading never recomputes silently.
"""
from __future__ import annotations
import base64, copy, dataclasses, datetime as _dt, hashlib, re, uuid

import menkor_engine as E

MAX_NAME = 80
MAX_SCENARIOS_PER_OWNER = 200          # technical safeguard, not a commercial limit
MAX_FOLDERS_PER_OWNER = 100
MAX_LOGO_BYTES = 400_000
MAX_BROKER_NAME = 80

# ─────────────────────────────── helpers ───────────────────────────────
def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _clean_name(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "")).strip()
    return n[:MAX_NAME]


def _owner(owner: str) -> str:
    o = (owner or "").strip().lower()
    if not o or "@" not in o:
        raise PermissionError("authenticated owner required")
    return o


def _ok(status) -> bool:
    return status in (200, 201, 204)


def _eq(v) -> str:
    return f"eq.{v}"


# ─────────────────────────────── Scenario <-> dict ───────────────────────────────
def scenario_to_dict(scn: E.Scenario) -> dict:
    return scn.canonical()


def scenario_from_dict(d: dict) -> E.Scenario:
    """Rebuild a Scenario from its stored dict. Unknown stored keys are ignored; missing keys take the dataclass default (never an invented value)."""
    d = dict(d or {})
    fx = d.pop("fx", None) or {}
    fu = d.pop("fuel", None) or {}
    fx_names = {f.name for f in dataclasses.fields(E.Fx)}
    fu_names = {f.name for f in dataclasses.fields(E.FuelConfig)}
    sc_names = {f.name for f in dataclasses.fields(E.Scenario)}
    kw = {k: v for k, v in d.items() if k in sc_names}
    kw["fx"] = E.Fx(**{k: v for k, v in fx.items() if k in fx_names})
    kw["fuel"] = E.FuelConfig(**{k: v for k, v in fu.items() if k in fu_names})
    return E.Scenario(**kw)


def user_entered_fields(scn: E.Scenario) -> list[str]:
    """Assumptions the user really supplied (typed or chosen), as opposed to defaults and reference data.
    A field only counts when it carries an entered value: a default or an empty field is never listed."""
    out = []
    if scn.billed_hours or scn.positioning_hours or scn.other_hours: out.append("hours")
    f = scn.fuel
    if f.price is not None: out.append("fuel_price")
    if f.price_source in ("benchmark", "manual"): out.append("fuel_price_method")
    if f.burn_method != "published": out.append("fuel_burn_method")
    if scn.charter_rate is not None:
        out.append("charter_rate")
        if scn.commission_pct is not None: out.append("commission_pct")
    for k in ("other_commercial_fees", "extra_fixed", "extra_var_h"):
        if getattr(scn, k): out.append(k)
    for k in ("supplements_retained_usd", "supplements_cost_usd", "depreciation_annual", "interest_annual", "positioning_ratio"):
        if getattr(scn, k) is not None: out.append(k)
    if scn.fixed_overrides: out.append("fixed_cost_edits")
    if scn.var_overrides_h: out.append("variable_cost_edits")
    if any((v or {}).get("amount") for v in (scn.management or {}).values()): out.append("management")
    if scn.cycle_status != "none": out.append("cost_per_landing")
    if any(((v or {}).get("count") or 0) * ((v or {}).get("salary") or 0) > 0 for v in (scn.additional_crew or {}).values()): out.append("crew_additional")
    if scn.other_maint_program_h: out.append("other_maintenance_programme")
    if scn.fx.usd_to_eur: out.append("exchange_rate")
    return sorted(set(out))


def results_snapshot(res: dict) -> dict:
    """Main figures AS CALCULATED when the scenario is saved. Missing stays None (never zero)."""
    pr = res.get("profit") or {}
    return dict(available=bool(res.get("available")), budget_usd=res.get("budget_usd"), cost_per_h_usd=res.get("cost_per_h_usd"),
                fixed_annual_usd=(res.get("fixed") or {}).get("annual_total"), variable_annual_usd=(res.get("variable") or {}).get("annual"),
                flown_hours=(res.get("hours") or {}).get("flown"), operating_result_usd=pr.get("operating_result"),
                config_hash=res.get("config_hash"), model=res.get("model"))


def version_status(stored: dict) -> dict:
    """Compare the versions a scenario was saved with against the running ones. Never claims 'identical' when they differ."""
    db_changed = stored.get("db_version") != E.DB_VERSION
    eng_changed = stored.get("engine_version") != E.ENGINE_VERSION
    return dict(db_changed=db_changed, engine_changed=eng_changed, changed=db_changed or eng_changed,
                saved_db=stored.get("db_version"), saved_engine=stored.get("engine_version"), current_db=E.DB_VERSION, current_engine=E.ENGINE_VERSION)


# ─────────────────────────────── scenarios ───────────────────────────────
def save_scenario(rest, owner, name, scn: E.Scenario, res: dict, folder_id=None, msn: str = ""):
    o = _owner(owner); n = _clean_name(name)
    if not n:
        return False, "Please enter a name for the scenario."
    cnt = count_scenarios(rest, o)
    if cnt is None:
        return False, "Storage is not available right now: nothing was saved."
    if cnt >= MAX_SCENARIOS_PER_OWNER:
        return False, f"Limit of {MAX_SCENARIOS_PER_OWNER} saved scenarios reached: delete one first."
    if folder_id and not get_folder(rest, o, folder_id):
        return False, "Unknown folder."
    row = dict(id=str(uuid.uuid4()), owner_email=o, name=n, folder_id=folder_id or None, aircraft_id=scn.aircraft_id,
               payload=dict(scenario=scenario_to_dict(scn), user_entered=user_entered_fields(scn), snapshot=results_snapshot(res), msn=_clean_name(msn or "")[:40]),
               db_version=E.DB_VERSION, engine_version=E.ENGINE_VERSION, config_hash=res.get("config_hash"),
               created_at=_now(), updated_at=_now(), deleted_at=None)
    st_, data = rest("POST", "scenarios", json=row)
    if not _ok(st_):
        return False, "Storage refused the save: nothing was saved."
    return True, row["id"]


def count_scenarios(rest, owner):
    st_, data = rest("GET", "scenarios", params={"owner_email": _eq(_owner(owner)), "deleted_at": "is.null", "select": "id"})
    return len(data) if _ok(st_) and isinstance(data, list) else None


def list_scenarios(rest, owner, folder_id=None, deleted=False):
    p = {"owner_email": _eq(_owner(owner)), "select": "*", "order": "updated_at.desc",
         "deleted_at": "not.is.null" if deleted else "is.null"}
    if folder_id:
        p["folder_id"] = _eq(folder_id)
    st_, data = rest("GET", "scenarios", params=p)
    return data if _ok(st_) and isinstance(data, list) else []


def get_scenario(rest, owner, sid):
    st_, data = rest("GET", "scenarios", params={"owner_email": _eq(_owner(owner)), "id": _eq(sid), "select": "*"})
    return data[0] if _ok(st_) and isinstance(data, list) and data else None


def get_scenarios_for_compare(rest, owner, ids):
    """Owner-filtered, non-deleted scenarios for a comparison, in the order requested. Another owner's id simply returns nothing."""
    out = []
    for sid in dict.fromkeys(ids or []):
        it = get_scenario(rest, owner, sid)
        if it and not it.get("deleted_at"):
            out.append(it)
    return out


def _patch(rest, owner, sid, fields):
    f = dict(fields); f["updated_at"] = _now()
    st_, data = rest("PATCH", "scenarios", params={"owner_email": _eq(_owner(owner)), "id": _eq(sid)}, json=f)
    return _ok(st_)


def rename_scenario(rest, owner, sid, name):
    n = _clean_name(name)
    if not n:
        return False
    return _patch(rest, owner, sid, {"name": n}) if get_scenario(rest, owner, sid) else False


def move_scenario(rest, owner, sid, folder_id):
    if folder_id and not get_folder(rest, owner, folder_id):
        return False
    return _patch(rest, owner, sid, {"folder_id": folder_id or None}) if get_scenario(rest, owner, sid) else False


def duplicate_scenario(rest, owner, sid):
    o = _owner(owner); src = get_scenario(rest, o, sid)
    if not src or src.get("deleted_at"):
        return False, "Scenario not found."
    cnt = count_scenarios(rest, o)
    if cnt is None or cnt >= MAX_SCENARIOS_PER_OWNER:
        return False, "Storage unavailable or limit reached."
    row = {k: v for k, v in src.items()}
    row.update(id=str(uuid.uuid4()), name=_clean_name(f"{src['name']} (copy)"), created_at=_now(), updated_at=_now(), deleted_at=None)
    st_, _ = rest("POST", "scenarios", json=row)
    return (True, row["id"]) if _ok(st_) else (False, "Storage refused the copy.")


def delete_scenario(rest, owner, sid, confirmed: bool):
    """Soft delete, only with an explicit confirmation. Recoverable with restore_scenario."""
    if not confirmed:
        return False
    return _patch(rest, owner, sid, {"deleted_at": _now()}) if get_scenario(rest, owner, sid) else False


def restore_scenario(rest, owner, sid):
    return _patch(rest, owner, sid, {"deleted_at": None}) if get_scenario(rest, owner, sid) else False


def purge_scenario(rest, owner, sid, confirmed: bool):
    """Irreversible removal of a scenario that is already in the bin."""
    o = _owner(owner); s = get_scenario(rest, o, sid)
    if not confirmed or not s or not s.get("deleted_at"):
        return False
    st_, _ = rest("DELETE", "scenarios", params={"owner_email": _eq(o), "id": _eq(sid)})
    return _ok(st_)


# ─────────────────────────────── folders ───────────────────────────────
def create_folder(rest, owner, name):
    o = _owner(owner); n = _clean_name(name)
    if not n:
        return False, "Please enter a folder name."
    if len(list_folders(rest, o)) >= MAX_FOLDERS_PER_OWNER:
        return False, "Folder limit reached."
    row = dict(id=str(uuid.uuid4()), owner_email=o, name=n, created_at=_now(), deleted_at=None)
    st_, _ = rest("POST", "folders", json=row)
    return (True, row["id"]) if _ok(st_) else (False, "Storage refused the folder.")


def list_folders(rest, owner):
    st_, data = rest("GET", "folders", params={"owner_email": _eq(_owner(owner)), "deleted_at": "is.null", "select": "*", "order": "name.asc"})
    return data if _ok(st_) and isinstance(data, list) else []


def get_folder(rest, owner, fid):
    st_, data = rest("GET", "folders", params={"owner_email": _eq(_owner(owner)), "id": _eq(fid), "deleted_at": "is.null", "select": "*"})
    return data[0] if _ok(st_) and isinstance(data, list) and data else None


def rename_folder(rest, owner, fid, name):
    n = _clean_name(name)
    if not n or not get_folder(rest, owner, fid):
        return False
    st_, _ = rest("PATCH", "folders", params={"owner_email": _eq(_owner(owner)), "id": _eq(fid)}, json={"name": n})
    return _ok(st_)


def delete_folder(rest, owner, fid, confirmed: bool):
    """Removes the folder only; its scenarios are KEPT and become 'no folder'."""
    o = _owner(owner)
    if not confirmed or not get_folder(rest, o, fid):
        return False
    rest("PATCH", "scenarios", params={"owner_email": _eq(o), "folder_id": _eq(fid)}, json={"folder_id": None})
    st_, _ = rest("PATCH", "folders", params={"owner_email": _eq(o), "id": _eq(fid)}, json={"deleted_at": _now()})
    return _ok(st_)


# ─────────────────────────────── broker profile ───────────────────────────────
def detect_image(b: bytes):
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:3] == b"\xff\xd8\xff":
        return "jpeg"
    return None


def validate_logo(b: bytes | None):
    """(ok, message). Only real PNG / JPEG files, bounded size."""
    if not b:
        return True, ""
    if len(b) > MAX_LOGO_BYTES:
        return False, f"Logo too large (max {MAX_LOGO_BYTES // 1000} KB)."
    if not detect_image(b):
        return False, "Logo must be a PNG or JPEG image."
    return True, ""


def save_broker_profile(rest, owner, broker_name, logo: bytes | None):
    o = _owner(owner); bn = re.sub(r"\s+", " ", (broker_name or "")).strip()[:MAX_BROKER_NAME]
    ok, msg = validate_logo(logo)
    if not ok:
        return False, msg
    row = dict(owner_email=o, broker_name=bn, logo_b64=base64.b64encode(logo).decode() if logo else None, updated_at=_now())
    st_, _ = rest("POST", "broker_profiles", params={"on_conflict": "owner_email"}, json=row, prefer="resolution=merge-duplicates")
    return (True, "") if _ok(st_) else (False, "Storage refused the profile.")


def get_broker_profile(rest, owner):
    st_, data = rest("GET", "broker_profiles", params={"owner_email": _eq(_owner(owner)), "select": "*"})
    if not (_ok(st_) and isinstance(data, list) and data):
        return None
    d = data[0]
    try:
        logo = base64.b64decode(d["logo_b64"]) if d.get("logo_b64") else None
    except Exception:
        logo = None
    if logo and not validate_logo(logo)[0]:
        logo = None
    return dict(broker_name=d.get("broker_name") or "", logo=logo)


def delete_broker_profile(rest, owner):
    st_, _ = rest("DELETE", "broker_profiles", params={"owner_email": _eq(_owner(owner))})
    return _ok(st_)


# ─────────────────────────────── comparison (Pro) ───────────────────────────────
CMP_INDICATIVE_NOTE = "Model-level estimates, not aircraft-specific budgets. Management fees excluded unless explicitly added."
CMP_INDICATIVE_BASE = ("Indicative comparison: each model's average costs, the aircraft's own fuel burn, and the common hours and fuel price. "
                       "No Cost Master edit is applied.")
CMP_HOURS_NOTE = "Equal annual hours do not imply equivalent missions or aircraft capabilities."
CMP_NO_RANKING_NOTE = ("Operating budget and economic cost are shown separately and are never ranked together. Compare figures only when the scope and the assumptions "
                       "shown are the same; a lower figure is not a recommendation.")
CMP_HARMONISE_HOURS_NOTE = ("Total flown hours are replaced; billed, positioning and other hours are scaled proportionally so the original split is kept "
                            "(a scenario with no hours gets them as non-billed hours).")
MGMT_KEYS = ("management", "aoc", "camo", "dispatch")


def _price_problem(v):
    """None = fine. A price that is entered but invalid is reported, never silently replaced by the common value."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "Fuel price must be a number."
    if f != f or f in (float("inf"), float("-inf")) or f <= 0:
        return "Fuel price must be greater than zero."
    return E.fuel_price_implausible(f)


def _hours_problem(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "Annual flown hours must be a number."
    if f != f or f < 0 or f > 8760:
        return "Annual flown hours must be between 0 and 8,760."
    return None


def _result_row(key, label, scn: E.Scenario, res: dict, extra: dict | None = None) -> dict:
    """One comparison line from the SAME engine result used everywhere else. Missing stays None (never zero)."""
    fuel = res.get("fuel") or {}
    mg = res.get("management") or {}
    mg_added = [k for k in MGMT_KEYS if (mg.get(k) or {}).get("status") == "added"]
    mg_total = sum((mg[k].get("amount_usd") or 0.0) for k in mg_added)
    crew = res.get("crew_additional") or {}
    crew_added = any((v or {}).get("status") == "added" for v in crew.values())
    dep = intr = None
    if scn.depreciation_annual is not None:
        dep, _e = E.amount_to_usd(scn.depreciation_annual, scn.depreciation_ccy, scn.fx)
    if scn.interest_annual is not None:
        intr, _e = E.amount_to_usd(scn.interest_annual, scn.interest_ccy, scn.fx)
    budget = res.get("budget_usd")
    econ = (budget + dep + intr) if (budget is not None and dep is not None and intr is not None) else None
    not_entered = []
    if not mg_added: not_entered.append("management fee")
    if not crew_added: not_entered.append("additional crew")
    if (mg.get("gov_taxes") or {}).get("status") != "added": not_entered.append("government taxes")
    if dep is None: not_entered.append("depreciation")
    if intr is None: not_entered.append("loan interest")
    row = dict(key=key, label=label, aircraft_id=scn.aircraft_id, model=res.get("model"), available=bool(res.get("available")),
               hours=(res.get("hours") or {}).get("flown"), burn_l_h=fuel.get("burn_l_h"), fuel_price_usd_l=fuel.get("price_usd_l"),
               fuel_price_entered=scn.fuel.price, fuel_price_ccy=scn.fuel.currency, fuel_method=scn.fuel.price_source,
               fixed_annual_usd=(res.get("fixed") or {}).get("annual_total"), variable_annual_usd=(res.get("variable") or {}).get("annual"),
               budget_usd=budget, cost_per_h_usd=res.get("cost_per_h_usd"),
               management_included_usd=mg_total if mg_added else None, management_text=(f"Included: {', '.join(mg_added)}" if mg_added else "Excluded (not entered)"),
               not_entered=not_entered, depreciation_usd=dep, interest_usd=intr, economic_cost_usd=econ,
               mode=scn.mode, config_hash=res.get("config_hash"),
               flags=[f["text"] for f in res.get("flags", []) if f.get("level") in ("warn", "error")][:3])
    row.update(_charter_fields(scn, res, budget))
    row.update(extra or {})
    return row


_MAINT_KEYS = ("airframe_maint", "engine_apu_maint", "other_maint_program")
_EDIT_LABELS = (("fixed_cost_edits", "fixed cost edits"), ("variable_cost_edits", "variable cost edits"), ("extra_fixed", "added fixed cost"),
                ("extra_var_h", "added variable cost"), ("crew_additional", "additional crew"), ("other_maintenance_programme", "other maintenance programme"),
                ("cost_per_landing", "cost per landing"), ("other_commercial_fees", "other commercial fees"))


def _charter_fields(scn: E.Scenario, res: dict, budget) -> dict:
    """Everything the saved-scenario comparison shows besides the cost lines — read from the SAME engine result (no formula of its own here).
    Missing stays None (never zero). The cost split (fixed / fuel / maintenance / other variable) uses the engine's exclusive components and always adds up to the budget."""
    hrs = res.get("hours") or {}
    out = dict(billed_hours=hrs.get("billed"), positioning_hours=hrs.get("positioning"), owner_hours=hrs.get("other"),
               fuel_method_label=scn.fuel.price_source, charter_available=False, charter_messages=[], rate_usd=None, rate_basis=None, commission_pct=None,
               revenue_usd=None, commission_usd=None, net_revenue_usd=None, other_annual_net_usd=None, operating_result_usd=None, owner_flight=None,
               economic_result_usd=None, cost_split=None, edits=[lab for k, lab in _EDIT_LABELS if k in user_entered_fields(scn)]
               + (["management"] if "management" in user_entered_fields(scn) else []))
    if res.get("available"):
        comps = res.get("components") or []
        fixed = (res.get("fixed") or {}).get("annual_total")
        fuel = sum(c["annual_usd"] for c in comps if c["category"] == "Variable" and c["key"] == "fuel")
        maint = sum(c["annual_usd"] for c in comps if c["category"] == "Variable" and c["key"] in _MAINT_KEYS)
        other = sum(c["annual_usd"] for c in comps if c["category"] == "Variable" and c["key"] != "fuel" and c["key"] not in _MAINT_KEYS)
        out["cost_split"] = dict(fixed=fixed, fuel=fuel, maintenance=maint, other_variable=other)
    pr = res.get("profit")
    if pr and pr.get("available"):
        out.update(charter_available=True, rate_usd=pr.get("rate_usd"), rate_basis=pr.get("rate_basis"), commission_pct=pr.get("commission_pct"),
                   revenue_usd=pr["revenue"], commission_usd=pr["commission"], net_revenue_usd=pr["revenue"] - pr["commission"],
                   other_annual_net_usd=pr.get("other_annual_net"), operating_result_usd=pr["operating_result"], owner_flight=pr.get("owner_flight"),
                   economic_result_usd=pr.get("economic_result"))
    elif pr:
        out["charter_messages"] = list(pr.get("messages") or [])
    return out


def compare_aircraft(df, ids, common: dict, adjustments: dict | None = None):
    """INDICATIVE model comparison: each model's own cost base, COMMON annual hours and fuel price, the aircraft's own burn.
    common: flown_hours (float|None), fuel_price (float|None), fuel_ccy ('USD'|'EUR'), fx (E.Fx).
    adjustments: {aircraft_id: {"flown_hours": x, "fuel_price": y}} — explicit, labelled, never applied to another aircraft.
      empty (None / key absent) = the common value is used; an entered 0 is a real zero (hours); an invalid price is an ERROR, never a silent fallback.
    Zero hours keep the fixed costs and give a cost per hour of None ('n/a'). No Cost Master edit is injected."""
    ids = list(dict.fromkeys(ids))
    if not 2 <= len(ids) <= 3:
        raise ValueError("compare 2 or 3 aircraft")
    adj = adjustments or {}
    out = []
    for aid in ids:
        sub = df[df["aircraft_id"] == aid]
        if not len(sub):
            out.append(dict(aircraft_id=aid, label=aid, available=False, missing=["aircraft not in the database"], errors=[], adjusted=[])); continue
        row = sub.iloc[0]; a = adj.get(aid) or {}
        hours = a["flown_hours"] if a.get("flown_hours") is not None else common.get("flown_hours")
        price = a["fuel_price"] if a.get("fuel_price") is not None else common.get("fuel_price")
        adjusted = [k for k in ("flown_hours", "fuel_price") if a.get(k) is not None]
        errors = [e for e in (_hours_problem(hours), _price_problem(price)) if e]
        missing = []
        if hours is None: missing.append("annual flown hours")
        if price is None: missing.append("fuel price")
        if errors or missing:
            out.append(dict(aircraft_id=aid, label=str(row["model"]), model=str(row["model"]), available=False, missing=missing, errors=errors, adjusted=adjusted)); continue
        scn = E.Scenario(aircraft_id=aid, mode="simulation", other_hours=float(hours), fx=common.get("fx") or E.Fx(),
                         fuel=E.FuelConfig(price_source="average", price=float(price), currency=common.get("fuel_ccy", "USD")))
        res = E.compute(row, scn)
        r = _result_row(aid, str(row["model"]), scn, res, dict(adjusted=adjusted, errors=[], missing=[] if res["available"] else ["incomplete reference data"]))
        r["fuel_price"] = float(price); r["hours"] = float(hours)
        out.append(r)
    return out


# ─────────────────────────────── comparison of SAVED scenarios (same engine as Cost Master) ───────────────────────────────
def harmonise(scn: E.Scenario, common: dict):
    """Return (copy, replaced) — the copy carries the common hours / fuel price; the stored scenario is never touched.
    replaced: {"flown_hours": (old, new), "fuel_price": (old, new)} for what was really replaced."""
    c = copy.deepcopy(scn); replaced = {}
    h = common.get("flown_hours")
    if h is not None:
        old = scn.flown_hours
        if old > 0:
            k = float(h) / old
            c.billed_hours = scn.billed_hours * k; c.positioning_hours = scn.positioning_hours * k; c.other_hours = scn.other_hours * k
        else:
            c.billed_hours = 0.0; c.positioning_hours = 0.0; c.other_hours = float(h)
        replaced["flown_hours"] = (old, float(h))
    p = common.get("fuel_price")
    if p is not None:
        old_p = (scn.fuel.price, scn.fuel.currency, scn.fuel.price_source)
        c.fuel = dataclasses.replace(scn.fuel, price_source="average", price=float(p), currency=common.get("fuel_ccy", "USD"), benchmark_region="")
        replaced["fuel_price"] = (old_p, (float(p), common.get("fuel_ccy", "USD"), "average"))
    return c, replaced


def recalc_key(it: dict) -> str:
    """Identity of a (scenario, saved versions, running versions) triple: an explicit recalculation is valid for exactly this."""
    return f"{it.get('id')}|{it.get('db_version')}|{it.get('engine_version')}|{E.DB_VERSION}|{E.ENGINE_VERSION}"


def compare_saved(df, items: list, common: dict | None = None, recalc_ok=None):
    """Compare 2–3 SAVED scenarios with the same engine as Cost Master. Each keeps its own aircraft and assumptions (default).
    common (optional, explicit): flown_hours / fuel_price / fuel_ccy — applied to a COPY, the saved scenarios are never modified; what was replaced is listed.
    A scenario saved with another base / engine version is recalculated now AND flagged (its saved figures are shown next to the new ones).
    recalc_ok (a collection of recalc_key values, None = legacy behaviour): when given, a scenario saved with other versions is NOT computed until its key is in it —
    the row says needs_recalc and nothing is silently mixed. The stored scenario is never modified either way.
    `common` is not used by the saved-scenarios screen (each scenario keeps its own assumptions)."""
    if not 2 <= len(items) <= 3:
        raise ValueError("compare 2 or 3 scenarios")
    common = {k: v for k, v in (common or {}).items()} if common else {}
    pe = _price_problem(common.get("fuel_price")); he = _hours_problem(common.get("flown_hours"))
    if pe or he:
        return [], [e for e in (he, pe) if e]
    out = []
    for it in items:
        payload = it.get("payload") or {}
        scn = scenario_from_dict(payload.get("scenario"))
        sub = df[df["aircraft_id"] == scn.aircraft_id]
        label = str(it.get("name") or scn.aircraft_id); msn = (payload.get("msn") or "")
        vs = version_status(it); snap = payload.get("snapshot") or {}
        if not len(sub):
            out.append(dict(key=it.get("id"), label=label, aircraft_id=scn.aircraft_id, available=False, missing=["aircraft not in the database"], replaced={}, version=vs)); continue
        if recalc_ok is not None and vs["changed"] and recalc_key(it) not in set(recalc_ok):
            out.append(dict(key=it.get("id"), label=label, aircraft_id=scn.aircraft_id, model=str(sub.iloc[0]["model"]), available=False, needs_recalc=True, msn=msn,
                            missing=["recalculation for this comparison (saved with another base or calculation version)"], replaced={}, version=vs,
                            saved_budget_usd=snap.get("budget_usd"), recalc_key=recalc_key(it), errors=[])); continue
        use, replaced = harmonise(scn, common) if (common.get("flown_hours") is not None or common.get("fuel_price") is not None) else (scn, {})
        res = E.compute(sub.iloc[0], use)
        r = _result_row(it.get("id"), label, use, res, dict(msn=msn, replaced=replaced, version=vs, saved_budget_usd=snap.get("budget_usd"), recalc_key=recalc_key(it),
                                                        missing=[] if res["available"] else ["incomplete data for this scenario"], errors=[]))
        out.append(r)
    return out, []


# ─────────────────────────────── saved-scenario comparison: ONE table / ONE chart dataset for screen, CSV and PDF ───────────────────────────────
CMP_SAVED_INTRO = "Each aircraft keeps its own saved operating and charter assumptions."
CMP_SAVED_NOTE = "Each scenario uses its own assumptions. Differences in utilisation, charter rates and cost scope affect the results."
CMP_COLORS = ("#C9A84C", "#4A90D9", "#A78BFA")          # one stable colour per scenario position (A, B, C)
CMP_LETTERS = ("A", "B", "C")
NA = "n/a"


def cmp_names(rows) -> list[str]:
    """Column / legend names: 'A · scenario name' — unique even when two scenarios share a name."""
    return [f"{CMP_LETTERS[i]} · {r.get('label') or r.get('model') or r.get('aircraft_id')}" for i, r in enumerate(rows)]


def _hours(v):
    return NA if v is None else f"{v:,.0f} h"


def _of_text(o, disp):
    """Owner-flight indicator exactly as the engine produced it (E.owner_flight_indicator): remaining per owner hour, or the covered / surplus / no-hours cases."""
    if o is None:
        return NA, NA, None
    if o["status"] == "remaining":
        return (disp.money(o["per_hour_usd"]) + " / h") if o["per_hour_usd"] is not None else "n/a — enter owner flight hours", disp.money(o["remaining_usd"]), None
    return "Operating costs fully covered", disp.money(0.0), (disp.money(o["surplus_usd"]) if o["status"] == "surplus" else None)


def comparison_table(rows, disp) -> list[dict]:
    """Rows of the comparison as {section, label, values[]} (one value per scenario, already formatted in the display currency). Nothing is computed here:
    every figure is a field of the engine row. A missing figure is 'n/a', never zero. The economic block is returned only when at least one scenario has ownership data."""
    D = disp.money
    out = []

    def add(sec, label, fn):
        vals = []
        for r in rows:
            try:
                vals.append(fn(r))
            except Exception:
                vals.append(NA)
        out.append(dict(section=sec, label=label, values=vals))

    def ok(r): return bool(r.get("available"))
    def charter(r, key, fmt=D): return fmt(r[key]) if (ok(r) and r.get("charter_available") and r.get(key) is not None) else NA

    A = "Main assumptions"
    add(A, "Model", lambda r: r.get("model") or NA)
    add(A, "Scenario", lambda r: (r.get("label") or NA) + (f" · {r['msn']}" if r.get("msn") else ""))
    add(A, "Total flown hours", lambda r: _hours(r.get("hours")) if ok(r) else NA)
    add(A, "Billed charter hours", lambda r: _hours(r.get("billed_hours")) if ok(r) else NA)
    add(A, "Positioning hours", lambda r: _hours(r.get("positioning_hours")) if ok(r) else NA)
    add(A, "Owner flight hours", lambda r: _hours(r.get("owner_hours")) if ok(r) else NA)
    add(A, "Charter rate / billed hour", lambda r: (D(r["rate_usd"]) + (" gross" if r.get("rate_basis") == "gross" else " net")) if (ok(r) and r.get("charter_available")) else NA)
    add(A, "Commission", lambda r: ((f"{r['commission_pct']:g}%" if r.get("rate_basis") == "gross" else "n/a (rate already net)") if (ok(r) and r.get("charter_available")) else NA))
    add(A, "Fuel price / litre", lambda r: D(r["fuel_price_usd_l"], 3) if (ok(r) and r.get("fuel_price_usd_l") is not None) else NA)
    add(A, "Management fee", lambda r: (D(r["management_included_usd"]) + " included") if r.get("management_included_usd") is not None else (r.get("management_text") or NA) if ok(r) else NA)
    add(A, "Cost edits and additions", lambda r: (", ".join(r.get("edits") or []) or "none") if ok(r) else NA)

    R = "Results"
    add(R, "Fixed costs / year", lambda r: D(r["fixed_annual_usd"]) if ok(r) and r.get("fixed_annual_usd") is not None else NA)
    add(R, "Variable costs / year", lambda r: D(r["variable_annual_usd"]) if ok(r) and r.get("variable_annual_usd") is not None else NA)
    add(R, "Annual operating budget", lambda r: D(r["budget_usd"]) if ok(r) and r.get("budget_usd") is not None else NA)
    add(R, "Cost / total flown hour", lambda r: D(r["cost_per_h_usd"]) if ok(r) and r.get("cost_per_h_usd") is not None else NA)
    add(R, "Charter revenue before commission", lambda r: charter(r, "revenue_usd"))
    add(R, "Commission", lambda r: charter(r, "commission_usd"))
    add(R, "Net charter revenue (after commission)", lambda r: charter(r, "net_revenue_usd"))
    add(R, "Other fees and supplements, net", lambda r: charter(r, "other_annual_net_usd"))
    add(R, "Estimated operating result", lambda r: charter(r, "operating_result_usd"))
    ofs = [(_of_text(r.get("owner_flight"), disp) if (ok(r) and r.get("charter_available")) else (NA, NA, None)) for r in rows]
    add(R, "Annual amount remaining to the owner", lambda r: ofs[rows.index(r)][1])
    if any(o[2] for o in ofs):
        add(R, "Estimated operating surplus", lambda r: ofs[rows.index(r)][2] or "—")
    add(R, "Remaining cost per owner flight hour", lambda r: ofs[rows.index(r)][0])

    if any(r.get("depreciation_usd") is not None or r.get("interest_usd") is not None for r in rows if ok(r)):
        E_ = "Ownership costs and economic result (shown separately)"
        add(E_, "Economic depreciation / year", lambda r: D(r["depreciation_usd"]) if ok(r) and r.get("depreciation_usd") is not None else NA)
        add(E_, "Loan interest / year", lambda r: D(r["interest_usd"]) if ok(r) and r.get("interest_usd") is not None else NA)
        add(E_, "Annual economic cost (budget + both)", lambda r: D(r["economic_cost_usd"]) if ok(r) and r.get("economic_cost_usd") is not None else NA)
        add(E_, "Economic result", lambda r: D(r["economic_result_usd"]) if ok(r) and r.get("economic_result_usd") is not None else NA)
    return out


def comparison_chart_data(rows, disp) -> dict:
    """The four comparison charts' numbers (display currency), shared by the screen and the PDF. None = n/a: nothing is drawn as zero."""
    c = disp.conv
    names = cmp_names(rows)
    avail = [bool(r.get("available")) for r in rows]
    split = [(r.get("cost_split") if a else None) for r, a in zip(rows, avail)]
    stack = dict(names=names, colors=list(CMP_COLORS[:len(rows)]), series=[
        ("Fixed costs", "#1A3A6E", [c(x["fixed"]) if x else None for x in split]),
        ("Fuel", "#F97316", [c(x["fuel"]) if x else None for x in split]),
        ("Maintenance", "#4A90D9", [c(x["maintenance"]) if x else None for x in split]),
        ("Other variable", "#8496B0", [c(x["other_variable"]) if x else None for x in split])],
        totals=[c(r["budget_usd"]) if a and r.get("budget_usd") is not None else None for r, a in zip(rows, avail)])
    ch = [a and bool(r.get("charter_available")) for r, a in zip(rows, avail)]
    rev = dict(names=names, series=[
        ("Net charter revenue", "#4ADE80", [c(r["net_revenue_usd"]) if k else None for r, k in zip(rows, ch)]),
        ("Annual operating costs", "#F97316", stack["totals"])])
    res = dict(names=names, colors=list(CMP_COLORS[:len(rows)]), values=[c(r["operating_result_usd"]) if k else None for r, k in zip(rows, ch)])
    per, labels = [], []
    for r, k in zip(rows, ch):
        if not k or r.get("owner_flight") is None:
            per.append(None); labels.append(NA); continue
        o = r["owner_flight"]
        if o["status"] == "remaining":
            per.append(c(o["per_hour_usd"]) if o["per_hour_usd"] is not None else None)
            labels.append((disp.money(o["per_hour_usd"]) + " / h") if o["per_hour_usd"] is not None else "n/a — no owner hours")
        else:
            per.append(0.0); labels.append("Fully covered" + (f" · surplus {disp.money(o['surplus_usd'])} / yr" if o["status"] == "surplus" else ""))
    owner = dict(names=names, colors=list(CMP_COLORS[:len(rows)]), values=per, labels=labels)
    return dict(currency=disp.ccy, symbol=disp.sym, stack=stack, revenue=rev, result=res, owner=owner)


def comparison_signature(rows, disp) -> str:
    """Changes when the selection, the assumptions, the currency / rate or any result of the comparison changes — used to invalidate a generated PDF."""
    import hashlib
    keyed = [(r.get("key"), r.get("config_hash"), r.get("available"), r.get("budget_usd"), r.get("operating_result_usd"), r.get("hours"), r.get("rate_usd"),
              r.get("billed_hours"), r.get("owner_hours")) for r in rows]
    fx = disp.fx
    return hashlib.sha256(repr((keyed, comparison_table(rows, disp), disp.ccy, getattr(fx, "usd_to_eur", None), getattr(fx, "rate_date", None), E.DB_VERSION, E.ENGINE_VERSION)).encode()).hexdigest()[:10]


def comparison_csv(rows, disp, meta) -> bytes:
    import csv as _csv, io as _io
    b = _io.StringIO(); w = _csv.writer(b)
    for k, v in meta: w.writerow([k, v])
    w.writerow([])
    w.writerow(["Section", "Line"] + cmp_names(rows))
    for t in comparison_table(rows, disp): w.writerow([t["section"], t["label"]] + t["values"])
    return b.getvalue().encode("utf-8")


# ─────────────────────────────── product events ───────────────────────────────
EVENTS = ("visit", "first_simulation", "signup", "subscription_activated", "scenario_saved", "report_generated",
          "study_request_received", "subscription_renewed", "subscription_cancelled")
# The ONLY properties an event may carry. No e-mail, name, free text, MSN or folder / scenario content can pass.
ALLOWED_PROPS = {"plan": ("free", "essentiel", "pro"), "journey": ("A", "B", "C"), "source": ("app", "stripe_check")}


def clean_event(event: str, props: dict | None = None):
    """Whitelist: unknown events are refused, unknown properties and values dropped."""
    if event not in EVENTS:
        return None
    clean = {}
    for k, v in (props or {}).items():
        if k in ALLOWED_PROPS and v in ALLOWED_PROPS[k]:
            clean[k] = v
    return dict(event=event, props=clean)


def anon_session_id(raw: str) -> str:
    """Random per-browser-session id, hashed: it identifies a visit, never a person."""
    return hashlib.sha256(("menkor-evt:" + raw).encode()).hexdigest()[:16]


def track(rest, state: dict, event: str, props: dict | None = None, once_key: str | None = None) -> bool:
    """Record one event. `state` is the Streamlit session state (a dict): `once_key` makes it idempotent across Streamlit reruns.
    Returns True only if the event was really stored; a failure is silent for the user and never recorded as done."""
    ev = clean_event(event, props)
    if ev is None or rest is None:
        return False
    done = state.setdefault("_events_done", set())
    key = once_key or event
    if key in done:
        return False
    sid = state.setdefault("_anon_sid", uuid.uuid4().hex)
    try:
        st_, _ = rest("POST", "events", json=dict(id=str(uuid.uuid4()), session_id=anon_session_id(sid), event=ev["event"], props=ev["props"], created_at=_now()))
    except Exception:
        return False
    if _ok(st_):
        done.add(key)
        return True
    return False
