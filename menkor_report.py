"""
menkor_report.py — PDF built from the SAME result dict as the screens (menkor_engine.compute).
No numbers are recalculated here: every figure comes from `res` and is formatted with `disp`.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from menkor_engine import USG_TO_L


def build_report_pdf(res: dict, disp, alerts: list, logo_bytes: bytes | None = None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader

    NAVY, GOLD, SLATE, LIGHT = HexColor("#112244"), HexColor("#C9A84C"), HexColor("#5A6B85"), HexColor("#F4F6FA")
    buf = BytesIO()
    page_w, page_h = A4
    cfg = res["config_hash"]

    def hf(canvas, doc):
        canvas.saveState()
        if logo_bytes:
            try:
                canvas.drawImage(ImageReader(BytesIO(logo_bytes)), 18 * mm, page_h - 22 * mm, width=38 * mm, height=14 * mm,
                                 preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(0.8)
        canvas.line(18 * mm, page_h - 23 * mm, page_w - 18 * mm, page_h - 23 * mm)
        canvas.line(18 * mm, 14 * mm, page_w - 18 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7); canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, f"Menkor Aviation GBL — Confidential · Config ID {cfg} · DB {res['db_version']} · Engine {res['engine_version']}")
        canvas.drawRightString(page_w - 18 * mm, 9 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=28 * mm, bottomMargin=22 * mm, leftMargin=18 * mm, rightMargin=18 * mm)
    ss = getSampleStyleSheet()
    sT = ParagraphStyle("T", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=20, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2)
    sA = ParagraphStyle("A", parent=ss["Normal"], fontName="Helvetica-Bold", fontSize=14, textColor=GOLD, alignment=TA_CENTER, spaceAfter=2)
    sS = ParagraphStyle("S", parent=ss["Normal"], fontName="Helvetica", fontSize=9, textColor=SLATE, alignment=TA_CENTER, spaceAfter=2)
    sH = ParagraphStyle("H", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=11, textColor=NAVY, spaceBefore=10, spaceAfter=5)
    sB = ParagraphStyle("B", parent=ss["Normal"], fontName="Helvetica", fontSize=8.5, textColor=NAVY, leading=11)
    sSm = ParagraphStyle("Sm", parent=ss["Normal"], fontName="Helvetica", fontSize=7.5, textColor=SLATE, leading=10)

    def P(t, st=sB): return Paragraph(escape(str(t)), st)

    def table(data, widths, header=True, bold_last=False):
        t = Table([[P(c) if not hasattr(c, "wrap") else c for c in r] for r in data], colWidths=widths, repeatRows=1 if header else 0)
        st = [("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("GRID", (0, 0), (-1, -1), 0.3, HexColor("#DDDDDD")), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if header:
            st += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
        else:
            st += [("BACKGROUND", (0, 0), (0, -1), LIGHT)]
        t.setStyle(TableStyle(st))
        return t

    def H(t):  # white header text
        return Paragraph(f'<font color="white"><b>{escape(t)}</b></font>', sB)

    m = disp.money
    hrs = res["hours"]
    mode_label = "Report reference (published totals, original assumptions)" if res["mode"] == "reference" else "Custom simulation (recalculated from the assumptions below)"
    story = [Spacer(1, 4 * mm), P("AVIATION COST REPORT", sT), P(res["model"], sA),
             P(f"{res.get('manufacturer') or ''} · aircraft_id {res['aircraft_id']}", sS), P(mode_label, sS),
             P(f"Generated {date.today().strftime('%d %B %Y')} · Config ID {cfg}", sS),
             HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6, spaceBefore=4)]

    # ── Assumptions ──────────────────────────────────────────────────────────
    story.append(P("1. Assumptions, units and currency", sH))
    kind = res.get("source_kind")
    kind_txt = {"pdf_acc": "Menkor reference database", "web_estimate": "Menkor reference database — partial web estimate (Guardian Jet economics + public technical summary), not a full reference record",
                "historical": "Historical sheet (totals only; detailed report to be reconstructed)"}.get(kind, str(kind))
    A = [["Mode", mode_label],
         ["Data source", kind_txt]]
    ws = res.get("web_source")
    if ws:
        A.append(["Web source / consultation", f"{ws.get('url') or 'n/a'} · consulted {ws.get('access_date') or 'n/a'} (consultation date, not validity date) · USD and US gallon assumed — to confirm"])
    act = res.get("actualisation") or {}
    if act.get("applied"):
        for it in act["items"]:
            if it["before"] is None:
                A.append(["Base update — " + it["item"], it["note"]])
            else:
                A.append(["Base update — " + it["item"], f"{m(it['before'])} → {m(it['after'])}" + (f" (+{it['pct']:g}%)" if it.get("pct") else "") + (f" — {it['note']}" if it.get("note") else "")])
        A.append(["Base update — scope", "Menkor update of 3-4 year old base costs; fuel, insurance, crew salaries/expenses, catering, crew travel and misc are not adjusted. User edits replace the updated values."])
    else:
        A.append(["Base update", "Not applied (raw Menkor reference values)"])
    A.append(["Currency", disp.note()])
    if res["mode"] == "reference":
        A.append(["Hours", f"{hrs['reference']:g} h/year — the report's own reference hours"])
    else:
        A.append(["Hours flown (total)", f"{hrs['flown']:g} h/year"])
        if not res.get("historical"):
            A.append(["  of which billed / positioning / other", f"{hrs['billed']:g} / {hrs['positioning']:g} / {hrs['other']:g} h"])
        A.append(["Report reference hours", f"{hrs['reference']:g} h/year" if hrs.get("reference") else "n/a"])
    f = res.get("fuel") or {}
    if f:
        bl = f.get("burn_l_h")
        A.append(["Fuel burn (average economic assumption)",
                  (f"{bl:,.0f} L/h = {bl / USG_TO_L:,.1f} US gal/h — {f.get('burn_label', '')}" if bl else "n/a")])
        pu = f.get("price_usd_l")
        if pu is not None:
            A.append(["Fuel price", f"{pu:.4f} USD/L (= {pu * USG_TO_L:.3f} USD/US gal) — {f.get('price_label', '')}"])
        loc = f.get("local")
        if loc:
            A.append(["Local fuel entry", f"ICAO {loc['airport_icao'] or '-'} / IATA {loc['airport_iata'] or '-'} · supplier {loc['supplier'] or '-'} · "
                      f"{loc['price']} {loc['currency']}/{loc['unit']} · taxes {loc['taxes_pct']}% · fees/uplift {loc['fees_per_uplift']} · valid {loc['validity_date'] or 'not stated'}"])
        A.append(["Fuel conversions", "1 US gal = 3.785411784 L. Litres, gallons, kg and lb are never mixed."])
    sc = res["scenario"]
    ed = [k for k in sc.get("fixed_overrides", {})] + [k for k in sc.get("var_overrides_h", {})]
    A.append(["Edited components (replace the report value)", ", ".join(ed) if ed else "none"])
    if res["mode"] == "simulation":
        if res.get("rate_usd"):
            cri = res.get("charter_rate_info") or {}
            src_txt = ("custom rate entered by the user" if cri.get("source", "custom") == "custom" else
                       f"ESTIMATE from the Menkor indicative charter price file ({cri['source'].replace('estimate_', '')}) — {cri.get('basis', '')}; "
                       "a public broker listing, not a quotation, not operator net revenue; taxes, fees and positioning may be extra")
            A.append(["Charter rate", f"{m(res['rate_usd'])} per billed hour (entered {sc['charter_rate']:g} {sc['charter_rate_ccy']}) — {src_txt}"])
        A.append(["Commission / other commercial fees", f"{sc['commission_pct']:g}% of revenue / {m(sc['other_commercial_fees'])} per year"])
    story.append(table(A, [62 * mm, 112 * mm], header=False))

    # ── Cost summary ─────────────────────────────────────────────────────────
    story.append(P("2. Cost summary", sH))
    if not res["available"]:
        story.append(P("Calculation unavailable: " + " ".join(x["text"] for x in res["flags"] if x["level"] == "error"), sB))
    else:
        v, fx = res["variable"], res["fixed"]
        S = [[H("Item"), H("Amount")],
             ["Annual fixed costs (incl. crew, crew training, hangar, insurance, misc — not added again)", m(fx["annual_total"])],
             ["Variable cost per flown hour — fuel", m(v["fuel_per_h"])],
             ["Variable cost per flown hour — other (maintenance, crew misc…)", m(v["nonfuel_per_h"])],
             ["Variable cost per flown hour — total", m(v["per_h"])],
             [f"Annual variable costs ({hrs['flown']:g} h)", m(v["annual"])],
             ["TOTAL ANNUAL BUDGET (fixed + variable)", m(res["budget_usd"])],
             ["Total cost per flown hour", m(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a (zero hours)"]]
        if res["mode"] == "reference":
            S[2][1] = m(v["fuel_per_h"]) + " (published fuel ÷ ref. hours)"
        story.append(table(S, [128 * mm, 46 * mm]))
        if res.get("reconciliation"):
            rc = res["reconciliation"]
            story.append(Spacer(1, 2 * mm))
            story.append(P(f"Reconciliation: at the report's own hours and fuel price the formula gives {m(rc['simulated_at_report_conditions'])} versus the published {m(rc['published_budget'])} "
                           f"({rc['difference_pct']:+.2f}%). {rc['note']}", sSm))
        rows = [[H("Component"), H("Annual"), H("Share")]]
        for c in res["components"]:
            if abs(c["annual_usd"]) < 0.5 and c.get("rounding"):
                continue
            rows.append([c["label"] + (" (edited)" if c.get("edited") and not c.get("rounding") else ""), m(c["annual_usd"]),
                         f"{c['share_pct']:.1f}%" if c.get("share_pct") is not None else ""])
        story.append(Spacer(1, 3 * mm))
        story.append(table(rows, [112 * mm, 36 * mm, 26 * mm]))

    # ── Profitability ────────────────────────────────────────────────────────
    pr = res.get("profit")
    if pr:
        story.append(P("3. Charter profitability (estimated operating result)", sH))
        if not pr.get("available"):
            story.append(P("Not calculated: " + " ".join(pr.get("messages", [])), sB))
        else:
            R = [[H("Item"), H("Amount")],
                 [f"Charter revenue ({pr['billed_hours']:g} billed h × {m(pr['rate_usd'])})", m(pr["revenue"])],
                 [f"Commission ({pr['commission_pct']:g}%)", m(-pr["commission"])],
                 ["Other commercial fees (not included in the report)", m(-pr["other_fees"])],
                 [f"Variable costs of ALL flown hours ({pr['flown_hours']:g} h incl. {pr['positioning_hours']:g} h positioning)", m(-pr["variable_cost_all_flown"])],
                 ["Fixed costs", m(-pr["fixed_cost"])],
                 ["ESTIMATED OPERATING RESULT (before financing, depreciation and tax)", m(pr["operating_result"])]]
            story.append(table(R, [128 * mm, 46 * mm]))
            story.append(Spacer(1, 2 * mm))
            story.append(P(f"Break-even: {pr['break_even_message']}", sB))
            story.append(P("Assumptions: " + pr["break_even_assumptions"], sSm))
            story.append(P("This is not a net profit: financing, depreciation and taxes are excluded.", sSm))

    # ── Alerts and limits ────────────────────────────────────────────────────
    story.append(P("4. Data alerts and limits", sH))
    items = [x["text"] for x in res["flags"]] + [a["text"] for a in alerts]
    items += ["Seats-occupied range (seats_full_range) is not the manufacturer's maximum range; ferry range is reported separately.",
              "The fuel burn is an average economic assumption, not a flight-planning calculation.",
              "No real-time fuel price is used: prices are the report's reference price or a manual entry.",
              "Figures are for simulation purposes only. The source database's commercial redistribution rights must be verified before publication."]
    for t in items:
        story.append(P("• " + t, sSm))
    doc.build(story, onFirstPage=hf, onLaterPages=hf)
    buf.seek(0)
    return buf.getvalue()
