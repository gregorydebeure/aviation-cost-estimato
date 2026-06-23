
"""
✈️ Aviation Cost Estimator — Streamlit Application v2
Estimation and simulation of business aircraft operating costs.
Includes AI-powered PDF budget import via Claude API.
"""
 
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import base64
import json
import requests
import warnings
warnings.filterwarnings("ignore")
 
# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Aviation Cost Estimator",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
# ─── CSS STYLES ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    :root {
        --navy:   #0B1629;
        --deep:   #112244;
        --mid:    #1A3A6E;
        --gold:   #C9A84C;
        --amber:  #E8C46A;
        --slate:  #8496B0;
        --light:  #D6E4F7;
        --card:   #13233F;
        --green:  #163A2A;
        --greentext: #4ADE80;
    }
    .stApp {
        background-color: var(--navy) !important;
        color: var(--light) !important;
        font-family: 'Segoe UI', system-ui, sans-serif;
    }
    [data-testid="stSidebar"] {
        background-color: var(--deep) !important;
        border-right: 1px solid var(--mid);
    }
    [data-testid="stSidebar"] * { color: var(--light) !important; }
    .main-title {
        font-size: 2rem; font-weight: 700; letter-spacing: 0.08em;
        color: var(--amber); text-transform: uppercase; margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 0.85rem; color: var(--slate); letter-spacing: 0.12em;
        text-transform: uppercase; margin-bottom: 1.5rem;
    }
    .metric-card {
        background: var(--card); border: 1px solid var(--mid);
        border-left: 3px solid var(--gold); border-radius: 6px;
        padding: 1rem 1.2rem; margin-bottom: 0.8rem;
    }
    .metric-label { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--slate); margin-bottom: 0.3rem; }
    .metric-value { font-size: 1.7rem; font-weight: 700; color: var(--amber); }
    .metric-sub   { font-size: 0.78rem; color: var(--slate); margin-top: 0.1rem; }
    .section-header {
        font-size: 0.7rem; letter-spacing: 0.18em; text-transform: uppercase;
        color: var(--gold); border-bottom: 1px solid var(--mid);
        padding-bottom: 0.4rem; margin: 1.2rem 0 0.8rem 0;
    }
    hr { border-color: var(--mid) !important; }
    .stSelectbox label, .stSlider label, .stNumberInput label,
    .stFileUploader label { color: var(--light) !important; font-size: 0.82rem; }
    [data-testid="stMetricValue"] { color: var(--amber) !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { color: var(--slate) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; }
    [data-testid="stMetricDelta"] { color: #4ADE80 !important; }
    .stAlert { background-color: var(--card) !important; border-color: var(--mid) !important; }
    .stButton > button {
        background: var(--mid) !important; color: var(--amber) !important;
        border: 1px solid var(--gold) !important; border-radius: 4px;
        letter-spacing: 0.06em; font-weight: 600;
    }
    .stButton > button:hover { background: var(--gold) !important; color: var(--navy) !important; }
    .stDataFrame { border: 1px solid var(--mid); border-radius: 6px; }
    [data-baseweb="tab-list"] { background: var(--card); border-radius: 6px; }
    [data-baseweb="tab"] { color: var(--slate) !important; }
    [aria-selected="true"] { color: var(--amber) !important; border-bottom-color: var(--gold) !important; }
    [data-testid="stExpander"] { background: var(--card); border: 1px solid var(--mid); border-radius: 6px; }
    .tag-ok   { background:#163A2A; color:#4ADE80; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-warn { background:#3A2A10; color:#FBBF24; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-err  { background:#3A1010; color:#F87171; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
 
    /* PDF import specific */
    .pdf-drop-zone {
        border: 2px dashed var(--mid); border-radius: 8px;
        padding: 2rem; text-align: center; color: var(--slate);
        background: var(--card); margin: 1rem 0;
    }
    .extracted-card {
        background: var(--card); border: 1px solid var(--mid);
        border-left: 3px solid var(--greentext); border-radius: 6px;
        padding: 1rem 1.2rem; margin: 0.5rem 0;
    }
    .extracted-label { font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--slate); }
    .extracted-value { font-size: 1.1rem; font-weight: 600; color: var(--greentext); }
    .step-badge {
        display: inline-block; background: var(--mid); color: var(--amber);
        border-radius: 50%; width: 24px; height: 24px; text-align: center;
        line-height: 24px; font-size: 0.75rem; font-weight: 700;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)
 
# ─── SESSION STATE INIT ──────────────────────────────────────────────────────
if "database" not in st.session_state:
    st.session_state["database"] = None   # Will hold the live DataFrame
if "extracted" not in st.session_state:
    st.session_state["extracted"] = None  # Last PDF extraction result
 
# ─── DEFAULT DATASET ────────────────────────────────────────────────────────
def get_default_data() -> pd.DataFrame:
    """Built-in sample dataset (JETNET / AMSTAT / NBAA 2023 references)."""
    data = {
        "Modele": [
            "Falcon 900EX", "Gulfstream G650", "Bombardier Global 6000",
            "Dassault Falcon 8X", "Cessna Citation XLS+", "Embraer Phenom 300E",
            "Pilatus PC-24", "Bombardier Challenger 350", "Gulfstream G550", "HondaJet Elite II",
        ],
        "Categorie": [
            "Grand Cabin", "Ultra Long Range", "Ultra Long Range", "Ultra Long Range",
            "Midsize", "Light Jet", "Light Jet", "Super Midsize", "Ultra Long Range", "Light Jet",
        ],
        "Couts_Fixes_Annuels":  [595915, 1_250_000, 1_180_000, 780_000, 320_000, 180_000, 210_000, 480_000, 1_100_000, 95_000],
        "Couts_Equipe_Annuels": [596_942, 900_000, 850_000, 650_000, 280_000, 160_000, 190_000, 380_000, 820_000, 90_000],
        "Cout_Horaire_Charter": [2_272, 4_500, 4_200, 3_100, 850, 520, 680, 1_650, 4_000, 290],
        "Cout_Horaire_Prive":   [1_900, 3_800, 3_600, 2_600, 720, 440, 570, 1_400, 3_400, 240],
        "Heures_Base":          [500, 450, 400, 500, 600, 700, 650, 550, 420, 800],
        "Taux_Charter_EUR_h":   [5_700, 12_000, 11_000, 8_500, 2_800, 1_800, 2_200, 4_500, 10_500, 950],
        "Vitesse_Croisiere_km_h": [870, 956, 904, 956, 815, 834, 815, 870, 904, 782],
        "Autonomie_km":         [7_200, 12_964, 11_112, 11_945, 3_700, 3_650, 3_333, 6_297, 11_112, 2_661],
        "Passagers_Max":        [13, 18, 17, 16, 9, 11, 10, 10, 18, 5],
    }
    return pd.DataFrame(data)
 
def get_active_db() -> pd.DataFrame:
    """Returns the live database (session) or the default one."""
    if st.session_state["database"] is not None:
        return st.session_state["database"]
    return get_default_data()
 
# ─── REQUIRED COLUMNS ────────────────────────────────────────────────────────
REQUIRED_COLUMNS = {
    "Modele":               "Aircraft name",
    "Couts_Fixes_Annuels":  "Fixed costs excl. crew (€/year)",
    "Couts_Equipe_Annuels": "Annual crew costs (€/year)",
    "Cout_Horaire_Charter": "Variable charter hourly cost (€/h)",
    "Cout_Horaire_Prive":   "Variable private hourly cost (€/h)",
    "Taux_Charter_EUR_h":   "Charter rate billed to client (€/h)",
}
 
# ─── DATA LOADING ────────────────────────────────────────────────────────────
def load_data(file) -> tuple:
    errors = []
    try:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        elif file.name.endswith(".xls"):
            df = pd.read_excel(file, engine="xlrd")
        else:
            df = pd.read_excel(file)
    except Exception as e:
        return None, [f"Cannot read file: {e}"]
 
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}. Detected: {', '.join(df.columns.tolist())}")
        return None, errors
 
    for col in [c for c in REQUIRED_COLUMNS if c != "Modele"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["Modele"]), errors
 
# ─── COST CALCULATIONS ───────────────────────────────────────────────────────
def calculate_costs(aircraft: pd.Series, h_charter: int, h_private: int) -> dict:
    fixed_costs    = aircraft["Couts_Fixes_Annuels"]
    crew_costs     = aircraft["Couts_Equipe_Annuels"]
    charter_rate_h = aircraft["Cout_Horaire_Charter"]
    private_rate_h = aircraft["Cout_Horaire_Prive"]
    charter_tariff = aircraft.get("Taux_Charter_EUR_h", 0)
    total_hours    = h_charter + h_private
    var_charter    = h_charter * charter_rate_h
    var_private    = h_private * private_rate_h
    total_variable = var_charter + var_private
    total_fixed    = fixed_costs + crew_costs
    grand_total    = total_fixed + total_variable
    avg_cost_h     = grand_total / total_hours if total_hours > 0 else 0
    return dict(fixed_costs=fixed_costs, crew_costs=crew_costs, total_fixed=total_fixed,
                var_charter=var_charter, var_private=var_private, total_variable=total_variable,
                grand_total=grand_total, avg_cost_h=avg_cost_h, h_charter=h_charter,
                h_private=h_private, total_hours=total_hours, charter_tariff=charter_tariff)
 
def calculate_profitability(costs: dict, commission_pct: float, custom_rate: float = None) -> dict:
    # Use custom rate if provided, otherwise fall back to database rate
    tariff        = custom_rate if (custom_rate is not None and custom_rate > 0) else costs["charter_tariff"]
    h_charter     = costs["h_charter"]
    gross_revenue = tariff * h_charter
    commission    = gross_revenue * commission_pct / 100
    net_revenue   = gross_revenue - commission
    net_result    = net_revenue - costs["grand_total"]
    coverage_rate = (net_revenue / costs["grand_total"] * 100) if costs["grand_total"] > 0 else 0
    return dict(gross_revenue=gross_revenue, commission=commission,
                net_revenue=net_revenue, net_result=net_result, coverage_rate=coverage_rate,
                effective_rate=tariff)
 
# ─── CHARTS ──────────────────────────────────────────────────────────────────
COLORS = {"fixed":"#1A3A6E","crew":"#C9A84C","charter":"#4A90D9",
          "private":"#8496B0","profit":"#4ADE80","loss":"#F87171"}
 
def chart_donut(costs):
    labels = ["Fixed Operating Costs","Crew Costs","Charter Variable","Private Variable"]
    values = [costs["fixed_costs"],costs["crew_costs"],costs["var_charter"],costs["var_private"]]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.56,
        marker=dict(colors=[COLORS["fixed"],COLORS["crew"],COLORS["charter"],COLORS["private"]],
                    line=dict(color="#0B1629",width=2)),
        textinfo="label+percent", textfont=dict(size=11,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>",
    ))
    fig.add_annotation(text=f"<b>{costs['grand_total']/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
                       x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"),align="center")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#D6E4F7"),height=320,
                      legend=dict(orientation="h",yanchor="bottom",y=-0.2,bgcolor="rgba(0,0,0,0)"),
                      margin=dict(t=10,b=10,l=10,r=10))
    return fig
 
def chart_stacked_bars(costs):
    categories = ["Charter","Private","Total"]
    th = max(costs["total_hours"],1)
    fig = go.Figure(data=[
        go.Bar(name="Fixed Costs",x=categories,marker_color=COLORS["fixed"],
               y=[costs["total_fixed"]*(costs["h_charter"]/th),costs["total_fixed"]*(costs["h_private"]/th),costs["total_fixed"]]),
        go.Bar(name="Charter Variable",x=categories,marker_color=COLORS["charter"],
               y=[costs["var_charter"],0,costs["var_charter"]]),
        go.Bar(name="Private Variable",x=categories,marker_color=COLORS["private"],
               y=[0,costs["var_private"],costs["var_private"]]),
    ])
    fig.update_layout(barmode="stack",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#D6E4F7"),height=300,
                      yaxis=dict(title="Cost (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.35,bgcolor="rgba(0,0,0,0)"),
                      margin=dict(t=10,b=40,l=10,r=10))
    return fig
 
def chart_waterfall(costs, prof):
    measures = ["relative","relative","relative","relative","total"]
    x = ["Gross Charter Revenue","Operator Commission","Variable Costs","Fixed Costs","Net Result"]
    y = [prof["gross_revenue"],-prof["commission"],-costs["total_variable"],-costs["total_fixed"],prof["net_result"]]
    fig = go.Figure(go.Waterfall(
        measure=measures,x=x,y=y,
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=COLORS["profit"]),decreasing=dict(marker_color=COLORS["loss"]),
        totals=dict(marker_color=COLORS["profit"] if prof["net_result"]>=0 else COLORS["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>",
    ))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#D6E4F7"),height=340,
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"),margin=dict(t=10,b=10,l=10,r=10))
    return fig
 
def chart_sensitivity(aircraft, h_private, commission_pct, custom_rate=None):
    hours_range = list(range(0,801,25))
    results = [calculate_profitability(calculate_costs(aircraft,h,h_private),commission_pct,custom_rate)["net_result"] for h in hours_range]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours_range,y=results,mode="lines",
                             line=dict(color=COLORS["charter"],width=2.5),
                             fill="tozeroy",fillcolor="rgba(74,144,217,0.12)",
                             hovertemplate="<b>%{x}h charter</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#C9A84C",line_width=1.5)
    for i in range(1,len(results)):
        if results[i-1]<0<=results[i]:
            h_be=hours_range[i]
            fig.add_vline(x=h_be,line_dash="dot",line_color="#E8C46A",line_width=1.5,
                         annotation_text=f"Break-even ~{h_be}h",annotation_font_color="#E8C46A",
                         annotation_position="top right")
            break
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#D6E4F7"),height=300,showlegend=False,
                      yaxis=dict(title="Net Result (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Charter Flight Hours",gridcolor="#1A3A6E"),
                      margin=dict(t=10,b=10,l=10,r=10))
    return fig
 
def fmt(v: float, decimals: int = 0) -> str:
    return f"€ {v:,.{decimals}f}"
 
# ════════════════════════════════════════════════════════════════════════════
# PDF EXTRACTION VIA CLAUDE API
# ════════════════════════════════════════════════════════════════════════════
 
EXTRACTION_PROMPT = """You are an expert in business aviation finance. 
Analyze this aircraft budget document and extract the key financial figures.
 
Return ONLY a valid JSON object with EXACTLY these fields (use null if not found):
{
  "aircraft_model": "Aircraft name and variant (e.g. Falcon 900EX)",
  "category": "Category (Light Jet / Midsize / Super Midsize / Grand Cabin / Ultra Long Range)",
  "fixed_costs_annual": <number in EUR, excluding crew>,
  "crew_costs_annual": <total annual crew costs in EUR>,
  "variable_cost_charter_per_hour": <variable cost per flight hour in charter mode, EUR>,
  "variable_cost_private_per_hour": <variable cost per flight hour in private/owner mode, EUR>,
  "base_flight_hours": <annual flight hours assumed in the budget>,
  "charter_rate_per_hour": <revenue rate charged to charter clients per hour, EUR>,
  "cruise_speed_kmh": <cruise speed in km/h or null>,
  "range_km": <maximum range in km or null>,
  "max_passengers": <maximum passenger capacity or null>,
  "currency": "EUR",
  "notes": "Any important assumptions or notes from the document"
}
 
Rules:
- All monetary values must be in EUR (convert if needed using rates in the document)
- Return ONLY the JSON, no explanation, no markdown, no code blocks
- If a value cannot be found or calculated, use null"""
 
 
def extract_pdf_with_claude(pdf_bytes: bytes, api_key: str) -> dict:
    """
    Sends the PDF to Claude API and extracts structured budget data.
    Returns a dict with extracted fields or raises an exception.
    """
    # Encode PDF to base64
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
 
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": EXTRACTION_PROMPT,
                    },
                ],
            }
        ],
    }
 
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "pdfs-2024-09-25",
        },
        json=payload,
        timeout=60,
    )
 
    if response.status_code != 200:
        raise ValueError(f"API error {response.status_code}: {response.text[:300]}")
 
    data = response.json()
    raw_text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
 
    # Clean and parse JSON
    clean = raw_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(clean)
 
 
def extracted_to_db_row(ext: dict) -> dict:
    """Converts Claude's extracted dict to a database row."""
    return {
        "Modele":                ext.get("aircraft_model") or "Unknown",
        "Categorie":             ext.get("category") or "Unknown",
        "Couts_Fixes_Annuels":   ext.get("fixed_costs_annual"),
        "Couts_Equipe_Annuels":  ext.get("crew_costs_annual"),
        "Cout_Horaire_Charter":  ext.get("variable_cost_charter_per_hour"),
        "Cout_Horaire_Prive":    ext.get("variable_cost_private_per_hour"),
        "Heures_Base":           ext.get("base_flight_hours"),
        "Taux_Charter_EUR_h":    ext.get("charter_rate_per_hour"),
        "Vitesse_Croisiere_km_h": ext.get("cruise_speed_kmh"),
        "Autonomie_km":          ext.get("range_km"),
        "Passagers_Max":         ext.get("max_passengers"),
    }
 
 
def add_to_database(new_row: dict):
    """Adds or updates an aircraft row in the session database."""
    db = get_active_db().copy()
    model_name = new_row["Modele"]
 
    # Replace if already exists, else append
    if model_name in db["Modele"].values:
        db = db[db["Modele"] != model_name]
 
    new_df = pd.DataFrame([new_row])
    st.session_state["database"] = pd.concat([db, new_df], ignore_index=True)
 
 
# ════════════════════════════════════════════════════════════════════════════
# MAIN INTERFACE
# ════════════════════════════════════════════════════════════════════════════
def main():
    # ── Header ───────────────────────────────────────────────────────────
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.markdown("<div style='font-size:3rem;text-align:center;margin-top:0.3rem'>✈</div>",
                    unsafe_allow_html=True)
    with col_title:
        st.markdown('<div class="main-title">Aviation Cost Estimator</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Operating Cost Simulation — Business Aviation</div>',
                    unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
 
    # ── Sidebar ──────────────────────────────────────────────────────────
    df = get_active_db()
 
    with st.sidebar:
        st.markdown('<div class="section-header">⬆ Database</div>', unsafe_allow_html=True)
 
        uploaded_file = st.file_uploader(
            "Import an Excel / CSV file", type=["xlsx","xls","csv"],
            help="Required columns: Modele, Couts_Fixes_Annuels, Couts_Equipe_Annuels, "
                 "Cout_Horaire_Charter, Cout_Horaire_Prive, Taux_Charter_EUR_h"
        )
        if uploaded_file:
            loaded_df, errors = load_data(uploaded_file)
            if errors:
                for e in errors: st.error(f"⚠ {e}")
                st.info("Using default dataset instead.")
            else:
                st.session_state["database"] = loaded_df
                df = loaded_df
                st.success(f"✓ {len(df)} aircraft loaded")
        else:
            db_count = len(df)
            is_default = st.session_state["database"] is None
            label = f"📋 Sample data ({db_count} aircraft)" if is_default else f"✓ Live database ({db_count} aircraft)"
            st.info(label)
 
        st.markdown('<div class="section-header">✈ Aircraft Selection</div>', unsafe_allow_html=True)
        df = get_active_db()
 
        if "Categorie" in df.columns:
            cats = ["All"] + sorted(df["Categorie"].dropna().unique().tolist())
            cat_sel = st.selectbox("Category", cats)
            df_filtered = df if cat_sel == "All" else df[df["Categorie"] == cat_sel]
        else:
            df_filtered = df
 
        aircraft_sel = st.selectbox("Aircraft Model", df_filtered["Modele"].tolist())
        aircraft = df_filtered[df_filtered["Modele"] == aircraft_sel].iloc[0]
 
        st.markdown('<div class="section-header">🕐 Flight Hours Configuration</div>', unsafe_allow_html=True)
        h_charter = st.slider("Charter Hours / year", 0, 800, 380, step=10,
                              help="Commercial charter flight hours (third-party clients)")
        h_private = st.slider("Private Hours / year",  0, 800, 120, step=10,
                              help="Owner / private use flight hours")
        if h_charter + h_private > 800:
            st.warning(f"⚠ Total {h_charter+h_private}h exceeds regulatory ceiling (800h)")
 
        st.markdown('<div class="section-header">💰 Charter Pricing</div>', unsafe_allow_html=True)
 
        # Show the database rate as reference
        db_rate = float(aircraft.get("Taux_Charter_EUR_h", 0))
        st.caption(f"Reference rate from database: **€ {db_rate:,.0f} / h**")
 
        # Toggle: use custom price or database price
        use_custom = st.toggle("Set a custom charter price", value=False)
 
        if use_custom:
            custom_rate = st.number_input(
                "Your charter price (€ / hour)",
                min_value=0, max_value=100_000,
                value=int(db_rate) if db_rate > 0 else 5000,
                step=100,
                help="The hourly rate you charge your charter clients"
            )
            # Show difference vs database rate
            if db_rate > 0:
                diff = custom_rate - db_rate
                diff_pct = diff / db_rate * 100
                color = "#4ADE80" if diff >= 0 else "#F87171"
                arrow = "▲" if diff >= 0 else "▼"
                st.markdown(f'<span style="color:{color};font-size:0.8rem">{arrow} {diff_pct:+.1f}% vs reference rate</span>',
                            unsafe_allow_html=True)
        else:
            custom_rate = db_rate
 
        commission_pct = st.slider("Operator Commission (%)", 0, 25, 10, step=1,
                                   help="% retained by the broker / operator")
 
    costs = calculate_costs(aircraft, h_charter, h_private)
    prof  = calculate_profitability(costs, commission_pct, custom_rate)
 
    # ════════════════════════════════════════════════════════════════════
    # TABS
    # ════════════════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊  Dashboard",
        "📈  Profitability",
        "🔍  Sensitivity",
        "🤖  Import PDF",
        "📋  Data",
    ])
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 1 : DASHBOARD
    # ──────────────────────────────────────────────────────────────────
    with tab1:
        col_id1, col_id2, col_id3, col_id4 = st.columns(4)
        with col_id1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Selected Aircraft</div>
                <div class="metric-value" style="font-size:1.2rem">{aircraft['Modele']}</div>
                <div class="metric-sub">{aircraft.get('Categorie','—')}</div>
            </div>""", unsafe_allow_html=True)
        with col_id2:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Total Hours / Year</div>
                <div class="metric-value">{costs['total_hours']}h</div>
                <div class="metric-sub">{h_charter}h charter · {h_private}h private</div>
            </div>""", unsafe_allow_html=True)
        with col_id3:
            if "Autonomie_km" in aircraft and pd.notna(aircraft["Autonomie_km"]):
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-label">Maximum Range</div>
                    <div class="metric-value">{aircraft['Autonomie_km']:,.0f} km</div>
                    <div class="metric-sub">{aircraft.get('Passagers_Max','—')} passengers max</div>
                </div>""", unsafe_allow_html=True)
        with col_id4:
            if "Vitesse_Croisiere_km_h" in aircraft and pd.notna(aircraft.get("Vitesse_Croisiere_km_h")):
                st.markdown(f"""<div class="metric-card">
                    <div class="metric-label">Cruise Speed</div>
                    <div class="metric-value">{aircraft['Vitesse_Croisiere_km_h']} km/h</div>
                    <div class="metric-sub">Certified performance</div>
                </div>""", unsafe_allow_html=True)
 
        st.markdown("<hr>", unsafe_allow_html=True)
        k1,k2,k3,k4 = st.columns(4)
        k1.metric("💶 Total Annual Cost",   fmt(costs["grand_total"]))
        k2.metric("🔒 Total Fixed Costs",   fmt(costs["total_fixed"]))
        k3.metric("⚡ Variable Costs",      fmt(costs["total_variable"]))
        k4.metric("⌛ Average Cost / Hour", fmt(costs["avg_cost_h"]))
        st.markdown("<hr>", unsafe_allow_html=True)
 
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown('<div class="section-header">Cost Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_donut(costs), use_container_width=True, config={"displayModeBar":False})
        with col_g2:
            st.markdown('<div class="section-header">Cost by Flight Mode</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_stacked_bars(costs), use_container_width=True, config={"displayModeBar":False})
 
        st.markdown('<div class="section-header">Cost Line Detail</div>', unsafe_allow_html=True)
        table_data = {
            "Line Item": ["Fixed Operating Costs","Crew Costs","Charter Variable Costs","Private Variable Costs","─────────────────────","GRAND TOTAL"],
            "Amount (€)": [costs["fixed_costs"],costs["crew_costs"],costs["var_charter"],costs["var_private"],None,costs["grand_total"]],
            "% of Total": [costs["fixed_costs"]/costs["grand_total"]*100,costs["crew_costs"]/costs["grand_total"]*100,
                           costs["var_charter"]/costs["grand_total"]*100,costs["var_private"]/costs["grand_total"]*100,None,100.0],
            "€ / Hour": [costs["fixed_costs"]/max(costs["total_hours"],1),costs["crew_costs"]/max(costs["total_hours"],1),
                         aircraft["Cout_Horaire_Charter"] if h_charter>0 else 0,
                         aircraft["Cout_Horaire_Prive"] if h_private>0 else 0,None,costs["avg_cost_h"]],
        }
        df_t = pd.DataFrame(table_data)
        df_t["Amount (€)"] = df_t["Amount (€)"].apply(lambda x: f"€ {x:>12,.0f}" if pd.notna(x) else "")
        df_t["% of Total"] = df_t["% of Total"].apply(lambda x: f"{x:5.1f} %" if pd.notna(x) else "")
        df_t["€ / Hour"]   = df_t["€ / Hour"].apply(lambda x: f"€ {x:>8,.0f}/h" if pd.notna(x) else "")
        st.dataframe(df_t, use_container_width=True, hide_index=True)
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 2 : PROFITABILITY
    # ──────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown('<div class="section-header">Charter Profitability Simulation</div>', unsafe_allow_html=True)
        if h_charter == 0:
            st.warning("⚠ No charter hours configured. Adjust the 'Charter Hours' slider in the sidebar.")
        else:
            net = prof["net_result"]; cr = prof["coverage_rate"]
            badge = ('<span class="tag-ok">✓ PROFITABLE</span>' if net>=0
                     else '<span class="tag-warn">⚠ NEAR BREAK-EVEN</span>' if cr>=70
                     else '<span class="tag-err">✗ LOSS-MAKING</span>')
            st.markdown(f"**Status:** {badge} — Cost coverage rate: **{cr:.1f}%**", unsafe_allow_html=True)
            st.markdown("")
 
            # Show effective rate prominently
            effective_rate = prof.get("effective_rate", custom_rate)
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:1rem">
                <div class="metric-label">Effective Charter Rate Applied</div>
                <div class="metric-value">€ {effective_rate:,.0f} <span style="font-size:1rem;color:#8496B0">/ hour</span></div>
                <div class="metric-sub">{h_charter}h × € {effective_rate:,.0f} = gross revenue € {effective_rate*h_charter:,.0f}</div>
            </div>""", unsafe_allow_html=True)
 
            r1,r2,r3,r4 = st.columns(4)
            r1.metric("💵 Gross Charter Revenue", fmt(prof["gross_revenue"]))
            r2.metric("📉 Operator Commission",   fmt(prof["commission"]))
            r3.metric("💰 Net Charter Revenue",   fmt(prof["net_revenue"]))
            r4.metric("📊 Net Result", fmt(net), delta=f"{cr:.1f}% costs covered")
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown('<div class="section-header">Financial Waterfall</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_waterfall(costs, prof), use_container_width=True, config={"displayModeBar":False})
            with st.expander("📌 Calculation Assumptions"):
                st.table(pd.DataFrame({
                    "Parameter": ["Charter rate applied","Charter hours","Operator commission",
                                  "Gross revenue","Net revenue (after commission)",
                                  "Total variable costs","Total fixed costs"],
                    "Value": [fmt(effective_rate) + "/h", f"{h_charter} h", f"{commission_pct} %",
                              fmt(prof["gross_revenue"]), fmt(prof["net_revenue"]),
                              fmt(costs["total_variable"]), fmt(costs["total_fixed"])],
                }))
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 3 : SENSITIVITY
    # ──────────────────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-header">Sensitivity Analysis — Charter Hours vs Net Result</div>', unsafe_allow_html=True)
        st.caption(f"Private hours fixed at {h_private}h — Commission {commission_pct}% — Rate € {custom_rate:,.0f}/h")
        st.plotly_chart(chart_sensitivity(aircraft, h_private, commission_pct, custom_rate), use_container_width=True, config={"displayModeBar":False})
 
        st.markdown('<div class="section-header">Fleet Comparison (Cost per Hour)</div>', unsafe_allow_html=True)
        comparison = [{"Model":row["Modele"],"Total Cost (€)":round(calculate_costs(row,h_charter,h_private)["grand_total"]),
                       "Cost/Hour (€)":round(calculate_costs(row,h_charter,h_private)["avg_cost_h"])} for _,row in df.iterrows()]
        df_comp = pd.DataFrame(comparison).sort_values("Total Cost (€)")
        fig_comp = px.bar(df_comp,x="Model",y="Total Cost (€)",color="Cost/Hour (€)",
                          color_continuous_scale=["#1A3A6E","#4A90D9","#C9A84C","#E8C46A"],template="plotly_dark")
        fig_comp.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                               font=dict(color="#D6E4F7"),height=350,
                               coloraxis_colorbar=dict(title="€/h",tickformat=",.0f"),
                               margin=dict(t=10,b=80,l=10,r=10),
                               xaxis=dict(tickangle=-30),yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f"))
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar":False})
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 4 : PDF IMPORT  ★ NEW ★
    # ──────────────────────────────────────────────────────────────────
    with tab4:
        st.markdown('<div class="section-header">🤖 AI-Powered PDF Budget Import</div>', unsafe_allow_html=True)
        st.markdown("""
        Upload any annual aircraft budget PDF — Claude AI will automatically read it and
        extract all key financial figures, then add the aircraft to your database.
        """)
 
        # ── Step 1: API Key ───────────────────────────────────────────
        st.markdown('<span class="step-badge">1</span> **Enter your Anthropic API Key**', unsafe_allow_html=True)
        st.caption("Your key is never stored — it's only used for this session. Get one free at platform.anthropic.com")
        api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...",
                                label_visibility="collapsed")
 
        st.markdown("<br>", unsafe_allow_html=True)
 
        # ── Step 2: Upload PDF ────────────────────────────────────────
        st.markdown('<span class="step-badge">2</span> **Upload your budget PDF**', unsafe_allow_html=True)
        pdf_file = st.file_uploader("Drop your aircraft budget PDF here", type=["pdf"],
                                    label_visibility="collapsed")
 
        if pdf_file:
            file_size_kb = len(pdf_file.getvalue()) / 1024
            st.markdown(f"""
            <div style="background:#13233F;border:1px solid #1A3A6E;border-radius:6px;padding:0.8rem 1rem;margin:0.5rem 0">
                📄 <b>{pdf_file.name}</b> &nbsp;·&nbsp;
                <span style="color:#8496B0">{file_size_kb:.0f} KB</span>
            </div>""", unsafe_allow_html=True)
 
        st.markdown("<br>", unsafe_allow_html=True)
 
        # ── Step 3: Extract ───────────────────────────────────────────
        st.markdown('<span class="step-badge">3</span> **Extract data with AI**', unsafe_allow_html=True)
 
        col_btn, col_status = st.columns([1, 3])
        with col_btn:
            extract_btn = st.button("🔍 Extract from PDF", disabled=(not pdf_file or not api_key))
        with col_status:
            if not api_key:
                st.markdown('<span style="color:#8496B0;font-size:0.82rem">⟵ Enter your API key first</span>', unsafe_allow_html=True)
            elif not pdf_file:
                st.markdown('<span style="color:#8496B0;font-size:0.82rem">⟵ Upload a PDF first</span>', unsafe_allow_html=True)
 
        if extract_btn and pdf_file and api_key:
            with st.spinner("🤖 Claude is reading your budget document..."):
                try:
                    pdf_bytes = pdf_file.getvalue()
                    extracted = extract_pdf_with_claude(pdf_bytes, api_key)
                    st.session_state["extracted"] = extracted
                    st.success("✓ Extraction successful!")
                except json.JSONDecodeError as e:
                    st.error(f"⚠ Could not parse AI response as JSON: {e}")
                    st.session_state["extracted"] = None
                except Exception as e:
                    st.error(f"⚠ Extraction failed: {e}")
                    st.session_state["extracted"] = None
 
        # ── Step 4: Review & Confirm ─────────────────────────────────
        if st.session_state["extracted"]:
            ext = st.session_state["extracted"]
 
            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown('<span class="step-badge">4</span> **Review extracted data — edit if needed**', unsafe_allow_html=True)
            st.caption("All fields are editable before adding to the database.")
 
            col_a, col_b = st.columns(2)
            with col_a:
                model_name  = st.text_input("Aircraft Model",   value=ext.get("aircraft_model") or "")
                category    = st.selectbox("Category", ["Light Jet","Midsize","Super Midsize","Grand Cabin","Ultra Long Range"],
                                           index=["Light Jet","Midsize","Super Midsize","Grand Cabin","Ultra Long Range"].index(
                                               ext.get("category","Light Jet")) if ext.get("category") in
                                               ["Light Jet","Midsize","Super Midsize","Grand Cabin","Ultra Long Range"] else 0)
                fixed_costs = st.number_input("Fixed Costs excl. Crew (€/year)", value=float(ext.get("fixed_costs_annual") or 0), step=1000.0)
                crew_costs  = st.number_input("Annual Crew Costs (€/year)",      value=float(ext.get("crew_costs_annual") or 0), step=1000.0)
                base_hours  = st.number_input("Base Flight Hours / year",         value=float(ext.get("base_flight_hours") or 500), step=10.0)
 
            with col_b:
                var_charter = st.number_input("Variable Cost Charter (€/h)", value=float(ext.get("variable_cost_charter_per_hour") or 0), step=10.0)
                var_private = st.number_input("Variable Cost Private (€/h)",  value=float(ext.get("variable_cost_private_per_hour") or 0), step=10.0)
                charter_rate= st.number_input("Charter Rate to Client (€/h)", value=float(ext.get("charter_rate_per_hour") or 0), step=100.0)
                range_km    = st.number_input("Range (km)",        value=float(ext.get("range_km") or 0), step=100.0)
                pax_max     = st.number_input("Max Passengers",    value=float(ext.get("max_passengers") or 0), step=1.0)
                speed       = st.number_input("Cruise Speed (km/h)", value=float(ext.get("cruise_speed_kmh") or 0), step=10.0)
 
            if ext.get("notes"):
                with st.expander("📝 AI Notes from the document"):
                    st.write(ext["notes"])
 
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<span class="step-badge">5</span> **Add to database**', unsafe_allow_html=True)
 
            col_add, col_discard = st.columns([1, 1])
            with col_add:
                if st.button("✅ Add to Database", type="primary"):
                    new_row = {
                        "Modele":                 model_name,
                        "Categorie":              category,
                        "Couts_Fixes_Annuels":    fixed_costs,
                        "Couts_Equipe_Annuels":   crew_costs,
                        "Cout_Horaire_Charter":   var_charter,
                        "Cout_Horaire_Prive":     var_private,
                        "Heures_Base":            base_hours,
                        "Taux_Charter_EUR_h":     charter_rate,
                        "Vitesse_Croisiere_km_h": speed if speed > 0 else None,
                        "Autonomie_km":           range_km if range_km > 0 else None,
                        "Passagers_Max":          int(pax_max) if pax_max > 0 else None,
                    }
                    add_to_database(new_row)
                    st.session_state["extracted"] = None
                    st.success(f"✅ **{model_name}** added to the database! Switch to the Dashboard to simulate.")
                    st.rerun()
            with col_discard:
                if st.button("🗑 Discard"):
                    st.session_state["extracted"] = None
                    st.rerun()
 
        # ── How to get API key ────────────────────────────────────────
        with st.expander("ℹ How to get a free Anthropic API key"):
            st.markdown("""
            1. Go to **[platform.anthropic.com](https://platform.anthropic.com)**
            2. Create a free account
            3. Go to **API Keys** in the left menu
            4. Click **Create Key** → copy and paste it above
 
            The free tier includes enough credits to extract dozens of PDF budgets.
            Your key is only used during this browser session and is never saved.
            """)
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 5 : DATA
    # ──────────────────────────────────────────────────────────────────
    with tab5:
        st.markdown('<div class="section-header">Aircraft Database</div>', unsafe_allow_html=True)
 
        current_db = get_active_db()
        st.dataframe(current_db, use_container_width=True, hide_index=True)
 
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            # Download current database
            buf = BytesIO()
            current_db.to_excel(buf, index=False, sheet_name="Aviation Data")
            st.download_button("⬇ Download Current Database (.xlsx)", data=buf.getvalue(),
                               file_name="aviation_database.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with col_dl2:
            # Reset database
            if st.button("🔄 Reset to Default Database"):
                st.session_state["database"] = None
                st.session_state["extracted"] = None
                st.rerun()
 
        st.markdown('<div class="section-header">Required Excel File Format</div>', unsafe_allow_html=True)
        df_format = pd.DataFrame(
            [{"Column":k,"Description":v,"Required":"✓"} for k,v in REQUIRED_COLUMNS.items()] +
            [{"Column":"Categorie","Description":"Category (Light Jet, Midsize, etc.)","Required":"—"},
             {"Column":"Autonomie_km","Description":"Maximum range in km","Required":"—"},
             {"Column":"Vitesse_Croisiere_km_h","Description":"Cruise speed in km/h","Required":"—"},
             {"Column":"Passagers_Max","Description":"Maximum number of passengers","Required":"—"}])
        st.table(df_format)
 
    # ── Footer ───────────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;font-size:0.72rem;color:#4A5568;letter-spacing:0.1em">'
        'AVIATION COST ESTIMATOR — Figures are indicative and for simulation purposes only'
        ' · Values based on market averages (NBAA / JETNET)</div>',
        unsafe_allow_html=True)
 
 
if __name__ == "__main__":
    main()
