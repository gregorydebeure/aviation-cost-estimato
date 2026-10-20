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
    return None


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
    row.update(extra or {})
    return row


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


def compare_saved(df, items: list, common: dict | None = None):
    """Compare 2–3 SAVED scenarios with the same engine as Cost Master. Each keeps its own aircraft and assumptions (default).
    common (optional, explicit): flown_hours / fuel_price / fuel_ccy — applied to a COPY, the saved scenarios are never modified; what was replaced is listed.
    A scenario saved with another base / engine version is recalculated now AND flagged (its saved figures are shown next to the new ones)."""
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
        use, replaced = harmonise(scn, common) if (common.get("flown_hours") is not None or common.get("fuel_price") is not None) else (scn, {})
        res = E.compute(sub.iloc[0], use)
        r = _result_row(it.get("id"), label, use, res, dict(msn=msn, replaced=replaced, version=vs, saved_budget_usd=snap.get("budget_usd"),
                                                        missing=[] if res["available"] else ["incomplete data for this scenario"], errors=[]))
        out.append(r)
    return out, []


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
