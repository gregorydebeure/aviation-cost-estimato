"""Menkor — orders, explicit acceptance of the terms (with durable proof), consistency of what is shown / paid, reconciliation, customer documents.

Pure logic with an INJECTED Supabase transport `rest(method, table, params=None, json=None, prefer=None) -> (status, data)` (same convention as menkor_store).
No Streamlit import, no network by itself.

Guarantees (each one is covered by tests/test_orders.py)
- A Stripe Checkout Session is created ONLY from a stored order that has a stored acceptance (`assert_payable`). The acceptance is validated on the server:
  exact label, ticked boxes, consumer boxes when required, legal documents ready. The UI cannot bypass it (no UI state is trusted).
- The amount shown in the recap, the order, the Stripe parameters and the paid session are the same number (`assert_consistent`, `reconcile`).
- A paid session activates nothing unless it carries the id of an order that exists, belongs to the same e-mail, was accepted and has the same amount.
- Events are processed idempotently: the order moves pending_payment -> paid by a conditional update, so replays change nothing.
- What was accepted is frozen: the rendered text is stored by SHA-256 in `legal_document_versions` (immutable) and referenced by the acceptance (immutable).
"""
from __future__ import annotations
import base64, datetime as _dt, hashlib, json, re, uuid

import menkor_legal as L

PRO_PRICE_EUR = 79                       # Menkor Pro, per month. The Stripe Price configured in STRIPE_PRICE_PRO MUST match (verify_price).
PRO_LEGACY_NOTE = "Existing Pro subscribers on a former price keep it; the former price is not sold any more."
PACK_DAYS_DEFAULT = 14
IMMEDIATE_REQUIRED_FOR_CONSUMERS = True  # consumer must request immediate performance to be served at once (to be validated by counsel)
STATUSES = ("draft", "pending_payment", "paid", "failed", "expired", "cancelled", "mismatch", "refunded", "partially_refunded")
TABLES = ("legal_document_versions", "orders", "order_acceptances", "signup_acceptances")

COUNTRIES = dict(x.split(":") for x in (
    "AF:Afghanistan;AL:Albania;DZ:Algeria;AD:Andorra;AO:Angola;AG:Antigua and Barbuda;AR:Argentina;AM:Armenia;AU:Australia;AT:Austria;AZ:Azerbaijan;BS:Bahamas;BH:Bahrain;"
    "BD:Bangladesh;BB:Barbados;BY:Belarus;BE:Belgium;BZ:Belize;BJ:Benin;BT:Bhutan;BO:Bolivia;BA:Bosnia and Herzegovina;BW:Botswana;BR:Brazil;BN:Brunei;BG:Bulgaria;BF:Burkina Faso;"
    "BI:Burundi;KH:Cambodia;CM:Cameroon;CA:Canada;CV:Cabo Verde;CF:Central African Republic;TD:Chad;CL:Chile;CN:China;CO:Colombia;KM:Comoros;CG:Congo;CD:DR Congo;CR:Costa Rica;"
    "CI:Cote d'Ivoire;HR:Croatia;CU:Cuba;CY:Cyprus;CZ:Czechia;DK:Denmark;DJ:Djibouti;DM:Dominica;DO:Dominican Republic;EC:Ecuador;EG:Egypt;SV:El Salvador;GQ:Equatorial Guinea;"
    "ER:Eritrea;EE:Estonia;SZ:Eswatini;ET:Ethiopia;FJ:Fiji;FI:Finland;FR:France;GA:Gabon;GM:Gambia;GE:Georgia;DE:Germany;GH:Ghana;GR:Greece;GD:Grenada;GT:Guatemala;GN:Guinea;"
    "GW:Guinea-Bissau;GY:Guyana;HT:Haiti;HN:Honduras;HK:Hong Kong;HU:Hungary;IS:Iceland;IN:India;ID:Indonesia;IR:Iran;IQ:Iraq;IE:Ireland;IL:Israel;IT:Italy;JM:Jamaica;JP:Japan;"
    "JO:Jordan;KZ:Kazakhstan;KE:Kenya;KI:Kiribati;KW:Kuwait;KG:Kyrgyzstan;LA:Laos;LV:Latvia;LB:Lebanon;LS:Lesotho;LR:Liberia;LY:Libya;LI:Liechtenstein;LT:Lithuania;LU:Luxembourg;"
    "MO:Macao;MG:Madagascar;MW:Malawi;MY:Malaysia;MV:Maldives;ML:Mali;MT:Malta;MH:Marshall Islands;MR:Mauritania;MU:Mauritius;MX:Mexico;FM:Micronesia;MD:Moldova;MC:Monaco;"
    "MN:Mongolia;ME:Montenegro;MA:Morocco;MZ:Mozambique;MM:Myanmar;NA:Namibia;NR:Nauru;NP:Nepal;NL:Netherlands;NZ:New Zealand;NI:Nicaragua;NE:Niger;NG:Nigeria;MK:North Macedonia;"
    "NO:Norway;OM:Oman;PK:Pakistan;PW:Palau;PS:Palestine;PA:Panama;PG:Papua New Guinea;PY:Paraguay;PE:Peru;PH:Philippines;PL:Poland;PT:Portugal;QA:Qatar;RO:Romania;RU:Russia;"
    "RW:Rwanda;KN:Saint Kitts and Nevis;LC:Saint Lucia;VC:Saint Vincent and the Grenadines;WS:Samoa;SM:San Marino;ST:Sao Tome and Principe;SA:Saudi Arabia;SN:Senegal;RS:Serbia;"
    "SC:Seychelles;SL:Sierra Leone;SG:Singapore;SK:Slovakia;SI:Slovenia;SB:Solomon Islands;SO:Somalia;ZA:South Africa;KR:South Korea;SS:South Sudan;ES:Spain;LK:Sri Lanka;SD:Sudan;"
    "SR:Suriname;SE:Sweden;CH:Switzerland;SY:Syria;TW:Taiwan;TJ:Tajikistan;TZ:Tanzania;TH:Thailand;TL:Timor-Leste;TG:Togo;TO:Tonga;TT:Trinidad and Tobago;TN:Tunisia;TR:Turkiye;"
    "TM:Turkmenistan;TV:Tuvalu;UG:Uganda;UA:Ukraine;AE:United Arab Emirates;GB:United Kingdom;US:United States;UY:Uruguay;UZ:Uzbekistan;VU:Vanuatu;VA:Vatican City;VE:Venezuela;"
    "VN:Vietnam;YE:Yemen;ZM:Zambia;ZW:Zimbabwe").split(";"))
EU_VAT_PREFIX = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "EL", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE"}


class OrderError(Exception):
    """A refused order. `.code` is stable (tests), `.problems` lists what to correct (shown to the customer)."""
    def __init__(self, code, problems=None):
        super().__init__(code); self.code = code; self.problems = list(problems or [])


def _now() -> _dt.datetime: return _dt.datetime.now(_dt.timezone.utc)
def _iso(d) -> str: return d.astimezone(_dt.timezone.utc).isoformat(timespec="seconds")
def _ok(s) -> bool: return s in (200, 201, 204)
def _canon(o) -> str: return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
def _sha(o) -> str: return hashlib.sha256(_canon(o).encode("utf-8")).hexdigest()
def money(minor: int, currency: str) -> str:
    sym = {"EUR": "€", "USD": "$"}.get(currency.upper(), currency.upper() + " ")
    return f"{sym} {minor/100:,.2f}".replace(".00", "") if minor % 100 == 0 else f"{sym} {minor/100:,.2f}"


# ── catalog: what is really sold (read from the code that grants the access, never retyped) ──────────────
def catalog(access=None, mkt=None, market_search_eur: int = 600, pro_eur: int = PRO_PRICE_EUR) -> dict:
    """offer key -> offer. Prices come from menkor_access.PRODUCTS / menkor_market.LISTING_PRICE_EUR / the Market Search constant / PRO_PRICE_EUR."""
    days = getattr(access, "PACK_DAYS", PACK_DAYS_DEFAULT); quota = getattr(access, "PRO_MODELS_PER_MONTH", 10)
    chg = getattr(access, "MAX_MODEL_CHANGES_PER_24H", 3)
    cat = {}
    credit_pack = dict(
        en=f"The models are chosen by you in the Model access panel. You may replace them during the period (at most {chg} replacements per rolling 24 hours). Regenerating or changing assumptions on an unlocked model costs nothing.",
        fr=f"Vous choisissez les modèles dans le panneau « Model access ». Vous pouvez les remplacer pendant la période (au plus {chg} remplacements par période glissante de 24 heures). Régénérer ou modifier les hypothèses d'un modèle débloqué ne consomme rien.")
    feats = dict(
        en="Full features on the unlocked models: your hours and fuel price, Profitability, Sensitivity, Cost Master, PDF report, CSV export, Quotation, saved scenarios.",
        fr="Toutes les fonctions sur les modèles débloqués : vos heures et prix du carburant, Rentabilité, Sensibilité, Cost Master, rapport PDF, export CSV, Devis, scénarios enregistrés.")
    P = getattr(access, "PRODUCTS", {})
    for k, p in P.items():
        if k == "extra_model":
            cat[k] = dict(key=k, category="time_limited_pack", mode="payment", currency="EUR", amount_minor=p["price_eur"] * 100, interval=None, access_days=days, models=1,
                          label=dict(en="Additional model", fr="Modèle supplémentaire"),
                          includes=dict(en="1 more unlocked model. Added to your pack for its remaining period; on Menkor Pro, +1 new model for the current month.",
                                        fr="1 modèle débloqué en plus. Ajouté à votre pack pour sa période restante ; avec Menkor Pro, +1 nouveau modèle pour le mois en cours."),
                          duration=dict(en=f"Pack holder: for the remaining period of the pack (it does not extend the dates). Pro: for as long as the subscription is active.",
                                        fr="Détenteur d'un pack : pour la période restante du pack (elle ne la prolonge pas). Pro : tant que l'abonnement est actif."),
                          credits=credit_pack)
        else:
            cat[k] = dict(key=k, category="time_limited_pack", mode="payment", currency="EUR", amount_minor=p["price_eur"] * 100, interval=None, access_days=days, models=p["slots"],
                          label=dict(en=p["label"], fr={"single": "Budget individuel", "comparison": "Pack Comparaison"}.get(k, p["label"])),
                          includes=dict(en=f"{p['slots']} model(s) unlocked. " + feats["en"], fr=f"{p['slots']} modèle(s) débloqué(s). " + feats["fr"]),
                          duration=dict(en=f"{days} days from payment, then the access to the models ends. Reports already downloaded stay with you.",
                                        fr=f"{days} jours à compter du paiement, puis l'accès aux modèles prend fin. Les rapports déjà téléchargés restent à vous."),
                          credits=credit_pack)
    cat["pro"] = dict(key="pro", category="subscription_access", mode="subscription", currency="EUR", amount_minor=pro_eur * 100, interval="month", access_days=None, models=quota,
                      label=dict(en="Menkor Pro", fr="Menkor Pro"),
                      includes=dict(en=f"{quota} new models per calendar month, with the full features on them. " + feats["en"], fr=f"{quota} nouveaux modèles par mois civil, avec toutes les fonctions. " + feats["fr"]),
                      duration=dict(en="Monthly subscription, renewed automatically each month until cancelled.", fr="Abonnement mensuel, reconduit automatiquement chaque mois jusqu'à résiliation."),
                      credits=dict(en=f"{quota} NEW models per calendar month (UTC). Models already unlocked stay accessible while the subscription is active. The unused quota is not carried over. Regenerating a model already unlocked consumes nothing.",
                                   fr=f"{quota} NOUVEAUX modèles par mois civil (UTC). Les modèles déjà débloqués restent accessibles tant que l'abonnement est actif. Le quota non utilisé n'est pas reporté. Régénérer un modèle déjà débloqué ne consomme rien."))
    lp = getattr(mkt, "LISTING_PRICE_EUR", None)
    if lp:
        cat["listing"] = dict(key="listing", category="listing_subscription", mode="subscription", currency="EUR", amount_minor=lp * 100, interval="month", access_days=None, models=0,
                              label=dict(en="Aircraft-for-sale listing", fr="Annonce d'avion à vendre"),
                              includes=dict(en="Publication of one aircraft listing, after review by Menkor Aviation, with enquiries forwarded to you by e-mail. Included at no extra cost with Menkor Pro (one listing).",
                                            fr="Publication d'une annonce d'avion, après validation par Menkor Aviation, avec transmission des demandes par e-mail. Incluse sans frais avec Menkor Pro (une annonce)."),
                              duration=dict(en="Monthly subscription, renewed automatically until cancelled; the listing stays visible until the end of the paid period.",
                                            fr="Abonnement mensuel, reconduit automatiquement jusqu'à résiliation ; l'annonce reste visible jusqu'à la fin de la période payée."),
                              credits=dict(en="No credits are consumed.", fr="Aucun crédit n'est consommé."))
    if market_search_eur:
        cat["market_search"] = dict(key="market_search", category="manual_service", mode="payment", currency="EUR", amount_minor=market_search_eur * 100, interval=None, access_days=None, models=0,
                                    label=dict(en="Personalized Aircraft Market Search", fr="Recherche de marché personnalisée"),
                                    includes=dict(en="A manual market study prepared by Menkor Aviation from the criteria you submit. Delivery time is confirmed when your request is reviewed.",
                                                  fr="Une étude de marché manuelle préparée par Menkor Aviation à partir des critères que vous soumettez. Le délai de livraison est confirmé lors de l'examen de votre demande."),
                                    duration=dict(en="One-off service, delivered once.", fr="Prestation ponctuelle, livrée une fois."),
                                    credits=dict(en="No credits are consumed.", fr="Aucun crédit n'est consommé."))
    return cat


def offers_table(cat: dict, lang: str) -> str:
    """Markdown table injected in the terms ({{offers_table}}): the terms always list the offers exactly as they are configured."""
    head = ("| Offre | Prix | Nature | Durée |\n|---|---|---|---|" if lang == "fr" else "| Offer | Price | Type | Duration |\n|---|---|---|---|")
    rows = []
    for o in cat.values():
        nature = (("Abonnement" if lang == "fr" else "Subscription") + (" / mois" if lang == "fr" else " / month")) if o["mode"] == "subscription" else ("Paiement unique" if lang == "fr" else "One-off payment")
        rows.append(f"| {o['label'][lang]} | {money(o['amount_minor'], o['currency'])} | {nature} | {o['duration'][lang]} |")
    return head + "\n" + "\n".join(rows)


def tax_line(cfg: dict, lang: str) -> str:
    mode = (cfg or {}).get("_tax_mode"); note = (cfg or {}).get("tax_note", "")
    if mode == "stripe_tax":
        base = ("Les taxes éventuellement applicables sont calculées par Stripe d'après votre pays de facturation et ajoutées sur la page de paiement, avant que vous ne payiez ; le total y est affiché."
                if lang == "fr" else "Any applicable taxes are calculated by Stripe from your billing country and added on the payment page before you pay; the total is shown there.")
    else:
        base = ""
    return (base + " " + note).strip()


# ── billing details ──────────────────────────────────────────────────────────
def _clean(s, n=120): return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def validate_profile(p: dict, email: str, lang: str = "en") -> tuple[dict, list[str]]:
    """-> (normalised profile, problems). Only useful fields. VAT / tax id is OPTIONAL even for businesses."""
    fr = lang == "fr"; probs = []
    t = _clean(p.get("customer_type"), 20)
    if t not in ("individual", "business"): probs.append("Choisissez Particulier ou Professionnel." if fr else "Choose Individual or Business.")
    out = dict(customer_type=t, first_name=_clean(p.get("first_name"), 60), last_name=_clean(p.get("last_name"), 60), email=(email or "").strip().lower(),
               country=_clean(p.get("country"), 2).upper(), address_line1=_clean(p.get("address_line1")), address_line2=_clean(p.get("address_line2")),
               postal_code=_clean(p.get("postal_code"), 20), city=_clean(p.get("city"), 80), company_name=_clean(p.get("company_name")), tax_id=_clean(p.get("tax_id"), 24))
    if not out["first_name"] or not out["last_name"]: probs.append("Indiquez prénom et nom." if fr else "Enter first and last name.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", out["email"]): probs.append("Adresse e-mail invalide." if fr else "Invalid e-mail address.")
    if out["country"] not in COUNTRIES: probs.append("Choisissez le pays de facturation." if fr else "Choose the billing country.")
    for k, lab_fr, lab_en in (("address_line1", "l'adresse", "the address"), ("postal_code", "le code postal", "the postal code"), ("city", "la ville", "the city")):
        if not out[k]: probs.append(f"Indiquez {lab_fr}." if fr else f"Enter {lab_en}.")
    if t == "business":
        if not out["company_name"]: probs.append("Indiquez la raison sociale." if fr else "Enter the company name.")
    else:
        out["company_name"] = ""; out["tax_id"] = ""
    if out["tax_id"] and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .\-/]{3,23}", out["tax_id"]):
        probs.append("Identifiant fiscal / TVA : format invalide (laissez vide s'il ne s'applique pas)." if fr else "Tax / VAT ID: invalid format (leave empty if not applicable).")
    return out, probs


def needs_immediate_request(profile: dict, offer: dict) -> bool:
    """Consumer buying a service / digital access: a SEPARATE request for immediate performance (and an acknowledgement) is collected, never pre-ticked."""
    return profile.get("customer_type") == "individual" and offer.get("category") in ("subscription_access", "time_limited_pack", "listing_subscription", "manual_service")


# ── recap shown before payment (built from the offer, the same numbers go to Stripe) ──
def recap(offer: dict, profile: dict, lang: str, cfg: dict) -> list[tuple[str, str]]:
    fr = lang == "fr"; mode = (cfg or {}).get("_tax_mode")
    price = money(offer["amount_minor"], offer["currency"]) + ((" / mois" if fr else " / month") if offer["interval"] else "")
    total = money(offer["amount_minor"], offer["currency"]) + (" + taxes applicables (affichées sur la page de paiement)" if (fr and mode == "stripe_tax") else (" + applicable taxes (shown on the payment page)" if mode == "stripe_tax" else ""))
    rows = [("Offre" if fr else "Offer", offer["label"][lang]),
            ("Contenu" if fr else "What is included", offer["includes"][lang]),
            ("Durée d'accès" if fr else "Access period", offer["duration"][lang]),
            ("Règles de consommation des crédits" if fr else "Credit consumption rules", offer["credits"][lang]),
            ("Prix" if fr else "Price", price),
            ("Devise" if fr else "Currency", offer["currency"]),
            ("Taxes" if fr else "Taxes", tax_line(cfg, lang)),
            ("Total à payer" if fr else "Total to pay", total + (" (puis chaque mois)" if fr and offer["interval"] else (" (then every month)" if offer["interval"] else ""))),
            ("Nature du paiement" if fr else "Type of payment",
             (("Récurrent : prélèvement mensuel" if fr else "Recurring: charged every month") if offer["mode"] == "subscription" else ("Paiement ponctuel" if fr else "One-off payment")))]
    if offer["mode"] == "subscription":
        rows += [("Facturation" if fr else "Billing", "Mensuelle, à date anniversaire du premier paiement." if fr else "Monthly, on the anniversary of the first payment."),
                 ("Renouvellement" if fr else "Renewal", "Automatique à chaque échéance jusqu'à résiliation." if fr else "Automatic at each due date until you cancel."),
                 ("Résiliation" if fr else "Cancellation", ("Depuis « Mes achats et documents », à tout moment ; elle prend effet à la fin de la période déjà payée. " if fr else "From “My purchases and documents”, at any time; it takes effect at the end of the period already paid. ") + (cfg or {}).get("cancellation_policy", ""))]
    return rows


def offer_snapshot(offer: dict, lang: str, cfg: dict, rows=None) -> dict:
    return dict(key=offer["key"], category=offer["category"], mode=offer["mode"], interval=offer["interval"], currency=offer["currency"], amount_minor=offer["amount_minor"],
                label=offer["label"][lang], recap=[list(r) for r in (rows or recap(offer, {}, lang, cfg))])


# ── placing an order: server-side validation + durable proof ─────────────────
def retain_until(now: _dt.datetime, cfg: dict) -> str:
    y = int((cfg or {}).get("retention_years") or 10)
    try: return _iso(now.replace(year=now.year + y))
    except ValueError: return _iso(now.replace(year=now.year + y, day=28))


def _store_documents(rest, bundle: L.Bundle, now):
    """Immutable copies (by SHA-256) of every document shown with the order. Insert-if-absent: an existing hash is never rewritten."""
    refs = []
    for key in L.DOC_KEYS:
        d = bundle.docs[key]
        refs.append(bundle.doc_ref(key))
        st, _ = rest("POST", "legal_document_versions?on_conflict=sha256", None,
                     dict(sha256=d["sha256"], doc_key=key, lang=bundle.lang, version=d["version"], effective=d["effective"] or None, title=d["title"], body=d["text"], created_at=_iso(now)),
                     "return=minimal,resolution=ignore-duplicates")
        if not _ok(st): raise OrderError("proof_storage_failed", ["Could not store the legal documents."])
    return refs


def place_order(rest, *, email, offer, profile, accept, bundle: L.Bundle, cfg: dict, now=None, extra=None) -> dict:
    """Validates EVERYTHING again, stores the order and its acceptance, returns the order (status pending_payment). Fails closed: any storage failure -> OrderError.
    `accept` = dict(terms=bool, label=str, immediate=bool, immediate_ack=bool, marketing=bool)."""
    now = now or _now(); lang = bundle.lang; email = (email or "").strip().lower()
    if not bundle.ready: raise OrderError("legal_not_ready", bundle.problems)
    if not email: raise OrderError("login_required", ["An e-mail address is required."])
    if not offer or offer.get("key") is None: raise OrderError("unknown_offer", ["Unknown offer."])
    prof, probs = validate_profile(profile or {}, email, lang)
    if probs: raise OrderError("invalid_profile", probs)
    acc = accept or {}
    if acc.get("terms") is not True: raise OrderError("terms_not_accepted", ["The Terms must be accepted before payment."])
    if acc.get("label") != L.label("terms", lang): raise OrderError("label_mismatch", ["The accepted statement does not match the current one."])
    need_imm = IMMEDIATE_REQUIRED_FOR_CONSUMERS and needs_immediate_request(prof, offer)
    if need_imm and not (acc.get("immediate") is True and acc.get("immediate_ack") is True):
        raise OrderError("immediate_request_missing", ["For consumers, the request for immediate performance and the acknowledgement are required to start the service immediately."])
    rows = recap(offer, prof, lang, cfg); snap = offer_snapshot(offer, lang, cfg, rows); fp = _sha(snap)
    docs = _store_documents(rest, bundle, now)
    oid = "ORD-" + uuid.uuid4().hex[:16].upper()
    terms_ref = bundle.doc_ref("terms")
    order = dict(id=oid, email=email, customer_type=prof["customer_type"], billing={k: v for k, v in prof.items() if k not in ("customer_type", "email")},
                 offer_key=offer["key"], offer_label=offer["label"][lang], amount_minor=offer["amount_minor"], currency=offer["currency"], mode=offer["mode"], interval=offer["interval"],
                 category=offer["category"], status="draft", lang=lang, terms_version=terms_ref["version"], terms_sha256=terms_ref["sha256"],
                 extra={**(extra or {}), "access_days": offer.get("access_days")},
                 created_at=_iso(now), updated_at=_iso(now))
    st, _ = rest("POST", "orders", None, order, "return=minimal")
    if not _ok(st): raise OrderError("order_storage_failed", ["The order could not be recorded."])
    proof = dict(id="ACC-" + uuid.uuid4().hex[:16].upper(), order_id=oid, email=email, accepted_at=_iso(now), lang=lang,
                 terms_version=terms_ref["version"], terms_sha256=terms_ref["sha256"], checkbox_label=acc["label"], checkbox_label_sha256=L.sha256_text(acc["label"]),
                 documents=docs, offer_snapshot=snap, offer_fingerprint=fp, amount_minor=offer["amount_minor"], currency=offer["currency"], mode=offer["mode"],
                 immediate_requested=bool(acc.get("immediate")) if need_imm else False, immediate_ack=bool(acc.get("immediate_ack")) if need_imm else False,
                 immediate_label=L.label("immediate", lang) if need_imm else None, immediate_ack_label=L.label("immediate_ack", lang) if need_imm else None,
                 marketing_opt_in=bool(acc.get("marketing")), marketing_label=L.label("marketing", lang), retain_until=retain_until(now, cfg))
    st, _ = rest("POST", "order_acceptances", None, proof, "return=minimal")
    if not _ok(st):
        rest("PATCH", "orders", {"id": f"eq.{oid}"}, dict(status="cancelled", updated_at=_iso(now)), "return=minimal")
        raise OrderError("proof_storage_failed", ["The acceptance could not be recorded, so no payment can start."])
    st, _ = rest("PATCH", "orders", {"id": f"eq.{oid}", "status": "eq.draft"}, dict(status="pending_payment", updated_at=_iso(now)), "return=minimal")
    if not _ok(st): raise OrderError("order_storage_failed", ["The order could not be activated."])
    order["status"] = "pending_payment"; order["_fingerprint"] = fp
    return order


def get_order(rest, email, order_id):
    """Owner check on the server: the e-mail filter is part of the query."""
    st, rows = rest("GET", "orders", {"id": f"eq.{order_id}", "email": f"eq.{(email or '').strip().lower()}", "select": "*", "limit": "1"})
    return rows[0] if _ok(st) and rows else None


def get_acceptance(rest, email, order_id):
    st, rows = rest("GET", "order_acceptances", {"order_id": f"eq.{order_id}", "email": f"eq.{(email or '').strip().lower()}", "select": "*", "limit": "1"})
    return rows[0] if _ok(st) and rows else None


def assert_payable(rest, email, order_id):
    """THE gate in front of every Stripe Checkout creation. Raises OrderError unless the order exists for this e-mail, is pending payment and has its acceptance."""
    o = get_order(rest, email, order_id)
    if not o: raise OrderError("order_not_found", ["Order not found."])
    if o.get("status") != "pending_payment": raise OrderError("order_not_payable", [f"Order status: {o.get('status')}."])
    a = get_acceptance(rest, email, order_id)
    if not a or a.get("order_id") != order_id: raise OrderError("no_acceptance", ["No recorded acceptance for this order."])
    if a.get("terms_sha256") != o.get("terms_sha256") or a.get("amount_minor") != o.get("amount_minor") or a.get("currency") != o.get("currency"):
        raise OrderError("acceptance_mismatch", ["The accepted terms or amount differ from the order."])
    return o


# ── Stripe parameters: same amount as the order, native invoices, order id everywhere ──
def params_amount(params: dict):
    """Total (minor units) of line_items given with price_data; None when a Stripe price id is used (then verify_price)."""
    tot = 0
    for li in params.get("line_items", []):
        pd = li.get("price_data")
        if not pd: return None
        tot += int(pd["unit_amount"]) * int(li.get("quantity", 1))
    return tot


def verify_price(price_obj, order: dict) -> None:
    """The Stripe Price behind a subscription (STRIPE_PRICE_PRO) must be exactly what the recap showed. Accepts a dict or a Stripe object."""
    g = (lambda o, k: (o.get(k) if hasattr(o, "get") else getattr(o, k, None)))
    rec = g(price_obj, "recurring")
    if g(price_obj, "unit_amount") != order["amount_minor"] or str(g(price_obj, "currency") or "").upper() != order["currency"] or (g(rec, "interval") if rec else None) != order["interval"]:
        raise OrderError("price_mismatch", ["The configured price does not match the displayed offer. Payment is blocked."])


def assert_consistent(params: dict, order: dict) -> None:
    amt = params_amount(params)
    if amt is not None and amt != order["amount_minor"]: raise OrderError("price_mismatch", ["Payment parameters do not match the order."])
    for li in params.get("line_items", []):
        pd = li.get("price_data")
        if pd and str(pd.get("currency", "")).upper() != order["currency"]: raise OrderError("price_mismatch", ["Currency mismatch."])
        if pd and bool(pd.get("recurring")) != (order["mode"] == "subscription"): raise OrderError("price_mismatch", ["Payment mode mismatch."])
    if params.get("mode") != order["mode"]: raise OrderError("price_mismatch", ["Payment mode mismatch."])


def decorate_params(params: dict, order: dict, cfg: dict, customer_id: str | None = None) -> dict:
    """Adds the order to Stripe Checkout parameters built by the existing product code (they keep their own metadata, line items and return URLs)."""
    p = dict(params); lang = order["lang"]; assert_consistent(p, order)
    md = dict(p.get("metadata") or {}); md.update(order_id=order["id"], terms_version=order["terms_version"], terms_sha256=order["terms_sha256"][:40], customer_type=order["customer_type"])
    p["metadata"] = md; p["client_reference_id"] = order["id"]; p["locale"] = "fr" if lang == "fr" else "en"
    p["billing_address_collection"] = "required"
    if customer_id: p.pop("customer_email", None); p["customer"] = customer_id; p["customer_update"] = {"name": "auto", "address": "auto"}
    else: p["customer_email"] = order["email"]
    if order["mode"] == "payment":
        p["invoice_creation"] = {"enabled": True, "invoice_data": {"description": order["offer_label"][:200], "metadata": {"order_id": order["id"]}}}
        if not customer_id: p["customer_creation"] = "always"
        p["payment_intent_data"] = {**(p.get("payment_intent_data") or {}), "metadata": {"order_id": order["id"]}}
    else:
        sd = dict(p.get("subscription_data") or {}); sd["metadata"] = {**(sd.get("metadata") or {}), **md}; p["subscription_data"] = sd
    if order["customer_type"] == "business": p["tax_id_collection"] = {"enabled": True}
    if (cfg or {}).get("_tax_mode") == "stripe_tax": p["automatic_tax"] = {"enabled": True}
    msg = (f"Commande {order['id']} — conditions {order['terms_version']} acceptées." if lang == "fr" else f"Order {order['id']} — terms {order['terms_version']} accepted.")
    p["custom_text"] = {"submit": {"message": msg}}
    return p


def customer_params(order: dict) -> dict:
    b = order["billing"]; biz = order["customer_type"] == "business"
    name = b.get("company_name") if biz and b.get("company_name") else f"{b.get('first_name','')} {b.get('last_name','')}".strip()
    return dict(email=order["email"], name=name,
                address=dict(line1=b.get("address_line1", ""), line2=b.get("address_line2") or None, postal_code=b.get("postal_code", ""), city=b.get("city", ""), country=b.get("country", "")),
                metadata=dict(menkor_email=order["email"], customer_type=order["customer_type"], contact_name=f"{b.get('first_name','')} {b.get('last_name','')}".strip()[:120]))


# ── reconciliation of paid sessions (no webhook: Stripe is read server side; idempotent) ──
def _g(o, k, d=None):
    try: v = o.get(k, d) if hasattr(o, "get") else getattr(o, k, d)
    except Exception: v = d
    return d if v is None else v


def _sid(x): return x if isinstance(x, str) else (_g(x, "id") if x else None)


def reconcile(rest, sessions, email, cfg=None, now=None) -> dict:
    """Moves orders from pending_payment to paid / expired / mismatch according to the Stripe sessions. Returns {'paid': [orders newly paid], 'skipped': [reasons]}.
    A replay (same session twice, or the same call twice) returns nothing new."""
    now = now or _now(); email = (email or "").strip().lower(); res = dict(paid=[], skipped=[])
    stax = (cfg or {}).get("_tax_mode") == "stripe_tax"
    for s in sessions or []:
        sid = _g(s, "id"); md = _g(s, "metadata", {}) or {}; oid = md.get("order_id") or _g(s, "client_reference_id")
        if not oid: continue                               # not created by the order flow
        o = get_order(rest, email, oid)
        if not o: res["skipped"].append(f"{oid}: not found for this e-mail"); continue
        if o.get("stripe_session_id") and o["stripe_session_id"] != sid: res["skipped"].append(f"{oid}: other session"); continue
        who = str((_g(_g(s, "customer_details", {}) or {}, "email") or _g(s, "customer_email") or "")).strip().lower()
        if who and who != email: res["skipped"].append(f"{oid}: different e-mail"); continue
        st_ = _g(s, "status")
        if st_ == "expired":
            rest("PATCH", "orders", {"id": f"eq.{oid}", "status": "eq.pending_payment"}, dict(status="expired", updated_at=_iso(now)), "return=minimal"); continue
        if _g(s, "payment_status") != "paid" or st_ != "complete": res["skipped"].append(f"{oid}: not paid yet"); continue   # failed / pending payment never activates
        amount = _g(s, "amount_subtotal") if stax else _g(s, "amount_total")
        if amount != o["amount_minor"] or str(_g(s, "currency", "")).upper() != o["currency"] or _g(s, "mode") != o["mode"]:
            rest("PATCH", "orders", {"id": f"eq.{oid}", "status": "eq.pending_payment"}, dict(status="mismatch", updated_at=_iso(now)), "return=minimal")
            res["skipped"].append(f"{oid}: amount / currency / mode mismatch"); continue
        if not get_acceptance(rest, email, oid): res["skipped"].append(f"{oid}: no acceptance"); continue
        days = (o.get("extra") or {}).get("access_days")
        upd = dict(status="paid", paid_at=_iso(now), updated_at=_iso(now), stripe_session_id=sid, stripe_customer_id=_sid(_g(s, "customer")),
                   stripe_payment_intent=_sid(_g(s, "payment_intent")), stripe_subscription_id=_sid(_g(s, "subscription")), stripe_invoice_id=_sid(_g(s, "invoice")),
                   access_start=_iso(now), access_end=(_iso(now + _dt.timedelta(days=days)) if days else None))
        st, rows = rest("PATCH", "orders", {"id": f"eq.{oid}", "status": "eq.pending_payment"}, upd, "return=representation")   # conditional: only ONE caller wins
        if _ok(st) and rows: res["paid"].append(rows[0])
    return res


def link_session(rest, email, order_id, session_id, customer_id=None):
    """Stores the Stripe session id (and customer) on the order right after creation, so a return can be matched to its order."""
    upd = dict(stripe_session_id=session_id, updated_at=_iso(_now()))
    if customer_id: upd["stripe_customer_id"] = customer_id
    st, _ = rest("PATCH", "orders", {"id": f"eq.{order_id}", "email": f"eq.{(email or '').strip().lower()}", "status": "eq.pending_payment"}, upd, "return=minimal")
    return _ok(st)


def cancel_pending(rest, email, order_id, now=None):
    """The customer corrects / abandons an order that is not paid: it can no longer be paid (a new order, with a new acceptance, is created instead)."""
    st, _ = rest("PATCH", "orders", {"id": f"eq.{order_id}", "email": f"eq.{(email or '').strip().lower()}", "status": "eq.pending_payment"}, dict(status="cancelled", updated_at=_iso(now or _now())), "return=minimal")
    return _ok(st)


def expire_stale(rest, email, hours=26, now=None):
    """Checkout Sessions expire after 24 h: older unpaid orders are closed (they can never be paid afterwards)."""
    now = now or _now(); cutoff = _iso(now - _dt.timedelta(hours=hours))
    st, _ = rest("PATCH", "orders", {"email": f"eq.{(email or '').strip().lower()}", "status": "eq.pending_payment", "created_at": f"lt.{cutoff}"}, dict(status="expired", updated_at=_iso(now)), "return=minimal")
    return _ok(st)


def period_end(sub) -> str:
    """Next due date of a Stripe subscription (current_period_end sits on the subscription or on its items depending on the API version)."""
    pe = _g(sub, "current_period_end")
    if not pe:
        ends = [int(_g(i, "current_period_end")) for i in _g(_g(sub, "items", {}), "data", []) if _g(i, "current_period_end")]
        pe = max(ends) if ends else None
    return _dt.datetime.fromtimestamp(int(pe), _dt.timezone.utc).strftime("%Y-%m-%d") if pe else "—"


def paid_order_ids(rest, email) -> set:
    st, rows = rest("GET", "orders", {"email": f"eq.{(email or '').strip().lower()}", "status": "in.(paid,partially_refunded)", "select": "id", "limit": "500"})
    return {r["id"] for r in rows} if _ok(st) and rows else set()


def claim_confirmation(rest, email, order_id, now=None) -> bool:
    """True for exactly ONE caller per order: that caller sends the confirmation e-mail."""
    st, rows = rest("PATCH", "orders", {"id": f"eq.{order_id}", "email": f"eq.{email}", "confirmation_sent_at": "is.null", "status": "in.(paid,partially_refunded)"},
                    dict(confirmation_sent_at=_iso(now or _now())), "return=representation")
    return bool(_ok(st) and rows)


def release_confirmation(rest, email, order_id):
    rest("PATCH", "orders", {"id": f"eq.{order_id}", "email": f"eq.{email}"}, dict(confirmation_sent_at=None), "return=minimal")


# ── customer area ────────────────────────────────────────────────────────────
def list_orders(rest, email):
    st, rows = rest("GET", "orders", {"email": f"eq.{(email or '').strip().lower()}", "select": "*", "order": "created_at.desc", "limit": "200"})
    return rows if _ok(st) and rows else []


def accepted_documents(rest, email, order_id):
    """The documents accepted for one order, exactly as stored then. Owner check included. -> (acceptance, [ {key,version,effective,title,body,sha256} ])."""
    a = get_acceptance(rest, email, order_id)
    if not a: return None, []
    out = []
    for ref in a.get("documents") or []:
        st, rows = rest("GET", "legal_document_versions", {"sha256": f"eq.{ref['sha256']}", "select": "*", "limit": "1"})
        if _ok(st) and rows: out.append(dict(key=ref["key"], version=ref["version"], effective=ref.get("effective"), title=rows[0]["title"], body=rows[0]["body"], sha256=ref["sha256"]))
    return a, out


def acceptance_pdf(a: dict, docs: list, order: dict, seller: str = "") -> bytes:
    """One PDF to keep: proof summary + the full accepted terms (and the information documents), from the stored copies."""
    lang = a["lang"]; fr = lang == "fr"
    lines = [f"# {'Preuve d’acceptation' if fr else 'Proof of acceptance'}", "",
             f"- **{'Commande' if fr else 'Order'}** : {order['id']}", f"- **{'Offre' if fr else 'Offer'}** : {a['offer_snapshot']['label']} — {money(a['amount_minor'], a['currency'])}"
             + ((" / mois" if fr else " / month") if a['mode'] == 'subscription' else ""),
             f"- **{'Date d’acceptation (UTC)' if fr else 'Accepted on (UTC)'}** : {a['accepted_at']}", f"- **{'Langue' if fr else 'Language'}** : {lang}",
             f"- **{'Version des conditions' if fr else 'Terms version'}** : {a['terms_version']}", f"- **SHA-256** : {a['terms_sha256']}",
             f"- **{'Case acceptée' if fr else 'Statement accepted'}** : {a['checkbox_label']}"]
    if a.get("immediate_requested"):
        lines += [f"- **{'Exécution immédiate demandée' if fr else 'Immediate performance requested'}** : {a['immediate_label']}", f"- **{'Information reconnue' if fr else 'Information acknowledged'}** : {a['immediate_ack_label']}"]
    lines += ["", "# " + ("Récapitulatif de la commande" if fr else "Order summary"), ""] + [f"- **{k}** : {v}" for k, v in a["offer_snapshot"]["recap"]]
    lines += ["", "# " + ("Documents" if fr else "Documents"), ""] + [f"- {d['title']} — version {d['version']} — SHA-256 {d['sha256']}" for d in docs]
    body = "\n".join(lines)
    for d in docs: body += f"\n\n# {d['title']} — version {d['version']}\n\n" + re.sub(r"(?m)^#", "##", d["body"])
    return L.document_pdf(dict(version=a["terms_version"], effective="", title=("Conditions acceptées et preuve" if fr else "Accepted terms and proof"), text=body, status="published"), lang, seller)


def confirmation_email(order: dict, a: dict, lang: str, cfg: dict, app_url: str, invoice_url: str | None, pdf: bytes | None):
    """-> (subject, html, attachments). Content required before the sale is complete; the accepted terms are ATTACHED (not only linked)."""
    fr = lang == "fr"; esc = lambda s: re.sub(r"[<>&]", lambda m: {"<": "&lt;", ">": "&gt;", "&": "&amp;"}[m.group(0)], str(s))
    snap = a["offer_snapshot"]; price = money(order["amount_minor"], order["currency"]) + ((" / mois" if fr else " / month") if order["interval"] else "")
    period = (f"{order.get('access_start','')[:10]} → {order['access_end'][:10]}" if order.get("access_end") else ("Abonnement mensuel, renouvelé jusqu'à résiliation" if fr else "Monthly subscription, renewed until cancelled") if order["interval"] else ("Prestation ponctuelle" if fr else "One-off service"))
    subj = (f"Confirmation de votre commande {order['id']}" if fr else f"Your order confirmation {order['id']}")
    wd = ("Rétractation : voir l'information « Rétractation, remboursements et résiliation » ci-jointe ; elle s'applique selon le droit qui régit votre achat." if fr else
          "Withdrawal: see the attached “Withdrawal, refunds and cancellation” information; it applies according to the law governing your purchase.")
    cancel = (("Résiliation : à tout moment depuis « Mes achats et documents » ; effet à la fin de la période payée. " if fr else "Cancellation: at any time from “My purchases and documents”; effective at the end of the paid period. ") + cfg.get("cancellation_policy", "")) if order["interval"] else ""
    inv = (f'<p>{"Facture" if fr else "Invoice"} : <a href="{esc(invoice_url)}">{esc(invoice_url)}</a></p>' if invoice_url else
           f'<p>{"Votre facture sera disponible dans" if fr else "Your invoice will be available in"} « {"Mes achats et documents" if fr else "My purchases and documents"} ».</p>')
    html = (f"<p>{'Merci pour votre commande.' if fr else 'Thank you for your order.'}</p><ul>"
            f"<li>{'Offre' if fr else 'Offer'} : <b>{esc(snap['label'])}</b></li><li>{'Montant' if fr else 'Amount'} : <b>{esc(price)}</b> ({esc(order['currency'])})</li>"
            f"<li>{'Période' if fr else 'Period'} : {esc(period)}</li><li>{'Conditions acceptées' if fr else 'Terms accepted'} : {esc(order['terms_version'])} ({esc(a['accepted_at'])} UTC)</li></ul>"
            f"{inv}<p>{'Documents et commandes' if fr else 'Documents and orders'} : <a href=\"{esc(app_url)}\">{esc(app_url)}</a></p><p>{esc(cancel)}</p><p>{esc(wd)}</p>"
            f"<p>{'Les conditions que vous avez acceptées sont jointes à ce message (PDF) : conservez-les.' if fr else 'The terms you accepted are attached (PDF): please keep them.'}</p>"
            f"<p>{esc(cfg.get('seller_name',''))} — {esc(cfg.get('contact_email',''))}</p>")
    att = [(f"terms-{order['id']}.pdf", pdf)] if pdf else []
    return subj, html, att


def send_email(post, api_key, sender, to, subject, html, attachments=()):
    """Resend REST with attachments. Best effort -> (ok, detail). `post` is injectable (tests never send)."""
    if not api_key: return False, "no e-mail key configured"
    body = dict(**{"from": sender}, to=[to], subject=subject, html=html)
    if attachments: body["attachments"] = [dict(filename=n, content=base64.b64encode(b).decode()) for n, b in attachments]
    try:
        r = post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}, json=body, timeout=15)
        return (200 <= r.status_code < 300), f"HTTP {r.status_code}"
    except Exception as e:
        return False, type(e).__name__


# ── Stripe documents of the customer (invoices, credit notes, refunds) — ownership by customer ids of OWN orders ──
def own_customer_ids(orders: list) -> set:
    return {o["stripe_customer_id"] for o in orders if o.get("stripe_customer_id")}


def stripe_documents(stripe_mod, orders: list) -> dict:
    """{'invoices': [...], 'credit_notes': [...]} for the customers of THIS user's orders only. Each row is re-checked against the owned customer ids."""
    own = own_customer_ids(orders); inv, cn = [], []
    for cid in sorted(own):
        try:
            for i in list(_g(stripe_mod.Invoice.list(customer=cid, limit=50), "data", [])):
                if _sid(_g(i, "customer")) != cid: continue
                inv.append(dict(id=_g(i, "id"), number=_g(i, "number"), status=_g(i, "status"), total=_g(i, "total"), currency=str(_g(i, "currency", "")).upper(),
                                created=_g(i, "created"), hosted_url=_g(i, "hosted_invoice_url"), pdf_url=_g(i, "invoice_pdf"), subscription=_sid(_g(i, "subscription"))))
        except Exception: pass
        try:
            for c in list(_g(stripe_mod.CreditNote.list(customer=cid, limit=50), "data", [])):
                if _sid(_g(c, "customer")) != cid: continue
                cn.append(dict(id=_g(c, "id"), number=_g(c, "number"), total=_g(c, "total"), currency=str(_g(c, "currency", "")).upper(), pdf_url=_g(c, "pdf"), invoice=_sid(_g(c, "invoice"))))
        except Exception: pass
    return dict(invoices=inv, credit_notes=cn)


def refund_state(stripe_mod, order: dict):
    """(refunded_minor, status). Read from Stripe; a refund stays traceable (stored on the order by `apply_refund`)."""
    pi = order.get("stripe_payment_intent")
    if not pi: return 0, None
    try:
        tot = sum(int(_g(r, "amount", 0)) for r in list(_g(stripe_mod.Refund.list(payment_intent=pi, limit=20), "data", [])) if _g(r, "status") in ("succeeded", "pending"))
    except Exception: return None, None
    return tot, ("refunded" if tot >= order["amount_minor"] else "partially_refunded" if tot > 0 else None)


def apply_refund(rest, order: dict, refunded_minor: int, status: str | None, now=None):
    if not status or refunded_minor == order.get("refunded_minor"): return False
    st, _ = rest("PATCH", "orders", {"id": f"eq.{order['id']}"}, dict(status=status, refunded_minor=refunded_minor, updated_at=_iso(now or _now())), "return=minimal")
    return _ok(st)


def can_cancel(orders: list, subscription_id: str) -> bool:
    """Cancellation is only possible for a subscription that belongs to one of the customer's own paid orders."""
    return any(o.get("stripe_subscription_id") == subscription_id and o.get("status") in ("paid", "partially_refunded") for o in orders)


# ── free sign-up: acceptance of the Terms of Use ────────────────────────────
def record_signup_acceptance(rest, email, bundle: L.Bundle, accepted: bool, label: str, cfg: dict, now=None):
    """Free account: acceptance of the Terms of Use (and awareness of the privacy policy). Raises OrderError when not accepted or not stored (account creation must stop)."""
    now = now or _now(); lang = bundle.lang
    if not bundle.ready: raise OrderError("legal_not_ready", bundle.problems)
    if accepted is not True or label != L.label("signup", lang): raise OrderError("terms_not_accepted", ["The Terms of Use must be accepted to create an account."])
    refs = _store_documents(rest, bundle, now); t = bundle.doc_ref("terms")
    st, _ = rest("POST", "signup_acceptances", None, dict(id="SGN-" + uuid.uuid4().hex[:16].upper(), email=(email or "").strip().lower(), accepted_at=_iso(now), lang=lang,
                 terms_version=t["version"], terms_sha256=t["sha256"], checkbox_label=label, documents=refs, retain_until=retain_until(now, cfg)), "return=minimal")
    if not _ok(st): raise OrderError("proof_storage_failed", ["The acceptance could not be recorded."])
    return True
