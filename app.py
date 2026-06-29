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
    .stApp { background-color: var(--navy) !important; color: var(--light) !important; font-family: 'Segoe UI', system-ui, sans-serif; }
    [data-testid="stSidebar"] { background-color: var(--deep) !important; border-right: 1px solid var(--mid); }
    [data-testid="stSidebar"] * { color: var(--light) !important; }
    .main-title { font-size: 2rem; font-weight: 700; letter-spacing: 0.08em; color: var(--amber); text-transform: uppercase; margin-bottom: 0.1rem; }
    .sub-title { font-size: 0.85rem; color: var(--slate); letter-spacing: 0.12em; text-transform: uppercase; margin-bottom: 1.5rem; }
    .metric-card { background: var(--card); border: 1px solid var(--mid); border-left: 3px solid var(--gold); border-radius: 6px; padding: 1rem 1.2rem; margin-bottom: 0.8rem; }
    .metric-label { font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--slate); margin-bottom: 0.3rem; }
    .metric-value { font-size: 1.7rem; font-weight: 700; color: var(--amber); }
    .metric-sub   { font-size: 0.78rem; color: var(--slate); margin-top: 0.1rem; }
    .section-header { font-size: 0.7rem; letter-spacing: 0.18em; text-transform: uppercase; color: var(--gold); border-bottom: 1px solid var(--mid); padding-bottom: 0.4rem; margin: 1.2rem 0 0.8rem 0; }
    .cat-header { font-size: 0.78rem; letter-spacing: 0.14em; text-transform: uppercase; color: var(--amber); background: var(--mid); border-radius: 4px; padding: 0.4rem 0.8rem; margin: 1rem 0 0.5rem 0; display: inline-block; }
    hr { border-color: var(--mid) !important; }
    .stSelectbox label, .stSlider label, .stNumberInput label, .stFileUploader label { color: var(--light) !important; font-size: 0.82rem; }
    [data-testid="stMetricValue"] { color: var(--amber) !important; font-size: 1.5rem !important; }
    [data-testid="stMetricLabel"] { color: var(--slate) !important; font-size: 0.72rem !important; letter-spacing: 0.1em; }
    [data-testid="stMetricDelta"] { color: #4ADE80 !important; }
    .stAlert { background-color: var(--card) !important; border-color: var(--mid) !important; }
    .stButton > button { background: var(--mid) !important; color: var(--amber) !important; border: 1px solid var(--gold) !important; border-radius: 4px; letter-spacing: 0.06em; font-weight: 600; }
    .stButton > button:hover { background: var(--gold) !important; color: var(--navy) !important; }
    .stDataFrame { border: 1px solid var(--mid); border-radius: 6px; }
    [data-baseweb="tab-list"] { background: var(--card); border-radius: 6px; }
    [data-baseweb="tab"] { color: var(--slate) !important; }
    [aria-selected="true"] { color: var(--amber) !important; border-bottom-color: var(--gold) !important; }
    [data-testid="stExpander"] { background: var(--card); border: 1px solid var(--mid); border-radius: 6px; }
    .tag-ok   { background:#163A2A; color:#4ADE80; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-warn { background:#3A2A10; color:#FBBF24; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .tag-err  { background:#3A1010; color:#F87171; padding:2px 8px; border-radius:3px; font-size:0.75rem; }
    .pdf-drop-zone { border: 2px dashed var(--mid); border-radius: 8px; padding: 2rem; text-align: center; color: var(--slate); background: var(--card); margin: 1rem 0; }
    .extracted-card { background: var(--card); border: 1px solid var(--mid); border-left: 3px solid var(--greentext); border-radius: 6px; padding: 1rem 1.2rem; margin: 0.5rem 0; }
    .extracted-label { font-size: 0.7rem; letter-spacing: 0.1em; text-transform: uppercase; color: var(--slate); }
    .extracted-value { font-size: 1.1rem; font-weight: 600; color: var(--greentext); }
    .step-badge { display: inline-block; background: var(--mid); color: var(--amber); border-radius: 50%; width: 24px; height: 24px; text-align: center; line-height: 24px; font-size: 0.75rem; font-weight: 700; margin-right: 0.5rem; }
    .cost-group-card { background: var(--card); border: 1px solid var(--mid); border-radius: 8px; padding: 1.2rem 1.4rem; margin-bottom: 1rem; }
    .cost-group-title { font-size: 0.8rem; letter-spacing: 0.15em; text-transform: uppercase; font-weight: 700; margin-bottom: 0.8rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--mid); }
    .cg-operational { color: #60A5FA; border-left: 3px solid #60A5FA; }
    .cg-direct { color: #F59E0B; border-left: 3px solid #F59E0B; }
    .cg-indirect { color: #A78BFA; border-left: 3px solid #A78BFA; }
    .total-banner { background: linear-gradient(135deg, #112244 0%, #1A3A6E 100%); border: 1px solid var(--gold); border-radius: 8px; padding: 1.5rem; text-align: center; margin: 1.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ─── SESSION STATE ───────────────────────────────────────────────────────────
for key, val in [("database", None), ("extracted", None), ("cost_master", None)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─── DEFAULT DATASET ────────────────────────────────────────────────────────
def get_default_data() -> pd.DataFrame:
    """Menkor Aviation GBL — 46 aircraft database v6."""
    data = [
        {"Modele": "Airbus 318", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 219176, "Couts_Equipe_Annuels": 450113, "Cout_Horaire_Charter": 4481, "Cout_Horaire_Prive": 3674, "Heures_Base": 350, "Taux_Charter_EUR_h": 6500, "Vitesse_Croisiere_km_h": 869, "Autonomie_km": 6862, "Passagers_Max": 19},
        {"Modele": "Airbus 319", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 225763, "Couts_Equipe_Annuels": 450113, "Cout_Horaire_Charter": 4338, "Cout_Horaire_Prive": 3557, "Heures_Base": 350, "Taux_Charter_EUR_h": 7000, "Vitesse_Croisiere_km_h": 869, "Autonomie_km": 11014, "Passagers_Max": 19},
        {"Modele": "Airbus 320", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 253951, "Couts_Equipe_Annuels": 361286, "Cout_Horaire_Charter": 5000, "Cout_Horaire_Prive": 4100, "Heures_Base": 100, "Taux_Charter_EUR_h": 8500, "Vitesse_Croisiere_km_h": 869, "Autonomie_km": 8938, "Passagers_Max": 150},
        {"Modele": "Airbus 321", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 277688, "Couts_Equipe_Annuels": 450113, "Cout_Horaire_Charter": 5331, "Cout_Horaire_Prive": 4371, "Heures_Base": 350, "Taux_Charter_EUR_h": 9000, "Vitesse_Croisiere_km_h": 822, "Autonomie_km": 8288, "Passagers_Max": 19},
        {"Modele": "Airbus 340", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 360066, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 11019, "Cout_Horaire_Prive": 9036, "Heures_Base": 100, "Taux_Charter_EUR_h": 28000, "Vitesse_Croisiere_km_h": 835, "Autonomie_km": 12640, "Passagers_Max": 400},
        {"Modele": "Airbus ACJ319neo", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 279335, "Couts_Equipe_Annuels": 376048, "Cout_Horaire_Charter": 3817, "Cout_Horaire_Prive": 3130, "Heures_Base": 350, "Taux_Charter_EUR_h": 9500, "Vitesse_Croisiere_km_h": 869, "Autonomie_km": 12501, "Passagers_Max": 19},
        {"Modele": "Airbus ACJ320neo", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 310659, "Couts_Equipe_Annuels": 376048, "Cout_Horaire_Charter": 3833, "Cout_Horaire_Prive": 3143, "Heures_Base": 350, "Taux_Charter_EUR_h": 10000, "Vitesse_Croisiere_km_h": 869, "Autonomie_km": 11299, "Passagers_Max": 19},
        {"Modele": "BAE RJ-70", "Categorie": "Regional Jet / VIP", "Couts_Fixes_Annuels": 222678, "Couts_Equipe_Annuels": 372857, "Cout_Horaire_Charter": 4357, "Cout_Horaire_Prive": 3573, "Heures_Base": 100, "Taux_Charter_EUR_h": 4500, "Vitesse_Croisiere_km_h": 755, "Autonomie_km": 3250, "Passagers_Max": 20},
        {"Modele": "BAE RJ-85", "Categorie": "Regional Jet / VIP", "Couts_Fixes_Annuels": 271095, "Couts_Equipe_Annuels": 372857, "Cout_Horaire_Charter": 4033, "Cout_Horaire_Prive": 3307, "Heures_Base": 100, "Taux_Charter_EUR_h": 4800, "Vitesse_Croisiere_km_h": 755, "Autonomie_km": 3366, "Passagers_Max": 20},
        {"Modele": "Beechcraft Beechjet 400", "Categorie": "Light Jet", "Couts_Fixes_Annuels": 34901, "Couts_Equipe_Annuels": 245619, "Cout_Horaire_Charter": 1823, "Cout_Horaire_Prive": 1495, "Heures_Base": 250, "Taux_Charter_EUR_h": 2200, "Vitesse_Croisiere_km_h": 826, "Autonomie_km": 2061, "Passagers_Max": 7},
        {"Modele": "Beechcraft Beechjet 400A", "Categorie": "Light Jet", "Couts_Fixes_Annuels": 36260, "Couts_Equipe_Annuels": 245619, "Cout_Horaire_Charter": 1568, "Cout_Horaire_Prive": 1286, "Heures_Base": 250, "Taux_Charter_EUR_h": 2300, "Vitesse_Croisiere_km_h": 832, "Autonomie_km": 2133, "Passagers_Max": 7},
        {"Modele": "Beechcraft Premier I", "Categorie": "Light Jet", "Couts_Fixes_Annuels": 35998, "Couts_Equipe_Annuels": 136880, "Cout_Horaire_Charter": 1254, "Cout_Horaire_Prive": 1028, "Heures_Base": 250, "Taux_Charter_EUR_h": 1800, "Vitesse_Croisiere_km_h": 789, "Autonomie_km": 1536, "Passagers_Max": 7},
        {"Modele": "Beechcraft Premier IA", "Categorie": "Light Jet", "Couts_Fixes_Annuels": 41947, "Couts_Equipe_Annuels": 136880, "Cout_Horaire_Charter": 1236, "Cout_Horaire_Prive": 1013, "Heures_Base": 250, "Taux_Charter_EUR_h": 1900, "Vitesse_Croisiere_km_h": 789, "Autonomie_km": 1536, "Passagers_Max": 7},
        {"Modele": "Boeing 737-500", "Categorie": "VIP Airliner / BBJ", "Couts_Fixes_Annuels": 242553, "Couts_Equipe_Annuels": 419143, "Cout_Horaire_Charter": 5456, "Cout_Horaire_Prive": 4474, "Heures_Base": 100, "Taux_Charter_EUR_h": 7500, "Vitesse_Croisiere_km_h": 839, "Autonomie_km": 5424, "Passagers_Max": 150},
        {"Modele": "Boeing 737-600", "Categorie": "VIP Airliner / BBJ", "Couts_Fixes_Annuels": 231007, "Couts_Equipe_Annuels": 419143, "Cout_Horaire_Charter": 4544, "Cout_Horaire_Prive": 3726, "Heures_Base": 100, "Taux_Charter_EUR_h": 7800, "Vitesse_Croisiere_km_h": 837, "Autonomie_km": 7073, "Passagers_Max": 119},
        {"Modele": "Boeing 737-700", "Categorie": "VIP Airliner / BBJ", "Couts_Fixes_Annuels": 225028, "Couts_Equipe_Annuels": 419143, "Cout_Horaire_Charter": 4669, "Cout_Horaire_Prive": 3829, "Heures_Base": 100, "Taux_Charter_EUR_h": 8000, "Vitesse_Croisiere_km_h": 838, "Autonomie_km": 7226, "Passagers_Max": 140},
        {"Modele": "Boeing 747-100", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 273066, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 19415, "Cout_Horaire_Prive": 15920, "Heures_Base": 100, "Taux_Charter_EUR_h": 55000, "Vitesse_Croisiere_km_h": 890, "Autonomie_km": 11195, "Passagers_Max": 400},
        {"Modele": "Boeing 747-200", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 289890, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 18520, "Cout_Horaire_Prive": 15186, "Heures_Base": 100, "Taux_Charter_EUR_h": 58000, "Vitesse_Croisiere_km_h": 890, "Autonomie_km": 12640, "Passagers_Max": 350},
        {"Modele": "Boeing 747-400", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 276703, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 15263, "Cout_Horaire_Prive": 12516, "Heures_Base": 100, "Taux_Charter_EUR_h": 65000, "Vitesse_Croisiere_km_h": 913, "Autonomie_km": 14626, "Passagers_Max": 420},
        {"Modele": "Boeing 747SP", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 239780, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 15953, "Cout_Horaire_Prive": 13081, "Heures_Base": 100, "Taux_Charter_EUR_h": 60000, "Vitesse_Croisiere_km_h": 902, "Autonomie_km": 13723, "Passagers_Max": 331},
        {"Modele": "Boeing 757-200ER", "Categorie": "VIP Airliner / BBJ", "Couts_Fixes_Annuels": 274945, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 5939, "Cout_Horaire_Prive": 4870, "Heures_Base": 100, "Taux_Charter_EUR_h": 12000, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 11159, "Passagers_Max": 200},
        {"Modele": "Boeing 767-200ER", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 384835, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 6537, "Cout_Horaire_Prive": 5360, "Heures_Base": 100, "Taux_Charter_EUR_h": 15000, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 13145, "Passagers_Max": 181},
        {"Modele": "Boeing 767-300ER", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 380439, "Couts_Equipe_Annuels": 471643, "Cout_Horaire_Charter": 8352, "Cout_Horaire_Prive": 6849, "Heures_Base": 100, "Taux_Charter_EUR_h": 18000, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 12474, "Passagers_Max": 218},
        {"Modele": "Boeing 787-8", "Categorie": "VIP Wide-Body", "Couts_Fixes_Annuels": 358241, "Couts_Equipe_Annuels": 521978, "Cout_Horaire_Charter": 7925, "Cout_Horaire_Prive": 6498, "Heures_Base": 100, "Taux_Charter_EUR_h": 20000, "Vitesse_Croisiere_km_h": 930, "Autonomie_km": 14538, "Passagers_Max": 381},
        {"Modele": "Boeing BBJ", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 218956, "Couts_Equipe_Annuels": 469635, "Cout_Horaire_Charter": 3763, "Cout_Horaire_Prive": 3086, "Heures_Base": 350, "Taux_Charter_EUR_h": 9000, "Vitesse_Croisiere_km_h": 871, "Autonomie_km": 11100, "Passagers_Max": 19},
        {"Modele": "Boeing BBJ2", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 241598, "Couts_Equipe_Annuels": 469653, "Cout_Horaire_Charter": 3882, "Cout_Horaire_Prive": 3183, "Heures_Base": 350, "Taux_Charter_EUR_h": 10000, "Vitesse_Croisiere_km_h": 840, "Autonomie_km": 10191, "Passagers_Max": 19},
        {"Modele": "Boeing BBJ3", "Categorie": "ACJ / VIP Airliner", "Couts_Fixes_Annuels": 248567, "Couts_Equipe_Annuels": 470089, "Cout_Horaire_Charter": 3889, "Cout_Horaire_Prive": 3189, "Heures_Base": 350, "Taux_Charter_EUR_h": 11000, "Vitesse_Croisiere_km_h": 840, "Autonomie_km": 8649, "Passagers_Max": 19},
        {"Modele": "Bombardier Challenger 604", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 376651, "Couts_Equipe_Annuels": 237726, "Cout_Horaire_Charter": 2726, "Cout_Horaire_Prive": 2450, "Heures_Base": 350, "Taux_Charter_EUR_h": 5200, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 6786, "Passagers_Max": 10},
        {"Modele": "Bombardier Challenger 605", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 500361, "Couts_Equipe_Annuels": 346500, "Cout_Horaire_Charter": 2619, "Cout_Horaire_Prive": 2360, "Heures_Base": 350, "Taux_Charter_EUR_h": 5500, "Vitesse_Croisiere_km_h": 849, "Autonomie_km": 6856, "Passagers_Max": 10},
        {"Modele": "Bombardier Challenger 650", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 488946, "Couts_Equipe_Annuels": 333270, "Cout_Horaire_Charter": 2455, "Cout_Horaire_Prive": 2210, "Heures_Base": 350, "Taux_Charter_EUR_h": 5800, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 6795, "Passagers_Max": 10},
        {"Modele": "Bombardier Global 5000", "Categorie": "Ultra Long Range Jet", "Couts_Fixes_Annuels": 702952, "Couts_Equipe_Annuels": 426052, "Cout_Horaire_Charter": 4051, "Cout_Horaire_Prive": 3646, "Heures_Base": 350, "Taux_Charter_EUR_h": 9000, "Vitesse_Croisiere_km_h": 904, "Autonomie_km": 9390, "Passagers_Max": 13},
        {"Modele": "Bombardier Global Express", "Categorie": "Ultra Long Range Jet", "Couts_Fixes_Annuels": 683427, "Couts_Equipe_Annuels": 426052, "Cout_Horaire_Charter": 4471, "Cout_Horaire_Prive": 4024, "Heures_Base": 350, "Taux_Charter_EUR_h": 9500, "Vitesse_Croisiere_km_h": 904, "Autonomie_km": 10726, "Passagers_Max": 13},
        {"Modele": "Bombardier Global Express XRS", "Categorie": "Ultra Long Range Jet", "Couts_Fixes_Annuels": 714023, "Couts_Equipe_Annuels": 426052, "Cout_Horaire_Charter": 4420, "Cout_Horaire_Prive": 3978, "Heures_Base": 350, "Taux_Charter_EUR_h": 10000, "Vitesse_Croisiere_km_h": 904, "Autonomie_km": 10934, "Passagers_Max": 13},
        {"Modele": "Challenger 300", "Categorie": "Super Midsize Jet", "Couts_Fixes_Annuels": 102295, "Couts_Equipe_Annuels": 392114, "Cout_Horaire_Charter": 2878, "Cout_Horaire_Prive": 2360, "Heures_Base": 350, "Taux_Charter_EUR_h": 3500, "Vitesse_Croisiere_km_h": 848, "Autonomie_km": 5545, "Passagers_Max": 8},
        {"Modele": "Challenger 350", "Categorie": "Super Midsize Jet", "Couts_Fixes_Annuels": 93921, "Couts_Equipe_Annuels": 394305, "Cout_Horaire_Charter": 2353, "Cout_Horaire_Prive": 1929, "Heures_Base": 350, "Taux_Charter_EUR_h": 4000, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 5784, "Passagers_Max": 8},
        {"Modele": "Challenger 600", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 78406, "Couts_Equipe_Annuels": 372774, "Cout_Horaire_Charter": 4337, "Cout_Horaire_Prive": 3556, "Heures_Base": 350, "Taux_Charter_EUR_h": 4500, "Vitesse_Croisiere_km_h": 849, "Autonomie_km": 5061, "Passagers_Max": 9},
        {"Modele": "Challenger 601-1A", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 84681, "Couts_Equipe_Annuels": 367240, "Cout_Horaire_Charter": 3720, "Cout_Horaire_Prive": 3050, "Heures_Base": 350, "Taux_Charter_EUR_h": 4500, "Vitesse_Croisiere_km_h": 821, "Autonomie_km": 5748, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 10", "Categorie": "Light Jet", "Couts_Fixes_Annuels": 279536, "Couts_Equipe_Annuels": 224844, "Cout_Horaire_Charter": 2372, "Cout_Horaire_Prive": 2135, "Heures_Base": 250, "Taux_Charter_EUR_h": 2800, "Vitesse_Croisiere_km_h": 837, "Autonomie_km": 2745, "Passagers_Max": 6},
        {"Modele": "Dassault Falcon 20C", "Categorie": "Midsize Jet", "Couts_Fixes_Annuels": 350751, "Couts_Equipe_Annuels": 278094, "Cout_Horaire_Charter": 3179, "Cout_Horaire_Prive": 2861, "Heures_Base": 250, "Taux_Charter_EUR_h": 3200, "Vitesse_Croisiere_km_h": 805, "Autonomie_km": 2167, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 20C-5", "Categorie": "Midsize Jet", "Couts_Fixes_Annuels": 356747, "Couts_Equipe_Annuels": 278094, "Cout_Horaire_Charter": 2675, "Cout_Horaire_Prive": 2408, "Heures_Base": 250, "Taux_Charter_EUR_h": 3400, "Vitesse_Croisiere_km_h": 842, "Autonomie_km": 3684, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 20F", "Categorie": "Midsize Jet", "Couts_Fixes_Annuels": 356077, "Couts_Equipe_Annuels": 278094, "Cout_Horaire_Charter": 2895, "Cout_Horaire_Prive": 2606, "Heures_Base": 250, "Taux_Charter_EUR_h": 3200, "Vitesse_Croisiere_km_h": 805, "Autonomie_km": 2420, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 20F-5", "Categorie": "Midsize Jet", "Couts_Fixes_Annuels": 353308, "Couts_Equipe_Annuels": 278094, "Cout_Horaire_Charter": 2485, "Cout_Horaire_Prive": 2237, "Heures_Base": 250, "Taux_Charter_EUR_h": 3500, "Vitesse_Croisiere_km_h": 842, "Autonomie_km": 4063, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 50", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 450596, "Couts_Equipe_Annuels": 334924, "Cout_Horaire_Charter": 3352, "Cout_Horaire_Prive": 3017, "Heures_Base": 350, "Taux_Charter_EUR_h": 5000, "Vitesse_Croisiere_km_h": 799, "Autonomie_km": 5526, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 50-40", "Categorie": "Large Jet", "Couts_Fixes_Annuels": 469453, "Couts_Equipe_Annuels": 334924, "Cout_Horaire_Charter": 3328, "Cout_Horaire_Prive": 2995, "Heures_Base": 350, "Taux_Charter_EUR_h": 5200, "Vitesse_Croisiere_km_h": 850, "Autonomie_km": 5905, "Passagers_Max": 9},
        {"Modele": "Dassault Falcon 7X", "Categorie": "Ultra Long Range Jet", "Couts_Fixes_Annuels": 588918, "Couts_Equipe_Annuels": 377505, "Cout_Horaire_Charter": 2994, "Cout_Horaire_Prive": 2695, "Heures_Base": 350, "Taux_Charter_EUR_h": 9500, "Vitesse_Croisiere_km_h": 904, "Autonomie_km": 9924, "Passagers_Max": 12},
        {"Modele": "Dassault Falcon 8X", "Categorie": "Ultra Long Range Jet", "Couts_Fixes_Annuels": 598153, "Couts_Equipe_Annuels": 377505, "Cout_Horaire_Charter": 2958, "Cout_Horaire_Prive": 2662, "Heures_Base": 350, "Taux_Charter_EUR_h": 10500, "Vitesse_Croisiere_km_h": 903, "Autonomie_km": 11365, "Passagers_Max": 12},
    ]
    return pd.DataFrame(data)

def get_active_db() -> pd.DataFrame:
    if st.session_state["database"] is not None:
        return st.session_state["database"]
    return get_default_data()

# ─── COST MASTER — DEFAULT VALUES ────────────────────────────────────────────
# Per-flight defaults (operational, applied × annual flights)
CM_DEFAULTS_OPERATIONAL_PER_FLIGHT = {
    "Handling":        800,
    "Ground Service":  600,
    "Catering":        400,
    "Hotel":           1200,
    "ATC Charges":     900,
    "Flight Planning": 250,
    "Permission":      350,
    "Miscellaneous":   300,
}
# Annual defaults (direct fixed costs)
CM_DEFAULTS_DIRECT = {
    "Maintenance":           85000,
    "Maintenance Programs":  42000,
    "Insurance":             38000,
    "Hangar":                30000,
    "Management Fee (VAT)":  55000,
    "Government Costs":      12000,
    "Cleaning":               8000,
    "Flight Planning Tools":  6000,
    "Nav Programme":          9500,
}
# Annual defaults (indirect / crew costs)
CM_DEFAULTS_INDIRECT = {
    "Crew Salaries":          180000,
    "Total Social Costs":      54000,
    "Training Cockpit":        18000,
    "Training Cabin":           8000,
    "Expense Training Crew":    5000,
    "Communication Crew":       4500,
    "Crew Expenses":           22000,
    "Freelancer":              15000,
    "Miscellaneous Crew":       6000,
}

REQUIRED_COLUMNS = {
    "Modele":               "Aircraft name",
    "Couts_Fixes_Annuels":  "Fixed costs excl. crew (€/year)",
    "Couts_Equipe_Annuels": "Annual crew costs (€/year)",
    "Cout_Horaire_Charter": "Variable charter hourly cost (€/h)",
    "Cout_Horaire_Prive":   "Variable private hourly cost (€/h)",
    "Taux_Charter_EUR_h":   "Charter rate billed to client (€/h)",
}

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
def calculate_costs(aircraft, h_charter, h_private):
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

def calculate_profitability(costs, commission_pct, custom_rate=None):
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

LAYOUT_BASE = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                   font=dict(color="#D6E4F7"), margin=dict(t=10,b=10,l=10,r=10))

def chart_donut(costs):
    labels = ["Fixed Operating Costs","Crew Costs","Charter Variable","Private Variable"]
    values = [costs["fixed_costs"],costs["crew_costs"],costs["var_charter"],costs["var_private"]]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.56,
        marker=dict(colors=[COLORS["fixed"],COLORS["crew"],COLORS["charter"],COLORS["private"]],
                    line=dict(color="#0B1629",width=2)),
        textinfo="label+percent", textfont=dict(size=11,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    fig.add_annotation(text=f"<b>{costs['grand_total']/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
                       x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"),align="center")
    fig.update_layout(**LAYOUT_BASE, height=320,
                      legend=dict(orientation="h",yanchor="bottom",y=-0.2,bgcolor="rgba(0,0,0,0)"))
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
    fig.update_layout(barmode="stack",**LAYOUT_BASE,height=300,
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
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(**LAYOUT_BASE,height=340,
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
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
    fig.update_layout(**LAYOUT_BASE,height=300,showlegend=False,
                      yaxis=dict(title="Net Result (€)",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Charter Flight Hours",gridcolor="#1A3A6E"))
    return fig

# ─── COST MASTER CHARTS ──────────────────────────────────────────────────────
def cm_donut(labels, values, colors, title_text):
    total = sum(v for v in values if v > 0)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.54,
        marker=dict(colors=colors, line=dict(color="#0B1629",width=2)),
        textinfo="label+percent", textfont=dict(size=10,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    fig.add_annotation(
        text=f"<b>{total/1000:.0f}K€</b><br><span style='font-size:9px'>{title_text}</span>",
        x=0.5,y=0.5,showarrow=False,font=dict(size=14,color="#E8C46A"),align="center")
    fig.update_layout(**LAYOUT_BASE, height=300,
                      legend=dict(orientation="h",yanchor="bottom",y=-0.3,bgcolor="rgba(0,0,0,0)",font=dict(size=9)),
                      margin=dict(t=10,b=10,l=5,r=5))
    return fig

def cm_global_donut(op_total, direct_total, indirect_total):
    labels = ["Operational Costs","Direct Costs","Indirect / Crew Costs"]
    values = [op_total, direct_total, indirect_total]
    colors = ["#60A5FA","#F59E0B","#A78BFA"]
    total  = sum(values)
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.56,
        marker=dict(colors=colors, line=dict(color="#0B1629",width=2)),
        textinfo="label+percent", textfont=dict(size=11,color="#D6E4F7"),
        hovertemplate="<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>"))
    fig.add_annotation(
        text=f"<b>{total/1e6:.2f}M€</b><br><span style='font-size:10px'>TOTAL</span>",
        x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"),align="center")
    fig.update_layout(**LAYOUT_BASE, height=360,
                      legend=dict(orientation="h",yanchor="bottom",y=-0.15,bgcolor="rgba(0,0,0,0)"))
    return fig

def cm_bar_breakdown(categories, values, color, title):
    paired = sorted(zip(values, categories), reverse=True)
    values_s, cats_s = zip(*paired) if paired else ([],[])
    fig = go.Figure(go.Bar(
        x=list(cats_s), y=list(values_s),
        marker_color=color, marker_line_color="#0B1629", marker_line_width=1,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} €<extra></extra>",
        text=[f"€{v:,.0f}" for v in values_s], textposition="outside",
        textfont=dict(size=9,color="#D6E4F7")))
    fig.update_layout(**LAYOUT_BASE, height=300, title=dict(text=title,font=dict(size=11,color="#8496B0"),x=0),
                      yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f",title="€"),
                      xaxis=dict(tickangle=-30,gridcolor="rgba(0,0,0,0)"),
                      margin=dict(t=30,b=60,l=10,r=10))
    return fig

def cm_waterfall_global(op, direct, indirect, charter_rev, commission_pct):
    commission = charter_rev * commission_pct / 100
    net_rev = charter_rev - commission
    grand_total = op + direct + indirect
    net = net_rev - grand_total
    fig = go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","relative","total"],
        x=["Charter Revenue","Commission","Operational","Direct Costs","Crew / Indirect","Net Result"],
        y=[charter_rev,-commission,-op,-direct,-indirect,net],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=COLORS["profit"]),
        decreasing=dict(marker_color=COLORS["loss"]),
        totals=dict(marker_color=COLORS["profit"] if net>=0 else COLORS["loss"]),
        texttemplate="%{y:+,.0f} €",textfont=dict(color="#D6E4F7",size=11),
        hovertemplate="<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>"))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(**LAYOUT_BASE, height=360,
                      yaxis=dict(title="€",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def fmt(v, decimals=0):
    return f"€ {v:,.{decimals}f}"

# ════════════════════════════════════════════════════════════════════════════
# PDF EXTRACTION
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
- All monetary values must be in EUR
- Return ONLY the JSON, no explanation, no markdown, no code blocks
- If a value cannot be found or calculated, use null"""

def extract_pdf_with_claude(pdf_bytes, api_key):
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    payload = {
        "model": "claude-sonnet-4-6", "max_tokens": 1000,
        "messages": [{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64}},
            {"type": "text", "text": EXTRACTION_PROMPT}
        ]}]
    }
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Content-Type":"application/json","x-api-key":api_key,
                 "anthropic-version":"2023-06-01","anthropic-beta":"pdfs-2024-09-25"},
        json=payload, timeout=60)
    if response.status_code != 200:
        raise ValueError(f"API error {response.status_code}: {response.text[:300]}")
    data = response.json()
    raw_text = "".join(b.get("text","") for b in data.get("content",[]) if b.get("type")=="text")
    clean = raw_text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(clean)

def add_to_database(new_row):
    db = get_active_db().copy()
    model_name = new_row["Modele"]
    if model_name in db["Modele"].values:
        db = db[db["Modele"] != model_name]
    st.session_state["database"] = pd.concat([db, pd.DataFrame([new_row])], ignore_index=True)

# ════════════════════════════════════════════════════════════════════════════
# COST MASTER INPUT SECTION
# ════════════════════════════════════════════════════════════════════════════
def cost_input_section(label, key, default, use_generic, col1, col2):
    """Render a two-column input row with generic/custom toggle."""
    with col1:
        st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{label}</span>', unsafe_allow_html=True)
    with col2:
        if use_generic:
            st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {default:,.0f}</span>', unsafe_allow_html=True)
            return float(default)
        else:
            val = st.number_input(f"###{key}", value=float(default), min_value=0.0, step=100.0,
                                  label_visibility="collapsed", key=key)
            return val

# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
def main():
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
        st.markdown('<div class="section-header">⬆ Database</div>', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Import an Excel / CSV file", type=["xlsx","xls","csv"],
            help="Required columns: Modele, Couts_Fixes_Annuels, Couts_Equipe_Annuels, Cout_Horaire_Charter, Cout_Horaire_Prive, Taux_Charter_EUR_h")
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
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊  Dashboard",
        "📈  Profitability",
        "🔍  Sensitivity",
        "💼  Cost Master",
        "🤖  Import PDF",
        "📋  Data",
    ])

    # ── TAB 1 : DASHBOARD ────────────────────────────────────────────────
    with tab1:
        col_id1,col_id2,col_id3,col_id4 = st.columns(4)
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
    # TAB 4 : COST MASTER ★ NEW ★
    # ════════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown('<div class="main-title" style="font-size:1.4rem">💼 Cost Master</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Full operational cost breakdown — enter your own figures or use generic benchmarks</div>', unsafe_allow_html=True)

        # ── Config bar ───────────────────────────────────────────────
        cfg1, cfg2, cfg3 = st.columns([2,2,2])
        with cfg1:
            annual_flights = st.number_input("Annual number of flights", min_value=1, max_value=2000,
                                             value=200, step=10,
                                             help="Total flights per year — used to scale per-flight operational costs")
        with cfg2:
            cm_charter_rate = st.number_input("Charter rate (€/h) for analysis",
                                              min_value=0, max_value=200000,
                                              value=int(custom_rate) if custom_rate > 0 else int(db_rate),
                                              step=500)
        with cfg3:
            cm_commission = st.slider("Commission (%)", 0, 25, int(commission_pct), step=1,
                                      key="cm_commission_slider")

        st.markdown("<hr>", unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════
        # INPUT FORM — 3 sections side by side
        # ═══════════════════════════════════════════════════════════
        st.markdown("### ✏️ Cost Input")
        st.markdown("Choose **Generic** to use benchmark values from our database, or **Custom** to enter your own figures.")

        mode_op  = st.radio("Operational Costs mode",  ["Generic", "Custom"], horizontal=True, key="mode_op",  label_visibility="collapsed")
        mode_dir = st.radio("Direct Costs mode",       ["Generic", "Custom"], horizontal=True, key="mode_dir", label_visibility="collapsed")
        mode_ind = st.radio("Indirect / Crew mode",    ["Generic", "Custom"], horizontal=True, key="mode_ind", label_visibility="collapsed")

        # Operational Costs (per flight × annual_flights)
        st.markdown("""<div class="cost-group-card">
            <div class="cost-group-title cg-operational">✈ Operational Costs &nbsp;<span style="font-size:0.72rem;color:#8496B0">(per flight × annual flights)</span></div>
        </div>""", unsafe_allow_html=True)

        mode_op_val  = st.radio("Operational", ["🌐  Generic benchmark", "✏️  Custom values"], horizontal=True, key="radio_op",  label_visibility="collapsed")
        mode_dir_val = st.radio("Direct",      ["🌐  Generic benchmark", "✏️  Custom values"], horizontal=True, key="radio_dir", label_visibility="collapsed")
        mode_ind_val = st.radio("Indirect",    ["🌐  Generic benchmark", "✏️  Custom values"], horizontal=True, key="radio_ind", label_visibility="collapsed")

        use_generic_op  = "Generic" in mode_op_val
        use_generic_dir = "Generic" in mode_dir_val
        use_generic_ind = "Generic" in mode_ind_val

        # ── OPERATIONAL COSTS ──
        with st.expander("✈  OPERATIONAL COSTS  (per flight)", expanded=True):
            st.markdown(f'<div style="font-size:0.72rem;color:#60A5FA;letter-spacing:0.1em;margin-bottom:0.5rem">{"🌐 GENERIC BENCHMARK VALUES" if use_generic_op else "✏️ CUSTOM VALUES — edit below"}</div>', unsafe_allow_html=True)
            op_vals = {}
            op_pairs = list(CM_DEFAULTS_OPERATIONAL_PER_FLIGHT.items())
            for i in range(0, len(op_pairs), 2):
                c1, c2, c3, c4 = st.columns([2,1,2,1])
                key1, def1 = op_pairs[i]
                op_vals[key1] = def1 if use_generic_op else st.columns([2,1,2,1])[1].number_input(
                    key1, value=float(def1), min_value=0.0, step=50.0, label_visibility="collapsed")
                if use_generic_op:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def1:,.0f}</span>', unsafe_allow_html=True)
                else:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: op_vals[key1] = st.number_input(f"op_{key1}", value=float(def1), min_value=0.0, step=50.0, label_visibility="collapsed", key=f"op_{key1}")

                if i+1 < len(op_pairs):
                    key2, def2 = op_pairs[i+1]
                    if use_generic_op:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def2:,.0f}</span>', unsafe_allow_html=True)
                        op_vals[key2] = def2
                    else:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: op_vals[key2] = st.number_input(f"op_{key2}", value=float(def2), min_value=0.0, step=50.0, label_visibility="collapsed", key=f"op_{key2}")

            op_per_flight = sum(op_vals.values())
            op_annual     = op_per_flight * annual_flights
            st.markdown(f'<div style="margin-top:0.5rem;padding:0.5rem 0.8rem;background:#112244;border-radius:4px;font-size:0.85rem">Per flight total: <b style="color:#60A5FA">€ {op_per_flight:,.0f}</b> &nbsp;·&nbsp; Annual total ({annual_flights} flights): <b style="color:#60A5FA">€ {op_annual:,.0f}</b></div>', unsafe_allow_html=True)

        # ── DIRECT COSTS ──
        with st.expander("🔧  DIRECT COSTS  (annual fixed)", expanded=True):
            st.markdown(f'<div style="font-size:0.72rem;color:#F59E0B;letter-spacing:0.1em;margin-bottom:0.5rem">{"🌐 GENERIC BENCHMARK VALUES" if use_generic_dir else "✏️ CUSTOM VALUES — edit below"}</div>', unsafe_allow_html=True)
            dir_vals = {}
            dir_pairs = list(CM_DEFAULTS_DIRECT.items())
            for i in range(0, len(dir_pairs), 2):
                c1, c2, c3, c4 = st.columns([2,1,2,1])
                key1, def1 = dir_pairs[i]
                if use_generic_dir:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def1:,.0f}</span>', unsafe_allow_html=True)
                    dir_vals[key1] = def1
                else:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: dir_vals[key1] = st.number_input(f"dir_{key1}", value=float(def1), min_value=0.0, step=500.0, label_visibility="collapsed", key=f"dir_{key1}")

                if i+1 < len(dir_pairs):
                    key2, def2 = dir_pairs[i+1]
                    if use_generic_dir:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def2:,.0f}</span>', unsafe_allow_html=True)
                        dir_vals[key2] = def2
                    else:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: dir_vals[key2] = st.number_input(f"dir_{key2}", value=float(def2), min_value=0.0, step=500.0, label_visibility="collapsed", key=f"dir_{key2}")

            dir_total = sum(dir_vals.values())
            st.markdown(f'<div style="margin-top:0.5rem;padding:0.5rem 0.8rem;background:#112244;border-radius:4px;font-size:0.85rem">Annual direct costs total: <b style="color:#F59E0B">€ {dir_total:,.0f}</b></div>', unsafe_allow_html=True)

        # ── INDIRECT / CREW COSTS ──
        with st.expander("👥  INDIRECT / CREW COSTS  (annual)", expanded=True):
            st.markdown(f'<div style="font-size:0.72rem;color:#A78BFA;letter-spacing:0.1em;margin-bottom:0.5rem">{"🌐 GENERIC BENCHMARK VALUES" if use_generic_ind else "✏️ CUSTOM VALUES — edit below"}</div>', unsafe_allow_html=True)
            ind_vals = {}
            ind_pairs = list(CM_DEFAULTS_INDIRECT.items())
            for i in range(0, len(ind_pairs), 2):
                c1, c2, c3, c4 = st.columns([2,1,2,1])
                key1, def1 = ind_pairs[i]
                if use_generic_ind:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def1:,.0f}</span>', unsafe_allow_html=True)
                    ind_vals[key1] = def1
                else:
                    with c1: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key1}</span>', unsafe_allow_html=True)
                    with c2: ind_vals[key1] = st.number_input(f"ind_{key1}", value=float(def1), min_value=0.0, step=500.0, label_visibility="collapsed", key=f"ind_{key1}")

                if i+1 < len(ind_pairs):
                    key2, def2 = ind_pairs[i+1]
                    if use_generic_ind:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: st.markdown(f'<span style="color:#E8C46A;font-size:0.88rem;font-weight:600">€ {def2:,.0f}</span>', unsafe_allow_html=True)
                        ind_vals[key2] = def2
                    else:
                        with c3: st.markdown(f'<span style="font-size:0.82rem;color:#D6E4F7">{key2}</span>', unsafe_allow_html=True)
                        with c4: ind_vals[key2] = st.number_input(f"ind_{key2}", value=float(def2), min_value=0.0, step=500.0, label_visibility="collapsed", key=f"ind_{key2}")

            ind_total = sum(ind_vals.values())
            st.markdown(f'<div style="margin-top:0.5rem;padding:0.5rem 0.8rem;background:#112244;border-radius:4px;font-size:0.85rem">Annual indirect / crew total: <b style="color:#A78BFA">€ {ind_total:,.0f}</b></div>', unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════
        # ANALYSIS BUTTON
        # ═══════════════════════════════════════════════════════════
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

        # ═══════════════════════════════════════════════════════════
        # FINANCIAL ANALYSIS (shown after button click)
        # ═══════════════════════════════════════════════════════════
        if st.session_state["cost_master"]:
            cm = st.session_state["cost_master"]
            op_a
