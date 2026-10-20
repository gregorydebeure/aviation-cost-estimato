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

from menkor_engine import (USG_TO_L, current_date, BUSINESS_TZ_NAME, AVERAGE_PRICE_LABEL, THRESHOLD_LABEL, THRESHOLD_LABEL_FR, THRESHOLD_NOTE, THRESHOLD_ECON_LABEL, THRESHOLD_ECON_LABEL_FR, OWNERSHIP_NOTE, MANAGEMENT_STATUS)

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


TEMPLATE_VERSION = "2.0"      # bump when the layout/content of the client report changes: the app invalidates PDFs built with another version


def build_report_pdf(res: dict, disp, alerts: list, logo_bytes: bytes | None = None, generated_on=None, study_url: str | None = None, broker: dict | None = None) -> bytes:
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

    broker = broker or {}
    broker_name = (broker.get("name") or "").strip()
    broker_logo = broker.get("logo")

    def hf(canvas, doc):
        canvas.saveState()
        if broker_logo:     # the broker's own logo sits on the right; the Menkor logo and the confidentiality line stay
            try:
                canvas.drawImage(ImageReader(BytesIO(broker_logo)), page_w - 18 * mm - 40 * mm, page_h - 22 * mm, width=40 * mm, height=18 * mm, preserveAspectRatio=True, anchor="se", mask="auto")
            except Exception:
                pass
        if logo_bytes:
            try:
                canvas.drawImage(ImageReader(BytesIO(logo_bytes)), 18 * mm, page_h - 22 * mm, width=40 * mm, height=18 * mm, preserveAspectRatio=True, anchor="sw", mask="auto")
            except Exception:
                pass
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(0.8)
        canvas.line(18 * mm, page_h - 23 * mm, page_w - 18 * mm, page_h - 23 * mm)
        canvas.line(18 * mm, 14 * mm, page_w - 18 * mm, 14 * mm)
        canvas.setFont(FR, 7.5); canvas.setFillColor(SLATE)
        canvas.drawString(18 * mm, 9 * mm, f"Menkor Aviation GBL — Confidential · Scenario ref. {cfg} · Template v{TEMPLATE_VERSION} · Generated {gen_txt}")
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
    sBd = ParagraphStyle("Bd", parent=sB, fontName=FB)
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

    def grid(data, widths, header=True, right_cols=(1,), bold_rows=(), zebra=True, pad=3.2):
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
              ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
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
    act = res.get("menkor_base") or {}
    dts = res.get("dates") or {}
    fuel = res.get("fuel") or {}

    # ── Assumptions: essential ones on page 1, the rest in the annex ───────────────
    sc = res.get("scope")
    Wm, Wx = [], []
    if kind == "web_estimate":
        Wm.append("Partial data: web estimate (not a full reference record). Fixed costs are not equivalent to the full Menkor reference records; operator validation advised.")
    if kind == "historical":
        Wm.append("Historical sheet: totals only, currency not documented (treated as USD, unverified), fuel not separable.")
    _erd = dts.get("economic_reference_date")
    Wm.append(f"Economic reference date of the figures: {_erd}." if _erd and str(_erd).lower() != "unknown" else "Economic reference date not documented: the cost figures carry no validity date.")
    if is_ref:
        Wm.append("Report reference: original published values, hours and fuel price of the report. The Menkor cost-base adjustment and user edits are not used.")
    elif act.get("applied"):
        Wm.append(f"Menkor cost base: selected cost lines include a {act.get('pct', 0):+g}% Menkor adjustment on the original values (details in the annex).")
        Wx.append(act.get("text") or "Menkor cost base: selected costs include a Menkor adjustment applied to the original published values.")
        if act.get("delta_total") is not None:
            Wx.append(f"Menkor cost base on the published basis: {M(act['published_budget_original'])} original budget {'+' if act['delta_total'] >= 0 else '−'} {M(abs(act['delta_total']))} = {M(act['published_budget_adjusted'])}.")
    else:
        Wm.append("Menkor cost base: no adjustment for this record (original published values).")
    avg = fuel.get("average")
    if avg and avg.get("price"):
        Wm.append(f"Fuel: average annual price of {avg['currency']} {avg['price']:,.3f} per litre entered by the user, taxes and fees included according to the operating habits. "
                  "A user hypothesis, not a verified local price and not a real-time price.")
    bm = fuel.get("benchmark")
    if bm:
        Wm.append(f"Fuel: regional market benchmark, {bm['region']} ({bm['period_label']}): {bm['benchmark_usd_l']:.3f} USD/L — a weekly refinery reference, not a delivered price.")
        Wx.append(bm["disclaimer"])
        if bm["user_adjusted"]:
            Wm.append(f"{bm['adjusted_text']} Price used: {bm['used_usd_l']:.3f} USD/L (user hypothesis).")
    if fv:
        if fv["status"] == "expired":
            Wm.append(f"Fuel price EXPIRED: valid until {fv['date']}, checked {fv['today']} ({BUSINESS_TZ_NAME}). "
                      + ("Used as a HISTORICAL assumption after explicit user confirmation — not a current market price." if fv.get("confirmed") else "Not confirmed: the price is not used."))
        elif fv["status"] == "unknown":
            Wm.append("Manual fuel price with UNKNOWN validity (no validity date): unverified assumption.")
        elif fv["status"] == "valid":
            Wm.append(f"Manual fuel price valid until {fv['date']} (checked {fv['today']}).")
        elif fv["status"] == "invalid":
            Wm.append(fv["message"])
    has_charter = (not is_ref) and pr is not None and pr.get("available")
    if has_charter:
        Wm.append("Charter revenue is the figure entered by the user ("
                  + ("already net of commission, no commission deducted" if pr["rate_basis"] == "net" else f"before commission, {pr['commission_pct']:g}% deducted once")
                  + "). Billed supplements are kept separate from the hourly revenue.")
    elif not is_ref:
        Wm.append("Cost report only: no charter revenue was entered, so no revenue, operating result or coverage threshold is shown.")
    if not is_ref:
        _mg = res.get("management") or {}
        _fee = (_mg.get("management") or {})
        if _fee.get("status") == "added":
            Wm.append(f"Management fee entered: {M(_fee['amount_usd'])} per year, added once to the fixed costs. Management fees are not included in the reference costs.")
        elif not (sc and any("Management fees excluded" in t for t in sc.get("exclusions", []))):
            Wm.append("Management fees excluded. Management fees are not included in the reference costs.")
        _act = [f"{v['label']} {M(v['amount_usd'])} per year" for k, v in _mg.items() if k != "management" and v.get("status") == "added"]
        _cc = [c for c in res["components"] if c["key"] == "cycle_cost"]
        if _cc:
            _act.append(f"additional cost per landing ({M(_cc[0]['hourly_usd'])} per flown hour)")
        if _act:
            Wm.append("Advanced adjustments active: " + "; ".join(_act) + ".")
    _fl = [x["text"] for x in res["flags"] if x["level"] in ("warn", "error") and x["code"] not in ("web_source",) and not x["code"].startswith("fuel_")]
    Wm += _fl[:3]; Wx += _fl[3:]
    n_alerts = len([a for a in alerts if a["level"] in ("warn", "error")])
    if n_alerts:
        Wm.append(f"{n_alerts} further data alert(s) are listed in the annex.")

    # ── Page 1: title + cost summary + results + essential assumptions + main exclusions ──
    story = [Spacer(1, 2 * mm), P("AVIATION COST REPORT", sT), P(res["model"], sA),
             P(mfr or "Historical sheet", sS), P(mode_label, sS),
             P(f"Generated {gen_txt} · Scenario reference {cfg} · Template v{TEMPLATE_VERSION}", sS)] \
            + ([P(f"Prepared by {broker_name} · calculated with the Menkor Aviation Cost Estimator", sS)] if broker_name else []) \
            + [HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=6, spaceBefore=4)]

    cur = disp.ccy if disp.ccy == "USD" else f"EUR (source USD, 1 USD = {disp.fx.usd_to_eur:.4f} EUR, rate dated {disp.fx.rate_date})"
    own = (pr or {}).get("ownership") or {}
    econ_ok = bool(has_charter and pr.get("economic_result") is not None)
    econ_partial = bool(has_charter and not econ_ok and own.get("missing") is not None and len(own["missing"]) < 2)
    if res["available"]:
        flown = hrs["flown"]
        kpis = [("Annual budget", M(res["budget_usd"])),
                ("Cost per flown hour", M(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a (zero hours)"),
                ("Flown hours / year", f"{flown:,.0f} h")]
        if has_charter:
            kpis.append(("Operating result", M(pr["operating_result"])))
            if econ_ok:
                kpis.append(("Economic result", M(pr["economic_result"])))
            elif econ_partial:
                kpis.append(("Economic result", "not complete"))
        cw = 174 * mm / len(kpis)
        cards = Table([[Paragraph(escape(k), sKL) for k, _ in kpis], [Paragraph(escape(v), sKV) for _, v in kpis]], colWidths=[cw] * len(kpis))
        cards.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, GOLD), ("INNERGRID", (0, 0), (-1, -1), 0.3, HexColor("#D5DAE3")),
                                   ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                   ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 7)]))
        story.append(cards)
        story.append(Spacer(1, 1.5 * mm))
        if has_charter:
            story.append(P("Operating result: before depreciation, interest and tax. It is not a net profit.", sSm))
            if econ_ok:
                story.append(P("Economic result: operating result minus the economic depreciation and loan interest entered. It is an economic view, not cash flow: capital repayment is not an economic cost but is a separate cash outflow.", sSm))
            elif econ_partial:
                story.append(P("Economic result not complete: missing " + " and ".join(own["missing"]) + ". Enter the amount, or 0 to state an explicit zero.", sSm))
        story.append(Spacer(1, 3 * mm))
        S = [["Aircraft", (f"{res['model']} ({mfr})" if mfr else res["model"])], ["Mode", mode_label],
             ["Hours", (f"{hrs['reference']:g} h/year (report reference hours)" if is_ref else
                        f"{flown:g} h flown/year" + ("" if res.get("historical") else (f" ({hrs['billed']:g} billed · {hrs['positioning']:g} positioning · {hrs['other']:g} other)" if has_charter else " (all hours flown, no charter revenue assumed)")))],
             ["Currency", cur], ["Annual fixed costs", M(res["fixed"]["annual_total"])],
             ["Annual variable costs", M(res["variable"]["annual"])]]
        story.append(grid(S, [48 * mm, 126 * mm], header=False, right_cols=()))
    else:
        story.append(P("Calculation unavailable: " + " ".join(x["text"] for x in res["flags"] if x["level"] == "error"), sB))

    wt = Table([[Paragraph("<b>Essential assumptions</b>", sW)]] + [[Paragraph("• " + escape(t), sW)] for t in Wm], colWidths=[174 * mm])
    wt.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, WARN_LN), ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
                            ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
    story += [Spacer(1, 4 * mm), wt]
    if sc and sc.get("exclusions"):
        ex = [t for t in sc["exclusions"]][:4]
        xt = Table([[Paragraph("<b>Main exclusions</b>", sW)]] + [[Paragraph("• " + escape(t), sW)] for t in ex]
                   + ([[Paragraph(escape(f"{len(sc['exclusions']) - 4} further exclusion(s) and the full list of costs included are in the annex."), sSm)]] if len(sc["exclusions"]) > 4 else [])
                   + [[Paragraph(escape(THRESHOLD_NOTE), sSm)]] if has_charter else
                   [[Paragraph("<b>Main exclusions</b>", sW)]] + [[Paragraph("• " + escape(t), sW)] for t in ex], colWidths=[174 * mm])
        xt.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, HexColor("#C5CCD9")), ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
                                ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5), ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
        story += [Spacer(1, 3 * mm), xt]

    # ── Page 2: breakdown, available scenarios, link to the custom study ────────────
    if res["available"]:
        story.append(PageBreak())
        v, fx = res["variable"], res["fixed"]
        crow = [["Component", "Annual", "Share"]]
        for c in res["components"]:
            if c.get("rounding"):
                continue
            crow.append([c["label"] + (" (edited)" if c.get("edited") else ""), M(c["annual_usd"]), fmt_pct(c["share_pct"]) if c.get("share_pct") is not None else ""])
        crow.append(["TOTAL ANNUAL BUDGET (fixed + variable)", M(res["budget_usd"]), "100.0%"])
        story.append(section("1. Detailed cost breakdown", grid(crow, [112 * mm, 34 * mm, 28 * mm], right_cols=(1, 2), bold_rows=(len(crow) - 1,), pad=2.1), P("Components break down the totals; they are not added to them.", sSm)))
        Srows = [["Per flown hour", "Amount"],
                 ["Fuel", M(v["fuel_per_h"], 2 if v["fuel_per_h"] is not None and abs(disp.conv(v["fuel_per_h"])) < 100 else 0)],
                 ["Other variable costs (maintenance, crew misc…)", M(v["nonfuel_per_h"])],
                 ["Total variable cost per flown hour", M(v["per_h"])]]
        if fuel.get("burn_l_h") and fuel.get("price_usd_l"):
            Srows.insert(1, [f"Fuel retained: {fuel['burn_l_h']:,.0f} L per flown hour × {M(fuel['price_usd_l'], 3)} per litre", ""])
        story += [Spacer(1, 2 * mm), grid(Srows, [128 * mm, 46 * mm], pad=2.1)]
        if has_charter:
            supp_r = pr.get("supplements_retained"); supp_c = pr.get("supplements_cost")
            R = [["Charter scenario", "Amount"],
                 [f"Charter revenue ({pr['billed_hours']:g} billed h × {M(pr['rate_usd'])}, " + ("rate already net)" if pr["rate_basis"] == "net" else "rate before commission)"), M(pr["revenue"])],
                 [("Commission (not applied: rate already net)" if pr["rate_basis"] == "net" else f"Commission ({pr['commission_pct']:g}%, deducted once)"), M(-pr["commission"])],
                 ["Other commercial fees (not included in the report)", M(-pr["other_fees"])]]
            if supp_r is not None or supp_c is not None:
                R += [["Billed supplements retained by the operator (separate)", M(supp_r) if supp_r is not None else "not entered"],
                      ["Cost linked to billed supplements (separate)", M(-supp_c) if supp_c is not None else "not entered"]]
            R += [[f"Variable costs of all flown hours ({pr['flown_hours']:g} h)", M(-pr["variable_cost_all_flown"])],
                  ["Fixed costs", M(-pr["fixed_cost"])],
                  ["OPERATING RESULT (before depreciation, interest and tax)", M(pr["operating_result"])]]
            bold = [len(R) - 1]
            if econ_ok:
                R += [["Economic ownership costs entered (depreciation + interest)", M(-pr["ownership_costs_total"])], ["ECONOMIC RESULT (not cash flow)", M(pr["economic_result"])]]
                bold.append(len(R) - 1)
            R += [["Owner remaining balance after charter contribution (negative = surplus)", M(pr["owner_remaining_cost"])]]
            story += [Spacer(1, 2 * mm), section("2. Charter scenario", grid(R, [128 * mm, 46 * mm], bold_rows=tuple(bold), pad=2.1))]
            th = pr.get("threshold") or {}
            lines = []
            if th.get("status") in ("ok", "exceeds_year"):
                lines.append(P(f"{th['message']} ({THRESHOLD_LABEL_FR})", sBd))
            elif th.get("status") == "unattainable":
                lines.append(P(f"{THRESHOLD_LABEL}: {th['message']}", sBd))
            else:
                lines.append(P(f"{THRESHOLD_LABEL}: not displayed — " + (th.get("message") or "the assumptions were not confirmed when the report was generated."), sBd))
            te = pr.get("threshold_economic") or {}
            if th.get("status") not in ("awaiting_confirmation", "ratio_undefined") and te:
                lines.append(P((f"{te['message']} ({THRESHOLD_ECON_LABEL_FR})" if te.get("status") in ("ok", "exceeds_year") else f"{THRESHOLD_ECON_LABEL}: {te.get('message', '')}"), sBd))
            lines.append(P(THRESHOLD_NOTE, sSm))
            story += [Spacer(1, 2 * mm)] + lines
        # custom study: the link is the configured destination only (never invented)
        _link = (f'<link href="{escape(study_url)}" color="#1A3A6E"><u>{escape(study_url)}</u></link>' if study_url
                 else "Open the Aviation Cost Estimator and choose “Request an aircraft-specific budget”.")
        bx = Table([[Paragraph("<b>Need a budget for a specific aircraft?</b>", sW)],
                    [Paragraph("These figures use average costs for the model, not the budget of one aircraft. A manually prepared budget based on serial number, programme coverage, upcoming maintenance and your intended operation is available from Menkor Aviation.", sW)],
                    [Paragraph(_link, sW)]], colWidths=[174 * mm])
        bx.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FR), ("BOX", (0, 0), (-1, -1), 0.8, GOLD), ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                                ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7)]))
        story += [Spacer(1, 3 * mm), KeepTogether([bx])]
        if sc:
            story.append(PageBreak())
            scp = [P("Included in the simulation", sBd)]
            scp += [P("• " + c["label"] + (f" — {M(c['annual_usd'])} per year" if c.get("annual_usd") is not None else ""), sSm) for c in sc["included"]]
            scp += [P("Not confirmed (unknown is never shown as zero)", sBd)] + [P("• " + t, sSm) for t in sc["not_confirmed"]]
            scp += [P("Known exclusions", sBd)] + [P("• " + t, sSm) for t in sc["exclusions"]]
            scp += [P("Limitations", sBd)] + [P("• " + t, sSm) for t in sc["limits"]]
            story.append(Paragraph("Annex — Costs included and limits", ParagraphStyle("AN0", parent=sH, fontSize=14, spaceBefore=0, spaceAfter=6)))
            story.extend(scp)
        if has_charter:
            supp = [P("Charter scenario details", sBd)]
            th_ = pr.get("threshold") or {}
            if th_.get("assumptions"): supp.append(P("Operating cost coverage threshold assumptions: " + th_["assumptions"], sSm))
            te_ = pr.get("threshold_economic") or {}
            if te_.get("assumptions"): supp.append(P("Economic coverage threshold assumptions: " + te_["assumptions"], sSm))
            C2 = [["External charter vs owner's own flying (kept separate)", "Amount"],
                  ["External charter contribution (net revenue + retained supplements − their cost − variable cost of billed and positioning hours)", M(pr["charter_external_contribution"])],
                  ["Owner private flying — variable cost of private/other hours", M(-pr["owner_private_variable_cost"])],
                  ["Fixed costs", M(-pr["fixed_cost"])],
                  ["Owner remaining balance after charter contribution (negative = surplus)", M(pr["owner_remaining_cost"])]]
            supp += [Spacer(1, 2 * mm), grid(C2, [128 * mm, 46 * mm], bold_rows=(4,)),
                     P("No internal payment from the owner to the operator is modelled: revenue paid by the owner to the operator for the owner's own flights is not external charter revenue and does not reduce the owner's consolidated cost.", sSm)]
            story += [Spacer(1, 4 * mm), KeepTogether(supp)]

    # ── Annex: technical details ─────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Annex — assumptions and adjustments", ParagraphStyle("AN", parent=sH, fontSize=14, spaceBefore=0, spaceAfter=6)))
    story.append(P("Assumptions, adjustments and limits behind the figures of the report. The figures themselves are not repeated here.", sSm))
    A = []
    ws = res.get("web_source")
    if ws:
        A.append(["Partial web estimate", "USD and US gallon assumed — to confirm; no validity date is documented."])
    _erd = dts.get("economic_reference_date")
    A.append(["Economic reference date", str(_erd) if _erd and str(_erd).lower() != "unknown" else "Economic reference date not documented"])
    if act.get("applied"):
        A.append(["Menkor cost base", act.get("text", "")])
        for it in act["items"]:
            if it["before"] is None:
                A.append(["  · " + it["item"], it["note"]])
            else:
                A.append(["  · " + it["item"], f"{M(it['before'])} → {M(it['after'])} ({M(it['delta'])})" + (f" ({fmt_pct(it['pct'], 1, sign=True)})" if it.get("pct") is not None else "") + (f" — {it['note']}" if it.get("note") else "")])
        A.append(["  · scope", "Fuel, insurance, crew salaries/expenses, catering, crew travel and misc are unchanged in the base. User edits replace the base values."])
    else:
        A.append(["Menkor cost base", "Not used: original published values" if is_ref else "No adjustment for this record (original published values)"])
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
            A.append(["Average fuel price (user hypothesis)" if avg else "Fuel price",
                      f"{pu:.4f} USD/L (= {pu * USG_TO_L:.3f} USD/US gal) — {fuel.get('price_label', '')}"])
        if avg and avg.get("price"):
            conv = (f" · converted at {avg['fx_rate']:g} EUR per 1 USD (rate dated {avg['fx_date']})" if avg.get("currency") == "EUR" and avg.get("fx_rate") else "")
            A.append(["Average price entered", f"{avg['currency']} {avg['price']:,.3f} per litre, taxes and fuel fees included per operating habits{conv}"])
        if bm:
            A.append(["Fuel price method", "Regional market benchmark" + (" — " + bm["adjusted_text"] if bm["user_adjusted"] else "")])
            A.append(["Main refuelling region", bm["region"]])
            A.append(["Benchmark period", f"{bm['period_label']} ({bm['period_start']} to {bm['period_end']}) — weekly regional refinery reference"])
            A.append(["Benchmark price", f"{bm['source_cents_usg']:.2f} US cents per US gallon = {bm['benchmark_usd_l']:.3f} USD/L (refinery reference)"])
            A.append(["Price used", f"{bm['used_usd_l']:.3f} USD/L — " + ("user hypothesis" if bm["user_adjusted"] else "refinery reference")])
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
            A.append(["Charter revenue per billed hour", f"{M(res['rate_usd'])} (entered {sc['charter_rate']:g} {sc['charter_rate_ccy']}) — entered by the user; no public or historical price is used; "
                      + ("already net of commission" if sc.get("rate_basis") == "net" else "before commission")])
        else:
            A.append(["Charter revenue per billed hour", "not entered — no revenue, result or threshold calculated"])
        A.append(["Commission / other commercial fees", ("not applied (rate already net)" if sc.get("rate_basis") == "net" else ("not entered" if sc.get("commission_pct") is None else f"{sc['commission_pct']:g}% of revenue"))
                  + f" / {M(sc['other_commercial_fees'])} per year"])
        A.append(["Hours assumptions", f"billed {sc['billed_hours']:g} h · positioning {sc['positioning_hours']:g} h · private/other {sc['other_hours']:g} h · "
                  f"positioning ratio {('%g' % sc['positioning_ratio']) if sc.get('positioning_ratio') is not None else 'from hours entered'} · confirmed by the user: positioning {'yes' if sc.get('positioning_confirmed') else 'no'}, "
                  f"private hours {'yes' if sc.get('private_hours_confirmed') else 'no'}, other fees {'yes' if sc.get('other_fees_confirmed') else 'no'} · costs-included review: {'yes' if sc.get('limits_reviewed') else 'no'} (not a validation of data completeness)"])
        mgs = res.get("management") or {}
        if mgs:
            A.append(["Management fee / CAMO / dispatch", " · ".join(f"{v['label']}: {MANAGEMENT_STATUS[v['status']]}" + (f" ({M(v['amount_usd'])} per year)" if v.get('amount_usd') is not None else "") for v in mgs.values())
                      + " · management fees are not included in the reference costs · not entered = nothing added (not a confirmed zero)"])
        A.append(["Additional cost per landing", ("added: cost per landing ÷ average flight duration, applied per flown hour, once" if sc.get("cycle_status") == "added" else "not enabled: nothing added")])
    A += [["Scenario reference", f"{cfg}"],
          ["Generated", f"{gen_txt} ({BUSINESS_TZ_NAME})"]]
    story.append(section("A. Scenario and assumptions", grid(A, [50 * mm, 124 * mm], header=False, right_cols=())))

    items = [x["text"] for x in res["flags"]] + [a["text"] for a in alerts]
    items = list(dict.fromkeys(items + Wx))
    items += ["The seats-occupied range is not the manufacturer's maximum range; ferry range is reported separately.",
              "The fuel burn is an average economic assumption, not a flight-planning calculation.",
              "No real-time fuel price is used: the fuel price is the report's reference price, an average price entered by the user, a weekly regional refinery benchmark (not an into-wing price) or an advanced dated local quote.",
              "Figures are for simulation purposes only."]
    story.append(section("C. Data alerts and limits", *[P("• " + t, sSm) for t in items[:1]]))
    for t in items[1:]:
        story.append(P("• " + t, sSm))
    doc.build(story, onFirstPage=hf, onLaterPages=hf, canvasmaker=NumberedCanvas)
    buf.seek(0)
    return buf.getvalue()
