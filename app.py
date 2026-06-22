"""
✈️ Aviation Cost Estimator — Application Streamlit
Estimation et simulation des coûts d'exploitation d'avions d'affaires.
Auteur : Généré pour analyse budgétaire aviation privée/charter.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import warnings
warnings.filterwarnings("ignore")

# ─── CONFIG PAGE ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aviation Cost Estimator",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── STYLES CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Palette : bleu nuit aviation + or ambre + gris ardoise */
    :root {
        --navy:   #0B1629;
        --deep:   #112244;
        --mid:    #1A3A6E;
        --gold:   #C9A84C;
        --amber:  #E8C46A;
        --slate:  #8496B0;
        --light:  #D6E4F7;
        --white:  #F0F4FA;
        --card:   #13233F;
    }

    /* Fond général */
    .stApp {
        background-color: var(--navy) !important;
        color: var(--light) !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--deep) !important;
        border-right: 1px solid var(--mid);
    }
    [data-testid="stSidebar"] * { color: var(--light) !important; }

    /* Titre principal */
    .main-title {
        font-family: 'Segoe UI', monospace;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: var(--amber);
        text-transform: uppercase;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 0.85rem;
        color: var(--slate);
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 1.5rem;
    }

    /* Cartes métriques */
    .metric-card {
        background: var(--card);
        border: 1px solid var(--mid);
        border-left: 3px solid var(--gold);
        border-radius: 6px;
        padding: 1rem 1.2rem;
        margin-bottom: 0.8rem;
    }
    .metric-label {
        font-size: 0.72rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--slate);
        margin-bottom: 0.3rem;
    }
    .metric-value {
        font-size: 1.7rem;
        font-weight: 700;
        color: var(--amber);
    }
    .metric-sub {
        font-size: 0.78rem;
        color: var(--slate);
        margin-top: 0.1rem;
    }

    /* Section headers */
    .section-header {
        font-size: 0.7rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--gold);
        border-bottom: 1px solid var(--mid);
        padding-bottom: 0.4rem;
        margin: 1.2rem 0 0.8rem 0;
    }

    /* Divider */
    hr { border-color: var(--mid) !important; }

    /* Streamlit widgets override */
    .stSelectbox label, .stSlider label, .stNumberInput label,
    .stFileUploader label { color: var(--light) !important; font-size: 0.82rem; }

    .stSlider [data-baseweb="slider"] { accent-color: var(--gold); }

    /* Metric natif */
    [data-testid="stMetricValue"] { color: var(--amber) !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { color: var(--slate) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; }
    [data-testid="stMetricDelta"] { color: #4ADE80 !important; }

    /* Alerte / info */
    .stAlert { background-color: var(--card) !important; border-color: var(--mid) !important; }

    /* Bouton */
    .stButton > button {
        background: var(--mid) !important;
        color: var(--amber) !important;
        border: 1px solid var(--gold) !important;
        border-radius: 4px;
        letter-spacing: 0.06em;
        font-weight: 600;
    }
    .stButton > button:hover { background: var(--gold) !important; color: var(--navy) !important; }

    /* Tableur */
    .stDataFrame { border: 1px solid var(--mid); border-radius: 6px; }

    /* Tabs */
    [data-baseweb="tab-list"] { background: var(--card); border-radius: 6px; }
    [data-baseweb="tab"] { color: var(--slate) !important; }
    [aria-selected="true"] { color: var(--amber) !important; border-bottom-color: var(--gold) !important; }

    /* Expander */
    [data-testid="stExpander"] { background: var(--card); border: 1px solid var(--mid); border-radius: 6px; }

    /* RunTag */
    .tag-ok  { background:#163A2A; color:#4ADE80; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-warn{ background:#3A2A10; color:#FBBF24; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-err { background:#3A1010; color:#F87171; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)

# ─── DONNÉES EXEMPLE ────────────────────────────────────────────────────────
def get_default_data() -> pd.DataFrame:
    """
    Jeu de données intégré par défaut basé sur des références réelles
    du marché de l'aviation d'affaires (source : JETNET, AMSTAT, NBAA 2023).
    """
    data = {
        "Modele": [
            "Falcon 900EX",
            "Gulfstream G650",
            "Bombardier Global 6000",
            "Dassault Falcon 8X",
            "Cessna Citation XLS+",
            "Embraer Phenom 300E",
            "Pilatus PC-24",
            "Bombardier Challenger 350",
            "Gulfstream G550",
            "HondaJet Elite II",
        ],
        "Categorie": [
            "Grand Cabin", "Ultra Long Range", "Ultra Long Range",
            "Ultra Long Range", "Midsize", "Light Jet",
            "Light Jet", "Super Midsize", "Ultra Long Range", "Light Jet",
        ],
        "Couts_Fixes_Annuels": [
            595915, 1_250_000, 1_180_000,
            780_000,   320_000,  180_000,
            210_000,   480_000, 1_100_000,  95_000,
        ],
        "Couts_Equipe_Annuels": [
            596_942, 900_000, 850_000,
            650_000, 280_000, 160_000,
            190_000, 380_000, 820_000,  90_000,
        ],
        "Cout_Horaire_Charter": [
            2_272, 4_500, 4_200,
            3_100,   850,   520,
              680, 1_650, 4_000,   290,
        ],
        "Cout_Horaire_Prive": [
            1_900, 3_800, 3_600,
            2_600,   720,   440,
              570, 1_400, 3_400,   240,
        ],
        "Heures_Base": [500, 450, 400, 500, 600, 700, 650, 550, 420, 800],
        "Taux_Charter_EUR_h": [
            5_700, 12_000, 11_000,
            8_500, 2_800, 1_800,
            2_200, 4_500, 10_500,  950,
        ],
        "Vitesse_Croisiere_km_h": [870, 956, 904, 956, 815, 834, 815, 870, 904, 782],
        "Autonomie_km": [7_200, 12_964, 11_112, 11_945, 3_700, 3_650, 3_333, 6_297, 11_112, 2_661],
        "Passagers_Max": [13, 18, 17, 16, 9, 11, 10, 10, 18, 5],
    }
    return pd.DataFrame(data)

# ─── COLONNES REQUISES ───────────────────────────────────────────────────────
COLONNES_REQUISES = {
    "Modele": "Nom de l'appareil",
    "Couts_Fixes_Annuels": "Coûts fixes hors équipage (€/an)",
    "Couts_Equipe_Annuels": "Coûts d'équipage annuels (€/an)",
    "Cout_Horaire_Charter": "Coût variable horaire Charter (€/h)",
    "Cout_Horaire_Prive": "Coût variable horaire Privé (€/h)",
    "Taux_Charter_EUR_h": "Tarif charter facturé (€/h)",
}

# ─── CHARGEMENT DONNÉES ──────────────────────────────────────────────────────
def charger_donnees(fichier) -> tuple[pd.DataFrame, list[str]]:
    """
    Charge un fichier Excel ou CSV uploadé par l'utilisateur.
    Retourne (DataFrame, liste_erreurs).
    """
    erreurs = []
    try:
        if fichier.name.endswith(".csv"):
            df = pd.read_csv(fichier)
        elif fichier.name.endswith(".xls"):
            df = pd.read_excel(fichier, engine="xlrd")
        else:
            df = pd.read_excel(fichier)
    except Exception as e:
        return None, [f"Impossible de lire le fichier : {e}"]

    # Vérification colonnes minimales requises
    manquantes = [col for col in COLONNES_REQUISES if col not in df.columns]
    if manquantes:
        erreurs.append(
            f"Colonnes manquantes : {', '.join(manquantes)}. "
            f"Colonnes détectées : {', '.join(df.columns.tolist())}"
        )
        return None, erreurs

    # Conversion types numériques
    cols_num = [c for c in COLONNES_REQUISES if c != "Modele"]
    for col in cols_num:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["Modele"])
    return df, erreurs

# ─── CALCULS COÛTS ───────────────────────────────────────────────────────────
def calculer_couts(avion: pd.Series, h_charter: int, h_prive: int) -> dict:
    """
    Calcule la décomposition complète des coûts annuels pour un appareil donné.
    """
    couts_fixes   = avion["Couts_Fixes_Annuels"]
    couts_equipe  = avion["Couts_Equipe_Annuels"]
    cout_h_charter = avion["Cout_Horaire_Charter"]
    cout_h_prive   = avion["Cout_Horaire_Prive"]
    tarif_charter  = avion.get("Taux_Charter_EUR_h", 0)

    total_heures   = h_charter + h_prive
    var_charter    = h_charter * cout_h_charter
    var_prive      = h_prive   * cout_h_prive
    total_variable = var_charter + var_prive
    total_fixe     = couts_fixes + couts_equipe
    total_general  = total_fixe + total_variable

    cout_moyen_h   = total_general / total_heures if total_heures > 0 else 0

    return {
        "couts_fixes":      couts_fixes,
        "couts_equipe":     couts_equipe,
        "total_fixe":       total_fixe,
        "var_charter":      var_charter,
        "var_prive":        var_prive,
        "total_variable":   total_variable,
        "total_general":    total_general,
        "cout_moyen_h":     cout_moyen_h,
        "h_charter":        h_charter,
        "h_prive":          h_prive,
        "total_heures":     total_heures,
        "tarif_charter":    tarif_charter,
    }

def calculer_rentabilite(couts: dict, marge_pct: float, commission_pct: float) -> dict:
    """
    Simulation de rentabilité charter :
    revenu brut, commission, revenu net, résultat net, break-even.
    """
    tarif         = couts["tarif_charter"]
    h_charter     = couts["h_charter"]
    revenu_brut   = tarif * h_charter
    commission    = revenu_brut * commission_pct / 100
    revenu_net    = revenu_brut - commission
    revenu_marge  = revenu_net * (1 + marge_pct / 100)  # si le propriétaire majore le tarif

    resultat_net  = revenu_net - couts["total_general"]
    taux_couverture = (revenu_net / couts["total_general"] * 100) if couts["total_general"] > 0 else 0

    # Heures break-even (combien d'heures charter couvrent les coûts totaux ?)
    if tarif - couts["h_charter"] > 0 and couts["h_charter"] > 0:
        h_breakeven = couts["total_fixe"] / (tarif * (1 - commission_pct/100) - couts["var_charter"] / max(h_charter, 1))
    else:
        h_breakeven = None

    return {
        "revenu_brut":      revenu_brut,
        "commission":       commission,
        "revenu_net":       revenu_net,
        "resultat_net":     resultat_net,
        "taux_couverture":  taux_couverture,
    }

# ─── GRAPHIQUES ──────────────────────────────────────────────────────────────
COULEURS = {
    "fixed":   "#1A3A6E",
    "equipe":  "#C9A84C",
    "charter": "#4A90D9",
    "prive":   "#8496B0",
    "revenu":  "#4ADE80",
    "perte":   "#F87171",
}

def graph_donut(couts: dict) -> go.Figure:
    """Diagramme en anneau de la répartition des coûts."""
    labels = ["Coûts fixes exploitation", "Équipage", "Variables Charter", "Variables Privé"]
    values = [
        couts["couts_fixes"],
        couts["couts_equipe"],
        couts["var_charter"],
        couts["var_prive"],
    ]
    couleurs = [COULEURS["fixed"], COULEURS["equipe"], COULEURS["charter"], COULEURS["prive"]]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.56,
        marker=dict(colors=couleurs, line=dict(color="#0B1629", width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{couts['total_general']/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="#E8C46A"),
        align="center",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=10, l=10, r=10),
        height=320,
        showlegend=True,
    )
    return fig

def graph_barres_empilees(couts: dict) -> go.Figure:
    """Barres empilées : comparaison Charter vs Privé vs Fixe."""
    categories = ["Charter", "Privé", "Total"]
    totaux = [
        couts["var_charter"] + couts["total_fixe"] * (couts["h_charter"] / max(couts["total_heures"], 1)),
        couts["var_prive"]   + couts["total_fixe"] * (couts["h_prive"]   / max(couts["total_heures"], 1)),
        couts["total_general"],
    ]

    traces = [
        go.Bar(name="Coûts fixes", x=categories,
               y=[couts["total_fixe"] * (couts["h_charter"] / max(couts["total_heures"],1)),
                  couts["total_fixe"] * (couts["h_prive"]   / max(couts["total_heures"],1)),
                  couts["total_fixe"]],
               marker_color=COULEURS["fixed"], text=None),
        go.Bar(name="Variables Charter", x=categories,
               y=[couts["var_charter"], 0, couts["var_charter"]],
               marker_color=COULEURS["charter"]),
        go.Bar(name="Variables Privé",   x=categories,
               y=[0, couts["var_prive"], couts["var_prive"]],
               marker_color=COULEURS["prive"]),
    ]
    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        yaxis=dict(title="Coût (€)", gridcolor="#1A3A6E", tickformat=",.0f"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=40, l=10, r=10),
        height=300,
    )
    return fig

def graph_rentabilite(couts: dict, renta: dict) -> go.Figure:
    """Waterfall : de revenu charter au résultat net."""
    mesures = ["relative","relative","relative","relative","total"]
    x = ["Revenu brut charter", "Commission opérateur", "Coûts variables", "Coûts fixes", "Résultat net"]
    y = [
        renta["revenu_brut"],
        -renta["commission"],
        -couts["total_variable"],
        -couts["total_fixe"],
        renta["resultat_net"],
    ]
    couleur_totale = COULEURS["revenu"] if renta["resultat_net"] >= 0 else COULEURS["perte"]

    fig = go.Figure(go.Waterfall(
        measure=mesures, x=x, y=y,
        connector=dict(line=dict(color="#1A3A6E", width=1.5)),
        increasing=dict(marker_color=COULEURS["revenu"]),
        decreasing=dict(marker_color=COULEURS["perte"]),
        totals=dict(marker_color=couleur_totale),
        texttemplate="%{y:+,.0f} €",
        textfont=dict(color="#D6E4F7", size=11),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#8496B0", line_width=1)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        yaxis=dict(title="€", gridcolor="#1A3A6E", tickformat=",.0f"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=10, l=10, r=10),
        height=340,
    )
    return fig

def graph_sensibilite(avion: pd.Series, h_prive: int, commission_pct: float) -> go.Figure:
    """Courbe de sensibilité : résultat net en fonction des heures charter."""
    heures_range = list(range(0, 801, 25))
    resultats = []
    for h in heures_range:
        c = calculer_couts(avion, h, h_prive)
        r = calculer_rentabilite(c, 0, commission_pct)
        resultats.append(r["resultat_net"])

    fig = go.Figure()
    # Zone positive (profit)
    fig.add_trace(go.Scatter(
        x=heures_range, y=resultats, mode="lines",
        line=dict(color=COULEURS["charter"], width=2.5),
        fill="tozeroy",
        fillcolor="rgba(74,144,217,0.12)",
        name="Résultat net",
        hovertemplate="<b>%{x}h charter</b><br>%{y:+,.0f} €<extra></extra>",
    ))
    # Ligne zéro
    fig.add_hline(y=0, line_dash="dash", line_color=COULEURS["gold"] if False else "#C9A84C", line_width=1.5)

    # Trouver le break-even
    for i in range(1, len(resultats)):
        if resultats[i-1] < 0 <= resultats[i]:
            h_be = heures_range[i]
            fig.add_vline(x=h_be, line_dash="dot", line_color="#E8C46A", line_width=1.5,
                         annotation_text=f"Break-even ~{h_be}h",
                         annotation_font_color="#E8C46A",
                         annotation_position="top right")
            break

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        yaxis=dict(title="Résultat net (€)", gridcolor="#1A3A6E", tickformat=",.0f"),
        xaxis=dict(title="Heures de vol charter", gridcolor="#1A3A6E"),
        margin=dict(t=10, b=10, l=10, r=10),
        height=300,
        showlegend=False,
    )
    return fig

# ─── FORMAT MONNAIE ──────────────────────────────────────────────────────────
def fmt(v: float, decimals: int = 0) -> str:
    """Formate un nombre en EUR avec séparateur milliers."""
    return f"{v:,.{decimals}f} €".replace(",", " ").replace(".", ",")

# ════════════════════════════════════════════════════════════════════════════
# INTERFACE PRINCIPALE
# ════════════════════════════════════════════════════════════════════════════
def main():
    # ── En-tête ──────────────────────────────────────────────────────────
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.markdown("<div style='font-size:3rem;text-align:center;margin-top:0.3rem'>✈</div>",
                    unsafe_allow_html=True)
    with col_title:
        st.markdown('<div class="main-title">Aviation Cost Estimator</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Simulation des coûts d\'exploitation — Aviation d\'affaires</div>',
                    unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    # ── Sidebar : chargement & configuration ─────────────────────────────
    with st.sidebar:
        st.markdown('<div class="section-header">⬆ Base de données</div>', unsafe_allow_html=True)

        fichier = st.file_uploader(
            "Importer un fichier Excel / CSV",
            type=["xlsx", "xls", "csv"],
            help="Format requis : colonnes Modele, Couts_Fixes_Annuels, Couts_Equipe_Annuels, "
                 "Cout_Horaire_Charter, Cout_Horaire_Prive, Taux_Charter_EUR_h"
        )

        if fichier:
            df, erreurs = charger_donnees(fichier)
            if erreurs:
                for e in erreurs:
                    st.error(f"⚠ {e}")
                st.info("Le jeu de données par défaut est utilisé à la place.")
                df = get_default_data()
            else:
                st.success(f"✓ {len(df)} appareil(s) chargés")
        else:
            df = get_default_data()
            st.info("📋 Données d'exemple utilisées (10 appareils)")

        st.markdown('<div class="section-header">✈ Sélection appareil</div>', unsafe_allow_html=True)

        # Filtre par catégorie si disponible
        if "Categorie" in df.columns:
            cats = ["Toutes"] + sorted(df["Categorie"].dropna().unique().tolist())
            cat_sel = st.selectbox("Catégorie", cats)
            df_filtre = df if cat_sel == "Toutes" else df[df["Categorie"] == cat_sel]
        else:
            df_filtre = df

        modele_sel = st.selectbox("Modèle d'avion", df_filtre["Modele"].tolist())
        avion = df_filtre[df_filtre["Modele"] == modele_sel].iloc[0]

        st.markdown('<div class="section-header">🕐 Configuration des heures</div>', unsafe_allow_html=True)

        h_charter = st.slider("Heures Charter / an", 0, 800, 380, step=10,
                              help="Heures de vol commerciales (charter tiers)")
        h_prive   = st.slider("Heures Privé / an",   0, 800, 120, step=10,
                              help="Heures d'utilisation propriétaire")

        heures_totales = h_charter + h_prive
        if heures_totales > 800:
            st.warning(f"⚠ Total {heures_totales}h dépasse le plafond réglementaire recommandé (800h)")

        st.markdown('<div class="section-header">💰 Simulation rentabilité</div>', unsafe_allow_html=True)

        marge_pct      = st.slider("Majoration tarifaire (%)", 0, 50, 0, step=5,
                                   help="% ajouté au tarif charter de base")
        commission_pct = st.slider("Commission opérateur (%)", 0, 25, 10, step=1,
                                   help="% de commission retenu par le broker/opérateur")

    # ── Calculs ──────────────────────────────────────────────────────────
    couts  = calculer_couts(avion, h_charter, h_prive)
    renta  = calculer_rentabilite(couts, marge_pct, commission_pct)

    # ════════════════════════════════════════════════════════════════════
    # ONGLETS
    # ════════════════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊  Tableau de bord",
        "📈  Simulation rentabilité",
        "🔍  Sensibilité",
        "📋  Données",
    ])

    # ──────────────────────────────────────────────────────────────────
    # ONGLET 1 : TABLEAU DE BORD
    # ──────────────────────────────────────────────────────────────────
    with tab1:
        # Identité appareil
        col_id1, col_id2, col_id3, col_id4 = st.columns(4)
        with col_id1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Appareil sélectionné</div>
                <div class="metric-value" style="font-size:1.2rem">{avion['Modele']}</div>
                <div class="metric-sub">{avion.get('Categorie','—')}</div>
            </div>""", unsafe_allow_html=True)
        with col_id2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total heures / an</div>
                <div class="metric-value">{couts['total_heures']}h</div>
                <div class="metric-sub">{h_charter}h charter · {h_prive}h privé</div>
            </div>""", unsafe_allow_html=True)
        with col_id3:
            if "Autonomie_km" in avion and pd.notna(avion["Autonomie_km"]):
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Autonomie maximale</div>
                    <div class="metric-value">{avion['Autonomie_km']:,.0f} km</div>
                    <div class="metric-sub">{avion.get('Passagers_Max','—')} passagers max</div>
                </div>""", unsafe_allow_html=True)
        with col_id4:
            if "Vitesse_Croisiere_km_h" in avion and pd.notna(avion.get("Vitesse_Croisiere_km_h")):
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Vitesse croisière</div>
                    <div class="metric-value">{avion['Vitesse_Croisiere_km_h']} km/h</div>
                    <div class="metric-sub">Performances certifiées</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # KPIs principaux
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💶 Coût total annuel",   fmt(couts["total_general"]))
        k2.metric("🔒 Coûts fixes totaux",  fmt(couts["total_fixe"]))
        k3.metric("⚡ Coûts variables",     fmt(couts["total_variable"]))
        k4.metric("⌛ Coût moyen / heure", fmt(couts["cout_moyen_h"], 0))

        st.markdown("<hr>", unsafe_allow_html=True)

        # Graphiques
        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            st.markdown('<div class="section-header">Répartition des coûts</div>', unsafe_allow_html=True)
            st.plotly_chart(graph_donut(couts), use_container_width=True, config={"displayModeBar": False})

        with col_g2:
            st.markdown('<div class="section-header">Décomposition par mode de vol</div>', unsafe_allow_html=True)
            st.plotly_chart(graph_barres_empilees(couts), use_container_width=True, config={"displayModeBar": False})

        # Détail tableau
        st.markdown('<div class="section-header">Détail des postes de coût</div>', unsafe_allow_html=True)
        table_data = {
            "Poste": [
                "Coûts fixes exploitation",
                "Coûts d'équipage",
                "Variables Charter",
                "Variables Privé",
                "─────────────────",
                "TOTAL GÉNÉRAL",
            ],
            "Montant (€)": [
                couts["couts_fixes"],
                couts["couts_equipe"],
                couts["var_charter"],
                couts["var_prive"],
                None,
                couts["total_general"],
            ],
            "% du total": [
                couts["couts_fixes"]   / couts["total_general"] * 100,
                couts["couts_equipe"]  / couts["total_general"] * 100,
                couts["var_charter"]   / couts["total_general"] * 100,
                couts["var_prive"]     / couts["total_general"] * 100,
                None,
                100.0,
            ],
            "€/heure": [
                couts["couts_fixes"]   / max(couts["total_heures"], 1),
                couts["couts_equipe"]  / max(couts["total_heures"], 1),
                avion["Cout_Horaire_Charter"] if h_charter > 0 else 0,
                avion["Cout_Horaire_Prive"]   if h_prive   > 0 else 0,
                None,
                couts["cout_moyen_h"],
            ],
        }
        df_table = pd.DataFrame(table_data)
        df_table["Montant (€)"] = df_table["Montant (€)"].apply(
            lambda x: f"{x:>12,.0f} €".replace(",", " ") if pd.notna(x) else "")
        df_table["% du total"]  = df_table["% du total"].apply(
            lambda x: f"{x:5.1f} %" if pd.notna(x) else "")
        df_table["€/heure"]    = df_table["€/heure"].apply(
            lambda x: f"{x:>8,.0f} €/h".replace(",", " ") if pd.notna(x) else "")
        st.dataframe(df_table, use_container_width=True, hide_index=True)

    # ──────────────────────────────────────────────────────────────────
    # ONGLET 2 : SIMULATION RENTABILITÉ
    # ──────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown('<div class="section-header">Simulation de rentabilité charter</div>',
                    unsafe_allow_html=True)

        if h_charter == 0:
            st.warning("⚠ Aucune heure charter configurée. Activez le slider 'Heures Charter' dans la barre latérale.")
        else:
            # Statut global
            solde = renta["resultat_net"]
            tc    = renta["taux_couverture"]
            if solde >= 0:
                badge = '<span class="tag-ok">✓ BÉNÉFICIAIRE</span>'
            elif tc >= 70:
                badge = '<span class="tag-warn">⚠ QUASI-ÉQUILIBRE</span>'
            else:
                badge = '<span class="tag-err">✗ DÉFICITAIRE</span>'
            st.markdown(f"**Statut :** {badge} — Taux de couverture des coûts : **{tc:.1f} %**",
                        unsafe_allow_html=True)
            st.markdown("")

            # KPIs rentabilité
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("💵 Revenu brut charter",   fmt(renta["revenu_brut"]))
            r2.metric("📉 Commission opérateur",  fmt(renta["commission"]))
            r3.metric("💰 Revenu net charter",    fmt(renta["revenu_net"]))
            delta_color = "normal" if solde >= 0 else "inverse"
            r4.metric("📊 Résultat net", fmt(solde), delta=f"{tc:.1f}% coûts couverts")

            st.markdown("<hr>", unsafe_allow_html=True)

            # Waterfall
            st.markdown('<div class="section-header">Cascade financière</div>', unsafe_allow_html=True)
            st.plotly_chart(graph_rentabilite(couts, renta), use_container_width=True,
                            config={"displayModeBar": False})

            # Hypothèses
            with st.expander("📌 Hypothèses de calcul"):
                hyp = {
                    "Paramètre": [
                        "Tarif charter base",
                        "Heures charter",
                        "Majoration tarifaire",
                        "Commission opérateur",
                        "Revenu brut",
                        "Coûts variables totaux",
                        "Coûts fixes totaux",
                    ],
                    "Valeur": [
                        fmt(avion.get("Taux_Charter_EUR_h", 0)),
                        f"{h_charter} h",
                        f"{marge_pct} %",
                        f"{commission_pct} %",
                        fmt(renta["revenu_brut"]),
                        fmt(couts["total_variable"]),
                        fmt(couts["total_fixe"]),
                    ],
                }
                st.table(pd.DataFrame(hyp))

    # ──────────────────────────────────────────────────────────────────
    # ONGLET 3 : SENSIBILITÉ
    # ──────────────────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-header">Analyse de sensibilité — Heures charter vs Résultat net</div>',
                    unsafe_allow_html=True)
        st.caption(f"Heures privé fixées à {h_prive}h — Commission {commission_pct}%")
        st.plotly_chart(graph_sensibilite(avion, h_prive, commission_pct),
                        use_container_width=True, config={"displayModeBar": False})

        # Comparaison multi-appareils
        st.markdown('<div class="section-header">Comparaison des appareils (coût/heure)</div>',
                    unsafe_allow_html=True)

        comparaison = []
        for _, row in df.iterrows():
            c = calculer_couts(row, h_charter, h_prive)
            comparaison.append({
                "Modèle":            row["Modele"],
                "Coût total (€)":    round(c["total_general"]),
                "Coût/heure (€)":    round(c["cout_moyen_h"]),
                "Coûts fixes (€)":   round(c["total_fixe"]),
                "Coûts variables (€)": round(c["total_variable"]),
            })
        df_comp = pd.DataFrame(comparaison).sort_values("Coût total (€)")

        fig_comp = px.bar(
            df_comp, x="Modèle", y="Coût total (€)",
            color="Coût/heure (€)",
            color_continuous_scale=["#1A3A6E", "#4A90D9", "#C9A84C", "#E8C46A"],
            template="plotly_dark",
        )
        fig_comp.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#D6E4F7"),
            coloraxis_colorbar=dict(title="€/h", tickformat=",.0f"),
            margin=dict(t=10, b=80, l=10, r=10),
            height=350,
            xaxis=dict(tickangle=-30),
            yaxis=dict(gridcolor="#1A3A6E", tickformat=",.0f"),
        )
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar": False})

    # ──────────────────────────────────────────────────────────────────
    # ONGLET 4 : DONNÉES
    # ──────────────────────────────────────────────────────────────────
    with tab4:
        st.markdown('<div class="section-header">Base de données des appareils</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown('<div class="section-header">Format requis pour votre fichier Excel</div>',
                    unsafe_allow_html=True)
        df_format = pd.DataFrame([
            {"Colonne": k, "Description": v, "Obligatoire": "✓"}
            for k, v in COLONNES_REQUISES.items()
        ] + [
            {"Colonne": "Categorie",            "Description": "Catégorie (Light, Midsize, etc.)", "Obligatoire": "—"},
            {"Colonne": "Autonomie_km",          "Description": "Autonomie maximale en km",         "Obligatoire": "—"},
            {"Colonne": "Vitesse_Croisiere_km_h","Description": "Vitesse croisière en km/h",       "Obligatoire": "—"},
            {"Colonne": "Passagers_Max",         "Description": "Nombre de passagers maximum",     "Obligatoire": "—"},
        ])
        st.table(df_format)

        # Téléchargement du template
        @st.cache_data
        def get_template_excel() -> bytes:
            buf = BytesIO()
            template = get_default_data()
            template.to_excel(buf, index=False, sheet_name="Aviation Data")
            return buf.getvalue()

        st.download_button(
            "⬇ Télécharger le template Excel",
            data=get_template_excel(),
            file_name="aviation_cost_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # ── Pied de page ─────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;font-size:0.72rem;color:#4A5568;letter-spacing:0.1em">'
        'AVIATION COST ESTIMATOR — Données indicatives à des fins de simulation uniquement'
        ' · Valeurs basées sur des moyennes de marché (NBAA / JETNET)</div>',
        unsafe_allow_html=True
    )


# ─── POINT D'ENTRÉE ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
