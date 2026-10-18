"""
menkor_engine.py — single calculation engine for Aviation Cost Estimator (Menkor Aviation GBL).

No Streamlit dependency: Dashboard, Profitability, Sensitivity, Cost Master, Quotation basis
and PDF all call compute() with the same Scenario and therefore show the same numbers.

Rules enforced here (see CHANGES_v15.md):
  * A missing source value is None, never 0.  A calculation that needs it is flagged unavailable.
  * Annual fixed totals already include crew, crew training, hangar, insurance, aircraft misc.
    They are NEVER added to crew expense again.  A user edit REPLACES a component (delta logic).
  * Annual variable totals already include fuel, airframe, engine/APU, crew misc variable
    (crew travel + catering + airport fees + other).  Sub-totals and components are not summed twice.
  * Source currency (USD, from the report "$" symbol) is separate from the display currency.
    EUR display needs an explicit, dated exchange rate entered by the user.
  * Fuel is handled in litres (1 US gal = 3.785411784 L).  Burn is an economic average, not flight planning.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

import pandas as pd

ENGINE_VERSION = "2.1"
DB_VERSION = "v16-167-models"
_HERE = Path(__file__).resolve().parent
# Data files live in data/. If they were uploaded flat next to app.py (GitHub web upload can flatten folders), fall back to that folder.
DATA_DIR = _HERE / "data" if (_HERE / "data" / "menkor_base_v16.csv").exists() else (_HERE if (_HERE / "menkor_base_v16.csv").exists() else _HERE / "data")

USG_TO_L = 3.785411784          # documented in the base (README_CLAUDE.md)
HOURS_IN_YEAR = 8760.0

LEGACY_STATUS = "legacy_not_reconstructed"
WEB_PREFIX = "web_estimate"

# Web estimates (Guardian Jet economics + ACC public technical summary): scope differs from ACC PDF reports.
WEB_VAR_COMPONENTS = {
    "maintenance_total": ("hourly_maintenance_total_usd", None,
                          "Maintenance (5-yr average + engine program; airframe/engine split unknown)"),
}

# component key -> (source field, label)
FIXED_COMPONENTS = {
    "crew_expense":  ("annual_crew_expense_fixed_usd",  "Crew expense"),
    "crew_training": ("annual_crew_training_fixed_usd", "Crew training"),
    "hangar":        ("annual_hangar_fixed_usd",        "Hangar"),
    "insurance":     ("annual_insurance_fixed_usd",     "Insurance"),
    "aircraft_misc": ("annual_aircraft_misc_fixed_usd", "Aircraft miscellaneous"),
}
# non-fuel variable components, editable per flight hour: key -> (hourly field, annual field or None, label)
VAR_COMPONENTS = {
    "airframe_maint":   ("hourly_airframe_maintenance_usd",  "annual_airframe_maintenance_usd",  "Airframe maintenance"),
    "engine_apu_maint": ("hourly_engine_apu_maintenance_usd", "annual_engine_apu_maintenance_usd", "Engine / APU maintenance"),
    "crew_travel":      ("hourly_crew_travel_usd",   None, "Crew travel (variable)"),
    "catering":         ("hourly_catering_usd",      None, "Catering"),
    "airport_fees":     ("hourly_airport_fees_usd",  None, "Airport fees"),
    "other":            ("hourly_other_usd",         None, "Other variable"),
}

STATUS_TEXT = {
    "pdf_extracted_review_required": "Menkor reference database — extracted record, review required (see checks).",
    "source_values_review_required": "Some printed values are invalid placeholders (left empty) — review required.",
    "model_name_and_source_values_review_required": "Model name differs between file name and report title, and some printed values are invalid — review required.",
    "model_name_review_required": "Model name differs between file name and report title — review required.",
    "web_estimate_partial_breakdown_review_required": "Menkor reference database — partial web estimate (Guardian Jet economics + public technical summary); cost breakdown differs from the full Menkor reference records.",
    "source_conflict_review_required": "Two source reports disagree for this model — primary source used, conflict kept (see conflicts table).",
    LEGACY_STATUS: "Historical sheet from the old Menkor base — no PDF report yet, detailed fields to be reconstructed.",
}


# ═════════════════════════════════════════════════════════════════════════════
# Data access
# ═════════════════════════════════════════════════════════════════════════════
def _read(name: str, **kw) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, encoding="utf-8-sig", **kw)


def load_base() -> pd.DataFrame:
    """165 aircraft (144 PDF-documented + 21 historical). aircraft_id is the stable key."""
    df = _read("menkor_base_v16.csv", dtype={"aircraft_id": "string", "report_contact_phone": "string"})
    df["aircraft_id"] = df["aircraft_id"].astype(str)
    df["has_detail"] = df["record_status"] != LEGACY_STATUS
    df["source_kind"] = df["record_status"].map(
        lambda x: "historical" if x == LEGACY_STATUS else ("web_estimate" if str(x).startswith(WEB_PREFIX) else "pdf_acc"))
    # Compatibility columns used by the Streamlit UI
    df["Modele"] = df["model"]
    df["Categorie"] = df["manufacturer"].fillna("Historical sheet (manufacturer n/a)")
    return df.sort_values(["has_detail", "model"], ascending=[False, True], kind="stable").reset_index(drop=True)


def load_checks() -> pd.DataFrame:
    return _read("controles.csv", dtype={"aircraft_id": "string"})


def load_conflicts() -> pd.DataFrame:
    return _read("conflits_G450.csv", dtype=str)


def load_conversions() -> pd.DataFrame:
    return _read("conversions_unites.csv", dtype=str)


def load_inventory() -> pd.DataFrame:
    return _read("inventaire_sources.csv", dtype=str)


def load_aliases() -> pd.DataFrame:
    return _read("aliases_modeles.csv", dtype=str)


def load_web_supplement() -> pd.DataFrame:
    return _read("complements_web_Global.csv", dtype=str)


def resolve_alias(query, base: pd.DataFrame, aliases: pd.DataFrame):
    """Resolve an aircraft_id, model name or historical alias (e.g. 'Global 7000') to ONE aircraft_id, or None.
    An alias never creates an aircraft: it points to an existing one."""
    q = str(query or "").strip().lower()
    if not q:
        return None
    ids = set(base["aircraft_id"].str.lower())
    if q in ids:
        return base.loc[base["aircraft_id"].str.lower() == q, "aircraft_id"].iloc[0]
    m = base[base["model"].str.lower() == q]
    if len(m):
        return m["aircraft_id"].iloc[0]
    a = aliases[aliases["alias"].str.lower() == q]
    if len(a) and a["aircraft_id"].iloc[0] in set(base["aircraft_id"]):
        return a["aircraft_id"].iloc[0]
    # manufacturer prefix omitted ("global 7500"): accepted only if it designates exactly one model
    m = base[base["model"].str.lower().str.endswith(" " + q)]
    if len(m) == 1:
        return m["aircraft_id"].iloc[0]
    return None


def load_provenance() -> pd.DataFrame:
    return _read("provenance.csv", dtype=str)


def public_text(t):
    """Free text from the data files, made safe for display: third-party calculator name replaced by Menkor."""
    if t is None or (isinstance(t, float) and t != t):
        return t
    import re as _r
    return _r.sub(r"\bACC\b( public( web)?)?", lambda m: "Menkor reference database (public)" if m.group(1) else "Menkor", str(t))


def public_source(s):
    """User-facing source label: the third-party calculator site is never shown; it is presented as the Menkor reference database."""
    if s is None or (isinstance(s, float) and s != s):
        return s
    t = str(s)
    return "Menkor reference database (public technical summary)" if "aircraftcostcalculator" in t.lower() else t


def num(row, f):
    """Numeric value or None. NaN / empty is None — NEVER silently zero."""
    try:
        v = row.get(f, None)
    except AttributeError:
        v = None
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


def source_kind(row) -> str:
    st = str(row.get("record_status"))
    return "historical" if st == LEGACY_STATUS else ("web_estimate" if st.startswith(WEB_PREFIX) else "pdf_acc")


def var_components_for(row) -> dict:
    """Editable non-fuel variable components whose scope is KNOWN for this source.
    Reference record: airframe, engine/APU, crew travel, catering, airport fees, other.
    Web estimate: only the combined maintenance line (airframe/engine split unknown) — nothing is invented."""
    return dict(WEB_VAR_COMPONENTS) if source_kind(row) == "web_estimate" else dict(VAR_COMPONENTS)


def fixed_label(row, key) -> str:
    lab = FIXED_COMPONENTS[key][1]
    if source_kind(row) == "web_estimate":
        if key == "crew_expense":
            return "Crew (aggregate — training not isolated)"
        if key == "insurance":
            return "Insurance (hull + liability)"
    return lab


def _web_source(row):
    """(url, access_date) of the web supplement for this aircraft, or (None, None)."""
    try:
        w = _web_cached()
        w = w[w["aircraft_id"] == row["aircraft_id"]]
        u = w[w["field"] == "source_url"]
        d = w[w["field"] == "source_access_date"]
        return (u["value"].iloc[0] if len(u) else None, d["value"].iloc[0] if len(d) else None)
    except Exception:
        return (None, None)


_WEB_CACHE = {}


def _web_cached():
    if "w" not in _WEB_CACHE:
        _WEB_CACHE["w"] = load_web_supplement()
    return _WEB_CACHE["w"]


# ═════════════════════════════════════════════════════════════════════════════
# Currency / display
# ═════════════════════════════════════════════════════════════════════════════
def _valid_date(s) -> bool:
    if not s or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s).strip()):
        return False
    try:
        date.fromisoformat(str(s).strip())
        return True
    except ValueError:
        return False


@dataclass
class Fx:
    display_ccy: str = "USD"          # 'USD' or 'EUR'
    usd_to_eur: float | None = None   # EUR obtained for 1 USD (explicit, user-entered)
    rate_date: str | None = None      # ISO date YYYY-MM-DD of that rate (user-entered)
    rate_source: str = ""             # free text: where the rate comes from

    def is_valid(self) -> bool:
        return bool(self.usd_to_eur and self.usd_to_eur > 0 and _valid_date(self.rate_date))


class Display:
    """Money formatting. Never labels a USD amount as EUR without a valid dated rate."""

    def __init__(self, fx: Fx):
        self.fx = fx
        self.requested = fx.display_ccy
        self.eur_blocked = fx.display_ccy == "EUR" and not fx.is_valid()
        self.ccy = "EUR" if (fx.display_ccy == "EUR" and fx.is_valid()) else "USD"
        self.factor = fx.usd_to_eur if self.ccy == "EUR" else 1.0
        self.sym = "€" if self.ccy == "EUR" else "$"

    def conv(self, usd):
        return None if usd is None else usd * self.factor

    def to_usd(self, amount):
        return None if amount is None else amount / self.factor

    def money(self, usd, d=0) -> str:
        if usd is None:
            return "n/a"
        return f"{self.sym} {usd * self.factor:,.{d}f}"

    def note(self) -> str:
        if self.ccy == "EUR":
            return (f"Source currency USD · displayed in EUR at 1 USD = {self.fx.usd_to_eur:.4f} EUR "
                    f"(rate dated {self.fx.rate_date}{', ' + self.fx.rate_source if self.fx.rate_source else ''})")
        if self.eur_blocked:
            return "EUR display requested but no valid dated exchange rate — amounts shown in USD (source currency)."
        return "Source currency USD (from the report '$' symbol) · no conversion applied"


# ═════════════════════════════════════════════════════════════════════════════
# Scenario
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class FuelConfig:
    price_source: str = "report"        # 'report' (reference_fuel_price_usd_per_l) | 'manual'
    burn_method: str = "published"      # 'published' | 'derived' | 'custom'
    custom_burn_l_h: float | None = None
    # manual local price (all optional metadata, recorded in results/exports)
    price: float | None = None
    unit: str = "L"                     # 'L' | 'USG'
    currency: str = "USD"               # 'USD' | 'EUR'
    taxes_pct: float = 0.0              # taxes applied on the price
    fees_per_uplift: float = 0.0        # fixed fees per uplift (in `currency`) — not part of the hourly average
    airport_icao: str = ""
    airport_iata: str = ""
    supplier: str = ""
    validity_date: str = ""             # ISO date entered by the user


# ═════════════════════════════════════════════════════════════════════════════
# Menkor base update (inflation) — Menkor decision, applied BEFORE any user edit
# ═════════════════════════════════════════════════════════════════════════════
ACTUALISE_DEFAULT = True          # tests of the raw base switch this off; the product default is ON
INFLATION_PCT_DEFAULT = 15.0      # cumulative uplift for 3-4 years of cost drift (Menkor assumption, to be reviewed)
RECURRENT_TRAINING_PER_PILOT_USD = {"bombardier_global": 60000.0}   # Menkor figure: Global recurrent training per pilot, USD/year (current price, NOT inflated again)
PILOTS_PER_AIRCRAFT = 2
# category -> list of (hourly field, annual field) ; hourly-only lines use hourly x reference hours
ACTUALISED = {
    "Maintenance & maintenance programs": dict(kind="var", pairs=[("hourly_airframe_maintenance_usd", "annual_airframe_maintenance_usd"),
                                                                    ("hourly_engine_apu_maintenance_usd", "annual_engine_apu_maintenance_usd")],
                                               scale_only=["hourly_maintenance_total_usd"], web_pairs=[("hourly_maintenance_total_usd", None)]),
    "Handling & en-route / airport fees": dict(kind="var", pairs=[("hourly_airport_fees_usd", None)], scale_only=[]),
    "Crew training": dict(kind="fixed", pairs=[(None, "annual_crew_training_fixed_usd")], scale_only=[]),
    "Hangar": dict(kind="fixed", pairs=[(None, "annual_hangar_fixed_usd")], scale_only=[]),
}


def recurrent_training_override(aircraft_id: str):
    """Annual crew training for the models with a Menkor recurrent-training price (per pilot x pilots), else None."""
    for prefix, per_pilot in RECURRENT_TRAINING_PER_PILOT_USD.items():
        if str(aircraft_id).startswith(prefix):
            return per_pilot
    return None


def adjust_row(row, scn):
    """Return (row2, items). Scales the listed ACTUALISED source values by the scenario's inflation, then moves the published
    totals by exactly the same amounts, so components still add up to the totals (no double counting, rounding rows unchanged).
    Fuel, insurance, crew salaries/expenses, catering, crew travel and misc are NOT touched. Missing values stay missing."""
    if not getattr(scn, "actualise", False) or str(row.get("record_status")) == LEGACY_STATUS:
        return row, []
    pct = float(scn.inflation_pct) / 100.0
    ref_h = num(row, "reference_annual_hours")
    if not ref_h:
        return row, []
    r = row.copy()
    web = source_kind(row) == "web_estimate"
    d_fixed = d_var = 0.0
    items = []

    def scaled(field):
        v = num(r, field)
        if v is None:
            return None
        r[field] = v * (1.0 + pct)
        return v

    for cat, spec in ACTUALISED.items():
        before = after = 0.0
        found = False
        pairs = spec["pairs"] if not web else spec.get("web_pairs", spec["pairs"])
        for hf, af in pairs:
            ann = num(row, af) if af else None
            hr = num(row, hf) if hf else None
            base_annual = ann if ann is not None else (hr * ref_h if hr is not None else None)
            if base_annual is None:
                continue
            found = True
            if hf: scaled(hf)
            if af: scaled(af)
            before += base_annual; after += base_annual * (1 + pct)
            delta = base_annual * pct
            if spec["kind"] == "fixed": d_fixed += delta
            else: d_var += delta
        for hf in spec.get("scale_only", []):
            if not web: scaled(hf)
        if cat == "Crew training":
            per_pilot = recurrent_training_override(row["aircraft_id"])
            cur = num(row, "annual_crew_training_fixed_usd")
            if per_pilot is not None and cur is not None:       # replaces the (inflated) base value; not inflated again
                new = per_pilot * PILOTS_PER_AIRCRAFT
                d_fixed += new - cur * (1 + pct)
                r["annual_crew_training_fixed_usd"] = new
                items.append(dict(item=cat, before=cur, after=new, pct=None,
                                  note=f"Menkor recurrent training: {PILOTS_PER_AIRCRAFT} pilots x {per_pilot:,.0f} USD (current price, not inflated)"))
                continue
        if found:
            items.append(dict(item=cat, before=before, after=after, pct=pct * 100, note=""))
        else:
            items.append(dict(item=cat, before=None, after=None, pct=None,
                              note="not available in this source — not adjusted, not replaced by zero"))
    tot_delta = d_fixed + d_var
    for f, dv in (("annual_fixed_cost_usd", d_fixed), ("annual_variable_cost_usd", d_var), ("annual_budget_usd", tot_delta),
                  ("fixed_excluding_crew_expense_usd", d_fixed)):
        v = num(r, f)
        if v is not None: r[f] = v + dv
    for f, dv in (("total_cost_per_h_from_annual_usd", tot_delta), ("variable_cost_per_h_from_annual_usd", d_var),
                  ("nonfuel_variable_cost_per_h_usd", d_var), ("variable_cost_per_h_displayed_sum_usd", d_var)):
        v = num(r, f)
        if v is not None: r[f] = v + dv / ref_h
    return r, items


@dataclass
class Scenario:
    aircraft_id: str
    mode: str = "simulation"            # 'reference' | 'simulation'
    billed_hours: float = 0.0           # charter hours invoiced to the client
    positioning_hours: float = 0.0      # empty / positioning legs (flown, not billed)
    other_hours: float = 0.0            # owner / private / other non-billed hours
    charter_rate: float | None = None   # per billed hour
    charter_rate_ccy: str = "USD"
    commission_pct: float = 0.0         # broker commission on charter revenue
    other_commercial_fees: float = 0.0  # annual, USD, NOT already included in the report
    fuel: FuelConfig = field(default_factory=FuelConfig)
    fixed_overrides: dict = field(default_factory=dict)   # key -> new annual amount (USD) REPLACING the component
    var_overrides_h: dict = field(default_factory=dict)   # key -> new hourly amount (USD) REPLACING the component
    extra_fixed: float = 0.0            # annual USD cost added by the user (not in report)
    extra_var_h: float = 0.0            # USD per flown hour added by the user (not in report)
    fx: Fx = field(default_factory=Fx)
    actualise: bool = field(default_factory=lambda: ACTUALISE_DEFAULT)   # Menkor base update (inflation) on/off
    inflation_pct: float = INFLATION_PCT_DEFAULT

    def canonical(self) -> dict:
        return asdict(self)

    def config_hash(self) -> str:
        payload = json.dumps({"scenario": self.canonical(), "db": DB_VERSION, "engine": ENGINE_VERSION},
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def flown_hours(self) -> float:
        return float(self.billed_hours) + float(self.positioning_hours) + float(self.other_hours)


# ═════════════════════════════════════════════════════════════════════════════
# Fuel helpers
# ═════════════════════════════════════════════════════════════════════════════
def manual_price_usd_per_l(fc: FuelConfig, fx: Fx):
    """Return (usd_per_litre or None, error or None). Taxes included, per-uplift fees excluded."""
    if fc.price is None or fc.price <= 0:
        return None, "Manual fuel price not entered."
    p = fc.price * (1.0 + (fc.taxes_pct or 0.0) / 100.0)
    if fc.unit == "USG":
        p = p / USG_TO_L
    elif fc.unit != "L":
        return None, f"Unknown fuel unit '{fc.unit}'."
    if fc.currency == "EUR":
        if not fx.is_valid():
            return None, "Manual fuel price is in EUR: enter a dated EUR/USD rate to convert it."
        p = p / fx.usd_to_eur
    elif fc.currency != "USD":
        return None, f"Unknown currency '{fc.currency}'."
    return p, None


def stopover_purchase(purchased_qty, unit, price, currency, taxes_pct, fees, consumed_l, fx: Fx):
    """Fuel CONSUMED on the leg vs fuel PURCHASED at the stopover (they differ: reserves, tankering, partial uplift)."""
    f = USG_TO_L if unit == "USG" else 1.0
    purchased_l = purchased_qty * f
    gross_per_unit = price * (1 + (taxes_pct or 0) / 100.0)
    cost_ccy = purchased_qty * gross_per_unit + (fees or 0.0)
    consumed_cost_ccy = (consumed_l / f) * gross_per_unit
    out = dict(purchased_l=purchased_l, consumed_l=consumed_l, balance_l=purchased_l - consumed_l,
               purchase_cost=cost_ccy, consumed_cost=consumed_cost_ccy, currency=currency, usd=None)
    if currency == "USD":
        out["usd"] = cost_ccy
    elif fx.is_valid():
        out["usd"] = cost_ccy / fx.usd_to_eur
    return out


# ═════════════════════════════════════════════════════════════════════════════
# Compute
# ═════════════════════════════════════════════════════════════════════════════
def _flag(flags, level, code, text):
    flags.append(dict(level=level, code=code, text=text))


def _empty_result(row, scn):
    return dict(
        engine_version=ENGINE_VERSION, db_version=DB_VERSION,
        aircraft_id=str(row["aircraft_id"]), model=str(row["model"]), manufacturer=row.get("manufacturer"),
        source_file=row.get("source_file"), record_status=row.get("record_status"),
        mode=scn.mode, available=False, historical=False, flags=[], config_hash=scn.config_hash(),
        source_kind=source_kind(row),
        source_currency="USD", scenario=scn.canonical(),
        hours=dict(billed=scn.billed_hours, positioning=scn.positioning_hours, other=scn.other_hours,
                   flown=scn.flown_hours, reference=None),
        fuel={}, fixed={}, variable={}, components=[], budget_usd=None, cost_per_h_usd=None,
        published={}, reconciliation=None, profit=None, rate_usd=None, actualisation=dict(applied=False, inflation_pct=0.0, items=[]))


def compute(row, scn: Scenario) -> dict:
    """The only place where costs and results are calculated."""
    res = _empty_result(row, scn)
    fl = res["flags"]
    if str(row.get("record_status")) == LEGACY_STATUS:
        if getattr(scn, "actualise", False):
            _flag(fl, "info", "actualise_na", "Menkor base update not applied: historical sheet without the cost breakdown needed (totals only).")
        return _compute_legacy(row, scn, res)
    row, adj_items = adjust_row(row, scn)
    res["actualisation"] = dict(applied=bool(adj_items), inflation_pct=scn.inflation_pct if adj_items else 0.0, items=adj_items)

    ref_h = num(row, "reference_annual_hours")
    fixed_src = num(row, "annual_fixed_cost_usd")
    var_src = num(row, "annual_variable_cost_usd")
    fuel_cost_src = num(row, "annual_fuel_cost_usd")
    budget_src = num(row, "annual_budget_usd")
    res["hours"]["reference"] = ref_h
    res["published"] = dict(
        annual_budget=budget_src, annual_fixed=fixed_src, annual_variable=var_src,
        annual_fuel_cost=fuel_cost_src, annual_fuel_volume_l=num(row, "annual_fuel_volume_l"),
        reference_hours=ref_h, reference_fuel_price_usd_per_l=num(row, "reference_fuel_price_usd_per_l"),
        fuel_burn_l_per_h=num(row, "fuel_burn_l_per_h"),
        fuel_burn_from_annual_l_per_h=num(row, "fuel_burn_from_annual_l_per_h"),
        total_cost_per_h=num(row, "total_cost_per_h_from_annual_usd"))

    kind = source_kind(row)
    if kind == "web_estimate":
        url, acc = _web_source(row)
        res["web_source"] = dict(url=url, access_date=acc)
        _flag(fl, "warn", "web_source",
              f"Source: Menkor reference database — partial web estimate (Guardian Jet economics + public technical summary), not a full reference record. "
              f"Page consulted {acc or 'n/a'} (consultation date, not a validity date). Scenario: {ref_h:g} h/year, fuel 7.54 USD per US gallon "
              f"(USD assumed from '$', US gallon assumed — to confirm). Fixed costs differ strongly from the full Menkor reference records: not equivalent, operator validation advised.")
    need = {"reference_annual_hours": ref_h, "annual_fixed_cost_usd": fixed_src,
            "annual_variable_cost_usd": var_src, "annual_fuel_cost_usd": fuel_cost_src}
    miss = [k for k, v in need.items() if v is None]
    if miss or not ref_h or ref_h <= 0:
        _flag(fl, "error", "missing_core",
              "Core source values missing or invalid (" + ", ".join(miss or ["reference_annual_hours"]) +
              ") — no calculation performed; nothing is replaced by zero.")
        return res

    # ── fixed components (source) ─────────────────────────────────────────────
    comp_src = {k: num(row, f) for k, (f, _) in FIXED_COMPONENTS.items()}
    # ── REFERENCE MODE: published totals with original assumptions ───────────
    if scn.mode == "reference":
        return _compute_reference(row, scn, res, ref_h, fixed_src, var_src, fuel_cost_src, budget_src, comp_src)

    # ── SIMULATION MODE ───────────────────────────────────────────────────────
    H = scn.flown_hours
    res["hours"]["flown"] = H
    if scn.billed_hours + scn.positioning_hours + scn.other_hours < 0 or min(
            scn.billed_hours, scn.positioning_hours, scn.other_hours) < 0:
        _flag(fl, "error", "neg_hours", "Hours cannot be negative.")
        return res

    # fuel burn (litres per hour)
    f_pub, f_der = num(row, "fuel_burn_l_per_h"), num(row, "fuel_burn_from_annual_l_per_h")
    method = scn.fuel.burn_method
    burn, burn_label = None, ""
    if method == "custom" and scn.fuel.custom_burn_l_h and scn.fuel.custom_burn_l_h > 0:
        burn, burn_label = scn.fuel.custom_burn_l_h, "User-defined average burn (L/h)"
    elif method == "derived" and f_der is not None:
        burn, burn_label = f_der, "Derived from annual fuel volume ÷ reference hours (fuel_burn_from_annual_l_per_h)"
    elif f_pub is not None and method in ("published", "custom", "derived"):
        burn, burn_label = f_pub, "Published hourly burn (fuel_burn_l_per_h)"
        if method != "published":
            _flag(fl, "warn", "burn_fallback", f"Requested burn method '{method}' unavailable — published burn used.")
    elif f_der is not None:
        burn, burn_label = f_der, "Derived from annual fuel volume ÷ reference hours (published burn missing)"
        _flag(fl, "warn", "burn_fallback", "Published burn missing — derived burn used.")
    if burn is not None and kind == "web_estimate" and burn_label.startswith("Published"):
        burn_label = "Web scenario burn (US gal/h converted to L/h, US gallon assumed; average economic assumption)"
    if burn is None:
        _flag(fl, "error", "no_burn", "No fuel burn available for this aircraft — fuel cannot be simulated (not set to zero).")
        return res

    # fuel price (USD per litre)
    ref_price = num(row, "reference_fuel_price_usd_per_l")
    price_usd_l, price_label = None, ""
    if scn.fuel.price_source == "manual":
        price_usd_l, err = manual_price_usd_per_l(scn.fuel, scn.fx)
        price_label = "Manual local price entered by the user (no live feed)"
        if err:
            _flag(fl, "error", "price_manual", err)
            return res
    else:
        price_usd_l = ref_price
        price_label = ("Web scenario price 7.54 USD per US gallon (Guardian Jet; US gallon assumed, to confirm) — not a current market price"
                       if kind == "web_estimate" else "Report reference price (reference_fuel_price_usd_per_l) — not a current market price")
        if price_usd_l is None:
            _flag(fl, "error", "no_ref_price", "Report fuel price missing — enter a manual fuel price.")
            return res

    fuel_h = burn * price_usd_l

    # non-fuel variable cost per hour from the source totals
    nonfuel_h = (var_src - fuel_cost_src) / ref_h
    # replace edited variable components (delta vs the printed hourly value)
    var_rows, var_delta = [], 0.0
    vcomps = var_components_for(row)
    for k, (hf, af, label) in vcomps.items():
        src_h = num(row, hf)
        new_h = scn.var_overrides_h.get(k)
        if new_h is not None and src_h is None:
            _flag(fl, "warn", "override_ignored", f"{label}: source hourly value missing — override ignored (no replacement possible).")
            new_h = None
        eff = src_h if new_h is None else new_h
        if new_h is not None:
            var_delta += new_h - src_h
        var_rows.append((k, label, src_h, eff, new_h is not None))
    nonfuel_h += var_delta + (scn.extra_var_h or 0.0)

    var_h = nonfuel_h + fuel_h
    var_annual = H * var_h

    # fixed costs retained
    fixed_delta = 0.0
    fx_rows = []
    for k, (f, _lab) in FIXED_COMPONENTS.items():
        label = fixed_label(row, k)
        src = comp_src[k]
        new = scn.fixed_overrides.get(k)
        if new is not None and src is None:
            _flag(fl, "warn", "override_ignored", f"{label}: source value missing — override ignored.")
            new = None
        if new is not None:
            fixed_delta += new - src
        fx_rows.append((k, label, src, src if new is None else new, new is not None))
    fixed_total = fixed_src + fixed_delta + (scn.extra_fixed or 0.0)

    budget = fixed_total + var_annual
    cost_h = (budget / H) if H > 0 else None
    if H <= 0:
        _flag(fl, "info", "zero_hours", "Annual flown hours are zero: cost per hour is not applicable. Fixed costs still apply.")

    res["fuel"] = dict(burn_l_h=burn, burn_method=method,
                       burn_label=burn_label, price_usd_l=price_usd_l, price_label=price_label,
                       price_source=scn.fuel.price_source, fuel_per_h_usd=fuel_h,
                       annual_litres=H * burn, annual_usg=H * burn / USG_TO_L, annual_cost_usd=H * fuel_h,
                       note="Average economic assumption (L/h × price) — not a flight-planning calculation.",
                       local=dict(airport_icao=scn.fuel.airport_icao, airport_iata=scn.fuel.airport_iata,
                                  supplier=scn.fuel.supplier, price=scn.fuel.price, unit=scn.fuel.unit,
                                  currency=scn.fuel.currency, taxes_pct=scn.fuel.taxes_pct,
                                  fees_per_uplift=scn.fuel.fees_per_uplift, validity_date=scn.fuel.validity_date)
                       if scn.fuel.price_source == "manual" else None)
    res["fixed"] = dict(source_total=fixed_src, override_delta=fixed_delta, extra=scn.extra_fixed or 0.0,
                        annual_total=fixed_total, includes="crew expense, crew training, hangar, insurance, aircraft misc")
    res["variable"] = dict(nonfuel_per_h=nonfuel_h, fuel_per_h=fuel_h, per_h=var_h, annual=var_annual,
                           source_nonfuel_per_h=(var_src - fuel_cost_src) / ref_h,
                           includes="fuel, airframe maintenance, engine/APU maintenance, crew misc (travel, catering, airport fees, other)")
    res["budget_usd"] = budget
    res["cost_per_h_usd"] = cost_h
    res["available"] = True

    # component table (no double counting: components are a BREAKDOWN of the totals above)
    comps = []
    for k, label, s, eff, ed in fx_rows:
        if eff is not None:
            comps.append(dict(category="Fixed", key=k, label=label, annual_usd=eff, hourly_usd=None,
                              edited=ed, source_value=s))
    sum_fx = sum(c["annual_usd"] for c in comps)
    if scn.extra_fixed:
        comps.append(dict(category="Fixed", key="extra_fixed", label="User-added fixed cost (not in report)",
                          annual_usd=scn.extra_fixed, hourly_usd=None, edited=True, source_value=None))
        sum_fx += scn.extra_fixed
    comps.append(dict(category="Fixed", key="rounding_fixed", label="Rounding vs printed fixed total",
                      annual_usd=fixed_total - sum_fx, hourly_usd=None, edited=False, source_value=None, rounding=True))
    comps.append(dict(category="Variable", key="fuel", label="Fuel", annual_usd=H * fuel_h, hourly_usd=fuel_h,
                      edited=scn.fuel.price_source == "manual" or method == "custom", source_value=None))
    # airframe / engine hourly from annual ÷ ref hours when not edited (more precise than rounded hourly)
    vs = 0.0
    for k, label, s, eff, ed in var_rows:
        if eff is None:
            continue
        hv = eff
        if not ed and vcomps[k][1]:
            a = num(row, vcomps[k][1])
            hv = a / ref_h if a is not None else eff
        comps.append(dict(category="Variable", key=k, label=label, annual_usd=H * hv, hourly_usd=hv,
                          edited=ed, source_value=s))
        vs += hv
    if scn.extra_var_h:
        comps.append(dict(category="Variable", key="extra_var", label="User-added variable cost (not in report)",
                          annual_usd=H * scn.extra_var_h, hourly_usd=scn.extra_var_h, edited=True, source_value=None))
        vs += scn.extra_var_h
    comps.append(dict(category="Variable", key="rounding_var", label="Rounding of printed hourly values",
                      annual_usd=H * (nonfuel_h - vs), hourly_usd=(nonfuel_h - vs), edited=False, source_value=None, rounding=True))
    for c in comps:
        c["share_pct"] = (c["annual_usd"] / budget * 100) if budget else None
    res["components"] = comps

    # reconciliation: simulation at the report's own conditions vs published budget (do not force equality)
    if ref_price is not None:
        sim_ref = fixed_src + ref_h * ((var_src - fuel_cost_src) / ref_h + burn * ref_price)
        if budget_src:
            res["reconciliation"] = dict(
                simulated_at_report_conditions=sim_ref, published_budget=budget_src,
                difference=sim_ref - budget_src, difference_pct=(sim_ref - budget_src) / budget_src * 100,
                note="Printed hourly burn and fuel price are rounded: their product may differ from the published annual fuel cost. Source data are not altered to force equality.")

    # profitability
    res["profit"] = _profit(scn, res, fixed_total, var_h, H)
    return res


def _compute_reference(row, scn, res, ref_h, fixed_src, var_src, fuel_cost_src, budget_src, comp_src):
    fl = res["flags"]
    res["hours"].update(billed=None, positioning=None, other=None, flown=ref_h)
    budget = budget_src if budget_src is not None else fixed_src + var_src
    if budget_src is None:
        _flag(fl, "warn", "no_budget", "Published annual budget missing — fixed + variable totals used.")
    elif abs(fixed_src + var_src - budget_src) > 1.0:
        _flag(fl, "warn", "budget_sum", f"Published fixed + variable differs from published budget by {fixed_src + var_src - budget_src:,.0f} USD (tolerance 1 USD).")
    res["fixed"] = dict(source_total=fixed_src, override_delta=0.0, extra=0.0, annual_total=fixed_src,
                        includes="crew expense, crew training, hangar, insurance, aircraft misc")
    res["variable"] = dict(nonfuel_per_h=(var_src - fuel_cost_src) / ref_h, fuel_per_h=fuel_cost_src / ref_h,
                           per_h=var_src / ref_h, annual=var_src,
                           source_nonfuel_per_h=(var_src - fuel_cost_src) / ref_h,
                           includes="fuel, airframe maintenance, engine/APU maintenance, crew misc (travel, catering, airport fees, other)")
    vol = num(row, "annual_fuel_volume_l")
    res["fuel"] = dict(burn_l_h=num(row, "fuel_burn_l_per_h"), burn_method="published",
                       burn_label=("Web scenario burn (US gal/h converted to L/h; average economic assumption)" if source_kind(row) == "web_estimate"
                                   else "Published hourly burn (report)"), price_usd_l=num(row, "reference_fuel_price_usd_per_l"),
                       price_label=("Web scenario price 7.54 USD per US gallon (US gallon assumed, to confirm)" if source_kind(row) == "web_estimate"
                                    else "Report reference price — not a current market price"), price_source="report",
                       fuel_per_h_usd=fuel_cost_src / ref_h, annual_litres=vol,
                       annual_usg=(vol / USG_TO_L if vol is not None else None), annual_cost_usd=fuel_cost_src,
                       note="Published annual fuel volume and cost of the report; average economic assumption, not flight planning.",
                       local=None)
    comps = []
    for k, (f, _lab) in FIXED_COMPONENTS.items():
        label = fixed_label(row, k)
        if comp_src[k] is not None:
            comps.append(dict(category="Fixed", key=k, label=label, annual_usd=comp_src[k], hourly_usd=None, edited=False, source_value=comp_src[k]))
    s_fx = sum(c["annual_usd"] for c in comps)
    comps.append(dict(category="Fixed", key="rounding_fixed", label="Rounding vs printed fixed total", annual_usd=fixed_src - s_fx, hourly_usd=None, edited=False, source_value=None, rounding=True))
    comps.append(dict(category="Variable", key="fuel", label="Fuel", annual_usd=fuel_cost_src, hourly_usd=fuel_cost_src / ref_h, edited=False, source_value=None))
    s_v = fuel_cost_src
    for k, (hf, af, label) in var_components_for(row).items():
        a = num(row, af) if af else None
        h = num(row, hf)
        if a is None and h is not None:
            a = h * ref_h
        if a is not None:
            comps.append(dict(category="Variable", key=k, label=label, annual_usd=a, hourly_usd=a / ref_h, edited=False, source_value=h))
            s_v += a
    comps.append(dict(category="Variable", key="rounding_var", label="Rounding of printed hourly values", annual_usd=var_src - s_v, hourly_usd=(var_src - s_v) / ref_h, edited=False, source_value=None, rounding=True))
    for c in comps:
        c["share_pct"] = c["annual_usd"] / budget * 100 if budget else None
    res["components"] = comps
    res["budget_usd"] = budget
    res["cost_per_h_usd"] = budget / ref_h
    res["available"] = True
    _flag(fl, "info", "reference_mode", "Report reference: published totals at the report's own hours and fuel price. Switch to Custom simulation to change hours, fuel or costs.")
    return res


def _compute_legacy(row, scn, res):
    """Historical sheets (no PDF yet). Totals only; fuel is not separable, so fuel inputs are ignored.

    Fixed total = Couts_Fixes (hangar, insurance, misc) + Couts_Equipe (crew expense + crew training), counted ONCE.
    This split was verified on the 10 models of the old base that now have a PDF report: for all of them
    Couts_Fixes + Couts_Equipe equals the report's annual fixed total within 1 USD (see tests)."""
    fl = res["flags"]
    res["historical"] = True
    ref_h = num(row, "legacy_Heures_Base")
    fixed_ex = num(row, "legacy_Couts_Fixes_Annuels")
    crew = num(row, "legacy_Couts_Equipe_Annuels")
    var_h = num(row, "legacy_Cout_Horaire_Charter")
    res["hours"]["reference"] = ref_h
    _flag(fl, "warn", "legacy", "Historical sheet from the old base: currency not documented (treated as USD, unverified), fuel is not separable, "
          "no charter/private distinction in the source, detailed report not yet reconstructed.")
    if fixed_ex is None or crew is None or var_h is None or ref_h is None:
        _flag(fl, "error", "missing_core", "Historical values missing — no calculation performed.")
        return res
    fixed = fixed_ex + crew
    _flag(fl, "info", "legacy_fixed_split", "Historical fixed total = fixed lines excluding crew (hangar, insurance, misc) + crew (expense and training), each counted once. "
          "This split reproduces the report fixed total within 1 USD on the 10 old-base models that now have a PDF report; to confirm for this sheet.")
    res["published"] = dict(annual_fixed=fixed, variable_per_h=var_h, reference_hours=ref_h,
                            annual_budget=fixed + var_h * ref_h)
    live = scn.mode != "reference"
    H = scn.flown_hours if live else ref_h
    res["hours"]["flown"] = H
    if not live:
        res["hours"].update(billed=None, positioning=None, other=None)
    extra_f = (scn.extra_fixed or 0.0) if live else 0.0
    extra_v = (scn.extra_var_h or 0.0) if live else 0.0
    fixed_total = fixed + extra_f
    vh = var_h + extra_v
    if live:
        _flag(fl, "info", "legacy_fuel", "Fuel price / burn inputs do not apply to historical sheets (fuel is included in the hourly rate and cannot be separated).")
    res["fixed"] = dict(source_total=fixed, override_delta=0.0, extra=extra_f, annual_total=fixed_total,
                        includes="historical sheet: fixed excl. crew + crew (expense and training), scope to confirm")
    res["variable"] = dict(nonfuel_per_h=None, fuel_per_h=None, per_h=vh, annual=H * vh, source_nonfuel_per_h=None,
                           includes="hourly rate as published in the historical sheet (fuel not separable)")
    res["fuel"] = {}
    res["budget_usd"] = fixed_total + H * vh
    res["cost_per_h_usd"] = (res["budget_usd"] / H) if H > 0 else None
    res["components"] = [
        dict(category="Fixed", key="legacy_fixed_ex_crew", label="Fixed excl. crew (hangar, insurance, misc)", annual_usd=fixed_ex, hourly_usd=None, edited=False, source_value=fixed_ex),
        dict(category="Fixed", key="legacy_crew", label="Crew (expense + training)", annual_usd=crew, hourly_usd=None, edited=False, source_value=crew)]
    if extra_f:
        res["components"].append(dict(category="Fixed", key="extra_fixed", label="User-added fixed cost (not in report)", annual_usd=extra_f, hourly_usd=None, edited=True, source_value=None))
    res["components"].append(dict(category="Variable", key="legacy_var", label="Variable (historical hourly × hours)", annual_usd=H * vh, hourly_usd=vh, edited=False, source_value=var_h))
    for c in res["components"]:
        c["share_pct"] = c["annual_usd"] / res["budget_usd"] * 100 if res["budget_usd"] else None
    res["available"] = True
    if H <= 0:
        _flag(fl, "info", "zero_hours", "Annual flown hours are zero: cost per hour is not applicable.")
    if live:
        res["profit"] = _profit(scn, res, fixed_total, vh, H)
    return res


# ═════════════════════════════════════════════════════════════════════════════
# Charter profitability
# ═════════════════════════════════════════════════════════════════════════════
def rate_to_usd(scn: Scenario):
    if scn.charter_rate is None or scn.charter_rate <= 0:
        return None, "Charter rate not entered."
    if scn.charter_rate_ccy == "USD":
        return scn.charter_rate, None
    if scn.charter_rate_ccy == "EUR":
        if not scn.fx.is_valid():
            return None, "Charter rate is in EUR: enter a dated EUR/USD rate to convert it."
        return scn.charter_rate / scn.fx.usd_to_eur, None
    return None, f"Unknown rate currency '{scn.charter_rate_ccy}'."


def _profit(scn: Scenario, res: dict, fixed_total: float, var_h: float, H: float) -> dict:
    """Estimated operating result = charter revenue − variable costs of ALL flown hours − fixed costs
    − commercial fees not already included. Excludes financing, depreciation and tax (NOT a net profit)."""
    B, P, O = scn.billed_hours, scn.positioning_hours, scn.other_hours
    c = (scn.commission_pct or 0.0) / 100.0
    fees = scn.other_commercial_fees or 0.0
    out = dict(available=False, billed_hours=B, positioning_hours=P, other_hours=O, flown_hours=H,
               commission_pct=scn.commission_pct, other_fees=fees, messages=[])
    rate, err = rate_to_usd(scn)
    out["rate_usd"] = rate
    res["rate_usd"] = rate
    # variable cost of ALL flown hours, fixed costs
    var_cost = H * var_h
    out.update(variable_cost_all_flown=var_cost, fixed_cost=fixed_total)
    if err:
        out["messages"].append(err)
        return out
    revenue = rate * B
    commission = revenue * c
    result = revenue - commission - fees - var_cost - fixed_total
    total_cost = var_cost + fixed_total
    out.update(available=True, revenue=revenue, commission=commission, net_revenue_after_fees=revenue - commission - fees,
               operating_result=result, total_cost=total_cost,
               coverage_pct=((revenue - commission - fees) / total_cost * 100) if total_cost > 0 else None)
    rho = (P / B) if B > 0 else 0.0
    u = rate * (1 - c) - var_h * (1 + rho)         # contribution per billed hour after variable costs of billed + positioning hours
    out.update(positioning_ratio=rho, contribution_per_billed_hour=u,
               break_even_assumptions=(f"Positioning hours scale with billed hours (ratio {rho:.2f} = {P:g} ÷ {B:g}); "
                                       f"non-billed other hours stay at {O:g} h; commission {scn.commission_pct:g}% of revenue; "
                                       f"fixed costs and other commercial fees unchanged."
                                       if B > 0 else
                                       "No billed hours configured: positioning ratio assumed 0; other hours stay at "
                                       f"{O:g} h; commission {scn.commission_pct:g}%."))
    fixed_like = fixed_total + fees + var_h * O
    if u <= 0:
        out["break_even_billed_hours"] = None
        out["break_even_message"] = ("No break-even is attainable under these conditions: the contribution per billed hour after "
                                     "variable costs (incl. positioning) and commission is zero or negative.")
    else:
        be = fixed_like / u
        out["break_even_billed_hours"] = be
        out["break_even_flown_hours"] = be * (1 + rho) + O
        out["break_even_message"] = (f"Break-even at {be:,.0f} billed hours "
                                     f"({out['break_even_flown_hours']:,.0f} flown hours in total).")
        if out["break_even_flown_hours"] > HOURS_IN_YEAR:
            out["break_even_message"] += " This exceeds the 8,760 hours of a year: not achievable."
    # required rate (per billed hour) for a given operating margin on revenue
    out["required_rate_usd"] = lambda_required_rate(total_cost + fees, B, c, 0.0)
    return out


def lambda_required_rate(costs, B, c, margin):
    """Rate per billed hour giving operating result = margin × revenue. None if impossible."""
    if B <= 0:
        return None
    k = 1 - c - margin
    if k <= 0:
        return None
    return costs / (B * k)


def required_rate(profit: dict, margin_pct: float):
    """Quotation basis: charter rate per billed hour for a target operating margin (on gross revenue)."""
    if not profit or not profit.get("available"):
        return None
    costs = profit["total_cost"] + profit["other_fees"]
    return lambda_required_rate(costs, profit["billed_hours"], profit["commission_pct"] / 100.0, margin_pct / 100.0)


def sensitivity_billed_hours(row, scn: Scenario, hours_list):
    """Operating result vs billed hours, same engine; positioning scales with billed hours."""
    P, B = scn.positioning_hours, scn.billed_hours
    rho = (P / B) if B > 0 else 0.0
    out = []
    for h in hours_list:
        s = Scenario(**{**scn.__dict__, "billed_hours": float(h), "positioning_hours": rho * h})
        r = compute(row, s)
        pr = r.get("profit")
        out.append((h, pr["operating_result"] if pr and pr.get("available") else None))
    return out


def sensitivity_fuel_price(row, scn: Scenario, prices_usd_l):
    out = []
    for p in prices_usd_l:
        fc = FuelConfig(**{**scn.fuel.__dict__, "price_source": "manual", "price": p, "unit": "L", "currency": "USD", "taxes_pct": 0.0})
        r = compute(row, Scenario(**{**scn.__dict__, "fuel": fc}))
        out.append((p, r["cost_per_h_usd"] if r["available"] else None, r["budget_usd"] if r["available"] else None))
    return out


def fleet_comparison(base: pd.DataFrame, scn: Scenario) -> pd.DataFrame:
    """Same hours / fuel assumptions for every aircraft with a detailed record (reference records + web estimates, flagged by source_kind). Historical sheets are excluded."""
    rows = []
    for _, r in base[base["has_detail"]].iterrows():
        s = Scenario(**{**scn.__dict__, "aircraft_id": r["aircraft_id"], "fixed_overrides": {}, "var_overrides_h": {},
                        "charter_rate": None})
        res = compute(r, s)
        if res["available"]:
            rows.append(dict(aircraft_id=r["aircraft_id"], model=r["model"], manufacturer=r["manufacturer"], source_kind=r["source_kind"],
                             budget_usd=res["budget_usd"], cost_per_h_usd=res["cost_per_h_usd"],
                             fixed_usd=res["fixed"]["annual_total"], variable_usd=res["variable"]["annual"]))
    return pd.DataFrame(rows)


# ═════════════════════════════════════════════════════════════════════════════
# Alerts, provenance, performance
# ═════════════════════════════════════════════════════════════════════════════
KEY_FIELDS = ["reference_annual_hours", "reference_fuel_price_usd_per_l", "annual_budget_usd", "annual_fixed_cost_usd",
              "annual_variable_cost_usd", "annual_fuel_cost_usd", "annual_fuel_volume_l", "fuel_burn_l_per_h",
              "annual_crew_expense_fixed_usd", "annual_crew_training_fixed_usd", "annual_hangar_fixed_usd",
              "annual_insurance_fixed_usd", "annual_aircraft_misc_fixed_usd", "annual_airframe_maintenance_usd",
              "annual_engine_apu_maintenance_usd", "annual_crew_misc_variable_usd", "seats_full_range_nm",
              "ferry_range_nm", "normal_cruise_kmh", "block_speed_kmh", "average_preowned_price_usd",
              "maximum_takeoff_weight_kg"]


def data_class(status) -> str:
    return {"extracted": "Extracted", "derived": "Calculated", "converted": "Converted (calculated)",
            "normalized": "Normalized", "missing": "Missing", "invalid_source_placeholder": "Invalid source value (left empty)",
            "not_applicable": "Not applicable", "not_transcribed": "Not transcribed", "processing_metadata": "Processing metadata",
            "visual_unverified_unit": "Visual — unit unverified", "legacy": "Historical",
            "web_extracted": "Web estimate (extracted)", "assumed": "Assumed — to confirm"}.get(str(status), str(status))


def provenance_for(prov: pd.DataFrame, row) -> pd.DataFrame:
    p = prov[(prov["aircraft_id"] == row["aircraft_id"]) & (prov["source_file"] == row.get("source_file"))]
    return p


def alerts_for(row, checks: pd.DataFrame, conflicts: pd.DataFrame, conversions: pd.DataFrame) -> list:
    """Alerts shown next to the results. Built from the base — nothing is hard-coded per aircraft."""
    out = []
    status = str(row.get("record_status"))
    out.append(dict(level="info", text=STATUS_TEXT.get(status, status)))
    if status == LEGACY_STATUS:
        out.append(dict(level="warn", text="Currency of historical amounts is undocumented; the legacy charter rate is labelled EUR in the old base and is unverified."))
        return out
    kind = source_kind(row)
    if kind == "web_estimate":
        url, acc = _web_source(row)
        w = _web_cached(); w = w[w["aircraft_id"] == row["aircraft_id"]]
        tech = w[w["field"] == "technical_source_url"]
        out.append(dict(level="warn", text=f"Economic data: Guardian Jet web estimate ({url or 'URL n/a'}), consulted {acc or 'n/a'} — consultation date only, "
                        "effective/validity date unknown. Different source and scope from the full Menkor reference records."))
        out.append(dict(level="warn", text="Assumptions to confirm: USD from the '$' symbol; gallons read as US gallons (1 US gal = 3.785411784 L); 300 h/year and 7.54 USD/gal come from this single scenario and must not be mixed with the hours/prices of the full Menkor reference records."))
        out.append(dict(level="warn", text="Crew rubric is aggregated: training is not isolated and its inclusion is unknown — left empty, no generic training added, never replaced by zero."))
        out.append(dict(level="warn", text="Maintenance = 5-year average + engine program (APU coverage unspecified): the airframe / engine-APU / crew-misc split is left empty; only the combined maintenance line can be edited."))
        out.append(dict(level="warn", text="Fixed costs differ strongly from the full Menkor reference records: not declared equivalent — operator validation recommended."))
        out.append(dict(level="info", text="Annual fuel cost and volume are derived (burn × price × 300 h), not printed annual amounts. Hourly fuel keeps the computed cents."))
        out.append(dict(level="info", text="Technical data (ranges, cabin, ceiling, passengers) come from a public technical summary, with provenance separate from the Guardian Jet costs"
                        + (f" ({public_source(tech['value'].iloc[0])})" if len(tech) else "") + ". Contradictory cruise speeds and missing weights stay unavailable."))
    else:
        out.append(dict(level="info", text="Report date not provided: prices have no validity date. "
                        f"extraction_date ({row.get('extraction_date')}) is the processing date, not a market date."))
        out.append(dict(level="info", text="Amounts are USD from the report '$' symbol; the currency itself is not confirmed by the source."))
    aid, sf = row["aircraft_id"], row.get("source_file")
    ck = checks[(checks["aircraft_id"] == aid) & (checks["source_file"] == sf) & (checks["status"] != "OK")]
    if len(ck):
        names = "; ".join(f"{r['check']} (observed {r['observed']}, expected {r['expected']}, tol. {r['tolerance']})" for _, r in ck.head(6).iterrows())
        out.append(dict(level="warn", text=f"{len(ck)} numeric check(s) to review: {names}" + (" …" if len(ck) > 6 else "")))
    if status in ("source_values_review_required", "model_name_and_source_values_review_required"):
        inv = ck[ck["check"].str.startswith("positive_")] if len(ck) else ck
        if len(inv):
            out.append(dict(level="error", text="Printed value(s) invalid (0): " + ", ".join(inv["check"].str.replace("positive_physical_value_", "").str.replace("positive_source_value_", "")) + " — left empty, not replaced."))
    if status == "source_conflict_review_required":
        c = conflicts[conflicts["aircraft_id"] == aid]
        out.append(dict(level="warn", text=f"Source conflict: {len(c)} field(s) differ between the two reports (primary: {sf}). Verify currency and date with the source before commercial use."))
    cv = conversions[conversions["aircraft_id"] == aid]
    if len(cv):
        out.append(dict(level="info", text="Imperial report converted to SI (1 US gal = 3.785411784 L; GAL assumed US gallon — to confirm with the source). Originals kept in the conversions table."))
    miss = [f for f in KEY_FIELDS if num(row, f) is None]
    if miss:
        out.append(dict(level="warn", text="Missing / empty fields (not replaced by zero): " + ", ".join(miss)))
    if num(row, "annual_insurance_fixed_usd") == 0:
        out.append(dict(level="warn", text="Insurance printed as 0 in the source — kept as published, to verify."))
    return out


def performance_summary(row) -> dict:
    """Range semantics: seats-occupied range is NOT the manufacturer maximum range."""
    return dict(
        seats_range_nm=num(row, "seats_full_range_nm"), seats_range_km=num(row, "seats_full_range_km"),
        ferry_range_nm=num(row, "ferry_range_nm"),
        cruise_kmh=num(row, "normal_cruise_kmh"), block_kmh=num(row, "block_speed_kmh"),
        pax=num(row, "maximum_passengers_report"),
        range_definition=public_text(row.get("range_definition")) if pd.notna(row.get("range_definition", None)) else None,
        conditions=public_text(row.get("performance_conditions")) if pd.notna(row.get("performance_conditions", None)) else None,
        alt_nm=num(row, "range_alternate_nm"))
