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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ENGINE_VERSION = "2.2"
DB_VERSION = "v17-167-models-adj15"
BASE_FILE = "menkor_base_couts_ajustes_15pct.csv"   # Menkor cost base: selected costs already +15 % (see menkor_* metadata), originals kept in original__* columns
_HERE = Path(__file__).resolve().parent
# Data files live in data/. If they were uploaded flat next to app.py (GitHub web upload can flatten folders), fall back to that folder.
DATA_DIR = _HERE / "data" if (_HERE / "data" / BASE_FILE).exists() else (_HERE if (_HERE / BASE_FILE).exists() else _HERE / "data")

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
    """167 aircraft (144 PDF-documented + 2 web scenarios + 21 historical). aircraft_id is the stable key.
    Selected cost fields hold the Menkor-adjusted values; the original published values stay in the original__* columns (see original_view)."""
    df = _read(BASE_FILE, dtype={"aircraft_id": "string", "report_contact_phone": "string"}).copy()
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


SOURCE_LABELS = {"pdf_acc": "Menkor reference", "web_estimate": "Web estimate (partial)", "historical": "Historical sheet"}


def source_label(kind):
    return SOURCE_LABELS.get(kind, str(kind))


def load_charter_prices() -> pd.DataFrame:
    """Menkor indicative charter-price file: one row per aircraft_id (167). Strings; numbers parsed on use. Nothing is imputed."""
    return _read("menkor_tarifs_charter.csv", dtype=str)


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _s(x):
    return None if x is None or (isinstance(x, float) and x != x) or str(x).strip() == "" else str(x).strip()


def charter_estimate(aircraft_id, prices=None):
    """Indicative charter price (per billable flight hour, whole aircraft) for this exact aircraft_id, or None if the id is unknown.
    `available` is False when the file has no usable public price: nothing is replaced by zero or by another model.
    `auto_prefill` follows the file (False = proxy / low confidence / configuration to confirm: shown, never pre-selected)."""
    prices = load_charter_prices() if prices is None else prices
    r = prices[prices["aircraft_id"] == str(aircraft_id)]
    if r.empty:
        return None
    r = r.iloc[0]
    ref = _f(r.get("charter_rate_reference_per_hour"))
    ccy = _s(r.get("currency"))
    avail = ref is not None and ref > 0 and ccy in ("USD", "EUR") and _s(r.get("reference_method")) != "unavailable"
    return dict(
        available=bool(avail), reference=ref if avail else None, low=_f(r.get("charter_rate_low_per_hour")) if avail else None,
        high=_f(r.get("charter_rate_high_per_hour")) if avail else None, currency=ccy,
        method=_s(r.get("reference_method")), scope=_s(r.get("match_scope")), confidence=_s(r.get("confidence")),
        auto_prefill=bool(avail and str(r.get("auto_prefill_allowed")).strip().lower() == "true"), action=_s(r.get("claude_action")),
        source_name=_s(r.get("source_name")), source_model=_s(r.get("source_model")), source_url=_s(r.get("source_url")),
        region=_s(r.get("market_region")), access_date=_s(r.get("access_date")), effective_date=_s(r.get("price_effective_date")),
        fuel=_s(r.get("fuel_inclusion")), taxes=_s(r.get("taxes_and_fees")), positioning=_s(r.get("positioning")),
        alt_reference=_f(r.get("alternative_rate_reference")), alt_currency=_s(r.get("alternative_currency")), alt_url=_s(r.get("alternative_source_url")),
        notes=_s(r.get("notes")), unit=_s(r.get("rate_unit")))


def charter_disclaimers(e: dict) -> list:
    """Plain-language caveats shown with every proposed charter price (screens, PDF)."""
    out = ["ESTIMATE — indicative customer charter price taken from a public broker listing. It is not a Menkor quotation, not an observed average of transactions, and not operator net revenue.",
           f"Whole aircraft, per billable flight hour. Page consulted {e['access_date'] or 'n/a'} (consultation date, not a validity date"
           + (f"; stated period: {e['effective_date']}" if e.get("effective_date") else "; effective date unknown") + ")."]
    scope = {"exact_model": "Matched to this exact model.",
             "family_proxy": "PROXY: price of a related model or family — confirm the match before using it.",
             "configuration_review": "Configuration to confirm: the source page mixes several configurations."}.get(e.get("scope"), "Match to the model not stated.")
    out.append(f"{scope} Confidence: {e.get('confidence') or 'n/a'}.")
    if e.get("method") == "published_range_midpoint_not_observed_mean":
        out.append("The reference is the midpoint of a published range, not an observed mean.")
    elif e.get("method") == "single_aircraft_advertised_reference":
        out.append("The reference is the advertised price of one aircraft, not a model average.")
    if e.get("fuel") == "included_with_standard_surcharge_per_publisher_guide":
        out.append("Per the broker's guide: fuel is included with a standard surcharge; taxes, airport fees and crew overnights are extra; positioning is charged additionally if required.")
    else:
        out.append("Fuel, taxes / airport fees and positioning terms of this price are unknown.")
    if e.get("region"):
        out.append(f"Market: {e['region']}.")
    out.append("The Menkor cost-base adjustment is never applied to this price.")
    return out


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


# ── "today" and validity of dated assumptions ────────────────────────────────
# The current date is always computed (never hard-coded). Business time zone = Dubai (Menkor Aviation GBL), UTC+04:00, no DST:
# a fuel quote valid "until 2026-10-18" is still valid during that whole calendar day in Dubai.
BUSINESS_TZ_NAME = "Asia/Dubai (UTC+04:00, no daylight saving)"
BUSINESS_TZ = timezone(timedelta(hours=4))


def current_date(now: datetime | None = None) -> date:
    """Today's calendar date in the business time zone (Dubai). `now` can be injected for tests."""
    return (now or datetime.now(timezone.utc)).astimezone(BUSINESS_TZ).date()


def validity_status(date_str, today: date | None = None) -> dict:
    """Status of a validity date: 'unknown' (no date), 'valid' (date >= today), 'expired' (date < today), 'invalid' (malformed).
    A malformed date is an explicit error and never silently treated as missing or valid."""
    today = today or current_date()
    out = dict(status="unknown", date=None, today=today.isoformat(), tz=BUSINESS_TZ_NAME, days=None, message="")
    txt = (str(date_str).strip() if date_str is not None else "")
    if not txt:
        out["message"] = "Validity unknown: no validity date entered."
        return out
    if not _valid_date(txt):
        out.update(status="invalid", date=txt,
                   message=f"Invalid validity date '{txt}': expected a real calendar date in the format YYYY-MM-DD (e.g. 2026-12-31).")
        return out
    d = date.fromisoformat(txt)
    out.update(date=txt, days=(d - today).days)
    if d >= today:
        out.update(status="valid", message=f"Valid: validity date {txt} is on or after today ({today.isoformat()}).")
    else:
        out.update(status="expired", message=f"EXPIRED: validity date {txt} is before today ({today.isoformat()}), {(today - d).days} day(s) ago.")
    return out


def fuel_confirmation_token(fc) -> str:
    """Identifies the exact manual price + date a user confirmed. Any change of price, unit, currency, taxes or date invalidates it."""
    return f"{fc.price}|{fc.unit}|{fc.currency}|{fc.taxes_pct}|{(fc.validity_date or '').strip()}"




def dates_for(row) -> dict:
    """The three different dates are never mixed: economic date (of the figures), consultation date (web page read), extraction date (file processing)."""
    econ = row.get("report_date") if hasattr(row, "get") else None
    econ = None if (econ is None or (isinstance(econ, float) and math.isnan(econ)) or str(econ).strip() in ("", "nan")) else str(econ)
    out = dict(economic_reference_date=econ or "unknown", consultation_date=None, extraction_date=None)
    ext = row.get("extraction_date") if hasattr(row, "get") else None
    if ext is not None and str(ext).strip() not in ("", "nan", "None"):
        out["extraction_date"] = str(ext)
    if source_kind(row) == "web_estimate":
        out["consultation_date"] = _web_source(row)[1] or None
    return out


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
    price_source: str = "report"        # 'report' (reference_fuel_price_usd_per_l) | 'average' (user's annual planning assumption: `price` per litre in `currency`)
                                        # | 'manual' (ADVANCED module: dated local quote with airport/supplier/taxes/fees/validity)
                                        # | 'benchmark' (regional refinery benchmark, data/fuel_regional_benchmarks.csv): `benchmark_region` selects the row,
                                        #   `price` (USD/L) is None = the benchmark itself, or the user's own value (= "User-adjusted annual fuel price assumption")
    burn_method: str = "published"      # 'published' | 'derived' | 'custom'
    custom_burn_l_h: float | None = None
    benchmark_region: str = ""          # region_id of fuel_regional_benchmarks.csv (benchmark method only)
    # 'average': price = average price PER LITRE (taxes and fuel fees included, per the user's operating habits), currency = 'USD' | 'EUR'.
    # 'manual' (advanced): price in `unit`, with the optional metadata below, recorded in results/exports.
    price: float | None = None
    unit: str = "L"                     # 'L' | 'USG' (advanced module only; the average price is always per litre)
    currency: str = "USD"               # 'USD' | 'EUR'
    taxes_pct: float = 0.0              # taxes applied on the price
    fees_per_uplift: float = 0.0        # fixed fees per uplift (in `currency`) — not part of the hourly average
    airport_icao: str = ""
    airport_iata: str = ""
    supplier: str = ""
    validity_date: str = ""             # ISO date entered by the user
    expired_confirmation: str = ""      # token of the price/date the user explicitly accepted as a HISTORICAL assumption (see fuel_confirmation_token)


# ═════════════════════════════════════════════════════════════════════════════
# Menkor cost base — the adjustment lives IN THE DATA (base CSV), never in the engine
# ═════════════════════════════════════════════════════════════════════════════
# The base file stores, for the selected lines (maintenance, airport fees, crew training, hangar) and the totals that contain them, the
# Menkor-adjusted values (+15 %, Menkor assumption). The original published values are kept in `original__<field>` columns.
#   * Custom simulation reads the stored (adjusted) fields.      * Report reference reads the original__ values only (original_view).
# There is no adjustment switch, percentage input or recalculation of the adjustment anywhere in the application.
ORIGINAL_PREFIX = "original__"
# lines described in the "original vs Menkor base" table: label -> (kind, [(hourly field, annual field)])
MENKOR_BASE_LINES = {
    "Maintenance & maintenance programs": dict(kind="var", pairs=[("hourly_airframe_maintenance_usd", "annual_airframe_maintenance_usd"),
                                                                    ("hourly_engine_apu_maintenance_usd", "annual_engine_apu_maintenance_usd")],
                                               web_pairs=[("hourly_maintenance_total_usd", None)]),
    "Handling & en-route / airport fees": dict(kind="var", pairs=[("hourly_airport_fees_usd", None)]),
    "Crew training": dict(kind="fixed", pairs=[(None, "annual_crew_training_fixed_usd")]),
    "Hangar": dict(kind="fixed", pairs=[(None, "annual_hangar_fixed_usd")]),
}


def original_view(row):
    """The record with every `original__<field>` value written back into <field>: the strictly original published values
    (used by Report reference). Fields without an original__ value are unchanged; nothing is recalculated."""
    r = row.copy()
    for c in row.index:
        if isinstance(c, str) and c.startswith(ORIGINAL_PREFIX):
            f = c[len(ORIGINAL_PREFIX):]
            if f in r.index and pd.notna(row[c]):
                r[f] = row[c]
    return r


def menkor_base_info(row) -> dict:
    """Metadata of the Menkor cost base for this record (from the data file, not computed)."""
    def g(k):
        v = row.get(k)
        return None if v is None or (not isinstance(v, str) and pd.isna(v)) else v
    applied = str(g("menkor_adjustment_applied")).strip().lower() in ("true", "1", "yes")
    pct = float(g("menkor_adjustment_pct") or 0.0)
    return dict(version=g("menkor_base_version"), applied=applied, pct=pct, status=g("menkor_adjustment_status"),
                method=g("menkor_adjustment_method"), processing_date=g("menkor_adjustment_processing_date"),
                economic_reference_date=g("menkor_economic_reference_date") or "unknown",
                delta_fixed=g("menkor_delta_fixed_usd"), delta_variable=g("menkor_delta_variable_usd"), delta_budget=g("menkor_delta_budget_usd"))


def menkor_base_text(info: dict) -> str:
    if not info.get("applied"):
        return "Menkor cost base: no adjustment for this record (original published values)."
    return (f"Menkor cost base: selected costs (maintenance, airport fees, crew training, hangar) include a Menkor adjustment of +{info['pct']:g}% "
            "applied to the original published values; fuel, insurance, crew salaries and expenses, catering and misc are unchanged. "
            "It is a Menkor assumption, not verified market inflation; the economic reference date is unknown. "
            "The original published values are kept separately and are used by Report reference.")


def menkor_base_items(row, orig) -> list:
    """Original vs Menkor-base values of the adjusted lines (read from the data, annual USD)."""
    ref_h = num(orig, "reference_annual_hours")
    web = source_kind(row) == "web_estimate"
    items = []
    if not ref_h:
        return items
    for cat, spec in MENKOR_BASE_LINES.items():
        before = after = 0.0
        found = False
        for hf, af in (spec.get("web_pairs", spec["pairs"]) if web else spec["pairs"]):
            def annual(r):
                a = num(r, af) if af else None
                h = num(r, hf) if hf else None
                return a if a is not None else (h * ref_h if h is not None else None)
            b0, b1 = annual(orig), annual(row)
            if b0 is None or b1 is None:
                continue
            found = True; before += b0; after += b1
        if found:
            items.append(dict(item=cat, before=before, after=after, pct=((after / before - 1.0) * 100.0) if before else None, delta=after - before,
                              note="Menkor recurrent training price (Global)" if cat == "Crew training" and before and abs(after / before - 1.15) > 1e-6 else ""))
        else:
            items.append(dict(item=cat, before=None, after=None, pct=None, delta=None, note="not available in this source — not adjusted, not replaced by zero"))
    return items


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
    charter_rate_source: str = "custom"      # 'custom' | 'estimate_ref' | 'estimate_low' | 'estimate_high' (Menkor charter price file)
    charter_rate_basis: str = ""            # short description of the estimate used (scope, confidence, consultation date)

    def canonical(self) -> dict:
        return asdict(self)

    def config_hash(self, extra: str = "") -> str:
        sc = self.canonical()
        if self.mode == "reference":
            # Report reference only depends on the aircraft and the display rate: stored custom parameters must not change its identity.
            sc = dict(aircraft_id=sc["aircraft_id"], mode="reference", fx=sc["fx"])
        payload = json.dumps({"scenario": sc, "db": DB_VERSION, "engine": ENGINE_VERSION, "extra": extra},
                             sort_keys=True, default=str)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    @property
    def flown_hours(self) -> float:
        return float(self.billed_hours) + float(self.positioning_hours) + float(self.other_hours)


# ═════════════════════════════════════════════════════════════════════════════
# Fuel helpers
# ═════════════════════════════════════════════════════════════════════════════
AVERAGE_PRICE_LABEL = "Average fuel price — annual planning assumption"
AVERAGE_PRICE_NATURE = ("Average fuel price entered by the user as an annual planning assumption; it includes the fuel taxes and fees that normally apply "
                        "according to the operating habits. It is not a verified local price and not a real-time price.")


BENCHMARK_FILE = "fuel_regional_benchmarks.csv"
BENCHMARK_DISCLAIMER = ("Refinery market benchmark — not an into-wing price. Adjust the average price to reflect your fuel contracts, "
                        "delivery charges and applicable non-recoverable taxes.")
BENCHMARK_USER_ADJUSTED = "User-adjusted annual fuel price assumption."
BENCHMARK_NATURE = ("Weekly refinery market benchmark (IATA Fuel Price Monitor, Platts data). Not a real-time feed, not an annual average, not a forecast, "
                    "not an average price delivered to the aircraft: no regional mark-up is added.")


def usd_per_l_from_us_cents_per_usg(cents) -> float:
    """price_usd_per_l = cents per US gallon / 100 / 3.785411784 (full precision kept; round only for display)."""
    return float(cents) / 100.0 / USG_TO_L


def load_fuel_benchmarks() -> pd.DataFrame:
    """Separate table (independent from the aircraft base). Adds price_usd_per_l computed from the stored source price. Empty frame if the file is absent."""
    f = DATA_DIR / BENCHMARK_FILE
    if not f.exists():
        f = _HERE / BENCHMARK_FILE
    if not f.exists():
        return pd.DataFrame()
    d = pd.read_csv(f, dtype=str, keep_default_na=False)
    d["price_us_cents_per_us_gallon"] = pd.to_numeric(d["price_us_cents_per_us_gallon"], errors="coerce")
    d["price_usd_per_l"] = d["price_us_cents_per_us_gallon"].map(lambda v: usd_per_l_from_us_cents_per_usg(v) if pd.notna(v) and v > 0 else None)
    return d


def benchmark_row(region_id: str):
    d = load_fuel_benchmarks()
    if d.empty or not region_id:
        return None
    m = d[d["region_id"] == region_id]
    return None if m.empty else m.iloc[0]


def benchmark_price_info(fc: "FuelConfig"):
    """Return (info dict or None, error or None) for the benchmark method. price_used = user value if set, else the exact benchmark."""
    r = benchmark_row(fc.benchmark_region)
    if r is None:
        return None, "Main refuelling region not selected or not found in the benchmark table."
    bench = r["price_usd_per_l"]
    if bench is None or pd.isna(bench):
        return None, "Benchmark price missing for this region."
    used = bench if fc.price is None else float(fc.price)
    if used <= 0:
        return None, "Average fuel price used must be greater than zero."
    adjusted = not math.isclose(used, float(bench), rel_tol=0, abs_tol=5e-4)   # displayed precision is 3 decimals
    if not adjusted:
        used = float(bench)                                                     # an untouched (rounded) field keeps the exact benchmark
    return dict(region_id=r["region_id"], region=r["region"], period_start=r["period_start"], period_end=r["period_end"], period_label=r["period_label"],
                benchmark=r["benchmark"], source_cents_usg=float(r["price_us_cents_per_us_gallon"]), benchmark_usd_l=float(bench), used_usd_l=float(used),
                user_adjusted=adjusted, nature="user hypothesis" if adjusted else "refinery reference",
                disclaimer=BENCHMARK_DISCLAIMER, adjusted_text=BENCHMARK_USER_ADJUSTED if adjusted else "", url_1=r["source_url_1"], url_2=r["source_url_2"],
                publisher=r["source_publisher"], licence_note=r["licence_note"], currency="USD", unit="USD per litre"), None


def average_price_usd_per_l(fc: FuelConfig, fx: Fx):
    """Average planning price: ONE price per litre + its currency. Returns (usd_per_litre or None, error or None).
    No airport, supplier, separate taxes, per-uplift fees or validity date take part in it. EUR needs an explicit dated rate (same rule as everywhere)."""
    if fc.price is None or fc.price <= 0:
        return None, "Average fuel price not entered."
    if fc.currency == "USD":
        return float(fc.price), None
    if fc.currency == "EUR":
        if not fx.is_valid():
            return None, "Average fuel price is in EUR: enter a dated EUR/USD rate to convert it."
        return float(fc.price) / fx.usd_to_eur, None
    return None, f"Unknown currency '{fc.currency}'."


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
        published={}, reconciliation=None, profit=None, rate_usd=None, fuel_validity=None, fuel_benchmark=None, dates=dates_for(row), menkor_base=dict(applied=False, pct=0.0, items=[], text=""),
        charter_rate_info=dict(source=getattr(scn, "charter_rate_source", "custom"), basis=getattr(scn, "charter_rate_basis", "")))


def compute(row, scn: Scenario, today: date | None = None) -> dict:
    """The only place where costs and results are calculated. `today` (business-zone date) is computed unless injected by a test."""
    res = _empty_result(row, scn)
    fl = res["flags"]
    today = today or current_date()
    if str(row.get("record_status")) == LEGACY_STATUS:
        return _compute_legacy(row, scn, res)
    orig_row = original_view(row)
    info = menkor_base_info(row)
    if scn.mode == "reference":
        # Report reference is STRICTLY the original published values (original__ columns): no Menkor adjustment, no user edit, whatever the scenario says.
        row = orig_row
        res["menkor_base"] = dict(info, applied=False, reason="reference_mode", items=[], text="Report reference: original published values (the Menkor cost-base adjustment is not used).")
    else:
        # Custom simulation reads the Menkor cost base as stored (adjustment already in the data); nothing is adjusted here.
        _ob, _ab = num(orig_row, "annual_budget_usd"), num(row, "annual_budget_usd")
        res["menkor_base"] = dict(info, items=menkor_base_items(row, orig_row) if info["applied"] else [], text=menkor_base_text(info),
                                  published_budget_original=_ob, published_budget_adjusted=_ab,
                                  delta_total=(_ab - _ob) if (_ob is not None and _ab is not None and info["applied"]) else None,
                                  delta_fixed=((num(row, "annual_fixed_cost_usd") or 0) - (num(orig_row, "annual_fixed_cost_usd") or 0)) if info["applied"] else 0.0,
                                  delta_variable=((num(row, "annual_variable_cost_usd") or 0) - (num(orig_row, "annual_variable_cost_usd") or 0)) if info["applied"] else 0.0)

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
    if scn.fuel.price_source == "average":
        price_usd_l, err = average_price_usd_per_l(scn.fuel, scn.fx)
        price_label = AVERAGE_PRICE_LABEL + " (user hypothesis, not a verified or real-time price)"
        if err:
            _flag(fl, "error", "price_average", err)
            return res
        _flag(fl, "info", "fuel_average_assumption", AVERAGE_PRICE_NATURE)
    elif scn.fuel.price_source == "benchmark":
        binfo, err = benchmark_price_info(scn.fuel)
        if err:
            _flag(fl, "error", "price_benchmark", err)
            return res
        res["fuel_benchmark"] = binfo
        res["config_hash"] = scn.config_hash(extra=f"bench={binfo['region_id']}:{binfo['period_end']}:{binfo['source_cents_usg']}:{binfo['used_usd_l']:.8f}")   # a refreshed table changes the id
        price_usd_l = binfo["used_usd_l"]
        price_label = ("Regional refinery benchmark, user-adjusted (user hypothesis)" if binfo["user_adjusted"] else "Regional refinery benchmark (not an into-wing price)")
        _flag(fl, "info", "fuel_benchmark", BENCHMARK_DISCLAIMER)
        if binfo["user_adjusted"]:
            _flag(fl, "info", "fuel_benchmark_adjusted", BENCHMARK_USER_ADJUSTED)
    elif scn.fuel.price_source == "manual":
        vs = validity_status(scn.fuel.validity_date, today)
        vs["confirmed"] = bool(vs["status"] == "expired" and scn.fuel.expired_confirmation
                               and scn.fuel.expired_confirmation == fuel_confirmation_token(scn.fuel))
        vs["used_as_historical"] = vs["confirmed"]
        res["fuel_validity"] = vs
        res["config_hash"] = scn.config_hash(extra=f"fuel_validity={vs['status']}:{vs['confirmed']}")   # the status can change with time even if the inputs do not
        price_usd_l, err = manual_price_usd_per_l(scn.fuel, scn.fx)
        price_label = "Advanced local quote entered by the user (no live feed)"
        if err:
            _flag(fl, "error", "price_manual", err)
            return res
        if vs["status"] == "invalid":
            _flag(fl, "error", "fuel_date_invalid", vs["message"] + " The calculation is not performed until the date is corrected or cleared.")
            return res
        if vs["status"] == "unknown":
            _flag(fl, "warn", "fuel_validity_unknown", "Manual fuel price with unknown validity (no validity date): treat it as an unverified assumption.")
        elif vs["status"] == "expired":
            if not vs["confirmed"]:
                _flag(fl, "error", "fuel_price_expired",
                      vs["message"] + " This price is not used until you explicitly confirm it as a historical assumption (checkbox next to the fuel price), or enter a current quote.")
                return res
            _flag(fl, "warn", "fuel_price_expired_confirmed",
                  vs["message"] + " Used as a HISTORICAL assumption after explicit user confirmation: not a current market price.")
    else:
        price_usd_l = ref_price
        price_label = ("Web scenario price 7.54 USD per US gallon (Guardian Jet; US gallon assumed, to confirm) — not a current market price"
                       if kind == "web_estimate" else "Report reference price (reference_fuel_price_usd_per_l) — not a current market price")
        if price_usd_l is None:
            _flag(fl, "error", "no_ref_price", "Report fuel price missing — enter an average fuel price.")
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
                                  fees_per_uplift=scn.fuel.fees_per_uplift, validity_date=scn.fuel.validity_date,
                                  validity_status=(res.get("fuel_validity") or {}).get("status"))
                       if scn.fuel.price_source == "manual" else None,
                       average=dict(price=scn.fuel.price, currency=scn.fuel.currency, price_usd_l=price_usd_l, nature=AVERAGE_PRICE_NATURE,
                                    fx_rate=(scn.fx.usd_to_eur if scn.fuel.currency == "EUR" else None), fx_date=(scn.fx.rate_date if scn.fuel.currency == "EUR" else None))
                       if scn.fuel.price_source == "average" else None,
                       benchmark=res.get("fuel_benchmark") if scn.fuel.price_source == "benchmark" else None)
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
                      edited=scn.fuel.price_source in ("manual", "average", "benchmark") or method == "custom", source_value=None))
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
                original_published_budget=num(orig_row, "annual_budget_usd"),
                adjustment_delta=(budget_src - num(orig_row, "annual_budget_usd")) if (info["applied"] and num(orig_row, "annual_budget_usd") is not None) else 0.0,
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
    _flag(fl, "info", "reference_mode", "Report reference: published totals at the report's own hours and fuel price, original published values only (the Menkor cost-base adjustment and every edit are not used). Switch to Custom simulation to adjust costs.")
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
        fc = FuelConfig(**{**scn.fuel.__dict__, "price_source": "average", "price": p, "unit": "L", "currency": "USD", "taxes_pct": 0.0})
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
