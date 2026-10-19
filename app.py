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
import streamlit.components.v1 as components

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
                 "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "RESEND_API_KEY", "BUDGET_REQUEST_TO"]
        with open(_secrets_path, "w") as f:
            for k in _keys:
                v = os.environ.get(k, "")
                f.write(f'{k} = {v!r}\n')
except Exception:
    pass  # never let this bootstrap crash the app on any platform

# ─── PAGE CONFIG & CSS ───────────────────────────────────────────────────────
st.set_page_config(page_title="Aviation Cost Estimator", page_icon="✈",
                   layout="wide", initial_sidebar_state="expanded")

# ─── PWA (installable Android/iOS app) ───────────────────────────────────────
# Streamlit doesn't expose <head>, so this injects the manifest/meta tags into
# the REAL page head via window.parent — standard trick for Streamlit + PWA.
# Requires: .streamlit/config.toml with enableStaticServing = true, and the
# static/ folder (manifest.json, sw.js, icons) committed next to this file.
try:
    components.html("""
    <script>
    (function(){
      try {
        var d = window.parent.document;
        function addLink(rel, href, attrs){
          if (d.querySelector('link[rel="'+rel+'"][href="'+href+'"]')) return;
          var l = d.createElement('link'); l.rel = rel; l.href = href;
          if (attrs) for (var k in attrs) l.setAttribute(k, attrs[k]);
          d.head.appendChild(l);
        }
        function addMeta(name, content){
          if (d.querySelector('meta[name="'+name+'"]')) return;
          var m = d.createElement('meta'); m.name = name; m.content = content;
          d.head.appendChild(m);
        }
        addLink('manifest', '/app/static/manifest.json');
        addLink('icon', '/app/static/icon-192.png', {sizes:'192x192'});
        addLink('apple-touch-icon', '/app/static/apple-touch-icon.png');
        addMeta('theme-color', '#0B1629');
        addMeta('mobile-web-app-capable', 'yes');
        addMeta('apple-mobile-web-app-capable', 'yes');
        addMeta('apple-mobile-web-app-status-bar-style', 'black-translucent');
        addMeta('apple-mobile-web-app-title', 'Menkor Cost');
        if ('serviceWorker' in navigator) {
          navigator.serviceWorker.register('/app/static/sw.js').catch(function(){});
        }
      } catch (e) {}
    })();
    </script>
    """, height=0, width=0)
except Exception:
    pass  # never let a PWA injection failure break the app

st.markdown("""<style>
/* Menkor theme. Rule: every colour that sets a text colour also sets its own background, so contrast never depends on the
   browser / OS light-dark mode or on Streamlit's default theme. Only stable hooks are used (data-testid, data-baseweb, role,
   aria-*): no generated emotion/css-xxxx class. The same palette is declared in .streamlit/config.toml [theme]. */
:root{--navy:#0B1629;--deep:#112244;--mid:#1A3A6E;--gold:#C9A84C;--amber:#E8C46A;
      --slate:#B9C6DC;--light:#F0F4FB;--card:#13233F;
      --field:#0E1B33;--field-border:#6384C0;--field-hover:#162A4D;--field-off:#0C1628;--text-off:#A9B8D2;--ph:#9FB0CC;--sel:#1A3A6E;}
html{color-scheme:dark;}
.stApp{background-color:var(--navy)!important;color:var(--light)!important;
       font-family:'Segoe UI',system-ui,sans-serif;font-size:1.02rem;}
[data-testid="stHeader"]{background-color:var(--navy)!important;}
[data-testid="stSidebar"]{background-color:var(--deep)!important;border-right:1px solid var(--mid);}
[data-testid="stSidebar"] *{color:var(--light)!important;}
.main-title{font-size:2rem;font-weight:700;letter-spacing:.08em;color:var(--amber);text-transform:uppercase;}
.sub-title{font-size:.9rem;color:var(--slate);letter-spacing:.12em;text-transform:uppercase;margin-bottom:1.5rem;}
.metric-card{background:var(--card);border:1px solid var(--mid);border-left:3px solid var(--gold);border-radius:6px;padding:1rem 1.2rem;margin-bottom:.8rem;}
.metric-label{font-size:.76rem;letter-spacing:.12em;text-transform:uppercase;color:var(--slate);margin-bottom:.3rem;}
.metric-value{font-size:1.7rem;font-weight:700;color:var(--amber);}
.metric-sub{font-size:.82rem;color:var(--slate);margin-top:.1rem;}
.section-header{font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;color:var(--gold);
                border-bottom:1px solid var(--mid);padding-bottom:.4rem;margin:1.2rem 0 .8rem 0;}
hr{border-color:var(--mid)!important;}
[data-testid="stMetricValue"]{color:var(--amber)!important;font-size:1.5rem!important;}
[data-testid="stMetricLabel"], [data-testid="stMetricLabel"] *{color:var(--slate)!important;font-size:.78rem!important;}
[data-testid="stMetricDelta"]{color:#4ADE80!important;}
.tag-ok{background:#163A2A;color:#4ADE80;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-warn{background:#3A2A10;color:#FBBF24;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.tag-err{background:#3A1010;color:#F87171;padding:2px 8px;border-radius:3px;font-size:.75rem;}
.total-banner{background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);border:1px solid var(--gold);border-radius:8px;padding:1.5rem;text-align:center;margin:1.5rem 0;}

/* Text */
[data-testid="stWidgetLabel"], [data-testid="stWidgetLabel"] *{color:var(--light)!important;font-size:.98rem!important;font-weight:500!important;opacity:1!important;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *, [data-testid="stMarkdownContainer"] small{
    color:var(--slate)!important;font-size:.85rem!important;opacity:1!important;}
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li{color:var(--light);}

/* Buttons */
.stButton>button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"]{
    background:var(--mid)!important;color:var(--amber)!important;border:1px solid var(--gold)!important;border-radius:4px;font-weight:600;font-size:1rem;}
.stButton>button *, [data-testid="stBaseButton-secondary"] *, [data-testid="stBaseButton-primary"] *{color:inherit!important;}
.stButton>button:hover, [data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-primary"]:hover{background:var(--gold)!important;color:var(--navy)!important;}
.stButton>button:focus-visible, [data-testid^="stBaseButton"]:focus-visible{outline:2px solid var(--amber)!important;outline-offset:2px;}
.stButton>button:disabled, [data-testid^="stBaseButton"]:disabled{background:var(--field-off)!important;color:var(--text-off)!important;border-color:var(--mid)!important;cursor:not-allowed;}
[data-testid="stDownloadButton"] button{background:var(--mid)!important;color:var(--amber)!important;border:1px solid var(--gold)!important;}
[data-testid="stDownloadButton"] button:hover{background:var(--gold)!important;color:var(--navy)!important;}

/* Tabs */
[data-baseweb="tab-list"]{background:var(--card);border-radius:6px;}
[data-baseweb="tab"]{color:#D6E4F7!important;opacity:1!important;font-weight:600;padding-left:14px!important;padding-right:14px!important;white-space:nowrap!important;}
[data-baseweb="tab"] *{color:inherit!important;}
[data-baseweb="tab"]:hover{color:var(--amber)!important;}
[aria-selected="true"]{color:var(--amber)!important;border-bottom-color:var(--gold)!important;font-weight:700;}

/* Text inputs, number inputs, text areas: dark field + light text, in every state */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"]{
    background-color:var(--field)!important;border-color:var(--field-border)!important;border-radius:4px;}
[data-baseweb="input"] input, [data-baseweb="base-input"] input, [data-baseweb="textarea"] textarea, [data-testid="stNumberInput"] input{
    background-color:var(--field)!important;color:var(--light)!important;-webkit-text-fill-color:var(--light)!important;caret-color:var(--amber);font-size:1rem!important;}
[data-baseweb="input"]:hover, [data-baseweb="base-input"]:hover, [data-baseweb="textarea"]:hover{border-color:var(--gold)!important;}
[data-baseweb="input"]:focus-within, [data-baseweb="base-input"]:focus-within, [data-baseweb="textarea"]:focus-within{border-color:var(--amber)!important;box-shadow:0 0 0 1px var(--amber)!important;}
[data-baseweb="input"] input::placeholder, [data-baseweb="textarea"] textarea::placeholder{color:var(--ph)!important;-webkit-text-fill-color:var(--ph)!important;opacity:1!important;}
[data-baseweb="input"]:has(input:disabled), [data-baseweb="base-input"]:has(input:disabled), [data-baseweb="textarea"]:has(textarea:disabled){
    background-color:var(--field-off)!important;border-color:var(--mid)!important;}
input:disabled, textarea:disabled{background-color:var(--field-off)!important;color:var(--text-off)!important;-webkit-text-fill-color:var(--text-off)!important;opacity:1!important;cursor:not-allowed;}
[data-testid="stNumberInput"] button{background-color:var(--field-hover)!important;color:var(--light)!important;border-color:var(--field-border)!important;}
[data-testid="stNumberInput"] button *{color:var(--light)!important;fill:var(--light)!important;}
[data-testid="stNumberInput"] button:hover{background-color:var(--mid)!important;}
[data-testid="stNumberInput"] button:disabled{background-color:var(--field-off)!important;}
[data-testid="stNumberInput"] button:disabled *{color:var(--text-off)!important;fill:var(--text-off)!important;}

/* Selectboxes (Manufacturer, Aircraft model...) and multiselects */
[data-baseweb="select"] > div{background-color:var(--field)!important;border:1px solid var(--field-border)!important;border-radius:4px;color:var(--light)!important;}
[data-baseweb="select"] *{color:var(--light)!important;-webkit-text-fill-color:var(--light)!important;}
[data-baseweb="select"] svg{fill:var(--amber)!important;color:var(--amber)!important;}
[data-baseweb="select"] input::placeholder{color:var(--ph)!important;-webkit-text-fill-color:var(--ph)!important;opacity:1!important;}
[data-baseweb="select"]:hover > div{border-color:var(--gold)!important;background-color:var(--field-hover)!important;}
[data-baseweb="select"]:focus-within > div, [data-baseweb="select"][aria-expanded="true"] > div{border-color:var(--amber)!important;box-shadow:0 0 0 1px var(--amber)!important;}
[data-baseweb="select"][aria-disabled="true"] > div, [data-baseweb="select"]:has(input:disabled) > div{background-color:var(--field-off)!important;border-color:var(--mid)!important;}
[data-baseweb="select"][aria-disabled="true"] *, [data-baseweb="select"]:has(input:disabled) *{color:var(--text-off)!important;-webkit-text-fill-color:var(--text-off)!important;cursor:not-allowed;}
[data-baseweb="tag"]{background-color:var(--mid)!important;}
[data-baseweb="tag"] *{color:var(--light)!important;}

/* Dropdown lists (rendered in a portal outside the sidebar) */
[data-baseweb="popover"], [data-baseweb="popover"] > div{background-color:var(--deep)!important;border:1px solid var(--gold);border-radius:4px;}
[data-baseweb="popover"] ul, [data-baseweb="menu"], [role="listbox"]{background-color:var(--deep)!important;}
[data-baseweb="popover"] li, [role="option"]{background-color:var(--deep)!important;color:var(--light)!important;}
[data-baseweb="popover"] li *, [role="option"] *{color:var(--light)!important;}
[data-baseweb="popover"] li:hover, [role="option"]:hover, [role="option"][data-highlighted="true"], [role="option"][aria-selected="true"]{background-color:var(--sel)!important;}
[role="option"][aria-selected="true"], [role="option"][aria-selected="true"] *{color:var(--amber)!important;font-weight:700;}
[role="option"][aria-disabled="true"], [role="option"][aria-disabled="true"] *{color:var(--text-off)!important;cursor:not-allowed;}

/* Radios, checkboxes, toggles (labels) */
[data-testid="stRadio"] label, [data-testid="stRadio"] label *, [data-testid="stCheckbox"] label, [data-testid="stCheckbox"] label *,
[data-testid="stToggle"] label, [data-testid="stToggle"] label *{color:var(--light)!important;opacity:1!important;}
[data-testid="stRadio"] label:has(input:disabled) *, [data-testid="stCheckbox"] label:has(input:disabled) *, [data-testid="stToggle"] label:has(input:disabled) *,
[data-testid="stWidgetLabel"]:has(+ * input:disabled) *{color:var(--text-off)!important;cursor:not-allowed;}
[data-testid="stSlider"] [data-testid="stSliderThumbValue"], [data-testid="stSlider"] [data-testid="stTickBarMin"], [data-testid="stSlider"] [data-testid="stTickBarMax"]{color:var(--amber)!important;}

/* Expanders: Cost Master fixed / variable bands, provenance, estimate notes... */
[data-testid="stExpander"]{background-color:var(--card)!important;border:1px solid var(--mid)!important;border-radius:6px;}
[data-testid="stExpander"] details, [data-testid="stExpander"] details > summary{background-color:var(--card)!important;color:var(--light)!important;border-radius:6px;}
[data-testid="stExpander"] summary *{color:var(--light)!important;}
[data-testid="stExpander"] summary svg{fill:var(--amber)!important;color:var(--amber)!important;}
[data-testid="stExpander"] summary:hover, [data-testid="stExpander"] summary:hover *{background-color:var(--mid)!important;color:var(--amber)!important;}
[data-testid="stExpander"] summary:focus-visible{outline:2px solid var(--amber);outline-offset:-2px;}
[data-testid="stExpander"] details[open] > summary{border-bottom:1px solid var(--gold);border-radius:6px 6px 0 0;}
[data-testid="stExpanderDetails"]{background-color:var(--card)!important;}

/* Alerts (info / success / warning / error): dark tinted background + light text, bright border */
[data-testid="stAlert"], [data-testid="stAlertContainer"]{background-color:#13233F!important;border:1px solid var(--mid)!important;border-left:4px solid var(--gold)!important;border-radius:6px;}
[data-testid="stAlert"] *, [data-testid="stAlertContainer"] *{color:var(--light)!important;}
[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]){background-color:#3A2A10!important;border-left-color:#FBBF24!important;}
[data-testid="stAlert"]:has([data-testid="stAlertContentError"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]){background-color:#3A1010!important;border-left-color:#F87171!important;}
[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]){background-color:#163A2A!important;border-left-color:#4ADE80!important;}
[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]), [data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]){background-color:#102A4D!important;border-left-color:#60A5FA!important;}
[data-testid="stDataFrame"]{border:1px solid var(--mid);border-radius:6px;}

/* Phones */
@media (max-width: 640px){
  .main-title{font-size:1.25rem;letter-spacing:.04em;}
  .sub-title{font-size:.72rem;letter-spacing:.06em;margin-bottom:1rem;}
  .metric-value{font-size:1.3rem;} [data-testid="stMetricValue"]{font-size:1.2rem!important;}
  .total-banner{padding:1rem;} .metric-card{padding:.8rem .9rem;}
  [data-baseweb="tab-list"]{overflow-x:auto;}
  [data-testid="stMainBlockContainer"], .block-container{padding-left:.8rem!important;padding-right:.8rem!important;}
  [data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"]{min-height:44px;}
}
</style>""", unsafe_allow_html=True)

# ─── LOGO ────────────────────────────────────────────────────────────────────
def _get_logo():
    """Menkor logo as base64. Bundled file first (menkor_logo.png next to app.py or in static/), GitHub URL only as fallback."""
    try:
        from pathlib import Path
        here = Path(__file__).resolve().parent
        for p in (here / "menkor_logo.png", here / "static" / "menkor_logo.png"):
            if p.exists():
                return base64.b64encode(p.read_bytes()).decode()
    except Exception:
        pass
    try:
        import urllib.request
        url = "https://raw.githubusercontent.com/gregorydebeure/aviation-cost-estimato/main/menkor_logo.png"
        with urllib.request.urlopen(url, timeout=4) as r:
            return base64.b64encode(r.read()).decode()
    except Exception:
        return ""

# ─── DATABASE & ENGINE (v15 — 165 models, single calculation engine) ─────────
# All numbers on every screen and in the PDF come from menkor_engine.compute().
# The old embedded 47-model table, the FUEL_BURN_GPH estimates, the 0.82 private
# coefficient and the generic CM_OP/CM_DIR/CM_IND amounts have been removed.
import menkor_engine as E
import menkor_report as RPT


@st.cache_data(show_spinner=False)
def get_base():
    return E.load_base()


@st.cache_data(show_spinner=False)
def get_support():
    return E.load_checks(), E.load_conflicts(), E.load_conversions()


@st.cache_data(show_spinner=False)
def get_prov():
    return E.load_provenance()


@st.cache_data(show_spinner=False)
def get_aliases():
    return E.load_aliases()


@st.cache_data(show_spinner=False)
def get_charter_prices():
    return E.load_charter_prices()


def get_active_db():
    return get_base()


# ─── CHARTS (all read the engine result; amounts converted by the Display object) ──
C={"fixed":"#1A3A6E","crew":"#C9A84C","charter":"#4A90D9","private":"#8496B0","profit":"#4ADE80","loss":"#F87171","fuel":"#F97316","nonfuel":"#4A90D9"}
BG=dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#D6E4F7"))
_PAL={"Fixed":["#1A3A6E","#2F5DA8","#4A7FD0","#7FA6E8","#B7CDF3","#DCE7FA"],
      "Variable":["#F97316","#4A90D9","#C9A84C","#60A5FA","#A78BFA","#4ADE80","#F87171","#93C5FD"]}

def chart_donut(res,disp):
    v=res["variable"]; fx=res["fixed"]["annual_total"]
    fuel=res["fuel"].get("annual_cost_usd") if res.get("fuel") else None
    labels=["Fixed (incl. crew)"]; values=[fx]; colors=[C["fixed"]]
    if fuel is not None:
        labels+=["Fuel","Other variable"]; values+=[fuel,v["annual"]-fuel]; colors+=[C["fuel"],C["nonfuel"]]
    else:
        labels+=["Variable (fuel not separable)"]; values+=[v["annual"]]; colors+=[C["nonfuel"]]
    values=[disp.conv(x) for x in values]
    fig=go.Figure(go.Pie(labels=labels,values=values,hole=0.56,marker=dict(colors=colors,line=dict(color="#0B1629",width=2)),
                         textinfo="label+percent",textfont=dict(size=11,color="#D6E4F7")))
    fig.add_annotation(text=f"<b>{disp.sym}{disp.conv(res['budget_usd'])/1e6:.2f}M</b>",x=0.5,y=0.5,showarrow=False,font=dict(size=16,color="#E8C46A"))
    fig.update_layout(**BG,height=320,margin=dict(t=10,b=10,l=10,r=10),legend=dict(orientation="h",yanchor="bottom",y=-0.2,bgcolor="rgba(0,0,0,0)"))
    return fig

def chart_per_hour(res,disp):
    H=res["hours"]["flown"] or 0
    if not H: return None
    fx_h=res["fixed"]["annual_total"]/H; v=res["variable"]
    fig=go.Figure()
    fig.add_bar(name="Fixed ÷ hours",x=["Cost per flown hour"],y=[disp.conv(fx_h)],marker_color=C["fixed"])
    if v.get("fuel_per_h") is not None:
        fig.add_bar(name="Fuel",x=["Cost per flown hour"],y=[disp.conv(v["fuel_per_h"])],marker_color=C["fuel"])
        fig.add_bar(name="Other variable",x=["Cost per flown hour"],y=[disp.conv(v["nonfuel_per_h"])],marker_color=C["nonfuel"])
    else:
        fig.add_bar(name="Variable",x=["Cost per flown hour"],y=[disp.conv(v["per_h"])],marker_color=C["nonfuel"])
    fig.update_layout(barmode="stack",**BG,height=300,margin=dict(t=10,b=40,l=10,r=10),
                      yaxis=dict(title=f"{disp.ccy} per flown hour",gridcolor="#1A3A6E",tickformat=",.0f"),
                      legend=dict(orientation="h",yanchor="bottom",y=-0.35,bgcolor="rgba(0,0,0,0)"))
    return fig

def chart_waterfall(res,disp):
    pr=res["profit"]
    fig=go.Figure(go.Waterfall(
        measure=["relative","relative","relative","relative","total"],
        x=["Charter revenue","Commission + fees","Variable (all flown h)","Fixed","Operating result"],
        y=[disp.conv(pr["revenue"]),-disp.conv(pr["commission"]+pr["other_fees"]),-disp.conv(pr["variable_cost_all_flown"]),-disp.conv(pr["fixed_cost"]),disp.conv(pr["operating_result"])],
        connector=dict(line=dict(color="#1A3A6E",width=1.5)),
        increasing=dict(marker_color=C["profit"]),decreasing=dict(marker_color=C["loss"]),
        totals=dict(marker_color=C["profit"] if pr["operating_result"]>=0 else C["loss"]),
        texttemplate="%{y:+,.0f}",textfont=dict(color="#D6E4F7",size=11)))
    fig.add_hline(y=0,line_dash="dash",line_color="#8496B0",line_width=1)
    fig.update_layout(**BG,height=340,margin=dict(t=10,b=10,l=10,r=10),yaxis=dict(title=disp.ccy,gridcolor="#1A3A6E",tickformat=",.0f"),xaxis=dict(gridcolor="rgba(0,0,0,0)"))
    return fig

def chart_sensitivity(points,be,current,disp):
    xs=[p[0] for p in points]; ys=[disp.conv(p[1]) if p[1] is not None else None for p in points]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines",line=dict(color=C["charter"],width=2.5),fill="tozeroy",fillcolor="rgba(74,144,217,0.12)"))
    fig.add_hline(y=0,line_dash="dash",line_color="#C9A84C",line_width=1.5)
    if be is not None:
        fig.add_vline(x=be,line_dash="dot",line_color="#E8C46A",line_width=1.5,annotation_text=f"Coverage threshold ≈ {be:,.0f} billed h",annotation_font_color="#E8C46A")
    fig.add_vline(x=current,line_dash="dot",line_color="#8496B0",line_width=1,annotation_text="current",annotation_position="bottom right",annotation_font_color="#8496B0")
    fig.update_layout(**BG,height=300,margin=dict(t=10,b=10,l=10,r=10),showlegend=False,
                      yaxis=dict(title=f"Operating result ({disp.ccy})",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Billed charter hours",gridcolor="#1A3A6E"))
    return fig

def chart_fuel_sens(points,disp,base_price):
    xs=[p[0] for p in points]; ys=[disp.conv(p[1]) if p[1] is not None else None for p in points]
    fig=go.Figure(go.Scatter(x=xs,y=ys,mode="lines+markers",line=dict(color=C["fuel"],width=2.5)))
    if base_price: fig.add_vline(x=base_price,line_dash="dot",line_color="#8496B0",line_width=1,annotation_text="current",annotation_font_color="#8496B0")
    fig.update_layout(**BG,height=280,margin=dict(t=10,b=10,l=10,r=10),showlegend=False,
                      yaxis=dict(title=f"Total cost per flown hour ({disp.ccy})",gridcolor="#1A3A6E",tickformat=",.0f"),
                      xaxis=dict(title="Fuel price (USD per litre)",gridcolor="#1A3A6E"))
    return fig

def cm_donut(res,disp,category):
    rows=[c for c in res["components"] if c["category"]==category and c["annual_usd"]>0 and not c.get("rounding")]
    if not rows: return None
    pal=_PAL[category]
    fig=go.Figure(go.Pie(labels=[c["label"] for c in rows],values=[disp.conv(c["annual_usd"]) for c in rows],hole=0.54,
        marker=dict(colors=[pal[i%len(pal)] for i in range(len(rows))],line=dict(color="#0B1629",width=2)),
        textinfo="percent",textfont=dict(size=10,color="#D6E4F7")))
    tot=sum(disp.conv(c["annual_usd"]) for c in rows)
    fig.add_annotation(text=f"<b>{disp.sym}{tot/1000:,.0f}K</b>",x=0.5,y=0.5,showarrow=False,font=dict(size=14,color="#E8C46A"))
    fig.update_layout(**BG,height=320,margin=dict(t=10,b=10,l=5,r=5),legend=dict(orientation="h",yanchor="bottom",y=-0.45,bgcolor="rgba(0,0,0,0)",font=dict(size=9)))
    return fig

def cm_bar(res,disp,category,title):
    rows=sorted([c for c in res["components"] if c["category"]==category and c["annual_usd"]>0 and not c.get("rounding")],key=lambda c:-c["annual_usd"])
    if not rows: return None
    vals=[disp.conv(c["annual_usd"]) for c in rows]
    fig=go.Figure(go.Bar(x=[c["label"] for c in rows],y=vals,marker_color="#F59E0B" if category=="Fixed" else "#60A5FA",
        text=[f"{disp.sym}{v:,.0f}" for v in vals],textposition="outside",textfont=dict(size=9,color="#D6E4F7")))
    fig.update_layout(**BG,height=300,margin=dict(t=30,b=60,l=10,r=10),title=dict(text=title,font=dict(size=11,color="#8496B0"),x=0),
                      yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f",title=disp.ccy),xaxis=dict(tickangle=-30,gridcolor="rgba(0,0,0,0)"))
    return fig

# ─── PDF (built by menkor_report from the engine result) ─────────────────────
def generate_pdf_report(res,disp,alerts):
    logo=_get_logo()
    return RPT.build_report_pdf(res,disp,alerts,base64.b64decode(logo) if logo else None)


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
DAY_PASS_PRICES_CENTS = {"essentiel":1000, "pro":5000}  # 10€ / 50€
DAY_PASS_HOURS = 48
DAY_PASS_LABELS = {"essentiel":"Day Pass Essentiel — €10 (48h)", "pro":"Day Pass Pro — €50 (48h)"}

def _get_active_day_pass(email):
    """Returns the active one-time day-pass tier ('essentiel'/'pro') for this user, or None if expired/absent.
    Reads the already-fetched Supabase user record — no extra Stripe call, cheap to call on every rerun."""
    try:
        import datetime
        rec=_sb_get_user(email) or {}
        tier=rec.get("pass_tier"); exp_raw=rec.get("pass_expires_at")
        if not tier or not exp_raw: return None
        exp=datetime.datetime.fromisoformat(str(exp_raw).replace("Z","+00:00"))
        now=datetime.datetime.now(exp.tzinfo) if exp.tzinfo else datetime.datetime.utcnow()
        return tier if exp>now else None
    except Exception: return None

def _day_pass_checkout_url(email,tier):
    """One-time Stripe payment for a 48h all-access pass at the given tier. Returns (url, error)."""
    try:
        import stripe
    except ImportError:
        return None,"The 'stripe' package isn't installed on the server (check requirements.txt)."
    try:
        key=st.secrets.get("STRIPE_SECRET_KEY")
        if not key: return None,"STRIPE_SECRET_KEY is missing/empty in this app's secrets."
        amount=DAY_PASS_PRICES_CENTS.get(tier)
        if not amount: return None,f"Unknown day pass tier: {tier}"
        stripe.api_key=key
        s=stripe.checkout.Session.create(
            mode="payment", customer_email=email,
            line_items=[{"price_data":{"currency":"eur","unit_amount":amount,
                "product_data":{"name":f"Aviation Cost Estimator — {DAY_PASS_LABELS.get(tier,tier)}"}},"quantity":1}],
            metadata={"type":"day_pass","tier":tier,"email":email},
            success_url="https://aviation-cost-estimator.onrender.com/?pass_session={CHECKOUT_SESSION_ID}",
            cancel_url="https://aviation-cost-estimator.onrender.com/?cancelled=1")
        return s.url,None
    except Exception as e:
        return None,f"{type(e).__name__}: {e}"

def _process_day_pass_return():
    """Call once near the top of main(): if the URL carries ?pass_session=... from a completed Stripe
    Checkout redirect, verify the payment server-side and grant the 48h pass. Never trusts the URL alone."""
    try:
        sess_id=st.query_params.get("pass_session")
        if not sess_id: return
        import stripe,datetime
        stripe.api_key=st.secrets.get("STRIPE_SECRET_KEY","")
        s=stripe.checkout.Session.retrieve(sess_id)
        if s.get("payment_status")=="paid":
            meta=s.get("metadata",{}) or {}
            tier=meta.get("tier")
            email=((s.get("customer_details") or {}).get("email") or meta.get("email") or "").strip().lower()
            if email and tier in ("essentiel","pro"):
                expires=(datetime.datetime.utcnow()+datetime.timedelta(hours=DAY_PASS_HOURS)).isoformat()+"Z"
                _sb_update_user(email,{"pass_tier":tier,"pass_expires_at":expires})
                st.session_state["_day_pass_toast"]=(tier,DAY_PASS_HOURS)
                if st.session_state.get("auth_email","").strip().lower()==email:
                    st.session_state["auth_pass_tier"]=tier
        st.query_params.clear()
    except Exception:
        pass

def _check_sub(email):
    """Returns 'pro', 'essentiel', or None based on any active Stripe subscription for this email.
    IMPORTANT: Stripe Checkout creates a brand-new Customer object every time it's given customer_email
    without an existing customer id — so the same person can end up with several Customer records
    under one email (visible side-by-side in the Stripe Dashboard → Clients). We must check ALL of
    them, not just the first one ever seen/cached, or a subscription paid under a newer customer
    object is silently missed forever even though the payment went through."""
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        pro_price=st.secrets.get("STRIPE_PRICE_PRO",""); ess_price=st.secrets.get("STRIPE_PRICE_ESSENTIEL","")
        custs=stripe.Customer.list(email=email,limit=25)
        if not custs.data: return None
        plan=None; active_cid=None
        for cust in custs.data:
            subs=stripe.Subscription.list(customer=cust.id,status="active",limit=10)
            for sub in subs.data:
                for item in sub["items"]["data"]:
                    pid=item["price"]["id"]
                    if pid==pro_price: plan="pro"; active_cid=cust.id
                    elif pid==ess_price and plan!="pro": plan="essentiel"; active_cid=active_cid or cust.id
            if plan=="pro": break
        if active_cid: _sb_update_user(email,{"stripe_cid":active_cid})
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
        # No payment_method_types here: newer Stripe accounts manage accepted payment methods from the
        # Dashboard (Settings → Payment methods) and reject this parameter on Checkout Session creation.
        s=stripe.checkout.Session.create(mode="subscription",
            customer_email=email,line_items=[{"price":price,"quantity":1}],metadata={"plan":plan},
            success_url=f"https://aviation-cost-estimator.onrender.com/?subscribed={plan}",
            cancel_url="https://aviation-cost-estimator.onrender.com/?cancelled=1")
        return s.url,None
    except Exception as e:
        return None,f"{type(e).__name__}: {e}"

def _market_search_checkout_url(email, meta):
    try:
        import stripe; stripe.api_key=st.secrets["STRIPE_SECRET_KEY"]
        # No payment_method_types here: newer Stripe accounts manage accepted payment methods from the
        # Dashboard (Settings → Payment methods) and reject this parameter on Checkout Session creation.
        s=stripe.checkout.Session.create(
            mode="payment", customer_email=email,
            line_items=[{"price_data":{"currency":"eur","unit_amount":30000,
                "product_data":{"name":"Personalized Aircraft Market Search"}},"quantity":1}],
            metadata=meta,
            success_url="https://aviation-cost-estimator.onrender.com/?market_submitted=1",
            cancel_url="https://aviation-cost-estimator.onrender.com/?market_cancelled=1")
        return s.url
    except Exception as e:
        st.warning("Payment couldn't be started right now. Please try again in a moment, or contact support if this keeps happening.")
        if st.session_state.get("auth_is_admin"): st.caption(f"Admin detail: {type(e).__name__}: {e}")
        return None

def _plan_buttons(email,current_plan=None,show_day_pass=True):
    """Renders a subscribe button for every plan tier above the user's current one, plus (optionally)
    one-time 48h day-pass options for occasional users who don't want a monthly commitment.
    On failure, the customer only ever sees a gentle message — the real Stripe error is shown to admins only."""
    is_admin=st.session_state.get("auth_is_admin",False)
    def _fail(label,err):
        st.warning(f"⚠ {label} checkout isn't available right now. Please try again shortly, or contact support if this persists.")
        if is_admin: st.caption(f"Admin detail: {err}")
    st.markdown('<div style="font-size:.74rem;color:#8496B0;text-align:center;margin:.3rem 0 .2rem 0;letter-spacing:.06em;text-transform:uppercase">Monthly subscription</div>',unsafe_allow_html=True)
    if current_plan not in ("essentiel","pro"):
        url,err=_checkout_url(email,"essentiel")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.3rem"><a href="{url}" target="_blank" style="display:block;background:#1A3A6E;color:#D6E4F7;border:1px solid #8496B0;padding:.5rem 1.2rem;border-radius:5px;font-weight:600;text-decoration:none">Essentiel — 15€/month</a></div>', unsafe_allow_html=True)
        else: _fail("Essentiel",err)
    if current_plan!="pro":
        url,err=_checkout_url(email,"pro")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.5rem"><a href="{url}" target="_blank" style="display:block;background:#C9A84C;color:#0B1629;padding:.5rem 1.2rem;border-radius:5px;font-weight:700;text-decoration:none">⭐ {"Upgrade to Pro" if current_plan=="essentiel" else "Pro"} — 50€/month</a></div>', unsafe_allow_html=True)
        else: _fail("Pro",err)
    if show_day_pass and current_plan!="pro":
        st.markdown('<div style="font-size:.74rem;color:#8496B0;text-align:center;margin:.8rem 0 .2rem 0;letter-spacing:.06em;text-transform:uppercase">Or, for a single one-off deal</div>',unsafe_allow_html=True)
        st.markdown('<div style="font-size:.72rem;color:#8496B0;text-align:center;margin-bottom:.3rem">No commitment — full access for 48h, then it locks again.</div>',unsafe_allow_html=True)
        url,err=_day_pass_checkout_url(email,"essentiel")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.3rem"><a href="{url}" target="_blank" style="display:block;background:transparent;color:#D6E4F7;border:1px dashed #8496B0;padding:.45rem 1.2rem;border-radius:5px;font-weight:600;text-decoration:none">{DAY_PASS_LABELS["essentiel"]}</a></div>', unsafe_allow_html=True)
        else: _fail("Day Pass Essentiel",err)
        url,err=_day_pass_checkout_url(email,"pro")
        if url: st.markdown(f'<div style="text-align:center;margin-top:.4rem"><a href="{url}" target="_blank" style="display:block;background:transparent;color:#E8C46A;border:1px dashed #C9A84C;padding:.45rem 1.2rem;border-radius:5px;font-weight:600;text-decoration:none">{DAY_PASS_LABELS["pro"]}</a></div>', unsafe_allow_html=True)
        else: _fail("Day Pass Pro",err)

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
                _ap=st.session_state.get("auth_pass_tier")
                if _ap: st.caption(f"⏱ {_ap.capitalize()} day pass active")
            if st.button("🚪 Log out",key="logout",width="stretch"):
                st.session_state["auth_email"]=None; st.session_state["auth_plan"]=None
                st.session_state["auth_is_admin"]=False; st.session_state["auth_pass_tier"]=None; st.rerun()
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
                                _em=em.strip().lower()
                                st.session_state["auth_email"]=_em
                                st.session_state["auth_plan"]=_check_sub(_em)
                                st.session_state["auth_pass_tier"]=_get_active_day_pass(_em)
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

# ─── THRESHOLD, COSTS SCOPE, MANUAL BUDGET OFFER ─────────────────────────────

def _render_one_threshold(th,title,title_fr,show_assumptions=True):
    st.markdown(f"**{title}**  ·  *{title_fr}*")
    stt=th.get("status")
    if stt=="awaiting_confirmation": st.info(th["message"]); return
    if stt in ("ratio_undefined",): st.warning(th["message"]); return
    if stt=="incomplete": st.warning(th["message"]); return
    if stt=="unattainable": st.error(th["message"])
    elif stt=="exceeds_year": st.warning(th["message"])
    else: st.success(th["message"])
    if stt in ("ok","exceeds_year"):
        t1,t2,t3,t4=st.columns(4)
        t1.metric("Billed hours (rounded up)",f"{th['billed_hours']:,d} h"); t2.metric("Total flown hours",f"{th['flown_hours']:,.0f} h")
        t3.metric("Positioning",f"{th['positioning_flown']:,.0f} h"); t4.metric("Private / other",f"{th['private_hours']:g} h")
    if show_assumptions and th.get("assumptions"): st.caption("Assumptions — "+th["assumptions"])

def _render_threshold(pr,D):
    """Thresholds A (operating costs entered) and B (with the economic ownership costs entered) — same engine values as PDF/CSV; nothing before confirmation."""
    th=pr.get("threshold") or {}; te=pr.get("threshold_economic") or {}
    _render_one_threshold(th,E.THRESHOLD_LABEL,E.THRESHOLD_LABEL_FR)
    st.caption(E.THRESHOLD_NOTE)
    if th.get("status") in ("awaiting_confirmation","ratio_undefined"): return
    st.markdown("<hr>",unsafe_allow_html=True)
    _render_one_threshold(te,E.THRESHOLD_ECON_LABEL,E.THRESHOLD_ECON_LABEL_FR,show_assumptions=False)
    if te.get("status") in ("ok","exceeds_year") and pr.get("economic_result") is not None:
        e1,e2=st.columns(2); e1.metric("Economic ownership costs entered",D(pr["ownership_costs_total"])); e2.metric("Economic result (operating result − ownership costs)",D(pr["economic_result"]))
    st.caption(E.OWNERSHIP_NOTE+" Revenue paid by the owner to the operator for the owner's own flights is not external charter revenue and does not reduce the owner's consolidated cost.")

def _render_costs_scope(row,res,scn,D,where="scope"):
    """Block 'Costs included & limitations'."""
    sc=E.costs_scope(row,res,scn)
    with st.expander("📋 Costs included & limitations",expanded=False):
        st.markdown("**Included in the simulation**")
        for c in sc["included"]:
            st.markdown("• "+c["label"]+(f" — {D(c['annual_usd'])} / year" if c.get("annual_usd") is not None else "")+(f" ({D(c['hourly_usd'])} per flown hour)" if c.get("hourly_usd") is not None else ""))
        st.markdown("**Not confirmed** (unknown is never shown as zero)")
        for t in sc["not_confirmed"]: st.markdown("• "+t)
        st.markdown("**Known exclusions**")
        for t in sc["exclusions"]: st.markdown("• "+t)
        st.markdown("**Limitations**")
        for t in sc["limits"]: st.markdown("• "+t)
        _render_budget_cta(res["model"],where)
    return sc

BUDGET_OFFER_TITLE="Aircraft-specific operating budget"
BUDGET_OFFER_TEXT=("Get a tailored operating budget based on the aircraft's serial number, maintenance status, programme coverage and your intended operation. "
                   "Prepared manually by Menkor Aviation.")
BUDGET_DELIVERABLES=["Detailed operating budget.","Recurring costs and identified exceptional expenses over three years.",
                     "First-year cash flow shown separately from the smoothed economic budget.","Private and charter scenarios.",
                     "Net cost remaining to the owner after the charter contribution.",
                     "Assumptions, missing documents and points to confirm with the CAMO / MRO."]
BUDGET_DISCLAIMER=("This is a manually prepared budget study. It is not a pre-purchase inspection (PPI), a technical or airworthiness validation, or a guarantee of costs. "
                   "Technical documents may be requested after the first exchange; do not send sensitive files through this form.")
BUDGET_CONFIG_HELP=("Reception is not configured: set RESEND_API_KEY and ADMIN_EMAIL (existing secrets; optionally BUDGET_REQUEST_TO to receive these requests "
                    "at another address) in the app secrets. Until then no request can be transmitted.")

def _send_budget_request(data,secrets=None,post=None):
    """Transmit a budget request by email through the existing Resend channel. Returns (ok, detail).
    ok is True ONLY after a successful transmission; a missing configuration or any failure returns False (never 'sent')."""
    import html as _html
    try:
        sec=secrets if secrets is not None else st.secrets
        key=sec.get("RESEND_API_KEY"); to=sec.get("BUDGET_REQUEST_TO") or sec.get("ADMIN_EMAIL")
    except Exception:
        key=to=None
    if not key or not to: return False,"not_configured"
    rows="".join(f"<tr><td style='padding:2px 10px 2px 0'><b>{_html.escape(k)}</b></td><td>{_html.escape(str(v) or '-')}</td></tr>" for k,v in data.items())
    try:
        if post is None:
            import requests; post=requests.post
        r=post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {key}","Content-Type":"application/json"},
               json={"from":"Aviation Cost Estimator <onboarding@resend.dev>","to":[to],"reply_to":data.get("Email",""),
                     "subject":f"Aircraft-specific operating budget request — {data.get('Aircraft model','')}",
                     "html":f"<p>Budget request received from the Aviation Cost Estimator:</p><table>{rows}</table>"},timeout=8)
        if r.status_code in (200,201): return True,""
        return False,f"HTTP {r.status_code}"
    except Exception as e:
        return False,f"{type(e).__name__}"

def _budget_form(model_name,where):
    """Single request path: one button, one inline form (no extra window). `where` makes the widget keys unique per place."""
    if st.button("Request a budget for your aircraft",key=f"bq_open_{where}"): st.session_state[f"_bq_open_{where}"]=True
    if not st.session_state.get(f"_bq_open_{where}"): return
    with st.form(f"budget_request_form_{where}"):
        f1,f2=st.columns(2)
        with f1: nm=st.text_input("Name",key=f"bq_name_{where}")
        with f2: em=st.text_input("Email",key=f"bq_email_{where}")
        g1,g2,g3=st.columns(3)
        with g1: md=st.text_input("Aircraft model",value=model_name,key=f"bq_model_{where}")
        with g2: yr=st.text_input("Year (optional)",key=f"bq_year_{where}")
        with g3: msn=st.text_input("MSN (optional at first contact)",key=f"bq_msn_{where}")
        base=st.text_input("Intended region / base",key=f"bq_base_{where}")
        h1,h2=st.columns(2)
        with h1: hp=st.text_input("Planned private hours per year (if known)",key=f"bq_hp_{where}")
        with h2: hc=st.text_input("Planned charter hours per year (if known)",key=f"bq_hc_{where}")
        own=st.radio("Aircraft status",["Already owned","Acquisition project"],key=f"bq_own_{where}",horizontal=True)
        prog=st.text_input("Known programmes (if available)",key=f"bq_prog_{where}")
        msg=st.text_area("Message",key=f"bq_msg_{where}",max_chars=1500)
        st.caption("Technical documents may be requested after the first exchange. Please do not send sensitive files through this form.")
        sub=st.form_submit_button("Send request")
    if sub:
        if not (nm.strip() and em.strip() and md.strip()): st.warning("Please fill in name, email and aircraft model."); return
        if not _re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+",em.strip()): st.warning("Please enter a valid email address."); return
        data={"Name":nm.strip(),"Email":em.strip(),"Aircraft model":md.strip(),"Year":yr.strip(),"MSN":msn.strip(),"Region / base":base.strip(),
              "Private hours / year":hp.strip(),"Charter hours / year":hc.strip(),"Status":own,"Known programmes":prog.strip(),"Message":msg.strip()[:1500]}
        ok,detail=_send_budget_request(data)
        if ok: st.success("Your request has been transmitted to Menkor Aviation. We will contact you to confirm the next steps.")
        elif detail=="not_configured": st.error("Your request could not be sent: reception is not configured on this installation. No request has been recorded. "
                                                "Please try again later or contact Menkor Aviation directly."); st.caption(BUDGET_CONFIG_HELP)
        else: st.error(f"Your request could not be sent ({detail}). No request has been recorded: please try again later.")

def _render_budget_cta(model_name,where):
    """Compact call-to-action next to the limits / the coverage result."""
    st.caption("These figures use average costs, not the budget of your aircraft. "+BUDGET_OFFER_TEXT)
    _budget_form(model_name,where)

def _render_budget_offer(model_name,where="offer"):
    st.markdown(f'<div class="section-header">✈ {BUDGET_OFFER_TITLE}</div>',unsafe_allow_html=True)
    st.markdown(f'''<div class="metric-card"><div class="metric-sub" style="font-size:.9rem;color:#D6E4F7">{BUDGET_OFFER_TEXT}</div></div>''',unsafe_allow_html=True)
    st.markdown("**What you receive**")
    for t in BUDGET_DELIVERABLES: st.markdown("• "+t)
    st.caption(BUDGET_DISCLAIMER)
    _budget_form(model_name,where)

# ─── MAIN ────────────────────────────────────────────────────────────────────


def _on_search():
    """Quick find: resolves an id, a model name or an alias (e.g. 'Global 7000' -> Global 7500) to ONE aircraft."""
    q=st.session_state.get("ac_search","")
    aid=E.resolve_alias(q,get_base(),get_aliases())
    if aid:
        st.session_state["ac_cat"]="All"; st.session_state["ac_sel"]=aid
        al=get_aliases(); hit=al[al["alias"].str.lower()==q.strip().lower()]
        st.session_state["ac_search_note"]=(f"'{hit.iloc[0]['alias']}' is a {hit.iloc[0]['relationship'].replace('_',' ')} of {hit.iloc[0]['canonical_model']} — showing that aircraft (no separate aircraft)."
                                            if len(hit) else f"Showing {aid}.")
    else:
        st.session_state["ac_search_note"]=f"No aircraft or alias matches '{q}'." if q.strip() else ""
    st.session_state["ac_search"]=""

_KEEP_KEYS=("q_margin","fleet_mf")   # widgets only shown in Custom simulation: their value survives a visit to Report reference

def _bump_overrides():
    st.session_state["_ov_ver"]=st.session_state.get("_ov_ver",0)+1

def _render_alerts(res,alerts,title="Data status & alerts"):
    """Alerts next to the results: errors/warnings are visible, informational notes are in an expander."""
    shown=[x for x in res["flags"] if x["level"] in ("error","warn")]+[a for a in alerts if a["level"] in ("error","warn")]
    for x in shown:
        (st.error if x["level"]=="error" else st.warning)(x["text"])
    infos=[x for x in res["flags"] if x["level"]=="info"]+[a for a in alerts if a["level"]=="info"]
    if infos:
        with st.expander(f"ℹ {title} — {len(infos)} note(s)"):
            for x in infos: st.markdown(f"- {x['text']}")

def _prov_table(row,prov):
    """Key fields with their data class: extracted / calculated / converted / normalized / missing / historical."""
    if not bool(row["has_detail"]):
        rows=[]
        for f,u in [("legacy_Couts_Fixes_Annuels","annual (currency undocumented)"),("legacy_Cout_Horaire_Charter","per hour (currency undocumented)"),
                    ("legacy_Heures_Base","hours"),
                    ("legacy_Vitesse_Croisiere_km_h","km/h"),("legacy_Autonomie_km","km (definition unverified)"),("legacy_Passagers_Max","pax")]:
            v=E.num(row,f)
            rows.append({"Field":f.replace("legacy_",""),"Value":"missing" if v is None else f"{v:,.0f}","Unit":u,"Data class":"Historical" if v is not None else "Missing","Source":row.get("source_file"),"Page":""})
        return pd.DataFrame(rows)
    p=E.provenance_for(prov,row)
    keep=E.KEY_FIELDS+["fuel_burn_from_annual_l_per_h","nonfuel_variable_cost_per_h_usd","fuel_price_implied_usd_per_l","total_cost_per_h_from_annual_usd","currency"]
    p=p[p["field"].isin(keep)].copy()
    p["Data class"]=p["status"].map(E.data_class)
    out=p.rename(columns={"field":"Field","value":"Value","unit":"Unit","source_file":"Source","source_page":"Page"})[["Field","Value","Unit","Data class","Source","Page"]]
    out["Value"]=out["Value"].fillna("missing")
    out["Source"]=out["Source"].map(E.public_source)
    _of={c[len(E.ORIGINAL_PREFIX):] for c in row.index if isinstance(c,str) and c.startswith(E.ORIGINAL_PREFIX)}
    def _base_val(f):
        if f not in _of: return ""
        v=E.num(row,f); o=E.num(E.original_view(row),f)
        return f"{v:,.2f}" if (v is not None and o is not None and abs(v-o)>1e-9) else ""
    out["Menkor base value"]=out["Field"].map(_base_val)
    return out.reset_index(drop=True)

def _results_csv(res,disp):
    """CSV export of the current result with its assumptions and exchange rate (same engine result as screen/PDF)."""
    rows=[("config_id",res["config_hash"]),("aircraft_id",res["aircraft_id"]),("model",res["model"]),("mode",res["mode"]),
          ("source","Menkor reference database"),("record_type",E.source_label(res.get("source_kind"))),
          ("menkor_base_version",res["menkor_base"].get("version")),("menkor_base_adjustment_applied_in_this_result",res["menkor_base"]["applied"]),
          ("menkor_base_adjustment_pct",res["menkor_base"].get("pct")),("menkor_base_adjustment_status",res["menkor_base"].get("status")),
          ("menkor_base_text",res["menkor_base"].get("text","")),("original_published_budget_usd",res["menkor_base"].get("published_budget_original")),
          ("menkor_base_delta_budget_usd",res["menkor_base"].get("delta_total")),
          ("economic_reference_date",(res.get("dates") or {}).get("economic_reference_date","unknown")),
          ("consultation_date",(res.get("dates") or {}).get("consultation_date") or ""),("extraction_date",(res.get("dates") or {}).get("extraction_date") or ""),
          ("web_source_url",(res.get("web_source") or {}).get("url","")),("web_source_consulted",(res.get("web_source") or {}).get("access_date","")),
          ("source_currency","USD"),("display_currency",disp.ccy),("usd_to_eur_rate",disp.fx.usd_to_eur if disp.ccy=="EUR" else ""),
          ("rate_date",disp.fx.rate_date if disp.ccy=="EUR" else ""),("hours_flown",res["hours"]["flown"]),
          ("annual_fixed_usd",res["fixed"].get("annual_total")),("variable_per_hour_usd",res["variable"].get("per_h")),
          ("annual_variable_usd",res["variable"].get("annual")),("annual_budget_usd",res["budget_usd"]),("cost_per_hour_usd",res["cost_per_h_usd"])]
    if res.get("fuel"):
        f=res["fuel"]; rows+=[("fuel_burn_l_per_h",f.get("burn_l_h")),("fuel_price_usd_per_l",f.get("price_usd_l")),("fuel_price_source",f.get("price_source"))]
        _av=f.get("average")
        if _av:
            rows+=[("fuel_price_nature","Average fuel price - annual planning assumption entered by the user (includes applicable fuel taxes and fees per operating habits); not a verified local price, not a real-time price"),
                   ("fuel_average_price_per_litre",_av["price"]),("fuel_average_price_currency",_av["currency"]),
                   ("fuel_average_price_usd_per_litre",_av["price_usd_l"]),("fuel_average_fx_usd_to_eur",_av.get("fx_rate") or ""),("fuel_average_fx_date",_av.get("fx_date") or "")]
    _bm=(res.get("fuel") or {}).get("benchmark")
    if _bm:
        rows+=[("fuel_price_method","Regional market benchmark"),("fuel_benchmark_region",_bm["region"]),("fuel_benchmark_region_id",_bm["region_id"]),
               ("fuel_benchmark_period",_bm["period_label"]),("fuel_benchmark_period_start",_bm["period_start"]),("fuel_benchmark_period_end",_bm["period_end"]),
               ("fuel_benchmark_source",_bm["benchmark"]),("fuel_benchmark_source_url",_bm["url_1"]),
               ("fuel_benchmark_price_us_cents_per_us_gallon",_bm["source_cents_usg"]),("fuel_benchmark_price_usd_per_l",_bm["benchmark_usd_l"]),
               ("fuel_price_used_usd_per_l",_bm["used_usd_l"]),("fuel_price_currency_unit",_bm["unit"]),("fuel_price_user_adjusted",_bm["user_adjusted"]),
               ("fuel_price_qualification","user hypothesis" if _bm["user_adjusted"] else "refinery reference"),
               ("fuel_price_disclaimer",_bm["disclaimer"]),("fuel_price_adjusted_text",_bm["adjusted_text"])]
    fv=res.get("fuel_validity")
    if fv:
        rows+=[("fuel_validity_status",fv["status"]),("fuel_validity_date",fv.get("date") or ""),("fuel_validity_checked_on",fv["today"]),
               ("fuel_validity_timezone",fv["tz"]),("fuel_expired_price_confirmed_as_historical",fv.get("confirmed",False))]
    for fl_ in res["flags"]:
        if fl_["level"] in ("warn","error"): rows.append((f"flag_{fl_['level']}_{fl_['code']}",fl_["text"]))
    pr=res.get("profit")
    if pr and pr.get("available"):
        rows+=[("charter_rate_basis","already net of commission" if pr["rate_basis"]=="net" else "before commission (gross)"),("charter_rate_usd_per_billed_hour",pr["rate_usd"]),
               ("commission_pct_applied",pr["commission_pct"]),("billed_hours",pr["billed_hours"]),("positioning_hours",pr["positioning_hours"]),("private_other_hours",pr["other_hours"]),
               ("revenue_usd",pr["revenue"]),("commission_usd",pr["commission"]),("other_commercial_fees_usd",pr["other_fees"]),
               ("billed_supplements_retained_usd",pr["supplements_retained"] if pr.get("supplements_retained") is not None else "not entered"),
               ("billed_supplements_cost_usd",pr["supplements_cost"] if pr.get("supplements_cost") is not None else "not entered"),
               ("variable_cost_all_flown_usd",pr["variable_cost_all_flown"]),("fixed_cost_usd",pr["fixed_cost"]),("estimated_operating_result_usd",pr["operating_result"]),
               ("external_charter_contribution_usd",pr["charter_external_contribution"]),("owner_private_variable_cost_usd",pr["owner_private_variable_cost"]),
               ("owner_remaining_cost_usd",pr["owner_remaining_cost"]),("contribution_per_billed_hour_usd",pr["contribution_per_billed_hour"])]
        th=pr.get("threshold") or {}
        rows+=[("operating_cost_coverage_threshold_status",th.get("status"))]
        if th.get("status") in ("ok","exceeds_year"):
            rows+=[("operating_cost_coverage_threshold_billed_hours",th["billed_hours"]),("operating_cost_coverage_threshold_flown_hours",round(th["flown_hours"],2)),
                   ("operating_cost_coverage_threshold_exact_billed_hours",round(th["billed_hours_exact"],4)),("operating_cost_coverage_threshold_assumptions",th["assumptions"])]
        elif th.get("status")=="unattainable": rows+=[("operating_cost_coverage_threshold_message",th["message"])]
        if th.get("status") in ("ok","exceeds_year","unattainable"): rows+=[("operating_cost_coverage_threshold_note",E.THRESHOLD_NOTE)]
        te=pr.get("threshold_economic") or {}
        rows+=[("economic_coverage_threshold_status",te.get("status")),("ownership_depreciation_usd",(pr.get("ownership") or {}).get("depreciation_usd") if (pr.get("ownership") or {}).get("depreciation_usd") is not None else "not entered"),
               ("ownership_loan_interest_usd",(pr.get("ownership") or {}).get("interest_usd") if (pr.get("ownership") or {}).get("interest_usd") is not None else "not entered")]
        if te.get("status") in ("ok","exceeds_year"):
            rows+=[("economic_coverage_threshold_billed_hours",te["billed_hours"]),("economic_coverage_threshold_flown_hours",round(te["flown_hours"],2)),
                   ("economic_result_usd",pr.get("economic_result")),("economic_coverage_threshold_assumptions",te["assumptions"])]
        elif te.get("status")=="unattainable": rows+=[("economic_coverage_threshold_message",te["message"])]
        elif te.get("status")=="incomplete": rows+=[("economic_coverage_threshold_missing",", ".join(te.get("missing",[]))),("economic_coverage_threshold_message",te["message"])]
        rows+=[("positioning_ratio_used",pr.get("positioning_ratio") if pr.get("positioning_ratio") is not None else "undefined"),
               ("confirmations","positioning, private hours, other fees and costs-included review confirmed" if (pr.get("threshold") or {}).get("status") not in ("awaiting_confirmation",) else "not all confirmed")]
    elif pr is not None:
        rows+=[("charter_result_status"," ".join(pr.get("messages",[])))]
    _sc=res.get("scope")
    if _sc:
        rows+=[("costs_included",_re.sub(r"\s+"," ","; ".join(f"{c['label']}" for c in _sc["included"]))),
               ("costs_not_confirmed"," | ".join(_sc["not_confirmed"])),("cost_known_exclusions"," | ".join(_sc["exclusions"])),("cost_limitations"," | ".join(_sc["limits"]))]
    for _k,_v in (res.get("management") or {}).items():
        rows.append((f"management_{_k}",f"{E.MANAGEMENT_STATUS.get(_v['status'],_v['status'])}"+(f" · {_v['amount_usd']:,.0f} USD per year" if _v.get("amount_usd") is not None else "")))
    if res.get("management"): rows.append(("management_note",E.MANAGEMENT_NOTE))
    _cy=[c for c in res["components"] if c["key"]=="cycle_cost"]
    if res["mode"]!="reference": rows.append(("additional_cost_per_landing",(f"added: {_cy[0]['hourly_usd']:,.2f} USD per flown hour (cost per landing ÷ average flight duration)" if _cy else "not enabled: nothing added")))
    for c in res["components"]: rows.append((f"component_{c['category'].lower()}_{c['key']}_annual_usd",c["annual_usd"]))
    return pd.DataFrame(rows,columns=["item","value"]).to_csv(index=False).encode("utf-8-sig")

def main():
    for k,v in [("database",None),("cost_master",None),("pdf_report",None),
                ("auth_email",None),("auth_plan",None),("auth_is_admin",False),("auth_pass_tier",None),
                ("q_legs",[{"from":"","to":"","dep_time":"08:00"}]),
                ("q_result",None),("q_pdf",None)]:
        if k not in st.session_state: st.session_state[k]=v

    # Keep the value of widgets that are not drawn in every mode (Streamlit forgets a widget that is skipped for one run):
    for _k in _KEEP_KEYS:
        if _k in st.session_state: st.session_state[_k]=st.session_state[_k]

    _process_day_pass_return()
    if st.session_state.get("_day_pass_toast"):
        _tier,_hrs=st.session_state.pop("_day_pass_toast")
        st.success(f"✓ {_tier.capitalize()} day pass activated — full access for the next {_hrs}h.")

    is_essentiel,is_pro=render_auth()
    # A day pass unlocks the same tiers as a subscription, just temporarily — merge both into the
    # effective access level without any extra Stripe/Supabase calls (expiry check is local/cheap).
    _active_pass=st.session_state.get("auth_pass_tier")
    if _active_pass=="pro": is_pro=True; is_essentiel=True
    elif _active_pass=="essentiel": is_essentiel=True

    # Header
    c1,c2=st.columns([1,6])
    with c1: st.markdown("<div style='font-size:3rem;text-align:center;margin-top:.3rem'>✈</div>",unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="main-title">Aviation Cost Estimator</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Operating Cost Simulation — Business Aviation</div>',unsafe_allow_html=True)

    _plan_name = "Pro" if is_pro else ("Essentiel" if is_essentiel else "Free")
    _plan_color = "#4ADE80" if is_pro else ("#60A5FA" if is_essentiel else "#8496B0")
    _plan_includes = ("Dashboard · Profitability · Sensitivity · Cost Master · Quotation · Market Search" if is_pro
        else "Dashboard · Profitability · Sensitivity" if is_essentiel
        else "Dashboard · Market Search only")
    st.markdown(f'''<div style="display:flex;align-items:center;gap:.6rem;background:#13233F;border:1px solid #1A3A6E;
         border-left:3px solid {_plan_color};border-radius:6px;padding:.5rem .9rem;margin-bottom:.8rem;font-size:.8rem">
        <span style="color:{_plan_color};font-weight:700">● {_plan_name} plan</span>
        <span style="color:#8496B0">— included: {_plan_includes}</span>
    </div>''', unsafe_allow_html=True)
    st.markdown("<hr>",unsafe_allow_html=True)

    try:
        df=get_active_db(); _checks,_conflicts,_convs=get_support()
    except Exception as _e:
        st.error(f"Aircraft database could not be loaded ({_e}). Make sure menkor_engine.py and the data/ folder are deployed next to app.py.")
        st.stop()
    _prov=None

    # ── Sidebar ─────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown('<div class="section-header">✈ Aircraft Selection</div>',unsafe_allow_html=True)
        st.text_input("Quick find (model or alias, e.g. Global 7000)",key="ac_search",on_change=_on_search)
        if st.session_state.get("ac_search_note"): st.caption(st.session_state["ac_search_note"])
        man_opts=["All"]+sorted(df["Categorie"].unique().tolist())
        cat_sel=st.selectbox("Manufacturer",man_opts,key="ac_cat")
        df_f=df if cat_sel=="All" else df[df["Categorie"]==cat_sel]
        _ids=df_f["aircraft_id"].tolist()
        _sfx={"pdf_acc":"","web_estimate":"  · web estimate","historical":"  · historical"}
        _lab={i:m+_sfx[k] for i,m,k in zip(df["aircraft_id"],df["model"],df["source_kind"])}
        _idx=_ids.index("dassault_falcon_7x") if "dassault_falcon_7x" in _ids else 0
        aid=st.selectbox("Aircraft model",_ids,index=_idx,format_func=lambda i:_lab[i],key="ac_sel")
        row=df[df["aircraft_id"]==aid].iloc[0]
        hist=not bool(row["has_detail"])
        skind=row["source_kind"]
        if hist: st.caption("Historical sheet: totals only, detailed report still to be reconstructed.")
        elif skind=="web_estimate": st.caption("Menkor reference database — partial web estimate (Guardian Jet economics + public technical summary), not a full reference record.")

        st.markdown('<div class="section-header">🧭 Calculation mode</div>',unsafe_allow_html=True)
        mode_lbl=st.radio("Calculation mode",["Report reference","Custom simulation"],key="calc_mode",label_visibility="collapsed",
                          help="Report reference = published totals with the report's own hours and fuel price. Custom simulation = recalculated from your hours, fuel and cost edits.")
        mode="reference" if mode_lbl=="Report reference" else "simulation"
        _locked=(mode=="reference")

        ref_h=E.num(row,"legacy_Heures_Base" if hist else "reference_annual_hours")
        ref_i=int(ref_h) if ref_h else 0
        st.markdown('<div class="section-header">🕐 Flight Hours</div>',unsafe_allow_html=True)
        if _locked: st.caption(f"Report reference: {ref_i} h/year (fixed). Switch to Custom simulation to change hours.")
        billed=st.slider("Billed charter hours / year",0,1500,min(ref_i,1500),step=10,key=f"bh_{aid}",disabled=_locked)
        posit=st.slider("Positioning hours (flown, not billed)",0,600,0,step=10,key=f"ph_{aid}",disabled=_locked)
        other=st.slider("Owner / private / other hours (not billed)",0,1500,0,step=10,key=f"oh_{aid}",disabled=_locked)
        if not _locked:
            st.caption(f"Total flown hours: **{billed+posit+other} h** — variable costs apply to every flown hour; only billed hours earn revenue.")
            if billed+posit+other>E.HOURS_IN_YEAR: st.warning("More than 8,760 hours in a year is not possible.")

        fuel=E.FuelConfig()
        if hist:
            st.markdown('<div class="section-header">⛽ Fuel</div>',unsafe_allow_html=True)
            st.caption("Not available for historical sheets: fuel is included in the hourly rate and cannot be separated.")
        else:
            st.markdown('<div class="section-header">⛽ Fuel (litres)</div>',unsafe_allow_html=True)
            rp=E.num(row,"reference_fuel_price_usd_per_l")
            _cv=_convs[(_convs["aircraft_id"]==aid)&(_convs["field"]=="reference_fuel_price_usd_per_l")]
            _bdf=E.load_fuel_benchmarks()
            src_opts=[f"Report price ({rp:.3f} USD/L)" if rp else "Report price (missing)","My average fuel price"]
            if len(_bdf): src_opts.append("Regional market benchmark")
            ps=st.radio("Fuel price method",src_opts,key=f"fps_{aid}",disabled=_locked)
            if len(_cv): st.caption(f"Report prints {_cv.iloc[0]['source_value']} {_cv.iloc[0]['source_unit']} → {float(_cv.iloc[0]['converted_value']):.3f} USD/L (1 US gal = 3.785411784 L; GAL assumed US gallon, to confirm).")
            bm_opts={"Published hourly burn":"published","Derived from annual volume":"derived","Custom burn (L/h)":"custom"}
            bm=st.selectbox("Burn method",list(bm_opts),key=f"bm_{aid}",disabled=_locked,
                            help="Average economic assumption, not a flight-planning calculation.")
            _pb,_db=E.num(row,"fuel_burn_l_per_h"),E.num(row,"fuel_burn_from_annual_l_per_h")
            st.caption(f"Published: {_pb:,.0f} L/h · derived from annual volume: {_db:,.1f} L/h" if (_pb and _db) else "Burn data incomplete for this model.")
            cburn=None
            if bm_opts[bm]=="custom":
                cburn=st.number_input("Average burn (L/h)",min_value=0.0,value=float(_pb or 0.0),step=10.0,key=f"cb_{aid}",disabled=_locked)
            average=(ps==src_opts[1]); bench_on=(len(src_opts)>2 and ps==src_opts[2])
            fuel=E.FuelConfig(price_source="average" if average else ("benchmark" if bench_on else "report"),burn_method=bm_opts[bm],custom_burn_l_h=cburn)
            if bench_on:
                with st.expander("Regional market benchmark — annual planning assumption",expanded=True):
                    st.warning(E.BENCHMARK_DISCLAIMER)
                    if _locked: st.caption("Report reference ignores this entry (your values are kept). Switch to Custom simulation to adjust costs.")
                    _rid=_bdf["region_id"].tolist(); _rname=dict(zip(_bdf["region_id"],_bdf["region"]))
                    fuel.benchmark_region=st.selectbox("Main refuelling region",_rid,format_func=lambda x:_rname[x],key="fu_bm_region",disabled=_locked,
                                                       help="Main refuelling region: the aircraft record does not determine all of its fuel purchases.")
                    _br=_bdf[_bdf["region_id"]==fuel.benchmark_region].iloc[0]
                    st.caption(f"Reference: {_br['benchmark']} · {_br['period_label']} ({_br['period_start']} to {_br['period_end']}) · "
                               f"{float(_br['price_us_cents_per_us_gallon']):.2f} US cents per US gallon = {float(_br['price_usd_per_l']):.3f} USD/L. "
                               "Weekly refinery reference: not a real-time feed, not an annual average, not a forecast.")
                    _pu=st.number_input("Average fuel price used (USD/L)",min_value=0.0,value=round(float(_br["price_usd_per_l"]),3),step=0.01,format="%.3f",
                                        key="fu_bm_price_"+fuel.benchmark_region,disabled=_locked,
                                        help="Pre-filled with the benchmark of the selected region; you can edit it.")
                    fuel.price=_pu if _pu>0 else None
                    _bi,_be=E.benchmark_price_info(fuel)
                    if _be: st.warning(_be)
                    elif _bi["user_adjusted"]: st.caption(E.BENCHMARK_USER_ADJUSTED)
            if average:
                with st.expander("Average fuel price — annual planning assumption",expanded=True):
                    st.caption("One average price per litre for the whole year. It includes the fuel taxes and fees that normally apply, "
                               "according to your operating habits. It is a planning hypothesis: not a verified local price and not a real-time price.")
                    if _locked: st.caption("Report reference ignores this entry (your values are kept). Switch to Custom simulation to adjust costs.")
                    ac1,ac2=st.columns(2)
                    with ac1: _ap=st.number_input("Average price per litre",min_value=0.0,value=0.0,step=0.05,format="%.3f",key="fu_avg_price",disabled=_locked)
                    with ac2: fuel.currency=st.selectbox("Currency of the average price",["USD","EUR"],key="fu_avg_ccy",disabled=_locked,
                                                         help="EUR is converted with the dated exchange rate entered in the Currency section.")
                    fuel.price=_ap if _ap>0 else None
                    if fuel.price is None: st.warning("Enter the average price per litre: until then the simulation is unavailable (no default value is invented).")
            # Advanced module — kept separate from the annual-planning path. Off by default.
            with st.expander("🔧 Advanced — dated local fuel quote (optional)",expanded=False):
                st.caption("For a specific quote only (airport, supplier, taxes, fees, validity date). Not needed for the annual planning assumption. No real-time price is connected.")
                _adv=st.checkbox("Use a detailed local quote instead of the fuel price source above",key="fu_adv_on",disabled=_locked)
                if _adv:
                    fuel=E.FuelConfig(price_source="manual",burn_method=bm_opts[bm],custom_burn_l_h=cburn)
                    if _locked: st.caption("Report reference ignores this entry (your values are kept). Switch to Custom simulation to adjust costs.")
                    fuel.airport_icao=st.text_input("Airport ICAO",key="fu_icao",max_chars=4,disabled=_locked).upper()
                    fuel.airport_iata=st.text_input("Airport IATA",key="fu_iata",max_chars=3,disabled=_locked).upper()
                    fuel.supplier=st.text_input("Supplier",key="fu_sup",disabled=_locked)
                    fc1,fc2=st.columns(2)
                    with fc1: _fp=st.number_input("Price",min_value=0.0,value=0.0,step=0.05,format="%.3f",key="fu_price",disabled=_locked)
                    with fc2: fuel.unit=st.selectbox("Unit",["L","USG"],key="fu_unit",help="L = litre · USG = US gallon",disabled=_locked)
                    fc3,fc4=st.columns(2)
                    with fc3: fuel.currency=st.selectbox("Currency",["USD","EUR"],key="fu_ccy",disabled=_locked)
                    with fc4: fuel.taxes_pct=st.number_input("Taxes (%)",min_value=0.0,value=0.0,step=1.0,key="fu_tax",disabled=_locked)
                    fuel.fees_per_uplift=st.number_input("Fees per uplift (fixed)",min_value=0.0,value=0.0,step=50.0,key="fu_fee",help="Recorded for stopover purchases; not part of the hourly average.",disabled=_locked)
                    fuel.validity_date=st.text_input("Quote valid until (YYYY-MM-DD)",key="fu_valid",disabled=_locked,help=f"Compared with today's date in {E.BUSINESS_TZ_NAME}.")
                    fuel.price=_fp if _fp>0 else None
                    if fuel.price is None: st.warning("Enter the fuel price: until then the simulation is unavailable (no default value is invented).")
                    _vs=E.validity_status(fuel.validity_date)
                    if _vs["status"]=="invalid": st.error(_vs["message"])
                    elif _vs["status"]=="unknown": st.warning(_vs["message"]+" The price is an unverified assumption.")
                    elif _vs["status"]=="valid": st.caption("✓ "+_vs["message"])
                    else:
                        st.warning(_vs["message"]+" An expired price is not used unless you confirm it as a historical assumption.")
                        _tok=E.fuel_confirmation_token(fuel)
                        # the key contains the price/date signature: changing the price or the date resets the confirmation
                        if st.checkbox("I confirm: use this expired price as a HISTORICAL assumption",key="fu_conf_"+hashlib.md5(_tok.encode()).hexdigest()[:10],disabled=_locked):
                            fuel.expired_confirmation=_tok

        st.markdown('<div class="section-header">💱 Currency</div>',unsafe_allow_html=True)
        disp_ccy=st.radio("Display currency",["USD","EUR"],horizontal=True,key="disp_ccy",help="Source amounts are USD. EUR needs an explicit, dated exchange rate.")
        with st.expander("Exchange rate USD → EUR (explicit, dated)",expanded=(disp_ccy=="EUR")):
            _fxr=st.number_input("EUR for 1 USD",min_value=0.0,value=0.0,step=0.01,format="%.4f",key="fx_rate")
            _fxd=st.text_input("Rate date (YYYY-MM-DD)",key="fx_date")
            _fxs=st.text_input("Rate source (optional)",key="fx_src")
        fx=E.Fx(disp_ccy,_fxr if _fxr>0 else None,_fxd.strip() or None,_fxs.strip())
        disp=E.Display(fx)
        if disp.eur_blocked: st.warning("EUR display needs a rate and a valid date (YYYY-MM-DD). Amounts stay in USD until then.")
        st.caption(disp.note())

        st.markdown('<div class="section-header">💰 Charter revenue — your assumption</div>',unsafe_allow_html=True)
        st.caption("No charter price is pre-filled or assumed. Enter the revenue you expect per billed hour; until then costs are shown but no revenue, result or threshold.")
        rc1,rc2=st.columns([2,1])
        with rc1: rate_in=st.number_input("Expected charter revenue per billed hour",min_value=0.0,value=0.0,step=100.0,format="%.0f",key=f"rate_{aid}")
        with rc2: rate_ccy=st.selectbox("Rate currency",["USD","EUR"],key=f"rateccy_{aid}",help="EUR is converted with the dated exchange rate entered in the Currency section.")
        _rb=st.radio("This rate represents",["Operator revenue before commission (gross)","Revenue already net of commission"],index=None,key=f"rbasis_{aid}",
                     help="Choose explicitly. Gross: the commission below is deducted once. Net: no commission is deducted. A public client price is not assumed to be revenue kept by the operator.")
        rate_basis=None if _rb is None else ("net" if _rb.startswith("Revenue already") else "gross")
        commission_pct=None
        if rate_basis=="gross":
            commission_pct=st.number_input("Commission (%) on gross revenue",min_value=0.0,max_value=100.0,value=None,step=1.0,format="%.1f",key=f"comm_{aid}",
                                           placeholder="enter 0 if none",help="Required: an empty field is not treated as zero. Enter 0 explicitly if there is no commission.")
        elif rate_basis=="net": st.caption("Rate already net: no commission is applied.")
        fees_in=st.number_input(f"Other commercial fees / year ({disp.ccy}) — not already in the report",min_value=0.0,value=0.0,step=1000.0,format="%.0f")
        with st.expander("Billed supplements (optional — kept separate from the hourly rate)",expanded=False):
            st.caption("Taxes, airport fees, crew overnights, positioning or other items billed on top are NOT assumed to be revenue kept by the operator. "
                       "Enter only what the operator actually retains, and the cost linked to it, separately. Empty = not entered (not zero).")
            _sr=st.number_input(f"Annual supplements retained by the operator ({disp.ccy})",min_value=0.0,value=0.0,step=1000.0,format="%.0f",key="supp_rev")
            _sc=st.number_input(f"Annual cost linked to those supplements ({disp.ccy})",min_value=0.0,value=0.0,step=1000.0,format="%.0f",key="supp_cost")
            supp_rev=disp.to_usd(_sr) if _sr>0 else None; supp_cost=disp.to_usd(_sc) if _sc>0 else None
        with st.expander("Economic ownership costs (optional)",expanded=False):
            st.caption(E.OWNERSHIP_NOTE+" Empty = not entered (never zero); type 0 to state an explicit zero, e.g. no interest on an aircraft bought without a loan.")
            od1,od2=st.columns([2,1])
            with od1: _dep=st.number_input("Annual economic depreciation",min_value=0.0,value=None,step=10000.0,format="%.0f",key="own_dep",placeholder="not entered")
            with od2: _depc=st.selectbox("Currency",["USD","EUR"],key="own_dep_ccy")
            oi1,oi2=st.columns([2,1])
            with oi1: _int=st.number_input("Annual loan interest and financing costs",min_value=0.0,value=None,step=10000.0,format="%.0f",key="own_int",placeholder="not entered")
            with oi2: _intc=st.selectbox("Currency ",["USD","EUR"],key="own_int_ccy")

        st.markdown('<div class="section-header">🎯 Coverage threshold — assumptions</div>',unsafe_allow_html=True)
        _pm=st.radio("Positioning assumption",["Hours entered above (needs billed hours > 0)","Ratio per billed hour"],key="pos_mode",
                     help="Positioning = non-billed hours flown per billed hour (empty legs). For the threshold this ratio stays constant when billed hours vary.")
        pos_ratio=None
        if _pm=="Ratio per billed hour":
            pos_ratio=st.number_input("Positioning hours per billed hour",min_value=0.0,value=None,step=0.05,format="%.2f",key="pos_ratio",placeholder="enter 0 if none")
            if pos_ratio is not None: posit=float(billed)*float(pos_ratio); st.caption(f"= {posit:g} positioning hours for {billed} billed hours.")
        _sig=hashlib.md5(repr((aid,rate_in,rate_ccy,rate_basis,commission_pct,billed,posit,pos_ratio,other,fees_in,supp_rev,supp_cost)).encode()).hexdigest()[:10]
        st.caption("Private/owner/other hours and other commercial fees stay constant in the threshold. Zero values are allowed but must be confirmed:")
        _ratio_txt=(f"{pos_ratio:g} h per billed hour" if pos_ratio is not None else f"{float(posit):g} h")
        pos_ok=st.checkbox(f"I confirm the positioning assumption: {_ratio_txt} (zero included).",key="conf_p_"+_sig,disabled=(_pm=="Ratio per billed hour" and pos_ratio is None))
        priv_ok=st.checkbox(f"I confirm the private/owner/other hours: {float(other):g} h per year (zero included).",key="conf_o_"+_sig)
        fees_ok=st.checkbox(f"I confirm the other commercial fees: {disp.money(disp.to_usd(fees_in))} per year (zero included).",key="conf_f_"+_sig)
        limits_ok=st.checkbox("I have reviewed the costs included and the limitations. This is not a validation that the data is complete.",key="conf_l_"+_sig)

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

    # ── Cost Master EDITORS (rendered first so every tab uses the same scenario) ─────
    ov_fixed={}; ov_var={}; extra_fixed_usd=0.0; extra_var_usd=0.0
    mgmt={}; mg_cov=False; cyc_status="none"; cyc_cost=None; cyc_ccy="USD"; cyc_avg=None
    with tab4:
        if not is_pro:
            premium_gate("pro")
        else:
            st.markdown('<div class="main-title" style="font-size:1.4rem">💼 Cost Master</div>',unsafe_allow_html=True)
            if hist:
                st.info("Historical sheet: component detail is not available (report not yet reconstructed). Totals only.")
            else:
                _dis=(mode=="reference")
                if _dis:
                    st.info("Report reference: original published components only. Switch to Custom simulation to adjust costs. (Your simulation edits are kept below but not applied.)")
                _rv=st.session_state.get("_ov_ver",0); _k=f"{aid}_{disp.ccy}_{disp.factor:.6f}_{_rv}"
                if skind=="web_estimate":
                    st.info("Web estimate: only components with a known scope can be replaced — crew (aggregate, training not isolated), hangar, insurance, misc and the combined maintenance line. "
                            "The airframe / engine-APU / crew-misc split and crew training are not available and are not filled with zero or generic costs.")
                st.caption("Edit a value to REPLACE that report component. The total is rebuilt as report total + your change, so nothing is counted twice. "
                           "Fuel is edited in the sidebar (burn × price).")
                with st.expander("🔒 Fixed costs — annual (the report total already includes all five lines)",expanded=True):
                    cols=st.columns(3)
                    for i,(k,(f,_l)) in enumerate(E.FIXED_COMPONENTS.items()):
                        label=E.fixed_label(row,k); src=E.num(row,f)
                        with cols[i%3]:
                            if src is None: st.markdown(f"**{label}**: not available in this source (not replaced by zero)")
                            else:
                                v=st.number_input(f"{label} ({disp.ccy}/yr)",min_value=0.0,value=float(disp.conv(src)),step=1000.0,format="%.0f",key=f"ovf_{k}_{_k}",disabled=_dis)
                                if abs(disp.to_usd(v)-src)>0.5: ov_fixed[k]=disp.to_usd(v)
                with st.expander("⚡ Variable costs — per flown hour (the report total already includes fuel)",expanded=True):
                    cols=st.columns(3)
                    for i,(k,(hf,af,label)) in enumerate(E.var_components_for(row).items()):
                        src=E.num(row,hf)
                        with cols[i%3]:
                            if src is None: st.markdown(f"**{label}**: not available in this source (not replaced by zero)")
                            else:
                                v=st.number_input(f"{label} ({disp.ccy}/h)",min_value=0.0,value=float(disp.conv(src)),step=10.0,format="%.0f",key=f"ovv_{k}_{_k}",disabled=_dis)
                                if abs(disp.to_usd(v)-src)>0.005: ov_var[k]=disp.to_usd(v)
                with st.expander("➕ Costs not in the report (user-added)",expanded=False):
                    x1,x2=st.columns(2)
                    with x1: _xf=st.number_input(f"Extra fixed cost ({disp.ccy}/yr)",min_value=0.0,value=0.0,step=1000.0,format="%.0f",key=f"xf_{_k}",disabled=_dis)
                    with x2: _xv=st.number_input(f"Extra variable cost ({disp.ccy}/flown h)",min_value=0.0,value=0.0,step=10.0,format="%.0f",key=f"xv_{_k}",disabled=_dis)
                    extra_fixed_usd=disp.to_usd(_xf); extra_var_usd=disp.to_usd(_xv)
                st.markdown("**Management fees**")
                st.caption(E.MANAGEMENT_NOTE)
                mf1,mf2=st.columns([2,1])
                with mf1: _mfee=st.number_input("Annual management fee",min_value=0.0,value=None,step=1000.0,format="%.0f",key=f"mgfee_{_k}",placeholder="optional",disabled=_dis)
                with mf2: _mfc=st.selectbox("Management fee currency",["USD","EUR"],key=f"mgfeec_{_k}",disabled=_dis)
                mgmt["management"]=dict(amount=_mfee,ccy=_mfc)
                if _mfee is None: st.caption(E.MANAGEMENT_EXCLUDED)
                with st.expander("⚙ Advanced adjustments",expanded=False):
                    st.caption("Optional. Leave empty if not needed: nothing is added.")
                    if _mfee is not None:
                        mg_cov=st.checkbox("My management fee already covers CAMO and dispatch",key=f"mgcov_{_k}",disabled=_dis)
                    for _mk,_ml in (("camo","CAMO"),("dispatch","Dispatch / flight support")):
                        ma1,ma2=st.columns([2,1])
                        _cov=bool(mg_cov and _mfee is not None)
                        with ma1: _a=st.number_input(f"{_ml} — annual cost",min_value=0.0,value=None,step=1000.0,format="%.0f",key=f"mga_{_mk}_{_k}",placeholder="optional",disabled=(_dis or _cov))
                        with ma2: _c=st.selectbox(f"{_ml} currency",["USD","EUR"],key=f"mgc_{_mk}_{_k}",disabled=(_dis or _cov))
                        mgmt[_mk]=dict(amount=_a,ccy=_c)
                    st.markdown("---")
                    _cyc_on=st.checkbox("Add additional costs per landing",key=f"cyc_{_k}",disabled=_dis)
                    st.caption("Enter only costs not already covered by the reference costs or your programmes.")
                    if _cyc_on:
                        cyc_status="added"
                        cy1,cy2=st.columns([2,1])
                        with cy1: cyc_cost=st.number_input("Additional cost per landing",min_value=0.0,value=None,step=50.0,format="%.0f",key=f"cycc_{_k}",placeholder="not entered",disabled=_dis)
                        with cy2: cyc_ccy=st.selectbox("Currency per landing",["USD","EUR"],key=f"cycccy_{_k}",disabled=_dis)
                        cyc_avg=st.number_input("Average flight duration (hours)",min_value=0.0,value=None,step=0.1,format="%.2f",key=f"cyca_{_k}",placeholder="not entered",disabled=_dis)
                        if cyc_cost is None or not cyc_avg: st.warning("Enter the additional cost per landing and the average flight duration, or untick the option.")
                st.button("↺ Reset all edits",key="ov_reset",on_click=_bump_overrides,disabled=_dis)

    # ── The single scenario & the single result used by every tab and the PDF ─────
    scn=E.Scenario(aircraft_id=aid,mode=mode,billed_hours=float(billed),positioning_hours=float(posit),other_hours=float(other),
                   charter_rate=(rate_in if rate_in>0 else None),charter_rate_ccy=rate_ccy,commission_pct=(None if commission_pct is None else float(commission_pct)),rate_basis=rate_basis,
                   supplements_retained_usd=supp_rev,supplements_cost_usd=supp_cost,positioning_ratio=pos_ratio,positioning_confirmed=bool(pos_ok),
                   private_hours_confirmed=bool(priv_ok),other_fees_confirmed=bool(fees_ok),limits_reviewed=bool(limits_ok),
                   depreciation_annual=_dep,depreciation_ccy=_depc,interest_annual=_int,interest_ccy=_intc,
                   management=mgmt,management_covers_camo_dispatch=bool(mg_cov),cycle_status=cyc_status,cycle_cost=cyc_cost,cycle_cost_ccy=cyc_ccy,avg_flight_hours=cyc_avg,
                   other_commercial_fees=float(disp.to_usd(fees_in)),fuel=fuel,fixed_overrides=ov_fixed,var_overrides_h=ov_var,
                   extra_fixed=float(extra_fixed_usd),extra_var_h=float(extra_var_usd),fx=fx)
    res=E.compute(row,scn)
    alerts=E.alerts_for(row,_checks,_conflicts,_convs)
    perf=E.performance_summary(row)
    D=disp.money

    # TAB 1: DASHBOARD
    with tab1:
        _mode_txt="Report reference — published totals, original assumptions" if mode=="reference" else "Custom simulation — recalculated from your assumptions"
        st.markdown(f'<div style="font-size:.78rem;color:#C9A84C;margin-bottom:.4rem">● {_mode_txt}</div>',unsafe_allow_html=True)
        k1,k2,k3,k4=st.columns(4)
        with k1:
            st.markdown(f'''<div class="metric-card"><div class="metric-label">Aircraft</div>
                <div class="metric-value" style="font-size:1.2rem">{row["model"]}</div>
                <div class="metric-sub">{row.get("manufacturer") if pd.notna(row.get("manufacturer")) else "Historical sheet"} · {"Menkor reference" if skind=="pdf_acc" else ("web estimate · partial" if skind=="web_estimate" else "to reconstruct")}</div></div>''',unsafe_allow_html=True)
        with k2:
            _fh=res["hours"]["flown"]; _fh=ref_h if _fh is None else _fh
            _sub=(f"report reference hours" if mode=="reference" else f"{billed:g} billed · {posit:g} positioning · {other:g} other")
            st.markdown(f'''<div class="metric-card"><div class="metric-label">Flown Hours / Year</div>
                <div class="metric-value">{_fh:,.0f} h</div><div class="metric-sub">{_sub}</div></div>''',unsafe_allow_html=True)
        with k3:
            if hist:
                _lr=E.num(row,"legacy_Autonomie_km")
                _val=f"{_lr:,.0f} km" if _lr else "n/a"
                _sub="historical value · definition unverified"
            else:
                _val=(f"{perf['seats_range_km']:,.0f} km" if perf["seats_range_km"] else (f"{perf['seats_range_nm']:,.0f} NM" if perf["seats_range_nm"] else "n/a"))
                _sub=(f"{perf['seats_range_nm']:,.0f} NM · all seats occupied" if perf["seats_range_nm"] else "not provided")
                if perf["ferry_range_nm"]: _sub+=f" · ferry {perf['ferry_range_nm']:,.0f} NM"
            st.markdown(f'''<div class="metric-card" title="{_re.sub(r'[^A-Za-z0-9 ,.;:()/%-]','',(perf['range_definition'] or '')[:300]) if not hist else ''}"><div class="metric-label">Range — seats occupied</div>
                <div class="metric-value">{_val}</div><div class="metric-sub">{_sub}</div></div>''',unsafe_allow_html=True)
        with k4:
            _sp=perf["cruise_kmh"] if not hist else E.num(row,"legacy_Vitesse_Croisiere_km_h")
            _bk=perf["block_kmh"] if not hist else None
            st.markdown(f'''<div class="metric-card"><div class="metric-label">Cruise Speed</div>
                <div class="metric-value">{f"{_sp:,.0f} km/h" if _sp else "n/a"}</div>
                <div class="metric-sub">{f"block speed {_bk:,.0f} km/h" if _bk else ("report value" if not hist else "historical value")}</div></div>''',unsafe_allow_html=True)
        if not hist and perf["range_definition"]:
            st.caption(f"ℹ Range = {perf['range_definition']} {perf['conditions'] or ''}".strip())
        st.markdown("<hr>",unsafe_allow_html=True)

        if not res["available"]:
            _render_alerts(res,alerts)
        elif is_essentiel or is_pro:
            st.caption(disp.note())
            m1,m2,m3,m4,m5=st.columns(5)
            v=res["variable"]
            m1.metric("🔒 Annual Fixed Costs",D(res["fixed"]["annual_total"]),help="Already includes crew, crew training, hangar, insurance and aircraft misc — crew is not added again.")
            m2.metric("⛽ Fuel / flown hour",D(v["fuel_per_h"]) if v["fuel_per_h"] is not None else "n/a",
                      help=(f"{res['fuel']['burn_l_h']:,.0f} L/h × {res['fuel']['price_usd_l']:.3f} USD/L" if res.get("fuel") and res["fuel"].get("burn_l_h") and res["fuel"].get("price_usd_l") else "Fuel not separable"))
            m3.metric("⚡ Other variable / hour",D(v["nonfuel_per_h"]) if v["nonfuel_per_h"] is not None else "n/a",help="Airframe, engines/APU, crew travel, catering, airport fees, other")
            m4.metric("💶 Total Annual Budget",D(res["budget_usd"]),help="Annual fixed + annual variable")
            m5.metric("⌛ Cost / flown hour",D(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a",
                      help="Annual budget ÷ flown hours. Not applicable when hours are zero.")
            st.caption(f"Variable per hour total {D(v['per_h'])} → annual variable {D(v['annual'])}  ·  Annual budget = fixed {D(res['fixed']['annual_total'])} + variable {D(v['annual'])}")
            if res.get("fuel"):
                f=res["fuel"]
                if f.get("burn_l_h") and f.get("price_usd_l"):
                    st.caption(f"⛽ Method: {f['burn_label']} = {f['burn_l_h']:,.0f} L/h ({f['burn_l_h']/E.USG_TO_L:,.0f} US gal/h) × {f['price_usd_l']:.3f} USD/L — {f['price_label']}. "
                               f"Annual fuel: {f['annual_litres']:,.0f} L ({f['annual_usg']:,.0f} US gal). {f['note']}")
            if res.get("reconciliation") and mode=="simulation":
                rc=res["reconciliation"]
                if rc.get("adjustment_delta"):
                    st.caption(f"Reconciliation: Menkor cost base {D(rc['published_budget'])} (= original published {D(rc['original_published_budget'])} + Menkor base adjustment {D(rc['adjustment_delta'])}) vs simulation recalculated at the report's own hours and fuel price (burn × price) {D(rc['simulated_at_report_conditions'])}: difference {D(rc['difference'])} ({rc['difference_pct']:+.2f}%). "
                               "It comes from the rounding of the printed hourly burn and fuel price, not from the Menkor base adjustment; the source data are not altered.")
                else:
                    st.caption(f"Reconciliation: at the report's own hours and fuel price the formula gives {D(rc['simulated_at_report_conditions'])} vs published {D(rc['published_budget'])} ({rc['difference_pct']:+.2f}%). Printed hourly values are rounded; the source data are not altered.")
            _render_alerts(res,alerts)
            st.markdown("<hr>",unsafe_allow_html=True)
            g1,g2=st.columns(2)
            with g1:
                st.markdown('<div class="section-header">Annual Cost Breakdown</div>',unsafe_allow_html=True)
                st.plotly_chart(chart_donut(res,disp),width="stretch",config={"displayModeBar":False})
            with g2:
                st.markdown('<div class="section-header">Cost per Flown Hour</div>',unsafe_allow_html=True)
                _fg=chart_per_hour(res,disp)
                if _fg is not None: st.plotly_chart(_fg,width="stretch",config={"displayModeBar":False})
                else: st.info("Cost per hour is not applicable: annual flown hours are zero.")
            _mb=res.get("menkor_base") or {}
            if mode=="reference":
                st.info("Report reference — original published values. Cost edits and the Menkor cost base apply to Custom simulation only.")
            elif _mb.get("applied"):
                with st.expander("📋 Menkor cost base — original published values vs base values (read-only)",expanded=False):
                    st.caption(_mb["text"]+" Your edits replace these values.")
                    _it=pd.DataFrame([{"Item":i["item"],f"Original published ({disp.ccy})":(round(disp.conv(i["before"])) if i["before"] is not None else None),
                                       f"Menkor base ({disp.ccy})":(round(disp.conv(i["after"])) if i["after"] is not None else None),
                                       "Change":(f"{i['pct']:+.1f}%" if i.get("pct") is not None else "n/a"),
                                       f"Difference ({disp.ccy})":(round(disp.conv(i["delta"])) if i.get("delta") is not None else None),
                                       "Note":i.get("note","")} for i in _mb["items"]])
                    st.dataframe(_it,width="stretch",hide_index=True)
                    if _mb.get("delta_total") is not None:
                        st.caption(f"Total on the published basis: {D(_mb['published_budget_original'])} original budget {'+' if _mb['delta_total']>=0 else '−'} {D(abs(_mb['delta_total']))} = {D(_mb['published_budget_adjusted'])} (Menkor cost base).")
            else:
                st.caption("Menkor cost base: no adjustment for this record (original published values).")
            with st.expander("🔎 Data provenance — extracted / calculated / converted / missing"):
                if _prov is None: _prov=get_prov()
                st.dataframe(_prov_table(row,_prov),width="stretch",hide_index=True)
                _d=res.get("dates") or {}
                st.caption(f"Dates — economic reference date of the figures: {_d.get('economic_reference_date','unknown')} · consultation date (web page read): {_d.get('consultation_date') or 'n/a'} · database extraction date: {_d.get('extraction_date') or 'n/a'} (processing date, not a price-validity date). Empty means missing — never zero.")
        else:
            def _locked_metric(label):
                return f'''<div class="metric-card" style="text-align:center">
                    <div class="metric-label">{label}</div>
                    <div style="font-size:1.6rem;font-weight:700;color:#4A5568;filter:blur(5px);user-select:none">$ 000,000</div>
                    <div class="metric-sub" style="color:#F59E0B">🔒 Essentiel</div></div>'''
            m1,m2,m3,m4,m5=st.columns(5)
            m1.markdown(_locked_metric("🔒 Annual Fixed Costs"),unsafe_allow_html=True)
            m2.markdown(_locked_metric("⛽ Fuel / hour"),unsafe_allow_html=True)
            m3.markdown(_locked_metric("⚡ Other variable / hour"),unsafe_allow_html=True)
            m4.markdown(_locked_metric("💶 Total Annual Budget"),unsafe_allow_html=True)
            m5.markdown(_locked_metric("⌛ Cost / hour"),unsafe_allow_html=True)
            st.markdown("<hr>",unsafe_allow_html=True)
            g1,g2=st.columns(2)
            for _g,_title in [(g1,"Annual Cost Breakdown"),(g2,"Cost per Flown Hour")]:
                with _g:
                    st.markdown(f'<div class="section-header">{_title}</div>',unsafe_allow_html=True)
                    st.markdown('''<div style="height:260px;display:flex;flex-direction:column;align-items:center;
                         justify-content:center;background:#13233F;border:1px dashed #1A3A6E;border-radius:6px">
                        <div style="font-size:1.8rem">🔒</div>
                        <div style="font-size:.78rem;color:#8496B0;margin-top:.4rem">Unlock with Essentiel — 15€/mo</div>
                    </div>''',unsafe_allow_html=True)
            st.markdown('<div style="text-align:center;margin-top:1rem">',unsafe_allow_html=True)
            st.caption("See the exact cost breakdown for every aircraft with an Essentiel or Pro plan.")
            if st.session_state.get("auth_email"): _plan_buttons(st.session_state["auth_email"],current_plan=st.session_state.get("auth_plan"))
            st.markdown('</div>',unsafe_allow_html=True)
        if res["available"] and (is_essentiel or is_pro): _render_costs_scope(row,res,scn,D,"scope_dash")
        st.markdown("<hr>",unsafe_allow_html=True)
        _render_budget_offer(res["model"],"offer")

    # TAB 2: PROFITABILITY
    with tab2:
        if not is_essentiel:
            premium_gate("essentiel")
        else:
            st.markdown('<div class="section-header">Charter Profitability — Estimated Operating Result</div>',unsafe_allow_html=True)
            st.caption(disp.note())
            if mode=="reference":
                st.info("The report has no charter revenue, billed hours or positioning data. Switch to **Custom simulation** (sidebar) to estimate profitability.")
            elif not res["available"]:
                _render_alerts(res,alerts)
            else:
                pr=res["profit"]
                if not pr["available"]:
                    st.info(" ".join(pr["messages"]))
                    st.caption("Costs are shown without any revenue, result, threshold or revenue chart until a valid charter revenue per billed hour is entered.")
                    p1,p2,p3=st.columns(3)
                    p1.metric("🔒 Annual fixed",D(res["fixed"]["annual_total"])); p2.metric("⚡ Annual variable",D(res["variable"]["annual"])); p3.metric("💶 Annual budget",D(res["budget_usd"]))
                    _render_costs_scope(row,res,scn,D,"scope_pr0")
                else:
                    r_=pr["operating_result"]; cov=pr["coverage_pct"]
                    badge=('<span class="tag-ok">✓ POSITIVE OPERATING RESULT</span>' if r_>=0 else
                           ('<span class="tag-warn">⚠ COSTS NOT FULLY COVERED</span>' if (cov or 0)>=70 else '<span class="tag-err">✗ NEGATIVE OPERATING RESULT</span>'))
                    st.caption("The charter revenue is the figure you entered ("+("already net of commission" if pr["rate_basis"]=="net" else f"before commission, {pr['commission_pct']:g}% deducted once")+"). "
                               "A public or client price is not assumed to be revenue kept by the operator: billed supplements are entered separately.")
                    st.markdown(f"**Status:** {badge} — Coverage: **{cov:.1f}%** (net revenue after commission and fees ÷ total costs)",unsafe_allow_html=True)
                    h1,h2,h3,h4=st.columns(4)
                    h1.metric("Total flown hours",f"{pr['flown_hours']:g} h"); h2.metric("Billed hours",f"{pr['billed_hours']:g} h")
                    h3.metric("Positioning hours",f"{pr['positioning_hours']:g} h"); h4.metric("Charter rate / billed h",D(pr["rate_usd"]))
                    r1,r2,r3,r4=st.columns(4)
                    r1.metric("💵 Charter revenue",D(pr["revenue"]))
                    r2.metric("📉 Commission + fees",D(pr["commission"]+pr["other_fees"]),help=("Rate already net: no commission deducted." if pr["rate_basis"]=="net" else None))
                    r3.metric("⚡ Variable (all flown h)",D(pr["variable_cost_all_flown"]))
                    r4.metric("🔒 Fixed",D(pr["fixed_cost"]))
                    st.metric("📊 Estimated operating result",D(r_),delta=f"{cov:.1f}% coverage")
                    st.caption("Estimated operating result = charter revenue − variable costs of ALL flown hours − fixed costs − commercial fees not already included. "
                               "It excludes financing, depreciation and tax: it is not a net profit.")
                    st.markdown("<hr>",unsafe_allow_html=True)
                    st.markdown("**Charter contribution vs owner's own flying** (kept separate; no internal owner-to-operator payment is modelled)")
                    o1,o2,o3=st.columns(3)
                    o1.metric("External charter contribution",D(pr["charter_external_contribution"]),help="Net charter revenue (+ retained supplements − their cost) − variable cost of billed and positioning hours.")
                    o2.metric("Owner private flying — variable",D(pr["owner_private_variable_cost"]),help="Variable cost of the private/other hours.")
                    o3.metric("Remaining cost to the owner (negative = surplus)",D(pr["owner_remaining_cost"]),help="Fixed + private variable − external charter contribution (= −operating result).")
                    if pr.get("supplements_retained") is not None or pr.get("supplements_cost") is not None:
                        st.caption(f"Billed supplements (separate): retained {D(pr['supplements_retained']) if pr.get('supplements_retained') is not None else 'not entered'} · "
                                   f"linked cost {D(pr['supplements_cost']) if pr.get('supplements_cost') is not None else 'not entered'}.")
                    st.markdown(f"**Contribution per billed hour** (rate after commission − variable cost of the billed hour incl. its positioning): **{D(pr['contribution_per_billed_hour'])}**")
                    _render_threshold(pr,D)
                    _render_budget_cta(res["model"],"thr")
                    _render_costs_scope(row,res,scn,D,"scope_pr")
                    st.plotly_chart(chart_waterfall(res,disp),width="stretch",config={"displayModeBar":False})
                _render_alerts(res,alerts)

    # TAB 3: SENSITIVITY
    with tab3:
        if not is_essentiel:
            premium_gate("essentiel")
        else:
            st.markdown('<div class="section-header">Sensitivity — Billed Hours vs Operating Result</div>',unsafe_allow_html=True)
            st.caption(disp.note())
            if mode=="reference":
                st.info("Sensitivity uses the simulation engine. Switch to **Custom simulation** to explore hours and fuel price.")
            elif not res["available"]:
                _render_alerts(res,alerts)
            else:
                pr=res["profit"]
                if pr["available"]:
                    st.caption(f"Positioning ratio {pr['positioning_ratio']:.2f} · other hours {other:g} h · commission {commission_pct}% · rate {D(pr['rate_usd'])}/billed h — same engine as every other tab.")
                    _pts=E.sensitivity_billed_hours(row,scn,list(range(0,1501,25)))
                    _th=pr.get("threshold") or {}
                    st.plotly_chart(chart_sensitivity(_pts,_th.get("billed_hours_exact") if _th.get("status")=="ok" else None,billed,disp),width="stretch",config={"displayModeBar":False})
                    _render_threshold(pr,D)
                else:
                    st.info(" ".join(pr["messages"]))
                if not hist:
                    st.markdown('<div class="section-header">Fuel price sensitivity</div>',unsafe_allow_html=True)
                    _bp=res["fuel"]["price_usd_l"]
                    _prices=[round(_bp*x,4) for x in (0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.75,2.0)]
                    st.plotly_chart(chart_fuel_sens(E.sensitivity_fuel_price(row,scn,_prices),disp,_bp),width="stretch",config={"displayModeBar":False})
                st.markdown('<div class="section-header">Fleet Comparison</div>',unsafe_allow_html=True)
                st.caption("Same hours and fuel assumptions applied to every PDF-documented aircraft, each with its own report data. Historical sheets are excluded (no fuel split).")
                comp=E.fleet_comparison(df,scn)
                if len(comp):
                    _m=df.set_index("aircraft_id")["Categorie"]
                    _sel=st.multiselect("Manufacturers",sorted(comp["manufacturer"].dropna().unique()),default=[row.get("manufacturer")] if row.get("manufacturer") in set(comp["manufacturer"]) else [],key="fleet_mf")
                    cs=comp[comp["manufacturer"].isin(_sel)] if _sel else comp
                    cs=cs.sort_values("budget_usd")
                    _web=cs[cs["source_kind"]=="web_estimate"]; cs_chart=cs[cs["source_kind"]=="pdf_acc"]
                    fig_c=px.bar(x=cs_chart["model"],y=[disp.conv(x) for x in cs_chart["budget_usd"]],color=[(disp.conv(x) if x is not None else None) for x in cs_chart["cost_per_h_usd"]],
                                 color_continuous_scale=["#1A3A6E","#4A90D9","#C9A84C","#E8C46A"],template="plotly_dark",
                                 labels={"x":"Model","y":f"Annual budget ({disp.ccy})","color":f"Cost/h ({disp.ccy})"})
                    fig_c.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font=dict(color="#D6E4F7"),height=350,
                                        margin=dict(t=10,b=80,l=10,r=10),xaxis=dict(tickangle=-30),yaxis=dict(gridcolor="#1A3A6E",tickformat=",.0f"))
                    st.plotly_chart(fig_c,width="stretch",config={"displayModeBar":False})
                    if len(_web): st.caption("Web estimates (Guardian Jet scenario, 300 h) are listed in the table but kept out of the chart: they are not equivalent to the full Menkor reference records.")
                    _t=cs.assign(**{f"Annual budget ({disp.ccy})":[round(disp.conv(x)) for x in cs["budget_usd"]],
                                    f"Cost/h ({disp.ccy})":[(round(disp.conv(x)) if (x is not None and x==x) else None) for x in cs["cost_per_h_usd"]]})[["model","manufacturer","source_kind",f"Annual budget ({disp.ccy})",f"Cost/h ({disp.ccy})"]]
                    _t["source_kind"]=_t["source_kind"].map(E.source_label)
                    _t=_t.rename(columns={"model":"Model","manufacturer":"Manufacturer","source_kind":"Source"})
                    st.dataframe(_t,width="stretch",hide_index=True)
                else:
                    st.info("Fleet comparison unavailable with the current fuel inputs (e.g. an average fuel price must be entered).")

    # TAB 4: COST MASTER — results (editors were rendered above)
    with tab4:
        if is_pro:
            st.markdown("<hr>",unsafe_allow_html=True)
            st.caption(disp.note())
            if not res["available"]:
                _render_alerts(res,alerts)
            else:
                v=res["variable"]
                st.markdown(f'''<div class="total-banner">
                    <div style="font-size:.72rem;color:#8496B0;margin-bottom:.4rem">{res["model"]} · {"Report reference" if mode=="reference" else "Custom simulation"} · config {res["config_hash"]}</div>
                    <div style="font-size:2.4rem;font-weight:800;color:#E8C46A">{D(res["budget_usd"])}</div>
                    <div style="font-size:.85rem;color:#8496B0">Fixed: <b style="color:#F59E0B">{D(res["fixed"]["annual_total"])}</b> (incl. crew) · Variable: <b style="color:#60A5FA">{D(v["annual"])}</b>
                    ({D(v["per_h"])}/h × {res["hours"]["flown"]:,.0f} h)</div>
                </div>''',unsafe_allow_html=True)
                kk=st.columns(4)
                kk[0].metric("🔒 Annual fixed",D(res["fixed"]["annual_total"]))
                kk[1].metric("⚡ Variable / hour",D(v["per_h"]))
                kk[2].metric("💶 Annual budget",D(res["budget_usd"]))
                kk[3].metric("⌛ Cost / flown hour",D(res["cost_per_h_usd"]) if res["cost_per_h_usd"] is not None else "n/a")
                _render_alerts(res,alerts)
                pr=res.get("profit")
                if pr and pr.get("available"):
                    kr=st.columns(3)
                    kr[0].metric("💵 Charter revenue",D(pr["revenue"])); kr[1].metric("📊 Estimated operating result",D(pr["operating_result"]))
                    _th=pr.get("threshold") or {}
                    kr[2].metric(E.THRESHOLD_LABEL,(f"{_th['billed_hours']:,d} billed h" if _th.get("status")=="ok" else (E.NO_THRESHOLD if _th.get("status")=="unattainable" else "confirm assumptions")))
                st.markdown("<hr>",unsafe_allow_html=True)
                d1,d2=st.columns(2)
                with d1:
                    st.markdown('<div class="section-header">Fixed components (annual)</div>',unsafe_allow_html=True)
                    _f=cm_donut(res,disp,"Fixed")
                    if _f is not None: st.plotly_chart(_f,width="stretch",config={"displayModeBar":False})
                with d2:
                    st.markdown('<div class="section-header">Variable components (annual)</div>',unsafe_allow_html=True)
                    _f=cm_donut(res,disp,"Variable")
                    if _f is not None: st.plotly_chart(_f,width="stretch",config={"displayModeBar":False})
                b1,b2=st.columns(2)
                with b1:
                    _f=cm_bar(res,disp,"Fixed","Fixed — annual")
                    if _f is not None: st.plotly_chart(_f,width="stretch",config={"displayModeBar":False})
                with b2:
                    _f=cm_bar(res,disp,"Variable","Variable — annual")
                    if _f is not None: st.plotly_chart(_f,width="stretch",config={"displayModeBar":False})
                rows2=[{"Category":c["category"],"Line":c["label"]+(" ✎" if c.get("edited") and not c.get("rounding") else ""),
                        f"Annual ({disp.ccy})":round(disp.conv(c["annual_usd"])),
                        f"Per hour ({disp.ccy})":(round(disp.conv(c["hourly_usd"]),2) if c.get("hourly_usd") is not None else None),
                        "% of budget":(round(c["share_pct"],1) if c.get("share_pct") is not None else None)} for c in res["components"]]
                rows2.append({"Category":"TOTAL","Line":"Annual budget (fixed + variable)",f"Annual ({disp.ccy})":round(disp.conv(res["budget_usd"])),f"Per hour ({disp.ccy})":None,"% of budget":100.0})
                st.dataframe(pd.DataFrame(rows2),width="stretch",hide_index=True)
                st.caption("Components break down the totals — they are not added to them. ✎ = replaced by your edit. Rounding lines reconcile printed rounded values with the source totals.")

                # Fuel consumed vs purchased at a stopover
                with st.expander("⛽ Stopover fuel: consumed vs purchased"):
                    st.caption("Fuel consumed on a leg is not the fuel bought at the stopover (reserves, tankering, partial uplift). Manual entry only — no live price.")
                    s1,s2,s3=st.columns(3)
                    with s1: _cons=st.number_input("Consumed on the leg (L)",min_value=0.0,value=0.0,step=100.0,key="sp_cons")
                    with s2: _pq=st.number_input("Purchased quantity",min_value=0.0,value=0.0,step=100.0,key="sp_qty")
                    with s3: _pu=st.selectbox("Unit",["L","USG"],key="sp_unit")
                    s4,s5,s6=st.columns(3)
                    with s4: _pp=st.number_input("Unit price",min_value=0.0,value=0.0,step=0.05,format="%.3f",key="sp_price")
                    with s5: _pc=st.selectbox("Currency",["USD","EUR"],key="sp_ccy")
                    with s6: _pt=st.number_input("Taxes (%)",min_value=0.0,value=0.0,step=1.0,key="sp_tax")
                    _pf=st.number_input("Fixed fees for the uplift",min_value=0.0,value=0.0,step=50.0,key="sp_fee")
                    if _pq>0 and _pp>0:
                        sp=E.stopover_purchase(_pq,_pu,_pp,_pc,_pt,_pf,_cons,fx)
                        st.markdown(f"Purchased **{sp['purchased_l']:,.0f} L** vs consumed **{sp['consumed_l']:,.0f} L** (balance {sp['balance_l']:+,.0f} L) · purchase cost **{sp['purchase_cost']:,.2f} {sp['currency']}**"
                                    + (f" = {D(sp['usd'])}" if sp['usd'] is not None else " (enter a dated EUR/USD rate to convert)"))
                st.markdown("<hr>",unsafe_allow_html=True)
                x1,x2=st.columns(2)
                with x1:
                    if st.button("📄 Generate PDF Report",width="stretch",type="primary"):
                        with st.spinner("Building report..."):
                            try:
                                st.session_state["pdf_report"]=dict(data=generate_pdf_report(res,disp,alerts),hash=res["config_hash"],aid=aid)
                                st.success("✓ Report ready!")
                            except Exception as e: st.error(f"PDF error: {e}")
                    _p=st.session_state.get("pdf_report")
                    if isinstance(_p,dict):
                        if _p["hash"]==res["config_hash"]:
                            st.download_button("⬇ Download PDF Report",data=_p["data"],file_name=f"Menkor_Cost_{res['model'].replace(' ','_')}_{res['config_hash']}.pdf",mime="application/pdf",width="stretch")
                        else:
                            st.warning(f"⚠ The last PDF (config {_p['hash']}) is obsolete: assumptions changed (current config {res['config_hash']}). Generate it again.")
                with x2:
                    st.download_button("⬇ Download results (CSV)",data=_results_csv(res,disp),file_name=f"Menkor_Results_{res['aircraft_id']}_{res['config_hash']}.csv",mime="text/csv",width="stretch")

    # TAB 5: QUOTATION
    with tab5:
        if not is_pro:
            premium_gate("pro")
        else:
            st.markdown('<div class="section-header">Quotation basis — from the same engine</div>',unsafe_allow_html=True)
            st.caption(disp.note())
            pr=res.get("profit") if res["available"] else None
            if mode=="reference":
                st.info("Switch to **Custom simulation** to build a quotation basis (billed hours, rate and commission are needed).")
                st.slider("Target operating margin on revenue (%)",0,40,10,step=1,key="q_margin",disabled=True)
            elif not pr or not pr.get("available"):
                st.info("Enter billed hours and your expected charter revenue per billed hour in the sidebar to see the quotation basis. "+(" ".join(pr["messages"]) if pr else ""))
            else:
                _mg=st.slider("Target operating margin on revenue (%)",0,40,10,step=1,key="q_margin")
                _rq=E.required_rate(pr,_mg)
                q1,q2,q3=st.columns(3)
                q1.metric("Cost per flown hour",D(res["cost_per_h_usd"]))
                q2.metric("Rate covering the entered costs (0% margin) / billed hour",D(E.required_rate(pr,0)) if E.required_rate(pr,0) else "n/a")
                q3.metric(f"Rate for {_mg}% margin / billed hour",D(_rq) if _rq else "not attainable")
                st.caption(f"Based on {pr['billed_hours']:g} billed h, {pr['positioning_hours']:g} h positioning, {pr['other_hours']:g} h other, commission {pr['commission_pct']:g}%. "
                           "Rate = (variable costs of all flown hours + fixed costs + fees) ÷ (billed hours × (1 − commission − margin)). Operating result, before financing, depreciation and tax.")
            _render_alerts(res,alerts,title="Quotation data notes")
            st.markdown("""
            <div style="background:linear-gradient(135deg,#112244 0%,#1A3A6E 100%);
                 border:1px solid #C9A84C;border-radius:12px;padding:2.2rem 2rem;text-align:center;margin:1.5rem 0">
                <div style="font-size:1.4rem;font-weight:700;color:#E8C46A;margin-bottom:.6rem">✈️ Charter Flight Quotation (routes, legs, extras)</div>
                <div style="font-size:.9rem;color:#8496B0;margin-bottom:1.2rem;line-height:1.6">
                    Route map, multi-leg itinerary and branded PDF are produced by the separate quotation tool.<br>
                    <b style="color:#D6E4F7">It is not yet connected to this calculation engine:</b> copy the hourly basis above into it.
                </div>
                <a href="https://menkor-quotation-9nff8mo2pbyf8vddbsucvm.streamlit.app/" target="_blank"
                   style="background:#C9A84C;color:#0B1629;padding:.7rem 2.2rem;border-radius:6px;font-weight:700;text-decoration:none;font-size:1rem">
                    ✈️ Open Quotation Tool
                </a>
            </div>""", unsafe_allow_html=True)

    # ── TAB 6 : MARKET SEARCH ───────────────────────────────────────────
    with tab6:
        st.markdown('<div class="main-title" style="font-size:1.4rem">🌐 Personalized Aircraft Market Search</div>',unsafe_allow_html=True)
        st.markdown('<div class="sub-title">Every active listing for your chosen model, consolidated and verified by our team</div>',unsafe_allow_html=True)

        ms_cats=["All"]+sorted(df["Categorie"].dropna().unique().tolist())
        msc1,msc2=st.columns(2)
        with msc1: ms_cat=st.selectbox("Manufacturer",ms_cats,key="ms_cat")
        df_ms=df if ms_cat=="All" else df[df["Categorie"]==ms_cat]
        _ms_list=df_ms["Modele"].tolist()
        _F7X="Dassault Falcon 7X"
        _ms_def=_ms_list.index(_F7X) if _F7X in _ms_list else 0
        with msc2: ms_model_preview=st.selectbox("Aircraft model",_ms_list,index=_ms_def,key="ms_model_preview")
        _is_f7x=(ms_model_preview==_F7X)

        if not _is_f7x:
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
        _f7x_ctx=st.container() if _is_f7x else st.expander("📂 Real Example — Falcon 7X Full Market Dossier & Turnkey Program", expanded=False)
        with _f7x_ctx:
            st.caption("A genuine, in-depth example of what the € 300 Market Search becomes once paired with Menkor's turnkey acquisition service — shown here for the Falcon 7X segment (24 aircraft tracked, 2007–2022).")

            # ── Falcon 7X market ledger ──────────────────────────────────
            st.markdown('<div class="section-header">Falcon 7X Market — 24 Aircraft Tracked</div>',unsafe_allow_html=True)
            _f7x_rows=[
                ("SN 296","2022","VP-CMY","Melbourne, FL / Europe","$39,900,000",None,"1,082","268","ESP Platinum / MSP Gold","EASy II Cert 5 / Ka-Band Satcom","Fresh 48M c/w June 2026; Factory warranty baseline","Dassault Aviation"),
                ("SN 288","2020","Pending","Brussels, Belgium",None,"$33.5M","1,797","820","ESP Platinum / MSP Gold","EASy II Cert 5 / Ka-Band High Speed","1C c/w; Next major 2028; EASA CAT compliant","Boutique European Broker"),
                ("SN 287","2020","F-reg","Le Bourget, France",None,"$33.0M","1,714","800","ESP Platinum / MSP Gold","EASy II Cert 5 / Ka-Band Satcom","EASA CAT maintenance compliance; Low exposure","Corporate Fleet Sales"),
                ("SN 233","2018","N666ZL","Fort Lauderdale, FL, USA",None,"$31.0M","490","185","ESP Platinum / MSP Gold","EASy II Cert 5 / Ku/Ka-Band","Ultra-low time (490h); Bespoke custom 14-pax interior","Equus Global Aviation"),
                ("SN 259","2015","LX-reg","Amsterdam, Netherlands",None,"$25.5M","4,047","1,592","ESP Platinum / MSP","EASy II Cert 4/5 / Ka-Band Satcom","1C c/w; Next heavy 2C/16-yr due 2031","Flying Service NV"),
                ("SN 255","2015","N-reg","Dallas, TX, USA",None,"$25.0M","4,081","1,620","ESP Platinum / MSP Gold","EASy II Cert 4 / Gogo AVANCE L5","1C c/w; Mid-life gear inspection schedule","Corporate Aircraft Partners"),
                ("SN 234","2015","N-reg","Los Angeles, CA, USA",None,"$25.2M","3,650","1,480","ESP Platinum / MSP Gold","EASy II Cert 5 / SwiftBroadband + Gogo 5G","1C c/w 2023; Clean 36-month CAMP projection","Jet Transactions Inc."),
                ("SN 235","2014","N606TJ","Oxford, CT, USA",None,"$24.0M","2,925","1,803","ESP Platinum / MSP Gold","EASy II / SwiftBroadband + Gogo","1C check c/w 2022; One US corporate owner since new","Dassault Falcon Jet Corp"),
                ("SN 222","2014","N-reg","Miami, FL, USA",None,"$23.5M","3,820","1,510","ESP Platinum / MSP Gold","EASy II Cert 4 / Ka-Band Satcom","1C c/w 2022; Available for sale or lease","Private Jet Sales Miami"),
                ("SN 211","2013","N-reg","Seattle, WA, USA","$22,950,000",None,"5,009","2,930","ESP Platinum / MSP Gold","EASy II+ Cert 5 / Ka-Band High Speed","1C/2C baseline clear; Next major 3C in 2029","Zone 5 Aviation"),
                ("SN 194","2013","N194W","Atlanta, GA, USA",None,"$21.8M","4,450","1,890","ESP Platinum / MSP Gold","EASy II Cert 5 / Gogo AVANCE L5","1C c/w; Clean corporate US pedigree; No damage history","VanAllen Group"),
                ("SN 165","2012","T7-AMY","Guernsey, Channel Islands, UK",None,"$18.5M","3,574","1,151","ESP Gold (100%) / MSP Gold","EASy II / SwiftBroadband","12/24/36-Mo completed Dec 2025; 2C due ~2028","Tangmere Aircraft Sales"),
                ("SN 143","2012","Pending","Seletar, Singapore",None,"$18.0M","5,000","1,980","ESP Platinum / MSP Gold","EASy II Cert 5 / Inmarsat Satcom","Compliant EU OPS 1 Subparts K&L; 2C due 2028","Global Jet / Private Broker"),
                ("SN 173","2012","N173CN","Sarasota, FL, USA",None,"$17.5M","5,979","2,510","ESP Gold / MSP Gold","EASy II / Gogo ATG-5000","2C (16-yr) approaching in 2028; Landing gear check","Pinnacle Aviation"),
                ("SN 118","2011","LX-reg","Geneva / Dubai",None,"$18.2M","4,210","1,650","ESP Platinum / MSP Gold","EASy II Cert 5 / Ka-Band Satcom","2C inspection window due 2027; FalconCare enrolled","Global Jet Monaco/Geneva"),
                ("SN 129","2011","N-reg","St. Louis, MO, USA",None,"$18.5M","3,895","1,740","ESP Platinum / MSP Gold","EASy II / Gogo AVANCE L5","Low time for year; 2C heavy check due 2027","Jetcraft"),
                ("SN 115","2011","N506BA","Ronkonkoma, NY, USA","$17,250,000",None,"5,831","2,488","ESP Platinum / MSP Gold","EASy II+ Cert 5 / Gogo AVANCE L5","2C check / gear overhaul exposure within 18 mos","Leading Edge Aviation Solutions / Avpro"),
                ("SN 096","2010","M-reg","Geneva, Switzerland",None,"$17.0M","3,231","1,290","ESP Gold / MSP Gold","EASy II Cert 4 / SwiftBroadband","2C inspection completed 2026; Clean near-term calendar","Boutsen Aviation"),
                ("SN 076","2010","Off-Market","Paris / London",None,"$16.8M","4,890","2,150","ESP Platinum / MSP Gold","EASy II / Inmarsat SwiftBroadband","2C check c/w 2026; Clean airframe records","Hyperluxe Off-Market"),
                ("SN 048","2009","N-reg","Chicago, IL, USA",None,"$16.2M","5,120","2,240","ESP Platinum / MSP Gold","EASy II / Inmarsat Satcom","2C c/w Q2 2025; Repainted 2020; Fresh interior","Central Business Jets"),
                ("SN 033","2009","N-reg","Savannah, GA, USA",None,"$16.5M","2,458","1,120","ESP Platinum / MSP Gold","EASy II / Gogo Biz","2C inspection completed; Low cycles; Repainted 2025","Guardian Jet"),
                ("SN 008","2008","M-REEE / G-reg","Biggin Hill, London, UK",None,"$16.0M","2,568","1,145","ESP Platinum / MSP Gold","EASy II Baseline / Inmarsat Satcom","2C (16-yr) & Landing Gear O/H completed Oct 2024","Freestream Aircraft / Avpro"),
                ("SN 034","2008","OE-reg","Vienna, Austria",None,"$14.8M","6,893","3,120","ESP Gold / MSP","EASy II / SwiftBroadband","Higher total time; 2C check done; 3C due 2032","Global Jet Concept"),
                ("SN 005","2007","LX-reg","Luxembourg",None,"$13.5M","7,867","3,610","ESP Gold (Partial) / MSP","EASy II Baseline / Ku-Band WiFi","Early serial; 2C completed; High time discount; Paint 2024","Boutsen Aviation"),
            ]
            _f7x_hdr=["Serial","Year","Reg.","Location","Price / Est. FMV","TTAF","Landings","Engine Program","Avionics","Inspection Status / Key Notes","Broker"]
            _f7x_html='<div style="overflow-x:auto;border:1px solid #1A3A6E;border-radius:6px"><table style="border-collapse:collapse;width:100%;min-width:980px;font-size:.78rem">'
            _f7x_html+='<tr>'+''.join(f'<th style="position:sticky;top:0;background:#13233F;color:#8496B0;text-align:left;padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;white-space:nowrap;font-size:.68rem;letter-spacing:.04em;text-transform:uppercase">{h}</th>' for h in _f7x_hdr)+'</tr>'
            for sn,yr,reg,loc,adv,fmv,ttaf,land,eng,av,notes,brk in _f7x_rows:
                price_html=f'<span style="color:#4ADE80;font-weight:700">{adv}</span>' if adv else f'<span style="color:#8496B0;font-style:italic">Make Offer</span><div style="font-size:.7rem;color:#8496B0;font-style:italic">Est. FMV {fmv}</div>'
                _f7x_html+=(f'<tr><td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#D6E4F7;font-weight:600;white-space:nowrap">{sn}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#D6E4F7;white-space:nowrap">{yr}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0;white-space:nowrap">{reg}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0">{loc}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;white-space:nowrap">{price_html}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#D6E4F7;white-space:nowrap">{ttaf}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#D6E4F7;white-space:nowrap">{land}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0;white-space:nowrap"><span style="border:1px solid #1A3A6E;border-radius:10px;padding:.1rem .5rem;font-size:.7rem">{eng}</span></td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0;white-space:nowrap">{av}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0;max-width:260px">{notes}</td>'
                            f'<td style="padding:.5rem .6rem;border-bottom:1px solid #1A3A6E;color:#8496B0;white-space:nowrap">{brk}</td></tr>')
            _f7x_html+='</table></div>'
            st.markdown(_f7x_html,unsafe_allow_html=True)
            st.caption("Full dossiers, HD photos and direct broker introductions are provided by Menkor Aviation on request — this is the raw ledger behind every Market Search.")

            # ── Turnkey acquisition timeline ─────────────────────────────
            st.markdown('<div class="section-header" style="margin-top:1.4rem">Turnkey Acquisition Timeline — Market → AOC</div>',unsafe_allow_html=True)
            _tl_steps=[
                ("01","Market Search / Advisory — Taxes / AOC / Registration","Full market search and technical screening, run alongside early advisory on applicable taxes, AOC placement options and the target registration jurisdiction.","3–5 days","$300"),
                ("02","Preselection / First Pre-Audit","Shortlist narrowed by our B1/B2 engineers and CAMO team; first pre-audit of maintenance records, engine program status and airframe history.","3–7 days",None),
                ("03","LOI / Deposit Escrow / Pre-Inspection","Letter of Intent negotiated and signed; deposit placed in escrow; informal pre-inspection to confirm the aircraft warrants a full PPI.","5–10 days","$1,500–$3,000"),
                ("04","APA / PPI","Aircraft Purchase Agreement finalized alongside the Pre-Purchase Inspection: full technical inspection, discrepancy list, closing conditions drafted.","7–14 days","$15,000–$35,000"),
                ("05","PPI Negotiation / PPI Review","Findings reviewed; price adjustment or corrective work negotiated with the seller based on the discrepancies the inspection raised.","3–7 days",None),
                ("06","Delivering","Technical acceptance, documentation handover, ferry flight to the aircraft's new base with a type-qualified crew.","1–3 days","$5,000–$25,000"),
                ("07","Deregistration","Export Certificate of Airworthiness issued and the aircraft removed from its current registry.","5–15 days","$1,500–$3,500"),
                ("08","Deal Closing","Escrow funds released, title transferred, bill of sale recorded, final settlement between buyer and seller.","2–5 days",None),
                ("09","Registration","Import and airworthiness certification in the target jurisdiction (EASA, FAA, other), new registration issued.","10–30 days","$8,000–$20,000"),
                ("10","New AOC Registration","Aircraft added to the operator's Air Operator Certificate, operations manual amended, regulatory approvals secured.","15–45 days","$4,000–$12,000"),
            ]
            for num,title,desc,delay,cost in _tl_steps:
                _cost_html=f'<span style="margin-left:1.2rem">💰 {cost}</span>' if cost else ''
                st.markdown(f'''<div class="metric-card" style="display:flex;gap:1rem;align-items:flex-start">
                    <div style="font-size:1.3rem;font-weight:800;color:#E8C46A;min-width:34px">{num}</div>
                    <div>
                        <div style="font-size:.95rem;font-weight:700;color:#D6E4F7">{title}</div>
                        <div style="font-size:.82rem;color:#8496B0;margin-top:.2rem">{desc}</div>
                        <div style="font-size:.72rem;color:#5A6B85;margin-top:.4rem">⏱ {delay}{_cost_html}</div>
                    </div>
                </div>''',unsafe_allow_html=True)
            st.markdown('''<div class="metric-card" style="border-left:3px dashed #C9A84C;display:flex;gap:1rem;align-items:flex-start">
                <div style="font-size:1.3rem;font-weight:800;color:#E8C46A;min-width:34px">11</div>
                <div>
                    <div style="font-size:.95rem;font-weight:700;color:#D6E4F7">Cost Control on the Entire Operation</div>
                    <div style="font-size:.82rem;color:#8496B0;margin-top:.2rem">Every cost line across all ten steps is tracked and reported transparently to the client throughout the transaction, then monitored on an ongoing basis after delivery via the Aviation Cost Estimator.</div>
                    <div style="font-size:.72rem;color:#5A6B85;margin-top:.4rem">⏱ Continuous, start to finish</div>
                </div>
            </div>''',unsafe_allow_html=True)

            # ── B1/B2/CAMO technical preselection ─────────────────────────
            st.markdown('<div class="section-header" style="margin-top:1.4rem">Technical Preselection — B1/B2 &amp; CAMO</div>',unsafe_allow_html=True)
            st.caption("No aircraft on the market is offered as-is: every listing is first run through an internal technical review before it ever reaches a client presentation.")
            tpc1,tpc2=st.columns(2)
            with tpc1:
                _roles=[("B1","Airframe / Powerplant Engineer","CAMP records, ESP/MSP engine program status, SMOH, AD/SB compliance, damage and structural-repair history."),
                        ("B2","Avionics Engineer","EASy certification level, connectivity compliance (Satcom/Ka-Band), avionics modification schedules."),
                        ("CAMO","Continuing Airworthiness Mgmt","Upcoming major inspection due dates (1C/2C/3C), maintenance program, EASA/FAA regulatory compliance for the target jurisdiction.")]
                for tag,title,desc in _roles:
                    st.markdown(f'''<div class="metric-card" style="display:flex;gap:.7rem;align-items:flex-start">
                        <span style="background:#C9A84C;color:#0B1629;font-weight:800;font-size:.72rem;border-radius:5px;padding:.15rem .5rem;white-space:nowrap">{tag}</span>
                        <div><div style="font-size:.88rem;font-weight:700;color:#D6E4F7">{title}</div>
                        <div style="font-size:.78rem;color:#8496B0;margin-top:.15rem">{desc}</div></div>
                    </div>''',unsafe_allow_html=True)
            with tpc2:
                _criteria=["Mission: range, passenger count, desired cabin configuration",
                           "Target budget against advertised price / FMV",
                           "Operating base and target registration (EASA, FAA, other)",
                           "Exposure to upcoming major inspections (1C/2C/3C) and near-term maintenance budget",
                           "Engine program status (ESP Platinum/Gold, MSP) and transferability",
                           "Ownership, damage and operating history (corporate vs. charter use)"]
                _crit_html='<div class="metric-card"><div class="metric-label" style="margin-bottom:.6rem">Shortlist criteria applied</div>'
                _crit_html+=''.join(f'<div style="font-size:.82rem;color:#D6E4F7;padding:.35rem 0;border-bottom:1px solid #1A3A6E">— {c}</div>' for c in _criteria)
                _crit_html+='</div>'
                st.markdown(_crit_html,unsafe_allow_html=True)

            st.markdown('''<div class="total-banner" style="padding:1rem 1.5rem">
                <div style="font-size:1.05rem;font-weight:700;color:#E8C46A;margin-bottom:.3rem">A shortlist built around your mission</div>
                <div style="font-size:.85rem;color:#8496B0">Send us your requirements — our B1/B2 engineers and CAMO team return a reasoned shortlist before any viewing or PPI is scheduled.</div>
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

