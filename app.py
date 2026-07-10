"""
✈️ Aviation Cost Estimator — Streamlit Application v3
Estimation and simulation of business aircraft operating costs.
Includes AI-powered PDF budget import via Claude API.
Includes Cost Master: full operational cost breakdown & financial analysis.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import base64
import warnings
warnings.filterwarnings("ignore")

REPORTLAB_OK = True

# ─── PAGE CONFIG ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Aviation Cost Estimator", page_icon="✈",
                   layout="wide", initial_sidebar_state="expanded")

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root{--navy:#0B1629;--deep:#112244;--mid:#1A3A6E;--gold:#C9A84C;--amber:#E8C46A;
      --slate:#8496B0;--light:#D6E4F7;--card:#13233F;--greentext:#4ADE80;}
.stApp{background-color:var(--navy)!important;color:var(--light)!important;
       font-family:'Segoe UI',system-ui,sans-serif;}
[data-testid="stSidebar"]{background-color:var(--deep)!important;border-right:1px solid var(--mid);}
[data-testid="stSidebar"] *{color:var(--light)!important;}
.main-title{font-size:2rem;font-weight:700;letter-spacing:.08em;color:var(--amber);
            text-transform:uppercase;margin-bottom:.1rem;}
.sub-title{font-size:.85rem;color:var(--slate);letter-spacing:.12em;
           text-transform:uppercase;margin-bottom:1.5rem;}
.metric-card{background:var(--card);border:1px solid var(--mid);border-left:3px solid var(--gold);
             border-radius:6px;padding:1rem 1.2rem;margin-bottom:.8rem;}
.metric-label{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;
              color:var(--slate);margin-bottom:.3rem;}
.metric-value{font-size:1.7rem;font-weight:700;color:var(--amber);}
.metric-sub{font-size:.78rem;color:var(--slate);margin-top:.1rem;}
.section-header{font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;
                color:var(--gold);border-bottom:1px solid var(--mid);
                padding-bottom:.4rem;margin:1.2rem 0 .8rem 0;}
hr{border-color:var(--mid)!important;}
[data-testid="stMetricValue"]{color:var(--amber)!important;font-size:1.5rem!important;}
[data-testid="stMetricLabel"]{color:var(--slate)!important;font-size:.72rem!important;}
[data-testid="stMetricDelta"]{color:#4ADE80!important;}
.stButton>button{background:var(--mid)!important;color:var(--amber)!important;
                 border:1px solid var(--gold)!important;border-radius:4px;font-weight:600;}
.stButton>button:hover{background:var(--gold)!important;color:var(--navy)!important;}
[data-baseweb="tab-list"]{background:var(--card);border-radius:6px;}
[data-baseweb="tab"]{color:var(--slate)!important;}
[aria-selected="true"]{color:var(--amber)!important;border-bottom-color:var(--gold)!important;}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--mid);border-radius:6px;}
.tag-ok{background:#163A2A;color:#4ADE80;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-warn{background:#3A2A10;color:#FBBF24;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-err{background:#3A1010;color:#F87171;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.total-banner{background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
              border:1px solid var(--gold);border-radius:8px;padding:1.5rem;
              text-align:center;margin:1.5rem 0;}
.step-badge{display:inline-block;background:var(--mid);color:var(--amber);border-radius:50%;
            width:24px;height:24px;text-align:center;line-height:24px;
            font-size:.75rem;font-weight:700;margin-right:.5rem;}
</style>
""", unsafe_allow_html=True)


# ─── LOGO ───────────────────────────────────────────────────────────────────
LOGO_B64 = ""  # Loaded lazily at PDF generation time

def _get_logo_b64():
    """Load logo only when needed for PDF — not at startup."""
    global LOGO_B64
    if LOGO_B64:
        return LOGO_B64
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/gregorydebeure/aviation-cost-estimato/main/menkor_logo.png"
        with urllib.request.urlopen(url, timeout=5) as r:
            LOGO_B64 = base64.b64encode(r.read()).decode()
    except Exception:
        LOGO_B64 = ""
    return LOGO_B64

def _b64_to_imgbuf(b64_str):
    return BytesIO(base64.b64decode(b64_str))

# ─── DATABASE ────────────────────────────────────────────────────────────────
def get_default_data():
    data = [
        {"Modele":"Airbus 318","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":219176,"Couts_Equipe_Annuels":450113,"Cout_Horaire_Charter":4481,"Cout_Horaire_Prive":3674,"Heures_Base":350,"Taux_Charter_EUR_h":6500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":6862,"Passagers_Max":19},
        {"Modele":"Airbus 319","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":225763,"Couts_Equipe_Annuels":450113,"Cout_Horaire_Charter":4338,"Cout_Horaire_Prive":3557,"Heures_Base":350,"Taux_Charter_EUR_h":7000,"Vitesse_Croisiere_km_h":869,"Autonomie_km":11014,"Passagers_Max":19},
        {"Modele":"Airbus 320","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":253951,"Couts_Equipe_Annuels":361286,"Cout_Horaire_Charter":5000,"Cout_Horaire_Prive":4100,"Heures_Base":100,"Taux_Charter_EUR_h":8500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":8938,"Passagers_Max":150},
        {"Modele":"Airbus 321","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":277688,"Couts_Equipe_Annuels":450113,"Cout_Horaire_Charter":5331,"Cout_Horaire_Prive":4371,"Heures_Base":350,"Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":822,"Autonomie_km":8288,"Passagers_Max":19},
        {"Modele":"Airbus 340","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":360066,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":11019,"Cout_Horaire_Prive":9036,"Heures_Base":100,"Taux_Charter_EUR_h":28000,"Vitesse_Croisiere_km_h":835,"Autonomie_km":12640,"Passagers_Max":400},
        {"Modele":"Airbus ACJ319neo","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":279335,"Couts_Equipe_Annuels":376048,"Cout_Horaire_Charter":3817,"Cout_Horaire_Prive":3130,"Heures_Base":350,"Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":12501,"Passagers_Max":19},
        {"Modele":"Airbus ACJ320neo","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":310659,"Couts_Equipe_Annuels":376048,"Cout_Horaire_Charter":3833,"Cout_Horaire_Prive":3143,"Heures_Base":350,"Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":869,"Autonomie_km":11299,"Passagers_Max":19},
        {"Modele":"BAE RJ-70","Categorie":"Regional Jet / VIP","Couts_Fixes_Annuels":222678,"Couts_Equipe_Annuels":372857,"Cout_Horaire_Charter":4357,"Cout_Horaire_Prive":3573,"Heures_Base":100,"Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":755,"Autonomie_km":3250,"Passagers_Max":20},
        {"Modele":"BAE RJ-85","Categorie":"Regional Jet / VIP","Couts_Fixes_Annuels":271095,"Couts_Equipe_Annuels":372857,"Cout_Horaire_Charter":4033,"Cout_Horaire_Prive":3307,"Heures_Base":100,"Taux_Charter_EUR_h":4800,"Vitesse_Croisiere_km_h":755,"Autonomie_km":3366,"Passagers_Max":20},
        {"Modele":"Beechcraft Beechjet 400","Categorie":"Light Jet","Couts_Fixes_Annuels":34901,"Couts_Equipe_Annuels":245619,"Cout_Horaire_Charter":1823,"Cout_Horaire_Prive":1495,"Heures_Base":250,"Taux_Charter_EUR_h":2200,"Vitesse_Croisiere_km_h":826,"Autonomie_km":2061,"Passagers_Max":7},
        {"Modele":"Beechcraft Beechjet 400A","Categorie":"Light Jet","Couts_Fixes_Annuels":36260,"Couts_Equipe_Annuels":245619,"Cout_Horaire_Charter":1568,"Cout_Horaire_Prive":1286,"Heures_Base":250,"Taux_Charter_EUR_h":2300,"Vitesse_Croisiere_km_h":832,"Autonomie_km":2133,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier I","Categorie":"Light Jet","Couts_Fixes_Annuels":35998,"Couts_Equipe_Annuels":136880,"Cout_Horaire_Charter":1254,"Cout_Horaire_Prive":1028,"Heures_Base":250,"Taux_Charter_EUR_h":1800,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier IA","Categorie":"Light Jet","Couts_Fixes_Annuels":41947,"Couts_Equipe_Annuels":136880,"Cout_Horaire_Charter":1236,"Cout_Horaire_Prive":1013,"Heures_Base":250,"Taux_Charter_EUR_h":1900,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Boeing 737-500","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":242553,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":5456,"Cout_Horaire_Prive":4474,"Heures_Base":100,"Taux_Charter_EUR_h":7500,"Vitesse_Croisiere_km_h":839,"Autonomie_km":5424,"Passagers_Max":150},
        {"Modele":"Boeing 737-600","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":231007,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":4544,"Cout_Horaire_Prive":3726,"Heures_Base":100,"Taux_Charter_EUR_h":7800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":7073,"Passagers_Max":119},
        {"Modele":"Boeing 737-700","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":225028,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":4669,"Cout_Horaire_Prive":3829,"Heures_Base":100,"Taux_Charter_EUR_h":8000,"Vitesse_Croisiere_km_h":838,"Autonomie_km":7226,"Passagers_Max":140},
        {"Modele":"Boeing 747-100","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":273066,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":19415,"Cout_Horaire_Prive":15920,"Heures_Base":100,"Taux_Charter_EUR_h":55000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":11195,"Passagers_Max":400},
        {"Modele":"Boeing 747-200","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":289890,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":18520,"Cout_Horaire_Prive":15186,"Heures_Base":100,"Taux_Charter_EUR_h":58000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":12640,"Passagers_Max":350},
        {"Modele":"Boeing 747-400","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":276703,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":15263,"Cout_Horaire_Prive":12516,"Heures_Base":100,"Taux_Charter_EUR_h":65000,"Vitesse_Croisiere_km_h":913,"Autonomie_km":14626,"Passagers_Max":420},
        {"Modele":"Boeing 747SP","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":239780,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":15953,"Cout_Horaire_Prive":13081,"Heures_Base":100,"Taux_Charter_EUR_h":60000,"Vitesse_Croisiere_km_h":902,"Autonomie_km":13723,"Passagers_Max":331},
        {"Modele":"Boeing 757-200ER","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":274945,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":5939,"Cout_Horaire_Prive":4870,"Heures_Base":100,"Taux_Charter_EUR_h":12000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":11159,"Passagers_Max":200},
        {"Modele":"Boeing 767-200ER","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":384835,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":6537,"Cout_Horaire_Prive":5360,"Heures_Base":100,"Taux_Charter_EUR_h":15000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":13145,"Passagers_Max":181},
        {"Modele":"Boeing 767-300ER","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":380439,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":8352,"Cout_Horaire_Prive":6849,"Heures_Base":100,"Taux_Charter_EUR_h":18000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":12474,"Passagers_Max":218},
        {"Modele":"Boeing 787-8","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":358241,"Couts_Equipe_Annuels":521978,"Cout_Horaire_Charter":7925,"Cout_Horaire_Prive":6498,"Heures_Base":100,"Taux_Charter_EUR_h":20000,"Vitesse_Croisiere_km_h":930,"Autonomie_km":14538,"Passagers_Max":381},
        {"Modele":"Boeing BBJ","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":218956,"Couts_Equipe_Annuels":469635,"Cout_Horaire_Charter":3763,"Cout_Horaire_Prive":3086,"Heures_Base":350,"Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":871,"Autonomie_km":11100,"Passagers_Max":19},
        {"Modele":"Boeing BBJ2","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":241598,"Couts_Equipe_Annuels":469653,"Cout_Horaire_Charter":3882,"Cout_Horaire_Prive":3183,"Heures_Base":350,"Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":10191,"Passagers_Max":19},
        {"Modele":"Boeing BBJ3","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":248567,"Couts_Equipe_Annuels":470089,"Cout_Horaire_Charter":3889,"Cout_Horaire_Prive":3189,"Heures_Base":350,"Taux_Charter_EUR_h":11000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":8649,"Passagers_Max":19},
        {"Modele":"Bombardier Challenger 604","Categorie":"Large Jet","Couts_Fixes_Annuels":376651,"Couts_Equipe_Annuels":237726,"Cout_Horaire_Charter":2726,"Cout_Horaire_Prive":2450,"Heures_Base":350,"Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6786,"Passagers_Max":10},
        {"Modele":"Bombardier Challenger 605","Categorie":"Large Jet","Couts_Fixes_Annuels":500361,"Couts_Equipe_Annuels":346500,"Cout_Horaire_Charter":2619,"Cout_Horaire_Prive":2360,"Heures_Base":350,"Taux_Charter_EUR_h":5500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":6856,"Passagers_Max":10},
        {"Modele":"Bombardier Challenger 650","Categorie":"Large Jet","Couts_Fixes_Annuels":488946,"Couts_Equipe_Annuels":333270,"Cout_Horaire_Charter":2455,"Cout_Horaire_Prive":2210,"Heures_Base":350,"Taux_Charter_EUR_h":5800,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6795,"Passagers_Max":10},
        {"Modele":"Bombardier Global 5000","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":702952,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4051,"Cout_Horaire_Prive":3646,"Heures_Base":350,"Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9390,"Passagers_Max":13},
        {"Modele":"Bombardier Global Express","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":683427,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4471,"Cout_Horaire_Prive":4024,"Heures_Base":350,"Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10726,"Passagers_Max":13},
        {"Modele":"Bombardier Global Express XRS","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":714023,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4420,"Cout_Horaire_Prive":3978,"Heures_Base":350,"Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10934,"Passagers_Max":13},
        {"Modele":"Challenger 300","Categorie":"Super Midsize Jet","Couts_Fixes_Annuels":102295,"Couts_Equipe_Annuels":392114,"Cout_Horaire_Charter":2878,"Cout_Horaire_Prive":2360,"Heures_Base":350,"Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":848,"Autonomie_km":5545,"Passagers_Max":8},
        {"Modele":"Challenger 350","Categorie":"Super Midsize Jet","Couts_Fixes_Annuels":93921,"Couts_Equipe_Annuels":394305,"Cout_Horaire_Charter":2353,"Cout_Horaire_Prive":1929,"Heures_Base":350,"Taux_Charter_EUR_h":4000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5784,"Passagers_Max":8},
        {"Modele":"Challenger 600","Categorie":"Large Jet","Couts_Fixes_Annuels":78406,"Couts_Equipe_Annuels":372774,"Cout_Horaire_Charter":4337,"Cout_Horaire_Prive":3556,"Heures_Base":350,"Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":5061,"Passagers_Max":9},
        {"Modele":"Challenger 601-1A","Categorie":"Large Jet","Couts_Fixes_Annuels":84681,"Couts_Equipe_Annuels":367240,"Cout_Horaire_Charter":3720,"Cout_Horaire_Prive":3050,"Heures_Base":350,"Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":821,"Autonomie_km":5748,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 10","Categorie":"Light Jet","Couts_Fixes_Annuels":279536,"Couts_Equipe_Annuels":224844,"Cout_Horaire_Charter":2372,"Cout_Horaire_Prive":2135,"Heures_Base":250,"Taux_Charter_EUR_h":2800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":2745,"Passagers_Max":6},
        {"Modele":"Dassault Falcon 20C","Categorie":"Midsize Jet","Couts_Fixes_Annuels":350751,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":3179,"Cout_Horaire_Prive":2861,"Heures_Base":250,"Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2167,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20C-5","Categorie":"Midsize Jet","Couts_Fixes_Annuels":356747,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2675,"Cout_Horaire_Prive":2408,"Heures_Base":250,"Taux_Charter_EUR_h":3400,"Vitesse_Croisiere_km_h":842,"Autonomie_km":3684,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F","Categorie":"Midsize Jet","Couts_Fixes_Annuels":356077,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2895,"Cout_Horaire_Prive":2606,"Heures_Base":250,"Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2420,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F-5","Categorie":"Midsize Jet","Couts_Fixes_Annuels":353308,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2485,"Cout_Horaire_Prive":2237,"Heures_Base":250,"Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":842,"Autonomie_km":4063,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50","Categorie":"Large Jet","Couts_Fixes_Annuels":450596,"Couts_Equipe_Annuels":334924,"Cout_Horaire_Charter":3352,"Cout_Horaire_Prive":3017,"Heures_Base":350,"Taux_Charter_EUR_h":5000,"Vitesse_Croisiere_km_h":799,"Autonomie_km":5526,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50-40","Categorie":"Large Jet","Couts_Fixes_Annuels":469453,"Couts_Equipe_Annuels":334924,"Cout_Horaire_Charter":3328,"Cout_Horaire_Prive":2995,"Heures_Base":350,"Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5905,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 7X","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":588918,"Couts_Equipe_Annuels":377505,"Cout_Horaire_Charter":2994,"Cout_Horaire_Prive":2695,"Heures_Base":350,"Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9924,"Passagers_Max":12},
        {"Modele":"Dassault Falcon 8X","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":598153,"Couts_Equipe_Annuels":377505,"Cout_Horaire_Charter":2958,"Cout_Horaire_Prive":2662,"Heures_Base":350,"Taux_Charter_EUR_h":10500,"Vitesse_Croisiere_km_h":903,"Autonomie_km":11365,"Passagers_Max":12},
    ]
    return pd.DataFrame(data)

def get_active_db():
    if st.session_state.get("database") is not None:
        return st.session_state["database"]
    return get_default_data()

def fmt(v, decimals=0):
    return f"€ {v:,.{decimals}f}"

def calculate_costs(aircraft, h_charter, h_private):
    fc = aircraft["Couts_Fixes_Annuels"]; cc = aircraft["Couts_Equipe_Annuels"]
    ch = aircraft["Cout_Horaire_Charter"]; ph = aircraft["Cout_Horaire_Prive"]
    tariff = float(aircraft.get("Taux_Charter_EUR_h", 0))
    th = h_charter + h_private
    vc = h_charter * ch; vp = h_private * ph
    tv = vc + vp; tf = fc + cc; gt = tf + tv
    return dict(fixed_costs=fc, crew_costs=cc, total_fixed=tf,
                var_charter=vc, var_private=vp, total_variable=tv,
                grand_total=gt, avg_cost_h=gt/th if th>0 else 0,
                h_charter=h_charter, h_private=h_private, total_hours=th,
                charter_tariff=tariff)

def calculate_profitability(costs, commission_pct, custom_rate=None):
    tariff = custom_rate if (custom_rate is not None and custom_rate > 0) else costs["charter_tariff"]
    gr = tariff * costs["h_charter"]
    comm = gr * commission_pct / 100
    nr = gr - comm
    net = nr - costs["grand_total"]
    cov = (nr / costs["grand_total"] * 100) if costs["grand_total"] > 0 else 0
    return dict(gross_revenue=gr, commission=comm, net_revenue=nr,
                net_result=net, coverage_rate=cov, effective_rate=tariff)

# ─── CHART HELPERS ───────────────────────────────────────────────────────────
COLORS = {"fixed":"#1A3A6E","crew":"#C9A84C","charter":"#4A90D9","private":"#8496B0",
          "profit":"#4ADE80","loss":"#F87171"}

def chart_donut(costs):
    lbl = ["Fixed Op","Crew","Charter Var","Private Var"]
    val = [costs["fixed_costs"],costs["crew_costs"],costs["var_charter"],costs["var_private"]]
    fig = go.Figure(go.Pie(labels=lbl, values=val, hole=0.56,
        marker=dict(colors=[COLORS["fixed"],COLORS["crew"],COLORS["charter"],COLORS["private"]],
                    line=dict(color="#0B1629",width=2)),
        textinfo="label+percent", textfont=dict(size=11,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    fig.add_annotation(text=f"<b>{costs['grand_total']/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
                       x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"),align="center")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10), height=320,
                      legend=dict(orientation="h",yanchor="bottom",y=-0.2,bgcolor="rgba(0,0,0,0)"))
    return fig

def chart_stacked_bars(costs):
    cats = ["Charter","Private","Total"]; th = max(costs["total_hours"],1)
    fig = go.Figure(data=[
        go.Bar(name="Fixed",x=cats,marker_color=COLORS["fixed"],
               y=[costs["total_fixed"]*(costs["h_charter"]/th),costs["total_fixed"]*(costs["h_private"]/th),costs["total_fixed"]]),
        go.Bar(name="Charter Var",x=cats,marker_color=COLORS["charter"],y=[costs["var_charter"],0,costs["var_charter"]]),
        go.Bar(name="Private Var",x=cats,marker_color=COLORS["private"],y=[0,costs["var_private"],costs["var_private"]]),
    ])
    fig.update_layout(barmode="stack",paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"),height=300,
                      yaxis=dict(title="Cost (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.35,bgcolor="rgba(0,0,0,0)"),
                      margin=dict(t=10,b=40,l=10,r=10))
    return fig

def chart_waterfall(costs, prof):
    fig = go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","total"],
        x=["Gross Revenue","Commission","Variable","Fixed","Net Result"],
        y=[prof["gross_revenue"],-prof["commission"],-costs["total_variable"],-costs["total_fixed"],prof["net_result"]],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=COLORS["profit"]),decreasing=dict(marker_color=COLORS["loss"]),
        totals=dict(marker_color=COLORS["profit"] if prof["net_result"]>=0 else COLORS["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10),height=340,
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def chart_sensitivity(aircraft, h_private, commission_pct, custom_rate=None):
    hrs = list(range(0,801,25))
    res = [calculate_profitability(calculate_costs(aircraft,h,h_private),commission_pct,custom_rate)["net_result"] for h in hrs]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hrs,y=res,mode="lines",
                             line=dict(color=COLORS["charter"],width=2.5),
                             fill="tozeroy",fillcolor="rgba(74,144,217,0.12)",
                             hovertemplate="<b>%{x}h</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#C9A84C",line_width=1.5)
    for i in range(1,len(res)):
        if res[i-1]<0<=res[i]:
            fig.add_vline(x=hrs[i],line_dash="dot",line_color="#E8C46A",line_width=1.5,
                         annotation_text=f"Break-even ~{hrs[i]}h",annotation_font_color="#E8C46A",
                         annotation_position="top right")
            break
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10),height=300,showlegend=False,
                      yaxis=dict(title="Net Result (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Charter Hours",gridcolor="#1A3A6E"))
    return fig

def cm_global_donut(op, direct, indirect):
    lbl=["Operational","Direct","Indirect/Crew"]; val=[op,direct,indirect]
    clr=["#60A5FA","#F59E0B","#A78BFA"]; total=sum(val)
    fig=go.Figure(go.Pie(labels=lbl,values=val,hole=0.56,
        marker=dict(colors=clr,line=dict(color="#0B1629",width=2)),
        textinfo="label+percent",textfont=dict(size=11,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<extra></extra>"))
    fig.add_annotation(text=f"<b>{total/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
                       x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"),align="center")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10),height=360,legend=dict(orientation="h",yanchor="bottom",y=-0.15,bgcolor="rgba(0,0,0,0)"))
    return fig

def cm_waterfall_global(op, direct, indirect, charter_rev, commission_pct):
    comm=charter_rev*commission_pct/100; nr=charter_rev-comm; gt=op+direct+indirect; net=nr-gt
    fig=go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","relative","total"],
        x=["Charter Revenue","Commission","Operational","Direct","Crew/Indirect","Net Result"],
        y=[charter_rev,-comm,-op,-direct,-indirect,net],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=COLORS["profit"]),decreasing=dict(marker_color=COLORS["loss"]),
        totals=dict(marker_color=COLORS["profit"] if net>=0 else COLORS["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10),height=360,yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def cm_donut(labels, values, colors, title_text):
    total=sum(v for v in values if v>0)
    fig=go.Figure(go.Pie(labels=labels,values=values,hole=0.54,
        marker=dict(colors=colors,line=dict(color="#0B1629",width=2)),
        textinfo="label+percent",textfont=dict(size=10,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<extra></extra>"))
    fig.add_annotation(text=f"<b>{total/1000:.0f}K€</b><br><span style='font-size:9px'>{title_text}</span>",
                       x=0.5,y=0.5,showarrow=False,font=dict(size=14,color="#E8C46A"),align="center")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"),height=300,legend=dict(orientation="h",yanchor="bottom",y=-0.3,bgcolor="rgba(0,0,0,0)",font=dict(size=9)),margin=dict(t=10,b=10,l=5,r=5))
    return fig

def cm_bar_breakdown(categories, values, color, title):
    paired=sorted(zip(values,categories),reverse=True)
    vs,cs=zip(*paired) if paired else ([],[])
    fig=go.Figure(go.Bar(x=list(cs),y=list(vs),marker_color=color,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>",
        text=[f"€{v:,.0f}" for v in vs],textposition="outside",textfont=dict(size=9,color="#D6E4F7")))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#D6E4F7"),height=300,title=dict(text=title,font=dict(size=11,color="#8496B0"),x=0),
                      yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f",title="€"),
                      xaxis=dict(tickangle=-30,gridcolor="rgba(0,0,0,0)"),
                      margin=dict(t=30,b=60,l=10,r=10))
    return fig

# Cost Master defaults
CM_DEFAULTS_OPERATIONAL_PER_FLIGHT = {
    "Handling":800,"Ground Service":600,"Catering":400,"Hotel":1200,
    "ATC Charges":900,"Flight Planning":250,"Permission":350,"Miscellaneous":300,
}
CM_DEFAULTS_DIRECT = {
    "Maintenance":85000,"Maintenance Programs":42000,"Insurance":38000,"Hangar":30000,
    "Management Fee (VAT)":55000,"Government Costs":12000,"Cleaning":8000,
    "Flight Planning Tools":6000,"Nav Programme":9500,
}
CM_DEFAULTS_INDIRECT = {
    "Crew Salaries":180000,"Total Social Costs":54000,"Training Cockpit":18000,
    "Training Cabin":8000,"Expense Training Crew":5000,"Communication Crew":4500,
    "Crew Expenses":22000,"Freelancer":15000,"Miscellaneous Crew":6000,
}


def generate_pdf_report(cm, aircraft_row, annual_flights):
    """Builds a branded Menkor Aviation PDF cost-master report and returns bytes."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                         TableStyle, Image as RLImage, PageBreak, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.utils import ImageReader
    except ImportError:
        raise RuntimeError("ReportLab not installed.")
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=28*mm, bottomMargin=22*mm,
                             leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()

    style_title = ParagraphStyle("MenkorTitle", parent=styles["Title"],
                                  fontName="Helvetica-Bold", fontSize=26, leading=30,
                                  textColor=NAVY, spaceAfter=4, alignment=TA_CENTER)
    style_sub = ParagraphStyle("MenkorSub", parent=styles["Normal"],
                                fontName="Helvetica", fontSize=11, leading=14,
                                textColor=SLATE, alignment=TA_CENTER, spaceAfter=2)
    style_h2 = ParagraphStyle("MenkorH2", parent=styles["Heading2"],
                               fontName="Helvetica-Bold", fontSize=13, leading=16,
                               textColor=NAVY, spaceBefore=14, spaceAfter=8)
    style_body = ParagraphStyle("MenkorBody", parent=styles["Normal"],
                                 fontName="Helvetica", fontSize=9.5, leading=13,
                                 textColor=HexColor("#1A1A1A"))
    style_small = ParagraphStyle("MenkorSmall", parent=styles["Normal"],
                                  fontName="Helvetica", fontSize=8, leading=10,
                                  textColor=SLATE)

    story = []

    # ── COVER PAGE ───────────────────────────────────────────────────────
    logo_buf = _b64_to_imgbuf(_get_logo_b64())
    logo_img = RLImage(logo_buf, width=70*mm, height=42*mm, kind="proportional")
    logo_img.hAlign = "CENTER"
    story.append(Spacer(1, 6*mm))
    story.append(logo_img)
    story.append(Spacer(1, 10*mm))

    story.append(Paragraph("AVIATION COST MASTER REPORT", style_title))
    story.append(Paragraph(f"{aircraft_row['Modele']}", ParagraphStyle(
        "AcName", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16,
        textColor=GOLD, alignment=TA_CENTER, spaceBefore=6, spaceAfter=4)))
    story.append(Paragraph(f"{aircraft_row.get('Categorie','')}", style_sub))
    story.append(Spacer(1, 8*mm))

    story.append(Spacer(1, 20*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD, spaceAfter=8))
    from datetime import date
    story.append(Paragraph(f"Report generated on {date.today().strftime('%d %B %Y')}", style_sub))
    story.append(Paragraph("Menkor Aviation — Operating Cost Simulation", style_sub))
    story.append(PageBreak())

    # ── SUMMARY ──────────────────────────────────────────────────────────
    op_a, dir_a, ind_a = cm["op_annual"], cm["dir_total"], cm["ind_total"]
    grand = op_a + dir_a + ind_a
    gross_rev  = cm["charter_rate"] * cm["h_charter"]
    commission = gross_rev * cm["commission_pct"] / 100
    net_rev    = gross_rev - commission
    net_result = net_rev - grand
    coverage   = (net_rev / grand * 100) if grand > 0 else 0

    story.append(Paragraph("Executive Summary", style_h2))
    summary_data = [
        ["Total Annual Operating Cost", f"€ {grand:,.0f}"],
        ["  · Operational Costs", f"€ {op_a:,.0f}"],
        ["  · Direct Costs", f"€ {dir_a:,.0f}"],
        ["  · Indirect / Crew Costs", f"€ {ind_a:,.0f}"],
        ["Gross Charter Revenue", f"€ {gross_rev:,.0f}"],
        ["Operator Commission", f"€ {commission:,.0f}"],
        ["Net Charter Revenue", f"€ {net_rev:,.0f}"],
        ["Net Result", f"€ {net_result:,.0f}"],
        ["Cost Coverage Rate", f"{coverage:.1f} %"],
    ]
    t = Table(summary_data, colWidths=[100*mm, 60*mm])
    t.setStyle(TableStyle([
        ("FONTNAME", (0,0), (-1,-1), "Helvetica"),
        ("FONTNAME", (0,0), (0,0), "Helvetica-Bold"),
        ("FONTNAME", (0,4), (0,4), "Helvetica-Bold"),
        ("FONTNAME", (0,7), (0,7), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 9.5),
        ("TEXTCOLOR", (1,7), (1,7), GREEN if net_result>=0 else RED),
        ("FONTNAME", (1,7), (1,7), "Helvetica-Bold"),
        ("ALIGN", (1,0), (1,-1), "RIGHT"),
        ("LINEBELOW", (0,0), (-1,0), 0.6, NAVY),
        ("LINEBELOW", (0,3), (-1,3), 0.4, HexColor("#CCCCCC")),
        ("LINEBELOW", (0,6), (-1,6), 0.4, HexColor("#CCCCCC")),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("BACKGROUND", (0,0), (-1,0), LIGHT),
    ]))
    story.append(t)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"Annual flights: <b>{annual_flights}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Charter hours: <b>{cm['h_charter']} h</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Charter rate: <b>€ {cm['charter_rate']:,.0f}/h</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Commission: <b>{cm['commission_pct']} %</b>", style_body))

    # ── COST CATEGORY TABLES ────────────────────────────────────────────
    def cost_table(title, vals, color, per_flight=False):
        story.append(Paragraph(title, style_h2))
        rows = [["Line Item", "Per Unit (€)" if per_flight else "Annual (€)", "Annual (€)", "% of Total"]]
        for k, v in vals.items():
            annual_v = v * annual_flights if per_flight else v
            pct = annual_v / grand * 100 if grand > 0 else 0
            if per_flight:
                rows.append([k, f"€ {v:,.0f}", f"€ {annual_v:,.0f}", f"{pct:.1f}%"])
            else:
                rows.append([k, "", f"€ {annual_v:,.0f}", f"{pct:.1f}%"])
        if not per_flight:
            rows = [["Line Item", "Annual (€)", "% of Total"]]
            for k, v in vals.items():
                pct = v / grand * 100 if grand > 0 else 0
                rows.append([k, f"€ {v:,.0f}", f"{pct:.1f}%"])
            colw = [90*mm, 45*mm, 25*mm]
        else:
            colw = [70*mm, 35*mm, 35*mm, 20*mm]

        tbl = Table(rows, colWidths=colw, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTNAME", (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE", (0,0), (-1,-1), 8.5),
            ("TEXTCOLOR", (0,0), (-1,0), HexColor("#FFFFFF")),
            ("BACKGROUND", (0,0), (-1,0), color),
            ("ALIGN", (1,0), (-1,-1), "RIGHT"),
            ("ALIGN", (0,0), (0,-1), "LEFT"),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [HexColor("#FFFFFF"), LIGHT]),
            ("TOPPADDING", (0,0), (-1,-1), 3.5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 3.5),
            ("GRID", (0,0), (-1,-1), 0.3, HexColor("#DDDDDD")),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 5*mm))

    cost_table("✈ Operational Costs (per flight)", cm["op_vals"], BLUE, per_flight=True)
    cost_table("🔧 Direct Costs (annual)", cm["dir_vals"], AMBER)
    cost_table("👥 Indirect / Crew Costs (annual)", cm["ind_vals"], PURPLE)

    story.append(PageBreak())

    # ── CHARTS PAGE (embed plotly charts as images) ─────────────────────
    # (Charts omitted — no kaleido dependency)

    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=HexColor("#CCCCCC")))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "Menkor Aviation — Figures are indicative and for simulation purposes only. "
        "This report is generated automatically based on user-provided and benchmark data.",
        style_small))

    # ── Logo header + footer sur chaque page via canvas callbacks ──────
    page_w, page_h = A4
    logo_data = base64.b64decode(_get_logo_b64() or "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    from reportlab.lib.utils import ImageReader

    def _draw_header_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        # Header: logo Menkor à gauche + ligne gold
        logo_io = ImageReader(BytesIO(logo_data))
        canvas_obj.drawImage(logo_io, 18*mm, page_h - 22*mm, width=38*mm, height=14*mm,
                              preserveAspectRatio=True, mask="auto")
        canvas_obj.setStrokeColor(GOLD)
        canvas_obj.setLineWidth(0.8)
        canvas_obj.line(18*mm, page_h - 23*mm, page_w - 18*mm, page_h - 23*mm)
        # Footer: ligne gold + texte centré + numéro de page
        canvas_obj.line(18*mm, 14*mm, page_w - 18*mm, 14*mm)
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(HexColor("#8496B0"))
        canvas_obj.drawCentredString(page_w / 2, 9*mm,
            "Menkor Aviation GBL — Confidential — Operating Cost Simulation")
        canvas_obj.drawRightString(page_w - 18*mm, 9*mm,
            f"Page {canvas_obj.getPageNumber()}")
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)
    buf.seek(0)
    return buf.getvalue()

# ════════════════════════════════════════════════════════════════════════════
# QUOTATION PDF
# ════════════════════════════════════════════════════════════════════════════
def generate_quotation_pdf(qr: dict, aircraft_row) -> bytes:
    """Generate a branded Menkor Aviation charter quotation PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                         TableStyle, Image as RLImage, PageBreak, HRFlowable)
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.utils import ImageReader
        from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect
    except ImportError:
        raise RuntimeError("ReportLab not installed.")
    import math
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             topMargin=28*mm, bottomMargin=22*mm,
                             leftMargin=18*mm, rightMargin=18*mm)
    styles = getSampleStyleSheet()

    NAVY_C = HexColor("#112244"); GOLD_C = HexColor("#C9A84C")
    SLATE_C = HexColor("#5A6B85"); LIGHT_C = HexColor("#F4F6FA")
    BLUE_C  = HexColor("#1A3A6E")

    style_title = ParagraphStyle("QT", parent=styles["Title"],
        fontName="Helvetica-Bold", fontSize=24, textColor=NAVY_C,
        alignment=TA_CENTER, spaceAfter=4)
    style_sub = ParagraphStyle("QS", parent=styles["Normal"],
        fontName="Helvetica", fontSize=11, textColor=SLATE_C,
        alignment=TA_CENTER, spaceAfter=2)
    style_h2 = ParagraphStyle("QH2", parent=styles["Heading2"],
        fontName="Helvetica-Bold", fontSize=12, textColor=NAVY_C,
        spaceBefore=10, spaceAfter=6)
    style_small = ParagraphStyle("QSm", parent=styles["Normal"],
        fontName="Helvetica", fontSize=7.5, textColor=SLATE_C)

    # Canvas callbacks for header/footer
    page_w, page_h = A4
    logo_data = base64.b64decode(_get_logo_b64() or "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    from reportlab.lib.utils import ImageReader

    def _hf(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.drawImage(ImageReader(BytesIO(logo_data)),
                              18*mm, page_h-22*mm, width=38*mm, height=14*mm,
                              preserveAspectRatio=True, mask="auto")
        canvas_obj.setStrokeColor(GOLD_C); canvas_obj.setLineWidth(0.8)
        canvas_obj.line(18*mm, page_h-23*mm, page_w-18*mm, page_h-23*mm)
        canvas_obj.line(18*mm, 14*mm, page_w-18*mm, 14*mm)
        canvas_obj.setFont("Helvetica", 7); canvas_obj.setFillColor(SLATE_C)
        canvas_obj.drawCentredString(page_w/2, 9*mm,
            "Menkor Aviation GBL — Confidential Charter Quotation")
        canvas_obj.drawRightString(page_w-18*mm, 9*mm,
            f"Page {canvas_obj.getPageNumber()}")
        canvas_obj.restoreState()

    from datetime import date
    story = []

    # ── Cover ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph("CHARTER FLIGHT QUOTATION", style_title))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(qr["aircraft"], ParagraphStyle("QAC",
        parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=16,
        textColor=GOLD_C, alignment=TA_CENTER, spaceBefore=4, spaceAfter=2)))
    story.append(Paragraph(str(aircraft_row.get("Categorie","")), style_sub))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=GOLD_C, spaceAfter=6))
    story.append(Paragraph(f"Date: {date.today().strftime('%d %B %Y')}", style_sub))
    story.append(Paragraph("Menkor Aviation GBL — Charter Quotation", style_sub))
    story.append(PageBreak())

    # ── Map page ─────────────────────────────────────────────────────────
    # ── Route Map (pure ReportLab — no kaleido needed) ──────────────────
    try:
        from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect
        from reportlab.graphics import renderPDF
        from reportlab.lib.colors import HexColor as HC

        map_w_pt = 173 * mm
        map_h_pt = 95  * mm

        all_lats = [l["lat1"] for l in qr["legs"]] + [l["lat2"] for l in qr["legs"]]
        all_lons = [l["lon1"] for l in qr["legs"]] + [l["lon2"] for l in qr["legs"]]
        lat_min, lat_max = min(all_lats), max(all_lats)
        lon_min, lon_max = min(all_lons), max(all_lons)
        pad_lat = max((lat_max - lat_min) * 0.35, 5)
        pad_lon = max((lon_max - lon_min) * 0.35, 8)
        lat_min -= pad_lat; lat_max += pad_lat
        lon_min -= pad_lon; lon_max += pad_lon

        def to_xy(lat, lon):
            x = (lon - lon_min) / (lon_max - lon_min) * map_w_pt
            y = (lat - lat_min) / (lat_max - lat_min) * map_h_pt
            return x, y

        d = Drawing(map_w_pt, map_h_pt)
        # Background
        d.add(Rect(0, 0, map_w_pt, map_h_pt, fillColor=HC("#0B1629"), strokeColor=HC("#C9A84C"), strokeWidth=1.5))

        # Grid lines (graticule)
        import math
        grid_col = HC("#1A3060")
        for lat_g in range(-80, 81, 20):
            if lat_min <= lat_g <= lat_max:
                _, y = to_xy(lat_g, lon_min)
                d.add(Line(0, y, map_w_pt, y, strokeColor=grid_col, strokeWidth=0.3))
        for lon_g in range(-180, 181, 30):
            if lon_min <= lon_g <= lon_max:
                x, _ = to_xy(0, lon_g)
                d.add(Line(x, 0, x, map_h_pt, strokeColor=grid_col, strokeWidth=0.3))

        leg_colors = ["#C9A84C", "#60A5FA", "#4ADE80", "#F87171", "#A78BFA"]
        n_steps = 40

        for i, leg in enumerate(qr["legs"]):
            clr = HC(leg_colors[i % len(leg_colors)])
            pts = []
            for s in range(n_steps + 1):
                f = s / n_steps
                lat = leg["lat1"] + (leg["lat2"] - leg["lat1"]) * f
                lon = leg["lon1"] + (leg["lon2"] - leg["lon1"]) * f
                pts.append(to_xy(lat, lon))
            # Draw arc as series of line segments
            for s in range(len(pts) - 1):
                d.add(Line(pts[s][0], pts[s][1], pts[s+1][0], pts[s+1][1],
                           strokeColor=clr, strokeWidth=2))
            # Arrow at midpoint
            mid = len(pts) // 2
            if mid > 0:
                dx = pts[mid][0] - pts[mid-1][0]
                dy = pts[mid][1] - pts[mid-1][1]
                mx, my = pts[mid]
                d.add(Circle(mx, my, 3, fillColor=clr, strokeColor=clr, strokeWidth=0))

        # Airport dots + labels
        seen_ap = {}
        for leg in qr["legs"]:
            for lk, lok, nk in [("lat1","lon1","from_name"),("lat2","lon2","to_name")]:
                key = (round(leg[lk],1), round(leg[lok],1))
                if key not in seen_ap:
                    seen_ap[key] = True
                    x, y = to_xy(leg[lk], leg[lok])
                    # Glow
                    d.add(Circle(x, y, 7, fillColor=HC("#C9A84C"), strokeColor=None, strokeWidth=0, fillOpacity=0.25))
                    # Dot
                    d.add(Circle(x, y, 4, fillColor=HC("#FFFFFF"), strokeColor=HC("#C9A84C"), strokeWidth=1.5))
                    # Label
                    name = leg[nk][:20]
                    d.add(String(x + 7, y - 3, name, fontSize=7, fillColor=HC("#E8C46A"),
                                 fontName="Helvetica-Bold"))

        story.append(PageBreak())
        story.append(Paragraph("Route Map", style_h2))
        story.append(Spacer(1, 2*mm))

        # Frame
        map_table = Table([[d]], colWidths=[map_w_pt + 4])
        map_table.setStyle(TableStyle([
            ("BOX",            (0,0),(-1,-1), 1.5, HC("#C9A84C")),
            ("TOPPADDING",     (0,0),(-1,-1), 2),
            ("BOTTOMPADDING",  (0,0),(-1,-1), 2),
            ("LEFTPADDING",    (0,0),(-1,-1), 2),
            ("RIGHTPADDING",   (0,0),(-1,-1), 2),
            ("BACKGROUND",     (0,0),(-1,-1), HC("#0B1629")),
        ]))
        story.append(map_table)

        # Route label
        route_parts = []
        for idx2, leg in enumerate(qr["legs"]):
            if idx2 == 0: route_parts.append(leg["from_name"].upper())
            route_parts.append(leg["to_name"].upper())
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph("  ✈  ".join(route_parts), ParagraphStyle(
            "RouteLabel", parent=styles["Normal"],
            fontName="Helvetica-Bold", fontSize=8,
            textColor=HC("#C9A84C"), alignment=TA_CENTER, spaceAfter=4)))
        story.append(Spacer(1, 5*mm))

    except Exception as map_err:
        story.append(Paragraph(f"Route map: {str(map_err)[:80]}", ParagraphStyle(
            "MapErr", parent=styles["Normal"], fontSize=7, textColor=HC("#8496B0"))))
        story.append(Spacer(1, 4*mm))

    # ── Route summary
    # ── Route summary ────────────────────────────────────────────────────
    story.append(Paragraph("Flight Itinerary", style_h2))

    # Route string
    route_parts = []
    for i, leg in enumerate(qr["legs"]):
        if i == 0: route_parts.append(leg["from_name"])
        route_parts.append(leg["to_name"])
    route_str = "  →  ".join(route_parts)
    story.append(Paragraph(f'<b style="color:#C9A84C">{route_str}</b>',
        ParagraphStyle("QRoute", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=11, textColor=GOLD_C,
        spaceAfter=8)))

    # Leg table
    leg_header = ["Leg", "From", "To", "Dep.", "Distance", "Flight Time",
                  f"Cost ({qr['currency']})"]
    leg_table_data = [leg_header]
    for i, leg in enumerate(qr["legs"]):
        leg_table_data.append([
            str(i+1),
            leg["from_name"], leg["to_name"],
            leg["dep_time"],
            f"{leg['dist_km']:,.0f} km",
            leg["flight_time_str"],
            f"{qr['currency']} {leg['cost']:,.0f}",
        ])
    # Totals row
    leg_table_data.append([
        "TOTAL", "", "",  "",
        f"{qr['total_dist']:,.0f} km",
        f"{int(qr['total_min']//60)}h {int(qr['total_min']%60):02d}m",
        f"{qr['currency']} {qr['total_cost']:,.0f}",
    ])

    col_w = [10*mm, 32*mm, 32*mm, 16*mm, 24*mm, 22*mm, 28*mm]
    leg_tbl = Table(leg_table_data, colWidths=col_w, repeatRows=1)
    leg_tbl.setStyle(TableStyle([
        ("FONTNAME",    (0,0),  (-1,0),  "Helvetica-Bold"),
        ("FONTNAME",    (0,1),  (-1,-2), "Helvetica"),
        ("FONTNAME",    (0,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",    (0,0),  (-1,-1), 8.5),
        ("TEXTCOLOR",   (0,0),  (-1,0),  HexColor("#FFFFFF")),
        ("BACKGROUND",  (0,0),  (-1,0),  NAVY_C),
        ("BACKGROUND",  (0,-1), (-1,-1), LIGHT_C),
        ("TEXTCOLOR",   (6,-1), (6,-1),  GOLD_C),
        ("FONTNAME",    (6,-1), (6,-1),  "Helvetica-Bold"),
        ("ALIGN",       (0,0),  (0,-1),  "CENTER"),
        ("ALIGN",       (4,0),  (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-2), [HexColor("#FFFFFF"), LIGHT_C]),
        ("GRID",        (0,0),  (-1,-1), 0.3, HexColor("#DDDDDD")),
        ("TOPPADDING",  (0,0),  (-1,-1), 4),
        ("BOTTOMPADDING",(0,0), (-1,-1), 4),
        ("LINEABOVE",   (0,-1), (-1,-1), 1, GOLD_C),
    ]))
    story.append(leg_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Aircraft specs ───────────────────────────────────────────────────
    story.append(Paragraph("Aircraft Specifications", style_h2))
    spec_data = [
        ["Aircraft", qr["aircraft"], "Category", str(aircraft_row.get("Categorie","—"))],
        ["Cruise Speed", f"{aircraft_row.get('Vitesse_Croisiere_km_h','—')} km/h",
         "Max Range", f"{aircraft_row.get('Autonomie_km',0):,.0f} km"],
        ["Max Passengers", str(aircraft_row.get("Passagers_Max","—")),
         "Operator Rate", f"{qr['currency']} {qr['rate']:,.0f}/h"],
    ]
    spec_tbl = Table(spec_data, colWidths=[38*mm, 47*mm, 38*mm, 47*mm])
    spec_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0,0),  (-1,-1), "Helvetica"),
        ("FONTNAME",  (0,0),  (0,-1),  "Helvetica-Bold"),
        ("FONTNAME",  (2,0),  (2,-1),  "Helvetica-Bold"),
        ("FONTSIZE",  (0,0),  (-1,-1), 9),
        ("TEXTCOLOR", (0,0),  (0,-1),  NAVY_C),
        ("TEXTCOLOR", (2,0),  (2,-1),  NAVY_C),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [LIGHT_C, HexColor("#FFFFFF")]),
        ("GRID",      (0,0),  (-1,-1), 0.3, HexColor("#DDDDDD")),
        ("TOPPADDING",(0,0),  (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story.append(spec_tbl)
    story.append(Spacer(1, 8*mm))

    # ── Extras & Notes ──────────────────────────────────────────────────
    if qr.get("extras"):
        story.append(Paragraph("Extras & Additional Services", style_h2))
        ext_header = ["Service", f"Cost ({qr['currency']})"]
        ext_data = [ext_header] + [[e["name"], f"{qr['currency']} {e['cost']:,.0f}"] for e in qr["extras"]]
        ext_data.append(["TOTAL EXTRAS", f"{qr['currency']} {qr.get('extras_total',0):,.0f}"])
        ext_tbl = Table(ext_data, colWidths=[120*mm, 50*mm])
        ext_tbl.setStyle(TableStyle([
            ("FONTNAME",   (0,0),  (-1,0),  "Helvetica-Bold"),
            ("FONTNAME",   (0,1),  (-1,-2), "Helvetica"),
            ("FONTNAME",   (0,-1), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0),  (-1,-1), 9),
            ("TEXTCOLOR",  (0,0),  (-1,0),  HexColor("#FFFFFF")),
            ("BACKGROUND", (0,0),  (-1,0),  NAVY_C),
            ("BACKGROUND", (0,-1), (-1,-1), LIGHT_C),
            ("ALIGN",      (1,0),  (1,-1),  "RIGHT"),
            ("ROWBACKGROUNDS",(0,1),(-1,-2),[HexColor("#FFFFFF"), LIGHT_C]),
            ("GRID",       (0,0),  (-1,-1), 0.3, HexColor("#DDDDDD")),
            ("TOPPADDING", (0,0),  (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LINEABOVE",  (0,-1), (-1,-1), 1, GOLD_C),
            ("TEXTCOLOR",  (1,-1), (1,-1),  GOLD_C),
        ]))
        story.append(ext_tbl)
        story.append(Spacer(1, 4*mm))

    # Grand total box
    flight_c = qr.get("flight_cost", qr["total_cost"])
    extras_c = qr.get("extras_total", 0)
    total_c  = qr["total_cost"]
    total_data = [
        ["Flight Cost", f"{qr['currency']} {flight_c:,.0f}"],
        ["Extras", f"{qr['currency']} {extras_c:,.0f}"],
        ["TOTAL QUOTATION", f"{qr['currency']} {total_c:,.0f}"],
    ]
    tot_tbl = Table(total_data, colWidths=[120*mm, 50*mm])
    tot_tbl.setStyle(TableStyle([
        ("FONTNAME",  (0,0),  (-1,-2), "Helvetica"),
        ("FONTNAME",  (0,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0),  (-1,-2), 10),
        ("FONTSIZE",  (0,-1), (-1,-1), 13),
        ("ALIGN",     (1,0),  (1,-1),  "RIGHT"),
        ("BACKGROUND",(0,-1), (-1,-1), NAVY_C),
        ("TEXTCOLOR", (0,-1), (-1,-1), GOLD_C),
        ("TOPPADDING",(0,0),  (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LINEABOVE", (0,-1), (-1,-1), 1.5, GOLD_C),
    ]))
    story.append(tot_tbl)
    story.append(Spacer(1, 5*mm))

    if qr.get("notes"):
        story.append(Paragraph(f"<b>Special Notes:</b> {qr['notes']}", ParagraphStyle(
            "QNotes", parent=styles["Normal"], fontName="Helvetica",
            fontSize=9, textColor=NAVY_C,
            backColor=LIGHT_C, borderPadding=6)))
        story.append(Spacer(1, 5*mm))

    # ── Disclaimer ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=HexColor("#CCCCCC"), spaceAfter=4))
    story.append(Paragraph(
        "This quotation is indicative and subject to aircraft availability, fuel surcharges, "
        "overflight permits, and applicable taxes. Valid for 48 hours from date of issue. "
        "All times are estimated. Menkor Aviation GBL reserves the right to adjust pricing.",
        style_small))

    doc.build(story, onFirstPage=_hf, onLaterPages=_hf)
    buf.seek(0)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
# ════════════════════════════════════════════════════════════════════════════
# AUTH & STRIPE
# ════════════════════════════════════════════════════════════════════════════
import hashlib
import re as _re

def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _get_users():
    if "_users_db" not in st.session_state:
        try:
            import json as _j
            st.session_state["_users_db"] = _j.loads(st.secrets.get("USERS_DB","{}"))
        except Exception:
            st.session_state["_users_db"] = {}
    return st.session_state["_users_db"]

def _save_users(u):
    st.session_state["_users_db"] = u

def _register(email, pwd):
    email = email.strip().lower()
    if not _re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False, "Invalid email."
    if len(pwd) < 6:
        return False, "Password must be at least 6 characters."
    u = _get_users()
    if email in u:
        return False, "Account already exists."
    u[email] = {"pwd_hash": _hash(pwd), "stripe_cid": None, "active": False}
    _save_users(u)
    return True, "Account created!"

def _login(email, pwd):
    email = email.strip().lower()
    u = _get_users()
    rec = u.get(email)
    if not rec or rec["pwd_hash"] != _hash(pwd):
        return False, "Incorrect email or password."
    return True, rec

def _check_subscription(email):
    try:
        import stripe
        stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
        u = _get_users()
        cid = u.get(email, {}).get("stripe_cid")
        if not cid:
            customers = stripe.Customer.list(email=email, limit=1)
            if not customers.data:
                return False
            cid = customers.data[0].id
            u[email]["stripe_cid"] = cid
            _save_users(u)
        subs = stripe.Subscription.list(customer=cid, status="active", limit=1)
        active = len(subs.data) > 0
        u[email]["active"] = active
        _save_users(u)
        return active
    except Exception:
        return False

def _checkout_url(email):
    try:
        import stripe
        stripe.api_key = st.secrets["STRIPE_SECRET_KEY"]
        s = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=email,
            line_items=[{"price": st.secrets["STRIPE_PRICE_ID"], "quantity": 1}],
            success_url="https://aviation-cost-estimato-6uj3ptpc57onofwlavwhfn.streamlit.app/?subscribed=1",
            cancel_url="https://aviation-cost-estimato-6uj3ptpc57onofwlavwhfn.streamlit.app/?cancelled=1",
        )
        return s.url
    except Exception:
        return None

def _sub_button(email):
    url = _checkout_url(email)
    if url:
        st.markdown(f'''<div style="text-align:center;margin-top:0.6rem">
        <a href="{url}" target="_blank" style="background:#C9A84C;color:#0B1629;
           padding:0.5rem 1.2rem;border-radius:5px;font-weight:700;
           text-decoration:none;font-size:0.85rem">⭐ Subscribe — 10€/month</a>
        </div>''', unsafe_allow_html=True)

def render_auth_wall():
    """Sidebar auth. Returns True if premium."""
    for k, v in [("auth_email",None),("auth_premium",False),("auth_is_admin",False)]:
        if k not in st.session_state:
            st.session_state[k] = v

    email    = st.session_state["auth_email"]
    is_admin = st.session_state["auth_is_admin"]

    with st.sidebar:
        st.markdown("---")
        if email:
            if is_admin:
                st.markdown('<div style="font-size:0.78rem;color:#F59E0B;font-weight:700">👑 ADMIN — Menkor Aviation</div>', unsafe_allow_html=True)
                st.markdown('<div style="font-size:0.7rem;color:#4ADE80;margin-bottom:0.5rem">Full access unlocked</div>', unsafe_allow_html=True)
                with st.expander("👥 User Management"):
                    users = _get_users()
                    if users:
                        for ue, ud in users.items():
                            active = ud.get("active", False)
                            col = "#4ADE80" if active else "#F87171"
                            st.markdown(f'<div style="font-size:0.75rem;padding:0.2rem 0;border-bottom:1px solid #1A3A6E"><b>{ue}</b> <span style="color:{col}">{"✓ Active" if active else "✗ Inactive"}</span></div>', unsafe_allow_html=True)
                        st.caption(f"{len(users)} user(s)")
                    else:
                        st.caption("No users yet.")
                    if st.button("🔄 Refresh", use_container_width=True, key="admin_refresh"):
                        for ue in list(users.keys()):
                            users[ue]["active"] = _check_subscription(ue)
                        _save_users(users)
                        st.rerun()
            else:
                premium = st.session_state["auth_premium"]
                st.markdown(f'<div style="font-size:0.78rem;color:#4ADE80">✓ {email}</div>', unsafe_allow_html=True)
                if premium:
                    st.markdown('<div style="font-size:0.72rem;color:#C9A84C">⭐ Premium</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="font-size:0.72rem;color:#F87171;margin-bottom:0.4rem">⚠ No subscription</div>', unsafe_allow_html=True)
                    _sub_button(email)
                    if st.button("🔄 Check subscription", use_container_width=True, key="chk_sub"):
                        st.session_state["auth_premium"] = _check_subscription(email)
                        st.rerun()
            if st.button("🚪 Log out", use_container_width=True, key="btn_logout"):
                st.session_state["auth_email"] = None
                st.session_state["auth_premium"] = False
                st.session_state["auth_is_admin"] = False
                st.rerun()
        else:
            st.markdown('<div class="section-header">🔐 Account</div>', unsafe_allow_html=True)
            view = st.radio("Account", ["Login", "Register"], horizontal=True,
                            key="auth_view", label_visibility="collapsed")
            if view == "Login":
                em = st.text_input("Email", key="li_em", placeholder="your@email.com")
                pw = st.text_input("Password", key="li_pw", type="password")
                if st.button("Login", use_container_width=True, key="btn_login"):
                    if em and pw:
                        try:
                            admin_email = st.secrets.get("ADMIN_EMAIL","")
                            admin_pwd   = st.secrets.get("ADMIN_PASSWORD","")
                        except Exception:
                            admin_email = admin_pwd = ""
                        if em.strip().lower() == admin_email.lower() and pw == admin_pwd:
                            st.session_state["auth_email"]    = em.strip().lower()
                            st.session_state["auth_premium"]  = True
                            st.session_state["auth_is_admin"] = True
                            st.rerun()
                        else:
                            ok, result = _login(em, pw)
                            if ok:
                                st.session_state["auth_email"]    = em.strip().lower()
                                st.session_state["auth_premium"]  = _check_subscription(em.strip().lower())
                                st.session_state["auth_is_admin"] = False
                                st.rerun()
                            else:
                                st.error(result)
                    else:
                        st.warning("Fill in all fields.")
            else:
                em  = st.text_input("Email", key="rg_em", placeholder="your@email.com")
                pw  = st.text_input("Password (min 6)", key="rg_pw", type="password")
                pw2 = st.text_input("Confirm password", key="rg_pw2", type="password")
                if st.button("Create account", use_container_width=True, key="btn_reg"):
                    if pw != pw2:
                        st.error("Passwords do not match.")
                    elif em and pw:
                        ok, msg = _register(em, pw)
                        if ok:
                            st.success(msg)
                            _sub_button(em.strip().lower())
                        else:
                            st.error(msg)
                    else:
                        st.warning("Fill in all fields.")
            st.markdown('<div style="font-size:0.7rem;color:#8496B0;text-align:center;margin-top:0.4rem">Dashboard free · Full access 10€/month</div>', unsafe_allow_html=True)

    return st.session_state.get("auth_premium", False)

def premium_gate():
    email = st.session_state.get("auth_email")
    st.markdown("""
    <div style="background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
         border:1px solid #C9A84C;border-radius:12px;padding:2.5rem;text-align:center;margin:2rem 0">
        <div style="font-size:2rem;margin-bottom:0.8rem">🔒</div>
        <div style="font-size:1.3rem;font-weight:700;color:#E8C46A;margin-bottom:0.5rem">Premium Feature</div>
        <div style="font-size:0.9rem;color:#8496B0;margin-bottom:1.5rem">
            Full access requires a subscription.<br><b style="color:#C9A84C">€10/month</b> — cancel anytime.
        </div>
        <div style="font-size:0.82rem;color:#D6E4F7">
            ✓ Profitability &nbsp;·&nbsp; ✓ Sensitivity &nbsp;·&nbsp; ✓ Cost Master &nbsp;·&nbsp; ✓ PDF Reports
        </div>
    </div>""", unsafe_allow_html=True)
    if not email:
        st.info("👈 Create a free account in the sidebar to get started.")
    else:
        _sub_button(email)


def main():
    # ── Session state init ───────────────────────────────────────────────
    for _key, _val in [("database", None), ("cost_master", None), ("pdf_report", None),
                       ("auth_email", None), ("auth_premium", False),
                       ("auth_is_admin", False), ("_users_db", {}), ("auth_view", "Login"),
                       ("q_legs", [{"from": "", "to": "", "dep_time": "08:00"}]),
                       ("q_result", None), ("q_pdf", None)]:
        if _key not in st.session_state:
            st.session_state[_key] = _val

    # ── Auth wall (sidebar login/subscribe) ──────────────────────────────
    is_premium = render_auth_wall()

    # Header
    col_logo, col_title = st.columns([1, 6])
    with col_logo:
        st.markdown("<div style='font-size:3rem;text-align:center;margin-top:0.3rem'>✈</div>", unsafe_allow_html=True)
    with col_title:
        st.markdown('<div class="main-title">Aviation Cost Estimator</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Operating Cost Simulation — Business Aviation</div>', unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    df = get_active_db()

    # Sidebar
    with st.sidebar:
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
        h_charter = st.slider("Charter Hours / year", 0, 800, 380, step=10)
        h_private = st.slider("Private Hours / year",  0, 800, 120, step=10)
        if h_charter + h_private > 800:
            st.warning(f"⚠ Total {h_charter+h_private}h exceeds regulatory ceiling (800h)")

        st.markdown('<div class="section-header">💰 Charter Pricing</div>', unsafe_allow_html=True)
        db_rate = float(aircraft.get("Taux_Charter_EUR_h", 0))
        st.caption(f"Reference rate from database: **€ {db_rate:,.0f} / h**")
        use_custom = st.toggle("Set a custom charter price", value=False)
        if use_custom:
            custom_rate = st.number_input("Your charter price (€ / hour)", min_value=0, max_value=100_000,
                                          value=int(db_rate) if db_rate > 0 else 5000, step=100)
            if db_rate > 0:
                diff = custom_rate - db_rate
                diff_pct = diff / db_rate * 100
                color = "#4ADE80" if diff >= 0 else "#F87171"
                arrow = "▲" if diff >= 0 else "▼"
                st.markdown(f'<span style="color:{color};font-size:0.8rem">{arrow} {diff_pct:+.1f}% vs reference rate</span>', unsafe_allow_html=True)
        else:
            custom_rate = db_rate

        commission_pct = st.slider("Operator Commission (%)", 0, 25, 10, step=1)

    costs = calculate_costs(aircraft, h_charter, h_private)
    prof  = calculate_profitability(costs, commission_pct, custom_rate)

    # ════════════════════════════════════════════════════════════════════
    # TABS
    # ════════════════════════════════════════════════════════════════════
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊  Dashboard",
        "📈  Profitability",
        "🔍  Sensitivity",
        "💼  Cost Master",
        "✈️  Quotation",
    ])

    # ── TAB 1 : DASHBOARD ────────────────────────────────────────────────
    with tab1:
        col_id1,col_id2,col_id3,col_id4 = st.columns(4)
        with col_id1:
            st.markdown(f"""<div class="metric-card">
                <div class="metric-label">Selected Aircraft</div>
                <div class="metric-value" style="font-size:1.2rem;color:#000000">{aircraft['Modele']}</div>
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

        col_g1,col_g2 = st.columns(2)
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

    # ── TAB 2 : PROFITABILITY ────────────────────────────────────────────
    with tab2:
        if not is_premium:
            premium_gate()
            st.stop()
        st.markdown('<div class="section-header">Charter Profitability Simulation</div>', unsafe_allow_html=True)
        if h_charter == 0:
            st.warning("⚠ No charter hours configured. Adjust the 'Charter Hours' slider in the sidebar.")
        else:
            net = prof["net_result"]; cr = prof["coverage_rate"]
            badge = ('<span class="tag-ok">✓ PROFITABLE</span>' if net>=0
                     else '<span class="tag-warn">⚠ NEAR BREAK-EVEN</span>' if cr>=70
                     else '<span class="tag-err">✗ LOSS-MAKING</span>')
            st.markdown(f"**Status:** {badge} — Cost coverage rate: **{cr:.1f}%**", unsafe_allow_html=True)
            effective_rate = prof.get("effective_rate", custom_rate)
            st.markdown(f"""
            <div class="metric-card" style="margin-bottom:1rem;margin-top:0.8rem">
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
                    "Parameter": ["Charter rate applied","Charter hours","Operator commission","Gross revenue","Net revenue (after commission)","Total variable costs","Total fixed costs"],
                    "Value": [fmt(effective_rate)+"/h",f"{h_charter} h",f"{commission_pct} %",fmt(prof["gross_revenue"]),fmt(prof["net_revenue"]),fmt(costs["total_variable"]),fmt(costs["total_fixed"])],
                }))

    # ── TAB 3 : SENSITIVITY ──────────────────────────────────────────────
    with tab3:
        if not is_premium:
            premium_gate()
            st.stop()
        st.markdown('<div class="section-header">Sensitivity Analysis — Charter Hours vs Net Result</div>', unsafe_allow_html=True)
        st.caption(f"Private hours fixed at {h_private}h — Commission {commission_pct}% — Rate € {custom_rate:,.0f}/h")
        st.plotly_chart(chart_sensitivity(aircraft, h_private, commission_pct, custom_rate), use_container_width=True, config={"displayModeBar":False})
        st.markdown('<div class="section-header">Fleet Comparison (Cost per Hour)</div>', unsafe_allow_html=True)
        comparison = [{"Model":row["Modele"],"Total Cost (€)":round(calculate_costs(row,h_charter,h_private)["grand_total"]),
                       "Cost/Hour (€)":round(calculate_costs(row,h_charter,h_private)["avg_cost_h"])} for _,row in df.iterrows()]
        df_comp = pd.DataFrame(comparison).sort_values("Total Cost (€)")
        fig_comp = px.bar(df_comp,x="Model",y="Total Cost (€)",color="Cost/Hour (€)",
                          color_continuous_scale=["#1A3A6E","#4A90D9","#C9A84C","#E8C46A"],template="plotly_dark")
        fig_comp.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#D6E4F7"),height=350,
                               coloraxis_colorbar=dict(title="€/h",tickformat=",.0f"),margin=dict(t=10,b=80,l=10,r=10),
                               xaxis=dict(tickangle=-30),yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f"))
        st.plotly_chart(fig_comp, use_container_width=True, config={"displayModeBar":False})


    # ════════════════════════════════════════════════════════════════════
    # TAB 4 : COST MASTER
    # ════════════════════════════════════════════════════════════════════
    with tab4:
        if not is_premium:
            premium_gate()
            st.stop()
        st.markdown('<div class="main-title" style="font-size:1.4rem">💼 Cost Master</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Full operational cost breakdown — Generic benchmarks or your own figures</div>', unsafe_allow_html=True)

        # ── Config ──────────────────────────────────────────────────────
        cfg1, cfg2, cfg3 = st.columns(3)
        with cfg1:
            annual_flights = st.number_input("Annual number of flights", min_value=1, max_value=2000, value=200, step=10)
        with cfg2:
            cm_charter_rate = st.number_input("Charter rate (€/h) for analysis", min_value=0, max_value=200000,
                                              value=int(custom_rate) if custom_rate > 0 else int(db_rate), step=500)
        with cfg3:
            cm_commission = st.slider("Commission (%)", 0, 25, int(commission_pct), step=1, key="cm_comm")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("### ✏️ Cost Input — choose mode per section")

        # ── MODE SELECTORS ───────────────────────────────────────────────
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            use_generic_op = st.radio("✈ Operational Costs", ["🌐 Generic", "✏️ Custom"], horizontal=True, key="gop") == "🌐 Generic"
        with mc2:
            use_generic_dir = st.radio("🔧 Direct Costs", ["🌐 Generic", "✏️ Custom"], horizontal=True, key="gdir") == "🌐 Generic"
        with mc3:
            use_generic_ind = st.radio("👥 Indirect / Crew", ["🌐 Generic", "✏️ Custom"], horizontal=True, key="gind") == "🌐 Generic"

        # ── HELPER: render a cost block ──────────────────────────────────
        def render_cost_block(title, color, defaults, prefix, use_generic, step=100.0):
            vals = {}
            with st.expander(title, expanded=True):
                mode_label = "🌐 GENERIC BENCHMARK" if use_generic else "✏️ CUSTOM — edit below"
                st.markdown(f'<div style="font-size:0.72rem;color:{color};letter-spacing:0.1em;margin-bottom:0.6rem">{mode_label}</div>',
                            unsafe_allow_html=True)
                pairs = list(defaults.items())
                for i in range(0, len(pairs), 2):
                    c1, c2, c3, c4 = st.columns([2.2, 1, 2.2, 1])
                    k1, d1 = pairs[i]
                    with c1:
                        st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{k1}</span>', unsafe_allow_html=True)
                    with c2:
                        if use_generic:
                            st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {d1:,.0f}</span>', unsafe_allow_html=True)
                            vals[k1] = float(d1)
                        else:
                            vals[k1] = st.number_input(k1, value=float(d1), min_value=0.0, step=step,
                                                       label_visibility="collapsed", key=f"{prefix}_{k1}")
                    if i + 1 < len(pairs):
                        k2, d2 = pairs[i + 1]
                        with c3:
                            st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{k2}</span>', unsafe_allow_html=True)
                        with c4:
                            if use_generic:
                                st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {d2:,.0f}</span>', unsafe_allow_html=True)
                                vals[k2] = float(d2)
                            else:
                                vals[k2] = st.number_input(k2, value=float(d2), min_value=0.0, step=step,
                                                           label_visibility="collapsed", key=f"{prefix}_{k2}")
            return vals

        op_vals  = render_cost_block("✈  OPERATIONAL COSTS  (per flight × annual flights)", "#60A5FA",
                                     CM_DEFAULTS_OPERATIONAL_PER_FLIGHT, "op", use_generic_op, step=50.0)
        op_per_flight = sum(op_vals.values())
        op_annual     = op_per_flight * annual_flights
        st.markdown(f'<div style="padding:0.4rem 0.8rem;background:#112244;border-radius:4px;font-size:0.84rem;margin-bottom:0.5rem">Per flight: <b style="color:#60A5FA">€ {op_per_flight:,.0f}</b> &nbsp;·&nbsp; Annual ({annual_flights} flights): <b style="color:#60A5FA">€ {op_annual:,.0f}</b></div>',
                    unsafe_allow_html=True)

        dir_vals  = render_cost_block("🔧  DIRECT COSTS  (annual)", "#F59E0B",
                                      CM_DEFAULTS_DIRECT, "dir", use_generic_dir, step=500.0)
        dir_total = sum(dir_vals.values())
        st.markdown(f'<div style="padding:0.4rem 0.8rem;background:#112244;border-radius:4px;font-size:0.84rem;margin-bottom:0.5rem">Annual direct costs: <b style="color:#F59E0B">€ {dir_total:,.0f}</b></div>',
                    unsafe_allow_html=True)

        ind_vals  = render_cost_block("👥  INDIRECT / CREW COSTS  (annual)", "#A78BFA",
                                      CM_DEFAULTS_INDIRECT, "ind", use_generic_ind, step=500.0)
        ind_total = sum(ind_vals.values())
        st.markdown(f'<div style="padding:0.4rem 0.8rem;background:#112244;border-radius:4px;font-size:0.84rem;margin-bottom:0.5rem">Annual indirect/crew costs: <b style="color:#A78BFA">€ {ind_total:,.0f}</b></div>',
                    unsafe_allow_html=True)

        # ── GENERATE BUTTON ─────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀  Generate Financial Analysis", use_container_width=True):
            st.session_state["cost_master"] = {
                "op_vals": op_vals, "op_annual": op_annual, "op_per_flight": op_per_flight,
                "dir_vals": dir_vals, "dir_total": dir_total,
                "ind_vals": ind_vals, "ind_total": ind_total,
                "annual_flights": annual_flights,
                "charter_rate": cm_charter_rate,
                "commission_pct": cm_commission,
                "h_charter": h_charter,
                "aircraft_name": aircraft["Modele"],
            }

        # ── FINANCIAL ANALYSIS ──────────────────────────────────────────
        if st.session_state["cost_master"]:
            cm      = st.session_state["cost_master"]
            op_a    = cm["op_annual"]
            dir_a   = cm["dir_total"]
            ind_a   = cm["ind_total"]
            grand   = op_a + dir_a + ind_a
            gross_rev  = cm["charter_rate"] * cm["h_charter"]
            commission = gross_rev * cm["commission_pct"] / 100
            net_rev    = gross_rev - commission
            net_result = net_rev - grand
            coverage   = (net_rev / grand * 100) if grand > 0 else 0

            st.markdown("<hr>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="total-banner">
                <div style="font-size:0.72rem;letter-spacing:0.15em;text-transform:uppercase;color:#8496B0;margin-bottom:0.4rem">
                    {cm['aircraft_name']} — Annual Cost Summary
                </div>
                <div style="font-size:2.4rem;font-weight:800;color:#E8C46A">€ {grand:,.0f}</div>
                <div style="font-size:0.85rem;color:#8496B0;margin-top:0.3rem">
                    Operational: <b style="color:#60A5FA">€ {op_a:,.0f}</b> &nbsp;·&nbsp;
                    Direct: <b style="color:#F59E0B">€ {dir_a:,.0f}</b> &nbsp;·&nbsp;
                    Indirect/Crew: <b style="color:#A78BFA">€ {ind_a:,.0f}</b>
                </div>
            </div>""", unsafe_allow_html=True)

            # KPIs
            k1, k2, k3, k4, k5 = st.columns(5)
            k1.metric("✈ Gross Revenue",  fmt(gross_rev))
            k2.metric("📉 Commission",     fmt(commission))
            k3.metric("💰 Net Revenue",    fmt(net_rev))
            k4.metric("💸 Total Costs",    fmt(grand))
            k5.metric("📊 Net Result",     fmt(net_result), delta=f"{coverage:.1f}% covered")

            st.markdown("<hr>", unsafe_allow_html=True)

            # Global donut + waterfall
            st.markdown('<div class="section-header">Global Cost Breakdown & P&L</div>', unsafe_allow_html=True)
            r1c1, r1c2 = st.columns(2)
            with r1c1:
                st.plotly_chart(cm_global_donut(op_a, dir_a, ind_a),
                                use_container_width=True, config={"displayModeBar": False})
            with r1c2:
                st.plotly_chart(cm_waterfall_global(op_a, dir_a, ind_a, gross_rev, cm["commission_pct"]),
                                use_container_width=True, config={"displayModeBar": False})

            st.markdown("<hr>", unsafe_allow_html=True)

            # Three category donuts
            st.markdown('<div class="section-header">Breakdown by Cost Category</div>', unsafe_allow_html=True)
            OP_COLORS  = ["#60A5FA","#3B82F6","#1D4ED8","#93C5FD","#BFDBFE","#2563EB","#1E40AF","#DBEAFE"]
            DIR_COLORS = ["#F59E0B","#D97706","#B45309","#FCD34D","#FDE68A","#92400E","#FBBF24","#FEF3C7","#78350F"]
            IND_COLORS = ["#A78BFA","#8B5CF6","#7C3AED","#C4B5FD","#DDD6FE","#6D28D9","#5B21B6","#EDE9FE","#4C1D95"]

            d1, d2, d3 = st.columns(3)
            with d1:
                st.markdown('<div style="text-align:center;font-size:0.72rem;color:#60A5FA;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">✈ Operational</div>', unsafe_allow_html=True)
                op_lbl = list(cm["op_vals"].keys())
                op_vls = [v * cm["annual_flights"] for v in cm["op_vals"].values()]
                st.plotly_chart(cm_donut(op_lbl, op_vls, OP_COLORS[:len(op_lbl)], "Operational"),
                                use_container_width=True, config={"displayModeBar": False})
            with d2:
                st.markdown('<div style="text-align:center;font-size:0.72rem;color:#F59E0B;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">🔧 Direct Costs</div>', unsafe_allow_html=True)
                dir_lbl = list(cm["dir_vals"].keys())
                dir_vls = list(cm["dir_vals"].values())
                st.plotly_chart(cm_donut(dir_lbl, dir_vls, DIR_COLORS[:len(dir_lbl)], "Direct"),
                                use_container_width=True, config={"displayModeBar": False})
            with d3:
                st.markdown('<div style="text-align:center;font-size:0.72rem;color:#A78BFA;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.3rem">👥 Indirect / Crew</div>', unsafe_allow_html=True)
                ind_lbl = list(cm["ind_vals"].keys())
                ind_vls = list(cm["ind_vals"].values())
                st.plotly_chart(cm_donut(ind_lbl, ind_vls, IND_COLORS[:len(ind_lbl)], "Crew"),
                                use_container_width=True, config={"displayModeBar": False})

            st.markdown("<hr>", unsafe_allow_html=True)

            # Three bar charts
            st.markdown('<div class="section-header">Detailed Bar Charts</div>', unsafe_allow_html=True)
            b1, b2, b3 = st.columns(3)
            with b1:
                st.plotly_chart(cm_bar_breakdown(list(cm["op_vals"].keys()),
                    [v * cm["annual_flights"] for v in cm["op_vals"].values()], "#60A5FA", "Operational (annual)"),
                    use_container_width=True, config={"displayModeBar": False})
            with b2:
                st.plotly_chart(cm_bar_breakdown(list(cm["dir_vals"].keys()),
                    list(cm["dir_vals"].values()), "#F59E0B", "Direct Costs"),
                    use_container_width=True, config={"displayModeBar": False})
            with b3:
                st.plotly_chart(cm_bar_breakdown(list(cm["ind_vals"].keys()),
                    list(cm["ind_vals"].values()), "#A78BFA", "Indirect / Crew"),
                    use_container_width=True, config={"displayModeBar": False})

            st.markdown("<hr>", unsafe_allow_html=True)

            # Full cost table
            st.markdown('<div class="section-header">Full Cost Table</div>', unsafe_allow_html=True)
            rows = []
            for k, v in cm["op_vals"].items():
                rows.append({"Category": "Operational", "Line Item": k,
                             "Per Unit (€)": v, "Annual (€)": v * cm["annual_flights"],
                             "% of Total": v * cm["annual_flights"] / grand * 100})
            for k, v in cm["dir_vals"].items():
                rows.append({"Category": "Direct", "Line Item": k,
                             "Per Unit (€)": v, "Annual (€)": v, "% of Total": v / grand * 100})
            for k, v in cm["ind_vals"].items():
                rows.append({"Category": "Indirect/Crew", "Line Item": k,
                             "Per Unit (€)": v, "Annual (€)": v, "% of Total": v / grand * 100})

            df_table = pd.DataFrame(rows)
            df_disp  = df_table.copy()
            df_disp["Per Unit (€)"] = df_disp["Per Unit (€)"].apply(lambda x: f"€ {x:,.0f}")
            df_disp["Annual (€)"]   = df_disp["Annual (€)"].apply(lambda x: f"€ {x:,.0f}")
            df_disp["% of Total"]   = df_disp["% of Total"].apply(lambda x: f"{x:.1f}%")
            st.dataframe(df_disp, use_container_width=True, hide_index=True)

            # ── PDF REPORT GENERATION ───────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📄  Generate PDF Report", use_container_width=True, type="primary"):
                with st.spinner("Building your Menkor Aviation cost report..."):
                    try:
                        pdf_bytes = generate_pdf_report(cm, aircraft, cm["annual_flights"])
                        st.session_state["pdf_report"] = pdf_bytes
                        st.success("✓ Report generated!")
                    except Exception as e:
                        st.error(f"⚠ Could not generate PDF report: {e}")
                        st.session_state["pdf_report"] = None

            if st.session_state.get("pdf_report"):
                st.download_button("⬇ Download PDF Report", data=st.session_state["pdf_report"],
                                   file_name=f"Menkor_Cost_Report_{cm['aircraft_name'].replace(' ', '_')}.pdf",
                                   mime="application/pdf", use_container_width=True)

    # ── TAB 5 : QUOTATION ───────────────────────────────────────────────
    with tab5:
        if not is_premium:
            premium_gate()
            st.stop()

        st.markdown('<div class="main-title" style="font-size:1.4rem">✈️ Flight Quotation</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Generate a professional charter quotation with route map & PDF</div>', unsafe_allow_html=True)

        # ── Aircraft & rate selection ────────────────────────────────────
        q1, q2, q3 = st.columns([2, 1, 1])
        with q1:
            df_q = get_active_db()
            aircraft_options = df_q["Modele"].tolist()
            q_aircraft_name = st.selectbox("Aircraft", aircraft_options, key="q_aircraft")
            q_aircraft = df_q[df_q["Modele"] == q_aircraft_name].iloc[0]
            speed_kmh = float(q_aircraft["Vitesse_Croisiere_km_h"]) * 0.9  # -10%
        with q2:
            q_rate = st.number_input("Operator rate (€/h)", min_value=0, max_value=200000,
                                      value=int(q_aircraft.get("Taux_Charter_EUR_h", 5000)), step=100,
                                      key="q_rate")
        with q3:
            q_currency = st.selectbox("Currency", ["EUR", "USD", "GBP", "AED"], key="q_currency")

        # ── Show aircraft specs ─────────────────────────────────────────
        sp1, sp2, sp3, sp4 = st.columns(4)
        sp1.metric("Category",  q_aircraft.get("Categorie", "—"))
        sp2.metric("Cruise Speed", f"{q_aircraft['Vitesse_Croisiere_km_h']} km/h")
        sp3.metric("Max Range",  f"{q_aircraft.get('Autonomie_km', '—'):,.0f} km")
        sp4.metric("Pax Max",   str(q_aircraft.get("Passagers_Max", "—")))

        st.markdown("<hr>", unsafe_allow_html=True)

        # ── Route builder ───────────────────────────────────────────────
        st.markdown('<div class="section-header">✈ Route</div>', unsafe_allow_html=True)

        if "q_legs" not in st.session_state:
            st.session_state["q_legs"] = [
                {"from": "", "to": "", "dep_time": "08:00"},
            ]

        legs = st.session_state["q_legs"]

        for i, leg in enumerate(legs):
            lc1, lc2, lc3, lc4 = st.columns([2.5, 2.5, 1.5, 0.5])
            with lc1:
                legs[i]["from"] = st.text_input(f"From", value=leg["from"],
                                                 placeholder="e.g. Dubai, OMDB",
                                                 key=f"leg_from_{i}")
            with lc2:
                legs[i]["to"] = st.text_input(f"To", value=leg["to"],
                                               placeholder="e.g. London Luton, EGGW",
                                               key=f"leg_to_{i}")
            with lc3:
                legs[i]["dep_time"] = st.text_input("Departure (local)", value=leg["dep_time"],
                                                     placeholder="HH:MM",
                                                     key=f"leg_time_{i}")
            with lc4:
                st.markdown("<br>", unsafe_allow_html=True)
                if i > 0 and st.button("✕", key=f"del_leg_{i}"):
                    legs.pop(i)
                    st.rerun()

        col_add, col_calc = st.columns([1, 2])
        with col_add:
            if st.button("➕ Add a stop", use_container_width=True):
                last_to = legs[-1]["to"] if legs else ""
                legs.append({"from": last_to, "to": "", "dep_time": "12:00"})
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        # ── EXTRAS ──────────────────────────────────────────────────────
        st.markdown('<div class="section-header">➕ Extras & Additional Services</div>', unsafe_allow_html=True)

        ex1, ex2 = st.columns(2)

        with ex1:
            st.markdown('<div style="font-size:0.78rem;color:#60A5FA;font-weight:600;margin-bottom:0.5rem">👤 Crew</div>', unsafe_allow_html=True)
            q_fa_count = st.number_input("Flight Attendant(s)", min_value=0, max_value=6, value=1, step=1, key="q_fa")
            q_fa_rate  = st.number_input("FA daily rate (€)", min_value=0, value=500, step=50, key="q_fa_rate")
            q_fa_days  = st.number_input("Number of days", min_value=1, value=1, step=1, key="q_fa_days")
            q_fa_total = q_fa_count * q_fa_rate * q_fa_days

            st.markdown('<div style="font-size:0.78rem;color:#60A5FA;font-weight:600;margin-top:0.8rem;margin-bottom:0.5rem">🍽️ Catering</div>', unsafe_allow_html=True)
            q_catering_pax  = st.number_input("Number of passengers", min_value=0, value=4, step=1, key="q_cat_pax")
            q_catering_rate = st.number_input("Catering per pax (€)", min_value=0, value=150, step=10, key="q_cat_rate")
            q_catering_total = q_catering_pax * q_catering_rate

        with ex2:
            st.markdown('<div style="font-size:0.78rem;color:#F59E0B;font-weight:600;margin-bottom:0.5rem">⭐ Special Services</div>', unsafe_allow_html=True)
            q_special_1_name  = st.text_input("Service 1", value="Ground Transfer", placeholder="Service name", key="q_sp1_name")
            q_special_1_price = st.number_input("Cost (€)", min_value=0, value=0, step=50, key="q_sp1_price")
            q_special_2_name  = st.text_input("Service 2", value="", placeholder="Service name", key="q_sp2_name")
            q_special_2_price = st.number_input("Cost (€) ", min_value=0, value=0, step=50, key="q_sp2_price")
            q_special_3_name  = st.text_input("Service 3", value="", placeholder="Service name", key="q_sp3_name")
            q_special_3_price = st.number_input("Cost (€)  ", min_value=0, value=0, step=50, key="q_sp3_price")
            q_notes = st.text_area("Special notes / instructions", placeholder="VIP requirements, dietary restrictions, special requests...", height=80, key="q_notes")

        # Build extras list
        q_extras = []
        if q_fa_count > 0 and q_fa_total > 0:
            q_extras.append({"name": f"Flight Attendant x{q_fa_count} ({q_fa_days}d)", "cost": q_fa_total})
        if q_catering_total > 0:
            q_extras.append({"name": f"Catering ({q_catering_pax} pax)", "cost": q_catering_total})
        for sp_name, sp_price in [(q_special_1_name, q_special_1_price),
                                    (q_special_2_name, q_special_2_price),
                                    (q_special_3_name, q_special_3_price)]:
            if sp_name.strip() and sp_price > 0:
                q_extras.append({"name": sp_name.strip(), "cost": sp_price})

        extras_total = sum(e["cost"] for e in q_extras)
        if q_extras:
            st.markdown(f'<div style="padding:0.4rem 0.8rem;background:#112244;border-radius:4px;font-size:0.84rem;margin-top:0.5rem">Extras total: <b style="color:#F59E0B">€ {extras_total:,.0f}</b></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        with col_calc:
            calc_btn = st.button("🧮 Calculate & Generate Quotation",
                                  use_container_width=True, type="primary")

        # ── Geocoding & calculation ─────────────────────────────────────
        def geocode(place: str):
            """Geocode via Nominatim (free, no key needed)."""
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": place, "format": "json", "limit": 1},
                    headers={"User-Agent": "MenkorAviationQuotation/1.0"},
                    timeout=8
                )
                data = r.json()
                if data:
                    return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
                return None, None, None
            except Exception:
                return None, None, None

        def haversine(lat1, lon1, lat2, lon2):
            """Great-circle distance in km."""
            import math
            R = 6371
            dl = math.radians(lat2 - lat1)
            dg = math.radians(lon2 - lon1)
            a = math.sin(dl/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dg/2)**2
            return R * 2 * math.asin(math.sqrt(a))

        def flight_time_str(dist_km, speed_kmh):
            """Returns (total_minutes, formatted string)."""
            cruise_min = (dist_km / speed_kmh) * 60
            total_min  = cruise_min + 10  # +10 min approach
            h = int(total_min // 60)
            m = int(total_min % 60)
            return total_min, f"{h}h {m:02d}m"

        if calc_btn:
            # Geocode all points
            all_legs_data = []
            errors = []

            progress = st.progress(0, text="Geocoding airports...")
            total_steps = sum(2 for l in legs if l["from"] and l["to"])
            step = 0

            for i, leg in enumerate(legs):
                if not leg["from"] or not leg["to"]:
                    errors.append(f"Leg {i+1}: please fill From and To fields.")
                    continue
                lat1, lon1, name1 = geocode(leg["from"])
                step += 1; progress.progress(step / max(total_steps, 1), text=f"Locating {leg['from']}...")
                lat2, lon2, name2 = geocode(leg["to"])
                step += 1; progress.progress(step / max(total_steps, 1), text=f"Locating {leg['to']}...")

                if None in (lat1, lon1, lat2, lon2):
                    errors.append(f"Leg {i+1}: could not locate '{leg['from']}' or '{leg['to']}'.")
                    continue

                dist = haversine(lat1, lon1, lat2, lon2)
                tot_min, ft_str = flight_time_str(dist, speed_kmh)
                cost = (tot_min / 60) * q_rate

                all_legs_data.append({
                    "from_name": leg["from"], "to_name": leg["to"],
                    "dep_time": leg["dep_time"],
                    "lat1": lat1, "lon1": lon1, "full_name1": name1,
                    "lat2": lat2, "lon2": lon2, "full_name2": name2,
                    "dist_km": dist,
                    "flight_time_min": tot_min,
                    "flight_time_str": ft_str,
                    "cost": cost,
                })

            progress.empty()

            if errors:
                for e in errors: st.error(e)
            else:
                flight_total = sum(l["cost"] for l in all_legs_data)
                st.session_state["q_result"] = {
                    "legs": all_legs_data,
                    "aircraft": q_aircraft_name,
                    "rate": q_rate,
                    "currency": q_currency,
                    "speed": speed_kmh,
                    "total_dist": sum(l["dist_km"] for l in all_legs_data),
                    "total_min": sum(l["flight_time_min"] for l in all_legs_data),
                    "total_cost": flight_total + extras_total,
                    "flight_cost": flight_total,
                    "extras": q_extras,
                    "extras_total": extras_total,
                    "notes": q_notes,
                }

        # ── Display results ─────────────────────────────────────────────
        if st.session_state.get("q_result"):
            qr = st.session_state["q_result"]
            legs_data = qr["legs"]

            st.markdown("<hr>", unsafe_allow_html=True)

            # KPIs
            rk1, rk2, rk3, rk4, rk5 = st.columns(5)
            rk1.metric("Total Distance",   f"{qr['total_dist']:,.0f} km")
            rk2.metric("Flight Time",      f"{int(qr['total_min']//60)}h {int(qr['total_min']%60):02d}m")
            rk3.metric("Flight Cost",      f"{qr['currency']} {qr.get('flight_cost', qr['total_cost']):,.0f}")
            rk4.metric("Extras",           f"{qr['currency']} {qr.get('extras_total', 0):,.0f}")
            rk5.metric("💰 Total Quote",   f"{qr['currency']} {qr['total_cost']:,.0f}")

            st.markdown("<hr>", unsafe_allow_html=True)

            # ── ROUTE MAP ───────────────────────────────────────────────
            st.markdown('<div class="section-header">🗺 Route Map</div>', unsafe_allow_html=True)

            # Build Plotly map with great-circle arcs
            import math

            def arc_points(lat1, lon1, lat2, lon2, n=50):
                """Generate n intermediate points along great circle."""
                lats, lons = [lat1], [lon1]
                for i in range(1, n):
                    f = i / n
                    # Linear interpolation (sufficient for display)
                    lats.append(lat1 + (lat2 - lat1) * f)
                    lons.append(lon1 + (lon2 - lon1) * f)
                lats.append(lat2); lons.append(lon2)
                return lats, lons

            fig_map = go.Figure()

            # Draw arcs for each leg
            colors_legs = ["#C9A84C", "#60A5FA", "#4ADE80", "#F87171", "#A78BFA"]
            all_lats = []
            all_lons = []

            for i, leg in enumerate(legs_data):
                arc_lats, arc_lons = arc_points(leg["lat1"], leg["lon1"], leg["lat2"], leg["lon2"])
                color = colors_legs[i % len(colors_legs)]

                # Arc line
                fig_map.add_trace(go.Scattergeo(
                    lat=arc_lats, lon=arc_lons, mode="lines",
                    line=dict(width=2.5, color=color),
                    name=f"Leg {i+1}: {leg['from_name']} → {leg['to_name']}",
                    hoverinfo="skip",
                ))

                # Direction arrow mid-point
                mid = len(arc_lats) // 2
                fig_map.add_trace(go.Scattergeo(
                    lat=[arc_lats[mid]], lon=[arc_lons[mid]],
                    mode="markers",
                    marker=dict(size=8, color=color, symbol="triangle-right"),
                    showlegend=False, hoverinfo="skip",
                ))

                all_lats += [leg["lat1"], leg["lat2"]]
                all_lons += [leg["lon1"], leg["lon2"]]

            # Airport markers
            seen_airports = {}
            for i, leg in enumerate(legs_data):
                for key in [("lat1","lon1","from_name","full_name1"),
                            ("lat2","lon2","to_name","full_name2")]:
                    lat_k, lon_k, name_k, full_k = key
                    akey = (round(leg[lat_k],2), round(leg[lon_k],2))
                    if akey not in seen_airports:
                        seen_airports[akey] = True
                        fig_map.add_trace(go.Scattergeo(
                            lat=[leg[lat_k]], lon=[leg[lon_k]],
                            mode="markers+text",
                            marker=dict(size=12, color="#FFFFFF",
                                        line=dict(width=2, color="#C9A84C")),
                            text=[leg[name_k]],
                            textposition="top center",
                            textfont=dict(size=11, color="#E8C46A", family="Helvetica"),
                            showlegend=False,
                            hovertemplate=f"<b>{leg[name_k]}</b><br>{leg[full_k]}<extra></extra>",
                        ))

            # Map styling
            center_lat = sum(all_lats) / len(all_lats)
            center_lon = sum(all_lons) / len(all_lons)

            fig_map.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=480,
                margin=dict(t=0, b=0, l=0, r=0),
                showlegend=True,
                legend=dict(
                    bgcolor="rgba(17,34,68,0.9)", font=dict(color="#D6E4F7", size=10),
                    bordercolor="#C9A84C", borderwidth=1,
                    x=0.01, y=0.99,
                ),
                geo=dict(
                    projection_type="natural earth",
                    showland=True,      landcolor="#1C2E55",
                    showocean=True,     oceancolor="#0B1629",
                    showcoastlines=True,coastlinecolor="#3A5080",
                    showcountries=True, countrycolor="#2A4070", countrywidth=0.6,
                    showlakes=True,     lakecolor="#0B1629",
                    showrivers=False,
                    showframe=False,
                    bgcolor="rgba(0,0,0,0)",
                    center=dict(lat=center_lat, lon=center_lon),
                    lataxis=dict(
                        range=[min(all_lats)-8, max(all_lats)+8],
                    ),
                    lonaxis=dict(
                        range=[min(all_lons)-12, max(all_lons)+12],
                    ),
                ),
            )

            st.plotly_chart(fig_map, use_container_width=True, config={"displayModeBar": False})

            # ── Leg detail table ────────────────────────────────────────
            st.markdown('<div class="section-header">📋 Leg Details</div>', unsafe_allow_html=True)

            leg_rows = []
            for i, leg in enumerate(legs_data):
                leg_rows.append({
                    "Leg": f"{i+1}",
                    "From": leg["from_name"],
                    "To":   leg["to_name"],
                    "Departure": leg["dep_time"],
                    "Distance": f"{leg['dist_km']:,.0f} km",
                    "Flight Time": leg["flight_time_str"],
                    f"Cost ({qr['currency']})": f"{leg['cost']:,.0f}",
                })
            df_legs = pd.DataFrame(leg_rows)
            st.dataframe(df_legs, use_container_width=True, hide_index=True)

            # Totals
            # Extras table
            if qr.get("extras"):
                st.markdown('<div class="section-header">➕ Extras & Services</div>', unsafe_allow_html=True)
                ext_rows = [{"Service": e["name"], f"Cost ({qr['currency']})": f"{e['cost']:,.0f}"} for e in qr["extras"]]
                st.dataframe(pd.DataFrame(ext_rows), use_container_width=True, hide_index=True)

            if qr.get("notes"):
                st.markdown(f'<div style="background:#13233F;border:1px solid #1A3A6E;border-radius:6px;padding:0.7rem 1rem;font-size:0.84rem;color:#D6E4F7;margin:0.5rem 0"><b>Notes:</b> {qr["notes"]}</div>', unsafe_allow_html=True)

            st.markdown(f"""
            <div class="total-banner" style="margin-top:0.5rem">
                <div style="font-size:0.72rem;letter-spacing:0.15em;text-transform:uppercase;
                     color:#8496B0;margin-bottom:0.3rem">{qr['aircraft']} · {qr['currency']} {qr['rate']:,.0f}/h operator rate</div>
                <div style="font-size:0.82rem;color:#8496B0;margin-bottom:0.3rem">
                    Flight: <b style="color:#60A5FA">{qr['currency']} {qr.get('flight_cost', qr['total_cost']):,.0f}</b>
                    &nbsp;+&nbsp; Extras: <b style="color:#F59E0B">{qr['currency']} {qr.get('extras_total', 0):,.0f}</b>
                </div>
                <div style="font-size:2rem;font-weight:800;color:#E8C46A">
                    {qr['currency']} {qr['total_cost']:,.0f}
                </div>
                <div style="font-size:0.85rem;color:#8496B0;margin-top:0.2rem">
                    {qr['total_dist']:,.0f} km · {int(qr['total_min']//60)}h {int(qr['total_min']%60):02d}m total flight time
                </div>
            </div>""", unsafe_allow_html=True)

            # ── PDF Generation ──────────────────────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📄 Generate PDF Quotation", use_container_width=True, type="primary"):
                with st.spinner("Building your Menkor Aviation quotation..."):
                    try:
                        pdf_bytes = generate_quotation_pdf(qr, q_aircraft)
                        st.session_state["q_pdf"] = pdf_bytes
                        st.success("✓ Quotation ready!")
                    except Exception as e:
                        st.error(f"⚠ PDF error: {e}")
                        st.session_state["q_pdf"] = None

            if st.session_state.get("q_pdf"):
                fname = f"Menkor_Quotation_{qr['aircraft'].replace(' ','_')}.pdf"
                st.download_button("⬇ Download Quotation PDF", data=st.session_state["q_pdf"],
                                   file_name=fname, mime="application/pdf",
                                   use_container_width=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:0.72rem;color:#4A5568;letter-spacing:0.1em">AVIATION COST ESTIMATOR — Figures are indicative and for simulation purposes only · Values based on market averages (NBAA / JETNET)</div>', unsafe_allow_html=True)


if __name__ == "__main__":
    main()
