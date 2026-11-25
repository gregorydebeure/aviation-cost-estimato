"""Menkor — legal documents: seller configuration, versioned texts, rendering, fingerprint, PDF.  Pure logic, no Streamlit import.

Principles
- The texts live in legal/<key>.<lang>.md with a small header (key, lang, version, status, effective, title). The seller's identity and policies are NEVER typed
  in the texts: they are placeholders ({{seller_name}}, ...) filled from configuration (secrets / environment, keys LEGAL_*). A text is published ONLY when
  every placeholder is filled and its header says `status: published` with an effective date. Nothing is invented, no provisional field is ever shown.
- Exception for tests with Stripe TEST keys only (sk_test_...): draft texts may be used so that the flow can be rehearsed. A live key never does.
- What a customer accepts is frozen at order time (menkor_orders): the rendered text, its SHA-256 and its version. Changing a text later cannot touch an old order.
- Releasing a new version: edit the text, raise `version`, add its hash to legal/MANIFEST.json (tests refuse a text that changed under the same version).
"""
from __future__ import annotations
import hashlib, io, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
LEGAL_DIR = os.path.join(HERE, "legal")
LANGS = ("fr", "en")
DOC_KEYS = ("terms", "withdrawal", "notice", "privacy", "cookies")      # terms = general terms of sale AND use, including the data and report licence (section 9)
CONTRACT_DOCS = ("terms",)                                                # the document the customer ACCEPTS; the others are made available (and their hash stored)
INFO_DOCS = ("withdrawal", "privacy")                                     # made available before payment, stored with the proof, not "accepted"

# placeholder -> configuration key (secret / environment). All REQUIRED before publication.
REQUIRED_CONFIG = {
    "seller_name": "LEGAL_SELLER_NAME",              # legal name of the selling company
    "seller_country": "LEGAL_SELLER_COUNTRY",        # country of registration
    "seller_address": "LEGAL_SELLER_ADDRESS",
    "seller_reg_number": "LEGAL_SELLER_REG_NUMBER",  # company registration number
    "seller_tax_id": "LEGAL_SELLER_TAX_ID",          # VAT / tax identifier, or the exact statement to print if there is none
    "contact_email": "LEGAL_CONTACT_EMAIL",
    "complaints_email": "LEGAL_COMPLAINTS_EMAIL",
    "markets": "LEGAL_MARKETS",                      # targeted markets (free text, printed in the terms)
    "governing_law": "LEGAL_GOVERNING_LAW",
    "courts": "LEGAL_COURTS",
    "refund_policy": "LEGAL_REFUND_POLICY",          # commercial policy: refunds
    "cancellation_policy": "LEGAL_CANCELLATION_POLICY",   # commercial policy: cancelling a subscription
    "tax_note": "LEGAL_TAX_NOTE",                    # sentence printed with prices (e.g. whether taxes are included) — must match the real invoicing set-up
    "host_details": "LEGAL_HOST_DETAILS",            # hosting provider name and address
    "retention_years": "LEGAL_RETENTION_YEARS",      # years the order / acceptance / invoice records are kept
}
TAX_MODES = ("included", "stripe_tax", "not_applicable")       # LEGAL_TAX_MODE: how amounts relate to taxes (see menkor_orders.tax_line)

_PH = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def sha256_text(t: str) -> str:
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ── configuration ────────────────────────────────────────────────────────────
def read_config(getter) -> dict:
    """getter(name, default='') -> str (the app's _secret). Returns {placeholder: value} for the filled keys only (whitespace-stripped, never invented)."""
    out = {}
    for ph, key in REQUIRED_CONFIG.items():
        try: v = str(getter(key, "") or "").strip()
        except Exception: v = ""
        if v: out[ph] = v
    try: out["_tax_mode"] = str(getter("LEGAL_TAX_MODE", "") or "").strip()
    except Exception: out["_tax_mode"] = ""
    try: out["_effective_override"] = str(getter("LEGAL_EFFECTIVE_DATE", "") or "").strip()
    except Exception: out["_effective_override"] = ""
    return out


def missing_config(cfg: dict) -> list[str]:
    """Names of the configuration keys still to provide (empty = complete)."""
    miss = [key for ph, key in REQUIRED_CONFIG.items() if not (cfg or {}).get(ph)]
    if (cfg or {}).get("_tax_mode") not in TAX_MODES: miss.append("LEGAL_TAX_MODE")
    ry = (cfg or {}).get("retention_years")
    if ry and not (ry.isdigit() and 1 <= int(ry) <= 99):
        miss.append("LEGAL_RETENTION_YEARS (a whole number of years)")
    return miss


# ── documents ────────────────────────────────────────────────────────────────
class Doc:
    def __init__(self, key, lang, version, status, effective, title, template):
        self.key, self.lang, self.version, self.status, self.effective, self.title, self.template = key, lang, version, status, effective, title, template


def parse_doc(raw: str) -> Doc:
    m = re.match(r"\A---\n(.*?)\n---\n(.*)\Z", raw, re.S)
    if not m: raise ValueError("legal text without header")
    h = {}
    for ln in m.group(1).splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1); h[k.strip()] = v.strip()
    for k in ("key", "lang", "version", "status", "title"):
        if not h.get(k): raise ValueError(f"legal text header misses '{k}'")
    if h["status"] not in ("draft", "published"): raise ValueError("status must be draft or published")
    return Doc(h["key"], h["lang"], h["version"], h["status"], h.get("effective", ""), h["title"], m.group(2).strip() + "\n")


def load_docs(directory: str = LEGAL_DIR) -> dict:
    docs = {}
    for k in DOC_KEYS:
        for lg in LANGS:
            p = os.path.join(directory, f"{k}.{lg}.md")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f: d = parse_doc(f.read())
                docs[(d.key, d.lang)] = d
    return docs


def placeholders(template: str) -> set:
    return set(_PH.findall(template))


def render(doc: Doc, cfg: dict, extra: dict | None = None):
    """-> (text, missing placeholders). `extra` carries computed values (e.g. offers_table). A missing value is left as the visible token and reported."""
    vals = {**{k: v for k, v in (cfg or {}).items() if not k.startswith("_")}, **(extra or {})}
    miss = []
    def _sub(m):
        k = m.group(1)
        if vals.get(k): return str(vals[k])
        miss.append(k); return m.group(0)
    return _PH.sub(_sub, doc.template), sorted(set(miss))


def is_test_key(stripe_key: str) -> bool:
    return str(stripe_key or "").startswith(("sk_test_", "rk_test_"))


class Bundle:
    """The legal documents of one language, rendered. `ready` is True only when they can be shown to a customer and accepted."""
    def __init__(self, lang, ready, docs, problems, draft_allowed):
        self.lang, self.ready, self.docs, self.problems, self.draft_allowed = lang, ready, docs, problems, draft_allowed

    def doc_ref(self, key):
        d = self.docs[key]
        return dict(key=key, lang=self.lang, version=d["version"], effective=d["effective"], sha256=d["sha256"])


def build_bundle(lang, cfg, docs=None, extra=None, stripe_key="", directory=LEGAL_DIR) -> Bundle:
    docs = docs if docs is not None else load_docs(directory)
    problems = []; out = {}
    draft_ok = is_test_key(stripe_key)
    mc = missing_config(cfg or {})
    if mc: problems.append("configuration missing: " + ", ".join(mc))
    for k in DOC_KEYS:
        d = docs.get((k, lang))
        if d is None: problems.append(f"text missing: {k}.{lang}"); continue
        if d.status != "published" and not draft_ok: problems.append(f"text not published: {k}.{lang}")
        eff = d.effective or (cfg or {}).get("_effective_override", "")
        if d.status == "published" and not eff: problems.append(f"effective date missing: {k}.{lang}")
        text, miss = render(d, cfg or {}, extra)
        if miss: problems.append(f"{k}.{lang}: unfilled fields {', '.join(miss)}")
        out[k] = dict(version=d.version, effective=eff, title=d.title, text=text, sha256=sha256_text(text), status=d.status)
    return Bundle(lang, not problems, out, problems, draft_ok)


# ── what the customer ticks (the exact label is stored with the proof, and re-checked on the server) ──
LABELS = {
    "terms": {
        "fr": "J'ai lu et j'accepte les Conditions générales de vente et d'utilisation, comprenant la licence d'utilisation des données et des rapports.",
        "en": "I have read and agree to the Terms of Sale and Use, including the data and report licence.",
    },
    "signup": {
        "fr": "J'ai lu et j'accepte les Conditions générales d'utilisation.",
        "en": "I have read and agree to the Terms of Use.",
    },
    "immediate": {
        "fr": "Je demande l'exécution immédiate du service et de l'accès numérique avant l'expiration de mon éventuel délai de rétractation.",
        "en": "I request immediate performance of the service and digital access before any right of withdrawal I may have has expired.",
    },
    "immediate_ack": {
        "fr": "Je reconnais avoir été informé(e) des conditions, du délai et des conséquences de l'exercice de mon éventuel droit de rétractation, décrits dans l'information « Rétractation, remboursements et résiliation ».",
        "en": "I acknowledge that I have been informed of the conditions, time limit and consequences of exercising any right of withdrawal I may have, as described in the “Withdrawal, refunds and cancellation” information.",
    },
    "marketing": {
        "fr": "Je souhaite recevoir des informations commerciales de Menkor Aviation (facultatif).",
        "en": "I would like to receive commercial information from Menkor Aviation (optional).",
    },
}


def label(kind: str, lang: str) -> str:
    return LABELS[kind][lang if lang in LANGS else "en"]


# ── public pages / PDF ───────────────────────────────────────────────────────
def doc_title(key: str, lang: str, docs=None) -> str:
    d = (docs or load_docs()).get((key, lang))
    return d.title if d else key


def _md_blocks(text: str):
    """Tiny markdown reader: '# ' / '## ' / '### ' headings, '- ' bullets, '| ' table rows, paragraphs."""
    para = []
    for ln in text.splitlines():
        s = ln.rstrip()
        if not s.strip():
            if para: yield ("p", " ".join(para)); para = []
            continue
        if s.startswith("#"):
            if para: yield ("p", " ".join(para)); para = []
            lvl = len(s) - len(s.lstrip("#")); yield (f"h{min(lvl,3)}", s.lstrip("#").strip()); continue
        if s.lstrip().startswith("- "):
            if para: yield ("p", " ".join(para)); para = []
            yield ("li", s.lstrip()[2:].strip()); continue
        if s.lstrip().startswith("|"):
            if para: yield ("p", " ".join(para)); para = []
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells): continue
            yield ("tr", cells); continue
        para.append(s.strip())
    if para: yield ("p", " ".join(para))


def _inline(t: str) -> str:
    from xml.sax.saxutils import escape
    t = escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return t


def document_pdf(rendered: dict, lang: str, seller_name: str = "") -> bytes:
    """PDF of one rendered document, with its version and effective date on the first lines and in the footer."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    NAVY = HexColor("#112244"); SLATE = HexColor("#5A6B85")
    st_ = getSampleStyleSheet()
    sT = ParagraphStyle("T", parent=st_["Title"], fontName="Helvetica-Bold", fontSize=17, textColor=NAVY, spaceAfter=4)
    sM = ParagraphStyle("M", parent=st_["Normal"], fontName="Helvetica", fontSize=8.5, textColor=SLATE, spaceAfter=10)
    sH = ParagraphStyle("H", parent=st_["Heading2"], fontName="Helvetica-Bold", fontSize=11.5, textColor=NAVY, spaceBefore=9, spaceAfter=4)
    sH3 = ParagraphStyle("H3", parent=st_["Heading3"], fontName="Helvetica-Bold", fontSize=10, textColor=NAVY, spaceBefore=6, spaceAfter=3)
    sP = ParagraphStyle("P", parent=st_["Normal"], fontName="Helvetica", fontSize=9, leading=12.2, spaceAfter=4)
    sC = ParagraphStyle("C", parent=sP, fontSize=8, leading=10)
    buf = io.BytesIO()
    ver = f"{'Version' if lang=='en' else 'Version'} {rendered['version']}"
    eff = (f"{'Effective' if lang=='en' else 'En vigueur le'} {rendered['effective']}" if rendered.get("effective") else "")
    draft = rendered.get("status") == "draft"
    foot = " · ".join(x for x in (seller_name, ver, eff, "DRAFT — NOT PUBLISHED" if draft else "") if x)
    def _f(c, d):
        c.saveState(); c.setFont("Helvetica", 7); c.setFillColor(SLATE)
        c.drawString(18 * mm, 9 * mm, foot[:120]); c.drawRightString(A4[0] - 18 * mm, 9 * mm, f"{d.page}"); c.restoreState()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
                            title=rendered["title"], author=seller_name or "Menkor Aviation")
    story = [Paragraph(_inline(rendered["title"]), sT), Paragraph(_inline(" · ".join(x for x in (ver, eff) if x)), sM)]
    items = []; rows = []
    def _flush_list():
        nonlocal items
        if items: story.append(ListFlowable([ListItem(Paragraph(_inline(i), sP)) for i in items], bulletType="bullet", leftIndent=12)); items = []
    def _flush_tbl():
        nonlocal rows
        if rows:
            n = max(len(r) for r in rows)
            data = [[Paragraph(_inline(c), sC) for c in r + [""] * (n - len(r))] for r in rows]
            t = Table(data, colWidths=[(A4[0] - 36 * mm) / n] * n, repeatRows=1)
            t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, HexColor("#CCCCCC")), ("BACKGROUND", (0, 0), (-1, 0), HexColor("#EEF2F8")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(t); story.append(Spacer(1, 4)); rows = []
    for kind, val in _md_blocks(rendered["text"]):
        if kind == "h1" and val.strip() == rendered["title"].strip(): continue          # the title is already printed above
        if kind != "li": _flush_list()
        if kind != "tr": _flush_tbl()
        if kind in ("h1", "h2"): story.append(Paragraph(_inline(val), sH))
        elif kind == "h3": story.append(Paragraph(_inline(val), sH3))
        elif kind == "li": items.append(val)
        elif kind == "tr": rows.append(val)
        else: story.append(Paragraph(_inline(val), sP))
    _flush_list(); _flush_tbl()
    doc.build(story, onFirstPage=_f, onLaterPages=_f)
    return buf.getvalue()


# ── manifest: a published version never changes silently ─────────────────────
def template_hashes(directory: str = LEGAL_DIR) -> dict:
    return {f"{k}.{lg}": sha256_text(d.template) for (k, lg), d in sorted(load_docs(directory).items())
            for d in [d]}


def manifest(directory: str = LEGAL_DIR) -> dict:
    p = os.path.join(directory, "MANIFEST.json")
    if not os.path.exists(p): return {}
    with open(p, encoding="utf-8") as f: return json.load(f)


def manifest_problems(directory: str = LEGAL_DIR) -> list[str]:
    """Texts whose content changed without a new version number (compared with legal/MANIFEST.json: {"terms.fr": {"version": "1.0", "sha256": "..."}})."""
    mf = manifest(directory); out = []
    for (k, lg), d in load_docs(directory).items():
        rec = mf.get(f"{k}.{lg}")
        if rec is None: out.append(f"{k}.{lg}: not in MANIFEST"); continue
        if rec["version"] == d.version and rec["sha256"] != sha256_text(d.template):
            out.append(f"{k}.{lg}: text changed but version {d.version} was kept")
    return out
