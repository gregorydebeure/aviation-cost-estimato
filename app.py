"""
✈️ Menkor Aviation — Charter Flight Quotation Tool
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
import base64
import math
import warnings
warnings.filterwarnings("ignore")

st.set_page_config(page_title="Menkor Aviation — Quotation", page_icon="✈",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown("""<style>
:root{--navy:#0B1629;--deep:#112244;--mid:#1A3A6E;--gold:#C9A84C;--amber:#E8C46A;
      --slate:#8496B0;--light:#D6E4F7;--card:#13233F;}
.stApp{background-color:var(--navy)!important;color:var(--light)!important;
       font-family:'Segoe UI',system-ui,sans-serif;}
.main-title{font-size:2rem;font-weight:700;letter-spacing:.08em;color:var(--amber);text-transform:uppercase;}
.sub-title{font-size:.85rem;color:var(--slate);letter-spacing:.12em;text-transform:uppercase;margin-bottom:1.5rem;}
.metric-card{background:var(--card);border:1px solid var(--mid);border-left:3px solid var(--gold);
             border-radius:6px;padding:1rem 1.2rem;margin-bottom:.8rem;}
.metric-label{font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--slate);margin-bottom:.3rem;}
.metric-value{font-size:1.7rem;font-weight:700;color:var(--amber);}
.section-header{font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);
                border-bottom:1px solid var(--mid);padding-bottom:.4rem;margin:1.2rem 0 .8rem 0;}
hr{border-color:var(--mid)!important;}
[data-testid="stMetricValue"]{color:var(--amber)!important;font-size:1.5rem!important;}
.stButton>button{background:var(--mid)!important;color:var(--amber)!important;
                 border:1px solid var(--gold)!important;border-radius:4px;font-weight:600;}
.stButton>button:hover{background:var(--gold)!important;color:var(--navy)!important;}
.total-banner{background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
              border:1px solid var(--gold);border-radius:8px;padding:1.5rem;text-align:center;margin:1.5rem 0;}
[data-baseweb="tab-list"]{background:var(--card);border-radius:6px;}
[data-baseweb="tab"]{color:var(--slate)!important;}
[aria-selected="true"]{color:var(--amber)!important;border-bottom-color:var(--gold)!important;}
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

# ─── AIRCRAFT DATABASE ───────────────────────────────────────────────────────
def get_aircraft():
    data = [
        {"Modele":"Airbus 318","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":6500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":6862,"Passagers_Max":19},
        {"Modele":"Airbus 319","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":7000,"Vitesse_Croisiere_km_h":869,"Autonomie_km":11014,"Passagers_Max":19},
        {"Modele":"Airbus 320","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":8500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":8938,"Passagers_Max":150},
        {"Modele":"Airbus 321","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":822,"Autonomie_km":8288,"Passagers_Max":19},
        {"Modele":"Airbus 340","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":28000,"Vitesse_Croisiere_km_h":835,"Autonomie_km":12640,"Passagers_Max":400},
        {"Modele":"Airbus ACJ319neo","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":869,"Autonomie_km":12501,"Passagers_Max":19},
        {"Modele":"Airbus ACJ320neo","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":869,"Autonomie_km":11299,"Passagers_Max":19},
        {"Modele":"BAE RJ-70","Categorie":"Regional Jet / VIP","Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":755,"Autonomie_km":3250,"Passagers_Max":20},
        {"Modele":"BAE RJ-85","Categorie":"Regional Jet / VIP","Taux_Charter_EUR_h":4800,"Vitesse_Croisiere_km_h":755,"Autonomie_km":3366,"Passagers_Max":20},
        {"Modele":"Beechcraft Beechjet 400","Categorie":"Light Jet","Taux_Charter_EUR_h":2200,"Vitesse_Croisiere_km_h":826,"Autonomie_km":2061,"Passagers_Max":7},
        {"Modele":"Beechcraft Beechjet 400A","Categorie":"Light Jet","Taux_Charter_EUR_h":2300,"Vitesse_Croisiere_km_h":832,"Autonomie_km":2133,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier I","Categorie":"Light Jet","Taux_Charter_EUR_h":1800,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Beechcraft Premier IA","Categorie":"Light Jet","Taux_Charter_EUR_h":1900,"Vitesse_Croisiere_km_h":789,"Autonomie_km":1536,"Passagers_Max":7},
        {"Modele":"Boeing 737-500","Categorie":"VIP Airliner / BBJ","Taux_Charter_EUR_h":7500,"Vitesse_Croisiere_km_h":839,"Autonomie_km":5424,"Passagers_Max":150},
        {"Modele":"Boeing 737-600","Categorie":"VIP Airliner / BBJ","Taux_Charter_EUR_h":7800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":7073,"Passagers_Max":119},
        {"Modele":"Boeing 737-700","Categorie":"VIP Airliner / BBJ","Taux_Charter_EUR_h":8000,"Vitesse_Croisiere_km_h":838,"Autonomie_km":7226,"Passagers_Max":140},
        {"Modele":"Boeing 747-100","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":55000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":11195,"Passagers_Max":400},
        {"Modele":"Boeing 747-200","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":58000,"Vitesse_Croisiere_km_h":890,"Autonomie_km":12640,"Passagers_Max":350},
        {"Modele":"Boeing 747-400","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":65000,"Vitesse_Croisiere_km_h":913,"Autonomie_km":14626,"Passagers_Max":420},
        {"Modele":"Boeing 747SP","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":60000,"Vitesse_Croisiere_km_h":902,"Autonomie_km":13723,"Passagers_Max":331},
        {"Modele":"Boeing 757-200ER","Categorie":"VIP Airliner / BBJ","Taux_Charter_EUR_h":12000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":11159,"Passagers_Max":200},
        {"Modele":"Boeing 767-200ER","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":15000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":13145,"Passagers_Max":181},
        {"Modele":"Boeing 767-300ER","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":18000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":12474,"Passagers_Max":218},
        {"Modele":"Boeing 787-8","Categorie":"VIP Wide-Body","Taux_Charter_EUR_h":20000,"Vitesse_Croisiere_km_h":930,"Autonomie_km":14538,"Passagers_Max":381},
        {"Modele":"Boeing BBJ","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":871,"Autonomie_km":11100,"Passagers_Max":19},
        {"Modele":"Boeing BBJ2","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":10191,"Passagers_Max":19},
        {"Modele":"Boeing BBJ3","Categorie":"ACJ / VIP Airliner","Taux_Charter_EUR_h":11000,"Vitesse_Croisiere_km_h":840,"Autonomie_km":8649,"Passagers_Max":19},
        {"Modele":"Bombardier Challenger 604","Categorie":"Large Jet","Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6786,"Passagers_Max":10},
        {"Modele":"Bombardier Challenger 605","Categorie":"Large Jet","Taux_Charter_EUR_h":5500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":6856,"Passagers_Max":10},
        {"Modele":"Bombardier Challenger 650","Categorie":"Large Jet","Taux_Charter_EUR_h":5800,"Vitesse_Croisiere_km_h":850,"Autonomie_km":6795,"Passagers_Max":10},
        {"Modele":"Bombardier Global 5000","Categorie":"Ultra Long Range Jet","Taux_Charter_EUR_h":9000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9390,"Passagers_Max":13},
        {"Modele":"Bombardier Global Express","Categorie":"Ultra Long Range Jet","Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10726,"Passagers_Max":13},
        {"Modele":"Bombardier Global Express XRS","Categorie":"Ultra Long Range Jet","Taux_Charter_EUR_h":10000,"Vitesse_Croisiere_km_h":904,"Autonomie_km":10934,"Passagers_Max":13},
        {"Modele":"Challenger 300","Categorie":"Super Midsize Jet","Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":848,"Autonomie_km":5545,"Passagers_Max":8},
        {"Modele":"Challenger 350","Categorie":"Super Midsize Jet","Taux_Charter_EUR_h":4000,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5784,"Passagers_Max":8},
        {"Modele":"Challenger 600","Categorie":"Large Jet","Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":849,"Autonomie_km":5061,"Passagers_Max":9},
        {"Modele":"Challenger 601-1A","Categorie":"Large Jet","Taux_Charter_EUR_h":4500,"Vitesse_Croisiere_km_h":821,"Autonomie_km":5748,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 10","Categorie":"Light Jet","Taux_Charter_EUR_h":2800,"Vitesse_Croisiere_km_h":837,"Autonomie_km":2745,"Passagers_Max":6},
        {"Modele":"Dassault Falcon 20C","Categorie":"Midsize Jet","Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2167,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20C-5","Categorie":"Midsize Jet","Taux_Charter_EUR_h":3400,"Vitesse_Croisiere_km_h":842,"Autonomie_km":3684,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F","Categorie":"Midsize Jet","Taux_Charter_EUR_h":3200,"Vitesse_Croisiere_km_h":805,"Autonomie_km":2420,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 20F-5","Categorie":"Midsize Jet","Taux_Charter_EUR_h":3500,"Vitesse_Croisiere_km_h":842,"Autonomie_km":4063,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50","Categorie":"Large Jet","Taux_Charter_EUR_h":5000,"Vitesse_Croisiere_km_h":799,"Autonomie_km":5526,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 50-40","Categorie":"Large Jet","Taux_Charter_EUR_h":5200,"Vitesse_Croisiere_km_h":850,"Autonomie_km":5905,"Passagers_Max":9},
        {"Modele":"Dassault Falcon 7X","Categorie":"Ultra Long Range Jet","Taux_Charter_EUR_h":9500,"Vitesse_Croisiere_km_h":904,"Autonomie_km":9924,"Passagers_Max":12},
        {"Modele":"Dassault Falcon 8X","Categorie":"Ultra Long Range Jet","Taux_Charter_EUR_h":10500,"Vitesse_Croisiere_km_h":903,"Autonomie_km":11365,"Passagers_Max":12},
    ]
    return pd.DataFrame(data)

# ─── AIRPORT LOOKUP (100% offline) ───────────────────────────────────────────
_AP = {
    "OMDB":("Dubai Intl",25.2528,55.3644),"DXB":("Dubai Intl",25.2528,55.3644),
    "DUBAI":("Dubai",25.2048,55.2708),"OMAA":("Abu Dhabi",24.4330,54.6511),
    "AUH":("Abu Dhabi",24.4330,54.6511),"OMDW":("Al Maktoum",24.8963,55.1614),
    "OTHH":("Doha Hamad",25.2731,51.6080),"DOH":("Doha",25.2731,51.6080),
    "OERK":("Riyadh",24.9578,46.6988),"RUH":("Riyadh",24.9578,46.6988),
    "OKBK":("Kuwait",29.2267,47.9689),"KWI":("Kuwait",29.2267,47.9689),
    "OEDF":("Dammam",26.4712,49.7979),"DMM":("Dammam",26.4712,49.7979),
    "EGLL":("London Heathrow",51.4775,-0.4614),"LHR":("London Heathrow",51.4775,-0.4614),
    "EGGW":("London Luton",51.8747,-0.3683),"LTN":("London Luton",51.8747,-0.3683),
    "EGKK":("London Gatwick",51.1537,-0.1821),"LGW":("London Gatwick",51.1537,-0.1821),
    "EGLF":("Farnborough",51.2775,-0.7764),"FAB":("Farnborough",51.2775,-0.7764),
    "EGMC":("Southend",51.5714,0.6956),"SEN":("Southend",51.5714,0.6956),
    "LFPG":("Paris CDG",49.0097,2.5479),"CDG":("Paris CDG",49.0097,2.5479),
    "LFPB":("Paris Le Bourget",48.9694,2.4414),"LBG":("Paris Le Bourget",48.9694,2.4414),
    "LFPO":("Paris Orly",48.7233,2.3794),"ORY":("Paris Orly",48.7233,2.3794),
    "LFPV":("Villacoublay",48.7742,2.2011),"LFPT":("Pontoise",49.0967,2.0406),
    "LFMN":("Nice",43.6584,7.2159),"NCE":("Nice",43.6584,7.2159),
    "LFML":("Marseille",43.4393,5.2214),"MRS":("Marseille",43.4393,5.2214),
    "LFLL":("Lyon",45.7256,5.0811),"LYS":("Lyon",45.7256,5.0811),
    "LFBO":("Toulouse",43.6293,1.3638),"TLS":("Toulouse",43.6293,1.3638),
    "LFBD":("Bordeaux",44.8283,-0.7156),"BOD":("Bordeaux",44.8283,-0.7156),
    "LFSB":("Basel Mulhouse",47.5896,7.5290),"BSL":("Basel",47.5896,7.5290),
    "EDDF":("Frankfurt",50.0333,8.5706),"FRA":("Frankfurt",50.0333,8.5706),
    "EDDM":("Munich",48.3537,11.7750),"MUC":("Munich",48.3537,11.7750),
    "EDDB":("Berlin",52.3667,13.5033),"BER":("Berlin",52.3667,13.5033),
    "EHAM":("Amsterdam",52.3086,4.7639),"AMS":("Amsterdam",52.3086,4.7639),
    "LEMD":("Madrid",40.4983,-3.5676),"MAD":("Madrid",40.4983,-3.5676),
    "LEBL":("Barcelona",41.2971,2.0785),"BCN":("Barcelona",41.2971,2.0785),
    "LIRF":("Rome Fiumicino",41.8003,12.2389),"FCO":("Rome",41.8003,12.2389),
    "LIME":("Milan Bergamo",45.6739,9.7042),"BGY":("Milan Bergamo",45.6739,9.7042),
    "LIMC":("Milan Malpensa",45.6306,8.7281),"MXP":("Milan Malpensa",45.6306,8.7281),
    "LMML":("Malta",35.8575,14.4775),"MLA":("Malta",35.8575,14.4775),
    "LSZH":("Zurich",47.4647,8.5492),"ZRH":("Zurich",47.4647,8.5492),
    "LSGG":("Geneva",46.2381,6.1089),"GVA":("Geneva",46.2381,6.1089),
    "LSZA":("Lugano",46.0044,8.9108),"LUG":("Lugano",46.0044,8.9108),
    "EBBR":("Brussels",50.9014,4.4844),"BRU":("Brussels",50.9014,4.4844),
    "ESSA":("Stockholm",59.6519,17.9186),"ARN":("Stockholm",59.6519,17.9186),
    "ENGM":("Oslo",60.1939,11.1004),"OSL":("Oslo",60.1939,11.1004),
    "EKCH":("Copenhagen",55.6181,12.6560),"CPH":("Copenhagen",55.6181,12.6560),
    "EFHK":("Helsinki",60.3172,24.9633),"HEL":("Helsinki",60.3172,24.9633),
    "LOWW":("Vienna",48.1103,16.5697),"VIE":("Vienna",48.1103,16.5697),
    "LKPR":("Prague",50.1008,14.2600),"PRG":("Prague",50.1008,14.2600),
    "EPWA":("Warsaw",52.1657,20.9671),"WAW":("Warsaw",52.1657,20.9671),
    "LHBP":("Budapest",47.4298,19.2611),"BUD":("Budapest",47.4298,19.2611),
    "UUEE":("Moscow Sheremetyevo",55.9726,37.4146),"SVO":("Moscow",55.9726,37.4146),
    "LLBG":("Tel Aviv",32.0114,34.8867),"TLV":("Tel Aviv",32.0114,34.8867),
    "LGAV":("Athens",37.9364,23.9445),"ATH":("Athens",37.9364,23.9445),
    "LTBA":("Istanbul",40.9769,28.8146),"IST":("Istanbul",40.9769,28.8146),
    "LTFM":("Istanbul New",41.2753,28.7519),
    "GMMN":("Casablanca",33.3675,-7.5900),"CMN":("Casablanca",33.3675,-7.5900),
    "GMME":("Rabat",34.0514,-6.7517),"RBA":("Rabat",34.0514,-6.7517),
    "GMFM":("Marrakech",31.6069,-8.0363),"RAK":("Marrakech",31.6069,-8.0363),
    "HECA":("Cairo",30.1219,31.4056),"CAI":("Cairo",30.1219,31.4056),
    "FACT":("Cape Town",-33.9649,18.6017),"CPT":("Cape Town",-33.9649,18.6017),
    "FAOR":("Johannesburg",-26.1392,28.2460),"JNB":("Johannesburg",-26.1392,28.2460),
    "HKJK":("Nairobi",-1.3192,36.9275),"NBO":("Nairobi",-1.3192,36.9275),
    "YSSY":("Sydney",-33.9461,151.1772),"SYD":("Sydney",-33.9461,151.1772),
    "KLAX":("Los Angeles",33.9425,-118.4081),"LAX":("Los Angeles",33.9425,-118.4081),
    "KJFK":("New York JFK",40.6413,-73.7781),"JFK":("New York JFK",40.6413,-73.7781),
    "KMIA":("Miami",25.7959,-80.2870),"MIA":("Miami",25.7959,-80.2870),
    "KSFO":("San Francisco",37.6213,-122.3790),"SFO":("San Francisco",37.6213,-122.3790),
    "VIDP":("New Delhi",28.5665,77.1031),"DEL":("New Delhi",28.5665,77.1031),
    "VABB":("Mumbai",19.0887,72.8679),"BOM":("Mumbai",19.0887,72.8679),
    "WSSS":("Singapore",1.3592,103.9894),"SIN":("Singapore",1.3592,103.9894),
    "VTBS":("Bangkok",13.6900,100.7501),"BKK":("Bangkok",13.6900,100.7501),
    "RJTT":("Tokyo Haneda",35.5494,139.7798),"HND":("Tokyo Haneda",35.5494,139.7798),
    "ZBAA":("Beijing",40.0799,116.6031),"PEK":("Beijing",40.0799,116.6031),
    "ZGSZ":("Shenzhen",22.6393,113.8107),"SZX":("Shenzhen",22.6393,113.8107),
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
    "DUBAI":("Dubai",25.2048,55.2708),"ABUDHABI":("Abu Dhabi",24.4539,54.3773),
}

def geocode(place):
    k = place.strip().upper().replace(" ","").replace("-","")
    if k in _AP: n,la,lo=_AP[k]; return la,lo,n
    for key,(n,la,lo) in _AP.items():
        if k in key or key in k: return la,lo,n
    pl = place.strip().lower()
    for key,(n,la,lo) in _AP.items():
        if pl in n.lower() or n.lower() in pl: return la,lo,n
    return None,None,None

def haversine(la1,lo1,la2,lo2):
    R=6371; dl=math.radians(la2-la1); dg=math.radians(lo2-lo1)
    a=math.sin(dl/2)**2+math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dg/2)**2
    return R*2*math.asin(math.sqrt(a))

def flight_time(dist,speed):
    tm=(dist/speed)*60+10; return tm,f"{int(tm//60)}h {int(tm%60):02d}m"

# ─── PDF ─────────────────────────────────────────────────────────────────────
def generate_pdf(qr, aircraft_row):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle, PageBreak, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.utils import ImageReader
    from reportlab.graphics.shapes import Drawing, Line, Circle, String, Rect
    from datetime import date

    NAVY=HexColor("#112244"); GOLD=HexColor("#C9A84C")
    SLATE=HexColor("#5A6B85"); LIGHT=HexColor("#F4F6FA")
    buf=BytesIO(); page_w,page_h=A4

    logo_b64=_get_logo(); logo_data=base64.b64decode(logo_b64) if logo_b64 else None

    def hf(cv,doc):
        cv.saveState()
        if logo_data:
            cv.drawImage(ImageReader(BytesIO(logo_data)),18*mm,page_h-22*mm,
                         width=38*mm,height=14*mm,preserveAspectRatio=True,mask="auto")
        cv.setStrokeColor(GOLD); cv.setLineWidth(0.8)
        cv.line(18*mm,page_h-23*mm,page_w-18*mm,page_h-23*mm)
        cv.line(18*mm,14*mm,page_w-18*mm,14*mm)
        cv.setFont("Helvetica",7); cv.setFillColor(SLATE)
        cv.drawCentredString(page_w/2,9*mm,"Menkor Aviation GBL — Charter Quotation — Confidential")
        cv.drawRightString(page_w-18*mm,9*mm,f"Page {cv.getPageNumber()}")
        cv.restoreState()

    doc=SimpleDocTemplate(buf,pagesize=A4,topMargin=28*mm,bottomMargin=22*mm,
                           leftMargin=18*mm,rightMargin=18*mm)
    styles=getSampleStyleSheet()
    sT=ParagraphStyle("T",parent=styles["Title"],fontName="Helvetica-Bold",
                       fontSize=22,textColor=NAVY,alignment=TA_CENTER)
    sS=ParagraphStyle("S",parent=styles["Normal"],fontName="Helvetica",
                       fontSize=10,textColor=SLATE,alignment=TA_CENTER,spaceAfter=2)
    sH=ParagraphStyle("H",parent=styles["Heading2"],fontName="Helvetica-Bold",
                       fontSize=12,textColor=NAVY,spaceBefore=10,spaceAfter=6)
    sSm=ParagraphStyle("Sm",parent=styles["Normal"],fontName="Helvetica",
                        fontSize=7.5,textColor=SLATE)
    story=[]

    # Cover
    story.append(Spacer(1,20*mm))
    story.append(Paragraph("CHARTER FLIGHT QUOTATION",sT))
    story.append(Paragraph(qr["aircraft"],ParagraphStyle("AC",parent=styles["Normal"],
        fontName="Helvetica-Bold",fontSize=15,textColor=GOLD,alignment=TA_CENTER,
        spaceBefore=4,spaceAfter=2)))
    story.append(Paragraph(str(aircraft_row.get("Categorie","")),sS))
    story.append(Spacer(1,6*mm))

    # Map drawing
    try:
        all_la=[l["lat1"] for l in qr["legs"]]+[l["lat2"] for l in qr["legs"]]
        all_lo=[l["lon1"] for l in qr["legs"]]+[l["lon2"] for l in qr["legs"]]
        lat_min,lat_max=min(all_la),max(all_la); lon_min,lon_max=min(all_lo),max(all_lo)
        pad_la=max((lat_max-lat_min)*0.35,5); pad_lo=max((lon_max-lon_min)*0.35,8)
        lat_min-=pad_la; lat_max+=pad_la; lon_min-=pad_lo; lon_max+=pad_lo
        mw=160*mm; mh=80*mm
        def xy(lat,lon): return ((lon-lon_min)/(lon_max-lon_min)*mw,(lat-lat_min)/(lat_max-lat_min)*mh)
        d=Drawing(mw,mh)
        d.add(Rect(0,0,mw,mh,fillColor=HexColor("#0B1629"),strokeColor=GOLD,strokeWidth=1.5))
        clrs=["#C9A84C","#60A5FA","#4ADE80","#F87171","#A78BFA"]
        for i,leg in enumerate(qr["legs"]):
            clr=HexColor(clrs[i%len(clrs)]); n=40
            pts=[xy(leg["lat1"]+(leg["lat2"]-leg["lat1"])*s/n,
                    leg["lon1"]+(leg["lon2"]-leg["lon1"])*s/n) for s in range(n+1)]
            for s in range(len(pts)-1):
                d.add(Line(pts[s][0],pts[s][1],pts[s+1][0],pts[s+1][1],
                           strokeColor=clr,strokeWidth=2))
        seen={}
        for leg in qr["legs"]:
            for lk,lok,nk in [("lat1","lon1","from_name"),("lat2","lon2","to_name")]:
                k=(round(leg[lk],1),round(leg[lok],1))
                if k not in seen:
                    seen[k]=True; x,y=xy(leg[lk],leg[lok])
                    d.add(Circle(x,y,4,fillColor=HexColor("#FFFFFF"),
                                 strokeColor=GOLD,strokeWidth=1.5))
                    d.add(String(x+6,y-3,leg[nk][:18],fontSize=6,
                                 fillColor=HexColor("#E8C46A"),fontName="Helvetica-Bold"))
        story.append(d); story.append(Spacer(1,4*mm))
    except Exception:
        pass

    story.append(HRFlowable(width="100%",thickness=1,color=GOLD,spaceAfter=6))
    story.append(Paragraph(f"Date: {date.today().strftime('%d %B %Y')}",sS))
    story.append(PageBreak())

    # Itinerary
    story.append(Paragraph("Flight Itinerary",sH))
    hdr=["#","From","To","Dep.","Distance","Flight Time",f"Cost ({qr['currency']})"]
    rows=[hdr]
    for i,leg in enumerate(qr["legs"]):
        rows.append([str(i+1),leg["from_name"][:18],leg["to_name"][:18],leg["dep_time"],
                     f"{leg['dist_km']:,.0f} km",leg["flight_time_str"],
                     f"{qr['currency']} {leg['cost']:,.0f}"])
    rows.append(["","","","",f"{qr['total_dist']:,.0f} km",
                 f"{int(qr['total_min']//60)}h{int(qr['total_min']%60):02d}m",
                 f"TOTAL: {qr['currency']} {qr['total_cost']:,.0f}"])
    tbl=Table(rows,colWidths=[8*mm,33*mm,33*mm,14*mm,23*mm,20*mm,30*mm],repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,1),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),8),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),
        ("BACKGROUND",(0,0),(-1,0),NAVY),("ALIGN",(4,0),(-1,-1),"RIGHT"),
        ("ROWBACKGROUNDS",(0,1),(-1,-2),[HexColor("#FFFFFF"),LIGHT]),
        ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("LINEABOVE",(0,-1),(-1,-1),1,GOLD),
        ("GRID",(0,0),(-1,-1),0.3,HexColor("#DDDDDD")),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3)]))
    story.append(tbl)

    # Extras
    if qr.get("extras"):
        story.append(Spacer(1,6*mm)); story.append(Paragraph("Extras & Services",sH))
        er=[["Service",f"Cost ({qr['currency']})"]]
        for e in qr["extras"]: er.append([e["name"],f"{qr['currency']} {e['cost']:,.0f}"])
        er.append(["TOTAL EXTRAS",f"{qr['currency']} {qr.get('extras_total',0):,.0f}"])
        et=Table(er,colWidths=[120*mm,44*mm])
        et.setStyle(TableStyle([
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTNAME",(0,1),(-1,-2),"Helvetica"),
            ("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
            ("BACKGROUND",(0,0),(-1,0),NAVY),("TEXTCOLOR",(0,0),(-1,0),HexColor("#FFFFFF")),
            ("ALIGN",(1,0),(1,-1),"RIGHT"),("GRID",(0,0),(-1,-1),0.3,HexColor("#DDDDDD")),
            ("LINEABOVE",(0,-1),(-1,-1),1,GOLD),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
        story.append(et)

    # Grand total
    story.append(Spacer(1,6*mm))
    tt=Table([["Flight Cost",f"{qr['currency']} {qr.get('flight_cost',qr['total_cost']):,.0f}"],
              ["Extras",f"{qr['currency']} {qr.get('extras_total',0):,.0f}"],
              ["TOTAL QUOTATION",f"{qr['currency']} {qr['total_cost']:,.0f}"]],
             colWidths=[120*mm,44*mm])
    tt.setStyle(TableStyle([
        ("FONTNAME",(0,0),(-1,-2),"Helvetica"),("FONTNAME",(0,-1),(-1,-1),"Helvetica-Bold"),
        ("FONTSIZE",(0,-1),(-1,-1),12),("ALIGN",(1,0),(1,-1),"RIGHT"),
        ("BACKGROUND",(0,-1),(-1,-1),NAVY),("TEXTCOLOR",(0,-1),(-1,-1),GOLD),
        ("LINEABOVE",(0,-1),(-1,-1),1.5,GOLD),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(tt)

    if qr.get("notes"):
        story.append(Spacer(1,4*mm))
        story.append(Paragraph(f"<b>Notes:</b> {qr['notes']}",
            ParagraphStyle("N",parent=styles["Normal"],fontSize=9,textColor=NAVY)))

    story.append(Spacer(1,8*mm))
    story.append(HRFlowable(width="100%",thickness=0.5,color=HexColor("#CCCCCC"),spaceAfter=4))
    story.append(Paragraph(
        "This quotation is indicative and subject to aircraft availability, fuel surcharges "
        "and applicable taxes. Valid 48 hours from date of issue.",sSm))

    doc.build(story,onFirstPage=hf,onLaterPages=hf)
    buf.seek(0); return buf.getvalue()

# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    for k,v in [("q_legs",[{"from":"","to":"","dep_time":"08:00"}]),
                ("q_result",None),("q_pdf",None)]:
        if k not in st.session_state: st.session_state[k]=v

    # Header
    c1,c2=st.columns([1,6])
    with c1: st.markdown("<div style='font-size:3rem;text-align:center;margin-top:.3rem'>✈</div>",unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="main-title">Charter Flight Quotation</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Menkor Aviation GBL — Professional Charter Quotation Tool</div>',unsafe_allow_html=True)
    st.markdown("<hr>",unsafe_allow_html=True)

    df=get_aircraft()

    # Aircraft & settings
    col1,col2,col3=st.columns([2,1,1])
    with col1:
        cats=["All"]+sorted(df["Categorie"].dropna().unique().tolist())
        cat=st.selectbox("Category",cats,key="q_cat")
        df_f=df if cat=="All" else df[df["Categorie"]==cat]
        ac_name=st.selectbox("Aircraft",df_f["Modele"].tolist(),key="q_ac")
        ac=df_f[df_f["Modele"]==ac_name].iloc[0]
        speed=float(ac["Vitesse_Croisiere_km_h"])*0.9
    with col2:
        rate=st.number_input("Operator rate (€/h)",min_value=0,max_value=500000,
                              value=int(ac.get("Taux_Charter_EUR_h",5000)),step=100,key="q_rate")
        curr=st.selectbox("Currency",["EUR","USD","GBP","AED"],key="q_curr")
    with col3:
        st.markdown('<div class="metric-card" style="margin-top:1.5rem">',unsafe_allow_html=True)
        st.markdown(f'<div class="metric-label">Cruise Speed</div><div class="metric-value" style="font-size:1.2rem">{ac["Vitesse_Croisiere_km_h"]} km/h</div>',unsafe_allow_html=True)
        st.markdown(f'<div class="metric-sub">Max range: {ac.get("Autonomie_km",0):,.0f} km · {ac.get("Passagers_Max","—")} pax</div></div>',unsafe_allow_html=True)

    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown('<div class="section-header">✈ Route</div>',unsafe_allow_html=True)

    st.caption("💡 Enter ICAO (OMDB, LFPB, EGLL), IATA (DXB, LHR, CDG) or city name (Dubai, London, Paris)")

    legs=st.session_state["q_legs"]
    for i,leg in enumerate(legs):
        lc1,lc2,lc3,lc4=st.columns([2.5,2.5,1.5,0.5])
        with lc1: legs[i]["from"]=st.text_input("From",value=leg["from"],key=f"qf_{i}",placeholder="OMDB / Dubai")
        with lc2: legs[i]["to"]=st.text_input("To",value=leg["to"],key=f"qt_{i}",placeholder="LFPB / Paris")
        with lc3: legs[i]["dep_time"]=st.text_input("Departure",value=leg["dep_time"],key=f"qd_{i}",placeholder="HH:MM")
        with lc4:
            st.markdown("<br>",unsafe_allow_html=True)
            if i>0 and st.button("✕",key=f"qdel_{i}"):
                legs.pop(i); st.rerun()

    st.markdown("<hr>",unsafe_allow_html=True)

    # Extras
    st.markdown('<div class="section-header">➕ Extras & Services</div>',unsafe_allow_html=True)
    ex1,ex2=st.columns(2)
    with ex1:
        st.markdown('<div style="font-size:.82rem;color:#60A5FA;font-weight:600;margin-bottom:.3rem">👤 Crew</div>',unsafe_allow_html=True)
        q_fa=st.number_input("Flight Attendant(s)",min_value=0,max_value=6,value=1,key="q_fa")
        q_fa_r=st.number_input("FA daily rate (€)",min_value=0,value=500,step=50,key="q_fa_r")
        q_fa_d=st.number_input("Days",min_value=1,value=1,key="q_fa_d")
        q_fa_t=q_fa*q_fa_r*q_fa_d
        st.markdown('<div style="font-size:.82rem;color:#60A5FA;font-weight:600;margin-top:.6rem;margin-bottom:.3rem">🍽️ Catering</div>',unsafe_allow_html=True)
        q_pax=st.number_input("Passengers",min_value=0,value=4,key="q_pax")
        q_cat_r=st.number_input("Catering/pax (€)",min_value=0,value=150,step=10,key="q_cat_r")
        q_cat_t=q_pax*q_cat_r
    with ex2:
        st.markdown('<div style="font-size:.82rem;color:#F59E0B;font-weight:600;margin-bottom:.3rem">⭐ Special Services</div>',unsafe_allow_html=True)
        sp1n=st.text_input("Service 1",value="Ground Transfer",key="sp1n")
        sp1p=st.number_input("Cost (€)",min_value=0,value=0,step=50,key="sp1p")
        sp2n=st.text_input("Service 2",value="",key="sp2n")
        sp2p=st.number_input("Cost (€) ",min_value=0,value=0,step=50,key="sp2p")
        sp3n=st.text_input("Service 3",value="",key="sp3n")
        sp3p=st.number_input("Cost (€)  ",min_value=0,value=0,step=50,key="sp3p")
        q_notes=st.text_area("Notes",placeholder="VIP requirements, dietary restrictions...",height=80,key="q_notes")

    extras=[]
    if q_fa>0 and q_fa_t>0: extras.append({"name":f"Flight Attendant x{q_fa} ({q_fa_d}d)","cost":q_fa_t})
    if q_cat_t>0: extras.append({"name":f"Catering ({q_pax} pax)","cost":q_cat_t})
    for sn,sp in [(sp1n,sp1p),(sp2n,sp2p),(sp3n,sp3p)]:
        if sn.strip() and sp>0: extras.append({"name":sn.strip(),"cost":sp})
    extras_t=sum(e["cost"] for e in extras)
    if extras:
        st.markdown(f'<div style="padding:.4rem .8rem;background:#112244;border-radius:4px;font-size:.84rem;margin:.5rem 0">Extras total: <b style="color:#F59E0B">€ {extras_t:,.0f}</b></div>',unsafe_allow_html=True)

    ca1,ca2=st.columns([1,2])
    with ca1:
        if st.button("➕ Add stop",key="add_stop"):
            last=legs[-1]["to"] if legs else ""; legs.append({"from":last,"to":"","dep_time":"12:00"}); st.rerun()
    with ca2:
        calc=st.button("🧮 Calculate & Generate Quotation",key="calc",type="primary")

    if calc:
        ald=[]; errs=[]
        for i,leg in enumerate(legs):
            if not leg["from"] or not leg["to"]:
                errs.append(f"Leg {i+1}: please fill From and To."); continue
            la1,lo1,n1=geocode(leg["from"])
            la2,lo2,n2=geocode(leg["to"])
            if None in (la1,lo1,la2,lo2):
                errs.append(f"Leg {i+1}: '{leg['from']}' or '{leg['to']}' not found. Use ICAO/IATA code or city name."); continue
            dist=haversine(la1,lo1,la2,lo2)
            tm,fts=flight_time(dist,speed)
            cost=(tm/60)*rate
            ald.append(dict(from_name=n1,to_name=n2,dep_time=leg["dep_time"],
                lat1=la1,lon1=lo1,lat2=la2,lon2=lo2,
                dist_km=dist,flight_time_min=tm,flight_time_str=fts,cost=cost))
        if errs:
            for e in errs: st.error(e)
        elif ald:
            ft=sum(l["cost"] for l in ald)
            st.session_state["q_result"]=dict(
                legs=ald,aircraft=ac_name,rate=rate,currency=curr,speed=speed,
                total_dist=sum(l["dist_km"] for l in ald),
                total_min=sum(l["flight_time_min"] for l in ald),
                total_cost=ft+extras_t,flight_cost=ft,
                extras=extras,extras_total=extras_t,notes=q_notes)
            st.session_state["q_pdf"]=None

    if st.session_state.get("q_result"):
        qr=st.session_state["q_result"]; ald=qr["legs"]
        st.markdown("<hr>",unsafe_allow_html=True)

        # KPIs
        k1,k2,k3,k4,k5=st.columns(5)
        k1.metric("Distance",f"{qr['total_dist']:,.0f} km")
        k2.metric("Flight Time",f"{int(qr['total_min']//60)}h {int(qr['total_min']%60):02d}m")
        k3.metric(f"Flight Cost",f"{qr['currency']} {qr.get('flight_cost',qr['total_cost']):,.0f}")
        k4.metric("Extras",f"{qr['currency']} {qr.get('extras_total',0):,.0f}")
        k5.metric("💰 Total Quote",f"{qr['currency']} {qr['total_cost']:,.0f}")

        # Map
        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown('<div class="section-header">🗺 Route Map</div>',unsafe_allow_html=True)
        fig=go.Figure()
        clrs=["#C9A84C","#60A5FA","#4ADE80","#F87171","#A78BFA"]
        all_la=[]; all_lo=[]
        for i,leg in enumerate(ald):
            clr=clrs[i%len(clrs)]; n=60
            alats=[leg["lat1"]+(leg["lat2"]-leg["lat1"])*s/n for s in range(n+1)]
            alons=[leg["lon1"]+(leg["lon2"]-leg["lon1"])*s/n for s in range(n+1)]
            fig.add_trace(go.Scattergeo(lat=alats,lon=alons,mode="lines",
                line=dict(width=2.5,color=clr),opacity=1,
                name=f"{leg['from_name']} → {leg['to_name']}",hoverinfo="skip"))
            mid=len(alats)//2
            fig.add_trace(go.Scattergeo(lat=[alats[mid]],lon=[alons[mid]],mode="markers",
                marker=dict(size=8,color=clr,symbol="triangle-right"),showlegend=False,hoverinfo="skip"))
            all_la+=[leg["lat1"],leg["lat2"]]; all_lo+=[leg["lon1"],leg["lon2"]]
        seen={}
        for leg in ald:
            for lk,lok,nk in [("lat1","lon1","from_name"),("lat2","lon2","to_name")]:
                k=(round(leg[lk],2),round(leg[lok],2))
                if k not in seen:
                    seen[k]=True
                    fig.add_trace(go.Scattergeo(lat=[leg[lk]],lon=[leg[lok]],mode="markers+text",
                        marker=dict(size=12,color="#FFFFFF",line=dict(width=2,color="#C9A84C")),
                        text=[leg[nk]],textposition="top center",
                        textfont=dict(size=11,color="#E8C46A"),showlegend=False,hoverinfo="skip"))
        pad_la=max((max(all_la)-min(all_la))*.3,5); pad_lo=max((max(all_lo)-min(all_lo))*.3,8)
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",height=480,
            margin=dict(t=0,b=0,l=0,r=0),showlegend=True,
            legend=dict(bgcolor="rgba(17,34,68,.9)",font=dict(color="#D6E4F7",size=10),
                        bordercolor="#C9A84C",borderwidth=1,x=.01,y=.99),
            geo=dict(projection_type="natural earth",
                showland=True,landcolor="#1C2E55",showocean=True,oceancolor="#0B1629",
                showcoastlines=True,coastlinecolor="#3A5080",
                showcountries=True,countrycolor="#2A4070",bgcolor="rgba(0,0,0,0)",
                center=dict(lat=sum(all_la)/len(all_la),lon=sum(all_lo)/len(all_lo)),
                lataxis=dict(range=[min(all_la)-pad_la,max(all_la)+pad_la]),
                lonaxis=dict(range=[min(all_lo)-pad_lo,max(all_lo)+pad_lo])))
        st.plotly_chart(fig,key="map_chart")

        # Leg table
        st.markdown('<div class="section-header">📋 Leg Details</div>',unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{
            "Leg":str(i+1),"From":l["from_name"],"To":l["to_name"],"Dep.":l["dep_time"],
            "Distance":f"{l['dist_km']:,.0f} km","Time":l["flight_time_str"],
            f"Cost ({qr['currency']})":f"{l['cost']:,.0f}"
        } for i,l in enumerate(ald)]),hide_index=True)

        if qr.get("extras"):
            st.markdown('<div class="section-header">➕ Extras</div>',unsafe_allow_html=True)
            st.dataframe(pd.DataFrame([{"Service":e["name"],f"Cost ({qr['currency']})":f"{e['cost']:,.0f}"} for e in qr["extras"]]),hide_index=True)

        if qr.get("notes"):
            st.markdown(f'<div style="background:#13233F;border:1px solid #1A3A6E;border-radius:6px;padding:.7rem 1rem;font-size:.84rem;color:#D6E4F7;margin:.5rem 0"><b>Notes:</b> {qr["notes"]}</div>',unsafe_allow_html=True)

        # Total banner
        st.markdown(f'''<div class="total-banner">
            <div style="font-size:.82rem;color:#8496B0;margin-bottom:.3rem">{qr["aircraft"]} · {qr["currency"]} {qr["rate"]:,.0f}/h operator rate</div>
            <div style="font-size:2rem;font-weight:800;color:#E8C46A">{qr["currency"]} {qr["total_cost"]:,.0f}</div>
            <div style="font-size:.85rem;color:#8496B0;margin-top:.2rem">{qr["total_dist"]:,.0f} km · {int(qr["total_min"]//60)}h {int(qr["total_min"]%60):02d}m total</div>
        </div>''',unsafe_allow_html=True)

        # PDF
        st.markdown("<br>",unsafe_allow_html=True)
        if st.button("📄 Generate PDF Quotation",type="primary"):
            with st.spinner("Building quotation..."):
                try:
                    st.session_state["q_pdf"]=generate_pdf(qr,ac)
                    st.success("✓ Quotation ready!")
                except Exception as e:
                    st.error(f"PDF error: {e}")

        if st.session_state.get("q_pdf"):
            st.download_button("⬇ Download PDF Quotation",data=st.session_state["q_pdf"],
                file_name=f"Menkor_Quote_{qr['aircraft'].replace(' ','_')}.pdf",
                mime="application/pdf")

    st.markdown("<hr>",unsafe_allow_html=True)
    st.markdown(f'<div style="text-align:center;font-size:.72rem;color:#4A5568">MENKOR AVIATION GBL · <a href="https://aviation-cost-estimato-6uj3ptpc57onofwlavwhfn.streamlit.app" style="color:#C9A84C">← Back to Cost Estimator</a></div>',unsafe_allow_html=True)

if __name__=="__main__":
    main()
