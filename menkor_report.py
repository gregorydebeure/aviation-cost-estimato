"""
menkor_report.py — PDF built from the SAME result dict as the screens (menkor_engine.compute).
No number is recalculated here: every figure comes from `res` and is only formatted with `disp`.

Layout: page 1 = readable summary (aircraft, mode, hours, currency, budget, cost per hour, operating result) + material
assumptions and warnings; then cost tables; technical checks, field names, tolerances and reconciliation are in the Annex.
Typography: Liberation Sans (OFL) is embedded when the font files are found, otherwise Helvetica is used. No tracking/character
spacing is applied to body text.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from menkor_engine import USG_TO_L, current_date, BUSINESS_TZ_NAME, adjustment_text

_HERE = Path(__file__).resolve().parent
_FONT_FILES = {"MenkorSans": "LiberationSans-Regular.ttf", "MenkorSans-Bold": "LiberationSans-Bold.ttf", "MenkorSans-Italic": "LiberationSans-Italic.ttf"}


def _register_fonts():
    """Embed Liberation Sans (looked up in fonts/ then next to this file: GitHub web upload may flatten folders). Returns (regular, bold, italic) names."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    try:
        for name, fn in _FONT_FILES.items():
            path = next((p for p in (_HERE / "fonts" / fn, _HERE / fn) if p.exists()), None)
            if path is None:
                raise FileNotFoundError(fn)
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
        pdfmetrics.registerFontFamily("MenkorSans", normal="MenkorSans", bold="MenkorSans-Bold", italic="MenkorSans-Italic", boldItalic="MenkorSans-Bold")
        return "MenkorSans", "MenkorSans-Bold", "MenkorSans-Italic"
    except Exception:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique"


def fmt_pct(x, d=1, sign=False):
    """Percentage without '-0.0%': values that round to zero are shown as 0.0%."""
    if x is None:
        return "n/a"
    r = round(float(x), d)
    if r == 0:
        r = 0.0
    return f"{r:+,.{d}f}%" if sign and r > 0 else f"{r:,.{d}f}%"


def build_report_pdf(res: dict, disp, alerts: list, logo_bytes: bytes | None = None, generated_on=None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, PageBreak, CondPageBreak)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as _canvas

    FR, FB, FI = _register_fonts()
    NAVY, GOLD, SLATE, LIGHT = HexColor("#112244"), HexColor("#C9A84C"), HexColor("#4A5A75"), HexColor("#F4F6FA")
    WARN_BG, WARN_LN = HexColor("#FFF7E0"), HexColor("#C9A84C")
    buf = BytesIO()
    page_w, page_h = A4
    cfg = res["config_hash"]
    gen = generated_on or current_date()
    gen_txt = gen.strftime("%d %B %Y")

    class NumberedCanvas(_canvas.Canvas):
        def __init__(self, *a, **k):
            k["initialFontName"] = FR; k["initialFontSize"] = 8     # no unembedded default font in the file
            super().__init__(*a, **k); self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__)); self._startPage()

        def save(self):
            n = len(self._saved)
            for st_ in self._saved:
                self.__dict__.update(st_)
                self.setFont(FR, 7.5); self.setFillColor(SLATE)
                self.drawRightString(page_w - 18 * mm, 9 * mm, f"Page {self._pageNumber} / {n}")
                super().showPage()
            super().save()

    def hf(canvas, doc):
        canvas.saveState()
        if logo_bytes:
            try:
                canvas.drawImage(ImageReader(BytesIO(logo_bytes)), 18 * mm, page_h - 22 * mm, width=40 * mm, height=18 * mm, preserveAspectRatio=True, anchor="sw", mask="auto")
            except Exception:
                pass
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(0.8)
        canvas.line(18 * mm, page_h - 23 * mm, page_w - 18 * mm, page_h - 23 * mm)
        canvas.line(18 * mm, 14 * mm, page_w - 18 * mm, 14 * mm)
        canvas.setFont(FR, 7.5); canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, f"Menkor Aviation GBL — Confidential · Config ID {cfg} · Generated {gen_txt} · DB {res['db_version']} · Engine {res['engine_version']}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=28 * mm, bottomMargin=20 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
                            title=f"Aviation Cost Report — {res['model']}", author="Menkor Aviation GBL")
    sT = ParagraphStyle("T", fontName=FB, fontSize=21, leading=25, textColor=NAVY, alignment=TA_CENTER, spaceAfter=2)
    sA = ParagraphStyle("A", fontName=FB, fontSize=14, leading=18, textColor=GOLD, alignment=TA_CENTER, spaceAfter=2)
    sS = ParagraphStyle("S", fontName=FR, fontSize=9, leading=12, textColor=SLATE, alignment=TA_CENTER, spaceAfter=1)
    sH = ParagraphStyle("H", fontName=FB, fontSize=11.5, leading=15, textColor=NAVY, spaceBefore=10, spaceAfter=5, keepWithNext=1)
    sB = ParagraphStyle("B", fontName=FR, fontSize=8.8, leading=11.5, textColor=NAVY)
    sBr = ParagraphStyle("Br", parent=sB, alignment=TA_RIGHT)
    sSm = ParagraphStyle("Sm", fontName=FR, fontSize=7.8, leading=10.2, textColor=SLATE)
    sW = ParagraphStyle("W", parent=sB, fontSize=8.5, leading=11)
    sKL = ParagraphStyle("KL", fontName=FR, fontSize=8, leading=10, textColor=SLATE)
    sKV = ParagraphStyle("KV", fontName=FB, fontSize=13.5, leading=16, textColor=NAVY)
    sWh = ParagraphStyle("Wh", parent=sB, textColor=HexColor("#FFFFFF"), fontName=FB)
    sWhr = ParagraphStyle("Whr", parent=sWh, alignment=TA_RIGHT)

    def P(t, st=sB): return Paragraph(escape(str(t)), st)

    def M(usd, d=0):
        """Money in the display currency; never a raw float; negative as '−$ 1,234'; zero never signed."""
        if usd is None:
            return "n/a"
        v = disp.conv(usd)
        r = round(v, d)
        if r == 0:
            r = 0.0
        return f"{'−' if r < 0 else ''}{disp.sym} {abs(r):,.{d}f}"

    def grid(data, widths, header=True, right_cols=(1,), bold_rows=(), zebra=True):
        rows = []
        for i, r in enumerate(data):
            cells = []
            for j, c in enumerate(r):
                if hasattr(c, "wrap"):
                    cells.append(c); continue
                if header and i == 0:
                    cells.append(Paragraph(f"<b>{escape(str(c))}</b>", sWhr if j in right_cols else sWh))
                else:
                    t = f"<b>{escape(str(c))}</b>" if i in bold_rows else escape(str(c))
                    cells.append(Paragraph(t, sBr if j in right_cols else sB))
            rows.append(cells)
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        st = [("FONTNAME", (0, 0), (-1, -1), FR), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, HexColor("#D5DAE3")),
              ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if header:
            st.append(("BACKGROUND", (0, 0), (-1, 0), NAVY))
            if zebra:
                for i in range(2, len(rows), 2): st.append(("BACKGROUND", (0, i), (-1, i), LIGHT))
        else:
            st.append(("BACKGROUND", (0, 0), (0, -1), LIGHT))
        for i in bold_rows:
            st.append(("LINEABOVE", (0, i), (-1, i), 0.9, GOLD))
        t.setStyle(TableStyle(st))
        return t

    def section(title, *flow):
        """Heading + content kept together: a table never starts alone at the bottom of a page."""
        return KeepTogether([Paragraph(escape(title), sH), *flow])

    hrs = res["hours"]
    mfr = res.get("manufacturer")
    mfr = "" if (mfr is None or str(mfr).strip().lower() in ("", "nan", "none")) else str(mfr)
    is_ref = res["mode"] == "reference"
    mode_label = "Report reference — original published values" if is_ref else "Custom simulation — recalculated from the assumptions"
    kind = res.get("source_kind")
    pr = res.get("profit")
    fv = res.get("fuel_validity")
    act = res.get("actualisation") or {}
    dts = res.get("dates") or {}
    fuel = res.get("fuel") or {}

    # ── Material assumptions / warnings (page 1) ────────────────────────────────
    W = []
    if kind == "web_estimate":
        W.append("Partial data: web estimate (not a full reference record). Fixed costs are not equivalent to the full Menkor reference records; operator validation advised.")
    if kind == "historical":
        W.append("Historical sheet: totals only, currency not documented (treated as USD, unverified), fuel not separable.")
    W.append(f"Economic reference date of the figures: {dts.get('economic_reference_date', 'unknown')}. Consultation date and extraction date are processing dates, not validity dates.")
    if is_ref:
        W.append("Report reference: original published values, hours and fuel price of the report. No Menkor adjustment and no user edit are applied.")
    elif act.get("applied"):
        W.append(act.get("text") or adjustment_text(act["inflation_pct"]))
        if act.get("delta_total") is not None:
            W.append(f"Adjustment impact on the published basis: {M(act['published_budget_original'])} original budget, {'+' if act['delta_total'] >= 0 else '−'} {M(abs(act['delta_total']))} = {M(act['published_budget_adjusted'])}.")
    else:
        W.append("No Menkor adjustment applied: original reference values are used.")
    if fv:
        if fv["status"] == "expired":
            W.append(f"Fuel price EXPIRED: valid until {fv['date']}, checked {fv['today']} ({BUSINESS_TZ_NAME}). "
                     + ("Used as a HISTORICAL assumption after explicit user confirmation — not a current market price." if fv.get("confirmed") else "Not confirmed: the price is not used."))
        elif fv["status"] == "unknown":
            W.append("Manual fuel price with UNKNOWN validity (no validity date): unverified assumption.")
        elif fv["status"] == "valid":
            W.append(f"Manual fuel price valid until {fv['date']} (checked {fv['today']}).")
        elif fv["status"] == "invalid":
            W.append(fv["message"])
    cri = res.get("charter_rate_info") or {}
    if not is_ref and cri.get("source", "custom") != "custom":
        W.append("Charter rate is an ESTIMATE (indicative public listing price): not a quotation and not operator net revenue; taxes, fees and positioning may be billed on top.")
    if pr is not None and pr.get("available"):
        W.append("Estimated operating result excludes financing, depreciation and taxes: it is not a net profit.")
    for x in res["flags"]:
        if x["level"] in ("warn", "error") and x["code"] not in ("web_source",) and not x["code"].startswith("fuel_"):
            W.append(x["text"])
    n_alerts = len([a for a in alerts if a["level"] in ("warn", "error")])
    if n_alerts:
        W.append(f"{n_alerts} further data alert(s) are listed in the Annex.")

    # ── Page 1: title + summary ──────────────────────────────────────────────────
    story = [Spacer(1, 2 * mm), P("AVIATION COST REPORT", sT), P(res["model"], sA),
             P(mfr or "Historical sheet", sS), P(mode_label, sS),
             P(f"Generated {gen_txt} · Config ID {cfg}", sS),
             HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6, spaceBefore=4)]

    cur = disp.ccy if disp.ccy == "USD" else f"EUR (source USD, 1 USD = {disp.fx.usd_to_eur:.4f} EUR, rate dated {disp.fx.rate_date})"
    if res["available"]:
        flown = hrs["flown"]
        kpis = [("Annual budget", M(res["budget_usd"])),
                ("Cost per flown hour", M(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a (zero hours)"),
                ("Flown hours / year", f"{flown:,.0f} h"),
                ("Estimated operating result", (M(pr["operating_result"]) if pr and pr.get("available") else "not calculated"))]
        if is_ref:
            kpis[3] = ("Estimated operating result", "n/a (simulation only)")
        cards = Table([[Paragraph(escape(k), sKL) for k, _ in kpis], [Paragraph(escape(v), sKV) for _, v in kpis]],
                      colWidths=[43.5 * mm] * 4)
        cards.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, GOLD), ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#D5DAE3")),
                                   ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
        story.append(cards)
        story.append(Spacer(1, 4 * mm))
        S = [["Aircraft", (f"{res['model']} ({mfr})" if mfr else res["model"])], ["Mode", mode_label],
             ["Hours", (f"{hrs['reference']:g} h/year (report reference hours)" if is_ref else
                        f"{flown:g} h flown/year" + ("" if res.get("historical") else f" ({hrs['billed']:g} billed · {hrs['positioning']:g} positioning · {hrs['other']:g} other)"))],
             ["Currency", cur], ["Annual fixed costs", M(res["fixed"]["annual_total"])],
             ["Annual variable costs", M(res["variable"]["annual"])]]
        story.append(grid(S, [48 * mm, 126 * mm], header=False, right_cols=()))
    else:
        story.append(P("Calculation unavailable: " + " ".join(x["text"] for x in res["flags"] if x["level"] == "error"), sB))

    wt = Table([[Paragraph("<b>Key assumptions and warnings</b>", sW)]] + [[Paragraph("• " + escape(t), sW)] for t in W], colWidths=[174 * mm])
    wt.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, WARN_LN), ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
                            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
    story += [Spacer(1, 5 * mm), wt]

    # ── Page 2: cost tables ──────────────────────────────────────────────────────
    if res["available"]:
        story.append(PageBreak())
        v, fx = res["variable"], res["fixed"]
        Srows = [["Item", "Amount"],
                 ["Annual fixed costs (incl. crew, crew training, hangar, insurance, misc — not added again)", M(fx["annual_total"])],
                 ["Variable cost per flown hour — fuel", M(v["fuel_per_h"], 2 if v["fuel_per_h"] is not None and abs(disp.conv(v["fuel_per_h"])) < 100 else 0) + (" (published fuel ÷ ref. hours)" if is_ref else "")],
                 ["Variable cost per flown hour — other (maintenance, crew misc…)", M(v["nonfuel_per_h"])],
                 ["Variable cost per flown hour — total", M(v["per_h"])],
                 [f"Annual variable costs ({hrs['flown']:g} h)", M(v["annual"])],
                 ["TOTAL ANNUAL BUDGET (fixed + variable)", M(res["budget_usd"])],
                 ["Total cost per flown hour", M(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a (zero hours)"]]
        story.append(section("1. Cost summary", grid(Srows, [128 * mm, 46 * mm], bold_rows=(6,))))
        crow = [["Component", "Annual", "Share"]]
        for c in res["components"]:
            if c.get("rounding"):
                continue
            crow.append([c["label"] + (" (edited)" if c.get("edited") else ""), M(c["annual_usd"]), fmt_pct(c["share_pct"]) if c.get("share_pct") is not None else ""])
        story.append(section("2. Cost components (breakdown of the totals, not added to them)", grid(crow, [112 * mm, 34 * mm, 28 * mm], right_cols=(1, 2))))
        story.append(Spacer(1, 1.5 * mm))
        story.append(P("Rounding differences between printed hourly values and the published totals are listed in the Annex.", sSm))
        if pr:
            if not pr.get("available"):
                story.append(section("3. Charter profitability", P("Not calculated: " + " ".join(pr.get("messages", [])), sB)))
            else:
                R = [["Item", "Amount"],
                     [f"Charter revenue ({pr['billed_hours']:g} billed h × {M(pr['rate_usd'])})", M(pr["revenue"])],
                     [f"Commission ({pr['commission_pct']:g}%)", M(-pr["commission"])],
                     ["Other commercial fees (not included in the report)", M(-pr["other_fees"])],
                     [f"Variable costs of ALL flown hours ({pr['flown_hours']:g} h incl. {pr['positioning_hours']:g} h positioning)", M(-pr["variable_cost_all_flown"])],
                     ["Fixed costs", M(-pr["fixed_cost"])],
                     ["ESTIMATED OPERATING RESULT (before financing, depreciation and tax)", M(pr["operating_result"])]]
                cov = pr.get("coverage_pct")
                story.append(section("3. Charter profitability (estimated operating result)", grid(R, [128 * mm, 46 * mm], bold_rows=(6,)),
                                     Spacer(1, 2 * mm), P(f"Coverage: {fmt_pct(cov)} · {pr['break_even_message']}", sB),
                                     P("Assumptions: " + pr["break_even_assumptions"], sSm)))

    # ── Annex: technical details ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Annex — technical details", ParagraphStyle("AN", parent=sH, fontSize=14, spaceBefore=0, spaceAfter=6)))
    story.append(P("Technical checks, field names, tolerances and reconciliation details. The figures of the main report are not repeated here.", sSm))
    kind_txt = {"pdf_acc": "Menkor reference database", "web_estimate": "Menkor reference database — partial web estimate (Guardian Jet economics + public technical summary), not a full reference record",
                "historical": "Historical sheet (totals only; detailed report to be reconstructed)"}.get(kind, str(kind))
    A = [["Data source", kind_txt]]
    ws = res.get("web_source")
    if ws:
        A.append(["Web source", f"{ws.get('url') or 'n/a'} — consultation date {ws.get('access_date') or 'n/a'} (not a validity date) · USD and US gallon assumed — to confirm"])
    A.append(["Dates (never mixed)", f"economic reference date: {dts.get('economic_reference_date', 'unknown')} · web consultation date: {dts.get('consultation_date') or 'n/a'} · database extraction date: {dts.get('extraction_date') or 'n/a'}"])
    if act.get("applied"):
        A.append(["Menkor adjustment", act.get("text", "")])
        for it in act["items"]:
            if it["before"] is None:
                A.append(["  · " + it["item"], it["note"]])
            else:
                A.append(["  · " + it["item"], f"{M(it['before'])} → {M(it['after'])} ({M(it['delta'])})" + (f" (+{it['pct']:g}%)" if it.get("pct") else "") + (f" — {it['note']}" if it.get("note") else "")])
        A.append(["  · scope", "Fuel, insurance, crew salaries/expenses, catering, crew travel and misc are not adjusted. User edits replace the adjusted values."])
    else:
        A.append(["Menkor adjustment", "Not applied (original reference values)"])
    A.append(["Currency", disp.note()])
    sc = res["scenario"]
    if is_ref:
        A.append(["Hours", f"{hrs['reference']:g} h/year — the report's own reference hours"])
        A.append(["Edited components", "not applicable in Report reference"])
    else:
        A.append(["Hours flown (total)", f"{hrs['flown']:g} h/year" + ("" if res.get("historical") else f" ({hrs['billed']:g} billed / {hrs['positioning']:g} positioning / {hrs['other']:g} other)")])
        A.append(["Report reference hours", f"{hrs['reference']:g} h/year" if hrs.get("reference") else "n/a"])
        ed = list(sc.get("fixed_overrides", {})) + list(sc.get("var_overrides_h", {}))
        A.append(["Edited components (replace the report value)", ", ".join(ed) if ed else "none"])
    if fuel:
        bl = fuel.get("burn_l_h")
        A.append(["Fuel burn (average economic assumption)", (f"{bl:,.0f} L/h = {bl / USG_TO_L:,.1f} US gal/h — {fuel.get('burn_label', '')}" if bl else "n/a")])
        pu = fuel.get("price_usd_l")
        if pu is not None:
            A.append(["Fuel price", f"{pu:.4f} USD/L (= {pu * USG_TO_L:.3f} USD/US gal) — {fuel.get('price_label', '')}"])
        loc = fuel.get("local")
        if loc:
            A.append(["Local fuel entry", f"ICAO {loc['airport_icao'] or '-'} / IATA {loc['airport_iata'] or '-'} · supplier {loc['supplier'] or '-'} · "
                      f"{loc['price']} {loc['currency']}/{loc['unit']} · taxes {loc['taxes_pct']}% · fees/uplift {loc['fees_per_uplift']}"])
        A.append(["Fuel conversions", "1 US gal = 3.785411784 L. Litres, gallons, kg and lb are never mixed."])
    if fv:
        A.append(["Fuel price validity", f"status {fv['status']} · validity date {fv.get('date') or 'none'} · checked {fv['today']} ({fv['tz']})"
                  + (f" · expired price confirmed as historical: {'yes' if fv.get('confirmed') else 'no'}" if fv["status"] == "expired" else "")])
    if not is_ref:
        if res.get("rate_usd"):
            src_txt = ("custom rate entered by the user" if cri.get("source", "custom") == "custom" else
                       f"ESTIMATE from the Menkor indicative charter price file ({cri['source'].replace('estimate_', '')}) — {cri.get('basis', '')}; "
                       "a public broker listing, not a quotation, not operator net revenue; taxes, fees and positioning may be extra")
            A.append(["Charter rate", f"{M(res['rate_usd'])} per billed hour (entered {sc['charter_rate']:g} {sc['charter_rate_ccy']}) — {src_txt}"])
        A.append(["Commission / other commercial fees", f"{sc['commission_pct']:g}% of revenue / {M(sc['other_commercial_fees'])} per year"])
    A += [["Identification", f"aircraft_id {res['aircraft_id']} · mode {res['mode']} · Config ID {cfg} · DB {res['db_version']} · Engine {res['engine_version']}"],
          ["Generated", f"{gen_txt} ({BUSINESS_TZ_NAME})"]]
    story.append(section("A. Scenario and assumptions", grid(A, [50 * mm, 124 * mm], header=False, right_cols=())))

    B = []
    if res.get("reconciliation"):
        rc = res["reconciliation"]
        txt = (f"Published basis {M(rc['published_budget'])}" + (f" (= original {M(rc['original_published_budget'])} + adjustment {M(rc['adjustment_delta'])})" if rc.get("adjustment_delta") else "")
               + f" · simulation recalculated at the report's own hours and fuel price {M(rc['simulated_at_report_conditions'])} · difference {M(rc['difference'])} ({fmt_pct(rc['difference_pct'], 2)}). {rc['note']}")
        B.append(["Reconciliation", txt])
    rr = [c for c in res["components"] if c.get("rounding") and abs(c["annual_usd"]) >= 0.5]
    for c in rr:
        B.append([c["label"], M(c["annual_usd"])])
    if B:
        story.append(section("B. Reconciliation and rounding", grid(B, [50 * mm, 124 * mm], header=False, right_cols=())))

    items = [x["text"] for x in res["flags"]] + [a["text"] for a in alerts]
    items += ["Seats-occupied range (seats_full_range) is not the manufacturer's maximum range; ferry range is reported separately.",
              "The fuel burn is an average economic assumption, not a flight-planning calculation.",
              "No real-time fuel price is used: prices are the report's reference price or a manual entry.",
              "Figures are for simulation purposes only. The source database's commercial redistribution rights must be verified before publication."]
    story.append(section("C. Data alerts and limits", *[P("• " + t, sSm) for t in items[:1]]))
    for t in items[1:]:
        story.append(P("• " + t, sSm))
    doc.build(story, onFirstPage=hf, onLaterPages=hf, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.getvalue()
