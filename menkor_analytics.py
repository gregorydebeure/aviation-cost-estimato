"""Google Analytics 4 for a Streamlit app — consent first, one page view per browser page load, no personal or confidential data.

Streamlit re-runs the whole script at every widget change (slider, button...). Nothing here depends on the number of runs:
  * the script is injected into the PARENT page (same technique as the PWA tags) and guarded by window.parent.__menkorGA, so a re-run, or a re-created
    iframe, does nothing;
  * the single `page_view` is sent manually (send_page_view=false) behind its own guard flag, once per browser page load;
  * Google's script is NOT loaded until the visitor accepts (Consent Mode default = denied for every storage); declining loads nothing;
  * only the origin + path of the page and a fixed title are sent: query strings (?reset=<token>, ?subscribed=1, ...) never leave the browser;
  * no user_id, no e-mail, no plan, no aircraft, hours, prices or scenario values: the payload contains the measurement ID only;
  * Google signals / ad personalisation are off.
"""
from __future__ import annotations

import re

DEFAULT_MEASUREMENT_ID = "G-YN0BMF7S3M"
_ID_RE = re.compile(r"G-[A-Z0-9]{6,12}")


def measurement_id(get_secret) -> str | None:
    """None = analytics off: GA_ENABLED=0, or a malformed ID (never injected into the page)."""
    if str(get_secret("GA_ENABLED", "1")).strip() == "0":
        return None
    mid = str(get_secret("GA_MEASUREMENT_ID", DEFAULT_MEASUREMENT_ID) or "").strip()
    return mid if _ID_RE.fullmatch(mid) else None


_JS = r"""
(function(){
  var ID="__MID__", KEY="menkor_ga_consent_v1", TITLE="Aviation Cost Estimator";
  try{
    var P=window.parent, D=P.document;
    if(P.__menkorGA){return;}                 // already installed in this page load: Streamlit re-runs do nothing
    P.__menkorGA={installed:true};
    function get(){try{return P.localStorage.getItem(KEY);}catch(e){return null;}}
    function put(v){try{P.localStorage.setItem(KEY,v);}catch(e){}}
    P.dataLayer=P.dataLayer||[];
    function gtag(){P.dataLayer.push(arguments);}
    gtag('consent','default',{analytics_storage:'denied',ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied'});
    var loaded=false;
    function where(){return P.location.origin+P.location.pathname;}          // never the query string
    function referrer(){try{return D.referrer?new URL(D.referrer).origin:'';}catch(e){return '';}}
    function load(){
      if(loaded){gtag('consent','update',{analytics_storage:'granted'});P['ga-disable-'+ID]=false;return;}
      loaded=true; P['ga-disable-'+ID]=false;
      gtag('consent','update',{analytics_storage:'granted'});
      gtag('js',new Date());
      gtag('config',ID,{send_page_view:false,allow_google_signals:false,allow_ad_personalization_signals:false,page_location:where(),page_title:TITLE,page_referrer:referrer()});
      var s=D.createElement('script'); s.async=true; s.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(ID); D.head.appendChild(s);
      if(!P.__menkorGAPV){P.__menkorGAPV=true; gtag('event','page_view',{page_location:where(),page_title:TITLE,page_referrer:referrer()});}   // once per page load
    }
    function unload(){
      P['ga-disable-'+ID]=true;
      gtag('consent','update',{analytics_storage:'denied'});
      try{var host=P.location.hostname.split('.'),names=['_ga','_ga_'+ID.slice(2)];
          for(var i=0;i<names.length;i++){for(var j=0;j<host.length-1;j++){
            D.cookie=names[i]+'=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain='+host.slice(j).join('.');}
            D.cookie=names[i]+'=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';}}catch(e){}
    }
    var box=null, link=null;
    function el(tag,css,txt){var e=D.createElement(tag); e.style.cssText=css; if(txt){e.textContent=txt;} return e;}
    function closeBanner(){if(box&&box.parentNode){box.parentNode.removeChild(box);} box=null;}
    function choose(v){put(v); closeBanner(); if(v==='granted'){load();}else{unload();} showLink();}
    function showBanner(){
      if(box){return;}
      box=el('div','position:fixed;left:12px;right:12px;bottom:12px;z-index:2147483000;max-width:760px;margin:0 auto;background:#112244;color:#F0F4FB;border:1px solid #C9A84C;border-radius:8px;padding:14px 16px;font:14px/1.45 "Segoe UI",system-ui,sans-serif;box-shadow:0 4px 18px rgba(0,0,0,.5)');
      box.setAttribute('role','dialog'); box.setAttribute('aria-label','Analytics consent'); box.id='menkor-ga-banner';
      box.appendChild(el('div','margin-bottom:10px','We use Google Analytics to count visits and see which parts of the app are used. No personal or confidential data (e-mail, aircraft, hours, prices, scenarios) is sent. Nothing is loaded unless you accept, and you can change your choice at any time.'));
      var row=el('div','display:flex;gap:10px;flex-wrap:wrap');
      var yes=el('button','background:#C9A84C;color:#0B1629;border:1px solid #C9A84C;border-radius:4px;padding:6px 16px;font-weight:700;cursor:pointer','Accept'); yes.id='menkor-ga-accept';
      var no=el('button','background:#1A3A6E;color:#F0F4FB;border:1px solid #C9A84C;border-radius:4px;padding:6px 16px;font-weight:600;cursor:pointer','Decline'); no.id='menkor-ga-decline';
      yes.onclick=function(){choose('granted');}; no.onclick=function(){choose('denied');};
      row.appendChild(yes); row.appendChild(no); box.appendChild(row); D.body.appendChild(box);
    }
    function showLink(){
      if(link){return;}
      link=el('button','position:fixed;left:8px;bottom:4px;z-index:2147482000;background:transparent;color:#8496B0;border:0;font:11px "Segoe UI",system-ui,sans-serif;text-decoration:underline;cursor:pointer','Cookie settings'); link.id='menkor-ga-settings';
      link.onclick=function(){showBanner();}; D.body.appendChild(link);
    }
    var c=get();
    if(c==='granted'){load(); showLink();}
    else if(c==='denied'){P['ga-disable-'+ID]=true; showLink();}
    else{showBanner();}
  }catch(e){}
})();
"""


def ga_html(mid: str) -> str:
    """HTML for components.html(height=0). The ID is validated; nothing else is interpolated (no session or user value)."""
    if not _ID_RE.fullmatch(mid or ""):
        raise ValueError("invalid GA4 measurement ID")
    return "<script>" + _JS.replace("__MID__", mid) + "</script>"
