
"""
✈️ Aviation Cost Estimator — Streamlit Application
Estimation and simulation of business aircraft operating costs.
"""
 
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
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
    /* Palette: aviation navy + amber gold + slate grey */
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
 
    /* Background */
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
 
    /* Main title */
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
 
    /* Metric cards */
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
 
    /* Widget labels */
    .stSelectbox label, .stSlider label, .stNumberInput label,
    .stFileUploader label { color: var(--light) !important; font-size: 0.82rem; }
 
    .stSlider [data-baseweb="slider"] { accent-color: var(--gold); }
 
    /* Native metrics */
    [data-testid="stMetricValue"] { color: var(--amber) !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { color: var(--slate) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; }
    [data-testid="stMetricDelta"] { color: #4ADE80 !important; }
 
    /* Alerts */
    .stAlert { background-color: var(--card) !important; border-color: var(--mid) !important; }
 
    /* Buttons */
    .stButton > button {
        background: var(--mid) !important;
        color: var(--amber) !important;
        border: 1px solid var(--gold) !important;
        border-radius: 4px;
        letter-spacing: 0.06em;
        font-weight: 600;
    }
    .stButton > button:hover { background: var(--gold) !important; color: var(--navy) !important; }
 
    /* Dataframe */
    .stDataFrame { border: 1px solid var(--mid); border-radius: 6px; }
 
    /* Tabs */
    [data-baseweb="tab-list"] { background: var(--card); border-radius: 6px; }
    [data-baseweb="tab"] { color: var(--slate) !important; }
    [aria-selected="true"] { color: var(--amber) !important; border-bottom-color: var(--gold) !important; }
 
    /* Expander */
    [data-testid="stExpander"] { background: var(--card); border: 1px solid var(--mid); border-radius: 6px; }
 
    /* Status tags */
    .tag-ok  { background:#163A2A; color:#4ADE80; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-warn{ background:#3A2A10; color:#FBBF24; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-err { background:#3A1010; color:#F87171; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
</style>
""", unsafe_allow_html=True)
 
# ─── DEFAULT DATASET ────────────────────────────────────────────────────────
def get_default_data() -> pd.DataFrame:
    """
    Built-in default dataset based on real business aviation market references
    (sources: JETNET, AMSTAT, NBAA 2023).
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
def load_data(file) -> tuple[pd.DataFrame, list[str]]:
    """
    Loads an Excel or CSV file uploaded by the user.
    Returns (DataFrame, list_of_errors).
    """
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
 
    # Check required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        errors.append(
            f"Missing columns: {', '.join(missing)}. "
            f"Detected columns: {', '.join(df.columns.tolist())}"
        )
        return None, errors
 
    # Convert to numeric types
    num_cols = [c for c in REQUIRED_COLUMNS if c != "Modele"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
 
    df = df.dropna(subset=["Modele"])
    return df, errors
 
# ─── COST CALCULATIONS ───────────────────────────────────────────────────────
def calculate_costs(aircraft: pd.Series, h_charter: int, h_private: int) -> dict:
    """
    Computes the full annual cost breakdown for a given aircraft.
    """
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
 
    return {
        "fixed_costs":    fixed_costs,
        "crew_costs":     crew_costs,
        "total_fixed":    total_fixed,
        "var_charter":    var_charter,
        "var_private":    var_private,
        "total_variable": total_variable,
        "grand_total":    grand_total,
        "avg_cost_h":     avg_cost_h,
        "h_charter":      h_charter,
        "h_private":      h_private,
        "total_hours":    total_hours,
        "charter_tariff": charter_tariff,
    }
 
def calculate_profitability(costs: dict, markup_pct: float, commission_pct: float) -> dict:
    """
    Charter profitability simulation:
    gross revenue, commission, net revenue, net result, break-even.
    """
    tariff        = costs["charter_tariff"]
    h_charter     = costs["h_charter"]
    gross_revenue = tariff * h_charter
    commission    = gross_revenue * commission_pct / 100
    net_revenue   = gross_revenue - commission
 
    net_result    = net_revenue - costs["grand_total"]
    coverage_rate = (net_revenue / costs["grand_total"] * 100) if costs["grand_total"] > 0 else 0
 
    return {
        "gross_revenue":  gross_revenue,
        "commission":     commission,
        "net_revenue":    net_revenue,
        "net_result":     net_result,
        "coverage_rate":  coverage_rate,
    }
 
# ─── CHARTS ──────────────────────────────────────────────────────────────────
COLORS = {
    "fixed":   "#1A3A6E",
    "crew":    "#C9A84C",
    "charter": "#4A90D9",
    "private": "#8496B0",
    "profit":  "#4ADE80",
    "loss":    "#F87171",
}
 
def chart_donut(costs: dict) -> go.Figure:
    """Donut chart showing cost breakdown."""
    labels = ["Fixed Operating Costs", "Crew Costs", "Charter Variable", "Private Variable"]
    values = [
        costs["fixed_costs"],
        costs["crew_costs"],
        costs["var_charter"],
        costs["var_private"],
    ]
    colors = [COLORS["fixed"], COLORS["crew"], COLORS["charter"], COLORS["private"]]
 
    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.56,
        marker=dict(colors=colors, line=dict(color="#0B1629", width=2)),
        textinfo="label+percent",
        textfont=dict(size=11, color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>",
    ))
    fig.add_annotation(
        text=f"<b>{costs['grand_total']/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
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
 
def chart_stacked_bars(costs: dict) -> go.Figure:
    """Stacked bar chart: Charter vs Private vs Fixed costs."""
    categories = ["Charter", "Private", "Total"]
 
    traces = [
        go.Bar(name="Fixed Costs", x=categories,
               y=[costs["total_fixed"] * (costs["h_charter"] / max(costs["total_hours"], 1)),
                  costs["total_fixed"] * (costs["h_private"] / max(costs["total_hours"], 1)),
                  costs["total_fixed"]],
               marker_color=COLORS["fixed"]),
        go.Bar(name="Charter Variable", x=categories,
               y=[costs["var_charter"], 0, costs["var_charter"]],
               marker_color=COLORS["charter"]),
        go.Bar(name="Private Variable", x=categories,
               y=[0, costs["var_private"], costs["var_private"]],
               marker_color=COLORS["private"]),
    ]
    fig = go.Figure(data=traces)
    fig.update_layout(
        barmode="stack",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        yaxis=dict(title="Cost (€)", gridcolor="#1A3A6E", tickformat=",.0f"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.35, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=10, b=40, l=10, r=10),
        height=300,
    )
    return fig
 
def chart_waterfall(costs: dict, prof: dict) -> go.Figure:
    """Waterfall chart: from charter revenue to net result."""
    measures = ["relative", "relative", "relative", "relative", "total"]
    x = ["Gross Charter Revenue", "Operator Commission", "Variable Costs", "Fixed Costs", "Net Result"]
    y = [
        prof["gross_revenue"],
        -prof["commission"],
        -costs["total_variable"],
        -costs["total_fixed"],
        prof["net_result"],
    ]
    total_color = COLORS["profit"] if prof["net_result"] >= 0 else COLORS["loss"]
 
    fig = go.Figure(go.Waterfall(
        measure=measures, x=x, y=y,
        connector=dict(line=dict(color="#1A3A6E", width=1.5)),
        increasing=dict(marker_color=COLORS["profit"]),
        decreasing=dict(marker_color=COLORS["loss"]),
        totals=dict(marker_color=total_color),
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
 
def chart_sensitivity(aircraft: pd.Series, h_private: int, commission_pct: float) -> go.Figure:
    """Sensitivity curve: net result vs charter hours."""
    hours_range = list(range(0, 801, 25))
    results = []
    for h in hours_range:
        c = calculate_costs(aircraft, h, h_private)
        r = calculate_profitability(c, 0, commission_pct)
        results.append(r["net_result"])
 
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=hours_range, y=results, mode="lines",
        line=dict(color=COLORS["charter"], width=2.5),
        fill="tozeroy",
        fillcolor="rgba(74,144,217,0.12)",
        name="Net Result",
        hovertemplate="<b>%{x}h charter</b><br>%{y:+,.0f} €<extra></extra>",
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="#C9A84C", line_width=1.5)
 
    # Find break-even point
    for i in range(1, len(results)):
        if results[i-1] < 0 <= results[i]:
            h_be = hours_range[i]
            fig.add_vline(x=h_be, line_dash="dot", line_color="#E8C46A", line_width=1.5,
                         annotation_text=f"Break-even ~{h_be}h",
                         annotation_font_color="#E8C46A",
                         annotation_position="top right")
            break
 
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#D6E4F7"),
        yaxis=dict(title="Net Result (€)", gridcolor="#1A3A6E", tickformat=",.0f"),
        xaxis=dict(title="Charter Flight Hours", gridcolor="#1A3A6E"),
        margin=dict(t=10, b=10, l=10, r=10),
        height=300,
        showlegend=False,
    )
    return fig
 
# ─── CURRENCY FORMAT ─────────────────────────────────────────────────────────
def fmt(v: float, decimals: int = 0) -> str:
    """Formats a number as EUR with thousands separator."""
    return f"€ {v:,.{decimals}f}"
 
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
    with st.sidebar:
        st.markdown('<div class="section-header">⬆ Database</div>', unsafe_allow_html=True)
 
        uploaded_file = st.file_uploader(
            "Import an Excel / CSV file",
            type=["xlsx", "xls", "csv"],
            help="Required columns: Modele, Couts_Fixes_Annuels, Couts_Equipe_Annuels, "
                 "Cout_Horaire_Charter, Cout_Horaire_Prive, Taux_Charter_EUR_h"
        )
 
        if uploaded_file:
            df, errors = load_data(uploaded_file)
            if errors:
                for e in errors:
                    st.error(f"⚠ {e}")
                st.info("Using default dataset instead.")
                df = get_default_data()
            else:
                st.success(f"✓ {len(df)} aircraft loaded")
        else:
            df = get_default_data()
            st.info("📋 Using sample data (10 aircraft)")
 
        st.markdown('<div class="section-header">✈ Aircraft Selection</div>', unsafe_allow_html=True)
 
        # Filter by category if available
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
 
        total_hours = h_charter + h_private
        if total_hours > 800:
            st.warning(f"⚠ Total {total_hours}h exceeds recommended regulatory ceiling (800h)")
 
        st.markdown('<div class="section-header">💰 Profitability Simulation</div>', unsafe_allow_html=True)
 
        markup_pct     = st.slider("Rate Markup (%)", 0, 50, 0, step=5,
                                   help="% added on top of the base charter rate")
        commission_pct = st.slider("Operator Commission (%)", 0, 25, 10, step=1,
                                   help="% commission retained by broker / operator")
 
    # ── Calculations ─────────────────────────────────────────────────────
    costs = calculate_costs(aircraft, h_charter, h_private)
    prof  = calculate_profitability(costs, markup_pct, commission_pct)
 
    # ════════════════════════════════════════════════════════════════════
    # TABS
    # ════════════════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊  Dashboard",
        "📈  Profitability Simulation",
        "🔍  Sensitivity Analysis",
        "📋  Data",
    ])
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 1 : DASHBOARD
    # ──────────────────────────────────────────────────────────────────
    with tab1:
        # Aircraft identity cards
        col_id1, col_id2, col_id3, col_id4 = st.columns(4)
        with col_id1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Selected Aircraft</div>
                <div class="metric-value" style="font-size:1.2rem">{aircraft['Modele']}</div>
                <div class="metric-sub">{aircraft.get('Categorie','—')}</div>
            </div>""", unsafe_allow_html=True)
        with col_id2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">Total Hours / Year</div>
                <div class="metric-value">{costs['total_hours']}h</div>
                <div class="metric-sub">{h_charter}h charter · {h_private}h private</div>
            </div>""", unsafe_allow_html=True)
        with col_id3:
            if "Autonomie_km" in aircraft and pd.notna(aircraft["Autonomie_km"]):
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Maximum Range</div>
                    <div class="metric-value">{aircraft['Autonomie_km']:,.0f} km</div>
                    <div class="metric-sub">{aircraft.get('Passagers_Max','—')} passengers max</div>
                </div>""", unsafe_allow_html=True)
        with col_id4:
            if "Vitesse_Croisiere_km_h" in aircraft and pd.notna(aircraft.get("Vitesse_Croisiere_km_h")):
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Cruise Speed</div>
                    <div class="metric-value">{aircraft['Vitesse_Croisiere_km_h']} km/h</div>
                    <div class="metric-sub">Certified performance</div>
                </div>""", unsafe_allow_html=True)
 
        st.markdown("<hr>", unsafe_allow_html=True)
 
        # Main KPIs
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("💶 Total Annual Cost",    fmt(costs["grand_total"]))
        k2.metric("🔒 Total Fixed Costs",    fmt(costs["total_fixed"]))
        k3.metric("⚡ Variable Costs",       fmt(costs["total_variable"]))
        k4.metric("⌛ Average Cost / Hour",  fmt(costs["avg_cost_h"]))
 
        st.markdown("<hr>", unsafe_allow_html=True)
 
        # Charts
        col_g1, col_g2 = st.columns([1, 1])
        with col_g1:
            st.markdown('<div class="section-header">Cost Breakdown</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_donut(costs), use_container_width=True, config={"displayModeBar": False})
 
        with col_g2:
            st.markdown('<div class="section-header">Cost by Flight Mode</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_stacked_bars(costs), use_container_width=True, config={"displayModeBar": False})
 
        # Detail table
        st.markdown('<div class="section-header">Cost Line Detail</div>', unsafe_allow_html=True)
        table_data = {
            "Line Item": [
                "Fixed Operating Costs",
                "Crew Costs",
                "Charter Variable Costs",
                "Private Variable Costs",
                "─────────────────────",
                "GRAND TOTAL",
            ],
            "Amount (€)": [
                costs["fixed_costs"],
                costs["crew_costs"],
                costs["var_charter"],
                costs["var_private"],
                None,
                costs["grand_total"],
            ],
            "% of Total": [
                costs["fixed_costs"]   / costs["grand_total"] * 100,
                costs["crew_costs"]    / costs["grand_total"] * 100,
                costs["var_charter"]   / costs["grand_total"] * 100,
                costs["var_private"]   / costs["grand_total"] * 100,
                None,
                100.0,
            ],
            "€ / Hour": [
                costs["fixed_costs"]   / max(costs["total_hours"], 1),
                costs["crew_costs"]    / max(costs["total_hours"], 1),
                aircraft["Cout_Horaire_Charter"] if h_charter > 0 else 0,
                aircraft["Cout_Horaire_Prive"]   if h_private > 0 else 0,
                None,
                costs["avg_cost_h"],
            ],
        }
        df_table = pd.DataFrame(table_data)
        df_table["Amount (€)"] = df_table["Amount (€)"].apply(
            lambda x: f"€ {x:>12,.0f}" if pd.notna(x) else "")
        df_table["% of Total"] = df_table["% of Total"].apply(
            lambda x: f"{x:5.1f} %" if pd.notna(x) else "")
        df_table["€ / Hour"]   = df_table["€ / Hour"].apply(
            lambda x: f"€ {x:>8,.0f}/h" if pd.notna(x) else "")
        st.dataframe(df_table, use_container_width=True, hide_index=True)
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 2 : PROFITABILITY SIMULATION
    # ──────────────────────────────────────────────────────────────────
    with tab2:
        st.markdown('<div class="section-header">Charter Profitability Simulation</div>',
                    unsafe_allow_html=True)
 
        if h_charter == 0:
            st.warning("⚠ No charter hours configured. Adjust the 'Charter Hours' slider in the sidebar.")
        else:
            # Global status
            net = prof["net_result"]
            cr  = prof["coverage_rate"]
            if net >= 0:
                badge = '<span class="tag-ok">✓ PROFITABLE</span>'
            elif cr >= 70:
                badge = '<span class="tag-warn">⚠ NEAR BREAK-EVEN</span>'
            else:
                badge = '<span class="tag-err">✗ LOSS-MAKING</span>'
            st.markdown(f"**Status:** {badge} — Cost coverage rate: **{cr:.1f}%**",
                        unsafe_allow_html=True)
            st.markdown("")
 
            # Profitability KPIs
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("💵 Gross Charter Revenue", fmt(prof["gross_revenue"]))
            r2.metric("📉 Operator Commission",   fmt(prof["commission"]))
            r3.metric("💰 Net Charter Revenue",   fmt(prof["net_revenue"]))
            r4.metric("📊 Net Result", fmt(net), delta=f"{cr:.1f}% costs covered")
 
            st.markdown("<hr>", unsafe_allow_html=True)
 
            # Waterfall
            st.markdown('<div class="section-header">Financial Waterfall</div>', unsafe_allow_html=True)
            st.plotly_chart(chart_waterfall(costs, prof), use_container_width=True,
                            config={"displayModeBar": False})
 
            # Assumptions
            with st.expander("📌 Calculation Assumptions"):
                hyp = {
                    "Parameter": [
                        "Base charter rate",
                        "Charter hours",
                        "Rate markup",
                        "Operator commission",
                        "Gross revenue",
                        "Total variable costs",
                        "Total fixed costs",
                    ],
                    "Value": [
                        fmt(aircraft.get("Taux_Charter_EUR_h", 0)),
                        f"{h_charter} h",
                        f"{markup_pct} %",
                        f"{commission_pct} %",
                        fmt(prof["gross_revenue"]),
                        fmt(costs["total_variable"]),
                        fmt(costs["total_fixed"]),
                    ],
                }
                st.table(pd.DataFrame(hyp))
 
    # ──────────────────────────────────────────────────────────────────
    # TAB 3 : SENSITIVITY ANALYSIS
    # ──────────────────────────────────────────────────────────────────
    with tab3:
        st.markdown('<div class="section-header">Sensitivity Analysis — Charter Hours vs Net Result</div>',
                    unsafe_allow_html=True)
        st.caption(f"Private hours fixed at {h_private}h — Commission {commission_pct}%")
        st.plotly_chart(chart_sensitivity(aircraft, h_private, commission_pct),
                        use_container_width=True, config={"displayModeBar": False})
 
        # Multi-aircraft comparison
        st.markdown('<div class="section-header">Fleet Comparison (Cost per Hour)</div>',
                    unsafe_allow_html=True)
 
        comparison = []
        for _, row in df.iterrows():
            c = calculate_costs(row, h_charter, h_private)
            comparison.append({
                "Model":             row["Modele"],
                "Total Cost (€)":    round(c["grand_total"]),
                "Cost/Hour (€)":     round(c["avg_cost_h"]),
                "Fixed Costs (€)":   round(c["total_fixed"]),
                "Variable Costs (€)": round(c["total_variable"]),
            })
        df_comp = pd.DataFrame(comparison).sort_values("Total Cost (€)")
 
        fig_comp = px.bar(
            df_comp, x="Model", y="Total Cost (€)",
            color="Cost/Hour (€)",
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
    # TAB 4 : DATA
    # ──────────────────────────────────────────────────────────────────
    with tab4:
        st.markdown('<div class="section-header">Aircraft Database</div>', unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)
 
        st.markdown('<div class="section-header">Required Excel File Format</div>',
                    unsafe_allow_html=True)
        df_format = pd.DataFrame([
            {"Column": k, "Description": v, "Required": "✓"}
            for k, v in REQUIRED_COLUMNS.items()
        ] + [
            {"Column": "Categorie",             "Description": "Category (Light Jet, Midsize, etc.)", "Required": "—"},
            {"Column": "Autonomie_km",           "Description": "Maximum range in km",                "Required": "—"},
            {"Column": "Vitesse_Croisiere_km_h", "Description": "Cruise speed in km/h",              "Required": "—"},
            {"Column": "Passagers_Max",          "Description": "Maximum number of passengers",      "Required": "—"},
        ])
        st.table(df_format)
 
        # Download template
        @st.cache_data
        def get_template_excel() -> bytes:
            buf = BytesIO()
            template = get_default_data()
            template.to_excel(buf, index=False, sheet_name="Aviation Data")
            return buf.getvalue()
 
        st.download_button(
            "⬇ Download Excel Template",
            data=get_template_excel(),
            file_name="aviation_cost_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
 
    # ── Footer ───────────────────────────────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        '<div style="text-align:center;font-size:0.72rem;color:#4A5568;letter-spacing:0.1em">'
        'AVIATION COST ESTIMATOR — Figures are indicative and for simulation purposes only'
        ' · Values based on market averages (NBAA / JETNET)</div>',
        unsafe_allow_html=True
    )
 
 
# ─── ENTRY POINT ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
