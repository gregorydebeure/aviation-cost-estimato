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

import os
from pathlib import Path

try:
    # Platforms like Render have no native st.secrets support, only plain env vars — bridge them into
    # a secrets.toml on every startup. NOTE: we deliberately never touch st.secrets here (not even
    # st.secrets.get(...)) — accessing it before any secrets.toml exists raises
    # StreamlitSecretNotFoundError, which the except below would swallow, silently skipping the write
    # entirely and leaving every later st.secrets[...] call in the app broken. Render restarts the
    # container fresh on every deploy, so unconditionally rewriting the file on each boot is safe and
    # also keeps it in sync if env vars change. On Streamlit Community Cloud, writing is skipped because
    # ADMIN_EMAIL won't be present as a plain env var there (it's native st.secrets-only), and that
    # filesystem is read-only anyway.
    if os.environ.get("ADMIN_EMAIL"):
        _secrets_path = Path(".streamlit/secrets.toml")
        _secrets_path.parent.mkdir(exist_ok=True)
        _keys = ["STRIPE_SECRET_KEY", "STRIPE_PRICE_ESSENTIEL", "STRIPE_PRICE_PRO", "ADMIN_EMAIL", "ADMIN_PASSWORD",
                 "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "RESEND_API_KEY"]
        with open(_secrets_path, "w") as f:
            for k in _keys:
                v = os.environ.get(k, "")
                f.write(f'{k} = {v!r}\n')
except Exception:
    pass  # never let this bootstrap crash the app on any platform

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
[data-baseweb="tab"]{color:#C3D1E8!important;opacity:1!important;font-weight:500;padding-left:14px!important;padding-right:14px!important;white-space:nowrap!important;}
[data-baseweb="tab"] *{color:inherit!important;}
[data-baseweb="tab"]:hover{color:var(--amber)!important;}
[aria-selected="true"]{color:var(--amber)!important;border-bottom-color:var(--gold)!important;font-weight:700;}
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
        {"Modele":"Bombardier Global 6000","Categorie":"Ultra Long Range Jet","Couts_Fixes_Annuels":675622,"Couts_Equipe_Annuels":442000,"Cout_Horaire_Charter":4200,"Cout_Horaire_Prive":3444,"Heures_Base":350,"Taux_Charter_EUR_h":10500,"Vitesse_Croisiere_km_h":945,"Autonomie_km":11112,"Passagers_Max":17},
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

# ─── AUTH (Supabase-backed persistent user store) ────────────────────────────
def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

def _sb_base():
    url=st.secrets.get("SUPABASE_URL","").rstrip("/")
    key=st.secrets.get("SUPABASE_SERVICE_KEY","")
    return url,key

def _sb_headers():
    _,key=_sb_base()
    return {"apikey":key,"Authorization":f"Bearer {key}","Content-Type":"application/json"}

def _sb_get_user(email):
    try:
        import requests
        url,key=_sb_base()
        if not url or not key: return None
        r=requests.get(f"{url}/rest/v1/users",headers=_sb_headers(),
                        params={"email":f"eq.{email}","select":"*"},timeout=6)
        if r.status_code==200 and r.json(): return r.json()[0]
        return None
    except Exception: return None

def _sb_list_users():
    try:
        import requests
        url,key=_sb_base()
        if not url or not key: return []
        r=requests.get(f"{url}/rest/v1/users",headers=_sb_headers(),
                        params={"select":"*","order":"created_at.desc"},timeout=6)
        return r.json() if r.status_code==200 else []
    except Exception: return []

def _sb_insert_user(email,pwd_hash):
    """Returns (ok, detail) — detail is the HTTP status + Supabase's error body on failure, for debugging."""
    try:
        import requests
        url,key=_sb_base()
        if not url or not key:
            return False,"SUPABASE_URL or SUPABASE_SERVICE_KEY is missing/empty in this app's secrets."
        r=requests.post(f"{url}/rest/v1/users",headers={**_sb_headers(),"Prefer":"return=minimal"},
                         json={"email":email,"pwd_hash":pwd_hash,"stripe_cid":None,"active":False,"plan":None},timeout=6)
        if r.status_code in (200,201): return True,""
        return False,f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False,f"{type(e).__name__}: {e}"

def _sb_delete_user(email):
    try:
        import requests
        url,key=_sb_base()
        if not url or not key: return False
        r=requests.delete(f"{url}/rest/v1/users",headers={**_sb_headers(),"Prefer":"return=minimal"},
                           params={"email":f"eq.{email}"},timeout=6)
        return r.status_code in (200,204)
    except Exception: return False

def _sb_update_user(email,fields):
    try:
        import requests
        url,key=_sb_base()
        if not url or not key: return False
        r=requests.patch(f"{url}/rest/v1/users",headers={**_sb_headers(),"Prefer":"return=minimal"},
                          params={"email":f"eq.{email}"},json=fields,timeout=6)
        return r.status_code in (200,204)
    except Exception: return False

def _notify_admin_new_signup(email):
    """Best-effort: registration must never fail because of this. Returns (ok, detail) for diagnostics."""
    try:
        import requests
        key=st.secrets.get("RESEND_API_KEY"); admin=st.secrets.get("ADMIN_EMAIL")
        if not key: return False,"RESEND_API_KEY is missing/empty in this app's secrets."
        if not admin: return False,"ADMIN_EMAIL is missing/empty in this app's secrets."
        r=requests.post("https://api.resend.com/emails",
            headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
            json={"from":"Aviation Cost Estimator <onboarding@resend.dev>","to":[admin],
                  "subject":"✈ New user registered — Aviation Cost Estimator",
                  "html":f"<p>A new account was just created:</p><p style='font-size:1.1rem;font-weight:700'>{email}</p>"},
            timeout=6)
        if r.status_code in (200,201): return True,""
        return False,f"HTTP {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return False,f"{type(e).__name__}: {e}"

def _register(email,pwd):
    email=email.strip().lower()
    if not _re.match(r"[^@]+@[^@]+\.[^@]+",email): return False,"Invalid email."
    if len(pwd)<6: return False,"Password must be at least 6 characters."
    if _sb_get_user(email): return False,"Account already exists."
    ok,detail=_sb_insert_user(email,_hash(pwd))
    if not ok:
        return False,f"Could not create account — {detail}"
    _notify_admin_new_signup(email)
    return True,"Account created!"

def _login(email,pwd):
    email=email.strip().lower(); rec=_sb_get_user(email)
    if not rec or rec.get("pwd_hash")!=_hash(pwd): return False,"Incorrect email or password."
    return True,rec

PLAN_PRICE_KEYS = {"essentiel":"STRIPE_PRICE_ESSENTIEL", "pro":"STRIPE_PRICE_PRO"}
PLAN_LABELS = {"essentiel":"Essentiel — €15/month", "pro":"Pro — €50/month"}

def _check_sub(email):
    """Returns 'pro', 'essentiel', or None based on the customer's active Stripe subscription."""
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        rec=_sb_get_user(email) or {}
        cid=rec.get("stripe_cid")
        if not cid:
            custs=stripe.Customer.list(email=email,limit=1)
            if not custs.data: return None
            cid=custs.data[0].id; _sb_update_user(email,{"stripe_cid":cid})
        subs=stripe.Subscription.list(customer=cid,status="active",limit=10)
        pro_price=st.secrets.get("STRIPE_PRICE_PRO",""); ess_price=st.secrets.get("STRIPE_PRICE_ESSENTIEL","")
        plan=None
        for sub in subs.data:
            for item in sub["items"]["data"]:
                pid=item["price"]["id"]
                if pid==pro_price: plan="pro"
                elif pid==ess_price and plan!="pro": plan="essentiel"
            if plan=="pro": break
        _sb_update_user(email,{"plan":plan,"active":plan is not None})
        return plan
    except Exception: return None

def _checkout_url(email,plan="pro"):
    """Returns (url, error). error is a human-readable string on failure, never silently None without reason."""
    try:
        import stripe
    except ImportError:
        return None,"The 'stripe' package isn't installed on the server (check requirements.txt)."
    try:
        key=st.secrets.get("STRIPE_SECRET_KEY")
        if not key: return None,"STRIPE_SECRET_KEY is missing/empty in this app's secrets."
        price_key=PLAN_PRICE_KEYS.get(plan)
        price=st.secrets.get(price_key) if price_key else None
        if not price: return None,f"{price_key} is missing/empty in this app's secrets."
        stripe.api_key=key
        s=stripe.checkout.Session.create(payment_method_types=["card"],mode="subscription",
            customer_email=email,line_items=[{"price":price,"quantity":1}],metadata={"plan":plan},
            success_url=f"https://aviation-cost-estimator.onrender.com/?subscribed={plan}",
            cancel_url="https://aviation-cost-estimator.onrender.com/?cancelled=1")
        return s.url,None
    except Exception as e:
        return None,f"{type(e).__name__}: {e}"

def _market_search_checkout_url(email, meta):
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        s=stripe.checkout.Session.create(
            payment_method_types=["card"], mode="payment", customer_email=email,
            line_items=[{"price_data":{"currency":"eur","unit_amount":30000,
                "product_data":{"name":"Personalized Aircraft Market Search"}},"quantity":1}],
            metadata=meta,
            success_url="https://aviation-cost-estimator.onrender.com/?market_submitted=1",
            cancel_url="https://aviation-cost-estimator.onrender.com/?market_cancelled=1")
        return s.url
    except Exception as e:
        st.error(f"Payment error: {e}")
        return None

def _plan_buttons(email,current_plan=None):
    """Renders a subscribe button for every plan tier above the user's current one.
    Never fails silently: if Stripe checkout can't be created, shows the real error instead of nothing."""
    if current_plan not in ("essentiel","pro"):
        url,err=_checkout_url(email,"essentiel")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.5rem"><a href="{url}" target="_blank" style="display:block;background:#1A3A6E;color:#D6E4F7;border:1px solid #8496B0;padding:.5rem 1.2rem;border-radius:5px;font-weight:600;text-decoration:none">Essentiel — 15€/month</a></div>', unsafe_allow_html=True)
        else: st.error(f"Essentiel checkout unavailable: {err}")
    if current_plan!="pro":
        url,err=_checkout_url(email,"pro")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.5rem"><a href="{url}" target="_blank" style="display:block;background:#C9A84C;color:#0B1629;padding:.5rem 1.2rem;border-radius:5px;font-weight:700;text-decoration:none">⭐ {"Upgrade to Pro" if current_plan=="essentiel" else "Pro"} — 50€/month</a></div>', unsafe_allow_html=True)
        else: st.error(f"Pro checkout unavailable: {err}")

def render_auth():
    for k,v in [("auth_email",None),("auth_plan",None),("auth_is_admin",False)]:
        if k not in st.session_state: st.session_state[k]=v
    email=st.session_state["auth_email"]; is_admin=st.session_state["auth_is_admin"]
    with st.sidebar:
        st.markdown("---")
        if email:
            if is_admin:
                st.markdown('<div style="font-size:.78rem;color:#F59E0B;font-weight:700">👑 ADMIN</div>', unsafe_allow_html=True)
                with st.expander("👥 Users",expanded=True):
                    users=_sb_list_users()
                    if not users:
                        st.caption("No users yet, or Supabase isn't configured (SUPABASE_URL / SUPABASE_SERVICE_KEY).")
                    for ud in users:
                        ue=ud.get("email",""); p=ud.get("plan")
                        col="#4ADE80" if p=="pro" else ("#60A5FA" if p=="essentiel" else "#F87171")
                        lbl={"pro":"Pro","essentiel":"Essentiel"}.get(p,"✗")
                        st.markdown(f'<div style="font-size:.75rem;border-bottom:1px solid #1A3A6E;padding:2px 0"><b>{ue}</b> <span style="color:{col}">{lbl}</span></div>', unsafe_allow_html=True)
                    if st.button("🔄 Refresh",key="admin_ref",width="stretch"):
                        for ud in users: _check_sub(ud.get("email",""))
                        st.rerun()
                with st.expander("🩺 Supabase diagnostics"):
                    _u,_k=_sb_base()
                    st.caption(f"SUPABASE_URL: {'✓ set — ' + _u if _u else '✗ missing'}")
                    st.caption(f"SUPABASE_SERVICE_KEY: {'✓ set (' + str(len(_k)) + ' chars)' if _k else '✗ missing'}")
                    if st.button("Test connection",key="sb_test",width="stretch"):
                        _diag_email=f"__diag_{int(__import__('time').time())}@test.invalid"
                        ok,detail=_sb_insert_user(_diag_email,"x")
                        if ok:
                            _sb_delete_user(_diag_email)
                            st.success("✓ Supabase accepted a test write. Storage is working.")
                        else: st.error(detail)
                with st.expander("🩺 Email notification diagnostics"):
                    _rk=st.secrets.get("RESEND_API_KEY",""); _ae=st.secrets.get("ADMIN_EMAIL","")
                    st.caption(f"RESEND_API_KEY: {'✓ set (' + str(len(_rk)) + ' chars)' if _rk else '✗ missing'}")
                    st.caption(f"ADMIN_EMAIL (recipient): {_ae if _ae else '✗ missing'}")
                    if st.button("Send test email",key="resend_test",width="stretch"):
                        ok,detail=_notify_admin_new_signup("diagnostic-test@menkor-aviation.test")
                        if ok: st.success(f"✓ Email sent to {_ae}. Check your inbox (and spam folder).")
                        else: st.error(detail)
                with st.expander("🩺 Stripe checkout diagnostics"):
                    _sk=st.secrets.get("STRIPE_SECRET_KEY",""); _pe=st.secrets.get("STRIPE_PRICE_ESSENTIEL",""); _pp=st.secrets.get("STRIPE_PRICE_PRO","")
                    st.caption(f"STRIPE_SECRET_KEY: {'✓ set (' + str(len(_sk)) + ' chars)' if _sk else '✗ missing'}")
                    st.caption(f"STRIPE_PRICE_ESSENTIEL: {'✓ ' + _pe if _pe else '✗ missing'}")
                    st.caption(f"STRIPE_PRICE_PRO: {'✓ ' + _pp if _pp else '✗ missing'}")
                    if st.button("Test Essentiel checkout link",key="stripe_test_ess",width="stretch"):
                        url,err=_checkout_url("diagnostic-test@menkor-aviation.test","essentiel")
                        if url: st.success(f"✓ Checkout link created: {url}")
                        else: st.error(err)
                    if st.button("Test Pro checkout link",key="stripe_test_pro",width="stretch"):
                        url,err=_checkout_url("diagnostic-test@menkor-aviation.test","pro")
                        if url: st.success(f"✓ Checkout link created: {url}")
                        else: st.error(err)
            else:
                st.markdown(f'<div style="font-size:.78rem;color:#4ADE80">✓ {email}</div>', unsafe_allow_html=True)
                plan=st.session_state["auth_plan"]
                if plan=="pro":
                    st.markdown('<div style="font-size:.72rem;color:#C9A84C">⭐ Pro plan</div>', unsafe_allow_html=True)
                elif plan=="essentiel":
                    st.markdown('<div style="font-size:.72rem;color:#60A5FA;margin-bottom:.4rem">✓ Essentiel plan</div>', unsafe_allow_html=True)
                    _plan_buttons(email,current_plan="essentiel")
                else:
                    st.markdown('<div style="font-size:.72rem;color:#F87171;margin-bottom:.4rem">⚠ No subscription</div>', unsafe_allow_html=True)
                    _plan_buttons(email,current_plan=None)
                if st.button("🔄 Check subscription",key="chk_sub",width="stretch"):
                    st.session_state["auth_plan"]=_check_sub(email); st.rerun()
            if st.button("🚪 Log out",key="logout",width="stretch"):
                st.session_state["auth_email"]=None; st.session_state["auth_plan"]=None
                st.session_state["auth_is_admin"]=False; st.rerun()
        else:
            st.markdown('<div class="section-header">🔐 Account</div>', unsafe_allow_html=True)
            view=st.radio("Account",["Login","Register"],horizontal=True,key="auth_view",label_visibility="collapsed")
            if view=="Login":
                em=st.text_input("Email",key="li_em",placeholder="your@email.com")
                pw=st.text_input("Password",key="li_pw",type="password")
                if st.button("Login",key="btn_login",width="stretch"):
                    if em and pw:
                        try: ae=st.secrets.get("ADMIN_EMAIL",""); ap=st.secrets.get("ADMIN_PASSWORD","")
                        except: ae=ap=""
                        if em.strip().lower()==ae.lower() and pw==ap:
                            st.session_state["auth_email"]=em.strip().lower()
                            st.session_state["auth_plan"]="pro"; st.session_state["auth_is_admin"]=True; st.rerun()
                        else:
                            ok,res=_login(em,pw)
                            if ok:
                                st.session_state["auth_email"]=em.strip().lower()
                                st.session_state["auth_plan"]=_check_sub(em.strip().lower())
                                st.session_state["auth_is_admin"]=False; st.rerun()
                            else: st.error(res)
                    else: st.warning("Fill in all fields.")
            else:
                em=st.text_input("Email",key="rg_em",placeholder="your@email.com")
                pw=st.text_input("Password (min 6)",key="rg_pw",type="password",
                                  help="Click the eye icon to verify what you typed before creating the account.")
                if st.button("Create account",key="btn_reg",width="stretch"):
                    if em and pw:
                        ok,msg=_register(em,pw)
                        if ok: st.success(msg); _plan_buttons(em.strip().lower(),current_plan=None)
                        else: st.error(msg)
                    else: st.warning("Fill in all fields.")
            st.markdown('<div style="font-size:.7rem;color:#8496B0;text-align:center;margin-top:.4rem">Dashboard free · Essentiel 15€/mo · Pro 50€/mo</div>', unsafe_allow_html=True)
    plan=st.session_state.get("auth_plan")
    return plan in ("essentiel","pro"), plan=="pro"

def premium_gate(required="pro"):
    email=st.session_state.get("auth_email")
    req_label="Pro" if required=="pro" else "Essentiel"
    price_label=PLAN_LABELS.get(required,"")
    st.markdown(f"""<div style="background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
         border:1px solid #C9A84C;border-radius:12px;padding:2.5rem;text-align:center;margin:2rem 0 1rem 0">
        <div style="font-size:2rem;margin-bottom:.8rem">🔒</div>
        <div style="font-size:1.3rem;font-weight:700;color:#E8C46A;margin-bottom:.5rem">{req_label} Feature</div>
        <div style="font-size:.9rem;color:#8496B0;margin-bottom:.2rem">This section requires the <b style="color:#C9A84C">{price_label}</b> plan.</div>
    </div>""", unsafe_allow_html=True)

    def _cell(included,is_current_col):
        mark='<span style="color:#4ADE80;font-weight:700">✓</span>' if included else '<span style="color:#4A5568">—</span>'
        bg="background:rgba(201,168,76,.10);" if is_current_col else ""
        return f'<td style="text-align:center;padding:.5rem .4rem;{bg}">{mark}</td>'

    rows=[("Dashboard",True,True,True),("Profitability",False,True,True),
          ("Sensitivity",False,True,True),("Cost Master",False,False,True),
          ("Quotation",False,False,True),("Market Search",True,True,True)]
    body="".join(
        f'<tr><td style="padding:.5rem .6rem;color:#D6E4F7;font-size:.82rem;'
        + ('font-weight:700;color:#E8C46A;' if name in ("Cost Master","Quotation","Profitability","Sensitivity") and
             ((required=="essentiel" and name in ("Profitability","Sensitivity")) or (required=="pro" and name in ("Cost Master","Quotation"))) else '')
        + f'">{name}</td>{_cell(free_,False)}{_cell(ess_,required=="essentiel")}{_cell(pro_,required=="pro")}</tr>'
        for name,free_,ess_,pro_ in rows
    )
    st.markdown(f"""<table style="width:100%;border-collapse:collapse;background:#13233F;border:1px solid #1A3A6E;border-radius:6px;margin-bottom:1.5rem">
        <thead><tr style="border-bottom:1px solid #1A3A6E">
            <th style="text-align:left;padding:.5rem .6rem;font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:#8496B0">Feature</th>
            <th style="padding:.5rem .4rem;font-size:.7rem;color:#8496B0">Free</th>
            <th style="padding:.5rem .4rem;font-size:.7rem;color:#8496B0">Essentiel<br>15€/mo</th>
            <th style="padding:.5rem .4rem;font-size:.7rem;color:#8496B0">Pro<br>50€/mo</th>
        </tr></thead>
        <tbody>{body}</tbody>
    </table>""", unsafe_allow_html=True)

    if not email: st.info("👈 Create a free account in the sidebar.")
    else: _plan_buttons(email,current_plan=st.session_state.get("auth_plan"))

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    for k,v in [("database",None),("cost_master",None),("pdf_report",None),
                ("auth_email",None),("auth_plan",None),("auth_is_admin",False),
                ("q_legs",[{"from":"","to":"","dep_time":"08:00"}]),
                ("q_result",None),("q_pdf",None)]:
        if k not in st.session_state: st.session_state[k]=v

    is_essentiel,is_pro=render_auth()

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

    def _tab_label(base,required):
        if required is None: return base
        unlocked = is_pro or (required=="essentiel" and is_essentiel)
        if unlocked: return base
        return f"{base}  🔒 {'15€/mo' if required=='essentiel' else '50€/mo'}"

    tab1,tab2,tab3,tab4,tab5,tab6=st.tabs([
        _tab_label("📊 Dashboard",None),
        _tab_label("📈 Profitability","essentiel"),
        _tab_label("🔍 Sensitivity","essentiel"),
        _tab_label("💼 Cost Master","pro"),
        _tab_label("✈️ Quotation","pro"),
        _tab_label("🌐 Market Search",None),
    ])

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
            st.plotly_chart(chart_donut(costs),width="stretch",config={"displayModeBar":False})
        with g2:
            st.markdown('<div class="section-header">Cost by Flight Mode</div>',unsafe_allow_html=True)
            st.plotly_chart(chart_bars(costs),width="stretch",config={"displayModeBar":False})

    # TAB 2: PROFITABILITY
    with tab2:
        if not is_essentiel: premium_gate("essentiel"); st.stop()
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
            st.plotly_chart(chart_waterfall(costs,prof),width="stretch",config={"displayModeBar":False})

    # TAB 3: SENSITIVITY
    with tab3:
        if not is_essentiel: premium_gate("essentiel"); st.stop()
        st.markdown('<div class="section-header">Sensitivity — Charter Hours vs Net Result</div>',unsafe_allow_html=True)
        st.caption(f"Private: {h_private}h | Commission: {commission_pct}% | Rate: € {custom_rate:,.0f}/h")
        st.plotly_chart(chart_sensitivity(aircraft,h_private,commission_pct,custom_rate),width="stretch",config={"displayModeBar":False})
        st.markdown('<div class="section-header">Fleet Comparison</div>',unsafe_allow_html=True)
        comp=[{"Model":row["Modele"],"Total Cost (€)":round(calculate_costs(row,h_charter,h_private)["grand_total"]),
               "Cost/Hour (€)":round(calculate_costs(row,h_charter,h_private)["avg_cost_h"])} for _,row in df.iterrows()]
        df_c=pd.DataFrame(comp).sort_values("Total Cost (€)")
        fig_c=px.bar(df_c,x="Model",y="Total Cost (€)",color="Cost/Hour (€)",
                     color_continuous_scale=["#1A3A6E","#4A90D9","#C9A84C","#E8C46A"],template="plotly_dark")
        fig_c.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#D6E4F7"),height=350,margin=dict(t=10,b=80,l=10,r=10),
                            xaxis=dict(tickangle=-30),yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f"))
        st.plotly_chart(fig_c,width="stretch",config={"displayModeBar":False})

    # TAB 4: COST MASTER
    with tab4:
        if not is_pro: premium_gate("pro"); st.stop()
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
        if st.button("🚀 Generate Financial Analysis",width="stretch"):
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
            with d1: st.plotly_chart(cm_global_donut(op_a2,dir_a,ind_a),width="stretch",config={"displayModeBar":False})
            with d2: st.plotly_chart(cm_waterfall(op_a2,dir_a,ind_a,gross,cm["commission_pct"]),width="stretch",config={"displayModeBar":False})
            b1,b2,b3=st.columns(3)
            with b1: st.plotly_chart(cm_donut(list(cm["op_vals"].keys()),[v*cm["annual_flights"] for v in cm["op_vals"].values()],["#60A5FA","#3B82F6","#1D4ED8","#93C5FD","#BFDBFE","#2563EB","#1E40AF","#DBEAFE"],"Operational"),width="stretch",config={"displayModeBar":False})
            with b2: st.plotly_chart(cm_donut(list(cm["dir_vals"].keys()),list(cm["dir_vals"].values()),["#F59E0B","#D97706","#B45309","#FCD34D","#FDE68A","#92400E","#FBBF24","#FEF3C7","#78350F"],"Direct"),width="stretch",config={"displayModeBar":False})
            with b3: st.plotly_chart(cm_donut(list(cm["ind_vals"].keys()),list(cm["ind_vals"].values()),["#A78BFA","#8B5CF6","#7C3AED","#C4B5FD","#DDD6FE","#6D28D9","#5B21B6","#EDE9FE","#4C1D95"],"Crew"),width="stretch",config={"displayModeBar":False})
            st.markdown("<hr>",unsafe_allow_html=True)
            bb1,bb2,bb3=st.columns(3)
            with bb1: st.plotly_chart(cm_bar(list(cm["op_vals"].keys()),[v*cm["annual_flights"] for v in cm["op_vals"].values()],"#60A5FA","Operational"),width="stretch",config={"displayModeBar":False})
            with bb2: st.plotly_chart(cm_bar(list(cm["dir_vals"].keys()),list(cm["dir_vals"].values()),"#F59E0B","Direct"),width="stretch",config={"displayModeBar":False})
            with bb3: st.plotly_chart(cm_bar(list(cm["ind_vals"].keys()),list(cm["ind_vals"].values()),"#A78BFA","Crew"),width="stretch",config={"displayModeBar":False})
            st.markdown("<hr>",unsafe_allow_html=True)
            rows2=[]
            for k,v in cm["op_vals"].items(): rows2.append({"Category":"Operational","Line":k,"Annual (€)":f"€ {v*cm['annual_flights']:,.0f}","% Total":f"{v*cm['annual_flights']/grand*100:.1f}%"})
            for k,v in cm["dir_vals"].items(): rows2.append({"Category":"Direct","Line":k,"Annual (€)":f"€ {v:,.0f}","% Total":f"{v/grand*100:.1f}%"})
            for k,v in cm["ind_vals"].items(): rows2.append({"Category":"Crew","Line":k,"Annual (€)":f"€ {v:,.0f}","% Total":f"{v/grand*100:.1f}%"})
            st.dataframe(pd.DataFrame(rows2),width="stretch",hide_index=True)
            if st.button("📄 Generate PDF Report",width="stretch",type="primary"):
                with st.spinner("Building report..."):
                    try:
                        st.session_state["pdf_report"]=generate_pdf_report(cm,aircraft,annual_flights)
                        st.success("✓ Report ready!")
                    except Exception as e: st.error(f"PDF error: {e}")
            if st.session_state.get("pdf_report"):
                st.download_button("⬇ Download PDF Report",data=st.session_state["pdf_report"],
                    file_name=f"Menkor_Cost_{aircraft['Modele'].replace(' ','_')}.pdf",mime="application/pdf",width="stretch")


    # ── TAB 5 : QUOTATION ───────────────────────────────────────────────
    with tab5:
        if not is_pro:
            premium_gate("pro")
            st.stop()
        st.markdown("""
        <div style="background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
             border:1px solid #C9A84C;border-radius:12px;padding:3rem 2rem;
             text-align:center;margin:2rem 0">
            <div style="font-size:3rem;margin-bottom:1rem">✈️</div>
            <div style="font-size:1.6rem;font-weight:700;color:#E8C46A;margin-bottom:.8rem">
                Charter Flight Quotation
            </div>
            <div style="font-size:.95rem;color:#8496B0;margin-bottom:2rem;line-height:1.6">
                Generate a professional charter quotation with interactive route map,<br>
                extras & services, and a branded Menkor Aviation PDF.
            </div>
            <div style="font-size:.82rem;color:#D6E4F7;margin-bottom:2rem">
                ✓ ICAO / IATA airport lookup &nbsp;·&nbsp;
                ✓ Multi-leg routes &nbsp;·&nbsp;
                ✓ Catering & crew extras &nbsp;·&nbsp;
                ✓ PDF with route map
            </div>
            <a href="https://menkor-quotation-9nff8mo2pbyf8vddbsucvm.streamlit.app/"
               target="_blank"
               style="background:#C9A84C;color:#0B1629;padding:.8rem 2.5rem;
                      border-radius:6px;font-weight:700;text-decoration:none;
                      font-size:1.05rem;letter-spacing:.04em">
                ✈️ Open Quotation Tool
            </a>
            <div style="font-size:.75rem;color:#8496B0;margin-top:1.2rem">
                Opens in a new tab
            </div>
        </div>""", unsafe_allow_html=True)

    # ── TAB 6 : MARKET SEARCH ───────────────────────────────────────────
    with tab6:
        st.markdown('<div class="main-title" style="font-size:1.4rem">🌐 Personalized Aircraft Market Search</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Every active listing for your chosen model, consolidated and verified by our team</div>',unsafe_allow_html=True)

        ms_cats=["All"]+sorted(df["Categorie"].dropna().unique().tolist())
        msc1,msc2=st.columns(2)
        with msc1: ms_cat=st.selectbox("Category",ms_cats,key="ms_cat")
        df_ms=df if ms_cat=="All" else df[df["Categorie"]==ms_cat]
        with msc2: ms_model_preview=st.selectbox("Aircraft model",df_ms["Modele"].tolist(),key="ms_model_preview")

        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown(f'<div class="section-header">📋 Sample Report Preview — {ms_model_preview}</div>',unsafe_allow_html=True)
        st.caption("Illustrative data only — not real listings. Your paid report replaces every row below with verified, current market listings for this exact model.")

        _sample_listings=[
            dict(year=2016,reg="N-XXXX",hours="1,850 h",price="$18.5M",location="USA · Teterboro",
                 maint="JSSI Enrolled",maint_color="#4ADE80",broker="Atlantic Aviation Brokers"),
            dict(year=2014,reg="VP-XXXX",hours="2,400 h",price="$15.9M",location="UK · London",
                 maint="OEM Program",maint_color="#60A5FA",broker="EuroCharter Sales"),
            dict(year=2018,reg="M-XXXX",hours="1,100 h",price="$21.2M",location="UAE · Dubai",
                 maint="JSSI Enrolled",maint_color="#4ADE80",broker="Gulf Jet Partners"),
            dict(year=2012,reg="HB-XXXX",hours="3,650 h",price="$12.4M",location="Switzerland · Geneva",
                 maint="Not Enrolled",maint_color="#F87171",broker="Alpine Aircraft Sales"),
        ]

        for lst in _sample_listings:
            st.markdown(f'''<div class="metric-card" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1rem">
                <div style="min-width:170px">
                    <div style="font-size:1.05rem;font-weight:700;color:#E8C46A">{ms_model_preview} · {lst["year"]}</div>
                    <div style="font-size:.78rem;color:#8496B0">Reg. {lst["reg"]} · {lst["location"]}</div>
                </div>
                <div style="text-align:center;min-width:90px">
                    <div class="metric-label" style="margin-bottom:.1rem">Hours</div>
                    <div style="font-size:.95rem;color:#D6E4F7;font-weight:600">{lst["hours"]}</div>
                </div>
                <div style="text-align:center;min-width:90px">
                    <div class="metric-label" style="margin-bottom:.1rem">Price</div>
                    <div style="font-size:.95rem;color:#D6E4F7;font-weight:600">{lst["price"]}</div>
                </div>
                <div style="text-align:center;min-width:120px">
                    <span style="background:{lst["maint_color"]}22;color:{lst["maint_color"]};padding:3px 10px;border-radius:12px;font-size:.72rem;font-weight:700">{lst["maint"]}</span>
                </div>
                <div style="text-align:right;min-width:170px">
                    <div style="font-size:.72rem;color:#8496B0">Seller broker</div>
                    <div style="font-size:.82rem;color:#5A6B85;filter:blur(3px);user-select:none">{lst["broker"]}</div>
                </div>
            </div>''',unsafe_allow_html=True)

        st.markdown('''<div style="text-align:center;font-size:.78rem;color:#8496B0;margin:.4rem 0 1.2rem 0">
            🔒 Broker names, direct contacts, and exact tail numbers are unlocked in your personalized report
        </div>''',unsafe_allow_html=True)

        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown('<div class="section-header">What You Get — € 300 Flat Fee</div>',unsafe_allow_html=True)
        f1,f2,f3=st.columns(3)
        with f1:
            st.markdown('''<div class="metric-card">
                <div class="metric-label">✓ Full Listing Set</div>
                <div class="metric-sub">Every active listing currently on and off market for your exact model, cross-checked against our broker network — not just public ads.</div>
            </div>''',unsafe_allow_html=True)
        with f2:
            st.markdown('''<div class="metric-card">
                <div class="metric-label">✓ Verified Seller Contacts</div>
                <div class="metric-sub">Direct broker name, email and phone routing for each listing, so you skip the blind-inquiry queue.</div>
            </div>''',unsafe_allow_html=True)
        with f3:
            st.markdown('''<div class="metric-card">
                <div class="metric-label">✓ Market Positioning</div>
                <div class="metric-sub">Where each asking price sits versus comparable trades, plus maintenance program status (enrolled programs noted, no third-party pricing disclosed).</div>
            </div>''',unsafe_allow_html=True)
        st.caption("Flat fee ensures every request is a serious inquiry, not a time-waster or competitor fishing for free data. Delivered within 48 hours by our team, by email.")

        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown('<div class="section-header">Request Your Market Search</div>',unsafe_allow_html=True)

        with st.form("market_search_form"):
            _ms_models=df["Modele"].tolist()
            _ms_default_idx=_ms_models.index(ms_model_preview) if ms_model_preview in _ms_models else 0
            ms_model = st.selectbox("Aircraft model you're interested in", _ms_models, index=_ms_default_idx)
            c1,c2 = st.columns(2)
            with c1: ms_budget = st.text_input("Budget (approximate, e.g. $15M-$20M)")
            with c2: ms_year = st.text_input("Year range (e.g. 2014-2020)")
            c3,c4 = st.columns(2)
            with c3: ms_hours = st.text_input("Max total hours (optional)")
            with c4: ms_location = st.text_input("Preferred location/region (optional)")
            ms_name = st.text_input("Your name")
            ms_email = st.text_input("Your email")
            ms_notes = st.text_area("Additional criteria (optional)")
            submitted = st.form_submit_button("Proceed to Payment — € 300", width="stretch")

        if submitted:
            if not (ms_name and ms_email and ms_budget):
                st.warning("Please fill in at least name, email, and budget.")
            else:
                meta = {"aircraft_model":ms_model,"budget":ms_budget,"year_range":ms_year,
                        "max_hours":ms_hours,"location":ms_location,"client_name":ms_name,"notes":ms_notes[:450]}
                url = _market_search_checkout_url(ms_email, meta)
                if url:
                    st.markdown(f'<div style="text-align:center;margin-top:.8rem"><a href="{url}" target="_blank" style="background:#C9A84C;color:#0B1629;padding:.6rem 1.5rem;border-radius:5px;font-weight:700;text-decoration:none">💳 Pay € 300 and Submit Request</a></div>', unsafe_allow_html=True)
                    st.info("After payment, our team will prepare your personalized market report within 48 hours and send it to your email.")

    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown('<div style="text-align:center;font-size:.72rem;color:#4A5568">MENKOR AVIATION — Figures for simulation purposes only</div>',unsafe_allow_html=True)

if __name__=="__main__":
    main()
