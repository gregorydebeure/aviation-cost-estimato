"""Builds data/menkor_base.csv from the Menkor workbook (sheet Base_123 + Maintenance/Salaires/Assurance_source).

    python tools/build_base_from_xlsx.py <workbook.xlsx> [out.csv]

Rules (nothing is invented):
  * the workbook MUST contain calculated values (open + save it in Excel, or recalculate with LibreOffice): a formula cell with no cached value is read as missing;
  * every total (fixed, variable, budget, cost/h) is re-computed here from its components with the workbook's own formula and compared with the workbook's value;
    any difference > 1 USD stops the build;
  * a total is left EMPTY when one of its components is missing (same rule as the workbook) — the engine then refuses to calculate and names the missing lines;
  * zero maintenance fixed fee = no programme (column left empty); the only non-zero fee is kept as its own fixed line;
  * a 'Constructeur' that is empty is completed from the first word of the model name (classification only, listed in the output).
"""
import sys
from pathlib import Path

import openpyxl
import pandas as pd

SOURCE_NAME = "Menkor_118_avions_carburant_1274_2026-11-12.xlsx"
EXCLUDED_IDS = {"airbus_acj319neo", "airbus_acj320neo"}      # removed from the base on 12 Nov 2026 (client instruction); the rows stay in the workbook
SHEET = "Base_123"
HEADER_ROW = 6
# workbook header -> engine field
MAP = {
    "Identifiant": "aircraft_id", "Modèle": "model", "Constructeur": "manufacturer",
    "Heures annuelles de référence": "reference_annual_hours",
    "Coût fixe annuel total (USD)": "annual_fixed_cost_usd", "Coût variable annuel total (USD)": "annual_variable_cost_usd",
    "Budget annuel estimé (USD)": "annual_budget_usd", "Coût horaire global (USD/h)": "total_cost_per_h_from_annual_usd",
    "Équipage annuel retenu (USD)": "annual_crew_expense_fixed_usd", "Formation annuelle (USD)": "annual_crew_training_fixed_usd",
    "Hangar annuel (USD)": "annual_hangar_fixed_usd", "Assurance annuelle (USD)": "annual_insurance_fixed_usd",
    "Autres frais fixes annuels (USD)": "annual_aircraft_misc_fixed_usd",
    "Maintenance générale variable annuelle (USD)": "annual_airframe_maintenance_usd",
    "Budget moteurs annuel (USD, APU à confirmer)": "annual_engine_apu_maintenance_usd",
    "Carburant annuel (USD)": "annual_fuel_cost_usd",
    "Déplacements équipage (USD/h)": "hourly_crew_travel_usd", "Restauration à bord (USD/h)": "hourly_catering_usd",
    "Redevances aéroportuaires (USD/h)": "hourly_airport_fees_usd", "Frais variables supplémentaires (USD/h)": "hourly_other_usd",
    "Maintenance équivalente totale (USD/h)": "hourly_maintenance_total_usd",
    "Point médian de prix demandé (USD)": "average_preowned_price_usd",
    "Volume annuel de carburant (L)": "annual_fuel_volume_l", "Consommation de carburant (L/h)": "fuel_burn_l_per_h",
    "Autonomie à pleine capacité (NM)": "seats_full_range_nm", "Autonomie à pleine capacité (km)": "seats_full_range_km",
    "Autonomie de convoyage (NM)": "ferry_range_nm", "Croisière normale (kt)": "normal_cruise_kts", "Croisière normale (km/h)": "normal_cruise_kmh",
    "Vitesse bloc (kt)": "block_speed_kts", "Vitesse bloc (km/h)": "block_speed_kmh",
    "Croisière long rayon (kt)": "long_range_cruise_kts", "Croisière long rayon (km/h)": "long_range_cruise_kmh",
    "Nombre maximal de passagers": "maximum_passengers_report", "Charge utile à plein carburant (kg)": "payload_full_fuel_kg",
    "Volume cabine (m³)": "cabin_volume_m3", "Hauteur cabine (m)": "cabin_height_m", "Largeur cabine (m)": "cabin_width_m", "Longueur cabine (m)": "cabin_length_m",
    "Début de production": "production_start_report", "Fin de production": "production_end_report", "Flotte active estimée": "active_fleet_approx_report",
    "Longueur de piste équilibrée (m)": "balanced_field_length_m", "Distance d’atterrissage (m)": "landing_distance_m",
    "Masse maximale au décollage (kg)": "maximum_takeoff_weight_kg", "Masse maximale à l’atterrissage (kg)": "maximum_landing_weight_kg",
    "Masse en ordre d’exploitation (kg)": "basic_operating_weight_kg", "Masse de carburant utilisable (kg)": "usable_fuel_weight_kg",
    "Plafond pratique (m)": "service_ceiling_m", "Dégagement de référence (NM)": "range_alternate_nm",
    "Statut des données": "menkor_data_status", "Code barème salaire": "menkor_crew_scale_code",
    "Équipage annuel EUR": "menkor_crew_annual_eur", "Taux USD pour 1 EUR": "menkor_eur_usd_rate", "Date du taux EUR/USD": "menkor_eur_usd_date",
    "Forfait maintenance fixe annuel USD": "annual_maintenance_program_fixed_usd",
    "Maintenance générale USD/h": "hourly_airframe_maintenance_usd", "Budget moteurs USD/h": "hourly_engine_apu_maintenance_usd",
    "Supplément maintenance annuel USD": "menkor_maintenance_supplement_annual_usd", "Mode maintenance": "menkor_maintenance_mode",
    "Statut maintenance": "menkor_maintenance_status", "Source maintenance": "menkor_maintenance_source",
    "Consultation maintenance": "menkor_maintenance_consulted", "Périmètre APU": "menkor_apu_note",
}
# the workbook says 'USD per 1 000 L'; the engine works in USD per litre
FUEL_PRICE_HEADER = "Prix carburant de référence (USD/1 000 L)"
# fields whose absence makes a total impossible (workbook rule) -> readable name for the message shown to the user
FIXED_NEEDED = [("annual_crew_expense_fixed_usd", "crew expense"), ("annual_crew_training_fixed_usd", "crew training"), ("annual_hangar_fixed_usd", "hangar"),
                ("annual_insurance_fixed_usd", "insurance"), ("annual_aircraft_misc_fixed_usd", "aircraft miscellaneous")]
VAR_NEEDED = [("annual_airframe_maintenance_usd", "airframe maintenance"), ("annual_engine_apu_maintenance_usd", "engine maintenance"), ("annual_fuel_cost_usd", "fuel"),
              ("hourly_crew_travel_usd", "crew travel"), ("hourly_catering_usd", "catering"), ("hourly_airport_fees_usd", "airport fees")]
HOURS = ("reference_annual_hours", "reference annual hours")


def _num(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if x != x else x


def uncached_formulas(path):
    """Number of formula cells that have NO stored result (a workbook that was never calculated, or saved by a tool that drops results).
    A formula whose result is an empty string is stored with an empty value and is not counted."""
    import re as _re
    import zipfile
    n = 0
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                xml = z.read(name).decode("utf-8", "ignore")
                for cell in _re.findall(r"<c\b[^>]*[^/>]>(?:(?!</c>).)*?</c>", xml, _re.S):
                    if "<f" not in cell:
                        continue
                    head = cell[:cell.index(">")]
                    empty_v = ("<v" not in cell) or _re.search(r"<v\s*/>|<v></v>", cell)
                    if empty_v and 't="str"' not in head:        # a formula that really returned "" is stored as a string; an uncalculated one has no type
                        n += 1
    return n


def read_workbook(path):
    n = uncached_formulas(path)
    if n:
        raise SystemExit(f"The workbook has {n} formula cell(s) without a calculated value: open it in Excel and save it (or recalculate it) before building the base.")
    ws = openpyxl.load_workbook(path, data_only=True)[SHEET]
    hdr = [c.value for c in ws[HEADER_ROW]]
    rows = []
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        if ws.cell(r, 1).value and ws.cell(r, 1).value not in EXCLUDED_IDS:
            rows.append({hdr[j]: ws.cell(r, j + 1).value for j in range(len(hdr))})
    return hdr, rows


def build(src, out, old_csv=None):
    hdr, rows = read_workbook(src)
    unknown = [h for h in hdr if h and h not in MAP and h != FUEL_PRICE_HEADER]
    if unknown:
        raise SystemExit(f"Unmapped workbook columns (add them to MAP): {unknown}")
    old = None
    if old_csv and Path(old_csv).exists():
        old = pd.read_csv(old_csv, encoding="utf-8-sig", dtype={"aircraft_id": "string"}).set_index("aircraft_id")
    recs, notes = [], []
    # first word of the model -> manufacturer, learned from the rows that state it (Challenger -> Bombardier, Airbus -> Airbus ...)
    fam = {}
    for w in rows:
        if w.get("Constructeur"):
            fam.setdefault(str(w["Modèle"]).split()[0].lower(), w["Constructeur"])
    for w in rows:
        r = {MAP[h]: w.get(h) for h in hdr if h in MAP}
        fp = _num(w.get(FUEL_PRICE_HEADER))
        r["reference_fuel_price_usd_per_l"] = fp / 1000.0 if fp is not None else None
        for k, v in list(r.items()):
            if isinstance(v, str) and v.strip() == "":
                r[k] = None
        aid = r["aircraft_id"]
        if not r.get("manufacturer"):
            first = str(r["model"]).split()[0]
            r["manufacturer"] = fam.get(first.lower(), first)
            notes.append(f"manufacturer completed from the model name / same family: {aid} -> {r['manufacturer']}")
        # ── totals re-computed with the workbook's own formulas, then compared ────────────────
        h = _num(r.get("reference_annual_hours"))
        fx = [_num(r.get(f)) for f, _ in FIXED_NEEDED]
        fee = _num(r.get("annual_maintenance_program_fixed_usd"))
        fixed = sum(fx) + fee if all(v is not None for v in fx) and fee is not None else None
        vv = [_num(r.get(f)) for f, _ in VAR_NEEDED]
        other_h = _num(r.get("hourly_other_usd")) or 0.0
        supp = _num(r.get("menkor_maintenance_supplement_annual_usd")) or 0.0
        var = None
        if h is not None and h >= 0 and all(v is not None for v in vv):
            var = vv[0] + vv[1] + vv[2] + h * (vv[3] + vv[4] + vv[5] + other_h) + supp
        for key, calc in (("annual_fixed_cost_usd", fixed), ("annual_variable_cost_usd", var)):
            wb = _num(r.get(key))
            if (wb is None) != (calc is None) or (wb is not None and abs(wb - calc) > 1.0):
                raise SystemExit(f"{aid}: workbook {key}={wb} differs from the recomputed {calc} (is the workbook calculated?)")
        bud = fixed + var if fixed is not None and var is not None else None
        if (_num(r.get("annual_budget_usd")) is None) != (bud is None) or (bud is not None and abs(_num(r["annual_budget_usd"]) - bud) > 1.0):
            raise SystemExit(f"{aid}: workbook budget differs from fixed + variable")
        # missing lines, readable (shown by the engine instead of a field name)
        missing = [lab for (f, lab), v in zip(FIXED_NEEDED, fx) if v is None] + [lab for (f, lab), v in zip(VAR_NEEDED, vv) if v is None]
        if h is None:
            missing.insert(0, HOURS[1])
        r["menkor_missing_fields"] = "; ".join(missing) if (fixed is None or var is None) else None
        # zero fee = no programme: left empty (a zero line would be shown for 119 aircraft)
        if fee == 0:
            r["annual_maintenance_program_fixed_usd"] = None
        # derived diagnostics used by the engine (only when the inputs exist; same definitions as the former base)
        fuelc, vol = _num(r.get("annual_fuel_cost_usd")), _num(r.get("annual_fuel_volume_l"))
        if h and var is not None:
            r["variable_cost_per_h_from_annual_usd"] = var / h
            r["nonfuel_variable_cost_per_h_usd"] = (var - fuelc) / h
        if h and vol is not None:
            r["fuel_burn_from_annual_l_per_h"] = vol / h
        if vol and fuelc is not None:
            r["fuel_price_implied_usd_per_l"] = fuelc / vol
        if fixed is not None:
            r["fixed_excluding_crew_expense_usd"] = fixed - _num(r["annual_crew_expense_fixed_usd"])
        if bud:
            r["annual_variable_share_report_pct"] = 100.0 * var / bud
            r["annual_fixed_share_report_pct"] = 100.0 * fixed / bud
        r["currency"] = "USD"
        r["record_status"] = "menkor_base_2026-11-12"
        r["source_file"] = SOURCE_NAME
        r["report_brand"] = "MENKOR AVIATION GBL"
        # the range definition / test conditions describe the SAME performance values as the former base (verified identical): kept for the same aircraft
        if old is not None and aid in old.index:
            for c in ("range_definition", "performance_conditions"):
                r[c] = old.at[aid, c]
        recs.append(r)
    df = pd.DataFrame(recs)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    return df, notes


if __name__ == "__main__":
    src = sys.argv[1]
    here = Path(__file__).resolve().parent.parent
    out = sys.argv[2] if len(sys.argv) > 2 else str(here / "data" / "menkor_base.csv")
    df, notes = build(src, out, here / "data" / "menkor_base_couts_ajustes_15pct.csv")
    print(f"{len(df)} aircraft -> {out}")
    print("complete (fixed+variable+budget):", int(df["annual_budget_usd"].notna().sum()), "| incomplete:", int(df["annual_budget_usd"].isna().sum()))
    for n in notes:
        print(" -", n)
