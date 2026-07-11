"""
✈️ Aviation Cost Estimator — Menkor Aviation GBL
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import base64
import hashlib
import re as _re
import warnings
warnings.filterwarnings("ignore")

# ─── PAGE CONFIG & CSS ───────────────────────────────────────────────────────
st.set_page_config(page_title="Aviation Cost Estimator", page_icon="✈",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
:root{--navy:#0B1629;--deep:#112244;--mid:#1A3A6E;--gold:#C9A84C;--amber:#E8C46A;
      --slate:#8496B0;--light:#D6E4F7;--card:#13233F;}
.stApp{background-color:var(--navy)!important;color:var(--light)!important;
       font-family:'Segoe UI',system-ui,sans-serif;}
[data-testid="stSidebar"]{background-color:var(--deep)!important;border-right:1px solid var(--mid);}
[data-testid="stSidebar"] *{color:var(--light)!important;}
.main-title{font-size:2rem;font-weight:700;letter-spacing:.08em;color:var(--amber);text-transform:uppercase;}
.sub-title{font-size:.85rem;color:var(--slate);letter-spacing:.12em;text-transform:uppercase;margin-bottom:1.5rem;}
.metric-card{background:var(--card);border:1px solid var(--mid);border-left:3px solid var(--gold);border-radius:6px;padding:1rem 1.2rem;margin-bottom:.8rem;}
.metric-label{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--slate);margin-bottom:.3rem;}
.metric-value{font-size:1.7rem;font-weight:700;color:var(--amber);}
.metric-sub{font-size:.78rem;color:var(--slate);margin-top:.1rem;}
.section-header{font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);
                border-bottom:1px solid var(--mid);padding-bottom:.4rem;margin:1.2rem 0 .8rem 0;}
hr{border-color:var(--mid)!important;}
[data-testid="stMetricValue"]{color:var(--amber)!important;font-size:1.5rem!important;}
[data-testid="stMetricLabel"]{color:var(--slate)!important;font-size:.72rem!important;}
[data-testid="stMetricDelta"]{color:#4ADE80!important;}
.stButton>button{background:var(--mid)!important;color:var(--amber)!important;border:1px solid var(--gold)!important;border-radius:4px;font-weight:600;}
.stButton>button:hover{background:var(--gold)!important;color:var(--navy)!important;}
[data-baseweb="tab-list"]{background:var(--card);border-radius:6px;}
[data-baseweb="tab"]{color:var(--slate)!important;}
[aria-selected="true"]{color:var(--amber)!important;border-bottom-color:var(--gold)!important;}
[data-testid="stExpander"]{background:var(--card);border:1px solid var(--mid);border-radius:6px;}
.tag-ok{background:#163A2A;color:#4ADE80;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-warn{background:#3A2A10;color:#FBBF24;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-err{background:#3A1010;color:#F87171;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.total-banner{background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);border:1px solid var(--gold);border-radius:8px;padding:1.5rem;text-align:center;margin:1.5rem 0;}
</style>""", unsafe_allow_html=True)

# ─── LOGO ────────────────────────────────────────────────────────────────────
def _get_logo():
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/gregorydebeure/aviation-cost-estimato/main/menkor_logo.png"
        with urllib.request.urlopen(url, timeout=4) as r:
            return base64.b64encode(r.read()).decode()
    except Exception:
        return ""

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
        {"Modele":"Boeing 737-700","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":225028,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":4669,"Cout_Horaire_Prive":3829,"Heures_Base":100,"Taux_Charter_EUR_h":8000,"Vitesse_Croisiere_km_h":838,"Autonomie_km":7226,"Passagers_Max":140},
        {"Modele":"Boeing 747-400","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":276703,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":15263,"Cout_Horaire_Prive":12516,"Heures_Base":100,"Taux_Charter_EUR_h":65000,"Vitesse_Croisiere_km_h":913,"Autonomie_km":14626,"Passagers_Max":420},
        {"Modele":"Boeing BBJ","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":218956,"Couts_Equipe_Annuels":469635,"Cout_Horaire_Charter":3763,"Cout_Horaire_Prive":3086,"Heures_Base":350,"Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":871,"Autonomie_km":11100,"Passagers_Max":19},
        {"Modele":"Bombardier Challenger 604","Categorie":"Large Jet","Couts_Fixes_Annuels":376651,"Couts_Equipe_Annuels":237726,"Cout_Horaire_Charter":2726,"Cout_Horaire_Prive":2450,"Heures_Base":350,"Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6786,"Passagers_Max":10},
        {"Modele":"Bombardier Global 5000","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":702952,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4051,"Cout_Horaire_Prive":3646,"Heures_Base":350,"Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9390,"Passagers_Max":13},
        {"Modele":"Challenger 350","Categorie":"Super Midsize Jet","Couts_Fixes_Annuels":93921,"Couts_Equipe_Annuels":394305,"Cout_Horaire_Charter":2353,"Cout_Horaire_Prive":1929,"Heures_Base":350,"Taux_Charter_EUR_h":4000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5784,"Passagers_Max":8},
        {"Modele":"Dassault Falcon 7X","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":588918,"Couts_Equipe_Annuels":377505,"Cout_Horaire_Charter":2994,"Cout_Horaire_Prive":2695,"Heures_Base":350,"Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9924,"Passagers_Max":12},
        {"Modele":"Dassault Falcon 8X","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":598153,"Couts_Equipe_Annuels":377505,"Cout_Horaire_Charter":2958,"Cout_Horaire_Prive":2662,"Heures_Base":350,"Taux_Charter_EUR_h":10500,"Vitesse_Croisiere_km_h":903,"Autonomie_km":11365,"Passagers_Max":12},
        {"Modele":"Beechcraft Beechjet 400A","Categorie":"Light Jet","Couts_Fixes_Annuels":36260,"Couts_Equipe_Annuels":245619,"Cout_Horaire_Charter":1568,"Cout_Horaire_Prive":1286,"Heures_Base":250,"Taux_Charter_EUR_h":2300,"Vitesse_Croisiere_km_h":832,"Autonomie_km":2133,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier I","Categorie":"Light Jet","Couts_Fixes_Annuels":35998,"Couts_Equipe_Annuels":136880,"Cout_Horaire_Charter":1254,"Cout_Horaire_Prive":1028,"Heures_Base":250,"Taux_Charter_EUR_h":1800,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier IA","Categorie":"Light Jet","Couts_Fixes_Annuels":41947,"Couts_Equipe_Annuels":136880,"Cout_Horaire_Charter":1236,"Cout_Horaire_Prive":1013,"Heures_Base":250,"Taux_Charter_EUR_h":1900,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Boeing 737-500","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":242553,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":5456,"Cout_Horaire_Prive":4474,"Heures_Base":100,"Taux_Charter_EUR_h":7500,"Vitesse_Croisiere_km_h":839,"Autonomie_km":5424,"Passagers_Max":150},
        {"Modele":"Boeing 737-600","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":231007,"Couts_Equipe_Annuels":419143,"Cout_Horaire_Charter":4544,"Cout_Horaire_Prive":3726,"Heures_Base":100,"Taux_Charter_EUR_h":7800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":7073,"Passagers_Max":119},
        {"Modele":"Boeing 747-100","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":273066,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":19415,"Cout_Horaire_Prive":15920,"Heures_Base":100,"Taux_Charter_EUR_h":55000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":11195,"Passagers_Max":400},
        {"Modele":"Boeing 747-200","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":289890,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":18520,"Cout_Horaire_Prive":15186,"Heures_Base":100,"Taux_Charter_EUR_h":58000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":12640,"Passagers_Max":350},
        {"Modele":"Boeing 747SP","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":239780,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":15953,"Cout_Horaire_Prive":13081,"Heures_Base":100,"Taux_Charter_EUR_h":60000,"Vitesse_Croisiere_km_h":902,"Autonomie_km":13723,"Passagers_Max":331},
        {"Modele":"Boeing 757-200ER","Categorie":"VIP Airliner / BBJ","Couts_Fixes_Annuels":274945,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":5939,"Cout_Horaire_Prive":4870,"Heures_Base":100,"Taux_Charter_EUR_h":12000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":11159,"Passagers_Max":200},
        {"Modele":"Boeing 767-200ER","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":384835,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":6537,"Cout_Horaire_Prive":5360,"Heures_Base":100,"Taux_Charter_EUR_h":15000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":13145,"Passagers_Max":181},
        {"Modele":"Boeing 767-300ER","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":380439,"Couts_Equipe_Annuels":471643,"Cout_Horaire_Charter":8352,"Cout_Horaire_Prive":6849,"Heures_Base":100,"Taux_Charter_EUR_h":18000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":12474,"Passagers_Max":218},
        {"Modele":"Boeing 787-8","Categorie":"VIP Wide-Body","Couts_Fixes_Annuels":358241,"Couts_Equipe_Annuels":521978,"Cout_Horaire_Charter":7925,"Cout_Horaire_Prive":6498,"Heures_Base":100,"Taux_Charter_EUR_h":20000,"Vitesse_Croisiere_km_h":930,"Autonomie_km":14538,"Passagers_Max":381},
        {"Modele":"Boeing BBJ2","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":241598,"Couts_Equipe_Annuels":469653,"Cout_Horaire_Charter":3882,"Cout_Horaire_Prive":3183,"Heures_Base":350,"Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":10191,"Passagers_Max":19},
        {"Modele":"Boeing BBJ3","Categorie":"ACJ / VIP Airliner","Couts_Fixes_Annuels":248567,"Couts_Equipe_Annuels":470089,"Cout_Horaire_Charter":3889,"Cout_Horaire_Prive":3189,"Heures_Base":350,"Taux_Charter_EUR_h":11000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":8649,"Passagers_Max":19},
        {"Modele":"Bombardier Challenger 605","Categorie":"Large Jet","Couts_Fixes_Annuels":500361,"Couts_Equipe_Annuels":346500,"Cout_Horaire_Charter":2619,"Cout_Horaire_Prive":2360,"Heures_Base":350,"Taux_Charter_EUR_h":5500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":6856,"Passagers_Max":10},
        {"Modele":"Bombardier Challenger 650","Categorie":"Large Jet","Couts_Fixes_Annuels":488946,"Couts_Equipe_Annuels":333270,"Cout_Horaire_Charter":2455,"Cout_Horaire_Prive":2210,"Heures_Base":350,"Taux_Charter_EUR_h":5800,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6795,"Passagers_Max":10},
        {"Modele":"Bombardier Global Express","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":683427,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4471,"Cout_Horaire_Prive":4024,"Heures_Base":350,"Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10726,"Passagers_Max":13},
        {"Modele":"Bombardier Global Express XRS","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":714023,"Couts_Equipe_Annuels":426052,"Cout_Horaire_Charter":4420,"Cout_Horaire_Prive":3978,"Heures_Base":350,"Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10934,"Passagers_Max":13},
        {"Modele":"Challenger 300","Categorie":"Super Midsize Jet","Couts_Fixes_Annuels":102295,"Couts_Equipe_Annuels":392114,"Cout_Horaire_Charter":2878,"Cout_Horaire_Prive":2360,"Heures_Base":350,"Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":848,"Autonomie_km":5545,"Passagers_Max":8},
        {"Modele":"Challenger 600","Categorie":"Large Jet","Couts_Fixes_Annuels":78406,"Couts_Equipe_Annuels":372774,"Cout_Horaire_Charter":4337,"Cout_Horaire_Prive":3556,"Heures_Base":350,"Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":5061,"Passagers_Max":9},
        {"Modele":"Challenger 601-1A","Categorie":"Large Jet","Couts_Fixes_Annuels":84681,"Couts_Equipe_Annuels":367240,"Cout_Horaire_Charter":3720,"Cout_Horaire_Prive":3050,"Heures_Base":350,"Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":821,"Autonomie_km":5748,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 10","Categorie":"Light Jet","Couts_Fixes_Annuels":279536,"Couts_Equipe_Annuels":224844,"Cout_Horaire_Charter":2372,"Cout_Horaire_Prive":2135,"Heures_Base":250,"Taux_Charter_EUR_h":2800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":2745,"Passagers_Max":6},
        {"Modele":"Dassault Falcon 20C","Categorie":"Midsize Jet","Couts_Fixes_Annuels":350751,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":3179,"Cout_Horaire_Prive":2861,"Heures_Base":250,"Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2167,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20C-5","Categorie":"Midsize Jet","Couts_Fixes_Annuels":356747,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2675,"Cout_Horaire_Prive":2408,"Heures_Base":250,"Taux_Charter_EUR_h":3400,"Vitesse_Croisiere_km_h":842,"Autonomie_km":3684,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F","Categorie":"Midsize Jet","Couts_Fixes_Annuels":356077,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2895,"Cout_Horaire_Prive":2606,"Heures_Base":250,"Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2420,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F-5","Categorie":"Midsize Jet","Couts_Fixes_Annuels":353308,"Couts_Equipe_Annuels":278094,"Cout_Horaire_Charter":2485,"Cout_Horaire_Prive":2237,"Heures_Base":250,"Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":842,"Autonomie_km":4063,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50","Categorie":"Large Jet","Couts_Fixes_Annuels":450596,"Couts_Equipe_Annuels":334924,"Cout_Horaire_Charter":3352,"Cout_Horaire_Prive":3017,"Heures_Base":350,"Taux_Charter_EUR_h":5000,"Vitesse_Croisiere_km_h":799,"Autonomie_km":5526,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50-40","Categorie":"Large Jet","Couts_Fixes_Annuels":469453,"Couts_Equipe_Annuels":334924,"Cout_Horaire_Charter":3328,"Cout_Horaire_Prive":2995,"Heures_Base":350,"Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5905,"Passagers_Max":9},
    ]
    return pd.DataFrame(data)

def get_active_db():
    return st.session_state.get("database") or get_default_data()

def fmt(v, d=0):
    return f"€ {v:,.{d}f}"

def calculate_costs(ac, hc, hp):
    fc=ac["Couts_Fixes_Annuels"]; cc=ac["Couts_Equipe_Annuels"]
    ch=ac["Cout_Horaire_Charter"]; ph=ac["Cout_Horaire_Prive"]
    tariff=float(ac.get("Taux_Charter_EUR_h",0))
    th=hc+hp; vc=hc*ch; vp=hp*ph; tv=vc+vp; tf=fc+cc; gt=tf+tv
    return dict(fixed_costs=fc,crew_costs=cc,total_fixed=tf,var_charter=vc,var_private=vp,
                total_variable=tv,grand_total=gt,avg_cost_h=gt/th if th>0 else 0,
                h_charter=hc,h_private=hp,total_hours=th,charter_tariff=tariff)

def calculate_profitability(costs, comm_pct, custom_rate=None):
    t=custom_rate if (custom_rate and custom_rate>0) else costs["charter_tariff"]
    gr=t*costs["h_charter"]; comm=gr*comm_pct/100; nr=gr-comm
    net=nr-costs["grand_total"]; cov=(nr/costs["grand_total"]*100) if costs["grand_total"]>0 else 0
    return dict(gross_revenue=gr,commission=comm,net_revenue=nr,net_result=net,coverage_rate=cov,effective_rate=t)

# ─── CHARTS ──────────────────────────────────────────────────────────────────
C={"fixed":"#1A3A6E","crew":"#C9A84C","charter":"#4A90D9","private":"#8496B0","profit":"#4ADE80","loss":"#F87171"}
BG=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#D6E4F7"))

def chart_donut(costs):
    fig=go.Figure(go.Pie(
        labels=["Fixed","Crew","Charter Var","Private Var"],
        values=[costs["fixed_costs"],costs["crew_costs"],costs["var_charter"],costs["var_private"]],
        hole=0.56,marker=dict(colors=[C["fixed"],C["crew"],C["charter"],C["private"]],line=dict(color="#0B1629",width=2)),
        textinfo="label+percent",textfont=dict(size=11,color="#D6E4F7")))
    fig.add_annotation(text=f"<b>{costs['grand_total']/1e6:.2f}M€</b>",x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"))
    fig.update_layout(**BG,height=320,margin=dict(t=10,b=10,l=10,r=10),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.2,bgcolor="rgba(0,0,0,0)"))
    return fig

def chart_bars(costs):
    th=max(costs["total_hours"],1)
    fig=go.Figure(data=[
        go.Bar(name="Fixed",x=["Charter","Private","Total"],marker_color=C["fixed"],
               y=[costs["total_fixed"]*(costs["h_charter"]/th),costs["total_fixed"]*(costs["h_private"]/th),costs["total_fixed"]]),
        go.Bar(name="Charter Var",x=["Charter","Private","Total"],marker_color=C["charter"],y=[costs["var_charter"],0,costs["var_charter"]]),
        go.Bar(name="Private Var",x=["Charter","Private","Total"],marker_color=C["private"],y=[0,costs["var_private"],costs["var_private"]]),
    ])
    fig.update_layout(barmode="stack",**BG,height=300,margin=dict(t=10,b=40,l=10,r=10),
                      yaxis=dict(title="Cost (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.35,bgcolor="rgba(0,0,0,0)"))
    return fig

def chart_waterfall(costs,prof):
    fig=go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","total"],
        x=["Revenue","Commission","Variable","Fixed","Net"],
        y=[prof["gross_revenue"],-prof["commission"],-costs["total_variable"],-costs["total_fixed"],prof["net_result"]],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=C["profit"]),decreasing=dict(marker_color=C["loss"]),
        totals=dict(marker_color=C["profit"] if prof["net_result"]>=0 else C["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11)))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(**BG,height=340,margin=dict(t=10,b=10,l=10,r=10),
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def chart_sensitivity(ac,hp,comm_pct,rate=None):
    hrs=list(range(0,801,25))
    res=[calculate_profitability(calculate_costs(ac,h,hp),comm_pct,rate)["net_result"] for h in hrs]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=hrs,y=res,mode="lines",line=dict(color=C["charter"],width=2.5),
                             fill="tozeroy",fillcolor="rgba(74,144,217,0.12)"))
    fig.add_hline(y=0,line_dash="dash",line_color="#C9A84C",line_width=1.5)
    for i in range(1,len(res)):
        if res[i-1]<0<=res[i]:
            fig.add_vline(x=hrs[i],line_dash="dot",line_color="#E8C46A",line_width=1.5,
                         annotation_text=f"Break-even ~{hrs[i]}h",annotation_font_color="#E8C46A")
            break
    fig.update_layout(**BG,height=300,margin=dict(t=10,b=10,l=10,r=10),showlegend=False,
                      yaxis=dict(title="Net Result (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Charter Hours",gridcolor="#1A3A6E"))
    return fig

def cm_global_donut(op,direct,indirect):
    total=op+direct+indirect
    fig=go.Figure(go.Pie(labels=["Operational","Direct","Crew/Indirect"],values=[op,direct,indirect],hole=0.56,
        marker=dict(colors=["#60A5FA","#F59E0B","#A78BFA"],line=dict(color="#0B1629",width=2)),
        textinfo="label+percent",textfont=dict(size=11,color="#D6E4F7")))
    fig.add_annotation(text=f"<b>{total/1e6:.2f}M€</b>",x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"))
    fig.update_layout(**BG,height=360,margin=dict(t=10,b=10,l=10,r=10),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.15,bgcolor="rgba(0,0,0,0)"))
    return fig

def cm_waterfall(op,direct,indirect,rev,comm_pct):
    comm=rev*comm_pct/100; nr=rev-comm; gt=op+direct+indirect; net=nr-gt
    fig=go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","relative","total"],
        x=["Revenue","Commission","Operational","Direct","Crew","Net"],
        y=[rev,-comm,-op,-direct,-indirect,net],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=C["profit"]),decreasing=dict(marker_color=C["loss"]),
        totals=dict(marker_color=C["profit"] if net>=0 else C["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11)))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(**BG,height=360,margin=dict(t=10,b=10,l=10,r=10),
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def cm_donut(labels,values,colors,title):
    total=sum(v for v in values if v>0)
    fig=go.Figure(go.Pie(labels=labels,values=values,hole=0.54,
        marker=dict(colors=colors,line=dict(color="#0B1629",width=2)),
        textinfo="label+percent",textfont=dict(size=10,color="#D6E4F7")))
    fig.add_annotation(text=f"<b>{total/1000:.0f}K€</b>",x=0.5,y=0.5,showarrow=False,font=dict(size=14,color="#E8C46A"))
    fig.update_layout(**BG,height=300,margin=dict(t=10,b=10,l=5,r=5),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.3,bgcolor="rgba(0,0,0,0)",font=dict(size=9)))
    return fig

def cm_bar(cats,vals,color,title):
    paired=sorted(zip(vals,cats),reverse=True)
    vs,cs=zip(*paired) if paired else ([],[])
    fig=go.Figure(go.Bar(x=list(cs),y=list(vs),marker_color=color,
        text=[f"€{v:,.0f}" for v in vs],textposition="outside",textfont=dict(size=9,color="#D6E4F7")))
    fig.update_layout(**BG,height=300,margin=dict(t=30,b=60,l=10,r=10),
                      title=dict(text=title,font=dict(size=11,color="#8496B0"),x=0),
                      yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f",title="€"),
                      xaxis=dict(tickangle=-30,gridcolor="rgba(0,0,0,0)"))
    return fig

CM_OP = {"Handling":800,"Ground Service":600,"Catering":400,"Hotel":1200,
          "ATC Charges":900,"Flight Planning":250,"Permission":350,"Miscellaneous":300}
CM_DIR = {"Maintenance":85000,"Maintenance Programs":42000,"Insurance":38000,"Hangar":30000,
           "Management Fee (VAT)":55000,"Government Costs":12000,"Cleaning":8000,
           "Flight Planning Tools":6000,"Nav Programme":9500}
CM_IND = {"Crew Salaries":180000,"Total Social Costs":54000,"Training Cockpit":18000,
           "Training Cabin":8000,"Expense Training Crew":5000,"Communication Crew":4500,
           "Crew Expenses":22000,"Freelancer":15000,"Miscellaneous Crew":6000}

# ─── PDF (lazy imports) ──────────────────────────────────────────────────────
def generate_pdf_report(cm, aircraft_row, annual_flights):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader
    from datetime import date
    NAVY=HexColor("#112244"); GOLD=HexColor("#C9A84C"); SLATE=HexColor("#5A6B85")
    LIGHT=HexColor("#F4F6FA"); GREEN=HexColor("#16A34A"); RED=HexColor("#DC2626")
    buf=BytesIO()
    page_w,page_h=A4
    logo_b64=_get_logo()
    logo_data=base64.b64decode(logo_b64) if logo_b64 else None
    def hf(canvas,doc):
        canvas.saveState()
        if logo_data:
            canvas.drawImage(ImageReader(BytesIO(logo_data)),18*mm,page_h-22*mm,width=38*mm,height=14*mm,preserveAspectRatio=True,mask="auto")
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(0.8)
        canvas.line(18*mm,page_h-23*mm,page_w-18*mm,page_h-23*mm)
        canvas.line(18*mm,14*mm,page_w-18*mm,14*mm)
        canvas.setFont("Helvetica",7); canvas.setFillColor(SLATE)
        canvas.drawCentredString(page_w/2,9*mm,"Menkor Aviation GBL — Confidential")
        canvas.drawRightString(page_w-18*mm,9*mm,f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    doc=SimpleDocTemplate(buf,pagesize=A4,topMargin=28*mm,bottomMargin=22*mm,leftMargin=18*mm,rightMargin=18*mm)
    styles=getSampleStyleSheet()
    sT=ParagraphStyle("T",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=24,textColor=NAVY,alignment=TA_CENTER,spaceAfter=4)
    sS=ParagraphStyle("S",parent=styles["Normal"],fontName="Helvetica",fontSize=11,textColor=SLATE,alignment=TA_CENTER,spaceAfter=2)
    sH=ParagraphStyle("H",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=12,textColor=NAVY,spaceBefore=10,spaceAfter=6)
    sSm=ParagraphStyle("Sm",parent=styles["Normal"],fontName="Helvetica",fontSize=8,textColor=SLATE)
    story=[]
    story.append(Spacer(1,25*mm))
    story.append(Paragraph("AVIATION COST MASTER REPORT",sT))
    story.append(Paragraph(aircraft_row["Modele"],ParagraphStyle("AC",parent=styles["Normal"],fontName="Helvetica-Bold",fontSize=16,textColor=GOLD,alignment=TA_CENTER,spaceBefore=6,spaceAfter=4)))
    story.append(Paragraph(str(aircraft_row.get("Categorie","")),sS))
    story.append(Spacer(1,10*mm))
    story.append(HRFlowable(width="100%",thickness=1,color=GOLD,spaceAfter=6))
    story.append(Paragraph(f"Report generated on {date.today().strftime('%d %B %Y')}",sS))
    story.append(PageBreak())
    op_a=cm["op_annual"]; dir_a=cm["dir_total"]; ind_a=cm["ind_total"]
    grand=op_a+dir_a+ind_a
    gross=cm["charter_rate"]*cm["h_charter"]; comm=gross*cm["commission_pct"]/100
    nr=gross-comm; net=nr-grand; cov=(nr/grand*100) if grand>0 else 0
    story.append(Paragraph("Executive Summary",sH))
    tdata=[["Total Annual Cost",f"€ {grand:,.0f}"],["  · Operational",f"€ {op_a:,.0f}"],
           ["  · Direct",f"€ {dir_a:,.0f}"],["  · Crew/Indirect",f"€ {ind_a:,.0f}"],
           ["Gross Revenue",f"€ {gross:,.0f}"],["Net Revenue",f"€ {nr:,.0f}"],
           ["Net Result",f"€ {net:,.0f}"],["Coverage",f"{cov:.1f}%"]]
    t=Table(tdata,colWidths=[100*mm,60*mm])
    t.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-1),"Helvetica"),("FONTSIZE",(0,0),(-1,-1),9.5),
        ("ALIGN",(1,0),(1,-1),"RIGHT"),("BACKGROUND",(0,0),(-1,0),LIGHT),
        ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
        ("GRID",(0,0),(-1,-1),0.3,HexColor("#DDDDDD"))]))
    story.append(t)
    doc.build(story,onFirstPage=hf,onLaterPages=hf)
    buf.seek(0); return buf.getvalue()

def generate_quotation_pdf(qr, aircraft_row):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, PageBreak, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader
    from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect
    from datetime import date
    import math
    NAVY=HexColor("#112244"); GOLD=HexColor("#C9A84C"); SLATE=HexColor("#5A6B85"); LIGHT=HexColor("#F4F6FA")
    buf=BytesIO(); page_w,page_h=A4
    logo_b64=_get_logo(); logo_data=base64.b64decode(logo_b64) if logo_b64 else None
    def hf(canvas,doc):
        canvas.saveState()
        if logo_data:
            canvas.drawImage(ImageReader(BytesIO(logo_data)),18*mm,page_h-22*mm,width=38*mm,height=14*mm,preserveAspectRatio=True,mask="auto")
        canvas.setStrokeColor(GOLD); canvas.setLineWidth(0.8)
        canvas.line(18*mm,page_h-23*mm,page_w-18*mm,page_h-23*mm)
        canvas.line(18*mm,14*mm,page_w-18*mm,14*mm)
        canvas.setFont("Helvetica",7); canvas.setFillColor(SLATE)
        canvas.drawCentredString(page_w/2,9*mm,"Menkor Aviation GBL — Charter Quotation")
        canvas.drawRightString(page_w-18*mm,9*mm,f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    doc=SimpleDocTemplate(buf,pagesize=A4,topMargin=28*mm,bottomMargin=22*mm,leftMargin=18*mm,rightMargin=18*mm)
    styles=getSampleStyleSheet()
    sT=ParagraphStyle("T",parent=styles["Title"],fontName="Helvetica-Bold",fontSize=22,textColor=NAVY,alignment=TA_CENTER)
    sS=ParagraphStyle("S",parent=styles["Normal"],fontName="Helvetica",fontSize=10,textColor=SLATE,alignment=TA_CENTER,spaceAfter=2)
    sH=ParagraphStyle("H",parent=styles["Heading2"],fontName="Helvetica-Bold",fontSize=12,textColor=NAVY,spaceBefore=10,spaceAfter=6)
    sSm=ParagraphStyle("Sm",parent=styles["Normal"],fontName="Helvetica",fontSize=7.5,textColor=SLATE)
    story=[]
    story.append(Spacer(1,20*mm))
    story.append(Paragraph("CHARTER FLIGHT QUOTATION",sT))
    story.append(Paragraph(qr["aircraft"],ParagraphStyle("AC",parent=styles["Normal"],fontName="Helvetica-Bold",fontSize=15,textColor=GOLD,alignment=TA_CENTER,spaceBefore=4,spaceAfter=2)))
    story.append(Paragraph(str(aircraft_row.get("Categorie","")),sS))
    story.append(Spacer(1,6*mm))
    # Map
    try:
        all_lats=[l["lat1"] for l in qr["legs"]]+[l["lat2"] for l in qr["legs"]]
        all_lons=[l["lon1"] for l in qr["legs"]]+[l["lon2"] for l in qr["legs"]]
        lat_min,lat_max=min(all_lats),max(all_lats); lon_min,lon_max=min(all_lons),max(all_lons)
        pad_la=max((lat_max-lat_min)*0.35,5); pad_lo=max((lon_max-lon_min)*0.35,8)
        lat_min-=pad_la; lat_max+=pad_la; lon_min-=pad_lo; lon_max+=pad_lo
        mw=160*mm; mh=80*mm
        def xy(lat,lon): return ((lon-lon_min)/(lon_max-lon_min)*mw,(lat-lat_min)/(lat_max-lat_min)*mh)
        d=Drawing(mw,mh)
        d.add(Rect(0,0,mw,mh,fillColor=HexColor("#0B1629"),strokeColor=GOLD,strokeWidth=1.5))
        clrs=["#C9A84C","#60A5FA","#4ADE80","#F87171","#A78BFA"]
        for i,leg in enumerate(qr["legs"]):
            clr=HexColor(clrs[i%len(clrs)]); n=40
            pts=[xy(leg["lat1"]+(leg["lat2"]-leg["lat1"])*s/n,leg["lon1"]+(leg["lon2"]-leg["lon1"])*s/n) for s in range(n+1)]
            for s in range(len(pts)-1):
                d.add(Line(pts[s][0],pts[s][1],pts[s+1][0],pts[s+1][1],strokeColor=clr,strokeWidth=2))
        seen={}
        for leg in qr["legs"]:
            for lk,lok,nk in [("lat1","lon1","from_name"),("lat2","lon2","to_name")]:
                k=(round(leg[lk],1),round(leg[lok],1))
                if k not in seen:
                    seen[k]=True; x,y=xy(leg[lk],leg[lok])
                    d.add(Circle(x,y,4,fillColor=HexColor("#FFFFFF"),strokeColor=GOLD,strokeWidth=1.5))
                    d.add(String(x+6,y-3,leg[nk][:15],fontSize=6,fillColor=HexColor("#E8C46A"),fontName="Helvetica-Bold"))
        story.append(d); story.append(Spacer(1,4*mm))
    except Exception:
        pass
    story.append(HRFlowable(width="100%",thickness=1,color=GOLD,spaceAfter=6))
    story.append(Paragraph(f"Date: {date.today().strftime('%d %B %Y')}",sS))
    story.append(PageBreak())
    story.append(Paragraph("Flight Itinerary",sH))
    hdr=["#","From","To","Dep.","Distance","Flight Time",f"Cost ({qr['currency']})"]
    rows=[hdr]
    for i,leg in enumerate(qr["legs"]):
        rows.append([str(i+1),leg["from_name"][:18],leg["to_name"][:18],leg["dep_time"],
                     f"{leg['dist_km']:,.0f} km",leg["flight_time_str"],f"{qr['currency']} {leg['cost']:,.0f}"])
    rows.append(["","","","",f"{qr['total_dist']:,.0f} km",
                 f"{int(qr['total_min']//60)}h{int(qr['total_min']%60):02d}m",
                 f"TOTAL: {qr['currency']} {qr['total_cost']:,.0f}"])
    tbl=Table(rows,colWidths=[8*mm,35*mm,35*mm,14*mm,22*mm,20*mm,30*mm],repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),8),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),
        ("BACKGROUND",(0,0),(-1,0),NAVY),("ALIGN",(4,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[HexColor("#FFFFFF"),LIGHT]),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("LINEABOVE",(0,-1),(-1,-1),1,GOLD),
        ("GRID",(0,0),(-1,-1),0.3,HexColor("#DDDDDD")),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(tbl)
    if qr.get("extras"):
        story.append(Spacer(1,6*mm)); story.append(Paragraph("Extras & Services",sH))
        erows=[["Service",f"Cost ({qr['currency']})"]]
        for e in qr["extras"]: erows.append([e["name"],f"{qr['currency']} {e['cost']:,.0f}"])
        erows.append(["TOTAL EXTRAS",f"{qr['currency']} {qr.get('extras_total',0):,.0f}"])
        et=Table(erows,colWidths=[120*mm,44*mm])
        et.setStyle(TableStyle([("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,1),(-1,-2),"Helvetica"),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
            ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),("GRID",(0,0),(-1,-1),0.3,HexColor("#DDDDDD")),
            ("LINEABOVE",(0,-1),(-1,-1),1,GOLD),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story.append(et)
    story.append(Spacer(1,6*mm))
    total_data=[["Flight Cost",f"{qr['currency']} {qr.get('flight_cost',qr['total_cost']):,.0f}"],
                ["Extras",f"{qr['currency']} {qr.get('extras_total',0):,.0f}"],
                ["TOTAL QUOTATION",f"{qr['currency']} {qr['total_cost']:,.0f}"]]
    tt=Table(total_data,colWidths=[120*mm,44*mm])
    tt.setStyle(TableStyle([("FONTNAME",(0,0),(-1,-2),"Helvetica"),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,-1),(-1,-1),12),("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BACKGROUND",(0,-1),(-1,-1),NAVY),("TEXTCOLOR",(0,-1),(-1,-1),GOLD),
        ("LINEABOVE",(0,-1),(-1,-1),1.5,GOLD),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(tt)
    if qr.get("notes"):
        story.append(Spacer(1,4*mm))
        story.append(Paragraph(f"<b>Notes:</b> {qr['notes']}",ParagraphStyle("N",parent=styles["Normal"],fontSize=9,textColor=NAVY)))
    story.append(Spacer(1,6*mm))
    story.append(HRFlowable(width="100%",thickness=0.5,color=HexColor("#CCCCCC"),spaceAfter=4))
    story.append(Paragraph("This quotation is indicative and subject to aircraft availability. Valid 48 hours.",sSm))
    doc.build(story,onFirstPage=hf,onLaterPages=hf); buf.seek(0); return buf.getvalue()

# ─── AUTH ────────────────────────────────────────────────────────────────────
def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _get_users():
    if "_users_db" not in st.session_state:
        try:
            import json; st.session_state["_users_db"]=json.loads(st.secrets.get("USERS_DB","{}"))
        except Exception: st.session_state["_users_db"]={}
    return st.session_state["_users_db"]

def _save_users(u): st.session_state["_users_db"]=u

def _register(email,pwd):
    email=email.strip().lower()
    if not _re.match(r"[^@]+@[^@]+\.[^@]+",email): return False,"Invalid email."
    if len(pwd)<6: return False,"Password must be at least 6 characters."
    u=_get_users()
    if email in u: return False,"Account already exists."
    u[email]={"pwd_hash":_hash(pwd),"stripe_cid":None,"active":False}; _save_users(u); return True,"Account created!"

def _login(email,pwd):
    email=email.strip().lower(); u=_get_users(); rec=u.get(email)
    if not rec or rec["pwd_hash"]!=_hash(pwd): return False,"Incorrect email or password."
    return True,rec

def _check_sub(email):
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        u=_get_users(); cid=u.get(email,{}).get("stripe_cid")
        if not cid:
            custs=stripe.Customer.list(email=email,limit=1)
            if not custs.data: return False
            cid=custs.data[0].id; u[email]["stripe_cid"]=cid; _save_users(u)
        subs=stripe.Subscription.list(customer=cid,status="active",limit=1)
        active=len(subs.data)>0; u[email]["active"]=active; _save_users(u); return active
    except Exception: return False

def _checkout_url(email):
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        s=stripe.checkout.Session.create(payment_method_types=["card"],mode="subscription",
            customer_email=email,line_items=[{"price":st.secrets["STRIPE_PRICE_ID"],"quantity":1}],
            success_url="https://aviation-cost-estimato-6uj3ptpc57onofwlavwhfn.streamlit.app/?subscribed=1",
            cancel_url="https://aviation-cost-estimato-6uj3ptpc57onofwlavwhfn.streamlit.app/?cancelled=1")
        return s.url
    except Exception: return None

def _sub_btn(email):
    url=_checkout_url(email)
    if url:
        st.markdown(f'<div style="text-align:center;margin-top:.6rem"><a href="{url}" target="_blank" style="background:#C9A84C;color:#0B1629;padding:.5rem 1.2rem;border-radius:5px;font-weight:700;text-decoration:none">⭐ Subscribe — 10€/month</a></div>', unsafe_allow_html=True)

def render_auth():
    for k,v in [("auth_email",None),("auth_premium",False),("auth_is_admin",False)]:
        if k not in st.session_state: st.session_state[k]=v
    email=st.session_state["auth_email"]; is_admin=st.session_state["auth_is_admin"]
    with st.sidebar:
        st.markdown("---")
        if email:
            if is_admin:
                st.markdown('<div style="font-size:.78rem;color:#F59E0B;font-weight:700">👑 ADMIN</div>', unsafe_allow_html=True)
                with st.expander("👥 Users"):
                    users=_get_users()
                    for ue,ud in users.items():
                        col="#4ADE80" if ud.get("active") else "#F87171"
                        st.markdown(f'<div style="font-size:.75rem;border-bottom:1px solid #1A3A6E"><b>{ue}</b> <span style="color:{col}">{"✓" if ud.get("active") else "✗"}</span></div>', unsafe_allow_html=True)
                    if st.button("🔄 Refresh",key="admin_ref",use_container_width=True):
                        for ue in list(users.keys()): users[ue]["active"]=_check_sub(ue)
                        _save_users(users); st.rerun()
            else:
                st.markdown(f'<div style="font-size:.78rem;color:#4ADE80">✓ {email}</div>', unsafe_allow_html=True)
                if st.session_state["auth_premium"]:
                    st.markdown('<div style="font-size:.72rem;color:#C9A84C">⭐ Premium</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="font-size:.72rem;color:#F87171;margin-bottom:.4rem">⚠ No subscription</div>', unsafe_allow_html=True)
                    _sub_btn(email)
                    if st.button("🔄 Check subscription",key="chk_sub",use_container_width=True):
                        st.session_state["auth_premium"]=_check_sub(email); st.rerun()
            if st.button("🚪 Log out",key="logout",use_container_width=True):
                st.session_state["auth_email"]=None; st.session_state["auth_premium"]=False
                st.session_state["auth_is_admin"]=False; st.rerun()
        else:
            st.markdown('<div class="section-header">🔐 Account</div>', unsafe_allow_html=True)
            view=st.radio("Account",["Login","Register"],horizontal=True,key="auth_view",label_visibility="collapsed")
            if view=="Login":
                em=st.text_input("Email",key="li_em",placeholder="your@email.com")
                pw=st.text_input("Password",key="li_pw",type="password")
                if st.button("Login",key="btn_login",use_container_width=True):
                    if em and pw:
                        try: ae=st.secrets.get("ADMIN_EMAIL",""); ap=st.secrets.get("ADMIN_PASSWORD","")
                        except: ae=ap=""
                        if em.strip().lower()==ae.lower() and pw==ap:
                            st.session_state["auth_email"]=em.strip().lower()
                            st.session_state["auth_premium"]=True; st.session_state["auth_is_admin"]=True; st.rerun()
                        else:
                            ok,res=_login(em,pw)
                            if ok:
                                st.session_state["auth_email"]=em.strip().lower()
                                st.session_state["auth_premium"]=_check_sub(em.strip().lower())
                                st.session_state["auth_is_admin"]=False; st.rerun()
                            else: st.error(res)
                    else: st.warning("Fill in all fields.")
            else:
                em=st.text_input("Email",key="rg_em",placeholder="your@email.com")
                pw=st.text_input("Password (min 6)",key="rg_pw",type="password")
                pw2=st.text_input("Confirm",key="rg_pw2",type="password")
                if st.button("Create account",key="btn_reg",use_container_width=True):
                    if pw!=pw2: st.error("Passwords do not match.")
                    elif em and pw:
                        ok,msg=_register(em,pw)
                        if ok: st.success(msg); _sub_btn(em.strip().lower())
                        else: st.error(msg)
                    else: st.warning("Fill in all fields.")
            st.markdown('<div style="font-size:.7rem;color:#8496B0;text-align:center;margin-top:.4rem">Dashboard free · Full access 10€/month</div>', unsafe_allow_html=True)
    return st.session_state.get("auth_premium",False)

def premium_gate():
    email=st.session_state.get("auth_email")
    st.markdown("""<div style="background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
         border:1px solid #C9A84C;border-radius:12px;padding:2.5rem;text-align:center;margin:2rem 0">
        <div style="font-size:2rem;margin-bottom:.8rem">🔒</div>
        <div style="font-size:1.3rem;font-weight:700;color:#E8C46A;margin-bottom:.5rem">Premium Feature</div>
        <div style="font-size:.9rem;color:#8496B0;margin-bottom:1.5rem">Full access requires a subscription.<br><b style="color:#C9A84C">€10/month</b></div>
    </div>""", unsafe_allow_html=True)
    if not email: st.info("👈 Create a free account in the sidebar.")
    else: _sub_btn(email)

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    for k,v in [("database",None),("cost_master",None),("pdf_report",None),
                ("auth_email",None),("auth_premium",False),("auth_is_admin",False),
                ("_users_db",{}),("q_legs",[{"from":"","to":"","dep_time":"08:00"}]),
                ("q_result",None),("q_pdf",None)]:
        if k not in st.session_state: st.session_state[k]=v

    is_premium=render_auth()

    # Header
    c1,c2=st.columns([1,6])
    with c1: st.markdown("<div style='font-size:3rem;text-align:center;margin-top:.3rem'>✈</div>",unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="main-title">Aviation Cost Estimator</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Operating Cost Simulation — Business Aviation</div>',unsafe_allow_html=True)
    st.markdown("<hr>",unsafe_allow_html=True)

    df=get_active_db()

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="section-header">✈ Aircraft Selection</div>',unsafe_allow_html=True)
        df=get_active_db()
        cats=["All"]+sorted(df["Categorie"].dropna().unique().tolist())
        cat_sel=st.selectbox("Category",cats)
        df_f=df if cat_sel=="All" else df[df["Categorie"]==cat_sel]
        ac_sel=st.selectbox("Aircraft Model",df_f["Modele"].tolist())
        aircraft=df_f[df_f["Modele"]==ac_sel].iloc[0]
        st.markdown('<div class="section-header">🕐 Flight Hours</div>',unsafe_allow_html=True)
        h_charter=st.slider("Charter Hours/year",0,800,380,step=10)
        h_private=st.slider("Private Hours/year",0,800,120,step=10)
        if h_charter+h_private>800: st.warning(f"⚠ Total {h_charter+h_private}h > 800h limit")
        st.markdown('<div class="section-header">💰 Charter Pricing</div>',unsafe_allow_html=True)
        db_rate=float(aircraft.get("Taux_Charter_EUR_h",0))
        st.caption(f"DB rate: € {db_rate:,.0f}/h")
        use_custom=st.toggle("Custom charter price",value=False)
        if use_custom:
            custom_rate=st.number_input("Your rate (€/h)",min_value=0,max_value=200000,value=int(db_rate) if db_rate>0 else 5000,step=100)
        else: custom_rate=db_rate
        commission_pct=st.slider("Commission (%)",0,25,10,step=1)

    costs=calculate_costs(aircraft,h_charter,h_private)
    prof=calculate_profitability(costs,commission_pct,custom_rate)

    tab1,tab2,tab3,tab4,tab5=st.tabs(["📊 Dashboard","📈 Profitability","🔍 Sensitivity","💼 Cost Master","✈️ Quotation"])

    # TAB 1: DASHBOARD
    with tab1:
        k1,k2,k3,k4=st.columns(4)
        with k1:
            st.markdown(f'''<div class="metric-card"><div class="metric-label">Aircraft</div>
                <div class="metric-value" style="font-size:1.2rem;color:#000000">{aircraft["Modele"]}</div>
                <div class="metric-sub">{aircraft.get("Categorie","—")}</div></div>''',unsafe_allow_html=True)
        with k2:
            st.markdown(f'''<div class="metric-card"><div class="metric-label">Total Hours/Year</div>
                <div class="metric-value">{costs["total_hours"]}h</div>
                <div class="metric-sub">{h_charter}h charter · {h_private}h private</div></div>''',unsafe_allow_html=True)
        with k3:
            if pd.notna(aircraft.get("Autonomie_km",None)):
                st.markdown(f'''<div class="metric-card"><div class="metric-label">Max Range</div>
                    <div class="metric-value">{aircraft["Autonomie_km"]:,.0f} km</div>
                    <div class="metric-sub">{aircraft.get("Passagers_Max","—")} pax max</div></div>''',unsafe_allow_html=True)
        with k4:
            if pd.notna(aircraft.get("Vitesse_Croisiere_km_h",None)):
                st.markdown(f'''<div class="metric-card"><div class="metric-label">Cruise Speed</div>
                    <div class="metric-value">{aircraft["Vitesse_Croisiere_km_h"]} km/h</div>
                    <div class="metric-sub">Certified performance</div></div>''',unsafe_allow_html=True)
        st.markdown("<hr>",unsafe_allow_html=True)
        m1,m2,m3,m4=st.columns(4)
        m1.metric("💶 Total Annual Cost",fmt(costs["grand_total"]))
        m2.metric("🔒 Fixed Costs",fmt(costs["total_fixed"]))
        m3.metric("⚡ Variable Costs",fmt(costs["total_variable"]))
        m4.metric("⌛ Cost/Hour",fmt(costs["avg_cost_h"]))
        st.markdown("<hr>",unsafe_allow_html=True)
        g1,g2=st.columns(2)
        with g1:
            st.markdown('<div class="section-header">Cost Breakdown</div>',unsafe_allow_html=True)
            st.plotly_chart(chart_donut(costs),use_container_width=True,config={"displayModeBar":False})
        with g2:
            st.markdown('<div class="section-header">Cost by Flight Mode</div>',unsafe_allow_html=True)
            st.plotly_chart(chart_bars(costs),use_container_width=True,config={"displayModeBar":False})

    # TAB 2: PROFITABILITY
    with tab2:
        if not is_premium: premium_gate(); st.stop()
        st.markdown('<div class="section-header">Charter Profitability Simulation</div>',unsafe_allow_html=True)
        if h_charter==0:
            st.warning("⚠ No charter hours configured.")
        else:
            net=prof["net_result"]; cr=prof["coverage_rate"]
            badge='<span class="tag-ok">✓ PROFITABLE</span>' if net>=0 else ('<span class="tag-warn">⚠ NEAR BREAK-EVEN</span>' if cr>=70 else '<span class="tag-err">✗ LOSS-MAKING</span>')
            st.markdown(f"**Status:** {badge} — Coverage: **{cr:.1f}%**",unsafe_allow_html=True)
            er=prof["effective_rate"]
            st.markdown(f'''<div class="metric-card" style="margin:.8rem 0"><div class="metric-label">Effective Rate</div>
                <div class="metric-value">€ {er:,.0f} <span style="font-size:1rem;color:#8496B0">/h</span></div>
                <div class="metric-sub">{h_charter}h × € {er:,.0f} = € {er*h_charter:,.0f}</div></div>''',unsafe_allow_html=True)
            r1,r2,r3,r4=st.columns(4)
            r1.metric("💵 Gross Revenue",fmt(prof["gross_revenue"]))
            r2.metric("📉 Commission",fmt(prof["commission"]))
            r3.metric("💰 Net Revenue",fmt(prof["net_revenue"]))
            r4.metric("📊 Net Result",fmt(net),delta=f"{cr:.1f}%")
            st.markdown("<hr>",unsafe_allow_html=True)
            st.plotly_chart(chart_waterfall(costs,prof),use_container_width=True,config={"displayModeBar":False})

    # TAB 3: SENSITIVITY
    with tab3:
        if not is_premium: premium_gate(); st.stop()
        st.markdown('<div class="section-header">Sensitivity — Charter Hours vs Net Result</div>',unsafe_allow_html=True)
        st.caption(f"Private: {h_private}h | Commission: {commission_pct}% | Rate: € {custom_rate:,.0f}/h")
        st.plotly_chart(chart_sensitivity(aircraft,h_private,commission_pct,custom_rate),use_container_width=True,config={"displayModeBar":False})
        st.markdown('<div class="section-header">Fleet Comparison</div>',unsafe_allow_html=True)
        comp=[{"Model":row["Modele"],"Total Cost (€)":round(calculate_costs(row,h_charter,h_private)["grand_total"]),
               "Cost/Hour (€)":round(calculate_costs(row,h_charter,h_private)["avg_cost_h"])} for _,row in df.iterrows()]
        df_c=pd.DataFrame(comp).sort_values("Total Cost (€)")
        fig_c=px.bar(df_c,x="Model",y="Total Cost (€)",color="Cost/Hour (€)",
                     color_continuous_scale=["#1A3A6E","#4A90D9","#C9A84C","#E8C46A"],template="plotly_dark")
        fig_c.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#D6E4F7"),height=350,margin=dict(t=10,b=80,l=10,r=10),
                            xaxis=dict(tickangle=-30),yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f"))
        st.plotly_chart(fig_c,use_container_width=True,config={"displayModeBar":False})

    # TAB 4: COST MASTER
    with tab4:
        if not is_premium: premium_gate(); st.stop()
        st.markdown('<div class="main-title" style="font-size:1.4rem">💼 Cost Master</div>',unsafe_allow_html=True)
        cfg1,cfg2,cfg3=st.columns(3)
        with cfg1: annual_flights=st.number_input("Annual flights",min_value=1,max_value=2000,value=200,step=10)
        with cfg2: cm_rate=st.number_input("Charter rate (€/h)",min_value=0,max_value=200000,value=int(custom_rate) if custom_rate>0 else int(db_rate),step=500)
        with cfg3: cm_comm=st.slider("Commission (%)",0,25,int(commission_pct),step=1,key="cm_comm")
        st.markdown("<hr>",unsafe_allow_html=True)
        mc1,mc2,mc3=st.columns(3)
        with mc1: use_gop=st.radio("✈ Operational",["🌐 Generic","✏️ Custom"],horizontal=True,key="gop")=="🌐 Generic"
        with mc2: use_gdir=st.radio("🔧 Direct",["🌐 Generic","✏️ Custom"],horizontal=True,key="gdir")=="🌐 Generic"
        with mc3: use_gind=st.radio("👥 Indirect",["🌐 Generic","✏️ Custom"],horizontal=True,key="gind")=="🌐 Generic"

        def render_block(title,color,defaults,prefix,use_generic,step=100.0):
            vals={}
            with st.expander(title,expanded=True):
                st.markdown(f'<div style="font-size:.72rem;color:{color};letter-spacing:.1em;margin-bottom:.6rem">{"🌐 GENERIC" if use_generic else "✏️ CUSTOM"}</div>',unsafe_allow_html=True)
                pairs=list(defaults.items())
                for i in range(0,len(pairs),2):
                    c1,c2,c3,c4=st.columns([2.2,1,2.2,1])
                    k1,d1=pairs[i]
                    with c1: st.markdown(f'<span style="font-size:.82rem;color:#D6E4F7">{k1}</span>',unsafe_allow_html=True)
                    with c2:
                        if use_generic: st.markdown(f'<span style="color:#E8C46A;font-size:.88rem;font-weight:600">€ {d1:,.0f}</span>',unsafe_allow_html=True); vals[k1]=float(d1)
                        else: vals[k1]=st.number_input(k1,value=float(d1),min_value=0.0,step=step,label_visibility="collapsed",key=f"{prefix}_{k1}")
                    if i+1<len(pairs):
                        k2,d2=pairs[i+1]
                        with c3: st.markdown(f'<span style="font-size:.82rem;color:#D6E4F7">{k2}</span>',unsafe_allow_html=True)
                        with c4:
                            if use_generic: st.markdown(f'<span style="color:#E8C46A;font-size:.88rem;font-weight:600">€ {d2:,.0f}</span>',unsafe_allow_html=True); vals[k2]=float(d2)
                            else: vals[k2]=st.number_input(k2,value=float(d2),min_value=0.0,step=step,label_visibility="collapsed",key=f"{prefix}_{k2}")
            return vals

        op_vals=render_block("✈ OPERATIONAL (per flight)","#60A5FA",CM_OP,"op",use_gop,50.0)
        op_pf=sum(op_vals.values()); op_a=op_pf*annual_flights
        st.markdown(f'<div style="padding:.4rem .8rem;background:#112244;border-radius:4px;font-size:.84rem;margin-bottom:.5rem">Per flight: <b style="color:#60A5FA">€ {op_pf:,.0f}</b> · Annual: <b style="color:#60A5FA">€ {op_a:,.0f}</b></div>',unsafe_allow_html=True)
        dir_vals=render_block("🔧 DIRECT COSTS (annual)","#F59E0B",CM_DIR,"dir",use_gdir,500.0)
        dir_t=sum(dir_vals.values())
        st.markdown(f'<div style="padding:.4rem .8rem;background:#112244;border-radius:4px;font-size:.84rem;margin-bottom:.5rem">Direct total: <b style="color:#F59E0B">€ {dir_t:,.0f}</b></div>',unsafe_allow_html=True)
        ind_vals=render_block("👥 INDIRECT / CREW (annual)","#A78BFA",CM_IND,"ind",use_gind,500.0)
        ind_t=sum(ind_vals.values())
        st.markdown(f'<div style="padding:.4rem .8rem;background:#112244;border-radius:4px;font-size:.84rem;margin-bottom:.5rem">Indirect total: <b style="color:#A78BFA">€ {ind_t:,.0f}</b></div>',unsafe_allow_html=True)

        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("🚀 Generate Financial Analysis",use_container_width=True):
            ft=op_a; st.session_state["cost_master"]=dict(op_vals=op_vals,op_annual=op_a,op_per_flight=op_pf,
                dir_vals=dir_vals,dir_total=dir_t,ind_vals=ind_vals,ind_total=ind_t,annual_flights=annual_flights,
                charter_rate=cm_rate,commission_pct=cm_comm,h_charter=h_charter,aircraft_name=aircraft["Modele"])

        if st.session_state.get("cost_master"):
            cm=st.session_state["cost_master"]; op_a2=cm["op_annual"]; dir_a=cm["dir_total"]; ind_a=cm["ind_total"]
            grand=op_a2+dir_a+ind_a; gross=cm["charter_rate"]*cm["h_charter"]
            commission=gross*cm["commission_pct"]/100; nr=gross-commission; net=nr-grand; cov=(nr/grand*100) if grand>0 else 0
            st.markdown("<hr>",unsafe_allow_html=True)
            st.markdown(f'''<div class="total-banner">
                <div style="font-size:.72rem;color:#8496B0;margin-bottom:.4rem">{cm["aircraft_name"]}</div>
                <div style="font-size:2.4rem;font-weight:800;color:#E8C46A">€ {grand:,.0f}</div>
                <div style="font-size:.85rem;color:#8496B0">Op: <b style="color:#60A5FA">€ {op_a2:,.0f}</b> · Direct: <b style="color:#F59E0B">€ {dir_a:,.0f}</b> · Crew: <b style="color:#A78BFA">€ {ind_a:,.0f}</b></div>
            </div>''',unsafe_allow_html=True)
            kk1,kk2,kk3,kk4,kk5=st.columns(5)
            kk1.metric("✈ Gross Revenue",fmt(gross)); kk2.metric("📉 Commission",fmt(commission))
            kk3.metric("💰 Net Revenue",fmt(nr)); kk4.metric("💸 Total Costs",fmt(grand))
            kk5.metric("📊 Net Result",fmt(net),delta=f"{cov:.1f}%")
            st.markdown("<hr>",unsafe_allow_html=True)
            d1,d2=st.columns(2)
            with d1: st.plotly_chart(cm_global_donut(op_a2,dir_a,ind_a),use_container_width=True,config={"displayModeBar":False})
            with d2: st.plotly_chart(cm_waterfall(op_a2,dir_a,ind_a,gross,cm["commission_pct"]),use_container_width=True,config={"displayModeBar":False})
            b1,b2,b3=st.columns(3)
            with b1: st.plotly_chart(cm_donut(list(cm["op_vals"].keys()),[v*cm["annual_flights"] for v in cm["op_vals"].values()],["#60A5FA","#3B82F6","#1D4ED8","#93C5FD","#BFDBFE","#2563EB","#1E40AF","#DBEAFE"],"Operational"),use_container_width=True,config={"displayModeBar":False})
            with b2: st.plotly_chart(cm_donut(list(cm["dir_vals"].keys()),list(cm["dir_vals"].values()),["#F59E0B","#D97706","#B45309","#FCD34D","#FDE68A","#92400E","#FBBF24","#FEF3C7","#78350F"],"Direct"),use_container_width=True,config={"displayModeBar":False})
            with b3: st.plotly_chart(cm_donut(list(cm["ind_vals"].keys()),list(cm["ind_vals"].values()),["#A78BFA","#8B5CF6","#7C3AED","#C4B5FD","#DDD6FE","#6D28D9","#5B21B6","#EDE9FE","#4C1D95"],"Crew"),use_container_width=True,config={"displayModeBar":False})
            st.markdown("<hr>",unsafe_allow_html=True)
            bb1,bb2,bb3=st.columns(3)
            with bb1: st.plotly_chart(cm_bar(list(cm["op_vals"].keys()),[v*cm["annual_flights"] for v in cm["op_vals"].values()],"#60A5FA","Operational"),use_container_width=True,config={"displayModeBar":False})
            with bb2: st.plotly_chart(cm_bar(list(cm["dir_vals"].keys()),list(cm["dir_vals"].values()),"#F59E0B","Direct"),use_container_width=True,config={"displayModeBar":False})
            with bb3: st.plotly_chart(cm_bar(list(cm["ind_vals"].keys()),list(cm["ind_vals"].values()),"#A78BFA","Crew"),use_container_width=True,config={"displayModeBar":False})
            st.markdown("<hr>",unsafe_allow_html=True)
            rows2=[]
            for k,v in cm["op_vals"].items(): rows2.append({"Category":"Operational","Line":k,"Annual (€)":f"€ {v*cm['annual_flights']:,.0f}","% Total":f"{v*cm['annual_flights']/grand*100:.1f}%"})
            for k,v in cm["dir_vals"].items(): rows2.append({"Category":"Direct","Line":k,"Annual (€)":f"€ {v:,.0f}","% Total":f"{v/grand*100:.1f}%"})
            for k,v in cm["ind_vals"].items(): rows2.append({"Category":"Crew","Line":k,"Annual (€)":f"€ {v:,.0f}","% Total":f"{v/grand*100:.1f}%"})
            st.dataframe(pd.DataFrame(rows2),use_container_width=True,hide_index=True)
            if st.button("📄 Generate PDF Report",use_container_width=True,type="primary"):
                with st.spinner("Building report..."):
                    try:
                        st.session_state["pdf_report"]=generate_pdf_report(cm,aircraft,annual_flights)
                        st.success("✓ Report ready!")
                    except Exception as e: st.error(f"PDF error: {e}")
            if st.session_state.get("pdf_report"):
                st.download_button("⬇ Download PDF Report",data=st.session_state["pdf_report"],
                    file_name=f"Menkor_Cost_{aircraft['Modele'].replace(' ','_')}.pdf",mime="application/pdf",use_container_width=True)

    # TAB 5: QUOTATION
    with tab5:
        if not is_premium: premium_gate(); st.stop()
        st.markdown('<div class="main-title" style="font-size:1.4rem">✈️ Flight Quotation</div>',unsafe_allow_html=True)
        q1,q2,q3=st.columns([2,1,1])
        with q1:
            df_q=get_active_db(); q_ac_name=st.selectbox("Aircraft",df_q["Modele"].tolist(),key="q_aircraft")
            q_ac=df_q[df_q["Modele"]==q_ac_name].iloc[0]; speed=float(q_ac["Vitesse_Croisiere_km_h"])*0.9
        with q2: q_rate=st.number_input("Rate (€/h)",min_value=0,max_value=200000,value=int(q_ac.get("Taux_Charter_EUR_h",5000)),step=100,key="q_rate")
        with q3: q_curr=st.selectbox("Currency",["EUR","USD","GBP","AED"],key="q_curr")
        sp1,sp2,sp3,sp4=st.columns(4)
        sp1.metric("Category",q_ac.get("Categorie","—"))
        sp2.metric("Cruise Speed",f"{q_ac['Vitesse_Croisiere_km_h']} km/h")
        sp3.metric("Max Range",f"{q_ac.get('Autonomie_km',0):,.0f} km")
        sp4.metric("Pax Max",str(q_ac.get("Passagers_Max","—")))
        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown('<div class="section-header">✈ Route</div>',unsafe_allow_html=True)
        legs=st.session_state["q_legs"]
        for i,leg in enumerate(legs):
            lc1,lc2,lc3,lc4=st.columns([2.5,2.5,1.5,0.5])
            with lc1: legs[i]["from"]=st.text_input("From",value=leg["from"],placeholder="e.g. Dubai OMDB",key=f"qf_{i}")
            with lc2: legs[i]["to"]=st.text_input("To",value=leg["to"],placeholder="e.g. London EGLL",key=f"qt_{i}")
            with lc3: legs[i]["dep_time"]=st.text_input("Dep.",value=leg["dep_time"],placeholder="HH:MM",key=f"qd_{i}")
            with lc4:
                st.markdown("<br>",unsafe_allow_html=True)
                if i>0 and st.button("✕",key=f"qdel_{i}"): legs.pop(i); st.rerun()
        st.markdown("<hr>",unsafe_allow_html=True)
        ex1,ex2=st.columns(2)
        with ex1:
            st.markdown('<div style="font-size:.78rem;color:#60A5FA;font-weight:600;margin-bottom:.5rem">👤 Crew</div>',unsafe_allow_html=True)
            q_fa=st.number_input("Flight Attendant(s)",min_value=0,max_value=6,value=1,key="q_fa")
            q_fa_rate=st.number_input("FA daily rate (€)",min_value=0,value=500,step=50,key="q_fa_rate")
            q_fa_days=st.number_input("Number of days",min_value=1,value=1,key="q_fa_days")
            q_fa_t=q_fa*q_fa_rate*q_fa_days
            st.markdown('<div style="font-size:.78rem;color:#60A5FA;font-weight:600;margin-top:.8rem;margin-bottom:.5rem">🍽️ Catering</div>',unsafe_allow_html=True)
            q_cat_pax=st.number_input("Passengers",min_value=0,value=4,key="q_cat_pax")
            q_cat_rate=st.number_input("Catering/pax (€)",min_value=0,value=150,step=10,key="q_cat_rate")
            q_cat_t=q_cat_pax*q_cat_rate
        with ex2:
            st.markdown('<div style="font-size:.78rem;color:#F59E0B;font-weight:600;margin-bottom:.5rem">⭐ Special Services</div>',unsafe_allow_html=True)
            sp1n=st.text_input("Service 1",value="Ground Transfer",key="sp1n"); sp1p=st.number_input("Cost (€)",min_value=0,value=0,step=50,key="sp1p")
            sp2n=st.text_input("Service 2",value="",key="sp2n"); sp2p=st.number_input("Cost (€) ",min_value=0,value=0,step=50,key="sp2p")
            sp3n=st.text_input("Service 3",value="",key="sp3n"); sp3p=st.number_input("Cost (€)  ",min_value=0,value=0,step=50,key="sp3p")
            q_notes=st.text_area("Notes",placeholder="VIP requirements...",height=80,key="q_notes")
        q_extras=[]
        if q_fa>0 and q_fa_t>0: q_extras.append({"name":f"Flight Attendant x{q_fa} ({q_fa_days}d)","cost":q_fa_t})
        if q_cat_t>0: q_extras.append({"name":f"Catering ({q_cat_pax} pax)","cost":q_cat_t})
        for sn,sp in [(sp1n,sp1p),(sp2n,sp2p),(sp3n,sp3p)]:
            if sn.strip() and sp>0: q_extras.append({"name":sn.strip(),"cost":sp})
        extras_t=sum(e["cost"] for e in q_extras)
        if q_extras: st.markdown(f'<div style="padding:.4rem .8rem;background:#112244;border-radius:4px;font-size:.84rem;margin:.5rem 0">Extras: <b style="color:#F59E0B">€ {extras_t:,.0f}</b></div>',unsafe_allow_html=True)
        ca1,ca2=st.columns([1,2])
        with ca1:
            if st.button("➕ Add stop",use_container_width=True):
                last=legs[-1]["to"] if legs else ""; legs.append({"from":last,"to":"","dep_time":"12:00"}); st.rerun()
        with ca2:
            calc=st.button("🧮 Calculate & Generate Quotation",use_container_width=True,type="primary")

        _AIRPORTS = {
            "OMDB":("Dubai Intl",25.2528,55.3644),"DXB":("Dubai Intl",25.2528,55.3644),
            "DUBAI":("Dubai",25.2048,55.2708),"OMAA":("Abu Dhabi",24.4330,54.6511),
            "AUH":("Abu Dhabi",24.4330,54.6511),"OMDW":("Al Maktoum",24.8963,55.1614),
            "EGLL":("London Heathrow",51.4775,-0.4614),"LHR":("London Heathrow",51.4775,-0.4614),
            "EGGW":("London Luton",51.8747,-0.3683),"LTN":("London Luton",51.8747,-0.3683),
            "EGKK":("London Gatwick",51.1537,-0.1821),"LGW":("London Gatwick",51.1537,-0.1821),
            "LFPG":("Paris CDG",49.0097,2.5479),"CDG":("Paris CDG",49.0097,2.5479),
            "LFPB":("Paris Le Bourget",48.9694,2.4414),"LBG":("Paris Le Bourget",48.9694,2.4414),
            "LFPO":("Paris Orly",48.7233,2.3794),"ORY":("Paris Orly",48.7233,2.3794),
            "LFMN":("Nice",43.6584,7.2159),"NCE":("Nice",43.6584,7.2159),
            "LFKJ":("Ajaccio",41.9236,8.8029),"AJA":("Ajaccio",41.9236,8.8029),
            "LFML":("Marseille",43.4393,5.2214),"MRS":("Marseille",43.4393,5.2214),
            "LFLL":("Lyon",45.7256,5.0811),"LYS":("Lyon",45.7256,5.0811),
            "LFLY":("Lyon Bron",45.7272,4.9444),
            "LFBO":("Toulouse",43.6293,1.3638),"TLS":("Toulouse",43.6293,1.3638),
            "LFBD":("Bordeaux",44.8283,-0.7156),"BOD":("Bordeaux",44.8283,-0.7156),
            "LFRN":("Rennes",48.0695,-1.7348),"RNS":("Rennes",48.0695,-1.7348),
            "LFRS":("Nantes",47.1532,-1.6108),"NTE":("Nantes",47.1532,-1.6108),
            "LFSB":("Basel Mulhouse",47.5896,7.5290),"BSL":("Basel",47.5896,7.5290),
            "LFST":("Strasbourg",48.5383,7.6281),"SXB":("Strasbourg",48.5383,7.6281),
            "LFPV":("Paris Villacoublay",48.7742,2.2011),
            "LFPT":("Paris Pontoise",49.0967,2.0406),
            "EDDF":("Frankfurt",50.0333,8.5706),"FRA":("Frankfurt",50.0333,8.5706),
            "EHAM":("Amsterdam",52.3086,4.7639),"AMS":("Amsterdam",52.3086,4.7639),
            "LEMD":("Madrid",40.4983,-3.5676),"MAD":("Madrid",40.4983,-3.5676),
            "LEBL":("Barcelona",41.2971,2.0785),"BCN":("Barcelona",41.2971,2.0785),
            "LIRF":("Rome Fiumicino",41.8003,12.2389),"FCO":("Rome",41.8003,12.2389),
            "LMML":("Malta",35.8575,14.4775),"MLA":("Malta",35.8575,14.4775),
            "GMMN":("Casablanca",33.3675,-7.5900),"CMN":("Casablanca",33.3675,-7.5900),
            "HECA":("Cairo",30.1219,31.4056),"CAI":("Cairo",30.1219,31.4056),
            "FACT":("Cape Town",-33.9649,18.6017),"CPT":("Cape Town",-33.9649,18.6017),
            "FAOR":("Johannesburg",-26.1392,28.2460),"JNB":("Johannesburg",-26.1392,28.2460),
            "HKJK":("Nairobi",-1.3192,36.9275),"NBO":("Nairobi",-1.3192,36.9275),
            "OTHH":("Doha",25.2731,51.6080),"DOH":("Doha",25.2731,51.6080),
            "OERK":("Riyadh",24.9578,46.6988),"RUH":("Riyadh",24.9578,46.6988),
            "OKBK":("Kuwait",29.2267,47.9689),"KWI":("Kuwait",29.2267,47.9689),
            "LSZH":("Zurich",47.4647,8.5492),"ZRH":("Zurich",47.4647,8.5492),
            "LSGG":("Geneva",46.2381,6.1089),"GVA":("Geneva",46.2381,6.1089),
            "ESSA":("Stockholm",59.6519,17.9186),"ARN":("Stockholm",59.6519,17.9186),
            "LOWW":("Vienna",48.1103,16.5697),"VIE":("Vienna",48.1103,16.5697),
            "UUEE":("Moscow",55.9726,37.4146),"SVO":("Moscow",55.9726,37.4146),
            "LLBG":("Tel Aviv",32.0114,34.8867),"TLV":("Tel Aviv",32.0114,34.8867),
            "LGAV":("Athens",37.9364,23.9445),"ATH":("Athens",37.9364,23.9445),
            "LTBA":("Istanbul",40.9769,28.8146),"IST":("Istanbul",40.9769,28.8146),
            "YSSY":("Sydney",-33.9461,151.1772),"SYD":("Sydney",-33.9461,151.1772),
            "KLAX":("Los Angeles",33.9425,-118.4081),"LAX":("Los Angeles",33.9425,-118.4081),
            "KJFK":("New York JFK",40.6413,-73.7781),"JFK":("New York JFK",40.6413,-73.7781),
            "KMIA":("Miami",25.7959,-80.2870),"MIA":("Miami",25.7959,-80.2870),
            "VIDP":("New Delhi",28.5665,77.1031),"DEL":("New Delhi",28.5665,77.1031),
            "VABB":("Mumbai",19.0887,72.8679),"BOM":("Mumbai",19.0887,72.8679),
            "WSSS":("Singapore",1.3592,103.9894),"SIN":("Singapore",1.3592,103.9894),
            "VTBS":("Bangkok",13.6900,100.7501),"BKK":("Bangkok",13.6900,100.7501),
            "RJTT":("Tokyo Haneda",35.5494,139.7798),"HND":("Tokyo Haneda",35.5494,139.7798),
            "ZBAA":("Beijing",40.0799,116.6031),"PEK":("Beijing",40.0799,116.6031),
            "LONDON":("London",51.5074,-0.1278),"PARIS":("Paris",48.8566,2.3522),
            "AMSTERDAM":("Amsterdam",52.3676,4.9041),"BERLIN":("Berlin",52.5200,13.4050),
            "ROME":("Rome",41.9028,12.4964),"MADRID":("Madrid",40.4168,-3.7038),
            "BARCELONA":("Barcelona",41.3851,2.1734),"MOSCOW":("Moscow",55.7558,37.6173),
            "TOKYO":("Tokyo",35.6762,139.6503),"SINGAPORE":("Singapore",1.3521,103.8198),
            "MUMBAI":("Mumbai",19.0760,72.8777),"DELHI":("New Delhi",28.6139,77.2090),
            "ISTANBUL":("Istanbul",41.0082,28.9784),"ZURICH":("Zurich",47.3769,8.5417),
            "GENEVA":("Geneva",46.2044,6.1432),"NICE":("Nice",43.7102,7.2620),
            "CANNES":("Cannes",43.5528,7.0174),"MONACO":("Monaco",43.7384,7.4246),
            "MARRAKECH":("Marrakech",31.6295,-7.9811),"DOHA":("Doha",25.2854,51.5310),
            "DUBAI AL MAKTOUM":("Al Maktoum",24.8963,55.1614),
        }
        def geocode(place):
            key=place.strip().upper().replace("-","")
            if key in _AIRPORTS: n,la,lo=_AIRPORTS[key]; return la,lo,n
            # partial match
            for k,(n,la,lo) in _AIRPORTS.items():
                if key in k or k in key: return la,lo,n
            # name match
            pl=place.strip().lower()
            for k,(n,la,lo) in _AIRPORTS.items():
                if pl in n.lower() or n.lower() in pl: return la,lo,n
            # try nominatim as last resort
            try:
                r=requests.get("https://nominatim.openstreetmap.org/search",
                    params={"q":place,"format":"json","limit":1},
                    headers={"User-Agent":"MenkorAviationQuotation/1.0"},timeout=6)
                d=r.json()
                if d: return float(d[0]["lat"]),float(d[0]["lon"]),d[0]["display_name"]
            except Exception: pass
            return None,None,None

        def haversine(la1,lo1,la2,lo2):
            import math; R=6371; dl=math.radians(la2-la1); dg=math.radians(lo2-lo1)
            a=math.sin(dl/2)**2+math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dg/2)**2
            return R*2*math.asin(math.sqrt(a))

        def ft_str(dist,spd):
            tm=(dist/spd)*60+10; h=int(tm//60); m=int(tm%60); return tm,f"{h}h {m:02d}m"

        if calc:
            ald=[]; errs=[]
            prog=st.progress(0,text="Geocoding...")
            tot=sum(2 for l in legs if l["from"] and l["to"]); step=0
            for i,leg in enumerate(legs):
                if not leg["from"] or not leg["to"]: errs.append(f"Leg {i+1}: fill From and To."); continue
                la1,lo1,n1=geocode(leg["from"]); step+=1; prog.progress(step/max(tot,1),text=f"Locating {leg['from']}...")
                la2,lo2,n2=geocode(leg["to"]); step+=1; prog.progress(step/max(tot,1),text=f"Locating {leg['to']}...")
                if None in (la1,lo1,la2,lo2): errs.append(f"Leg {i+1}: could not locate airports."); continue
                dist=haversine(la1,lo1,la2,lo2); tm,fts=ft_str(dist,speed); cost=(tm/60)*q_rate
                ald.append(dict(from_name=leg["from"],to_name=leg["to"],dep_time=leg["dep_time"],
                    lat1=la1,lon1=lo1,full_name1=n1,lat2=la2,lon2=lo2,full_name2=n2,
                    dist_km=dist,flight_time_min=tm,flight_time_str=fts,cost=cost))
            prog.empty()
            if errs:
                for e in errs: st.error(e)
            else:
                ft=sum(l["cost"] for l in ald)
                st.session_state["q_result"]=dict(legs=ald,aircraft=q_ac_name,rate=q_rate,currency=q_curr,speed=speed,
                    total_dist=sum(l["dist_km"] for l in ald),total_min=sum(l["flight_time_min"] for l in ald),
                    total_cost=ft+extras_t,flight_cost=ft,extras=q_extras,extras_total=extras_t,notes=q_notes)

        if st.session_state.get("q_result"):
            qr=st.session_state["q_result"]; ald=qr["legs"]
            st.markdown("<hr>",unsafe_allow_html=True)
            rk1,rk2,rk3,rk4,rk5=st.columns(5)
            rk1.metric("Distance",f"{qr['total_dist']:,.0f} km")
            rk2.metric("Flight Time",f"{int(qr['total_min']//60)}h {int(qr['total_min']%60):02d}m")
            rk3.metric("Flight Cost",f"{qr['currency']} {qr.get('flight_cost',qr['total_cost']):,.0f}")
            rk4.metric("Extras",f"{qr['currency']} {qr.get('extras_total',0):,.0f}")
            rk5.metric("💰 Total Quote",f"{qr['currency']} {qr['total_cost']:,.0f}")
            st.markdown("<hr>",unsafe_allow_html=True)
            st.markdown('<div class="section-header">🗺 Route Map</div>',unsafe_allow_html=True)
            fig_map=go.Figure()
            clrs=["#C9A84C","#60A5FA","#4ADE80","#F87171","#A78BFA"]
            all_la=[]; all_lo=[]
            for i,leg in enumerate(ald):
                clr=clrs[i%len(clrs)]; n=50
                alats=[leg["lat1"]+(leg["lat2"]-leg["lat1"])*s/n for s in range(n+1)]
                alons=[leg["lon1"]+(leg["lon2"]-leg["lon1"])*s/n for s in range(n+1)]
                fig_map.add_trace(go.Scattergeo(lat=alats,lon=alons,mode="lines",line=dict(width=2.5,color=clr),
                    name=f"Leg {i+1}: {leg['from_name']} → {leg['to_name']}",hoverinfo="skip"))
                mid=len(alats)//2
                fig_map.add_trace(go.Scattergeo(lat=[alats[mid]],lon=[alons[mid]],mode="markers",
                    marker=dict(size=8,color=clr,symbol="triangle-right"),showlegend=False,hoverinfo="skip"))
                all_la+=[leg["lat1"],leg["lat2"]]; all_lo+=[leg["lon1"],leg["lon2"]]
            seen={}
            for leg in ald:
                for lk,lok,nk,fk in [("lat1","lon1","from_name","full_name1"),("lat2","lon2","to_name","full_name2")]:
                    k=(round(leg[lk],2),round(leg[lok],2))
                    if k not in seen:
                        seen[k]=True
                        fig_map.add_trace(go.Scattergeo(lat=[leg[lk]],lon=[leg[lok]],mode="markers+text",
                            marker=dict(size=12,color="#FFFFFF",line=dict(width=2,color="#C9A84C")),
                            text=[leg[nk]],textposition="top center",textfont=dict(size=11,color="#E8C46A"),
                            showlegend=False,hovertemplate=f"<b>{leg[nk]}</b><br>{leg[fk]}<extra></extra>"))
            pad_la=max((max(all_la)-min(all_la))*.3,5); pad_lo=max((max(all_lo)-min(all_lo))*.3,8)
            fig_map.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=480,
                margin=dict(t=0,b=0,l=0,r=0),showlegend=True,
                legend=dict(bgcolor="rgba(17,34,68,.9)",font=dict(color="#D6E4F7",size=10),bordercolor="#C9A84C",borderwidth=1,x=.01,y=.99),
                geo=dict(projection_type="natural earth",showland=True,landcolor="#1C2E55",
                    showocean=True,oceancolor="#0B1629",showcoastlines=True,coastlinecolor="#3A5080",
                    showcountries=True,countrycolor="#2A4070",bgcolor="rgba(0,0,0,0)",
                    center=dict(lat=sum(all_la)/len(all_la),lon=sum(all_lo)/len(all_lo)),
                    lataxis=dict(range=[min(all_la)-pad_la,max(all_la)+pad_la]),
                    lonaxis=dict(range=[min(all_lo)-pad_lo,max(all_lo)+pad_lo])))
            st.plotly_chart(fig_map,use_container_width=True,config={"displayModeBar":False})
            st.markdown('<div class="section-header">📋 Leg Details</div>',unsafe_allow_html=True)
            lr=[{"Leg":str(i+1),"From":l["from_name"],"To":l["to_name"],"Dep.":l["dep_time"],
                 "Distance":f"{l['dist_km']:,.0f} km","Time":l["flight_time_str"],
                 f"Cost ({qr['currency']})":f"{l['cost']:,.0f}"} for i,l in enumerate(ald)]
            st.dataframe(pd.DataFrame(lr),use_container_width=True,hide_index=True)
            if qr.get("extras"):
                st.markdown('<div class="section-header">➕ Extras</div>',unsafe_allow_html=True)
                st.dataframe(pd.DataFrame([{"Service":e["name"],f"Cost ({qr['currency']})":f"{e['cost']:,.0f}"} for e in qr["extras"]]),use_container_width=True,hide_index=True)
            if qr.get("notes"):
                st.markdown(f'<div style="background:#13233F;border:1px solid #1A3A6E;border-radius:6px;padding:.7rem 1rem;font-size:.84rem;color:#D6E4F7;margin:.5rem 0"><b>Notes:</b> {qr["notes"]}</div>',unsafe_allow_html=True)
            st.markdown(f'''<div class="total-banner">
                <div style="font-size:.82rem;color:#8496B0;margin-bottom:.3rem">{qr["aircraft"]} · {qr["currency"]} {qr["rate"]:,.0f}/h</div>
                <div style="font-size:2rem;font-weight:800;color:#E8C46A">{qr["currency"]} {qr["total_cost"]:,.0f}</div>
                <div style="font-size:.85rem;color:#8496B0;margin-top:.2rem">{qr["total_dist"]:,.0f} km · {int(qr["total_min"]//60)}h {int(qr["total_min"]%60):02d}m</div>
            </div>''',unsafe_allow_html=True)
            st.markdown("<br>",unsafe_allow_html=True)
            if st.button("📄 Generate PDF Quotation",use_container_width=True,type="primary"):
                with st.spinner("Building quotation..."):
                    try:
                        st.session_state["q_pdf"]=generate_quotation_pdf(qr,q_ac)
                        st.success("✓ Quotation ready!")
                    except Exception as e: st.error(f"PDF error: {e}")
            if st.session_state.get("q_pdf"):
                st.download_button("⬇ Download Quotation PDF",data=st.session_state["q_pdf"],
                    file_name=f"Menkor_Quote_{qr['aircraft'].replace(' ','_')}.pdf",mime="application/pdf",use_container_width=True)

    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:.72rem;color:#4A5568">MENKOR AVIATION — Figures for simulation purposes only</div>',unsafe_allow_html=True)

if __name__=="__main__":
    main()
